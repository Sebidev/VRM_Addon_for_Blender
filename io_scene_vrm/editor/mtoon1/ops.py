import math
from sys import float_info
from typing import Optional, Set, Tuple, cast

import bpy
from bpy_extras.io_utils import ImportHelper

from ...common import convert, shader
from .. import search
from .property_group import (
    Mtoon1BaseColorTextureInfoPropertyGroup,
    Mtoon1EmissiveTextureInfoPropertyGroup,
    Mtoon1MatcapTextureInfoPropertyGroup,
    Mtoon1MaterialPropertyGroup,
    Mtoon1NormalTextureInfoPropertyGroup,
    Mtoon1OutlineWidthMultiplyTextureInfoPropertyGroup,
    Mtoon1RimMultiplyTextureInfoPropertyGroup,
    Mtoon1SamplerPropertyGroup,
    Mtoon1ShadeMultiplyTextureInfoPropertyGroup,
    Mtoon1ShadingShiftTextureInfoPropertyGroup,
    Mtoon1TextureInfoPropertyGroup,
    Mtoon1UvAnimationMaskTextureInfoPropertyGroup,
    reset_shader_node_group,
)


class VRM_OT_convert_material_to_mtoon1(bpy.types.Operator):  # type: ignore[misc] # noqa: N801
    bl_idname = "vrm.convert_material_to_mtoon1"
    bl_label = "Convert Material to MToon 1.0"
    bl_description = "Convert Material to MToon 1.0"
    bl_options = {"REGISTER", "UNDO"}

    material_name: bpy.props.StringProperty(  # type: ignore[valid-type]
        options={"HIDDEN"}  # noqa: F821
    )

    def execute(self, context: bpy.types.Context) -> Set[str]:
        material = bpy.data.materials.get(self.material_name)
        if not isinstance(material, bpy.types.Material):
            return {"CANCELLED"}
        self.convert_material_to_mtoon1(context, material)
        return {"FINISHED"}

    @staticmethod
    def assign_mtoon_unversioned_image(
        texture_info: Mtoon1TextureInfoPropertyGroup,
        image_name_and_sampler_type: Optional[Tuple[str, int, int]],
        uv_offset: Tuple[float, float],
        uv_scale: Tuple[float, float],
    ) -> None:
        texture_info.extensions.khr_texture_transform.offset = uv_offset
        texture_info.extensions.khr_texture_transform.scale = uv_scale

        if image_name_and_sampler_type is None:
            return

        image_name, wrap_number, filter_number = image_name_and_sampler_type
        image = bpy.data.images.get(image_name)
        if not image:
            return

        texture_info.index.source = image

        mag_filter = Mtoon1SamplerPropertyGroup.MAG_FILTER_NUMBER_TO_ID.get(
            filter_number
        )
        if mag_filter:
            texture_info.index.sampler.mag_filter = mag_filter

        min_filter = Mtoon1SamplerPropertyGroup.MIN_FILTER_NUMBER_TO_ID.get(
            filter_number
        )
        if min_filter:
            texture_info.index.sampler.min_filter = min_filter

        wrap = Mtoon1SamplerPropertyGroup.WRAP_NUMBER_TO_ID.get(wrap_number)
        if wrap:
            texture_info.index.sampler.wrap_s = wrap
            texture_info.index.sampler.wrap_t = wrap

    def convert_material_to_mtoon1(
        self, context: bpy.types.Context, material: bpy.types.Material
    ) -> None:
        node = search.vrm_shader_node(material)
        if (
            isinstance(node, bpy.types.Node)
            and node.node_tree["SHADER"] == "MToon_unversioned"
        ):
            self.convert_mtoon_unversioned_to_mtoon1(context, material, node)
            return

        reset_shader_node_group(context, material)

    def convert_mtoon_unversioned_to_mtoon1(
        self,
        context: bpy.types.Context,
        material: bpy.types.Material,
        node: bpy.types.Node,
    ) -> None:
        transparent_with_z_write = False
        alpha_cutoff: Optional[float] = 0.5
        if material.blend_method == "OPAQUE":
            alpha_mode = Mtoon1MaterialPropertyGroup.ALPHA_MODE_OPAQUE
        elif material.blend_method == "CLIP":
            alpha_cutoff = shader.get_float_value(node, "CutoffRate", 0, float_info.max)
            if alpha_cutoff is None:
                alpha_cutoff = 0.5
            alpha_mode = Mtoon1MaterialPropertyGroup.ALPHA_MODE_MASK
        else:
            alpha_mode = Mtoon1MaterialPropertyGroup.ALPHA_MODE_BLEND
            transparent_with_z_write_float = shader.get_float_value(
                node, "TransparentWithZWrite"
            )
            transparent_with_z_write = (
                transparent_with_z_write_float is not None
                and math.fabs(transparent_with_z_write_float) >= float_info.epsilon
            )

        base_color_factor = shader.get_rgba_value(node, "DiffuseColor", 0.0, 1.0) or (
            0,
            0,
            0,
            1,
        )
        base_color_texture = shader.get_image_name_and_sampler_type(
            node,
            "MainTexture",
        )

        uv_offset = (0.0, 0.0)
        uv_scale = (1.0, 1.0)

        main_texture_socket = node.inputs.get("MainTexture")
        if (
            main_texture_socket
            and main_texture_socket.links
            and main_texture_socket.links[0]
            and main_texture_socket.links[0].from_node
            and main_texture_socket.links[0].from_node.inputs
            and main_texture_socket.links[0].from_node.inputs[0]
            and main_texture_socket.links[0].from_node.inputs[0].links
            and main_texture_socket.links[0].from_node.inputs[0].links[0]
            and main_texture_socket.links[0].from_node.inputs[0].links[0].from_node
        ):
            mapping_node = (
                main_texture_socket.links[0].from_node.inputs[0].links[0].from_node
            )
            if isinstance(mapping_node, bpy.types.ShaderNodeMapping):
                uv_offset = (
                    float(mapping_node.inputs["Location"].default_value[0]),
                    float(mapping_node.inputs["Location"].default_value[1]),
                )
                uv_scale = (
                    float(mapping_node.inputs["Scale"].default_value[0]),
                    float(mapping_node.inputs["Scale"].default_value[1]),
                )

        shade_color_factor = shader.get_rgb_value(node, "ShadeColor", 0.0, 1.0) or (
            0,
            0,
            0,
        )
        shade_multiply_texture = shader.get_image_name_and_sampler_type(
            node,
            "ShadeTexture",
        )
        normal_texture = shader.get_image_name_and_sampler_type(
            node,
            "NormalmapTexture",
        )
        if not normal_texture:
            normal_texture = shader.get_image_name_and_sampler_type(
                node,
                "NomalmapTexture",
            )
        normal_texture_scale = shader.get_float_value(node, "BumpScale")

        shading_shift_0x = shader.get_float_value(node, "ShadeShift")
        if shading_shift_0x is None:
            shading_shift_0x = 0.0

        shading_toony_0x = shader.get_float_value(node, "ShadeToony")
        if shading_toony_0x is None:
            shading_toony_0x = 0.0

        shading_shift_factor = convert.mtoon_shading_shift_0_to_1(
            shading_toony_0x, shading_shift_0x
        )

        shading_toony_factor = convert.mtoon_shading_toony_0_to_1(
            shading_toony_0x, shading_shift_0x
        )

        gi_equalization_0x = shader.get_float_value(node, "IndirectLightIntensity")
        gi_equalization_factor = None
        if gi_equalization_0x is not None:
            gi_equalization_factor = convert.mtoon_intensity_to_gi_equalization(
                gi_equalization_0x
            )

        emissive_factor = shader.get_rgb_value(node, "EmissionColor", 0.0, 1.0) or (
            0,
            0,
            0,
        )
        emissive_texture = shader.get_image_name_and_sampler_type(
            node,
            "Emission_Texture",
        )
        matcap_texture = shader.get_image_name_and_sampler_type(
            node,
            "SphereAddTexture",
        )

        parametric_rim_color_factor = shader.get_rgb_value(node, "RimColor", 0.0, 1.0)
        parametric_rim_fresnel_power_factor = shader.get_float_value(
            node, "RimFresnelPower", 0.0, float_info.max
        )
        parametric_rim_lift_factor = shader.get_float_value(node, "RimLift")

        rim_multiply_texture = shader.get_image_name_and_sampler_type(
            node,
            "RimTexture",
        )

        centimeter_to_meter = 0.01
        one_hundredth = 0.01

        outline_width_mode_float = shader.get_float_value(node, "OutlineWidthMode")
        outline_width = shader.get_float_value(node, "OutlineWidth")
        if outline_width is None:
            outline_width = 0.0
        outline_width_multiply_texture = shader.get_image_name_and_sampler_type(
            node,
            "OutlineWidthTexture",
        )

        outline_color_factor = shader.get_rgb_value(node, "OutlineColor", 0.0, 1.0) or (
            0,
            0,
            0,
        )

        outline_color_mode = shader.get_float_value(node, "OutlineColorMode")
        if outline_color_mode is not None:
            outline_color_mode = int(round(outline_color_mode))
        else:
            outline_color_mode = 0

        outline_lighting_mix_factor = 0.0
        if outline_color_mode == 1:
            outline_lighting_mix_factor = (
                shader.get_float_value(node, "OutlineLightingMix") or 1.0
            )

        uv_animation_mask_texture = shader.get_image_name_and_sampler_type(
            node,
            "UV_Animation_Mask_Texture",
        )
        uv_animation_rotation_speed_factor = shader.get_float_value(
            node, "UV_Scroll_Rotation"
        )
        uv_animation_scroll_x_speed_factor = shader.get_float_value(node, "UV_Scroll_X")
        uv_animation_scroll_y_speed_factor = shader.get_float_value(node, "UV_Scroll_Y")
        if isinstance(uv_animation_scroll_y_speed_factor, float):
            uv_animation_scroll_y_speed_factor *= -1

        shader.load_mtoon1_shader(context, material)

        root = material.vrm_addon_extension.mtoon1
        mtoon = root.extensions.vrmc_materials_mtoon

        root.alpha_mode = alpha_mode
        root.alpha_cutoff = alpha_cutoff
        mtoon.transparent_with_z_write = transparent_with_z_write
        root.pbr_metallic_roughness.base_color_factor = base_color_factor
        self.assign_mtoon_unversioned_image(
            root.pbr_metallic_roughness.base_color_texture,
            base_color_texture,
            uv_offset,
            uv_scale,
        )
        mtoon.shade_color_factor = shade_color_factor
        self.assign_mtoon_unversioned_image(
            mtoon.shade_multiply_texture,
            shade_multiply_texture,
            uv_offset,
            uv_scale,
        )
        self.assign_mtoon_unversioned_image(
            root.normal_texture,
            normal_texture,
            uv_offset,
            uv_scale,
        )
        if normal_texture_scale is not None:
            root.normal_texture.scale = normal_texture_scale

        mtoon.shading_shift_factor = shading_shift_factor
        mtoon.shading_toony_factor = shading_toony_factor

        if gi_equalization_factor is not None:
            mtoon.gi_equalization_factor = gi_equalization_factor

        root.emissive_factor = emissive_factor
        self.assign_mtoon_unversioned_image(
            root.emissive_texture,
            emissive_texture,
            uv_offset,
            uv_scale,
        )
        self.assign_mtoon_unversioned_image(
            mtoon.matcap_texture,
            matcap_texture,
            (0, 0),
            (1, 1),
        )

        if parametric_rim_color_factor is not None:
            mtoon.parametric_rim_color_factor = parametric_rim_color_factor
        if parametric_rim_fresnel_power_factor is not None:
            mtoon.parametric_rim_fresnel_power_factor = (
                parametric_rim_fresnel_power_factor
            )
        if parametric_rim_lift_factor is not None:
            mtoon.parametric_rim_lift_factor = parametric_rim_lift_factor

        self.assign_mtoon_unversioned_image(
            mtoon.rim_multiply_texture,
            rim_multiply_texture,
            uv_offset,
            uv_scale,
        )

        # https://github.com/vrm-c/UniVRM/blob/7c9919ef47a25c04100a2dcbe6a75dff49ef4857/Assets/VRM10/Runtime/Migration/Materials/MigrationMToonMaterial.cs#L287-L290
        mtoon.rim_lighting_mix_factor = 1.0

        centimeter_to_meter = 0.01
        one_hundredth = 0.01

        if outline_width_mode_float is not None:
            outline_width_mode = int(round(outline_width_mode_float))
        else:
            outline_width_mode = 0

        if outline_width is None:
            outline_width = 0.0

        if outline_width_mode == 1:
            mtoon.outline_width_mode = mtoon.OUTLINE_WIDTH_MODE_WORLD_COORDINATES
            mtoon.outline_width_factor = max(0.0, outline_width * centimeter_to_meter)
        elif outline_width_mode == 2:
            mtoon.outline_width_mode = mtoon.OUTLINE_WIDTH_MODE_SCREEN_COORDINATES
            mtoon.outline_width_factor = max(0.0, outline_width * one_hundredth * 0.5)
        else:
            mtoon.outline_width_mode = mtoon.OUTLINE_WIDTH_MODE_NONE

        self.assign_mtoon_unversioned_image(
            mtoon.outline_width_multiply_texture,
            outline_width_multiply_texture,
            uv_offset,
            uv_scale,
        )

        mtoon.outline_color_factor = outline_color_factor
        mtoon.outline_lighting_mix_factor = 0.0
        if outline_color_mode == 1:
            mtoon.outline_lighting_mix_factor = outline_lighting_mix_factor

        self.assign_mtoon_unversioned_image(
            mtoon.uv_animation_mask_texture,
            uv_animation_mask_texture,
            uv_offset,
            uv_scale,
        )

        if uv_animation_rotation_speed_factor is not None:
            mtoon.uv_animation_rotation_speed_factor = (
                uv_animation_rotation_speed_factor
            )
        if uv_animation_scroll_x_speed_factor is not None:
            mtoon.uv_animation_scroll_x_speed_factor = (
                uv_animation_scroll_x_speed_factor
            )
        if uv_animation_scroll_y_speed_factor is not None:
            mtoon.uv_animation_scroll_y_speed_factor = (
                uv_animation_scroll_y_speed_factor
            )


class VRM_OT_convert_mtoon1_to_bsdf_principled(bpy.types.Operator):  # type: ignore[misc] # noqa: N801
    bl_idname = "vrm.convert_mtoon1_to_bsdf_principled"
    bl_label = "Convert MToon 1.0 to Principled BSDF"
    bl_description = "Convert MToon 1.0 to Principled BSDF"
    bl_options = {"REGISTER", "UNDO"}

    material_name: bpy.props.StringProperty(  # type: ignore[valid-type]
        options={"HIDDEN"}  # noqa: F821
    )

    def execute(self, _context: bpy.types.Context) -> Set[str]:
        material = bpy.data.materials.get(self.material_name)
        if not isinstance(material, bpy.types.Material):
            return {"CANCELLED"}
        self.convert_mtoon1_to_bsdf_principled(material)
        return {"FINISHED"}

    def convert_mtoon1_to_bsdf_principled(self, material: bpy.types.Material) -> None:
        shader.clear_node_tree(material.node_tree, clear_inputs_outputs=True)
        shader_node = material.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        output_node = material.node_tree.nodes.new("ShaderNodeOutputMaterial")
        material.node_tree.links.new(
            output_node.inputs["Surface"], shader_node.outputs["BSDF"]
        )


class VRM_OT_reset_mtoon1_material_shader_node_group(bpy.types.Operator):  # type: ignore[misc] # noqa: N801
    bl_idname = "vrm.reset_mtoon1_material_shader_node_group"
    bl_label = "Reset Shader Node Group"
    bl_description = "Reset MToon 1.0 Material Shader Node Group"
    bl_options = {"REGISTER", "UNDO"}

    material_name: bpy.props.StringProperty(  # type: ignore[valid-type]
        options={"HIDDEN"}  # noqa: F821
    )

    def execute(self, context: bpy.types.Context) -> Set[str]:
        material = bpy.data.materials.get(self.material_name)
        if not isinstance(material, bpy.types.Material):
            return {"CANCELLED"}
        reset_shader_node_group(context, material)
        return {"FINISHED"}


class VRM_OT_import_mtoon1_texture_image_file(bpy.types.Operator, ImportHelper):  # type: ignore[misc] # noqa: N801
    bl_idname = "vrm.import_mtoon1_texture_image_file"
    bl_label = "Open"
    bl_description = "Import Texture Image File"
    bl_options = {"REGISTER", "UNDO"}

    filepath: bpy.props.StringProperty(  # type: ignore[valid-type]
        options={"HIDDEN"},  # noqa: F821
        default="",  # noqa: F722
    )

    filter_glob: bpy.props.StringProperty(  # type: ignore[valid-type]
        options={"HIDDEN"},  # noqa: F821
        # https://docs.blender.org/api/2.83/bpy.types.Image.html#bpy.types.Image.file_format
        default=(
            "*.bmp"  # noqa: F722
            ";*.sgi"
            ";*.bw"
            ";*.rgb"
            ";*.rgba"
            ";*.png"
            ";*.jpg"
            ";*.jpeg"
            ";*.jp2"
            ";*.tga"
            ";*.cin"
            ";*.dpx"
            ";*.exr"
            ";*.hdr"
            ";*.tif"
            ";*.tiff"
        ),
    )

    material_name: bpy.props.StringProperty(  # type: ignore[valid-type]
        options={"HIDDEN"},  # noqa: F821
    )

    target_texture_info_items = [
        (Mtoon1BaseColorTextureInfoPropertyGroup.__name__, "", "", "NONE", 0),
        (Mtoon1ShadeMultiplyTextureInfoPropertyGroup.__name__, "", "", "NONE", 1),
        (Mtoon1NormalTextureInfoPropertyGroup.__name__, "", "", "NONE", 2),
        (Mtoon1ShadingShiftTextureInfoPropertyGroup.__name__, "", "", "NONE", 3),
        (Mtoon1EmissiveTextureInfoPropertyGroup.__name__, "", "", "NONE", 4),
        (Mtoon1RimMultiplyTextureInfoPropertyGroup.__name__, "", "", "NONE", 5),
        (Mtoon1MatcapTextureInfoPropertyGroup.__name__, "", "", "NONE", 6),
        (
            Mtoon1OutlineWidthMultiplyTextureInfoPropertyGroup.__name__,
            "",
            "",
            "NONE",
            7,
        ),
        (Mtoon1UvAnimationMaskTextureInfoPropertyGroup.__name__, "", "", "NONE", 8),
    ]

    target_texture_info: bpy.props.EnumProperty(  # type: ignore[valid-type]
        options={"HIDDEN"},  # noqa: F821
        items=target_texture_info_items,
        name="Target Texture Info",  # noqa: F722
    )

    def execute(self, _context: bpy.types.Context) -> Set[str]:
        filepath = self.filepath
        if not isinstance(filepath, str):
            return {"CANCELLED"}

        last_images_len = len(bpy.data.images)
        image = bpy.data.images.load(filepath, check_existing=True)
        if not isinstance(image, bpy.types.Image):
            return {"CANCELLED"}
        created = last_images_len < len(bpy.data.images)

        material = bpy.data.materials.get(self.material_name)
        if not isinstance(material, bpy.types.Material):
            return {"FINISHED"}

        root = material.vrm_addon_extension.mtoon1
        mtoon = root.extensions.vrmc_materials_mtoon

        if self.target_texture_info == Mtoon1BaseColorTextureInfoPropertyGroup.__name__:
            root.pbr_metallic_roughness.base_color_texture.index.source = image
            if created:
                image.colorspace_settings.name = (
                    Mtoon1BaseColorTextureInfoPropertyGroup.colorspace
                )
        elif (
            self.target_texture_info
            == Mtoon1ShadeMultiplyTextureInfoPropertyGroup.__name__
        ):
            mtoon.shade_multiply_texture.index.source = image
            if created:
                image.colorspace_settings.name = (
                    Mtoon1ShadeMultiplyTextureInfoPropertyGroup.colorspace
                )
        elif self.target_texture_info == Mtoon1NormalTextureInfoPropertyGroup.__name__:
            root.normal_texture.index.source = image
            if created:
                image.colorspace_settings.name = (
                    Mtoon1NormalTextureInfoPropertyGroup.colorspace
                )
        elif (
            self.target_texture_info
            == Mtoon1ShadingShiftTextureInfoPropertyGroup.__name__
        ):
            mtoon.shading_shift_texture.index.source = image
            if created:
                image.colorspace_settings.name = (
                    Mtoon1ShadingShiftTextureInfoPropertyGroup.colorspace
                )
        elif (
            self.target_texture_info == Mtoon1EmissiveTextureInfoPropertyGroup.__name__
        ):
            root.emissive_texture.index.source = image
            if created:
                image.colorspace_settings.name = (
                    Mtoon1EmissiveTextureInfoPropertyGroup.colorspace
                )
        elif (
            self.target_texture_info
            == Mtoon1RimMultiplyTextureInfoPropertyGroup.__name__
        ):
            mtoon.rim_multiply_texture.index.source = image
            if created:
                image.colorspace_settings.name = (
                    Mtoon1RimMultiplyTextureInfoPropertyGroup.colorspace
                )
        elif self.target_texture_info == Mtoon1MatcapTextureInfoPropertyGroup.__name__:
            mtoon.matcap_texture.index.source = image
            if created:
                image.colorspace_settings.name = (
                    Mtoon1MatcapTextureInfoPropertyGroup.colorspace
                )
        elif (
            self.target_texture_info
            == Mtoon1OutlineWidthMultiplyTextureInfoPropertyGroup.__name__
        ):
            mtoon.outline_width_multiply_texture.index.source = image
            if created:
                image.colorspace_settings.name = (
                    Mtoon1OutlineWidthMultiplyTextureInfoPropertyGroup.colorspace
                )
        elif (
            self.target_texture_info
            == Mtoon1UvAnimationMaskTextureInfoPropertyGroup.__name__
        ):
            mtoon.uv_animation_mask_texture.index.source = image
            if created:
                image.colorspace_settings.name = (
                    Mtoon1UvAnimationMaskTextureInfoPropertyGroup.colorspace
                )

        return {"FINISHED"}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event) -> Set[str]:
        self.filepath = ""
        return cast(Set[str], ImportHelper.invoke(self, context, event))
