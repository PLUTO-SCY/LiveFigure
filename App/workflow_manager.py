import os
import json
import shutil
import sys
from config import Config
from api_clients import APIManager
from ppt_renderer import PPTRenderer
from coder import Coder
from icon_factory import BatchIconFactory

class WorkflowManager:
    def __init__(self):
        self.api = APIManager()
        self.coder = Coder(self.api)
        self.renderer = PPTRenderer()
        self.icon_factory = BatchIconFactory()

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


    def run(self, user_requirement, output_dir=None, debug_from_step4=False):
        """
        Execute complete workflow.
        Args:
            user_requirement: User requirement text
            output_dir: (optional) Specify output directory. If not provided, automatically create.
            debug_from_step4: (optional) Whether to enable Step 4 debug mode (Clone old data).
        Returns:
            (success: bool, message: str)
        """
        # ==============================================================================
        # Configuration & Directory Setup
        # ==============================================================================
        
        # 1. Determine run directory
        if output_dir:
            run_dir = output_dir
            if not os.path.exists(run_dir):
                os.makedirs(run_dir)
        else:
            run_dir = Config.create_run_directory()

        # 2. Define debug source directory
        # NOTE: For anonymous submission, this should be configured via environment variable
        TARGET_DIR = os.getenv("DEBUG_TARGET_DIR", "")
        
        # 3. File names required for state recovery
        START_PNG_NAME = "01_code_iter_0_try_0.png"   # Initial rendered image
        START_CODE_NAME = "01_code_iter_0_final.py"    # Initial runnable code
        # ==============================================================================

        current_code = ""
        current_png = None
        ref_image_path = None
        asset_map = {}

        # ==============================================================================
        # Branch A: DEBUG Mode (Only debug Step 4)
        # ==============================================================================
        if debug_from_step4:
            print(f"\n🔧 [DEBUG Mode] Enabled (Only debug Step 4).")
            print(f"📂 Cloning historical source directory: {TARGET_DIR}")

            if not TARGET_DIR or not os.path.exists(TARGET_DIR):
                print(f"❌ Source directory does not exist: {TARGET_DIR}")
                return False, f"Source directory does not exist: {TARGET_DIR}"
            
            # 1. Copy all files from source directory to new directory
            try:
                # dirs_exist_ok=True allows directory to already exist (adapts to batch runner created empty directories)
                shutil.copytree(TARGET_DIR, run_dir, dirs_exist_ok=True)
                print(f"✅ Historical files cloned completely")
            except Exception as e:
                print(f"❌ File cloning failed: {e}")
                return False, f"File cloning failed: {e}"

            # 2. Restore key state required for Step 4
            ref_image_path = os.path.join(run_dir, "00_reference_gemini.png")
            if not os.path.exists(ref_image_path):
                print(f"❌ Reference image missing: {ref_image_path}")
                return False, "Reference image missing"
            
            current_png = os.path.join(run_dir, START_PNG_NAME)
            if not os.path.exists(current_png):
                print(f"❌ Initial rendered image missing: {current_png}")
                return False, "Initial rendered image missing"
                
            code_path = os.path.join(run_dir, START_CODE_NAME)
            if os.path.exists(code_path):
                with open(code_path, "r", encoding="utf-8") as f:
                    current_code = f.read()
                print(f"✅ Initial code loaded: {START_CODE_NAME}")
            else:
                print(f"❌ Initial code file missing: {code_path}")
                return False, "Initial code file missing"

            # 3. Ensure tools.py exists
            dst_tools = os.path.join(run_dir, "tools.py")
            if not os.path.exists(dst_tools):
                src_tools = os.path.join(os.path.dirname(os.path.dirname(__file__)), "App", "tools.py")
                if os.path.exists(src_tools):
                    shutil.copy(src_tools, dst_tools)
                    print("✅ tools.py added")

        # ==============================================================================
        # Branch B: Normal Full Pipeline (Step 1 -> 1.5 -> 2 -> 3 -> 4)
        # ==============================================================================
        else:
            # Basic environment setup
            src_tools = os.path.join(os.path.dirname(__file__), "tools.py")
            dst_tools = os.path.join(run_dir, "tools.py")
            if os.path.exists(src_tools):
                shutil.copy(src_tools, dst_tools)
            with open(os.path.join(run_dir, "requirement.txt"), "w", encoding="utf-8") as f:
                f.write(user_requirement)

            print(f"🚀 Task started: {user_requirement}")
            
            # Step 1
            print("\n=== Step 1: Gemini Visual Concept ===")
            ref_img_name = "00_reference_gemini.png"
            ref_image_prompt = (
                f"A rigorous, publication-quality scientific diagram illustrating: {user_requirement}. "
                "Style guide: Emulate the aesthetic standard of high-impact journals like Nature or Science. "
                "Constraint: No main title, no placeholders. Pure white background."
            )
            ref_image_path = self.coder.generate_image_gemini(ref_image_prompt, run_dir, ref_img_name)
            if not ref_image_path: 
                return False, "Step 1 reference image generation failed"

            # Step 1.5
            print("\n=== Step 1.5: Icon Asset Preparation ===")
            complex_icons = self.coder.plan_complex_icons(ref_image_path)
            if complex_icons:
                icon_descriptions = self.coder.batch_extract_descriptions(ref_image_path, complex_icons)
                print(f"\nicon_descriptions: {icon_descriptions}\n")
                if icon_descriptions:
                    sheet_path = self.icon_factory.generate_grid_sheet(icon_descriptions, run_dir)
                    if sheet_path:
                        asset_map = self.icon_factory.slice_and_process(sheet_path, complex_icons, run_dir)
                        print(f"✅ Icon asset processing complete, total {len(asset_map)} icons.")

            # Step 2 & 3
            print("\n=== Step 2 & 3: Initial Code Construction and Debugging ===")
            init_generator = lambda: self.coder.image_to_code(ref_image_path, user_requirement, asset_map=asset_map)
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
