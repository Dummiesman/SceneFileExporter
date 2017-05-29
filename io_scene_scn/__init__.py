# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons Attribution-NonCommercial-ShareAlike 3.0
# https://creativecommons.org/licenses/by-nc-sa/3.0/
#
# Copyright (C) Dummiesman, 2016
#
# ##### END LICENSE BLOCK #####

bl_info = {
    "name": "Intermediate Scene Format",
    "author": "Dummiesman",
    "version": (0, 0, 1),
    "blender": (2, 78, 0),
    "location": "File > Import-Export",
    "description": "Import-Export SCENE files",
    "warning": "",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.7/Py/"
                "Scripts/Import-Export/SCN",
    "support": 'COMMUNITY',
    "category": "Import-Export"}

import bpy
from bpy.props import (
        BoolProperty,
        EnumProperty,
        FloatProperty,
        StringProperty,
        CollectionProperty,
        )
from bpy_extras.io_utils import (
        ImportHelper,
        ExportHelper,
        )

class ExportSCN(bpy.types.Operator, ExportHelper):
    """Export to SCN file format (.SCN)"""
    bl_idname = "export_scene.scn"
    bl_label = 'Export SCN'

    filename_ext = ".scn"
    filter_glob = StringProperty(
            default="*.scn",
            options={'HIDDEN'},
            )
        
    # props
    embed_textures = BoolProperty(
        name="Embed Textures",
        description="Embeds textures within the SCN file rather than referencing their file paths.",
        default=False,
        )
        
    # texture relative type
    texture_path_mode = bpy.props.EnumProperty(name="Relativity", 
                                               items = (('abs', 'absolute',''), ('blend','to *.blend',''),('scn','to *.scn','')),
                                               default='scn')
    
    # export things
    modifier_mode = bpy.props.EnumProperty(name="Modifier Mode", 
                                           items = (('preserve', 'Export Modifiers',''), ('apply','Apply Before Export',''), ('noapply', 'Do Nothing', '')),
                                           default='preserve')
    
        
    def draw(self, context):
        layout = self.layout
        
        #box = layout.box()
        #box.label("General settings")
        
        box = layout.box()
        box.label("Mesh settings")
        box.prop(self, "modifier_mode")
        
        box = layout.box()
        box.label("Texture settings")
        box.prop(self, "embed_textures")
        
        if not self.embed_textures:
            box = layout.box()
            box.label("Texture paths")
            box.prop(self, "texture_path_mode")
        
    def execute(self, context):
        from . import export_scn
        
        keywords = self.as_keywords(ignore=("axis_forward",
                                            "axis_up",
                                            "filter_glob",
                                            "check_existing",
                                            ))
                                    
        return export_scn.save(self, context, **keywords)


# Add to a menu
def menu_func_export(self, context):
    self.layout.operator(ExportSCN.bl_idname, text="Intermediate Scene Format (.scn)")

def register():
    bpy.utils.register_module(__name__)

    bpy.types.INFO_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_module(__name__)

    bpy.types.INFO_MT_file_export.remove(menu_func_export)

if __name__ == "__main__":
    register()
