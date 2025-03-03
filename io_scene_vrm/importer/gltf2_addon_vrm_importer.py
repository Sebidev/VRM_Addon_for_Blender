import base64
import contextlib
import json
import math
import os.path
import re
import shutil
import struct
import tempfile
from typing import Dict, List, Optional, Set, Tuple, Union

import bgl
import bpy
import mathutils
from mathutils import Matrix, Vector

from ..common import convert, deep, gltf, shader
from ..common.deep import Json
from ..common.logging import get_logger
from ..common.version import addon_version
from ..common.vrm1 import human_bone as vrm1_human_bone
from ..common.vrm1.human_bone import HumanBoneName, HumanBoneSpecifications
from ..editor import make_armature, migration
from ..editor.extension import (
    VrmAddonArmatureExtensionPropertyGroup,
    VrmAddonBoneExtensionPropertyGroup,
)
from ..editor.mtoon1.property_group import (
    Mtoon1KhrTextureTransformPropertyGroup,
    Mtoon1SamplerPropertyGroup,
    Mtoon1TextureInfoPropertyGroup,
    Mtoon1TexturePropertyGroup,
)
from ..editor.spring_bone1.property_group import SpringBone1SpringBonePropertyGroup
from ..editor.vrm1.property_group import (
    Vrm1ExpressionPropertyGroup,
    Vrm1ExpressionsPropertyGroup,
    Vrm1FirstPersonPropertyGroup,
    Vrm1HumanBonesPropertyGroup,
    Vrm1HumanoidPropertyGroup,
    Vrm1LookAtPropertyGroup,
    Vrm1MetaPropertyGroup,
    Vrm1PropertyGroup,
)
from .abstract_base_vrm_importer import AbstractBaseVrmImporter
from .gltf2_addon_importer_user_extension import Gltf2AddonImporterUserExtension
from .vrm_parser import ParseResult, remove_unsafe_path_chars

logger = get_logger(__name__)


class RetryUsingLegacyVrmImporter(Exception):
    pass


class Gltf2AddonVrmImporter(AbstractBaseVrmImporter):
    def __init__(
        self,
        context: bpy.types.Context,
        parse_result: ParseResult,
        extract_textures_into_folder: bool,
        make_new_texture_folder: bool,
    ) -> None:
        super().__init__(
            context, parse_result, extract_textures_into_folder, make_new_texture_folder
        )
        self.import_id = Gltf2AddonImporterUserExtension.update_current_import_id()
        self.temp_object_name_count = 0
        self.object_names: Dict[int, str] = {}
        self.mesh_object_names: Dict[int, str] = {}

    def import_vrm(self) -> None:
        wm = self.context.window_manager
        wm.progress_begin(0, 9)
        try:
            affected_object = self.scene_init()
            wm.progress_update(1)
            self.import_gltf2_with_indices()
            wm.progress_update(2)
            if self.extract_textures_into_folder:
                self.extract_textures(repack=False)
            elif bpy.app.version < (3, 1):
                self.extract_textures(repack=True)

            wm.progress_update(3)
            self.use_fake_user_for_thumbnail()
            wm.progress_update(4)
            if self.parse_result.vrm1_extension:
                self.make_mtoon1_materials()
            elif self.parse_result.vrm0_extension:
                self.make_material()
            wm.progress_update(5)
            if self.parse_result.vrm1_extension:
                self.load_vrm1_extensions()
            elif self.parse_result.vrm0_extension:
                self.load_vrm0_extensions()
            wm.progress_update(6)
            self.cleaning_data()
            wm.progress_update(7)
            self.finishing(affected_object)
            wm.progress_update(8)
            self.viewport_setup()
        finally:
            try:
                Gltf2AddonImporterUserExtension.clear_current_import_id()
            finally:
                wm.progress_end()

    def assign_texture(
        self,
        texture: Mtoon1TexturePropertyGroup,
        texture_dict: Dict[str, Json],
        linear: bool,
    ) -> None:
        source = texture_dict.get("source")
        if isinstance(source, int):
            image = self.images.get(source)
            if image:
                if linear:
                    image.colorspace_settings.name = "Non-Color"
                else:
                    image.colorspace_settings.name = "sRGB"
                texture.source = image

        sampler = texture_dict.get("sampler")
        samplers = self.parse_result.json_dict.get("samplers")
        if not isinstance(sampler, int) or not isinstance(samplers, list):
            return
        if not 0 <= len(samplers) < sampler:
            return

        sampler_dict = samplers[sampler]
        if not isinstance(sampler_dict, dict):
            return

        mag_filter = sampler_dict.get("magFilter")
        if isinstance(mag_filter, int):
            mag_filter_id = Mtoon1SamplerPropertyGroup.MAG_FILTER_NUMBER_TO_ID.get(
                mag_filter
            )
            if isinstance(mag_filter_id, str):
                texture.sampler.mag_filter = mag_filter_id

        min_filter = sampler_dict.get("minFilter")
        if isinstance(min_filter, int):
            min_filter_id = Mtoon1SamplerPropertyGroup.MIN_FILTER_NUMBER_TO_ID.get(
                min_filter
            )
            if isinstance(min_filter_id, str):
                texture.sampler.min_filter = min_filter_id

        wrap_s = sampler_dict.get("wrapS")
        if isinstance(wrap_s, int):
            wrap_s_id = Mtoon1SamplerPropertyGroup.WRAP_NUMBER_TO_ID.get(wrap_s)
            if isinstance(wrap_s_id, str):
                texture.sampler.wrap_s = wrap_s_id

        wrap_t = sampler_dict.get("wrapT")
        if isinstance(wrap_t, int):
            wrap_t_id = Mtoon1SamplerPropertyGroup.WRAP_NUMBER_TO_ID.get(wrap_t)
            if isinstance(wrap_t_id, str):
                texture.sampler.wrap_t = wrap_t_id

    def assign_khr_texture_transform(
        self,
        khr_texture_transform: Mtoon1KhrTextureTransformPropertyGroup,
        khr_texture_transform_dict: Dict[str, Json],
    ) -> None:
        offset = khr_texture_transform_dict.get("offset")
        if isinstance(offset, list):
            offset = offset[:2]
            if len(offset) == 2:
                khr_texture_transform.offset = offset

        scale = khr_texture_transform_dict.get("scale")
        if isinstance(scale, list):
            scale = scale[:2]
            if len(scale) == 2:
                khr_texture_transform.scale = scale

    def assign_texture_info(
        self,
        texture_info: Mtoon1TextureInfoPropertyGroup,
        texture_info_dict: Dict[str, Json],
        non_color: bool,
    ) -> None:
        index = texture_info_dict.get("index")
        if isinstance(index, int):
            texture_dicts = self.parse_result.json_dict.get("textures")
            if isinstance(texture_dicts, list) and 0 <= index < len(texture_dicts):
                texture_dict = texture_dicts[index]
                if isinstance(texture_dict, dict):
                    self.assign_texture(texture_info.index, texture_dict, non_color)

        khr_texture_transform_dict = deep.get(
            texture_info_dict, ["extensions", "KHR_texture_transform"]
        )
        if isinstance(khr_texture_transform_dict, dict):
            self.assign_khr_texture_transform(
                texture_info.extensions.khr_texture_transform,
                khr_texture_transform_dict,
            )

    def make_mtoon1_material(
        self, material_index: int, gltf_dict: Dict[str, Json]
    ) -> None:
        mtoon_dict = deep.get(gltf_dict, ["extensions", "VRMC_materials_mtoon"])
        if not isinstance(mtoon_dict, dict):
            return
        material = self.materials.get(material_index)
        if not material:
            name = gltf_dict.get("name")
            if not isinstance(name, str):
                name = "Material"
            material = bpy.data.materials.new(name)
        self.reset_material(material)

        root = material.vrm_addon_extension.mtoon1
        root.enabled = True
        mtoon = root.extensions.vrmc_materials_mtoon

        pbr_metallic_roughness_dict = gltf_dict.get("pbrMetallicRoughness")
        if isinstance(pbr_metallic_roughness_dict, dict):
            base_color_factor = shader.rgba_or_none(
                pbr_metallic_roughness_dict.get("baseColorFactor")
            )
            if base_color_factor:
                root.pbr_metallic_roughness.base_color_factor = base_color_factor

            base_color_texture_dict = pbr_metallic_roughness_dict.get(
                "baseColorTexture"
            )
            if isinstance(base_color_texture_dict, dict):
                self.assign_texture_info(
                    root.pbr_metallic_roughness.base_color_texture,
                    base_color_texture_dict,
                    non_color=False,
                )

        alpha_mode = gltf_dict.get("alphaMode")
        if alpha_mode in root.ALPHA_MODE_IDS:
            root.alpha_mode = alpha_mode

        alpha_cutoff = gltf_dict.get("alphaCutoff")
        if isinstance(alpha_cutoff, (float, int)):
            root.alpha_cutoff = float(alpha_cutoff)

        double_sided = gltf_dict.get("doubleSided")
        if isinstance(double_sided, bool):
            root.double_sided = double_sided

        normal_texture_dict = gltf_dict.get("normalTexture")
        if isinstance(normal_texture_dict, dict):
            self.assign_texture_info(
                root.normal_texture,
                normal_texture_dict,
                non_color=True,
            )
            normal_texture_scale = normal_texture_dict.get("scale")
            if isinstance(normal_texture_scale, (float, int)):
                root.normal_texture.scale = float(normal_texture_scale)

        emissive_factor = shader.rgb_or_none(gltf_dict.get("emissiveFactor"))
        if emissive_factor:
            root.emissive_factor = emissive_factor

        emissive_texture_dict = gltf_dict.get("emissiveTexture")
        if isinstance(emissive_texture_dict, dict):
            self.assign_texture_info(
                root.emissive_texture,
                emissive_texture_dict,
                non_color=False,
            )

        shade_color_factor = shader.rgb_or_none(mtoon_dict.get("shadeColorFactor"))
        if shade_color_factor:
            mtoon.shade_color_factor = shade_color_factor

        shade_multiply_texture_dict = mtoon_dict.get("shadeMultiplyTexture")
        if isinstance(shade_multiply_texture_dict, dict):
            self.assign_texture_info(
                mtoon.shade_multiply_texture,
                shade_multiply_texture_dict,
                non_color=False,
            )

        transparent_with_z_write = mtoon_dict.get("transparentWithZWrite")
        if isinstance(transparent_with_z_write, bool):
            mtoon.transparent_with_z_write = transparent_with_z_write

        render_queue_offset_number = mtoon_dict.get("renderQueueOffsetNumber")
        if isinstance(render_queue_offset_number, (float, int)):
            mtoon.render_queue_offset_number = max(
                -9, min(9, int(render_queue_offset_number))
            )

        shading_shift_factor = mtoon_dict.get("shadingShiftFactor")
        if isinstance(shading_shift_factor, (float, int)):
            mtoon.shading_shift_factor = float(shading_shift_factor)

        shading_toony_factor = mtoon_dict.get("shadingToonyFactor")
        if isinstance(shading_toony_factor, (float, int)):
            mtoon.shading_toony_factor = float(shading_toony_factor)

        gi_equalization_factor = mtoon_dict.get("giEqualizationFactor")
        if isinstance(gi_equalization_factor, (float, int)):
            mtoon.gi_equalization_factor = float(gi_equalization_factor)

        matcap_factor = shader.rgb_or_none(mtoon_dict.get("matcapFactor"))
        if matcap_factor:
            mtoon.matcap_factor = matcap_factor

        matcap_texture_dict = mtoon_dict.get("matcapTexture")
        if isinstance(matcap_texture_dict, dict):
            self.assign_texture_info(
                mtoon.matcap_texture,
                matcap_texture_dict,
                non_color=False,
            )

        parametric_rim_color_factor = mtoon_dict.get("parametricRimColorFactor")
        if isinstance(parametric_rim_color_factor, (float, int)):
            mtoon.parametric_rim_color_factor = float(parametric_rim_color_factor)

        parametric_rim_fresnel_power_factor = mtoon_dict.get(
            "parametricRimFresnelPowerFactor"
        )
        if isinstance(parametric_rim_fresnel_power_factor, (float, int)):
            mtoon.parametric_rim_fresnel_power_factor = float(
                parametric_rim_fresnel_power_factor
            )

        parametric_rim_lift_factor = mtoon_dict.get("parametricRimLiftFactor")
        if isinstance(parametric_rim_lift_factor, (float, int)):
            mtoon.parametric_rim_lift_factor = float(parametric_rim_lift_factor)

        rim_multiply_texture_dict = mtoon_dict.get("rimMultiplyTexture")
        if isinstance(rim_multiply_texture_dict, dict):
            self.assign_texture_info(
                mtoon.rim_multiply_texture,
                rim_multiply_texture_dict,
                non_color=False,
            )

        rim_lighting_mix_factor = mtoon_dict.get("rimLightingMixFactor")
        if isinstance(rim_lighting_mix_factor, (float, int)):
            mtoon.rim_lighting_mix_factor = float(rim_lighting_mix_factor)

        outline_width_mode = mtoon_dict.get("outlineWidthMode")
        if outline_width_mode in mtoon.OUTLINE_WIDTH_MODE_IDS:
            mtoon.outline_width_mode = outline_width_mode

        outline_width_factor = mtoon_dict.get("outlineWidthFactor")
        if isinstance(outline_width_factor, (float, int)):
            mtoon.outline_width_factor = float(outline_width_factor)

        outline_width_multiply_texture_dict = mtoon_dict.get(
            "outlineWidthMultiplyTexture"
        )
        if isinstance(outline_width_multiply_texture_dict, dict):
            self.assign_texture_info(
                mtoon.outline_width_multiply_texture,
                outline_width_multiply_texture_dict,
                non_color=True,
            )

        outline_color_factor = shader.rgb_or_none(mtoon_dict.get("outlineColorFactor"))
        if outline_color_factor:
            mtoon.outline_color_factor = outline_color_factor

        outline_lighting_mix_factor = mtoon_dict.get("outlineLightingMixFactor")
        if isinstance(outline_lighting_mix_factor, (float, int)):
            mtoon.outline_lighting_mix_factor = float(outline_lighting_mix_factor)

        uv_animation_mask_texture_dict = mtoon_dict.get("uvAnimationMaskTexture")
        if isinstance(uv_animation_mask_texture_dict, dict):
            self.assign_texture_info(
                mtoon.uv_animation_mask_texture,
                uv_animation_mask_texture_dict,
                non_color=True,
            )

        uv_animation_rotation_speed_factor = mtoon_dict.get(
            "uvAnimationRotationSpeedFactor"
        )
        if isinstance(uv_animation_rotation_speed_factor, (float, int)):
            mtoon.uv_animation_rotation_speed_factor = float(
                uv_animation_rotation_speed_factor
            )

        uv_animation_scroll_x_speed_factor = mtoon_dict.get(
            "uvAnimationScrollXSpeedFactor"
        )
        if isinstance(uv_animation_scroll_x_speed_factor, (float, int)):
            mtoon.uv_animation_scroll_x_speed_factor = float(
                uv_animation_scroll_x_speed_factor
            )

        uv_animation_scroll_y_speed_factor = mtoon_dict.get(
            "uvAnimationScrollYSpeedFactor"
        )
        if isinstance(uv_animation_scroll_y_speed_factor, (float, int)):
            mtoon.uv_animation_scroll_y_speed_factor = float(
                uv_animation_scroll_y_speed_factor
            )

    def make_mtoon1_materials(self) -> None:
        material_dicts = self.parse_result.json_dict.get("materials")
        if not isinstance(material_dicts, list):
            return
        for index, material_dict in enumerate(material_dicts):
            if isinstance(material_dict, dict):
                self.make_mtoon1_material(index, material_dict)

    def find_vrm0_bone_node_indices(self) -> List[int]:
        result: List[int] = []
        vrm0_dict = self.parse_result.vrm0_extension

        first_person_bone_index = deep.get(
            vrm0_dict, ["firstPerson", "firstPersonBone"]
        )
        if isinstance(first_person_bone_index, int):
            result.append(first_person_bone_index)

        human_bone_dicts = deep.get(vrm0_dict, ["humanoid", "humanBones"])
        if isinstance(human_bone_dicts, list):
            for human_bone_dict in human_bone_dicts:
                if not isinstance(human_bone_dict, dict):
                    continue
                node_index = human_bone_dict.get("node")
                if isinstance(node_index, int):
                    result.append(node_index)

        collider_group_dicts = deep.get(
            vrm0_dict, ["secondaryAnimation", "colliderGroups"]
        )
        if isinstance(collider_group_dicts, list):
            for collider_group_dict in collider_group_dicts:
                if not isinstance(collider_group_dict, dict):
                    continue
                node_index = collider_group_dict.get("node")
                if isinstance(node_index, int):
                    result.append(node_index)

        bone_group_dicts = deep.get(vrm0_dict, ["secondaryAnimation", "boneGroups"])
        if isinstance(bone_group_dicts, list):
            for bone_group_dict in bone_group_dicts:
                if not isinstance(bone_group_dict, dict):
                    continue
                center_index = bone_group_dict.get("center")
                if isinstance(center_index, int):
                    result.append(center_index)
                bone_indices = bone_group_dict.get("bones")
                if isinstance(bone_indices, list):
                    for bone_index in bone_indices:
                        if isinstance(bone_index, int):
                            result.append(bone_index)
        return list(dict.fromkeys(result))  # Remove duplicates

    def find_vrm1_bone_node_indices(self) -> List[int]:
        result: List[int] = []
        vrm1_dict = self.parse_result.vrm1_extension
        human_bones_dict = deep.get(vrm1_dict, ["humanoid", "humanBones"])
        if isinstance(human_bones_dict, dict):
            for human_bone_dict in human_bones_dict.values():
                if not isinstance(human_bone_dict, dict):
                    continue
                node_index = human_bone_dict.get("node")
                if isinstance(node_index, int):
                    result.append(node_index)
        return list(dict.fromkeys(result))  # Remove duplicates

    def find_spring_bone1_bone_node_indices(self) -> List[int]:
        spring_bone1_dict = deep.get(
            self.parse_result.json_dict,
            ["extensions", "VRMC_springBone"],
        )
        if not isinstance(spring_bone1_dict, dict):
            return []

        result: List[int] = []

        collider_dicts = spring_bone1_dict.get("colliders")
        if isinstance(collider_dicts, list):
            for collider_dict in collider_dicts:
                if not isinstance(collider_dict, dict):
                    continue

                node_index = collider_dict.get("node")
                if isinstance(node_index, int):
                    result.append(node_index)

        spring_dicts = spring_bone1_dict.get("springs")
        if isinstance(spring_dicts, list):
            for spring_dict in spring_dicts:
                if not isinstance(spring_dict, dict):
                    continue

                center_index = spring_dict.get("center")
                if isinstance(center_index, int):
                    result.append(center_index)

                joint_dicts = spring_dict.get("joints")
                if not isinstance(joint_dicts, list):
                    continue

                for joint_dict in joint_dicts:
                    if not isinstance(joint_dict, dict):
                        continue
                    node_index = joint_dict.get("node")
                    if isinstance(node_index, int):
                        result.append(node_index)

        return list(dict.fromkeys(result))  # Remove duplicates

    def find_vrm_bone_node_indices(self) -> List[int]:
        # TODO: SkinnedMeshRenderer root <=> skin.skeleton???
        return list(
            dict.fromkeys(  # Remove duplicates
                self.find_vrm0_bone_node_indices()
                + self.find_vrm1_bone_node_indices()
                + self.find_spring_bone1_bone_node_indices()
            )
        )

    # VRM再インポートを繰り返すことでボーンが増殖しないように注意。
    # 特に注意するべきもの:
    # - ルートボーン
    # - メッシュがペアレンティングされているボーン
    def find_retain_node_indices(self, scene_dict: Dict[str, Json]) -> List[int]:
        scene_node_index_jsons = scene_dict.get("nodes")
        if not isinstance(scene_node_index_jsons, list):
            return []
        scene_node_indices = [
            index for index in scene_node_index_jsons if isinstance(index, int)
        ]
        json_dict = self.parse_result.json_dict
        node_dict_jsons = json_dict.get("nodes")
        if not isinstance(node_dict_jsons, list):
            return []
        node_dicts = [
            node_dict for node_dict in node_dict_jsons if isinstance(node_dict, dict)
        ]
        skin_dict_jsons = json_dict.get("skins")
        if not isinstance(skin_dict_jsons, list):
            skin_dict_jsons = []
        skin_dicts = [
            skin_dict for skin_dict in skin_dict_jsons if isinstance(skin_dict, dict)
        ]

        bone_node_indices = self.find_vrm_bone_node_indices()

        # シーンノードツリーのうち、hipsボーンが存在するツリーの全てのノードを集める。また、そのツリーのルートノードもボーン扱いする。
        all_scene_node_indices: List[int] = []
        hips_found = False
        for scene_node_index in scene_node_indices:
            all_scene_node_indices.clear()

            search_scene_node_indices = [scene_node_index]
            while search_scene_node_indices:
                search_scene_node_index = search_scene_node_indices.pop()
                if search_scene_node_index == self.parse_result.hips_node_index:
                    bone_node_indices.append(scene_node_index)
                    hips_found = True
                if not 0 <= search_scene_node_index < len(node_dicts):
                    continue
                node_dict = node_dicts[search_scene_node_index]
                all_scene_node_indices.append(search_scene_node_index)
                child_indices = node_dict.get("children")
                if not isinstance(child_indices, list):
                    continue
                for child_index in child_indices:
                    if not isinstance(child_index, int):
                        continue
                    if child_index in all_scene_node_indices:
                        # Avoid recursive nodes
                        continue
                    search_scene_node_indices.append(child_index)
            if hips_found:
                break
        if not hips_found:
            return []

        all_scene_node_indices = list(dict.fromkeys(all_scene_node_indices))  # Distinct

        # skinに登録されているインデックスもボーン扱いする
        for node_index in all_scene_node_indices:
            if not 0 <= node_index < len(node_dicts):
                continue
            node_dict = node_dicts[node_index]
            skin_index = node_dict.get("skin")
            if not isinstance(skin_index, int) or not 0 <= skin_index < len(skin_dicts):
                continue
            skin_dict = skin_dicts[skin_index]
            skeleton_index = skin_dict.get("skeleton")
            if isinstance(skeleton_index, int):
                bone_node_indices.append(skeleton_index)
            joint_indices = skin_dict.get("joints")
            if isinstance(joint_indices, list):
                for joint_index in joint_indices:
                    if isinstance(joint_index, int):
                        bone_node_indices.append(joint_index)

        # ボーンインデックスからシーンノードindexに入ってないヤツを削除
        for bone_node_index in list(bone_node_indices):
            if bone_node_index not in all_scene_node_indices:
                bone_node_indices.remove(bone_node_index)

        # 現在見つかっているボーンノードから、メッシュノードにぶつかるまで子供を追加
        search_bone_node_indices = list(bone_node_indices)
        while search_bone_node_indices:
            search_bone_node_index = search_bone_node_indices.pop()
            if not 0 <= search_bone_node_index < len(node_dicts):
                continue
            node_dict = node_dicts[search_bone_node_index]
            if isinstance(node_dict.get("mesh"), int):
                continue

            bone_node_indices.append(search_bone_node_index)

            child_indices = node_dict.get("children")
            if not isinstance(child_indices, list):
                continue
            for child_index in child_indices:
                if not isinstance(child_index, int):
                    continue
                if child_index in bone_node_indices:
                    continue
                search_bone_node_indices.append(child_index)

        # メッシュノードの子供にボーンノードが存在する場合は、そのメッシュノードもボーン扱いする
        bone_node_indices.extend(
            sum(
                [
                    self.find_middle_bone_indices(
                        node_dicts, bone_node_indices, bone_node_index, []
                    )
                    for bone_node_index in bone_node_indices
                ],
                [],
            )
        )

        return list(dict.fromkeys(bone_node_indices))  # Distinct

    def find_middle_bone_indices(
        self,
        node_dicts: List[Dict[str, Json]],
        bone_node_indices: List[int],
        bone_node_index: int,
        middle_bone_node_indices: List[int],
    ) -> List[int]:
        if not 0 <= bone_node_index < len(node_dicts):
            return []
        node_dict = node_dicts[bone_node_index]
        child_indices = node_dict.get("children")
        if not isinstance(child_indices, list):
            return []

        result = []
        for child_index in child_indices:
            if not isinstance(child_index, int):
                continue
            if not 0 <= child_index < len(node_dicts):
                continue
            if child_index in bone_node_indices:
                result.extend(middle_bone_node_indices)
                continue
            result.extend(
                self.find_middle_bone_indices(
                    node_dicts,
                    bone_node_indices,
                    child_index,
                    middle_bone_node_indices + [bone_node_index],
                )
            )
        return result

    def import_gltf2_with_indices(self) -> None:
        with open(self.parse_result.filepath, "rb") as f:
            json_dict, body_binary = gltf.parse_glb(f.read())

        for key in ["nodes", "materials", "meshes"]:
            if key not in json_dict or not isinstance(json_dict[key], list):
                continue
            value_dicts = json_dict.get(key)
            if not isinstance(value_dicts, list):
                continue
            for index, value_dict in enumerate(value_dicts):
                if not isinstance(value_dict, dict):
                    continue
                extras_dict = value_dict.get("extras")
                if not isinstance(extras_dict, dict):
                    extras_dict = {}
                    value_dict["extras"] = extras_dict

                extras_dict.update({self.import_id + key.capitalize(): index})
                mesh_index = value_dict.get("mesh")
                if key == "nodes" and isinstance(mesh_index, int):
                    extras_dict.update({self.import_id + "Meshes": mesh_index})

        legacy_image_name_prefix = self.import_id + "Image"
        image_dicts = json_dict.get("images")
        if bpy.app.version < (3, 1) and isinstance(image_dicts, list):
            for image_index, image_dict in enumerate(image_dicts):
                if not isinstance(image_dict, dict):
                    continue
                name = image_dict.get("name")
                if not isinstance(name, str) or not name:
                    # https://github.com/KhronosGroup/glTF-Blender-IO/blob/709630548cdc184af6ea50b2ff3ddc5450bc0af3/addons/io_scene_gltf2/blender/imp/gltf2_blender_image.py#L54
                    name = f"Image_{image_index}"
                image_dict["name"] = (
                    legacy_image_name_prefix + str(image_index) + "_" + name
                )

        mesh_dicts = json_dict.get("meshes")
        if isinstance(mesh_dicts, list):
            for mesh_dict in mesh_dicts:
                if not isinstance(mesh_dict, dict):
                    continue
                mesh_extras_dict = mesh_dict.get("extras")
                if not isinstance(mesh_extras_dict, dict):
                    mesh_extras_dict = {}
                    mesh_dict["extras"] = mesh_extras_dict
                mesh_target_names = mesh_extras_dict.get("targetNames")
                if isinstance(mesh_target_names, list):
                    continue
                primitive_dicts = mesh_dict.get("primitives")
                if not isinstance(primitive_dicts, list):
                    continue
                for primitive_dict in primitive_dicts:
                    if not isinstance(primitive_dict, dict):
                        continue
                    primitive_extras_dict = primitive_dict.get("extras")
                    if not isinstance(primitive_extras_dict, dict):
                        continue
                    primitive_target_names = primitive_extras_dict.get("targetNames")
                    if not isinstance(primitive_target_names, list):
                        continue
                    mesh_extras_dict["targetNames"] = primitive_target_names
                    break

        texture_dicts = json_dict.get("textures")
        if isinstance(texture_dicts, list) and texture_dicts:
            primitive_dicts = []

            for texture_index, _ in enumerate(texture_dicts):
                buffer_dicts = json_dict.get("buffers")
                if not isinstance(buffer_dicts, list):
                    buffer_dicts = []
                    json_dict["buffers"] = buffer_dicts
                position_buffer_index = len(buffer_dicts)
                position_buffer_bytes = struct.pack(
                    "<9f", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0
                )
                buffer_dicts.append(
                    {
                        "uri": "data:application/gltf-buffer;base64,"
                        + base64.b64encode(position_buffer_bytes).decode("ascii"),
                        "byteLength": len(position_buffer_bytes),
                    }
                )
                texcoord_buffer_index = len(buffer_dicts)
                texcoord_buffer_bytes = struct.pack("<6f", 0.0, 0.0, 1.0, 0.0, 0.0, 1.0)
                buffer_dicts.append(
                    {
                        "uri": "data:application/gltf-buffer;base64,"
                        + base64.b64encode(texcoord_buffer_bytes).decode("ascii"),
                        "byteLength": len(texcoord_buffer_bytes),
                    }
                )

                buffer_view_dicts = json_dict.get("bufferViews")
                if not isinstance(buffer_view_dicts, list):
                    buffer_view_dicts = []
                    json_dict["bufferViews"] = buffer_view_dicts
                position_buffer_view_index = len(buffer_view_dicts)
                buffer_view_dicts.append(
                    {
                        "buffer": position_buffer_index,
                        "byteOffset": 0,
                        "byteLength": len(position_buffer_bytes),
                    }
                )
                texcoord_buffer_view_index = len(buffer_view_dicts)
                buffer_view_dicts.append(
                    {
                        "buffer": texcoord_buffer_index,
                        "byteOffset": 0,
                        "byteLength": len(texcoord_buffer_bytes),
                    }
                )

                accessor_dicts = json_dict.get("accessors")
                if not isinstance(accessor_dicts, list):
                    accessor_dicts = []
                    json_dict["accessors"] = accessor_dicts
                position_accessors_index = len(accessor_dicts)
                accessor_dicts.append(
                    {
                        "bufferView": position_buffer_view_index,
                        "byteOffset": 0,
                        "type": "VEC3",
                        "componentType": bgl.GL_FLOAT,
                        "count": 3,
                        "min": [0, 0, 0],
                        "max": [1, 1, 0],
                    }
                )
                texcoord_accessors_index = len(accessor_dicts)
                accessor_dicts.append(
                    {
                        "bufferView": texcoord_buffer_view_index,
                        "byteOffset": 0,
                        "type": "VEC2",
                        "componentType": bgl.GL_FLOAT,
                        "count": 3,
                    }
                )

                material_dicts = json_dict.get("materials")
                if not isinstance(material_dicts, list):
                    material_dicts = []
                    json_dict["materials"] = material_dicts
                tex_material_index = len(material_dicts)
                material_dicts.append(
                    {
                        "name": self.temp_object_name(),
                        "emissiveTexture": {"index": texture_index},
                    }
                )
                primitive_dicts.append(
                    {
                        "attributes": {
                            "POSITION": position_accessors_index,
                            "TEXCOORD_0": texcoord_accessors_index,
                        },
                        "material": tex_material_index,
                    }
                )

            mesh_dicts = json_dict.get("meshes")
            if not isinstance(mesh_dicts, list):
                mesh_dicts = []
                json_dict["meshes"] = mesh_dicts
            tex_mesh_index = len(mesh_dicts)
            mesh_dicts.append(
                {"name": self.temp_object_name(), "primitives": primitive_dicts}
            )

            node_dicts = json_dict.get("nodes")
            if not isinstance(node_dicts, list):
                node_dicts = []
                json_dict["nodes"] = node_dicts
            tex_node_index = len(node_dicts)
            node_dicts.append({"name": self.temp_object_name(), "mesh": tex_mesh_index})

            scene_dicts = json_dict.get("scenes")
            if not isinstance(scene_dicts, list):
                scene_dicts = []
                json_dict["scenes"] = scene_dicts
            scene_dicts.append(
                {"name": self.temp_object_name(), "nodes": [tex_node_index]}
            )

        scene_dicts = json_dict.get("scenes")
        node_dicts = json_dict.get("nodes")
        if isinstance(scene_dicts, list) and isinstance(node_dicts, list):
            for scene_dict in scene_dicts:
                if not isinstance(scene_dict, dict):
                    continue
                retain_node_indices = self.find_retain_node_indices(scene_dict)
                if not retain_node_indices:
                    continue

                buffer_dicts = json_dict.get("buffers")
                if not isinstance(buffer_dicts, list):
                    buffer_dicts = []
                    json_dict["buffers"] = buffer_dicts
                position_buffer_index = len(buffer_dicts)
                position_buffer_bytes = struct.pack(
                    "<9f", 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0
                )
                buffer_dicts.append(
                    {
                        "uri": "data:application/gltf-buffer;base64,"
                        + base64.b64encode(position_buffer_bytes).decode("ascii"),
                        "byteLength": len(position_buffer_bytes),
                    }
                )
                joints_buffer_index = len(buffer_dicts)
                joints_buffer_bytes = struct.pack(
                    "<12H", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
                )
                buffer_dicts.append(
                    {
                        "uri": "data:application/gltf-buffer;base64,"
                        + base64.b64encode(joints_buffer_bytes).decode("ascii"),
                        "byteLength": len(joints_buffer_bytes),
                    }
                )
                weights_buffer_index = len(buffer_dicts)
                weights_buffer_bytes = struct.pack(
                    "<12f", 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0
                )
                buffer_dicts.append(
                    {
                        "uri": "data:application/gltf-buffer;base64,"
                        + base64.b64encode(weights_buffer_bytes).decode("ascii"),
                        "byteLength": len(weights_buffer_bytes),
                    }
                )

                buffer_view_dicts = json_dict.get("bufferViews")
                if not isinstance(buffer_view_dicts, list):
                    buffer_view_dicts = []
                    json_dict["bufferViews"] = buffer_view_dicts
                position_buffer_view_index = len(buffer_view_dicts)
                buffer_view_dicts.append(
                    {
                        "buffer": position_buffer_index,
                        "byteOffset": 0,
                        "byteLength": len(position_buffer_bytes),
                    }
                )
                joints_buffer_view_index = len(buffer_view_dicts)
                buffer_view_dicts.append(
                    {
                        "buffer": joints_buffer_index,
                        "byteOffset": 0,
                        "byteLength": len(joints_buffer_bytes),
                    }
                )
                weights_buffer_view_index = len(buffer_view_dicts)
                buffer_view_dicts.append(
                    {
                        "buffer": weights_buffer_index,
                        "byteOffset": 0,
                        "byteLength": len(weights_buffer_bytes),
                    }
                )

                accessor_dicts = json_dict.get("accessors")
                if not isinstance(accessor_dicts, list):
                    accessor_dicts = []
                    json_dict["accessors"] = accessor_dicts
                position_accessors_index = len(accessor_dicts)
                accessor_dicts.append(
                    {
                        "bufferView": position_buffer_view_index,
                        "byteOffset": 0,
                        "type": "VEC3",
                        "componentType": bgl.GL_FLOAT,
                        "count": 3,
                        "min": [0, 0, 0],
                        "max": [1, 1, 0],
                    }
                )
                joints_accessors_index = len(accessor_dicts)
                accessor_dicts.append(
                    {
                        "bufferView": joints_buffer_view_index,
                        "byteOffset": 0,
                        "type": "VEC4",
                        "componentType": bgl.GL_UNSIGNED_SHORT,
                        "count": 3,
                    }
                )
                weights_accessors_index = len(accessor_dicts)
                accessor_dicts.append(
                    {
                        "bufferView": weights_buffer_view_index,
                        "byteOffset": 0,
                        "type": "VEC4",
                        "componentType": bgl.GL_FLOAT,
                        "count": 3,
                    }
                )

                primitive_dicts = [
                    {
                        "attributes": {
                            "POSITION": position_accessors_index,
                            "JOINTS_0": joints_accessors_index,
                            "WEIGHTS_0": weights_accessors_index,
                        }
                    }
                ]

                mesh_dicts = json_dict.get("meshes")
                if not isinstance(mesh_dicts, list):
                    mesh_dicts = []
                    json_dict["meshes"] = mesh_dicts
                skin_mesh_index = len(mesh_dicts)
                mesh_dicts.append(
                    {"name": self.temp_object_name(), "primitives": primitive_dicts}
                )

                skin_dicts = json_dict.get("skins")
                if not isinstance(skin_dicts, list):
                    skin_dicts = []
                    json_dict["skins"] = skin_dicts
                skin_index = len(skin_dicts)
                skin_dicts.append({"joints": list(retain_node_indices)})

                node_dicts = json_dict.get("nodes")
                if not isinstance(node_dicts, list):
                    node_dicts = []
                    json_dict["nodes"] = node_dicts
                skin_node_index = len(node_dicts)
                node_dicts.append(
                    {
                        "name": self.temp_object_name(),
                        "mesh": skin_mesh_index,
                        "skin": skin_index,
                    }
                )

                scene_nodes = scene_dict.get("nodes")
                if not isinstance(scene_nodes, list):
                    scene_nodes = []
                    scene_dict["nodes"] = scene_nodes

                scene_nodes.append(skin_node_index)

        # glTF 2.0アドオンが未対応のエクステンションが"extensionsRequired"に含まれている場合はエラーになるのを抑止
        extensions_required = json_dict.get("extensionsRequired")
        if isinstance(extensions_required, list):
            for supported_extension in [
                "VRM",
                "VRMC_vrm",
                "VRMC_springBone",
                "VRMC_node_constraint",
                "VRMC_materials_mtoon",
                "VRMC_materials_hdr_emissiveMultiplier",
            ]:
                while supported_extension in extensions_required:
                    extensions_required.remove(supported_extension)

        if self.parse_result.spec_version_number < (1, 0):
            bone_heuristic = "FORTUNE"
        else:
            bone_heuristic = "BLENDER"
        full_vrm_import_success = False
        with tempfile.TemporaryDirectory() as temp_dir:
            indexed_vrm_filepath = os.path.join(temp_dir, "indexed.vrm")
            with open(indexed_vrm_filepath, "wb") as file:
                file.write(gltf.pack_glb(json_dict, body_binary))
            try:
                bpy.ops.import_scene.gltf(
                    filepath=indexed_vrm_filepath,
                    import_pack_images=True,
                    bone_heuristic=bone_heuristic,
                    guess_original_bind_pose=False,
                )
                full_vrm_import_success = True
            except RuntimeError:
                logger.exception(
                    f'Failed to import "{indexed_vrm_filepath}"'
                    + f' generated from "{self.parse_result.filepath}" using glTF 2.0 Add-on'
                )
                self.cleanup_gltf2_with_indices()
        if not full_vrm_import_success:
            # Some VRMs have broken animations.
            # https://github.com/vrm-c/UniVRM/issues/1522
            # https://github.com/saturday06/VRM_Addon_for_Blender/issues/58
            if "animations" in json_dict:
                del json_dict["animations"]
            with tempfile.TemporaryDirectory() as temp_dir:
                indexed_vrm_filepath = os.path.join(temp_dir, "indexed.vrm")
                with open(indexed_vrm_filepath, "wb") as file:
                    file.write(gltf.pack_glb(json_dict, body_binary))
                try:
                    bpy.ops.import_scene.gltf(
                        filepath=indexed_vrm_filepath,
                        import_pack_images=True,
                        bone_heuristic=bone_heuristic,
                        guess_original_bind_pose=False,
                    )
                except RuntimeError as e:
                    logger.exception(
                        f'Failed to import "{indexed_vrm_filepath}"'
                        + f' generated from "{self.parse_result.filepath}" using glTF 2.0 Add-on'
                        + " without animations key"
                    )
                    self.cleanup_gltf2_with_indices()
                    if self.parse_result.spec_version_number >= (1, 0):
                        raise e
                    raise RetryUsingLegacyVrmImporter() from e

        extras_node_index_key = self.import_id + "Nodes"
        for obj in self.context.selectable_objects:
            if extras_node_index_key in obj:
                node_index = obj[extras_node_index_key]
                if isinstance(node_index, int):
                    self.object_names[node_index] = obj.name
                    if isinstance(obj.data, bpy.types.Mesh):
                        self.mesh_object_names[node_index] = obj.name
                del obj[extras_node_index_key]
            data = obj.data
            if isinstance(data, bpy.types.Mesh) and extras_node_index_key in data:
                del data[extras_node_index_key]

            if not isinstance(data, bpy.types.Armature):
                continue

            for pose_bone in obj.pose.bones:
                if extras_node_index_key in pose_bone:
                    del pose_bone[extras_node_index_key]

            for bone_name, bone in data.bones.items():
                bone_node_index = bone.get(extras_node_index_key)
                if extras_node_index_key in bone:
                    del bone[extras_node_index_key]
                if not isinstance(bone_node_index, int):
                    continue
                node_dicts = self.parse_result.json_dict.get("nodes")
                if not isinstance(node_dicts, list):
                    continue
                if 0 <= bone_node_index < len(node_dicts):
                    node_dict = node_dicts[bone_node_index]
                    if isinstance(node_dict, dict):
                        node_dict["name"] = bone_name
                self.bone_names[bone_node_index] = bone_name
                if (
                    self.armature is not None
                    or bone_node_index != self.parse_result.hips_node_index
                ):
                    continue

                if self.parse_result.spec_version_number < (1, 0):
                    vrm0_humanoid = obj.data.vrm_addon_extension.vrm0.humanoid
                    vrm0_humanoid.initial_automatic_bone_assignment = False
                else:
                    vrm1_humanoid = obj.data.vrm_addon_extension.vrm1.humanoid
                    vrm1_humanoid.human_bones.initial_automatic_bone_assignment = False
                self.armature = obj

        if (
            self.armature is not None
            and self.parse_result.spec_version_number < (1, 0)
            and self.armature.rotation_mode == "QUATERNION"
        ):
            obj = self.armature
            obj.rotation_quaternion.rotate(mathutils.Euler((0.0, 0.0, math.pi), "XYZ"))
            if self.context.object is not None:
                bpy.ops.object.mode_set(mode="OBJECT")
            bpy.ops.object.select_all(action="DESELECT")
            obj.select_set(True)
            previous_active = self.context.view_layer.objects.active
            try:
                self.context.view_layer.objects.active = obj

                bone_name_to_roll = {}
                bpy.ops.object.mode_set(mode="EDIT")
                for bone in obj.data.edit_bones:
                    bone_name_to_roll[bone.name] = bone.roll
                bpy.ops.object.mode_set(mode="OBJECT")

                bpy.ops.object.transform_apply(
                    location=False, rotation=True, scale=False, properties=False
                )

                self.save_bone_child_object_world_matrices(obj)

                bpy.ops.object.mode_set(mode="EDIT")
                bones = [bone for bone in obj.data.edit_bones if not bone.parent]
                while bones:
                    bone = bones.pop(0)
                    roll = bone_name_to_roll.get(bone.name)
                    if roll is not None:
                        bone.roll = roll
                    bones.extend(bone.children)
                bpy.ops.object.mode_set(mode="OBJECT")
            finally:
                self.context.view_layer.objects.active = previous_active

        extras_mesh_index_key = self.import_id + "Meshes"
        for obj in self.context.selectable_objects:
            data = obj.data
            if not isinstance(data, bpy.types.Mesh):
                continue
            mesh_index = obj.data.get(extras_mesh_index_key)
            if isinstance(mesh_index, int):
                self.meshes[mesh_index] = obj
            else:
                mesh_index = obj.get(extras_mesh_index_key)
                if isinstance(mesh_index, int):
                    self.meshes[mesh_index] = obj

            if extras_mesh_index_key in obj:
                del obj[extras_mesh_index_key]
            if extras_mesh_index_key in obj.data:
                del obj.data[extras_mesh_index_key]

        extras_material_index_key = self.import_id + "Materials"
        for material in bpy.data.materials:
            if self.is_temp_object_name(material.name):
                continue
            material_index = material.get(extras_material_index_key)
            if extras_material_index_key in material:
                del material[extras_material_index_key]
            if isinstance(material_index, int):
                self.materials[material_index] = material

        for image in list(bpy.data.images):
            image_index = image.get(self.import_id)
            if not isinstance(image_index, int) and image.name.startswith(
                legacy_image_name_prefix
            ):
                image_index_str = "".join(
                    image.name.split(legacy_image_name_prefix)[1:]
                ).split("_", maxsplit=1)[0]
                with contextlib.suppress(ValueError):
                    image_index = int(image_index_str)
            if not isinstance(image_index, int):
                continue
            image_dicts = json_dict.get("images")
            if isinstance(image_dicts, list) and 0 <= image_index < len(image_dicts):
                # image.nameはインポート時に勝手に縮められてしまうことがあるので、jsonの値から復元する
                image_dict = image_dicts[image_index]
                indexed_image_name = None

                if isinstance(image_dict, dict):
                    indexed_image_name = image_dict.get("name")

                if isinstance(indexed_image_name, str):
                    if indexed_image_name.startswith(legacy_image_name_prefix):
                        indexed_image_name = "_".join(indexed_image_name.split("_")[1:])
                else:
                    indexed_image_name = None

                if indexed_image_name:
                    image.name = indexed_image_name
                else:
                    # https://github.com/KhronosGroup/glTF-Blender-IO/blob/709630548cdc184af6ea50b2ff3ddc5450bc0af3/addons/io_scene_gltf2/blender/imp/gltf2_blender_image.py#L54
                    image.name = f"Image_{image_index}"

            else:
                image.name = "_".join(image.name.split("_")[1:])

            self.images[image_index] = image

        if self.context.object is not None and self.context.object.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")

        while True:
            temp_object = {
                0: o
                for o in bpy.data.objects
                if o and o.users <= 1 and self.is_temp_object_name(o.name)
            }.get(0)
            if not temp_object:
                break
            bpy.data.objects.remove(temp_object)

        while True:
            temp_mesh = {
                0: m
                for m in bpy.data.meshes
                if m and m.users <= 1 and self.is_temp_object_name(m.name)
            }.get(0)
            if not temp_mesh:
                break
            bpy.data.meshes.remove(temp_mesh)

        while True:
            temp_material = {
                0: m
                for m in bpy.data.materials
                if m and m.users <= 1 and self.is_temp_object_name(m.name)
            }.get(0)
            if not temp_material:
                break
            bpy.data.materials.remove(temp_material)

        if self.armature is None:
            logger.warning("Failed to read VRM Humanoid")

    def cleanup_gltf2_with_indices(self) -> None:
        if (
            self.context.view_layer.objects.active is not None
            and self.context.view_layer.objects.active.mode != "OBJECT"
        ):
            bpy.ops.object.mode_set(mode="OBJECT")
        meshes_key = self.import_id + "Meshes"
        nodes_key = self.import_id + "Nodes"
        remove_objs = []
        for obj in list(self.context.scene.collection.objects):
            if isinstance(obj.data, bpy.types.Armature):
                for bone in obj.data.bones:
                    if nodes_key in bone:
                        remove_objs.append(obj)
                        break
                continue

            if isinstance(obj.data, bpy.types.Mesh) and (
                nodes_key in obj.data
                or meshes_key in obj.data
                or self.is_temp_object_name(obj.data.name)
            ):
                remove_objs.append(obj)
                continue

            if (
                nodes_key in obj
                or meshes_key in obj
                or self.is_temp_object_name(obj.name)
            ):
                remove_objs.append(obj)

        bpy.ops.object.select_all(action="DESELECT")
        for obj in remove_objs:
            obj.select_set(True)
        bpy.ops.object.delete()

        retry = True
        while retry:
            retry = False
            for obj in bpy.data.objects:
                if obj in remove_objs and not obj.users:
                    retry = True
                    bpy.data.objects.remove(obj, do_unlink=True)

    def temp_object_name(self) -> str:
        self.temp_object_name_count += 1
        return f"{self.import_id}Temp_{self.temp_object_name_count}_"

    def is_temp_object_name(self, name: str) -> bool:
        return name.startswith(f"{self.import_id}Temp_")

    def extract_textures(self, repack: bool) -> None:
        dir_path = os.path.abspath(self.parse_result.filepath) + ".textures"
        if self.make_new_texture_folder or repack:
            for i in range(100001):
                checking_dir_path = dir_path if i == 0 else f"{dir_path}.{i}"
                if not os.path.exists(checking_dir_path):
                    os.mkdir(checking_dir_path)
                    dir_path = checking_dir_path
                    break
        elif not os.path.exists(dir_path):
            os.mkdir(dir_path)

        if bpy.app.version >= (3, 1) and not bpy.data.filepath:
            blend_dir_path = os.path.dirname(self.parse_result.filepath)
            blend_base_path = os.path.basename(self.parse_result.filepath)
            blend_file_root, _ = os.path.splitext(blend_base_path)
            filepath = os.path.join(blend_dir_path, blend_file_root + ".temp.blend")
            for count in range(100000):
                if os.path.exists(filepath):
                    filepath = os.path.join(
                        blend_dir_path,
                        blend_file_root + ".temp" + str(count + 1) + ".blend",
                    )
                    continue
                bpy.ops.wm.save_as_mainfile(filepath=filepath)
                break

        for image_index, image in self.images.items():
            image_name = os.path.basename(image.filepath_from_user())
            if image_name:
                legacy_image_name_prefix = self.import_id + "Image"
                if image_name.startswith(legacy_image_name_prefix):
                    image_name = re.sub(
                        r"^\d+_",
                        "",
                        image_name[
                            slice(len(legacy_image_name_prefix), len(image_name))
                        ],
                    )
            if not image_name:
                image_name = image.name
            image_type = image.file_format.lower()
            if len(image_name) >= 100:
                new_image_name = "texture_too_long_name_" + str(image_index)
                logger.warning(
                    f"too long name image: {image_name} is named {new_image_name}"
                )
                image_name = new_image_name

            image_name = remove_unsafe_path_chars(image_name)
            image_path = os.path.join(dir_path, image_name)
            if not image_name.lower().endswith("." + image_type.lower()) and not (
                image_name.lower().endswith(".jpg") and image_type.lower() == "jpeg"
            ):
                image_path += "." + image_type

            written = False
            retry_limit = 100000

            for retry_count in range(retry_limit):
                root, ext = os.path.splitext(os.path.basename(image_path))
                if os.path.exists(image_path):
                    next_image_name = root + "_" + str(retry_count + 1) + ext
                    image_path = os.path.join(dir_path, next_image_name)
                    continue

                image.unpack(method="WRITE_ORIGINAL")
                with contextlib.suppress(shutil.SameFileError):
                    shutil.move(image.filepath_from_user(), image_path)
                image.filepath = image_path
                image.reload()
                if repack:
                    image.pack()

                written = True
                break

            if not written:
                logger.error(
                    f"There are more than {retry_limit} images with the same name in the folder."
                    + f" Failed to write file: {image_name}"
                )

        if repack:
            shutil.rmtree(dir_path, ignore_errors=True)

    def setup_vrm1_humanoid_bones(self) -> None:
        armature = self.armature
        if not armature:
            return
        addon_extension = armature.data.vrm_addon_extension
        if not isinstance(addon_extension, VrmAddonArmatureExtensionPropertyGroup):
            return

        Vrm1HumanBonesPropertyGroup.check_last_bone_names_and_update(
            armature.data.name, defer=False
        )

        human_bones = addon_extension.vrm1.humanoid.human_bones
        for name, human_bone in human_bones.human_bone_name_to_human_bone().items():
            if (
                human_bone.node.value
                and human_bone.node.value not in human_bone.node_candidates
            ):
                # Invalid bone structure
                return

            spec = HumanBoneSpecifications.get(name)
            if spec.requirement and not human_bone.node.value:
                # Missing required bones
                return

        previous_active = self.context.view_layer.objects.active
        previous_cursor_matrix = self.context.scene.cursor.matrix
        try:
            self.context.view_layer.objects.active = armature

            bone_name_to_human_bone_name: Dict[str, HumanBoneName] = {}
            for (
                human_bone_name,
                human_bone,
            ) in human_bones.human_bone_name_to_human_bone().items():
                if not human_bone.node.value:
                    continue
                bone_name_to_human_bone_name[human_bone.node.value] = human_bone_name

            bpy.ops.object.mode_set(mode="EDIT")

            # ボーンの子が複数ある場合そのボーン名からテールを向ける先の子ボーン名を拾えるdictを作る
            bone_name_to_main_child_bone_name: Dict[str, str] = {}
            for (
                bone_name,
                human_bone_name,
            ) in bone_name_to_human_bone_name.items():
                # 現在のアルゴリズムでは
                #
                #   head ---- node ---- leftEye
                #                   \
                #                    -- rightEye
                #
                # を上手く扱えないので、leftEyeとrightEyeは処理しない
                if human_bone_name in [HumanBoneName.RIGHT_EYE, HumanBoneName.LEFT_EYE]:
                    continue

                bone = armature.data.edit_bones.get(bone_name)
                if not bone:
                    continue
                last_human_bone_name = human_bone_name
                while True:
                    parent = bone.parent
                    if not parent:
                        break
                    parent_human_bone_name = bone_name_to_human_bone_name.get(
                        parent.name
                    )

                    if parent_human_bone_name in [
                        HumanBoneName.RIGHT_HAND,
                        HumanBoneName.LEFT_HAND,
                    ]:
                        break

                    if (
                        parent_human_bone_name == HumanBoneName.UPPER_CHEST
                        and last_human_bone_name
                        not in [HumanBoneName.HEAD, HumanBoneName.NECK]
                    ):
                        break

                    if (
                        parent_human_bone_name == HumanBoneName.CHEST
                        and last_human_bone_name
                        not in [
                            HumanBoneName.HEAD,
                            HumanBoneName.NECK,
                            HumanBoneName.UPPER_CHEST,
                        ]
                    ):
                        break

                    if (
                        parent_human_bone_name == HumanBoneName.SPINE
                        and last_human_bone_name
                        not in [
                            HumanBoneName.HEAD,
                            HumanBoneName.NECK,
                            HumanBoneName.UPPER_CHEST,
                            HumanBoneName.CHEST,
                        ]
                    ):
                        break

                    if (
                        parent_human_bone_name == HumanBoneName.HIPS
                        and last_human_bone_name != HumanBoneName.SPINE
                    ):
                        break

                    if parent_human_bone_name:
                        last_human_bone_name = parent_human_bone_name

                    bone_name_to_main_child_bone_name[parent.name] = bone.name
                    bone = parent

            # ヒューマンボーンとその先祖ボーンを得る
            human_bone_tree_bone_names: Set[str] = set()
            for bone_name in bone_name_to_human_bone_name:
                bone = armature.data.edit_bones.get(bone_name)
                while bone:
                    human_bone_tree_bone_names.add(bone.name)
                    bone = bone.parent

            bone_name_to_axis_translation: Dict[str, str] = {}

            human_bone_tree_bones = []
            non_human_bone_tree_bones = []
            constraint_node_index_to_source_index: Dict[int, int] = {}
            constraint_node_index_groups: List[Set[int]] = []
            nodes = self.parse_result.json_dict.get("nodes")
            if not isinstance(nodes, list):
                nodes = []
            for node_index, node_dict in enumerate(nodes):
                if not isinstance(node_dict, dict):
                    continue

                constraint_dict = deep.get(
                    node_dict, ["extensions", "VRMC_node_constraint", "constraint"]
                )
                if not isinstance(constraint_dict, dict):
                    continue

                object_or_bone = self.get_object_or_bone_by_node_index(node_index)
                if not object_or_bone:
                    continue

                source = deep.get(constraint_dict, ["roll", "source"])
                if not isinstance(source, int):
                    source = deep.get(constraint_dict, ["aim", "source"])
                if not isinstance(source, int):
                    source = deep.get(constraint_dict, ["rotation", "source"])
                if not isinstance(source, int):
                    continue

                constraint_node_index_to_source_index[node_index] = source

            node_indices = list(constraint_node_index_to_source_index.keys())
            while node_indices:
                node_index = node_indices.pop()
                source_index = constraint_node_index_to_source_index.get(node_index)
                if not isinstance(source_index, int):
                    continue
                node_indices.append(source_index)
                found = False
                for constraint_node_index_group in constraint_node_index_groups:
                    if node_index in constraint_node_index_group:
                        constraint_node_index_group.add(source_index)
                        found = True
                        break
                    if source_index in constraint_node_index_group:
                        constraint_node_index_group.add(node_index)
                        found = True
                        break

                if not found:
                    constraint_node_index_groups.append({node_index, source_index})

            # 軸変換時コンストレイントがついている場合にヒューマンボーンとその先祖ボーンを優先したいので、
            # それらを深さ優先で先に処理し、その後その他のボーンを深さ優先で処理する
            unsorted_bones = [
                bone for bone in armature.data.edit_bones if not bone.parent
            ]
            while unsorted_bones:
                bone = unsorted_bones.pop()
                unsorted_bones.extend(bone.children)
                if bone.name in human_bone_tree_bone_names:
                    human_bone_tree_bones.append(bone)
                else:
                    non_human_bone_tree_bones.append(bone)

            for bone in human_bone_tree_bones + non_human_bone_tree_bones:
                bone_index = {
                    0: i for i, n in self.bone_names.items() if n == bone.name
                }.get(0)
                if isinstance(bone_index, int):
                    group_axis_translation: Optional[str] = None
                    for node_index in {
                        0: g for g in constraint_node_index_groups if bone_index in g
                    }.get(0, set()):
                        object_or_bone = self.get_object_or_bone_by_node_index(
                            node_index
                        )
                        if isinstance(object_or_bone, bpy.types.PoseBone):
                            group_axis_translation = bone_name_to_axis_translation.get(
                                object_or_bone.name
                            )
                            if group_axis_translation is not None:
                                break
                    if group_axis_translation is not None:
                        bone.matrix = VrmAddonBoneExtensionPropertyGroup.translate_axis(
                            bone.matrix,
                            group_axis_translation,
                        )
                        if bone.parent and not bone.children:
                            bone.length = max(
                                bone.parent.length / 2, make_armature.MIN_BONE_LENGTH
                            )
                        bone_name_to_axis_translation[
                            bone.name
                        ] = group_axis_translation
                        continue

                main_child_bone_name = bone_name_to_main_child_bone_name.get(bone.name)
                target_vector: Optional[Vector] = None
                if main_child_bone_name:
                    main_child = [
                        bone
                        for bone in bone.children
                        if bone.name == main_child_bone_name
                    ][0]
                    target_translation = (
                        armature.matrix_world @ Matrix.Translation(main_child.head)
                    ).to_translation()
                    base_translation = (
                        armature.matrix_world @ Matrix.Translation(bone.head)
                    ).to_translation()
                    target_vector = target_translation - base_translation
                elif bone.children:
                    target_translation = Vector()
                    for child in bone.children:
                        child_translation = (
                            armature.matrix_world @ Matrix.Translation(child.head)
                        ).to_translation()
                        target_translation += child_translation
                    target_translation /= len(bone.children)
                    base_translation = (
                        armature.matrix_world @ Matrix.Translation(bone.head)
                    ).to_translation()
                    target_vector = target_translation - base_translation
                elif not bone.parent:
                    bone_name_to_axis_translation[
                        bone.name
                    ] = VrmAddonBoneExtensionPropertyGroup.AXIS_TRANSLATION_NONE_ID
                    continue
                elif bone_name_to_human_bone_name.get(bone.name) in [
                    HumanBoneName.RIGHT_EYE,
                    HumanBoneName.LEFT_EYE,
                    HumanBoneName.RIGHT_FOOT,
                    HumanBoneName.LEFT_FOOT,
                ]:
                    target_vector = Vector((0, -1, 0))
                else:
                    target_translation = (
                        armature.matrix_world @ Matrix.Translation(bone.head)
                    ).to_translation()
                    base_translation = (
                        armature.matrix_world @ Matrix.Translation(bone.parent.head)
                    ).to_translation()
                    target_vector = target_translation - base_translation

                base_rotation = (armature.matrix_world @ bone.matrix).to_quaternion()

                x_vector = Vector((1, 0, 0))
                x_vector.rotate(base_rotation)
                x_negated_vector = x_vector.copy()
                x_negated_vector.negate()
                y_vector = Vector((0, 1, 0))
                y_vector.rotate(base_rotation)
                y_negated_vector = y_vector.copy()
                y_negated_vector.negate()
                z_vector = Vector((0, 0, 1))
                z_vector.rotate(base_rotation)
                z_negated_vector = z_vector.copy()
                z_negated_vector.negate()

                cos_angle_and_axis_translations: List[Tuple[float, str]] = [
                    (
                        target_vector.dot(x_vector) / target_vector.length,
                        VrmAddonBoneExtensionPropertyGroup.AXIS_TRANSLATION_X_TO_Y_ID,
                    ),
                    (
                        target_vector.dot(y_vector) / target_vector.length,
                        VrmAddonBoneExtensionPropertyGroup.AXIS_TRANSLATION_NONE_ID,
                    ),
                    (
                        target_vector.dot(z_vector) / target_vector.length,
                        VrmAddonBoneExtensionPropertyGroup.AXIS_TRANSLATION_Z_TO_Y_ID,
                    ),
                    (
                        target_vector.dot(x_negated_vector) / target_vector.length,
                        VrmAddonBoneExtensionPropertyGroup.AXIS_TRANSLATION_MINUS_X_TO_Y_ID,
                    ),
                    (
                        target_vector.dot(y_negated_vector) / target_vector.length,
                        VrmAddonBoneExtensionPropertyGroup.AXIS_TRANSLATION_MINUS_Y_TO_Y_AROUND_Z_ID,
                    ),
                    (
                        target_vector.dot(z_negated_vector) / target_vector.length,
                        VrmAddonBoneExtensionPropertyGroup.AXIS_TRANSLATION_MINUS_Z_TO_Y_ID,
                    ),
                ]
                cos_angle, axis_translation = sorted(
                    cos_angle_and_axis_translations, reverse=True, key=lambda x: x[0]
                )[0]
                bone.matrix = VrmAddonBoneExtensionPropertyGroup.translate_axis(
                    bone.matrix,
                    axis_translation,
                )
                if bone.children:
                    bone.length = max(
                        target_vector.length * cos_angle, make_armature.MIN_BONE_LENGTH
                    )
                elif bone.parent:
                    bone.length = max(
                        bone.parent.length / 2, make_armature.MIN_BONE_LENGTH
                    )
                bone_name_to_axis_translation[bone.name] = axis_translation

            make_armature.connect_parent_tail_and_child_head_if_very_close_position(
                armature.data
            )

            bpy.ops.object.mode_set(mode="OBJECT")
            for bone_name, axis_translation in bone_name_to_axis_translation.items():
                bone = armature.data.bones.get(bone_name)
                if not bone:
                    continue
                bone.vrm_addon_extension.axis_translation = (
                    VrmAddonBoneExtensionPropertyGroup.reverse_axis_translation(
                        axis_translation
                    )
                )

            for node_index in set(constraint_node_index_to_source_index.keys()) | set(
                constraint_node_index_to_source_index.values()
            ):
                object_or_bone = self.get_object_or_bone_by_node_index(node_index)
                if not isinstance(object_or_bone, bpy.types.Object):
                    continue
                for group_node_index in {
                    0: g for g in constraint_node_index_groups if node_index in g
                }.get(0, set()):
                    group_object_or_bone = self.get_object_or_bone_by_node_index(
                        group_node_index
                    )
                    if isinstance(group_object_or_bone, bpy.types.PoseBone):
                        self.translate_object_axis(
                            object_or_bone,
                            VrmAddonBoneExtensionPropertyGroup.reverse_axis_translation(
                                group_object_or_bone.bone.vrm_addon_extension.axis_translation
                            ),
                        )
                        break
        finally:
            if self.context.view_layer.objects.active.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            self.context.view_layer.objects.active = previous_active
            self.context.scene.cursor.matrix = previous_cursor_matrix

        self.load_bone_child_object_world_matrices(armature)

    def translate_object_axis(
        self, obj: bpy.types.Object, axis_translation: str
    ) -> None:
        if (
            axis_translation
            != VrmAddonBoneExtensionPropertyGroup.AXIS_TRANSLATION_AUTO_ID
        ):
            return
        matrix = VrmAddonBoneExtensionPropertyGroup.translate_axis(
            obj.matrix_world, axis_translation
        )
        location, rotation, _ = matrix.decompose()
        matrix = Matrix.Translation(location) @ rotation.to_matrix().to_4x4()
        bpy.ops.object.select_all(action="DESELECT")
        self.context.scene.cursor.matrix = matrix
        obj.select_set(True)
        bpy.ops.object.origin_set(type="ORIGIN_CURSOR", center="MEDIAN")

        obj.vrm_addon_extension.axis_translation = (
            VrmAddonBoneExtensionPropertyGroup.reverse_axis_translation(
                axis_translation
            )
        )

    def load_vrm1_extensions(self) -> None:
        armature = self.armature
        if not armature:
            return
        addon_extension = armature.data.vrm_addon_extension
        if not isinstance(addon_extension, VrmAddonArmatureExtensionPropertyGroup):
            return
        vrm1 = addon_extension.vrm1
        if not isinstance(vrm1, Vrm1PropertyGroup):
            return

        addon_extension.spec_version = addon_extension.SPEC_VERSION_VRM1
        vrm1_extension_dict = self.parse_result.vrm1_extension

        addon_extension.addon_version = addon_version()

        textblock = bpy.data.texts.new(name="vrm.json")
        textblock.write(json.dumps(self.parse_result.json_dict, indent=4))

        self.load_vrm1_meta(vrm1.meta, vrm1_extension_dict.get("meta"))
        self.load_vrm1_humanoid(vrm1.humanoid, vrm1_extension_dict.get("humanoid"))
        self.setup_vrm1_humanoid_bones()
        self.load_vrm1_first_person(
            vrm1.first_person, vrm1_extension_dict.get("firstPerson")
        )
        self.load_vrm1_look_at(
            vrm1.look_at, vrm1_extension_dict.get("lookAt"), vrm1.humanoid
        )
        self.load_vrm1_expressions(
            vrm1.expressions, vrm1_extension_dict.get("expressions")
        )
        self.load_spring_bone1(
            addon_extension.spring_bone1,
            deep.get(self.parse_result.json_dict, ["extensions", "VRMC_springBone"]),
        )
        self.load_node_constraint1()
        migration.migrate(armature.name, defer=False)

    def load_vrm1_meta(self, meta: Vrm1MetaPropertyGroup, meta_dict: Json) -> None:
        if not isinstance(meta_dict, dict):
            return

        name = meta_dict.get("name")
        if name is not None:
            meta.vrm_name = str(name)

        version = meta_dict.get("version")
        if version is not None:
            meta.version = str(version)

        authors = meta_dict.get("authors")
        if isinstance(authors, list):
            for author in authors:
                if author is not None:
                    meta.authors.add().value = str(author)

        copyright_information = meta_dict.get("copyrightInformation")
        if copyright_information is not None:
            meta.copyright_information = str(copyright_information)

        contact_information = meta_dict.get("contactInformation")
        if contact_information is not None:
            meta.contact_information = str(contact_information)

        references = meta_dict.get("references")
        if isinstance(references, list):
            for reference in references:
                if reference is not None:
                    meta.references.add().value = str(reference)

        third_party_licenses = meta_dict.get("thirdPartyLicenses")
        if third_party_licenses is not None:
            meta.third_party_licenses = str(third_party_licenses)

        thumbnail_image_index = meta_dict.get("thumbnailImage")
        if isinstance(thumbnail_image_index, int):
            thumbnail_image = self.images.get(thumbnail_image_index)
            if thumbnail_image:
                meta.thumbnail_image = thumbnail_image

        avatar_permission = meta_dict.get("avatarPermission")
        if (
            isinstance(avatar_permission, str)
            and avatar_permission in Vrm1MetaPropertyGroup.AVATAR_PERMISSION_VALUES
        ):
            meta.avatar_permission = avatar_permission

        meta.allow_excessively_violent_usage = bool(
            meta_dict.get("allowExcessivelyViolentUsage")
        )

        meta.allow_excessively_sexual_usage = bool(
            meta_dict.get("allowExcessivelySexualUsage")
        )

        commercial_usage = meta_dict.get("commercialUsage")
        if (
            isinstance(commercial_usage, str)
            and commercial_usage in Vrm1MetaPropertyGroup.COMMERCIAL_USAGE_VALUES
        ):
            meta.commercial_usage = commercial_usage

        meta.allow_political_or_religious_usage = bool(
            meta_dict.get("allowPoliticalOrReligiousUsage")
        )

        meta.allow_antisocial_or_hate_usage = bool(
            meta_dict.get("allowAntisocialOrHateUsage")
        )

        credit_notation = meta_dict.get("creditNotation")
        if (
            isinstance(credit_notation, str)
            and credit_notation in Vrm1MetaPropertyGroup.CREDIT_NOTATION_VALUES
        ):
            meta.credit_notation = credit_notation

        meta.allow_redistribution = bool(meta_dict.get("allowRedistribution"))

        modification = meta_dict.get("modification")
        if (
            isinstance(modification, str)
            and modification in Vrm1MetaPropertyGroup.MODIFICATION_VALUES
        ):
            meta.modification = modification

        other_license_url = meta_dict.get("otherLicenseUrl")
        if other_license_url is not None:
            meta.other_license_url = str(other_license_url)

    def load_vrm1_humanoid(
        self, humanoid: Vrm1HumanoidPropertyGroup, humanoid_dict: Json
    ) -> None:
        if not isinstance(humanoid_dict, dict):
            return

        human_bones_dict = humanoid_dict.get("humanBones")
        if not isinstance(human_bones_dict, dict):
            return

        human_bone_name_to_human_bone = (
            humanoid.human_bones.human_bone_name_to_human_bone()
        )

        assigned_bone_names = []
        for human_bone_name in [
            human_bone.name
            for human_bone in vrm1_human_bone.HumanBoneSpecifications.all_human_bones
        ]:
            human_bone_dict = human_bones_dict.get(human_bone_name.value)
            if not isinstance(human_bone_dict, dict):
                continue
            node_index = human_bone_dict.get("node")
            if not isinstance(node_index, int):
                continue
            bone_name = self.bone_names.get(node_index)
            if not isinstance(bone_name, str) or bone_name in assigned_bone_names:
                continue
            human_bone_name_to_human_bone[human_bone_name].node.value = bone_name
            assigned_bone_names.append(bone_name)

    def load_vrm1_first_person(
        self,
        first_person: Vrm1FirstPersonPropertyGroup,
        first_person_dict: Json,
    ) -> None:
        if not isinstance(first_person_dict, dict):
            return

        mesh_annotation_dicts = first_person_dict.get("meshAnnotations")
        if not isinstance(mesh_annotation_dicts, list):
            mesh_annotation_dicts = []

        for mesh_annotation_dict in mesh_annotation_dicts:
            mesh_annotation = first_person.mesh_annotations.add()
            if not isinstance(mesh_annotation_dict, dict):
                continue

            node = mesh_annotation_dict.get("node")
            if isinstance(node, int):
                mesh_object_name = self.mesh_object_names.get(node)
                if isinstance(mesh_object_name, str):
                    mesh_annotation.node.value = mesh_object_name

            type_ = mesh_annotation_dict.get("type")
            if type_ in ["auto", "both", "thirdPersonOnly", "firstPersonOnly"]:
                mesh_annotation.type = type_

    def load_vrm1_look_at(
        self,
        look_at: Vrm1LookAtPropertyGroup,
        look_at_dict: Json,
        humanoid: Vrm1HumanoidPropertyGroup,
    ) -> None:
        if not isinstance(look_at_dict, dict):
            return
        armature = self.armature
        if armature is None:
            return
        offset_from_head_bone = convert.vrm_json_array_to_float_vector(
            look_at_dict.get("offsetFromHeadBone"), [0, 0, 0]
        )
        head_bone = armature.data.bones.get(humanoid.human_bones.head.node.value)
        if head_bone:
            axis_translation = head_bone.vrm_addon_extension.axis_translation
            offset_from_head_bone = VrmAddonBoneExtensionPropertyGroup.translate_axis(
                Matrix.Translation(offset_from_head_bone),
                VrmAddonBoneExtensionPropertyGroup.reverse_axis_translation(
                    axis_translation
                ),
            ).to_translation()
        look_at.offset_from_head_bone = offset_from_head_bone

        type_ = look_at_dict.get("type")
        if type_ in ["bone", "expression"]:
            look_at.type = type_

        for (range_map, range_map_dict) in [
            (
                look_at.range_map_horizontal_inner,
                look_at_dict.get("rangeMapHorizontalInner"),
            ),
            (
                look_at.range_map_horizontal_outer,
                look_at_dict.get("rangeMapHorizontalOuter"),
            ),
            (
                look_at.range_map_vertical_down,
                look_at_dict.get("rangeMapVerticalDown"),
            ),
            (
                look_at.range_map_vertical_up,
                look_at_dict.get("rangeMapVerticalUp"),
            ),
        ]:
            if not isinstance(range_map_dict, dict):
                continue

            input_max_value = range_map_dict.get("inputMaxValue")
            if isinstance(input_max_value, (float, int)):
                range_map.input_max_value = float(input_max_value)

            output_scale = range_map_dict.get("outputScale")
            if isinstance(output_scale, (float, int)):
                range_map.output_scale = float(output_scale)

    def load_vrm1_expression(
        self,
        expression: Vrm1ExpressionPropertyGroup,
        expression_dict: Json,
    ) -> None:
        if not isinstance(expression_dict, dict):
            return

        morph_target_bind_dicts = expression_dict.get("morphTargetBinds")
        if not isinstance(morph_target_bind_dicts, list):
            morph_target_bind_dicts = []

        for morph_target_bind_dict in morph_target_bind_dicts:
            if not isinstance(morph_target_bind_dict, dict):
                continue

            morph_target_bind = expression.morph_target_binds.add()

            weight = morph_target_bind_dict.get("weight")
            if not isinstance(weight, (int, float)):
                weight = 0

            morph_target_bind.weight = weight

            node_index = morph_target_bind_dict.get("node")
            if not isinstance(node_index, int):
                continue

            mesh_obj = self.meshes.get(node_index)
            if not mesh_obj:
                continue

            morph_target_bind.node.value = mesh_obj.name
            index = morph_target_bind_dict.get("index")
            if not isinstance(index, int):
                continue

            if 1 <= (index + 1) < len(mesh_obj.data.shape_keys.key_blocks):
                morph_target_bind.index = mesh_obj.data.shape_keys.key_blocks.keys()[
                    index + 1
                ]

        material_color_bind_dicts = expression_dict.get("materialColorBinds")
        if not isinstance(material_color_bind_dicts, list):
            material_color_bind_dicts = []

        for material_color_bind_dict in material_color_bind_dicts:
            material_color_bind = expression.material_color_binds.add()

            if not isinstance(material_color_bind_dict, dict):
                continue

            material_index = material_color_bind_dict.get("material")
            if isinstance(material_index, int):
                material = self.materials.get(material_index)
                if material:
                    material_color_bind.material = material

            type_ = material_color_bind_dict.get("type")
            if type_ in [
                "color",
                "emissionColor",
                "shadeColor",
                "rimColor",
                "outlineColor",
            ]:
                material_color_bind.type = type_

            target_value = material_color_bind_dict.get("targetValue")
            if not isinstance(target_value, list):
                target_value = []
            target_value = [
                float(v) if isinstance(v, (float, int)) else 0.0 for v in target_value
            ]
            while len(target_value) < 4:
                target_value.append(0.0)
            material_color_bind.target_value = target_value[:4]

        texture_transform_bind_dicts = expression_dict.get("textureTransformBinds")
        if not isinstance(texture_transform_bind_dicts, list):
            texture_transform_bind_dicts = []
        for texture_transform_bind_dict in texture_transform_bind_dicts:
            texture_transform_bind = expression.texture_transform_binds.add()

            if not isinstance(texture_transform_bind_dict, dict):
                continue

            material_index = texture_transform_bind_dict.get("material")
            if isinstance(material_index, int):
                material = self.materials.get(material_index)
                if material:
                    texture_transform_bind.material = material

            texture_transform_bind.scale = convert.vrm_json_array_to_float_vector(
                texture_transform_bind_dict.get("scale"), [1, 1]
            )

            texture_transform_bind.offset = convert.vrm_json_array_to_float_vector(
                texture_transform_bind_dict.get("offset"), [0, 0]
            )

        is_binary = expression_dict.get("isBinary")
        if isinstance(is_binary, bool):
            expression.is_binary = is_binary

        override_blink = expression_dict.get("overrideBlink")
        if (
            isinstance(override_blink, str)
            and override_blink
            in Vrm1ExpressionPropertyGroup.EXPRESSION_OVERRIDE_TYPE_VALUES
        ):
            expression.override_blink = override_blink

        override_look_at = expression_dict.get("overrideLookAt")
        if (
            isinstance(override_look_at, str)
            and override_look_at
            in Vrm1ExpressionPropertyGroup.EXPRESSION_OVERRIDE_TYPE_VALUES
        ):
            expression.override_look_at = override_look_at

        override_mouth = expression_dict.get("overrideMouth")
        if (
            isinstance(override_mouth, str)
            and override_mouth
            in Vrm1ExpressionPropertyGroup.EXPRESSION_OVERRIDE_TYPE_VALUES
        ):
            expression.override_mouth = override_mouth

    def load_vrm1_expressions(
        self,
        expressions: Vrm1ExpressionsPropertyGroup,
        expressions_dict: Json,
    ) -> None:
        if not isinstance(expressions_dict, dict):
            return

        preset_dict = expressions_dict.get("preset")
        if isinstance(preset_dict, dict):
            for (
                preset_name,
                expression,
            ) in expressions.preset_name_to_expression_dict().items():
                self.load_vrm1_expression(expression, preset_dict.get(preset_name))

        custom_dict = expressions_dict.get("custom")
        if isinstance(custom_dict, dict):
            for custom_name, expression_dict in custom_dict.items():
                expression = expressions.custom.add()
                expression.custom_name = custom_name
                self.load_vrm1_expression(expression.expression, expression_dict)

    def load_spring_bone1_colliders(
        self,
        spring_bone: SpringBone1SpringBonePropertyGroup,
        spring_bone_dict: Dict[str, Json],
        armature: bpy.types.Object,
    ) -> None:
        collider_dicts = spring_bone_dict.get("colliders")
        if not isinstance(collider_dicts, list):
            collider_dicts = []

        for collider_dict in collider_dicts:
            if bpy.ops.vrm.add_spring_bone1_collider(armature_name=armature.name) != {
                "FINISHED"
            }:
                raise Exception(
                    f'Failed to add spring bone 1.0 collider to "{armature.name}"'
                )

            collider = spring_bone.colliders[-1]

            if not isinstance(collider_dict, dict):
                continue

            bone: Optional[bpy.types.Bone] = None
            node_index = collider_dict.get("node")
            if isinstance(node_index, int):
                bone_name = self.bone_names.get(node_index)
                if isinstance(bone_name, str):
                    collider.node.value = bone_name
                    collider.bpy_object.name = f"{bone_name} Collider"
                    bone = armature.data.bones.get(collider.node.value)

            shape_dict = collider_dict.get("shape")
            if not isinstance(shape_dict, dict):
                continue

            shape = collider.shape

            sphere_dict = shape_dict.get("sphere")
            if isinstance(sphere_dict, dict):
                collider.shape_type = collider.SHAPE_TYPE_SPHERE
                offset = convert.vrm_json_array_to_float_vector(
                    sphere_dict.get("offset"), [0, 0, 0]
                )
                if bone:
                    axis_translation = bone.vrm_addon_extension.axis_translation
                    offset = Vector(
                        offset
                    ) @ VrmAddonBoneExtensionPropertyGroup.translate_axis(
                        Matrix(),
                        VrmAddonBoneExtensionPropertyGroup.reverse_axis_translation(
                            axis_translation
                        ),
                    )
                shape.sphere.offset = offset
                radius = sphere_dict.get("radius")
                if isinstance(radius, (float, int)):
                    shape.sphere.radius = float(radius)
                continue

            capsule_dict = shape_dict.get("capsule")
            if not isinstance(capsule_dict, dict):
                continue

            collider.shape_type = collider.SHAPE_TYPE_CAPSULE

            offset = convert.vrm_json_array_to_float_vector(
                capsule_dict.get("offset"), [0, 0, 0]
            )
            if bone:
                axis_translation = bone.vrm_addon_extension.axis_translation
                offset = Vector(
                    offset
                ) @ VrmAddonBoneExtensionPropertyGroup.translate_axis(
                    Matrix(),
                    VrmAddonBoneExtensionPropertyGroup.reverse_axis_translation(
                        axis_translation
                    ),
                )
            shape.capsule.offset = offset

            radius = capsule_dict.get("radius")
            if isinstance(radius, (float, int)):
                shape.capsule.radius = float(radius)

            tail = convert.vrm_json_array_to_float_vector(
                capsule_dict.get("tail"), [0, 0, 0]
            )
            if bone:
                axis_translation = bone.vrm_addon_extension.axis_translation
                tail = Vector(tail) @ VrmAddonBoneExtensionPropertyGroup.translate_axis(
                    Matrix(),
                    VrmAddonBoneExtensionPropertyGroup.reverse_axis_translation(
                        axis_translation
                    ),
                )
            shape.capsule.tail = tail

        for collider in spring_bone.colliders:
            collider.reset_bpy_object(self.context, self.armature)

        if spring_bone.colliders:
            colliders_collection = bpy.data.collections.new("Colliders")
            self.context.scene.collection.children.link(colliders_collection)
            for collider in spring_bone.colliders:
                colliders_collection.objects.link(collider.bpy_object)
                if collider.bpy_object.name in self.context.scene.collection.objects:
                    self.context.scene.collection.objects.unlink(collider.bpy_object)
                for child in collider.bpy_object.children:
                    colliders_collection.objects.link(child)
                    if child.name in self.context.scene.collection.objects:
                        self.context.scene.collection.objects.unlink(child)

    def load_spring_bone1_collider_groups(
        self,
        spring_bone: SpringBone1SpringBonePropertyGroup,
        spring_bone_dict: Dict[str, Json],
        armature_name: str,
    ) -> None:
        collider_group_dicts = spring_bone_dict.get("colliderGroups")
        if not isinstance(collider_group_dicts, list):
            collider_group_dicts = []

        for collider_group_index, collider_group_dict in enumerate(
            collider_group_dicts
        ):
            if bpy.ops.vrm.add_spring_bone1_collider_group(
                armature_name=armature_name
            ) != {"FINISHED"}:
                raise Exception(
                    f"Failed to add spring bone 1.0 collider group to {armature_name}"
                )

            if not isinstance(collider_group_dict, dict):
                continue

            collider_group = spring_bone.collider_groups[-1]

            name = collider_group_dict.get("name")
            if isinstance(name, str):
                collider_group.vrm_name = name

            collider_indices = collider_group_dict.get("colliders")
            if not isinstance(collider_indices, list):
                continue

            for collider_index in collider_indices:
                if bpy.ops.vrm.add_spring_bone1_collider_group_collider(
                    armature_name=armature_name,
                    collider_group_index=collider_group_index,
                ) != {"FINISHED"}:
                    raise Exception(
                        "Failed to assign spring bone 1.0 collider to collider group "
                        + f"{collider_group_index} in {armature_name}"
                    )
                if not isinstance(collider_index, int):
                    continue
                if not 0 <= collider_index < len(spring_bone.colliders):
                    continue
                collider = spring_bone.colliders[collider_index]
                if not collider:
                    continue
                collider_reference = collider_group.colliders[-1]
                collider_reference.collider_name = collider.name

    def load_spring_bone1_springs(
        self,
        spring_bone: SpringBone1SpringBonePropertyGroup,
        spring_bone_dict: Dict[str, Json],
        armature_name: str,
    ) -> None:
        spring_dicts = spring_bone_dict.get("springs")
        if not isinstance(spring_dicts, list):
            spring_dicts = []

        for spring_dict in spring_dicts:
            if bpy.ops.vrm.add_spring_bone1_spring(armature_name=armature_name) != {
                "FINISHED"
            } or not isinstance(spring_dict, dict):
                continue

            spring = spring_bone.springs[-1]

            name = spring_dict.get("name")
            if isinstance(name, str):
                spring.vrm_name = name

            center_index = spring_dict.get("center")
            if isinstance(center_index, int):
                bone_name = self.bone_names.get(center_index)
                if bone_name:
                    spring.center.value = bone_name

            joint_dicts = spring_dict.get("joints")
            if not isinstance(joint_dicts, list):
                joint_dicts = []
            for joint_dict in joint_dicts:
                if bpy.ops.vrm.add_spring_bone1_spring_joint(
                    armature_name=armature_name,
                    spring_index=len(spring_bone.springs) - 1,
                ) != {"FINISHED"}:
                    continue
                if not isinstance(joint_dict, dict):
                    continue

                joint = spring.joints[-1]

                node_index = joint_dict.get("node")
                if isinstance(node_index, int):
                    bone_name = self.bone_names.get(node_index)
                    if bone_name:
                        joint.node.value = bone_name

                hit_radius = joint_dict.get("hitRadius")
                if isinstance(hit_radius, (int, float)):
                    joint.hit_radius = hit_radius

                stiffness = joint_dict.get("stiffness")
                if isinstance(stiffness, (int, float)):
                    joint.stiffness = stiffness

                gravity_power = joint_dict.get("gravityPower")
                if isinstance(gravity_power, (int, float)):
                    joint.gravity_power = gravity_power

                joint.gravity_dir = convert.vrm_json_array_to_float_vector(
                    joint_dict.get("gravityDir"),
                    [0.0, -1.0, 0.0],
                )

                drag_force = joint_dict.get("dragForce")
                if isinstance(drag_force, (int, float)):
                    joint.drag_force = drag_force

            collider_group_indices = spring_dict.get("colliderGroups")
            if not isinstance(collider_group_indices, list):
                collider_group_indices = []
            for collider_group_index in collider_group_indices:
                if bpy.ops.vrm.add_spring_bone1_spring_collider_group(
                    armature_name=armature_name,
                    spring_index=len(spring_bone.springs) - 1,
                ) != {"FINISHED"}:
                    continue
                if not isinstance(collider_group_index, int):
                    continue
                if not 0 <= collider_group_index < len(spring_bone.collider_groups):
                    continue
                collider_group = spring_bone.collider_groups[collider_group_index]
                if not collider_group:
                    continue
                collider_group_reference = spring.collider_groups[-1]
                collider_group_reference.collider_group_name = collider_group.name

    def load_spring_bone1(
        self,
        spring_bone: SpringBone1SpringBonePropertyGroup,
        spring_bone_dict: Json,
    ) -> None:
        if not isinstance(spring_bone_dict, dict):
            return
        armature = self.armature
        if armature is None:
            raise ValueError("armature is None")

        self.load_spring_bone1_colliders(spring_bone, spring_bone_dict, armature)

        self.load_spring_bone1_collider_groups(
            spring_bone,
            spring_bone_dict,
            armature.name,
        )

        self.load_spring_bone1_springs(
            spring_bone,
            spring_bone_dict,
            armature.name,
        )

    def get_object_or_bone_by_node_index(
        self, node_index: int
    ) -> Union[bpy.types.Object, bpy.types.PoseBone, None]:
        object_name = self.object_names.get(node_index)
        bone_name = self.bone_names.get(node_index)
        if object_name is not None:
            return bpy.data.objects.get(object_name)
        if self.armature and bone_name is not None:
            return self.armature.pose.bones.get(bone_name)
        return None

    def load_node_constraint1(
        self,
    ) -> None:
        armature = self.armature
        if not armature:
            return

        nodes = self.parse_result.json_dict.get("nodes")
        if not isinstance(nodes, list):
            nodes = []
        for node_index, node_dict in enumerate(nodes):
            if not isinstance(node_dict, dict):
                continue

            constraint_dict = deep.get(
                node_dict, ["extensions", "VRMC_node_constraint", "constraint"]
            )
            if not isinstance(constraint_dict, dict):
                continue

            roll_dict = constraint_dict.get("roll")
            aim_dict = constraint_dict.get("aim")
            rotation_dict = constraint_dict.get("rotation")

            object_or_bone = self.get_object_or_bone_by_node_index(node_index)
            if not object_or_bone:
                continue

            axis_translation = (
                VrmAddonBoneExtensionPropertyGroup.reverse_axis_translation(
                    object_or_bone.bone.vrm_addon_extension.axis_translation
                    if isinstance(object_or_bone, bpy.types.PoseBone)
                    else object_or_bone.vrm_addon_extension.axis_translation
                )
            )

            if isinstance(roll_dict, dict):
                constraint = object_or_bone.constraints.new(type="COPY_ROTATION")
                constraint.mix_mode = "ADD"
                constraint.owner_space = "LOCAL"
                constraint.target_space = "LOCAL"
                roll_axis = roll_dict.get("rollAxis")
                if isinstance(object_or_bone, bpy.types.PoseBone) and isinstance(
                    roll_axis, str
                ):
                    roll_axis = VrmAddonBoneExtensionPropertyGroup.node_constraint_roll_axis_translation(
                        axis_translation,
                        roll_axis,
                    )
                constraint.use_x = False
                constraint.use_y = False
                constraint.use_z = False
                if roll_axis == "X":
                    constraint.use_x = True
                elif roll_axis == "Y":
                    constraint.use_y = True
                elif roll_axis == "Z":
                    constraint.use_z = True
                weight = roll_dict.get("weight")
                if isinstance(weight, (int, float)):
                    constraint.influence = weight
                source_index = roll_dict.get("source")
            elif isinstance(aim_dict, dict):
                constraint = object_or_bone.constraints.new(type="DAMPED_TRACK")
                aim_axis = aim_dict.get("aimAxis")
                if isinstance(aim_axis, str) and isinstance(
                    object_or_bone, bpy.types.PoseBone
                ):
                    aim_axis = VrmAddonBoneExtensionPropertyGroup.node_constraint_aim_axis_translation(
                        axis_translation,
                        aim_axis,
                    )
                if isinstance(aim_axis, str):
                    track_axis = convert.VRM_AIM_AXIS_TO_BPY_TRACK_AXIS.get(aim_axis)
                    if track_axis:
                        constraint.track_axis = track_axis
                weight = aim_dict.get("weight")
                if isinstance(weight, (int, float)):
                    constraint.influence = weight
                source_index = aim_dict.get("source")
            elif isinstance(rotation_dict, dict):
                constraint = object_or_bone.constraints.new(type="COPY_ROTATION")
                constraint.mix_mode = "ADD"
                constraint.owner_space = "LOCAL"
                constraint.target_space = "LOCAL"
                constraint.use_x = True
                constraint.use_y = True
                constraint.use_z = True
                weight = rotation_dict.get("weight")
                if isinstance(weight, (int, float)):
                    constraint.influence = weight
                source_index = rotation_dict.get("source")
            else:
                continue

            if isinstance(source_index, int):
                source = self.get_object_or_bone_by_node_index(source_index)
                if isinstance(source, bpy.types.Object):
                    constraint.target = source
                elif isinstance(source, bpy.types.PoseBone):
                    constraint.target = armature
                    constraint.subtarget = source.name
