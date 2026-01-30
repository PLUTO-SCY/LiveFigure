import os
import json
import shutil
import re
import datetime
from tqdm import tqdm

# Import modified WorkflowManager
from workflow_manager import WorkflowManager

# ================= Batch Configuration Area =================
# NOTE: Update these paths according to your setup
DATASET_PATH = os.getenv("DATASET_PATH", "path/to/your/dataset.jsonl")
OUTPUT_ROOT = os.getenv("OUTPUT_ROOT", "path/to/output/directory")
TEST_LIMIT = 50
# ==================================================

class BatchRunner:
    def __init__(self):
        print("🔧 [Init] Initializing batch runner...")
        # Only instantiate Manager once to avoid repeated model resource loading
        self.manager = WorkflowManager()
        
        if not os.path.exists(OUTPUT_ROOT):
            os.makedirs(OUTPUT_ROOT)

    def _clean_filename(self, text):
        """Clean filename"""
        if not text: return "Unknown"
        clean_text = re.sub(r'[\\/*?:"<>|]', '_', text)
        clean_text = clean_text.replace(" ", "_")
        clean_text = re.sub(r'_+', '_', clean_text)
        return clean_text.strip()[:100] # Slightly limit length to prevent path too long

    def _is_step_done(self, step_dir):
        """
        [Key Logic] Check if a specific step (V1 or V2) is completed.
        Criterion: Whether any .pptx file matching the generation pattern exists in the directory.
        Filename examples: 01_code_iter_0_try_2.pptx, 03_code_iter_2_try_0.pptx
        """
        if not os.path.exists(step_dir):
            return False
        
        # Traverse all files in directory
        for fname in os.listdir(step_dir):
            # If find any file containing "code_iter" and ending with ".pptx", consider it successful
            if fname.endswith(".pptx") and "code_iter" in fname:
                return True
        
        return False

    def run(self):
        print(f"📖 Loading dataset: {DATASET_PATH}")
        if not os.path.exists(DATASET_PATH):
            print(f"❌ Error: Dataset file not found.")
            return

        with open(DATASET_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        target_lines = lines[:TEST_LIMIT]
        print(f"🚀 开始批量任务 (Top {len(target_lines)})")
        print(f"📂 输出目录: {OUTPUT_ROOT}")

        success_count = 0
        fail_count = 0
        
        # tqdm 进度条
        pbar = tqdm(target_lines, desc="Running Batch")
        
        for line in pbar:
            try:
                item = json.loads(line)
            except:
                continue
            
            paper_name = item.get("paper_name", "Unknown")
            fig_label = item.get("figure_label", "Fig")
            
            safe_name = self._clean_filename(paper_name)
            safe_label = self._clean_filename(fig_label)
            case_id = f"{safe_name}_{safe_label}"
            
            case_dir = os.path.join(OUTPUT_ROOT, case_id)
            os.makedirs(case_dir, exist_ok=True)

            # 1. 复制 GT 图片 (如果有，且目标不存在时才复制)
            gt_src = item.get("image_abs_path")
            if gt_src and os.path.exists(gt_src):
                gt_dst = os.path.join(case_dir, "ground_truth.jpg")
                if not os.path.exists(gt_dst):
                    shutil.copy(gt_src, gt_dst)

            # 2. 准备 Prompt
            caption = item.get("caption", "")
            description = item.get("description", "")

            prompt_v1 = f"Create a scientific diagram. Caption: {caption}"
            prompt_v2 = f"Create a scientific diagram. Caption: {caption}\nContext: {description}"

            # ================= 3. 运行 V1 (独立检查) =================
            dir_v1 = os.path.join(case_dir, "V1_CaptionOnly")
            success_v1 = False
            msg_v1 = "Skipped (Already Done)"

            # 细粒度断点续传：先检查 V1 是否做完了
            if self._is_step_done(dir_v1):
                pbar.write(f"⏩ [{case_id}] V1 已完成，跳过...")
                success_v1 = True
            else:
                pbar.write(f"\n🌀 [{case_id}] Running V1...")
                try:
                    success_v1, msg_v1 = self.manager.run(
                        user_requirement=prompt_v1, 
                        output_dir=dir_v1
                    )
                except Exception as e:
                    success_v1, msg_v1 = False, str(e)

            # ================= 4. Run V2 (Independent Check) =================
            dir_v2 = os.path.join(case_dir, "V2_WithContext")
            success_v2 = False
            msg_v2 = "Skipped (Already Done)"

            # Fine-grained checkpoint resume: Independent check for V2
            if self._is_step_done(dir_v2):
                pbar.write(f"⏩ [{case_id}] V2 completed, skipping...")
                success_v2 = True
            else:
                pbar.write(f"\n🌀 [{case_id}] Running V2...")
                try:
                    success_v2, msg_v2 = self.manager.run(
                        user_requirement=prompt_v2, 
                        output_dir=dir_v2
                    )
                except Exception as e:
                    success_v2, msg_v2 = False, str(e)

            # ================= 5. 记录状态与统计 =================
            status = {
                "paper": paper_name,
                "figure": fig_label,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "v1_result": "Success" if success_v1 else f"Fail: {msg_v1}",
                "v2_result": "Success" if success_v2 else f"Fail: {msg_v2}"
            }
            
            # 将状态写入 JSON
            with open(os.path.join(case_dir, "batch_status.json"), "w") as f:
                json.dump(status, f, indent=2)

            # 统计逻辑：只有当 V1 和 V2 最终都处于成功状态（无论是本次跑的还是跳过的）才算 Success
            if success_v1 and success_v2:
                success_count += 1
            elif (not success_v1) and (not success_v2):
                # 两个都失败了才算彻底 Fail，混合状态暂不计入 Fail 以免混淆
                fail_count += 1
            
            # 更新进度条后缀
            pbar.set_postfix({"OK": success_count, "Fail": fail_count})

        print(f"\n✅ 批量测试结束!")
        print(f"双项全成 (V1 & V2 OK): {success_count}")
        print(f"双项全败 (V1 & V2 Fail): {fail_count}")

if __name__ == "__main__":
    runner = BatchRunner()
    runner.run()
