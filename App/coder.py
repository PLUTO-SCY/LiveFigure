import os
from config import Config
import requests
import json
import base64
import traceback
import re
from coder_prompts import PPTX_BEST_PRACTICES, TOOLS_SPECIFICATION

class Coder:
    def __init__(self, api_manager):
        self.api = api_manager

    def generate_image_gemini(self, prompt, output_dir, filename):
        """
        Generate image and save to specified directory
        """
        headers = {
            'Authorization': f'Bearer {Config.GEMINI_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = json.dumps({
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
                "imageConfig": {"aspectRatio": "16:9"}
            }
        })

        try:
            response = requests.post(Config.GEMINI_GEN_IMG_URL, headers=headers, data=payload)
            response.raise_for_status()
            response_json = response.json()

            if "candidates" in response_json and response_json["candidates"]:
                parts = response_json["candidates"][0]["content"]["parts"]
                for part in parts:
                    if "inlineData" in part:
                        base64_data = part["inlineData"]["data"]
                        image_bytes = base64.b64decode(base64_data)
                        
                        save_path = os.path.join(output_dir, filename)
                        with open(save_path, "wb") as f:
                            f.write(image_bytes)
                        print(f"✅ Gemini reference image saved: {save_path}")
                        return save_path
            return None
        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            return None

    def image_to_code(self, image_path, requirement, asset_map=None, output_filename="temp_render.pptx"):
        # Calculate size hints
        w_cm = Config.PPT_WIDTH_Cm
        h_cm = Config.PPT_HEIGHT_Cm

        """
        When generating code, if asset_map exists, inject it into the Prompt.
        """
        asset_prompt_section = ""
        if asset_map:
            asset_info = "\n".join([f'- "{name}": "{path}"' for name, path in asset_map.items()])
            asset_prompt_section = f"""
            *** AVAILABLE PRE-GENERATED ICONS (USE THESE!) ***
            The following complex icons have been pre-generated and saved locally. 
            You MUST use `slide.shapes.add_picture(path, ...)` to insert them instead of drawing them manually.
            
            Registry:
            {asset_info}
            
            Example Usage:
            # Inserting the 'Brain' icon
            slide.shapes.add_picture("{list(asset_map.values())[0] if asset_map else 'path'}", Inches(1), Inches(1), width=Inches(1))
            """
        
        prompt = f"""
        You are an expert Python developer specialized in `python-pptx`.
        
        Task: Write a COMPLETE, STANDALONE Python script to reconstruct the scientific diagram from the image.
        
        Context Requirements:
        1. **Objective**: Create a scientific diagram based on the user's request: "{requirement}".
        2. **Layout Reference**: Mimic the attached image's structure, shapes, arrows, and text.
        3. **Text Guidelines**: 
            - Always use black as the text color.
            - All text inside shapes or text boxes should be center-aligned.
            - Text size should not be too small and should be proportionate to the corresponding shapes.
        4. **Coordinates**: Pay close attention to carefully arranging the coordinates of all components and text! as they directly determine alignment and the overall visual quality of the figure!!!
        
        
        Technical Specifications:
        1. **Canvas Size**: Width = {w_cm} cm, Height = {h_cm} cm. If absolutely necessary, the canvas size may be adjusted at your discretion.
        2. **Output**: You MUST save the presentation exactly as "{output_filename}".
        3. **Imports**: Include ALL necessary imports (Presentation, Cm, Inches, RGBColor, etc.).

        
        {asset_prompt_section}

        {PPTX_BEST_PRACTICES}

        {TOOLS_SPECIFICATION}
        
        !!! IMPORTANT OUTPUT FORMAT !!!
        1. Return **RAW Python code** only.
        2. **DO NOT** use Markdown code blocks (e.g., do NOT use ```python ... ```).
        3. **DO NOT** write any introduction, explanation, or summary.
        4. The output must start directly with `import` and end with the save command.
        """
        return self.api.chat_with_vlm(prompt, image_paths=[image_path], model=Config.MODEL_CODER)

    def debug_code(self, broken_code, error_log):
        """
        Use text-only LLM to fix code based on error log
        """
        output_filename = "temp_render.pptx"
        
        # System Prompt set as Python expert
        system_prompt = "You are an expert Python developer and debugger for the `python-pptx` library."
        
        prompt = f"""
        The following Python script failed to execute.
        
        --------------------------------------------------
        [Error Log]
        {error_log}
        --------------------------------------------------
        
        [Broken Code]
        {broken_code}
        --------------------------------------------------
        
        **Task**:
        1. Analyze the Error Log to identify the syntax or logical issue.
        2. Fix the code to resolve the error.
        3. Ensure the code saves the output as "{output_filename}".
        4. Return the **COMPLETE, FIXED** Python script.
        5. For parts of the code that do not involve errors, no modifications are made.

        {PPTX_BEST_PRACTICES}

        {TOOLS_SPECIFICATION}
        
        !!! IMPORTANT OUTPUT FORMAT !!!
        1. Return **RAW Python code** only.
        2. **DO NOT** use Markdown code blocks (no ```python).
        3. **DO NOT** explain the fix.
        4. Start directly with imports.
        """
        
        # Call text-only interface
        return self.api.chat_with_llm(
            prompt=prompt, 
            system_prompt=system_prompt, 
            model=Config.MODEL_CODER
        )
    

    def refine_code(self, ref_image, current_image, current_code, output_filename="temp_render.pptx"):
        prompt = f"""
        Task: Fix visual discrepancies between Current Image and Reference Image.
        
        Input 1: Reference Image (Goal).
        Input 2: Current Rendered Image (Current Result).
        Input 3: Previous Python Code.
        
        Instructions:
        1. Compare Input 2 against Input 1. Identify missing elements, wrong positions, or incorrect colors.
        2. Modify the Previous Code to fix these issues.
        3. Ensure the code saves the file as "{output_filename}".

        {PPTX_BEST_PRACTICES}

        {TOOLS_SPECIFICATION}
        
        !!! IMPORTANT OUTPUT FORMAT !!!
        1. Return the **FULL, CORRECTED RAW Python code**.
        2. **DO NOT** use Markdown backticks (```).
        3. **DO NOT** explain what you changed. Just output the code.
        4. Start directly with `import`.
        
        Previous Code:
        {current_code}
        """
        return self.api.chat_with_vlm(prompt, image_paths=[ref_image, current_image], model=Config.MODEL_CODER)


    def generate_critique(self, ref_image, current_image):
        """
        [Critic Role]
        Compare two images and output specific, actionable modification suggestions bound to specific elements.
        """
        prompt = """
        You are a **Senior Design QA Engineer** for scientific publications.
        Your goal is to guide a developer to fix the "Current Result" to match the high standards of the "Reference Goal".
        
        Task: Compare the images and perform a **Structured Visual Inspection** using the checklist below.
        
        ### ⚠️ CRITICAL REQUIREMENT: BE SPECIFIC
        - **BAD:** "Fix the arrow."
        - **GOOD:** "Change the **arrow connecting 'Input' and 'Model'** to **Elbow Connector**."
        - **GOOD:** "The arrow head is too huge. Change it to **Medium** size."
        
        --------------------------------------------------
        
        ### 🔍 INSPECTION CHECKLIST (Check these 4 dimensions):
        
        **1. CANVAS & BOUNDARIES (Critical)**
           - Check: Is any content (especially on the Right or Bottom) **clipped or cut off** by the slide edge?
           - **Fix Advice**: "Move [Specific Element Name] LEFT/UP to avoid clipping" or "Shift ALL elements LEFT".
           - If absolutely necessary, the canvas size can be adjusted.
        
        **2. CONNECTOR LOGIC & STYLE (Critical)**
           - Check: Do any arrows **cross OVER text boxes** or other shapes instead of going around them? (Severe Error).
           - Check: Are arrow start/end points attached to the correct side of the nodes?
           - **Check (Style)**: Is the **Arrowhead too large/clumsy**? Is the line too thick (looks like a stick) or too thin? 
             *(Scientific figures usually prefer **1.5pt - 2.0pt** lines and **Medium** or **Small** arrowheads)*.
           - **Fix Advice**: 
             - "Reroute arrow between [A] and [B] to avoid [C]"
             - "Set connector type to **Elbow**"
             - "**Reduce arrowhead size** to Medium or Small"
             - "Set line width to **1.5 pt**".
        
        **3. TEXT INTEGRITY**
           - Check: Is text **spilling out** of its container?
           - Check: Is font size too large (crowded) or too small (unreadable)?
           - Check: **Font Color**. Is it too light? (Standard should be **BLACK** or dark gray).
           - **Fix Advice**: "Move [Specific Text Box] RIGHT by [approx distance]", "Change [Specific Label] color to BLACK", "Widen [Specific Shape]".
        
        **4. VISUAL ALIGNMENT & STYLE**
           - Check: Is the logical layout structure consistent with the Reference? 
           - Check: Are colors professional? (Avoid neon/light colors unless necessary).
        
        --------------------------------------------------
        
        ### 📝 OUTPUT REQUIREMENTS:
        - Provide a **numbered list** of the top 3-5 most critical issues.
        - Use the format: **[CATEGORY] Issue Description -> Actionable Fix**.
        - **Negative Constraint**: Do NOT output Python code. Do NOT provide vague advice.
        
        ### Example Output:
        1. [BOUNDARIES] The **'Output' block** on the far right is cut off -> Shift the **'Output' block** and its label LEFT by approx 1 inch.
        2. [CONNECTORS] The arrow from **'Encoder'** to **'Decoder'** cuts through the text -> Change to **Elbow Type**.
        3. [CONNECTORS] The arrowheads on the main flow are **too large and block the text** -> Set arrow tail/head width to **SMALL**.
        4. [TEXT] The **'Feed Forward' text** is grey -> Change font color to **BLACK**.
        """
        
        print(f"👀 [Critic] Performing structured visual inspection (Focus: Specific Entities & Arrow Styles)...")
        return self.api.chat_with_vlm(prompt, image_paths=[ref_image, current_image], model=Config.MODEL_CODER)


    def refine_code_with_critique(self, ref_image, current_image, current_code, critique, output_filename="temp_render.pptx"):
        """
        [Actor Role]
        Modify Python code based on Critic's suggestions and visual reference.
        Key point: Surgical modifications only, strictly prohibit rewriting overall logic, strictly prohibit discarding existing assets.
        """
        prompt = f"""
        You are an expert Python Developer (The Actor) specializing in **Surgical Code Maintenance**.
        
        Task: Apply the Critic's specific fixes to the "Current Code" to match the visual goal.
        
        Inputs:
        1. **Reference Image**: The visual goal.
        2. **Current Image**: What the current code produces.
        3. **Critic's Feedback**: A checklist of specific bugs/issues.
        
        **CRITIC'S FEEDBACK (STRICTLY EXECUTE THESE FIXES ONLY):**
        {critique}
        
        --------------------------------------------------
        
        ### ⚠️ CRITICAL CONSTRAINTS (READ CAREFULLY):
        
        1. **SURGICAL EDITS ONLY**: 
           - **DO NOT** rewrite the entire layout logic.
           - Only modify the specific lines (coordinates, sizes, colors, connectors) mentioned in the Feedback.
           - **Keep 95% of the original code unchanged.** If the Critic didn't mention it, DO NOT TOUCH IT.
           
        2. **PRESERVE ASSETS (VERY IMPORTANT)**: 
           - The code uses `add_picture(..., image_path=...)` to load high-quality icons.
           - **NEVER** replace these `add_picture` calls with `add_block` or raw shapes.
           - If an icon is in the wrong place, update its `left/top` coordinates in `add_picture`. **DO NOT delete it.**
           
        3. **STABILITY**: 
           - Do not reinvent the wheel. If the overall structure is close, just tweak the parameters (e.g., `left += Inches(0.5)`).
           - Do not change variable names or the overall flow.
        
        {PPTX_BEST_PRACTICES}
        
        {TOOLS_SPECIFICATION}
        
        !!! IMPORTANT OUTPUT FORMAT !!!
        1. Return the **FULL, CORRECTED RAW Python code**.
        2. **DO NOT** use Markdown backticks (```).
        3. **DO NOT** explain what you changed. Just output the code.
        4. Start directly with `import`.
        5. Ensure the code saves the result file as "{output_filename}".
        
        Previous Code:
        {current_code}
        """
        
        print(f"🎨 [Actor] Performing targeted code correction (Surgical Edits)...")
        return self.api.chat_with_vlm(prompt, image_paths=[ref_image, current_image], model=Config.MODEL_CODER)
    
    
    def plan_complex_icons(self, ref_image_path):
        """
        [Enhanced Version] Observe reference image, identify complex icons that need to be extracted.
        Uses regex to extract JSON and relaxes judgment criteria.
        """
        # Relaxed criteria Prompt
        prompt = """
        Analyze the scientific diagram provided. 
        Your task is to identify **Meaningful Visual Icons** that should be extracted as separate assets.

        ### What counts as a "Complex Icon"? (Broad Criteria)
        1. **Symbolic Objects**: Any graphic representing a concept (e.g., "Server", "Database", "Document", "User", "Brain", "Globe", "Lock").
        2. **Composite Shapes**: Even if it looks geometric, if it represents a specific entity (e.g., a cylinder representing a "Database", a page icon representing a "File"), include it.
        3. **Illustrations**: Anything that isn't a simple connecting line or a layout frame.

        ### What to EXCLUDE (Strict):
        - Pure layout containers (empty rectangles holding other content).
        - Simple arrows connecting boxes.
        - Text labels themselves (but include the icon *next* to the text).

        ### Output Format (CRITICAL):
        - Return ONLY a raw JSON list of strings.
        - Do not use Markdown code blocks.
        - Do not explain.
        - Example: ["Database Cylinder", "User Avatar", "AI Brain Icon"]
        
        If no icons are found, return [].
        """
        
        try:
            print(f"🔍 [Icon Planner] Requesting VLM to analyze image: {ref_image_path}...")
            response = self.api.chat_with_vlm(prompt, image_paths=[ref_image_path], model=Config.MODEL_PLANNER)
            
            # Debug: Print raw response
            print(f"👀 [Icon Planner Raw Debug]: {repr(response)}") 
            
            if not response:
                return []

            # Robustness fix: Use regex to extract JSON list
            # Find content wrapped in [ ]
            match = re.search(r'\[.*\]', response, re.DOTALL)
            if match:
                json_str = match.group(0)
                icon_list = json.loads(json_str)
                
                # Filter out non-string impurities
                icon_list = [item for item in icon_list if isinstance(item, str)]
                
                if icon_list:
                    print(f"✅ [Icon Planner] Successfully identified: {icon_list}")
                    return icon_list
            
            print("⚠️ [Icon Planner] Failed to extract JSON list from response, or list is empty.")
            return []
            
        except json.JSONDecodeError as e:
            print(f"❌ [Icon Planner] JSON parsing failed: {e}. Raw content might be invalid.")
            return []
        except Exception as e:
            print(f"⚠️ Icon Planning Failed (Unknown Error): {e}")
            return []
        

    def batch_extract_descriptions(self, ref_image_path, icon_list):
        """
        [New] Reuse the original batch_extract_descriptions logic,
        but changed to call self.api to maintain unified VLM interface.
        """
        if not icon_list: return {}
        
        req_str = json.dumps(icon_list, ensure_ascii=False)
        prompt = f"""
        Look at the image. Extract visual descriptions for these specific icons:
        {req_str}
        
        Task:
        1. Locate each icon in the image.
        2. Describe its visual appearance (color, shape, style) in detail so a painter can recreate it.
        3. Return a JSON object: {{ "Icon Name": "visual_description", ... }}
        """
        
        try:
            response = self.api.chat_with_vlm(
                prompt,
                image_paths=[ref_image_path],
                model=Config.MODEL_PLANNER
            )
            json_str = response.replace("```json", "").replace("```", "").strip()
            return json.loads(json_str)

        except Exception as e:
            return {
                "error": str(e),
                "traceback": traceback.format_exc()
            }

