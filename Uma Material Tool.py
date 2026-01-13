bl_info = {
    "name": "Uma Material Tool",
    "author": "Gvt5036",
    "version": (1, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > Uma Tool",
    "description": "Automates LooperHonstropy's Umamusume material setup and renaming.",
    "category": "Object",
}

import bpy
import os

# ------------------------------------------------------------------------
#   Preferences to store Texture Directory
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
#   Core Script
# ------------------------------------------------------------------------
class UMA_OT_ApplyMaterials(bpy.types.Operator):
    """Apply and Rename Uma Materials"""
    bl_idname = "object.uma_apply_materials"
    bl_label = "Apply/Rename Materials"
    bl_options = {'REGISTER', 'UNDO'}

    # Operator properties (inputs for the popup)
    uma_number: bpy.props.StringProperty(name="Uma Number", default="")
    uma_name: bpy.props.StringProperty(name="Uma Name", default="")
    
    # We reproduce the texture dir here so it can be edited in the popup
    texture_dir_override: bpy.props.StringProperty(
        name="Texture Directory", 
        subtype='DIR_PATH',
        description="Leave empty to use User Preferences"
    )

    def invoke(self, context, event):
        # Load default directory from preferences if available
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
        # 1. Validation
        tex_path = self.texture_dir_override
        # Save path back to preferences for convenience
        prefs = context.preferences.addons[__name__].preferences
        prefs.texture_dir = tex_path
        
        if not os.path.isdir(tex_path):
            self.report({'ERROR'}, "Invalid Texture Directory.")
            return {'CANCELLED'}
        
        if not self.uma_number or not self.uma_name:
            self.report({'ERROR'}, "Please enter both Uma Number and Name.")
            return {'CANCELLED'}

        # Find source object
        source_obj_name = "Icosphere of Materials"
        if source_obj_name not in bpy.data.objects:
            self.report({'ERROR'}, f"Object '{source_obj_name}' not found in project.")
            return {'CANCELLED'}
        
        source_obj = bpy.data.objects[source_obj_name]
        
        # Get Source Materials
        src_mat_shader = bpy.data.materials.get("Uma Shader")
        src_mat_eyes = bpy.data.materials.get("Uma Eyes")

        if not src_mat_shader or not src_mat_eyes:
            self.report({'ERROR'}, "Source materials 'Uma Shader' or 'Uma Eyes' missing.")
            return {'CANCELLED'}

        # Get Target Object
        target_obj = context.active_object
        if not target_obj or not target_obj.material_slots:
            self.report({'ERROR'}, "Please select a model with materials.")
            return {'CANCELLED'}

        # 2. Iterate Slots
        for slot in target_obj.material_slots:
            if not slot.material:
                continue
            
            old_name = slot.material.name.lower()
            num = self.uma_number
            name = self.uma_name
            
            new_mat = None
            part_type = None

            # ----------------------------------------------------------------
            #   Identify Part & Rename
            # ----------------------------------------------------------------
            
            # CHECK: BODY
            if f"bdy{num}" in old_name:
                part_type = "Body"
                new_mat = src_mat_shader.copy()
                new_mat.name = f"{name} Body"
                
                self.setup_textures(new_mat, tex_path, num, part="Body")

            # CHECK: FACE
            elif f"chr{num}" in old_name and "face" in old_name:
                part_type = "Face"
                new_mat = src_mat_shader.copy()
                new_mat.name = f"{name} Face"
                
                self.setup_textures(new_mat, tex_path, num, part="Face")
                
                # Toggle Face Param
                self.set_face_toggle(new_mat)

            # CHECK: HAIR
            elif f"chr{num}" in old_name and "hair" in old_name:
                part_type = "Hair"
                new_mat = src_mat_shader.copy()
                new_mat.name = f"{name} Hair"
                
                self.setup_textures(new_mat, tex_path, num, part="Hair")

            # CHECK: TAIL
            elif "tail" in old_name:
                # Tail logic: usually matches if it's a tail material, usually 'tail' is enough context
                # but we check if it follows general tail naming patterns provided
                part_type = "Tail"
                new_mat = src_mat_shader.copy()
                new_mat.name = f"{name} Tail"
                
                self.setup_textures(new_mat, tex_path, num, part="Tail")

            # CHECK: EYE
            elif "eye" in old_name:
                part_type = "Eye"
                new_mat = src_mat_eyes.copy() # Copy Uma Eyes
                new_mat.name = f"{name} Eye"
                # No texture setup for eyes requested

            # ----------------------------------------------------------------
            #   Apply Material to Slot
            # ----------------------------------------------------------------
            if new_mat:
                slot.material = new_mat
            
        # 3. Cleanup unused materials
        # Simple cleanup: iterate all materials, if users == 0, remove. 
        # (Be careful with this, normally blender cleans up on reload, 
        # but we can force it if explicitly requested).
        for mat in bpy.data.materials:
            if mat.users == 0:
                bpy.data.materials.remove(mat)

        self.report({'INFO'}, "Materials Updated Successfully.")
        return {'FINISHED'}

    def set_face_toggle(self, mat):
        """Finds 'Toggle If Face' node/value and sets it to 1"""
        if not mat.use_nodes: return
        
        # Method 1: Look for a Value Node with that label
        for node in mat.node_tree.nodes:
            if "Toggle If Face" in node.label or "Toggle If Face" in node.name:
                if hasattr(node.outputs[0], 'default_value'):
                    node.outputs[0].default_value = 1.0
                    return
        
        # Method 2: If it's a Group Input (if the logic is inside a group)
        # Note: Since the prompt implies editing the shader directly, 
        # we check mostly for Value nodes or Group Inputs.

    def setup_textures(self, mat, directory, num, part):
        """Finds texture nodes in frames and assigns images"""
        if not mat.use_nodes: return

        # Define filenames based on part
        files = {}
        
        if part == "Body":
            files['Base'] = f"tex_bdy{num}_00_base.png"
            files['Ctrl'] = f"tex_bdy{num}_00_ctrl.png"
            files['Shaded'] = f"tex_bdy{num}_00_shad_c.png"
            files['Diffuse'] = f"tex_bdy{num}_00_diff.png"
            
        elif part == "Face":
            files['Base'] = f"tex_chr{num}_00_face_base.png"
            files['Ctrl'] = f"tex_chr{num}_00_face_ctrl.png"
            files['Shaded'] = f"tex_chr{num}_00_face_shad_c.png"
            files['Diffuse'] = f"tex_chr{num}_00_face_diff.png"
            
        elif part == "Hair":
            files['Base'] = f"tex_chr{num}_00_hair_base.png"
            files['Ctrl'] = f"tex_chr{num}_00_hair_ctrl.png"
            files['Shaded'] = f"tex_chr{num}_00_hair_shad_c.png"
            files['Diffuse'] = f"tex_chr{num}_00_hair_diff.png"
            
        elif part == "Tail":
            # Tail Exception logic
            files['Base'] = "tex_tail0001_00_0000_base.png"
            files['Ctrl'] = "tex_tail0001_00_0000_ctrl.png"
            files['Shaded'] = f"tex_tail0001_00_{num}_shad_c.png"
            files['Diffuse'] = f"tex_tail0001_00_{num}_diff.png"

        # Helper to load image
        def load_image(filename, colorspace):
            filepath = os.path.join(directory, filename)
            if not os.path.exists(filepath):
                print(f"Warning: File not found: {filename}")
                return None
            
            try:
                img = bpy.data.images.load(filepath)
                # Set Colorspace
                try:
                    img.colorspace_settings.name = colorspace
                except TypeError:
                    print(f"Colorspace '{colorspace}' not found, defaulting.")
                return img
            except:
                return None

        # Search Nodes
        # We look for nodes that are CHILDREN of a Frame Node with specific labels
        
        nodes = mat.node_tree.nodes
        
        for node in nodes:
            if node.type == 'TEX_IMAGE' and node.parent:
                frame_label = node.parent.label.lower()
                
                target_key = None
                target_cs = "sRGB" # Default fallback
                
                if "base texture" in frame_label:
                    target_key = 'Base'
                    target_cs = "Non-Color"
                elif "ctrl texture" in frame_label:
                    target_key = 'Ctrl'
                    target_cs = "Non-Color"
                elif "shaded" in frame_label:
                    target_key = 'Shaded'
                    target_cs = "ACES 2.0 sRGB"
                elif "diffuse" in frame_label:
                    target_key = 'Diffuse'
                    target_cs = "ACES 2.0 sRGB"
                
                if target_key:
                    img = load_image(files[target_key], target_cs)
                    if img:
                        node.image = img

# ------------------------------------------------------------------------
#   UI Panel
# ------------------------------------------------------------------------
class VIEW3D_PT_UmaPanel(bpy.types.Panel):
    bl_label = "Uma Tool"
    bl_idname = "VIEW3D_PT_uma_tool"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Uma Tool"

    def draw(self, context):
        layout = self.layout
        layout.operator("object.uma_apply_materials")

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