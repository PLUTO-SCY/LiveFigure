import os
import json
import shutil
import sys
from config import Config
from api_clients import APIManager
from ppt_renderer import PPTRenderer
from coder import Coder
from icon_factory import BatchIconFactory
from visual_researcher import VisualDeepResearcher

class WorkflowManager:
    def __init__(self):
        self.api = APIManager()
        self.coder = Coder(self.api)
        self.renderer = PPTRenderer()
        self.icon_factory = BatchIconFactory()
        
        # Initialize Visual Deep Researcher (optional)
        if Config.ENABLE_DEEP_RESEARCH:
            try:
                self.researcher = VisualDeepResearcher()
                print("  -> Visual Deep Research module enabled")
            except Exception as e:
                print(f"  -> Warning: Failed to initialize Visual Deep Research: {e}")
                self.researcher = None
        else:
            self.researcher = None

    def _save_text(self, path, content):
        """Helper function: Save text file"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    def _generate_and_debug_loop(self, generator_func, run_dir, file_prefix, max_retries=3):
        """[Core Abstraction] Generic code generation -> execution -> auto-debug loop function"""
        print(f"🏗️ [{file_prefix}] Generating code...")
        current_code = generator_func()
        self._save_text(os.path.join(run_dir, f"{file_prefix}_draft.py"), current_code)

        for attempt in range(max_retries + 1):
            print(f"🔄 [{file_prefix}] Compile and run attempt [{attempt}/{max_retries}] ...")
            base_name = f"{file_prefix}_try_{attempt}"
            
            pptx, pdf, png, error_msg = self.renderer.render_pipeline(
                code_str=current_code, 
                output_dir=run_dir, 
                filename_base=base_name
            )

            if error_msg is None and png is not None:
                print(f"✅ [{file_prefix}] Code execution successful: {png}")
                self._save_text(os.path.join(run_dir, f"{file_prefix}_final.py"), current_code)
                return True, current_code, png
            
            else:
                print(f"❌ [{file_prefix}] Failed (Try {attempt}).")
                log_filename = f"{file_prefix}_error_log_try_{attempt}.txt"
                self._save_text(os.path.join(run_dir, log_filename), str(error_msg))

                if attempt < max_retries:
                    print(f"🛠️ [{file_prefix}] Requesting Coder to fix bug...")
                    current_code = self.coder.debug_code(current_code, str(error_msg))
                    self._save_text(os.path.join(run_dir, f"{file_prefix}_fix_{attempt+1}.py"), current_code)
                else:
                    print(f"💀 [{file_prefix}] Maximum retries reached, giving up.")
        
        return False, current_code, None


    def run(self, user_requirement, output_dir=None):
        """
        Execute complete workflow.
        Args:
            user_requirement: User requirement text
            output_dir: (optional) Specify output directory. If not provided, automatically create.
        Returns:
            (success: bool, message: str)
        """
        # ==============================================================================
        # Configuration & Directory Setup
        # ==============================================================================
        
        # Determine run directory
        if output_dir:
            run_dir = output_dir
            if not os.path.exists(run_dir):
                os.makedirs(run_dir)
        else:
            run_dir = Config.create_run_directory()

        # Basic environment setup
        src_tools = os.path.join(os.path.dirname(__file__), "tools.py")
        dst_tools = os.path.join(run_dir, "tools.py")
        if os.path.exists(src_tools):
            shutil.copy(src_tools, dst_tools)
        with open(os.path.join(run_dir, "requirement.txt"), "w", encoding="utf-8") as f:
            f.write(user_requirement)

        print(f"🚀 Task started: {user_requirement}")
        
        # Step 0: Visual Deep Research (Optional)
        style_guide = None
        if self.researcher and Config.ENABLE_DEEP_RESEARCH:
            print("\n=== Step 0: Visual Deep Research ===")
            try:
                # Search for reference images
                ref_images = self.researcher.search_references(query=user_requirement)
                
                if ref_images:
                    # Extract design style from references
                    style_guide = self.researcher.extract_design_style(ref_images)
                    
                    # Save style guide for reference
                    style_guide_path = os.path.join(run_dir, "style_guide.json")
                    with open(style_guide_path, 'w', encoding='utf-8') as f:
                        json.dump(style_guide, f, indent=2, ensure_ascii=False)
                    print(f"✅ Style guide extracted and saved: {style_guide_path}")
                else:
                    print("⚠️ No reference images found, using default style")
                    style_guide = None
            except Exception as e:
                print(f"⚠️ Visual Deep Research failed: {e}")
                print("   Continuing with default style...")
                style_guide = None
        
        # Step 1: Gemini Visual Concept
        print("\n=== Step 1: Gemini Visual Concept ===")
        ref_img_name = "00_reference_gemini.png"
        # Enhance prompt with style guide if available
        style_constraint = ""
        if style_guide:
            layout_info = style_guide.get("layout_engine", {})
            flow_dir = layout_info.get("flow_direction", "")
            topology = layout_info.get("topology", "")
            if flow_dir or topology:
                style_constraint = f" Follow the design style: {topology} with {flow_dir} flow. "
        
        ref_image_prompt = (
            f"A rigorous, publication-quality scientific diagram illustrating: {user_requirement}. "
            f"{style_constraint}"
            "Style guide: Emulate the aesthetic standard of high-impact journals like Nature or Science. "
            "Constraint: No main title, no placeholders. Pure white background."
        )
        ref_image_path = self.coder.generate_image_gemini(ref_image_prompt, run_dir, ref_img_name)
        if not ref_image_path: 
            return False, "Step 1 reference image generation failed"

        # Step 1.5: Icon Asset Preparation
        print("\n=== Step 1.5: Icon Asset Preparation ===")
        asset_map = {}
        complex_icons = self.coder.plan_complex_icons(ref_image_path)
        if complex_icons:
            icon_descriptions = self.coder.batch_extract_descriptions(ref_image_path, complex_icons)
            print(f"\nicon_descriptions: {icon_descriptions}\n")
            if icon_descriptions:
                sheet_path = self.icon_factory.generate_grid_sheet(icon_descriptions, run_dir)
                if sheet_path:
                    asset_map = self.icon_factory.slice_and_process(sheet_path, complex_icons, run_dir)
                    print(f"✅ Icon asset processing complete, total {len(asset_map)} icons.")

        # Step 2 & 3: Initial Code Construction and Debugging
        print("\n=== Step 2 & 3: Initial Code Construction and Debugging ===")
        init_generator = lambda: self.coder.image_to_code(
            ref_image_path, 
            user_requirement, 
            asset_map=asset_map,
            style_guide=style_guide
        )
        success, final_code, final_png = self._generate_and_debug_loop(
            generator_func=init_generator, run_dir=run_dir, file_prefix="01_code_iter_0", max_retries=3
        )
        if not success: 
            return False, "Step 2/3 initial code generation failed"
        
        current_code = final_code
        current_png = final_png

        # ==============================================================================
        # === Step 4: Actor-Critic Iterative Optimization (Round 1...N) ===
        # ==============================================================================
        print("\n=== Step 4: Actor-Critic Iterative Optimization ===")
        
        # At this point current_code and current_png must be ready
        init_code_for_iter = current_code 
        
        for i in range(Config.MAX_ITERATIONS):
            iter_num = i + 1
            print(f"\n🎬 Round {iter_num}: [Critic] Reviewing differences...")
            
            # Critic phase
            critique_text = self.coder.generate_critique(ref_image_path, current_png)
            
            critique_filename = f"{iter_num:02d}_critique_iter_{iter_num}.txt"
            self._save_text(os.path.join(run_dir, critique_filename), critique_text)
            print(f"📝 Critic suggestions saved. Summary: {critique_text[:100]}...\n")

            # Actor phase
            print(f"🎨 Round {iter_num}: [Actor] Modifying and self-correcting...")
            
            actor_generator = lambda: self.coder.refine_code_with_critique(
                ref_image_path, 
                current_png, 
                init_code_for_iter, 
                critique_text
            )
            
            # File prefix like: 02_code_iter_1
            prefix = f"{iter_num+1:02d}_code_iter_{iter_num}"
            
            success, refined_code, refined_png = self._generate_and_debug_loop(
                generator_func=actor_generator,
                run_dir=run_dir,
                file_prefix=prefix,
                max_retries=3
            )
            
            if success:
                print(f"✅ Round {iter_num} optimization successful.")
                current_png = refined_png
                init_code_for_iter = refined_code
            else:
                print(f"⚠️ Round {iter_num} optimization failed (code cannot run), keeping previous round result.")
                continue

        print(f"\n🎉 Task completed. All files saved to: {run_dir}")
        return True, "Success"
