# ##### BEGIN LICENSE BLOCK #####
#
# This program is licensed under Creative Commons BY-NC-SA:
# https://creativecommons.org/licenses/by-nc-sa/3.0/
#
# Copyright (C) Dummiesman, 2016
#
# ##### END LICENSE BLOCK #####

import os, time, struct, math, sys
import os.path as path

import bpy, bmesh, mathutils

current_id = -1

# maps
armature_map = {}
action_map = {}
camera_map = {}
sound_map = {}
speaker_map = {}
object_map = {}
texture_map = {}
material_map = {}
lamp_map = {}
texture_map = {}
mesh_map = {}
curve_map = {}
rigidbody_map = {}
vertex_group_map = {}
userdata_map = {}
modifier_map = {}

# used for options
export_options = {}
export_path = None

# constants
light_type_dict = {'POINT': 0, 'SPOT': 1, 'SUN':2, 'AREA':3}
texture_blend_type_dict = {'MIX': 0, 
                           'ADD': 1, 
                           'SUBTRACT': 2, 
                           'MULTIPLY': 3, 
                           'SCREEN': 4, 
                           'OVERLAY': 5, 
                           'DIFFERENCE': 6, 
                           'DIVIDE': 7, 
                           'DARKEN': 8, 
                           'LIGHTEN': 9, 
                           'HUE': 10, 
                           'SATURATION': 11, 
                           'VALUE': 12, 
                           'COLOR': 13,
                          }
rigidbody_shape_dict = {'BOX': 0, 'SPHERE': 1, 'CAPSULE': 2, 'CYLINDER': 3, 'CONE': 4, 'CONVEX_HULL': 5, 'MESH': 6}                           
curve_type_dict = {'POLY': 0, 'BEZIER': 1, 'BSPLINE': 2, 'CARDINAL': 3, 'NURBS': 4}
curve_tilt_dict = {'LINEAR': 0, 'CARDINAL': 1, 'BSPLINE': 2, 'EASE': 3}
modifier_type_dict = {'EDGE_SPLIT': 0, 'MIRROR': 1, 'SUBSURF': 2, 'ARRAY': 3, 'BOOLEAN': 4}
boolean_operator_dict = {'INTERSECT': 0, 'UNION': 1, 'DIFFERENCE': 2}

######################################################
# VERIFICATION FUNCTIONS
######################################################
def verify_object_type(ob):
  if ob.type != 'LAMP' and ob.type != 'SPEAKER' and ob.type != 'EMPTY' and ob.type != 'CAMERA' and ob.type != 'MESH' and ob.type != 'CURVE' and ob.type != 'ARMATURE':
    return False
  return True

  
def verify_constraint_type(constraint):
  if constraint.type != 'FIXED' and constraint.type != 'HINGE' and constraint.type != 'GENERIC_SPRING' and constraint.type != 'MOTOR':
    return False
  return True
  
  
######################################################
# CHUNK FUNCTIONS
######################################################
def write_modifier_chunk(file, modifier):
    # verify we support this
    if modifier_type_dict.get(modifier.type, -1) < 0:
      return
    
    # write chunk
    ptr = create_chunk(file, "MDFR", 1, get_uuid())
    
    # write type
    file.write(struct.pack("<H", modifier_type_dict.get(modifier.type)))
      
    # write modifier specific data (TODO: seperate? maybe in its own .py file?)
    if modifier.type == 'EDGE_SPLIT':
      file.write(struct.pack("<H", 1 if modifier.use_edge_sharp else 0))
      file.write(struct.pack("<H", 1 if modifier.use_edge_angle else 0))
      
      # write angle if specified
      if modifier.use_edge_angle:
        file.write(struct.pack("<f", modifier.split_angle * 57.2958))
    elif modifier.type == 'MIRROR':
      # create axis bitfield
      axis_id = 0
      if modifier.use_x:
        axis_id |= 1
      if modifier.use_y:
        axis_id |= 2
      if modifier.use_z:
        axis_id |= 4
        
      file.write(struct.pack("<H", axis_id))
      
      # create uv axis bitfield
      uv_axis_id = 0
      if modifier.use_mirror_u:
        uv_axis_id |= 1
      if modifier.use_mirror_v:
        uv_axis_id |= 2
      
      file.write(struct.pack("<H", uv_axis_id))
      
      # write the rest
      file.write(struct.pack("<H", 1 if modifier.use_clip else 0))
      file.write(struct.pack("<H", 1 if modifier.use_mirror_merge else 0))
      
      # write if applicable
      if modifier.use_mirror_merge:
        file.write(struct.pack("<f", modifier.merge_threshold)) 
    elif modifier.type == 'SUBSURF':
      file.write(struct.pack("<H", modifier.levels))
      file.write(struct.pack("<H", 0 if modifier.subdivision_type == 'SIMPLE' else 1))
    elif modifier.type == 'ARRAY':
      file.write(struct.pack("<H", modifier.count - 1))
      
      # write type
      if modifier.use_relative_offset:
        file.write(struct.pack("<H", 0))
      elif modifier.use_constant_offset:
        file.write(struct.pack("<H", 1))        
      elif modifier.use_object_offset:
        file.write(struct.pack("<H", 2))
      
      # write offset or datablock id
      if modifier.use_object_offset:
        file.write(struct.pack("<i", object_map.get(modifier.offset_object.name, -1)))
      else:
        offset = [0.0, 0.0, 0.0]
        if modifier.use_relative_offset:
          offset = modifier.relative_offset_displace
        else:
          offset = modifier.constant_offset_displace
        file.write(struct.pack("<fff", *offset))
        
      # write merge settings
      file.write(struct.pack("<H", 1 if modifier.use_merge_vertices else 0))
      if modifier.use_merge_vertices:
        file.write(struct.pack("<f", modifier.merge_threshold))
    elif modifier.type == 'BOOLEAN':
      file.write(struct.pack("<i", object_map.get(modifier.object.name, -1)))
      file.write(struct.pack("<H", boolean_operator_dict.get(modifier.operation, 0)))
      file.write(struct.pack("<H", 0 if modifier.solver == 'CARVE' else 1))
      
    # close chunk
    close_chunk(file, ptr)


def write_meta_chunk(file, pairs, type = "META"):
    # return if nothing
    if(len(pairs) == 0):
      return
      
    # write chunk
    ptr = create_chunk(file, type, 1, get_uuid())
    
    num_pairs = len(pairs)
    file.write(struct.pack("<I", num_pairs))
    
    # write pairs
    for pair in pairs:
      write_string(file, pair[0])
      write_string(file, pair[1])
    
    # close chunk
    close_chunk(file, ptr)

    
def write_light_chunk(file, light):
    # verify we support this
    if light.type == 'HEMI':
      return
    
    # write chunk
    ptr = create_chunk(file, "LGHT", 1, get_uuid())
    
    # write type
    file.write(struct.pack("<H", light_type_dict.get(light.type, 0)))
      
    # write color
    color = (light.color[0], light.color[1], light.color[2], 1.0)
    file.write(struct.pack("<ffff", *color))
    
    # write obvious data
    file.write(struct.pack("<f", light.energy))
    
    # write shadow data
    file.write(struct.pack("<H", (0 if light.shadow_method == 'NOSHADOW' else 1)))
    
    if light.shadow_method != 'NOSHADOW':
      shadow_color = (light.shadow_color[0],light.shadow_color[1], light.shadow_color[2], 1.0)
      file.write(struct.pack("<ffff", *shadow_color))
      file.write(struct.pack("<f", light.shadow_soft_size))
    
    if light.type == 'POINT' or light.type == 'SPOT' or light.type == 'AREA':
      file.write(struct.pack("<f", light.distance))
      
    if light.type == 'SPOT':
      inner_angle_percent = 1.0 - light.spot_blend
      real_angle = (light.spot_size / 3.14159) * 180.0
      file.write(struct.pack("<f", real_angle))
      file.write(struct.pack("<f", real_angle * inner_angle_percent))
    elif light.type == 'AREA':
      if light.shape == 'RECTANGLE':
        file.write(struct.pack("<ff", light.size, light.size_y))
      else:
        file.write(struct.pack("<ff", light.size, light.size))
    # close chunk
    close_chunk(file, ptr)

def write_sound_resource_chunk(file, sound):
  # write chunk
  ptr = create_chunk(file, "RSRC", 1, get_uuid())
  
  # get absolute path to the sound to use for later
  sound_realpath = bpy.path.abspath(sound.filepath)
  if export_options["EMBED_RESOURCES"]:
    # write basename path if we're embedding textures, source path is useless
    write_string(file, bpy.path.basename(sound_realpath))
  else:
    # write path to the image based on a user setting
    if export_options["RELATIVITY"] == "blend":
      write_string(file, bpy.path.relpath(sound_realpath)[2:])
    elif export_options["RELATIVITY"] == "abs":
      write_string(file, sound_realpath)
    else:
      write_string(file, bpy.path.relpath(sound_realpath, start=os.path.dirname(export_path))[2:])
  
  # write sound file extension
  sound_extension = sound.filepath[-3:].upper() + " "
  file.write(sound_extension.encode('ascii'))
  
  file.write(struct.pack("<H", 0)) # reserved
  
  # embed?
  file.write(struct.pack("<H", (1 if export_options["EMBED_RESOURCES"] else 0)))
  if export_options["EMBED_RESOURCES"]:
    # get our image binary  data
    sound_data = None
    
    if sound.packed_file is not None:
      sound_data = texture.image.packed_file.data
    else:
      sound_file = open(sound_realpath, "rb")
      sound_data = sound_file.read()
      sound_file.close()
    
    # write it
    sound_len = len(sound_data)
    file.write(struct.pack("<I", sound_len))
    file.write(sound_data)
    
    # add padding if we need it
    if sound_len % 2 > 0:
      file.write("\x00".encode("ascii"))
  
  close_chunk(file, ptr)
  
def write_speaker_chunk(file, speaker):
  # write chunk
  ptr = create_chunk(file, "AUDS", 1, get_uuid())
  
  file.write(struct.pack("<fff", speaker.volume, speaker.pitch, speaker.attenuation))
  file.write(struct.pack("<ff", speaker.volume_min, speaker.volume_max))
  file.write(struct.pack("<ff", speaker.distance_reference, speaker.distance_max))
  file.write(struct.pack("<ff", speaker.cone_angle_outer, speaker.cone_angle_inner))
  
  file.write(struct.pack("<H", (1 if speaker.muted else 0)))
    
  if speaker.sound is not None:
    file.write(struct.pack("<I", sound_map[speaker.sound.name]))
  else:
    file.write(struct.pack("<i", -1))
  
  close_chunk(file, ptr)
  
def write_scene_chunk(file, world):
  # wite chunk
  ptr = create_chunk(file, "SCNE", 1, get_uuid())
  
  write_string(file, world.name)
  
  file.write(struct.pack("<ffff", world.ambient_color[0], world.ambient_color[1], world.ambient_color[2], 1.0)) #ambient
  file.write(struct.pack("<ffff", world.zenith_color[0], world.zenith_color[1], world.zenith_color[2], 1.0)) #sky
  file.write(struct.pack("<ffff", world.horizon_color[0], world.horizon_color[1], world.horizon_color[2], 1.0)) #horizon
  
  # write fog only if enabled
  file.write(struct.pack("<H", (1 if world.mist_settings.use_mist else 0)))
  if world.mist_settings.use_mist:
    file.write(struct.pack("<ffff", world.horizon_color[0], world.horizon_color[1], world.horizon_color[2], 1.0)) #fog
    
    file.write(struct.pack("<ffff", world.mist_settings.intensity, 
                                   world.mist_settings.start, 
                                   world.mist_settings.depth, 
                                   world.mist_settings.height))
                                   
    file.write(struct.pack("<H", (1 if world.mist_settings.falloff == 'QUADRATIC' else 0))) #type
  
  close_chunk(file, ptr)
  
def write_object_chunk(file, ob):
  if verify_object_type(ob) == False:
    return
    
  # write chunk
  ptr = create_chunk(file, "OBJT", 2, get_uuid())
  
  write_string(file, ob.name)
  rotation_radians = ob.matrix_world.to_euler()
  file.write(struct.pack("<fff", *ob.matrix_local.to_translation()))
  file.write(struct.pack("<fff", math.degrees(rotation_radians[0]), math.degrees(rotation_radians[1]), math.degrees(rotation_radians[2])))
  file.write(struct.pack("<fff", *ob.scale))
  
  # write parent
  if ob.parent is not None:
    file.write(struct.pack("<I", object_map[ob.parent.name]))
  else:
    file.write(struct.pack("<I", 0))
    
  # create layer mask
  layer_mask = 0
  for layer_num in range(20):
    if ob.layers[layer_num]:
      layer_mask |= (1<<layer_num)
      
  file.write(struct.pack("<I", layer_mask))
  
  # wrtie visible state and selected state
  file.write(struct.pack("<HH", (1 if ob.is_visible(bpy.context.scene) else 0), (1 if ob.select else 0)))
  
  # write datablocks
  datablock_count = 0
  if export_options["MODIFIER_MODE"] == 'preserve': datablock_count += len(ob.modifiers)
  if ob.type != 'EMPTY':  datablock_count += 1
  if ob.rigid_body is not None: datablock_count += 2
  if ob.rigid_body_constraint is not None and verify_constraint_type(ob.rigid_body_constraint): datablock_count += 1
  if len(ob.vertex_groups) > 0: datablock_count += len(ob.vertex_groups)
  if len(ob.keys()) > 0: datablock_count += 1
  if ob.animation_data is not None and ob.animation_data.action is not None: datablock_count += 1
  if ob.type == 'CURVE': datablock_count += len(ob.data.splines)
  
  # gather material datablocks
  material_datablock_ids = []
  for ms in ob.material_slots:
    if ms is not None and ms.material is not None:
      datablock_count += 1
      material_datablock_ids.append(material_map[ms.material.name])
  
  file.write(struct.pack("<H", datablock_count)) #datablock count
  
  # write material datablocks
  for matid in material_datablock_ids:
    file.write(struct.pack("<I", matid))
  
  # write modifier datablocks
  if export_options["MODIFIER_MODE"] == 'preserve':
    for mod in ob.modifiers:
      file.write(struct.pack("<I", modifier_map[ob.name + "_" + mod.name]))
  
  # write "concrete" datablock
  map = None
  if ob.type == 'LAMP':
    map = lamp_map
  elif ob.type == 'SPEAKER':
    map = speaker_map
  elif ob.type == 'CAMERA':
    map = camera_map
  elif ob.type == 'MESH':
    map = mesh_map
  elif ob.type == 'ARMATURE':
    map = armature_map
  
  if map is not None:
    file.write(struct.pack("<I", map[ob.data.name]))
  
  # write rigidbody datablock
  if ob.rigid_body is not None:
    if ob.rigid_body_constraint is not None and  verify_constraint_type(ob.rigid_body_constraint):
      file.write(struct.pack("<I", rigidbody_map[ob.name] - 2)) # constraint chunk written 2  chunks prior
    file.write(struct.pack("<I", rigidbody_map[ob.name] - 1)) # collision chunk written prior
    file.write(struct.pack("<I", rigidbody_map[ob.name]))
    
  # write spline datablocks
  if ob.type == 'CURVE':
    for cspline in len(ob.data.splines):
      file.write(struct.pack("<I", curve_map[ob.data.name + "_SCN_EXPORT_ID_" + str(cspline)]))
  
  # write vertex_group datablock
  if len(ob.vertex_groups) > 0:
    for group in ob.vertex_groups:
      file.write(struct.pack("<I", vertex_group_map[group.name]))
  
  # write animation datablock
  if ob.animation_data is not None and ob.animation_data.action is not None: 
    file.write(struct.pack("<I", action_map[ob.animation_data.action.name]))
    
  # write user data datablock
  if len(ob.keys()) > 0:
    file.write(struct.pack("<I", userdata_map[ob.name]))
  
  # close chunk
  close_chunk(file, ptr)
  
def write_camera_chunk(file, camera):
  # write chunk
  ptr = create_chunk(file, "CAMR", 1, get_uuid())
  
  file.write(struct.pack("<H", (0 if camera.type == 'ORTHO' else 1)))
  file.write(struct.pack("<ff", camera.clip_start, camera.clip_end))
  
  aspect_ratio = camera.sensor_width / camera.sensor_height
  file.write(struct.pack("<f", aspect_ratio))
  
  file.write(struct.pack("<ff", camera.shift_x, camera.shift_y))
  
  file.write(struct.pack("<f", camera.sensor_width))
  
  # write DOF settings
  dof_enabled = (camera.dof_distance > 0 or camera.dof_object is not None)
  file.write(struct.pack("<H", (1 if dof_enabled else 0)))
  
  if dof_enabled:
    if camera.dof_object is None:
      file.write(struct.pack("<i", -1))
    else:
      file.write(struct.pack("<i", object_map[camera.dof_object.name]))
      
    file.write(struct.pack("<ff", camera.dof_distance, camera.gpu_dof.fstop))
  
  # write FOV / ortho size
  if camera.type == 'ORTHO':
    file.write(struct.pack("<f", camera.ortho_scale))
  else:
    real_fov = (camera.angle / 3.01675) * 172.847
    file.write(struct.pack("<f", real_fov))
    
  close_chunk(file, ptr)

  
def write_texture_resource_chunk(file, texture):
  # write chunk
  ptr = create_chunk(file, "RSRC", 1, get_uuid())
  
  write_string(file, texture.name)
  if texture.type == 'IMAGE' and texture.image is not None:
    # get absolute path to the image to use for later
    image_realpath = bpy.path.abspath(texture.image.filepath)
    if export_options["EMBED_RESOURCES"]:
      # write basename path if we're embedding textures, source path is useless
      write_string(file, bpy.path.basename(image_realpath))
    else:
      # write path to the image based on a user setting
      if export_options["RELATIVITY"] == "blend":
        write_string(file, bpy.path.relpath(image_realpath)[2:])
      elif export_options["RELATIVITY"] == "abs":
        write_string(file, image_realpath)
      else:
        write_string(file, bpy.path.relpath(image_realpath, start=os.path.dirname(export_path))[2:])
    
    # check if we're using DDS, it's different
    tex_extension = texture.image.filepath[-3:].lower()
    if tex_extension == "dds":
      file.write("DDS ".encode('ascii'))
    else:
      file.write(truncate_format_string(texture.image.file_format).encode('ascii'))
    
    file.write(struct.pack("<H", texture.image.depth)) # reserved, in this case : depth
    
    # embed?
    file.write(struct.pack("<H", (1 if export_options["EMBED_RESOURCES"] else 0)))
    if export_options["EMBED_RESOURCES"]:
      # get our image binary  data
      image_data = None
      
      if texture.image.packed_file is not None:
        image_data = texture.image.packed_file.data
      else:
        image_file = open(image_realpath, "rb")
        image_data = image_file.read()
        image_file.close()
      
      # write it
      image_len = len(image_data)
      file.write(struct.pack("<I", image_len))
      file.write(image_data)
      
      # add padding if we need it
      if image_len % 2 > 0:
        file.write("\x00".encode("ascii"))
      
    
  else:
    write_string(file, "null")
    file.write("null".encode("ascii"))
    file.write(struct.pack("<HH", 0, 0))
  
  close_chunk(file, ptr)
  
  
def write_material_chunk(file, material):
  # write chunk
  ptr = create_chunk(file, "MTRL", 2, get_uuid())
  
  write_string(file, material.name) # write name
  
  diffuse_color = [material.diffuse_color[0] * material.diffuse_intensity,
                   material.diffuse_color[1] * material.diffuse_intensity,
                   material.diffuse_color[2] * material.diffuse_intensity, 
                   material.alpha]
                   
  specular_color = [material.specular_color[0] * material.specular_intensity,
                    material.specular_color[1] * material.specular_intensity,
                    material.specular_color[2] * material.specular_intensity,
                    material.specular_alpha]
                    
  specular_hardness = (material.specular_hardness - 1) / 511
  
  # write rest
  file.write(struct.pack("<ffff", *diffuse_color))
  file.write(struct.pack("<ffff", *specular_color))
  file.write(struct.pack("<ffff", 0.0, 0.0, 0.0, 1.0))
  file.write(struct.pack("<ffff", 0.0, 0.0, 0.0, 1.0))
  
  file.write(struct.pack("<f", specular_hardness))
  file.write(struct.pack("<f", material.ambient))
  
  # full emission if shadeless
  if material.use_shadeless:
    file.write(struct.pack("<f", 1.0))
  else:
    file.write(struct.pack("<f", material.emit))
    
  file.write(struct.pack("<f", material.specular_ior))
  
  # write textures
  num_textures = 0
  texture_ptr = file.tell()
  file.write(struct.pack("<I", 0))
  
  for slot in material.texture_slots:
    if slot is not None and slot.texture is not None and slot.use:
      # get blend mode
      blend_mode = texture_blend_type_dict.get(slot.blend_type, 0)
        
      # write stuff about this texture (TODO: clean)
      # TODO: REALLY CLEAN, It's gotten worse
      if slot.use_map_color_diffuse:
        write_texture_reference(file, slot.texture, 0, slot.diffuse_color_factor, blend_mode, slot.offset, slot.scale) #diffuse.color
        num_textures += 1
      if slot.use_map_diffuse:
        write_texture_reference(file, slot.texture, 1, slot.diffuse_factor, blend_mode, slot.offset, slot.scale) #diffuse.intensity
        num_textures += 1
      if slot.use_map_color_spec:
        write_texture_reference(file, slot.texture, 2, slot.specular_color_factor, blend_mode, slot.offset, slot.scale) #specular.color
        num_textures += 1
      if slot.use_map_specular:
        write_texture_reference(file, slot.texture, 3, slot.specular_factor, blend_mode, slot.offset, slot.scale) #specular.intensity
        num_textures += 1
      if slot.use_map_hardness:
        write_texture_reference(file, slot.texture, 4, slot.hardness_factor, blend_mode, slot.offset, slot.scale) #specular.hardness
        num_textures += 1
      if slot.use_map_displacement:
        write_texture_reference(file, slot.texture, 6, slot.displacement_factor, blend_mode, slot.offset, slot.scale) #displacement
        num_textures += 1
      if slot.use_map_ambient:
        write_texture_reference(file, slot.texture, 8, slot.ambient_factor, blend_mode, slot.offset, slot.scale) #ambient
        num_textures += 1
      if slot.use_map_translucency or slot.use_map_alpha:
        write_texture_reference(file, slot.texture, 7, (slot.translucency_factor if slot.use_map_translucency else slot.alpha_factor), blend_mode, slot.offset, slot.scale) #translucency
        num_textures += 1
      if slot.use_map_normal:
        write_texture_reference(file, slot.texture, 12, slot.normal_factor, blend_mode, slot.offset, slot.scale) #normalmap
        num_textures += 1
      if slot.use_map_emit:
        write_texture_reference(file, slot.texture, 9, slot.emit_factor, blend_mode, slot.offset, slot.scale) #emission
        num_textures += 1  
  
  # go back and write num textures
  file.seek(texture_ptr)
  file.write(struct.pack("<I", num_textures))
  file.seek(0, 2)
  
  close_chunk(file, ptr)
  
def write_mesh_chunk(file, mesh):
  # write chunk
  ptr = create_chunk(file, "MESH", 3, get_uuid())
  
  write_string(file, mesh.name)
  
  # write mesh info
  file.write(struct.pack("<H", (1 if mesh.use_auto_smooth else 0)))
  file.write(struct.pack("<H", (1 if len(mesh.vertices) <= 65535 else 0)))
  
  # write bounding box
  bbox_min, bbox_max, bbox_center = bounds(mesh)
  file.write(struct.pack("<fff", *bbox_min))
  file.write(struct.pack("<fff", *bbox_max))
  file.write(struct.pack("<fff", *bbox_center))
  
  # load up bmesh data
  bm = bmesh.new()
  
  # use mesh with modifiers applied if we only have one user & the export option was set
  if mesh.users == 1 and export_options["MODIFIER_MODE"] == 'apply':
    # find our parent owner
    for ob in bpy.data.objects:
      if ob.type == 'MESH' and ob.data.name == mesh.name:
        bm.from_mesh(ob.to_mesh(bpy.context.scene, apply_modifiers = True, settings='PREVIEW'))
  else:
    bm.from_mesh(mesh)
  
  # get edge crease layer
  crease_layer = bm.edges.layers.crease.verify()
  
  # log edges we want to export
  # we do this so we don't have to loop the edge table
  # several times
  export_edges = []
  edge_index_remap = {}
  for edge in bm.edges:
    crease = edge[crease_layer]
    if not edge.smooth or edge.seam or crease > 0:
      edge_index_remap[edge.index] = len(export_edges)
      export_edges.append(edge)
      
  # gather tag list
  tag_list = []
  for edge in export_edges:
    if not edge.smooth and not "SHARP" in tag_list:
      tag_list.append("SHARP")
    if edge.seam and not "SEAM" in tag_list:
      tag_list.append("SEAM")
  
  # write tag list
  file.write(struct.pack("<H", len(tag_list)))
  for tag in tag_list:
    write_string(file, tag)
  
  # write and gather color and uv layers
  file.write(struct.pack("<HH", len(mesh.uv_layers), len(mesh.vertex_colors)))
  bm_uv_layers = []
  bm_vc_layers = []
  
  for uv_layer in mesh.uv_layers:
    write_string(file, uv_layer.name)
    file.write(struct.pack("<H", (1 if mesh.uv_layers.active.name == uv_layer.name else 0)))
    bm_uv_layers.append(bm.loops.layers.uv.get(uv_layer.name))
    
  for vc_layer in mesh.vertex_colors:
    write_string(file, vc_layer.name)
    file.write(struct.pack("<H", (1 if vc_layer.active_render else 0)))
    bm_vc_layers.append(bm.loops.layers.color.get(vc_layer.name))
  
  
  # gather tag links
  tag_links = []
  
  for edge in export_edges:
    if not edge.smooth:
      tag_links.append((1, tag_list.index("SHARP"), edge_index_remap[edge.index]))
    if edge.seam:
      tag_links.append((1, tag_list.index("SEAM"), edge_index_remap[edge.index]))
  
  # write  tag links (but get some important data first!)
  num_verts = len(bm.verts)
  compact_indices = (num_verts <= 65535) # if we have less than 65535 verts, use short instead of long  
  
  file.write(struct.pack("<I", len(tag_links)))
  for link in tag_links:
    file.write(struct.pack("<HH", link[0], link[1])) #type, ID
    file.write(struct.pack(("H" if compact_indices else "I"), link[2])) # index in list of vert/edge/face
    
  
  # write geometry
  file.write(struct.pack("<III", num_verts, len(export_edges), max(len(mesh.materials), 1)))
  for vert in bm.verts:
    file.write(struct.pack("<fff", vert.co[0], vert.co[1], vert.co[2]))
    file.write(struct.pack("<fff", vert.normal[0], vert.normal[1], vert.normal[2]))
  
  for edge in export_edges:
    file.write(struct.pack(("HH" if compact_indices else "II"), edge.verts[0].index, edge.verts[1].index))
    file.write(struct.pack("<f", crease))
  
  # gather num faces on each mat
  num_materials = max(len(mesh.materials), 1)
  face_counts = [0] * num_materials
  for face in bm.faces:
    face_counts[max(face.material_index, 0)] += 1
  
  # gather prim types (num sides) and build prim groups
  max_prim = 0
  for face in bm.faces:
    num_sides = len(face.loops)
    max_prim = max(num_sides, max_prim)
  
  # write FaceContainers
  for mat_index in range(num_materials):
    # find out how what kind of prims we need
    prim_map = {}
    for face in bm.faces:
      # only grab faces for this material
      if max(face.material_index, 0) != mat_index:
        continue
        
      # get num sides and add to map if it's not there
      num_sides = len(face.loops)
      if not num_sides in prim_map:
        prim_map[num_sides] = 1
      else:
        prim_map[num_sides] += 1
    
    #write facecontainer 
    file.write(struct.pack("<H", len(prim_map)))
    
    # write primgroups
    for key in prim_map:
      file.write(struct.pack("<IH", prim_map[key], key))
      
      # write faces for prim group
      for face in bm.faces:
        # verify we're on the right mat
        if max(face.material_index, 0) != mat_index or len(face.loops) != key:
          continue
        
        # write face
        for loop in face.loops:
          file.write(struct.pack(("H" if compact_indices else "I"), loop.vert.index))
          for uv_layer in bm_uv_layers:
            uv_loop = loop[uv_layer]
            file.write(struct.pack("<ff", uv_loop.uv[0], uv_loop.uv[1]))
          for vc_layer in bm_vc_layers:
            vc_loop = loop[vc_layer]
            file.write(struct.pack("<ffff", vc_loop[0], vc_loop[1], vc_loop[2], 1.0))
   
  # release resources
  bm.free()
  
  close_chunk(file, ptr)


def write_collision_chunk(file, rigidbody):
  # write chunk
  ptr = create_chunk(file, "COLL", 1, get_uuid())
  
  prim_type = rigidbody_shape_dict.get(rigidbody.collision_shape, 0)
  file.write(struct.pack("<H", prim_type))
  file.write(struct.pack("ffffff", 0, 0, 0, 1, 1, 1))
    
  file.write(struct.pack("<ff", rigidbody.friction, rigidbody.restitution))
  
  # write mesh id if applicable
  if prim_type >= 5:
    rigidbody_parent = bpy.data.objects[rigidbody.id_data.name]
    if rigidbody_parent.type == 'MESH':
      file.write(struct.pack("<I", mesh_map[rigidbody_parent.data.name]))
    else:
      file.write(struct.pack("<i", -1))
    
  close_chunk(file, ptr)
    
  
def write_rigidbody_chunk(file, rigidbody):
  # write chunk
  ptr = create_chunk(file, "RGDB", 1, get_uuid())
  
  file.write(struct.pack("<fff", rigidbody.mass, 
                                  rigidbody.linear_damping, 
                                  rigidbody.angular_damping,))
  
  file.write(struct.pack("<HH", (1 if rigidbody.kinematic else 0), (1 if rigidbody.use_start_deactivated else 0)))
  
  close_chunk(file, ptr)
  
def write_spline_chunk(file, resolution, spline):
  # write chunk
  ptr = create_chunk(file, "SPLN", 1, get_uuid())
  
  #write spline point count
  point_source = sub_spline.bezier_points if sub_spline.type == 'BEZIER' else sub_spline.points
  file.write(struct.pack("<I", len(point_source)))
  
  # write segment count
  file.write(struct.pack("<H", resolution))
  
  #write looped
  file.write(struct.pack("<H", (1 if spline.use_cyclic_u else 0)))
  
  # get type and tilt type
  type = curve_type_dict.get(spline.type, 0)
  tilt_type = curve_tilt_dict.get(spline.tilt_interpolation, 0)
    
  # write type and tilt type
  file.write(struct.pack("<HH", type, tilt_type))
  
  for point in point_source:
    file.write(struct.pack("<fff", point.co[0], point.co[1], point.co[2]))
    file.write(struct.pack("<fff", point.radius, point.tilt, (point.weight if sub_spline.type != 'BEZIER' else 0.0)))
    if sub_spline.type == 'BEZIER':
      file.write(struct.pack("<fff", point.handle_left[0], point.handle_left[1], point.handle_left[2]))
      file.write(struct.pack("<fff", point.handle_right[0], point.handle_right[1], point.handle_right[2]))
  
  
  close_chunk(file, ptr)

  
def write_vertex_group_chunk(file, group, object):
    # write chunk
    ptr = create_chunk(file, "VTXG", 1, get_uuid())
    
    num_vertices = len(object.data.vertices)
    
    # write name
    write_string(file, group.name)
    active = (group.name == object.vertex_groups.active.name)
    
    # calculate sub pairs for efficient storage
    sub_pairs = []
    
    pair_start = 0
    pair_end = 0
    in_void = False
    
    # look through verts + 1 to cause an exeption on the last vert
    # kinda hacky :D
    for vert_index in range(num_vertices + 1):
      try:
        # hack since we have no exception for out of bounds :|
        if vert_index == num_vertices:
          raise Exception("Shieeet")
          
        group.weight(vert_index)
        
        # start a new pair if the last thing we did was get an exception
        if in_void:
          in_void = False
          pair_start = vert_index
          
        pair_end = vert_index
      except Exception:
        if not in_void and pair_end != pair_start:
          sub_pairs.append([pair_start, pair_end])
          
        in_void = True
    
    # write the rest of the VertexGroup, then write the sub pairs
    file.write(struct.pack("<HH", (1 if active else 0), len(sub_pairs)))
    
    for pair in sub_pairs:
      file.write(struct.pack("<II", *pair))
      for vert_index in range(pair[0], pair[1] + 1):
        file.write(struct.pack("<f", group.weight(vert_index)))
      
      
    
    # close chunk
    close_chunk(file, ptr)    
    

def write_constraint_info(file, constraint):
  # write constraint info
  file.write(struct.pack("<HH", (0 if constraint.disable_collisions else 1), (1 if constraint.use_breaking else 0)))
  
  # write break threshold
  if constraint.use_breaking:
    file.write(struct.pack("f", constraint.breaking_threshold))
    

def write_spring_joint_chunk(file, constraint):
  ptr = create_chunk(file, "SJNT", 1, get_uuid())
  
  # spring joint specific
  constraint_obj_id = -1 if constraint.object2 is None else object_map[constraint.object2.name]
  file.write(struct.pack("<i", constraint_obj_id))
  
  file.write(struct.pack("fff", 0, 0, 0)) # local attachment point
  
  # compute avg spring damp and force
  avg_spring_damp = (constraint.spring_damping_x, constraint.spring_damping_y, constraint.spring_damping_z) / 3
  avg_spring_force = (constraint.spring_stiffness_x, constraint.spring_stiffness_y, constraint.spring_stiffness_z) / 3
  
  file.write(struct.pack("ff", avg_spring_force, avg_spring_damp))
  
  # write constraint shared info
  write_constraint_info(file, constraint)
  
  close_chunk(file, ptr)
  
def write_fixed_joint_chunk(file, constraint):
  ptr = create_chunk(file, "FJNT", 1, get_uuid())
  
  # fixed joint specific
  constraint_obj_id = -1 if constraint.object2 is None else object_map[constraint.object2.name]
  file.write(struct.pack("<i", constraint_obj_id))
  
  # write constraint shared info
  write_constraint_info(file, constraint)
  
  close_chunk(file, ptr)

  
def write_hinge_joint_chunk(file, constraint):
  ptr = create_chunk(file, "HJNT", 1, get_uuid())
  
  # hinge  joint specific
  constraint_obj_id = -1 if constraint.object2 is None else object_map[constraint.object2.name]
  file.write(struct.pack("<i", constraint_obj_id))
  
  file.write(struct.pack("fff", 0, 0, 0)) # local attachment point
  
  # calculate rotation axis
  if constraint.object2 is None:
    file.write(struct.pack("fff", 0, 0, 0)) # hinge axis, no reference to anything so 0,0,0
  else:
    parent_rotation = mathutils.Euler(constraint.object2.rotation_euler, 'XYZ').to_quaternion()
    rotation_axis = None
    if constraint.type == 'HINGE':
      rotation_axis = parent_rotation * mathutils.Vector((0,0,1))
    elif constraint.type == 'MOTOR':
      rotation_axis = parent_rotation * mathutils.Vector((1,0,0))
    file.write(struct.pack("fff", rotation_axis[0], rotation_axis[1], rotation_axis[2])) # hinge axis
  
  # rotation limits
  file.write(struct.pack("H", (1 if constraint.use_limit_ang_z else 0)))
  if constraint.use_limit_ang_z:
    file.write(struct.pack("ff", math.degrees(constraint.limit_ang_z_lower), math.degrees(constraint.limit_ang_z_upper)))
  
  # motor specific
  file.write(struct.pack("H", (1 if (constraint.type == 'MOTOR' and constraint.use_motor_ang) else 0)))
  if constraint.type == 'MOTOR' and constraint.use_motor_ang:
    file.write(struct.pack("ff", constraint.motor_ang_target_velocity, constraint.motor_ang_max_impulse))
  
  # write constraint shared info
  write_constraint_info(file, constraint)
  
  close_chunk(file, ptr)

  
def write_constraint_chunk(file, constraint):
  if constraint.type == 'HINGE' or constraint.type == 'MOTOR':
    write_hinge_joint_chunk(file, constraint)
  if constraint.type == 'GENERIC_SPRING':
    write_spring_joint_chunk(file, constraint)
  if constraint.type == 'FIXED':
    write_fixed_joint_chunk(file, constraint)

    
def write_file_chunk(file):
  ptr = create_chunk(file, "FILE", 1, get_uuid())
  
  file.write(struct.pack("<H",1)) # feature set 1
  
  close_chunk(file, ptr)
  

def write_anim_chunk(file, anim):
  ptr = create_chunk(file, "ANIM", 2, get_uuid())
  
  # write name
  write_string(file, anim.name)
  
  # math
  frame_divisor = float(bpy.context.scene.render.fps)
  
  # write header
  curve_count = len(anim.fcurves)
  file.write(struct.pack("<ffI", 
                         anim.frame_range[0] / frame_divisor, 
                         anim.frame_range[1] / frame_divisor,
                         curve_count))
  
  # write curves
  for curve in anim.fcurves:
    # make a data path like "location_0" etc, and use the translated result
    data_path = translate_data_path(curve.data_path + ":" + str(curve.array_index))
    
    # get animation data
    keyframes = curve.keyframe_points
    
    # write curve header
    write_string(file, data_path)
    file.write(struct.pack("<H", 0)) # value type = 0 (float)
    file.write(struct.pack("<I", len(keyframes))) # keyframes
    # write keyframes
    for kf in keyframes:
      # calculate keyframe data
      kf_time =  kf.co[0]
      kf_value = curve.evaluate(kf_time)
      kf_in_tangent = angle2d(kf.co, kf.handle_left)
      kf_out_tangent = angle2d(kf.co, kf.handle_right)
      
      # get interpolation type
      kf_interpolation_type = 1 # default to linear
      if kf.interpolation == 'CONSTANT':
        kf_interpolation_type = 0
      else:
        kf_interpolation_type = 2
      
      # special case: convert from radians to degrees (I got it, I figured it out!)
      if curve.data_path == "rotation_euler":
        kf_value = math.degrees(kf_value)
      
      # write keyframe data
      file.write(struct.pack("<fffHf", kf_time / frame_divisor, kf_in_tangent, kf_out_tangent, kf_interpolation_type, kf_value))
    
  # finish off
  close_chunk(file, ptr)

def write_armature_chunk(file, armature):
  ptr = create_chunk(file, "SKEL", 1, get_uuid())
  
  bone_map = {}
  cur_bone_idx = 0
  
  # write num bones
  file.write(struct.pack('<H', len(armature.bones)))
  
  # create bone map
  for bone in armature.bones:
    bone_map[bone.name] = cur_bone_idx
    cur_bone_idx += 1
    
  # bone export
  for bone in armature.bones:
    write_string(file, bone.name)
    
    # write parent
    if bone.parent is not None:
      file.write(struct.pack('<h', bone_map[bone.parent.name]))
    else:
      file.write(struct.pack('<h', -1)) # root
    
    file.write(struct.pack("<fff", *bone.head_local))
    file.write(struct.pack("<fff", *bone.tail_local))
    file.write(struct.pack("<f", 0)) # TODO : USE EDIT BONE ROLL
    
  close_chunk(file, ptr)
  
######################################################
# EXPORT HELPERS
######################################################
def get_heirarchy_level(ob):
  level = 0
  
  current_object = ob
  while current_object.parent is not None:
    level += 1
    current_object = current_object.parent
    
  return level


def angle2d(p1, p2):
    s = p1[0] * p2[1] - p2[0] * p1[1] 
    c = p1[0] * p2[0] + p1[1] * p2[1]
    return math.atan2(s, c)

    
def translate_data_path(path):
  seperated = path.split('"].')
  
  # get parts based on content
  print("translating " + path)
  parts = None
  if '"].' in path:
    parts = seperated[1].split(':')
  else:
    parts = path.split(':')
  
  # TRS
  if parts[0] == "location" or parts[0] == "scale" or parts[0] == "rotation_euler" or parts[0] == "position" or parts[0] == "rotation_quaternion":
      base_prop = ""
      # if this accesses a cihld object, set base path first
      # using the child operator (object:propertypath)
      if len(seperated) > 1:
        base_prop = "Bone/" + seperated[0].split('["')[1] + "/"
      
      # get base path
      if parts[0] == "location" or parts[0] == "position": base_prop += "Transform/Position/"
      if parts[0] == "scale": base_prop += "Transform/Scale/"
      if parts[0] == "rotation_euler": base_prop += "Transform/RotationEuler/"
      if parts[0] == "rotation_quaternion": base_prop += "Transform/RotationQuaternion/"
      
      # add axis
      if parts[1] == "0": base_prop += "X"
      if parts[1] == "1": base_prop += "Y"
      if parts[1] == "2": base_prop += "Z"
      if parts[1] == "3": base_prop += "W"
        
      return base_prop
   
  print("Unable to translate animation path: " + path)


def bounds(msh):
    bnd_max = [-9999.0, -9999.0, -9999.0]
    bnd_min = [9999.0, 9999.0, 9999.0]
    for vert in msh.vertices:
      bnd_min[0] = min(vert.co[0], bnd_min[0])
      bnd_min[1] = min(vert.co[1], bnd_min[1])
      bnd_min[2] = min(vert.co[2], bnd_min[2])
      
      bnd_max[0] = max(vert.co[0], bnd_max[0])
      bnd_max[1] = max(vert.co[1], bnd_max[1])
      bnd_max[2] = max(vert.co[2], bnd_max[2])
    bnd_center = [(bnd_min[0] + bnd_max[0]) / 2, (bnd_min[1] + bnd_max[1]) / 2, (bnd_min[2] + bnd_max[2]) / 2]
    return bnd_min, bnd_max, bnd_center

def truncate_format_string(format):
    """truncate or expand format string to 4 chars"""
    if format == 'TARGA' or format == 'TARGA_RAW':
      return "TGA "
    elif format == 'JPEG' or format == 'JPEG2000':
      return "JPEG"
    elif format == 'THEORA':
      return "THEO"
    elif format == 'FFMPEG':
      return "MPEG"
    elif format == 'FRAMESERVER':
      return "FSVR"
    elif format == 'AVI_RAW' or format == 'AVI_JPEG':
      return "AVI "
    elif format == 'OPEN_EXR':
      return "EXR "
    elif format == 'OPEN_EXR_MULTILAYER':
      return "EXRM"
    elif format == 'CINEON':
      return "CINE"
    elif len(format) == 3:
      return format + " "
    else:
      return format


def write_texture_reference(file, texture, mapping, multiplier, blend_type, offset, scale):
    file.write(struct.pack("<I", texture_map[texture.name]))
    file.write(struct.pack("<HH", mapping, blend_type))
    file.write(struct.pack("<f", multiplier))
    file.write(struct.pack("<ff", offset[0], offset[1]))
    file.write(struct.pack("<ff", scale[0], scale[1]))

    
def write_string(file, strng):
    file.write(struct.pack("B", len(strng)))
    file.write(strng.encode("ascii"))
    
    if (len(strng) % 2) == 0:
      # write padding byte. hacky but it works
      file.write("\x00".encode("ascii"))

      
def get_uuid():
    global current_id
    current_id += 1
    return current_id

    
def create_chunk(file, type, version, id):
    # verify length
    if(len(type) != 4):
      raise Exception("create_chunk got invalid type! (given " + type + ")")
      
    # get ptr
    ptr = file.tell()
    
    #write LIST header
    file.write(("LISTxxxx" + type).encode("ascii"))
    
    # write INFO chunk
    file.write("INFO".encode("ascii"))
    file.write(struct.pack("<III", 8, version, id)) #8 length for 2 ints

    # write DATA chunk header
    file.write("DATAxxxx".encode("ascii"))
    
    return ptr


def close_chunk(file, ptr):
    # get difference
    difference = file.tell() - ptr
    list_length = difference - 8
    data_length = list_length - 28
    
    # write LIST length
    file.seek(ptr + 4)
    file.write(struct.pack("<I", list_length))
    
    # write DATA length
    file.seek(24, 1)
    file.write(struct.pack("<I", data_length))
    
    # seek back to end
    file.seek(0, 2)

    
def create_chunk_map():
    return None
######################################################
# EXPORT MAIN FILES
######################################################
def export_scene(file):
    # reset globals
    global current_id
    current_id = -1
    
    # write RIFF header
    file.write("RIFFxxxxSCNE".encode("ascii"))
    
    # write info
    write_file_chunk(file)
    
    # write scene
    write_scene_chunk(file, bpy.data.worlds[0])
    
    # write meta
    meta_test = [["exporter", "BlenderOfficial"], 
                 ["package", "Blender " + bpy.app.version_string + " " + bpy.app.version_cycle],
                 ["source", bpy.path.basename(bpy.context.blend_data.filepath)],
                 ["author", os.getlogin()]]
                 
    write_meta_chunk(file, meta_test)
    
    # write actions
    global action_map
    action_map = {}
    
    for act in bpy.data.actions:
      write_anim_chunk(file, act)
      action_map[act.name] = current_id

    # write sounds
    global sound_map
    sound_map = {}
    
    for snd in bpy.data.sounds:
      write_sound_resource_chunk(file, snd)
      sound_map[snd.name] = current_id
    
    # write speakers
    global speaker_map
    speaker_map = {}
    
    for spkr in bpy.data.speakers:
      write_speaker_chunk(file, spkr)
      speaker_map[spkr.name] = current_id
      
    # write lights
    global lamp_map
    lamp_map = {}
    
    for lght in bpy.data.lamps:
      write_light_chunk(file, lght)
      lamp_map[lght.name] = current_id
    
    # write cameras
    global camera_map
    camera_map = {}
    
    for cmra in bpy.data.cameras:
      write_camera_chunk(file, cmra)
      camera_map[cmra.name] = current_id
    
    # write textures
    global texture_map
    texture_map = {}
    
    for txtr in bpy.data.textures:
      write_texture_resource_chunk(file, txtr)
      texture_map[txtr.name] = current_id
    
    # write materials
    global material_map
    material_map = {}
    
    for mtrl in bpy.data.materials:
      # don't write unused stuff
      if mtrl.users == 0:
        continue
        
      write_material_chunk(file, mtrl)
      material_map[mtrl.name] = current_id
    
    # write armatures
    global armature_map
    armature_map = {}
    
    for arma in bpy.data.armatures:
      write_armature_chunk(file, arma)
      armature_map[arma.name] = current_id
      
    # write curves
    global curve_map
    curve_map = {}
    
    for curve in bpy.data.curves:
      curve_splines = curve.splines
      spline_count = len(curve_splines)
      for cspline in range(spline_count):
        write_spline_chunk(file, curve.resolution_u, curve_splines[cspline])
        curve_map[curve.name + "_SCN_EXPORT_ID_" + str(cspline)] = current_id
    
    # write meshes
    global mesh_map
    mesh_map = {}
    
    for mesh in bpy.data.meshes:
      # don't write unused stuff
      if mesh.users == 0:
        continue
        
      print("...writing mesh " + mesh.name)
      write_mesh_chunk(file, mesh)
      mesh_map[mesh.name] = current_id
    
    # write userdata (custom props)
    global userdata_map
    userdata_map = {}
    
    for ob in bpy.data.objects:
      if len(ob.keys()) > 0:
        # gather pairs
        userdata = []
        for key in ob.keys():
          # why is this a thing?
          if key == "_RNA_UI":
            continue
            
          userdata.append([key, str(ob[key])])
          
        # write
        write_meta_chunk(file, userdata, "USER")
        userdata_map[ob.name] = current_id
        
    ###################
    #create object map#
    ###################
    global object_map
    object_map = {}
    fake_id = current_id
    
    #first, get the highest heirarchy level
    heirarchy_max_level = 0
    for ob in bpy.data.objects:
      heirarchy_max_level = max(heirarchy_max_level, get_heirarchy_level(ob))
      
    # then map unparented objects, then unparented
    for level in range(heirarchy_max_level + 1):
      for ob in bpy.data.objects:
        # proper level?
        if get_heirarchy_level(ob) != level:
          continue
        
        if ob.rigid_body is not None:
          if ob.rigid_body_constraint is not None and verify_constraint_type(ob.rigid_body_constraint):
            fake_id += 1
          fake_id += 2
        
        if len(ob.vertex_groups) > 0:
          fake_id += 1
          
        # write modifier chunks
        if export_options["MODIFIER_MODE"] == 'preserve':
          for mod in ob.modifiers:
            fake_id += 1
            
        # map object  
        fake_id += 1
        object_map[ob.name] = fake_id
    
    ######################
    # write objects last #
    ######################
    global vertex_group_map, modifier_map, rigidbody_map
    rigidbody_map = {}
    vertex_group_map = {}
    modifier_map = {}
    
    # first write unparented objects, then unparented
    for level in range(heirarchy_max_level + 1):
      for ob in bpy.data.objects:
        # proper level?
        if get_heirarchy_level(ob) != level:
          continue
          
        print("...writing object " + ob.name)
        
        # write the rigidbody chunk
        if ob.rigid_body is not None:
          if ob.rigid_body_constraint is not None and verify_constraint_type(ob.rigid_body_constraint):
            write_constraint_chunk(file, ob.rigid_body_constraint)
          write_collision_chunk(file, ob.rigid_body)
          write_rigidbody_chunk(file, ob.rigid_body)
          rigidbody_map[ob.name] = current_id
        
        # write the vertex group chunk for me!! :)
        if len(ob.vertex_groups) > 0:
          for group in ob.vertex_groups:
            write_vertex_group_chunk(file, group, ob)
            vertex_group_map[group.name] = current_id
          
        # write modifier chunks
        if export_options["MODIFIER_MODE"] == 'preserve':
          for mod in ob.modifiers:
            write_modifier_chunk(file, mod)
            modifier_map[ob.name + "_" + mod.name] = current_id
          
        # write object  
        write_object_chunk(file, ob)
        object_map[ob.name] = current_id
      
    #finish off
    file_length = file.tell()
    file.seek(4)
    file.write(struct.pack("<I", file_length - 8))

######################################################
# EXPORT
######################################################
def save_scn(filepath,
             context):

    print("exporting SCENE: %r..." % (filepath))
    time1 = time.clock()

    # write SCENE
    binfile = open(filepath, 'wb')
    export_scene(binfile)
    binfile.close()
    
    # SCENE export complete
    print(" done in %.4f sec." % (time.clock() - time1))


def save(operator,
         context,
         filepath="",
         embed_resources=False,
         resource_path_mode=None,
         modifier_mode = 'apply',
         ):
    
    # set up options
    global export_options, export_path
    export_path = filepath
    export_options = {}
    
    export_options["EMBED_RESOURCES"] = embed_resources
    export_options["RELATIVITY"] = resource_path_mode
    export_options["MODIFIER_MODE"] = modifier_mode
    
    # save it
    save_scn(filepath,
             context,
             )

    return {'FINISHED'}

