from typing import Dict

import bpy
from bpy.app.translations import pgettext

from ...common.preferences import get_preferences
from .. import search
from ..extension import VrmAddonArmatureExtensionPropertyGroup
from ..panel import VRM_PT_vrm_armature_object_property
from .property_group import NodeConstraint1NodeConstraintPropertyGroup


def active_object_is_vrm1_armature(context: bpy.types.Context) -> bool:
    return bool(
        context
        and context.active_object
        and context.active_object.type == "ARMATURE"
        and hasattr(context.active_object.data, "vrm_addon_extension")
        and isinstance(
            context.active_object.data.vrm_addon_extension,
            VrmAddonArmatureExtensionPropertyGroup,
        )
        and context.active_object.data.vrm_addon_extension.is_vrm1()
    )


def draw_roll_constraint_layout(
    layout: bpy.types.UILayout,
    node_constraint: NodeConstraint1NodeConstraintPropertyGroup,
    object_constraints: Dict[str, bpy.types.CopyRotationConstraint],
    bone_constraints: Dict[str, bpy.types.CopyRotationConstraint],
) -> None:
    constraints_box = layout.box()
    constraints_row = constraints_box.row()
    constraints_row.alignment = "LEFT"
    constraints_row.prop(
        node_constraint,
        "show_expanded_roll_constraints",
        icon="TRIA_DOWN"
        if node_constraint.show_expanded_roll_constraints
        else "TRIA_RIGHT",
        emboss=False,
    )
    if not node_constraint.show_expanded_roll_constraints:
        return

    constraints_column = constraints_box.column()
    if object_constraints or bone_constraints:
        constraints_expanded_column = constraints_column.column()
        for object_name, constraint in object_constraints.items():
            constraint_row = constraints_expanded_column.row()
            constraint_row.alignment = "LEFT"
            constraint_row.label(
                text=object_name + ": " + constraint.name,
                icon="CONSTRAINT",
                translate=False,
            )
        for bone_name, constraint in bone_constraints.items():
            constraint_row = constraints_expanded_column.row()
            constraint_row.alignment = "LEFT"
            constraint_row.label(
                text=bone_name + ": " + constraint.name,
                icon="CONSTRAINT_BONE",
                translate=False,
            )

    constraints_help_column = constraints_column.box().column()
    help_message = pgettext(
        "Conditions exported as Roll Constraint\n"
        + " - Copy Rotation\n"
        + " - Enabled\n"
        + " - No Vertex Group\n"
        + " - Axis is one of X, Y and Z\n"
        + " - No Inverted\n"
        + " - Mix is Add\n"
        + " - Target is Local Space\n"
        + " - Owner is Local Space\n"
        + " - No circular dependencies\n"
        + " - The one at the top of the list of\n"
        + "   those that meet all the conditions\n"
    )
    for index, help_line in enumerate(help_message.splitlines()):
        constraints_help_column.label(
            text=help_line, translate=False, icon="HELP" if index == 0 else "NONE"
        )


def draw_aim_constraint_layout(
    layout: bpy.types.UILayout,
    node_constraint: NodeConstraint1NodeConstraintPropertyGroup,
    object_constraints: Dict[str, bpy.types.DampedTrackConstraint],
    bone_constraints: Dict[str, bpy.types.DampedTrackConstraint],
) -> None:
    constraints_box = layout.box()
    constraints_row = constraints_box.row()
    constraints_row.alignment = "LEFT"
    constraints_row.prop(
        node_constraint,
        "show_expanded_aim_constraints",
        icon="TRIA_DOWN"
        if node_constraint.show_expanded_aim_constraints
        else "TRIA_RIGHT",
        emboss=False,
    )
    if not node_constraint.show_expanded_aim_constraints:
        return

    constraints_column = constraints_box.column()
    if object_constraints or bone_constraints:
        constraints_expanded_column = constraints_column.column()
        for object_name, constraint in object_constraints.items():
            constraint_row = constraints_expanded_column.row()
            constraint_row.alignment = "LEFT"
            constraint_row.label(
                text=object_name + ": " + constraint.name,
                icon="CONSTRAINT",
                translate=False,
            )
        for bone_name, constraint in bone_constraints.items():
            constraint_row = constraints_expanded_column.row()
            constraint_row.alignment = "LEFT"
            constraint_row.label(
                text=bone_name + ": " + constraint.name,
                icon="CONSTRAINT_BONE",
                translate=False,
            )

    constraints_help_column = constraints_column.box().column()
    help_message = pgettext(
        "Conditions exported as Aim Constraint\n"
        + " - Damped Track\n"
        + " - Enabled\n"
        + " - Target Bone Head/Tail is 0\n"
        + " - No Follow Target Bone B-Bone\n"
        + " - No circular dependencies\n"
        + " - The one at the top of the list of\n"
        + "   those that meet all the conditions\n"
    )
    for index, help_line in enumerate(help_message.splitlines()):
        constraints_help_column.label(
            text=help_line, translate=False, icon="HELP" if index == 0 else "NONE"
        )


def draw_rotation_constraint_layout(
    layout: bpy.types.UILayout,
    node_constraint: NodeConstraint1NodeConstraintPropertyGroup,
    object_constraints: Dict[str, bpy.types.CopyRotationConstraint],
    bone_constraints: Dict[str, bpy.types.CopyRotationConstraint],
) -> None:
    constraints_box = layout.box()
    constraints_row = constraints_box.row()
    constraints_row.alignment = "LEFT"
    constraints_row.prop(
        node_constraint,
        "show_expanded_rotation_constraints",
        icon="TRIA_DOWN"
        if node_constraint.show_expanded_rotation_constraints
        else "TRIA_RIGHT",
        emboss=False,
    )
    if not node_constraint.show_expanded_rotation_constraints:
        return

    constraints_column = constraints_box.column()
    if object_constraints or bone_constraints:
        constraints_expanded_column = constraints_column.column()
        for object_name, constraint in object_constraints.items():
            constraint_row = constraints_expanded_column.row()
            constraint_row.alignment = "LEFT"
            constraint_row.label(
                text=object_name + ": " + constraint.name,
                icon="CONSTRAINT",
                translate=False,
            )
        for bone_name, constraint in bone_constraints.items():
            constraint_row = constraints_expanded_column.row()
            constraint_row.alignment = "LEFT"
            constraint_row.label(
                text=bone_name + ": " + constraint.name,
                icon="CONSTRAINT_BONE",
                translate=False,
            )

    constraints_help_column = constraints_column.box().column()
    help_message = pgettext(
        "Conditions exported as Rotation Constraint\n"
        + " - Copy Rotation\n"
        + " - Enabled\n"
        + " - No Vertex Group\n"
        + " - Axis is X, Y and Z\n"
        + " - No Inverted\n"
        + " - Mix is Add\n"
        + " - Target is Local Space\n"
        + " - Owner is Local Space\n"
        + " - No circular dependencies\n"
        + " - The one at the top of the list of\n"
        + "   those that meet all the conditions\n"
    )
    for index, help_line in enumerate(help_message.splitlines()):
        constraints_help_column.label(
            text=help_line, translate=False, icon="HELP" if index == 0 else "NONE"
        )


def draw_node_constraint1_layout(
    context: bpy.types.Context,
    armature: bpy.types.Object,
    layout: bpy.types.UILayout,
    node_constraint: NodeConstraint1NodeConstraintPropertyGroup,
) -> None:
    preferences = get_preferences(context)
    objs = search.export_objects(
        context, preferences.export_invisibles, export_only_selections=False
    )
    object_constraints, bone_constraints, _ = search.export_constraints(objs, armature)
    draw_roll_constraint_layout(
        layout,
        node_constraint,
        object_constraints.roll_constraints,
        bone_constraints.roll_constraints,
    )
    draw_aim_constraint_layout(
        layout,
        node_constraint,
        object_constraints.aim_constraints,
        bone_constraints.aim_constraints,
    )
    draw_rotation_constraint_layout(
        layout,
        node_constraint,
        object_constraints.rotation_constraints,
        bone_constraints.rotation_constraints,
    )


class VRM_PT_node_constraint1_armature_object_property(bpy.types.Panel):  # type: ignore[misc] # noqa: N801
    bl_idname = "VRM_PT_node_constraint1_armature_object_property"
    bl_label = "Node Constraint"
    bl_translation_context = "VRM"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"DEFAULT_CLOSED"}
    bl_parent_id = VRM_PT_vrm_armature_object_property.bl_idname

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return active_object_is_vrm1_armature(context)

    def draw_header(self, _context: bpy.types.Context) -> None:
        self.layout.label(icon="CONSTRAINT")

    def draw(self, context: bpy.types.Context) -> None:
        draw_node_constraint1_layout(
            context,
            context.active_object,
            self.layout,
            context.active_object.data.vrm_addon_extension.node_constraint1,
        )


class VRM_PT_node_constraint1_ui(bpy.types.Panel):  # type: ignore[misc] # noqa: N801
    bl_idname = "VRM_PT_node_constraint1_ui"
    bl_label = "Node Constraint"
    bl_translation_context = "VRM"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "VRM"
    bl_options = {"DEFAULT_CLOSED"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return search.current_armature_is_vrm1(context)

    def draw_header(self, _context: bpy.types.Context) -> None:
        self.layout.label(icon="CONSTRAINT")

    def draw(self, context: bpy.types.Context) -> None:
        armature = search.current_armature(context)
        if not armature:
            return
        draw_node_constraint1_layout(
            context,
            armature,
            self.layout,
            armature.data.vrm_addon_extension.node_constraint1,
        )
