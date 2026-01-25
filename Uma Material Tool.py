bl_info = {
    "name": "Uma Material Tool",
    "author": "Gvt5036",
    "version": (1, 1),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Uma Tool",
    "description": "Automates LooperHonstropy's Umamusume material setup and renaming.",
    "category": "Object",
}

import bpy
import os
import re

# ------------------------------------------------------------------------
#   Preferences
# ------------------------------------------------------------------------
class UmaToolPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    texture_dir: bpy.props.StringProperty(
        name="Texture Directory",
        subtype='DIR_PATH',
        description="Folder where the textures are located"
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "texture_dir")

# ------------------------------------------------------------------------
#   Core Logic
# ------------------------------------------------------------------------
class UMA_OT_ApplyMaterials(bpy.types.Operator):
    """Apply and Rename Uma Materials"""
    bl_idname = "object.uma_apply_materials"
    bl_label = "Apply/Rename Materials"
    bl_options = {'REGISTER', 'UNDO'}

    uma_number: bpy.props.StringProperty(name="Uma Number", default="")
    uma_name: bpy.props.StringProperty(name="Uma Name", default="")
    
    texture_dir_override: bpy.props.StringProperty(
        name="Texture Directory", 
        subtype='DIR_PATH',
        description="Leave empty to use User Preferences"
    )

    def invoke(self, context, event):
        prefs = context.preferences.addons[__name__].preferences
        if prefs.texture_dir and not self.texture_dir_override:
            self.texture_dir_override = prefs.texture_dir
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "texture_dir_override")
        layout.prop(self, "uma_number")
        layout.prop(self, "uma_name")

    def execute(self, context):
        tex_path = self.texture_dir_override
        prefs = context.preferences.addons[__name__].preferences
        prefs.texture_dir = tex_path
        
        if not os.path.isdir(tex_path):
            self.report({'ERROR'}, "Invalid Texture Directory.")
            return {'CANCELLED'}
        
        if not self.uma_number or not self.uma_name:
            self.report({'ERROR'}, "Please enter both Uma Number and Name.")
            return {'CANCELLED'}

        # Get Source Materials
        src_mat_shader = bpy.data.materials.get("Uma Shader")
        src_mat_eyes = bpy.data.materials.get("Uma Eyes")

        if not src_mat_shader or not src_mat_eyes:
            self.report({'ERROR'}, "Source materials 'Uma Shader' or 'Uma Eyes' missing.")
            return {'CANCELLED'}

        target_obj = context.active_object
        if not target_obj or not target_obj.material_slots:
            self.report({'ERROR'}, "Please select a model with materials.")
            return {'CANCELLED'}

        # ---------------------------------------------------------
        # 1. Apply & Rename Materials
        # ---------------------------------------------------------
        for slot in target_obj.material_slots:
            if not slot.material: continue
            
            old_name = slot.material.name.lower()
            num = self.uma_number
            name = self.uma_name
            
            new_mat = None
            
            # --- BODY ---
            if f"bdy{num}" in old_name:
                new_mat = src_mat_shader.copy()
                new_mat.name = f"{name} Body"
                self.setup_standard_textures(new_mat, tex_path, num, "Body")

            # --- FACE ---
            elif f"chr{num}" in old_name and "face" in old_name:
                new_mat = src_mat_shader.copy()
                new_mat.name = f"{name} Face"
                self.setup_standard_textures(new_mat, tex_path, num, "Face")
                self.set_face_toggle(new_mat)

            # --- HAIR ---
            elif f"chr{num}" in old_name and "hair" in old_name:
                new_mat = src_mat_shader.copy()
                new_mat.name = f"{name} Hair"
                self.setup_standard_textures(new_mat, tex_path, num, "Hair")

            # --- TAIL ---
            elif "tail" in old_name:
                new_mat = src_mat_shader.copy()
                new_mat.name = f"{name} Tail"
                self.setup_standard_textures(new_mat, tex_path, num, "Tail")

            # --- EYE ---
            elif "eye" in old_name:
                new_mat = src_mat_eyes.copy()
                new_mat.name = f"{name} Eye"
                self.setup_eye_textures(new_mat, tex_path, num)

            if new_mat:
                slot.material = new_mat

        # ---------------------------------------------------------
        # 2. Cleanup Duplicates
        # ---------------------------------------------------------
        self.cleanup_materials(target_obj, self.uma_name)

        self.report({'INFO'}, "Materials Updated & Cleaned.")
        return {'FINISHED'}

    # ---------------------------------------------------------
    #   Logic Helpers
    # ---------------------------------------------------------

    def set_face_toggle(self, mat):
        """Finds 'Toggle If Face' input in the shader group and sets it to 1"""
        if not mat.use_nodes: return
        
        # Iterate all nodes to find the main Group node (usually "Uma Shader" or similar)
        # We search for a node that HAS an input named "Toggle If Face..."
        for node in mat.node_tree.nodes:
            if node.type == 'GROUP':
                # Check inputs of this group node
                for input_socket in node.inputs:
                    if "toggle if face" in input_socket.name.lower():
                        input_socket.default_value = 1.0
                        return

    def load_image(self, directory, filename, colorspace):
        """Helper to safely load an image and set colorspace"""
        filepath = os.path.join(directory, filename)
        if not os.path.exists(filepath):
            print(f"File missing: {filename}")
            return None
        try:
            img = bpy.data.images.load(filepath)
            try:
                img.colorspace_settings.name = colorspace
            except:
                pass
            return img
        except:
            return None

    def setup_standard_textures(self, mat, directory, num, part):
        """Handles Body, Face, Hair, Tail based on Node Frames"""
        if not mat.use_nodes: return

        files = {}
        if part == "Body":
            files = {
                'Base': f"tex_bdy{num}_00_base.png",
                'Ctrl': f"tex_bdy{num}_00_ctrl.png",
                'Shaded': f"tex_bdy{num}_00_shad_c.png",
                'Diffuse': f"tex_bdy{num}_00_diff.png"
            }
        elif part == "Face":
            files = {
                'Base': f"tex_chr{num}_00_face_base.png",
                'Ctrl': f"tex_chr{num}_00_face_ctrl.png",
                'Shaded': f"tex_chr{num}_00_face_shad_c.png",
                'Diffuse': f"tex_chr{num}_00_face_diff.png"
            }
        elif part == "Hair":
            files = {
                'Base': f"tex_chr{num}_00_hair_base.png",
                'Ctrl': f"tex_chr{num}_00_hair_ctrl.png",
                'Shaded': f"tex_chr{num}_00_hair_shad_c.png",
                'Diffuse': f"tex_chr{num}_00_hair_diff.png"
            }
        elif part == "Tail":
            files = {
                'Base': "tex_tail0001_00_0000_base.png",
                'Ctrl': "tex_tail0001_00_0000_ctrl.png",
                'Shaded': f"tex_tail0001_00_{num}_shad_c.png",
                'Diffuse': f"tex_tail0001_00_{num}_diff.png"
            }

        for node in mat.node_tree.nodes:
            if node.type == 'TEX_IMAGE' and node.parent:
                label = node.parent.label.lower()
                
                target = None
                cs = "sRGB"
                
                if "base texture" in label:
                    target = 'Base'
                    cs = "Non-Color"
                elif "ctrl texture" in label:
                    target = 'Ctrl'
                    cs = "Non-Color"
                elif "shaded" in label:
                    target = 'Shaded'
                    cs = "ACES 2.0 sRGB"
                elif "diffuse" in label:
                    target = 'Diffuse'
                    cs = "ACES 2.0 sRGB"
                
                if target:
                    img = self.load_image(directory, files[target], cs)
                    if img: node.image = img

    def setup_eye_textures(self, mat, directory, num):
        """Handles the Eye Logic: 3 UV-linked textures (sorted Y) + 1 unconnected texture"""
        if not mat.use_nodes: return
        
        # 1. Find all Image Nodes
        img_nodes = [n for n in mat.node_tree.nodes if n.type == 'TEX_IMAGE']
        
        uv_linked_nodes = []
        unconnected_nodes = []
        
        # 2. Check connections
        for node in img_nodes:
            is_connected_to_uv = False
            # Check inputs[0] (Vector). If it has a link, traverse back to see if it hits a UV Map or Mapping node
            if node.inputs[0].is_linked:
                # We assume if it has input, it's the UV ones. 
                # The user said "3 image textures coming from a UV node" vs "1 not connected"
                is_connected_to_uv = True
            
            if is_connected_to_uv:
                uv_linked_nodes.append(node)
            else:
                unconnected_nodes.append(node)
                
        # 3. Sort UV nodes Top-Down (Higher Y is top)
        uv_linked_nodes.sort(key=lambda n: n.location.y, reverse=True)
        
        # 4. Assign Textures
        # The 3 Highlights
        eye_highs = [
            f"tex_chr{num}_00_eyehi00.png",
            f"tex_chr{num}_00_eyehi01.png",
            f"tex_chr{num}_00_eyehi02.png"
        ]
        
        for i, node in enumerate(uv_linked_nodes):
            if i < 3:
                img = self.load_image(directory, eye_highs[i], "sRGB") # Assuming sRGB for eyes unless specified otherwise
                if img: node.image = img
                
        # The Main Eye (Unconnected)
        eye_base_file = f"tex_chr{num}_eye0.png"
        for node in unconnected_nodes:
            # We pick the first unconnected one we find (should only be 1 based on prompt)
            img = self.load_image(directory, eye_base_file, "sRGB")
            if img: node.image = img
            break

    def cleanup_materials(self, obj, uma_name):
        """Removes duplicate slots for Body, Face, Eye, Hair, Tail"""
        target_parts = ["Body", "Face", "Eye", "Hair", "Tail"]
        
        # We need to find the "Best" slot index for each part and list indices to remove
        slots_to_keep = {} # { 'Body': slot_index, 'Face': slot_index ... }
        slots_to_remove = []
        
        # 1. Map parts to slots
        for i, slot in enumerate(obj.material_slots):
            if not slot.material: continue
            
            mat_name = slot.material.name
            
            # check if this material belongs to one of our target parts
            matched_part = None
            for part in target_parts:
                # Pattern: "[Uma Name] [Part]"
                # We look for the exact start string provided in renaming
                target_name_start = f"{uma_name} {part}"
                
                if mat_name.startswith(target_name_start):
                    matched_part = part
                    break
            
            if matched_part:
                # Logic: If we haven't found a slot for this part yet, take this one.
                # If we HAVE found one, check if the current one is "better" (shorter name, no .001)
                # or if the existing one is "better".
                
                if matched_part not in slots_to_keep:
                    slots_to_keep[matched_part] = i
                else:
                    # Compare current slot (i) vs stored slot (existing_i)
                    existing_i = slots_to_keep[matched_part]
                    existing_name = obj.material_slots[existing_i].material.name
                    
                    # Heuristic: The one WITHOUT numbers is better. 
                    # Generally len("Name") < len("Name.001")
                    if len(mat_name) < len(existing_name):
                        # Found a better one, mark the old one for removal, keep new
                        slots_to_remove.append(existing_i)
                        slots_to_keep[matched_part] = i
                    else:
                        # Current one is worse (duplicate), mark for removal
                        slots_to_remove.append(i)
                        
        # 2. Remove slots
        # MUST delete in reverse index order to avoid shifting indices of subsequent items
        slots_to_remove.sort(reverse=True)
        
        for i in slots_to_remove:
            obj.active_material_index = i
            bpy.ops.object.material_slot_remove()

# ------------------------------------------------------------------------
#   Registration
# ------------------------------------------------------------------------
classes = (
    UmaToolPreferences,
    UMA_OT_ApplyMaterials,
    VIEW3D_PT_UmaPanel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()