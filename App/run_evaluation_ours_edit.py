import os
import json
import base64
import pandas as pd
import re
import glob
from tqdm import tqdm
from openai import OpenAI

# ================= ⚙️ 配置区域 =================
# 1. 待评估的生成结果根目录
EVAL_ROOT = "/data5/shaochenyang/Workspace/AutoSciFigure2/Eval/Our_Batch_Generation/Batch_Run_01"

# 2. 数据集路径 (用于获取 Prompt 上下文，辅助 Log)
DATASET_PATH = "/data5/shaochenyang/AI_Scientist/AutoSciFigure/VisualDeepResearch/Construct/output/iclr_2024_figures_dataset.jsonl"

# 3. 输出文件名
MODEL_NAME = "LiveFigure_Ours"
OUTPUT_REPORT_PATH = f"/data5/shaochenyang/Workspace/AutoSciFigure2/Eval/Evaluation_Edit/evaluation_report_SED_{MODEL_NAME}.csv"
OUTPUT_SUMMARY_PATH = f"/data5/shaochenyang/Workspace/AutoSciFigure2/Eval/Evaluation_Edit/evaluation_summary_SED_{MODEL_NAME}.md"

# 4. LLM Configuration
JUDGE_MODEL = "gpt-5" # Recommend using the strongest model for SED judgment
API_KEY = os.getenv("API_KEY", "YOUR_API_KEY_HERE")
API_BASE = os.getenv("API_BASE", "YOUR_API_BASE_URL") 

# ==============================================

class SEDEvaluator:
    def __init__(self):
        print(f"🔧 [Init] 初始化 SED 评估裁判: {JUDGE_MODEL}")
        self.client = OpenAI(api_key=API_KEY, base_url=API_BASE)
        self.results = []
        self.prompt_lookup = self._load_dataset_prompts()

    def _clean_filename(self, text):
        if not text: return "Unknown"
        clean_text = re.sub(r'[\\/*?:"<>|]', '_', text)
        clean_text = clean_text.replace(" ", "_")
        clean_text = re.sub(r'_+', '_', clean_text)
        return clean_text.strip()[:100]

    def _load_dataset_prompts(self):
        print(f"📖 Loading dataset metadata...")
        lookup = {}
        try:
            with open(DATASET_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    item = json.loads(line)
                    p_name = self._clean_filename(item.get("paper_name", "Unknown"))
                    f_label = self._clean_filename(item.get("figure_label", "Fig"))
                    case_id = f"{p_name}_{f_label}"
                    lookup[case_id] = {
                        "caption": item.get("caption", ""),
                        "description": item.get("description", "")
                    }
        except Exception as e:
            print(f"⚠️ Failed to load dataset: {e}")
        return lookup

    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def _find_best_image(self, folder_path):
        """
        查找策略：iter_2 > iter_1 > iter_0
        """
        if not os.path.exists(folder_path):
            return None
        
        all_files = [f for f in os.listdir(folder_path) if f.endswith(".png")]
        
        for target_iter in ["iter_2", "iter_1", "iter_0"]:
            candidates = [f for f in all_files if target_iter in f]
            # 排除 assets 和 reference
            candidates = [f for f in candidates if "reference" not in f and "assets" not in f]
            
            if candidates:
                candidates.sort() # 字母序排序，取最后一个 (try_x 最大值)
                best_img = candidates[-1]
                return os.path.join(folder_path, best_img)
        return None

    # =========================================================================
    # 核心：计算 Semantic Edit Distance (SED)
    # =========================================================================
    def evaluate_sed(self, gt_path, gen_path):
        """
        输入：GT图片路径，生成图片路径
        输出：JSON (Steps, Plan, Analysis)
        """
        if not os.path.exists(gen_path): return None
        
        # 处理 GT 图片 (兼容 jpg/png)
        real_gt_path = gt_path
        if not os.path.exists(real_gt_path):
            real_gt_path = gt_path.replace(".jpg", ".png")
            if not os.path.exists(real_gt_path):
                # 如果找不到 GT，无法计算 SED
                return None

        b64_gen = self.encode_image(gen_path)
        b64_gt = self.encode_image(real_gt_path)

        # Prompt: 这里的定义非常关键，直接决定了 SED 的粒度
        system_prompt = """
        You are a Senior Scientific Editor and Layout Engineer.
        Your task is to evaluate a **Generated Scientific Figure** against a **Ground Truth (Reference)**.
        
        GOAL:
        Determine the **Semantic Edit Distance (SED)**, which is the sequence of Atomic Operations required to transform the Generated Figure into a publication-ready state that matches the information fidelity and visual standard of the Ground Truth.
        
        NOTE:
        - You do NOT need pixel-perfect matching.
        - Focus on Information Accuracy (Text, Topology) and Visual Clarity (Layout, Style).
        - If the generated figure is already perfect or semantically equivalent, return an empty list.

        DEFINITIONS OF ATOMIC OPERATIONS (1 Step each):
        1. [TEXT_EDIT]: Fix typo, change text content, or adjust font size/weight.
        2. [MOVE]: Move a SINGLE object/group to a correct position.
        3. [RESIZE]: Resize a SINGLE object.
        4. [STYLE]: Change color, border, or shape style of a SINGLE object.
        5. [ADD]: Add a missing object or arrow.
        6. [DELETE]: Remove a hallucinated or unnecessary object.
        7. [CONNECT]: Fix or reroute a connection arrow.

        STRICT RULES:
        - Be granular. Do not say "Fix layout" (which is vague). Say "Move Box A", "Move Box B", "Resize Box C".
        - Count steps conservatively but accurately.
        
        OUTPUT FORMAT (JSON ONLY):
        {
            "analysis": "Brief analysis of the main differences...",
            "edit_plan": [
                {"step": 1, "type": "TEXT_EDIT", "description": "Change 'Hellow' to 'Hello' in the blue box"},
                {"step": 2, "type": "MOVE", "description": "Move the 'Encoder' block to the left"},
                ...
            ],
            "total_steps": <int count of list>,
            "is_publication_ready": <bool>
        }
        """

        user_content = [
            {"type": "text", "text": "Reference Ground Truth (Target Standard):"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_gt}"}},
            {"type": "text", "text": "Generated Figure (To be fixed):"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_gen}"}},
            {"type": "text", "text": "Please list the atomic edit operations required."}
        ]

        try:
            response = self.client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                response_format={"type": "json_object"},
                temperature=0.2 
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            print(f"  ⚠️ API Error during SED calculation: {e}")
            return None

    # =========================================================================
    # 主循环
    # =========================================================================
    def run(self):
        if not os.path.exists(EVAL_ROOT):
            print(f"❌ 路径不存在: {EVAL_ROOT}")
            return

        cases = sorted([d for d in os.listdir(EVAL_ROOT) if os.path.isdir(os.path.join(EVAL_ROOT, d))])
        print(f"🚀 开始 SED 评估 | 共 {len(cases)} 个 Case | 模型: {JUDGE_MODEL}")

        for case_name in tqdm(cases, desc="Evaluating SED"):
            case_dir = os.path.join(EVAL_ROOT, case_name)
            
            # 查找 GT
            gt_path = os.path.join(case_dir, "ground_truth.jpg")
            
            # 定义 V1 和 V2 目录
            v1_dir = os.path.join(case_dir, "V1_CaptionOnly")
            v2_dir = os.path.join(case_dir, "V2_WithContext")
            
            # 找到最佳生成图
            v1_img = self._find_best_image(v1_dir)
            v2_img = self._find_best_image(v2_dir)

            for ver_label, img_path in [("V1", v1_img), ("V2", v2_img)]:
                if not img_path: continue
                
                # 计算 SED
                res = self.evaluate_sed(gt_path, img_path)
                
                if res:
                    # 将 edit_plan 转换为字符串以便存入 CSV
                    plan_str = json.dumps(res.get("edit_plan", []), ensure_ascii=False)
                    
                    record = {
                        "CaseID": case_name,
                        "Version": ver_label,
                        "SED_Score": res.get("total_steps", 999), # 999 表示异常
                        "Is_Publication_Ready": res.get("is_publication_ready", False),
                        "Analysis": res.get("analysis", ""),
                        "Edit_Plan": plan_str[:3000], # 防止 CSV 爆掉，截断一下
                        "Used_Image": os.path.basename(img_path)
                    }
                    self.results.append(record)
                    
                    # 实时打印比较好的结果（可选）
                    # if res.get("total_steps", 999) == 0:
                    #    tqdm.write(f"🎉 Perfect Match found: {case_name} ({ver_label})")

        self.save_reports()

    def save_reports(self):
        if not self.results: 
            print("⚠️ 没有产生结果")
            return
            
        df = pd.DataFrame(self.results)
        df.to_csv(OUTPUT_REPORT_PATH, index=False)
        print(f"\n✅ 详细日志已保存: {OUTPUT_REPORT_PATH}")

        # 统计分析
        # 计算 V1 和 V2 的平均编辑距离
        summary_sed = df.groupby("Version")["SED_Score"].mean().round(2)
        summary_ready = df.groupby("Version")["Is_Publication_Ready"].sum()
        total_count = df.groupby("Version")["CaseID"].count()
        ready_rate = (summary_ready / total_count * 100).round(1)

        print("\n" + "="*60)
        print(f"📊 SED Evaluation Summary: {MODEL_NAME}")
        print("="*60)
        print(f"Average SED (Lower is Better):")
        print(summary_sed.to_string())
        print("-" * 60)
        print(f"Publication Ready Rate (Higher is Better):")
        print(ready_rate.to_string())
        print("="*60)

        # 生成 Markdown 报告
        md_content = f"# Semantic Edit Distance (SED) Report\n"
        md_content += f"**Judge Model**: {JUDGE_MODEL}\n\n"
        
        md_content += "## 1. Average SED (Lower is better)\n"
        md_content += summary_sed.to_markdown() + "\n\n"
        
        md_content += "## 2. Publication Ready Rate\n"
        md_content += ready_rate.to_markdown() + "\n\n"
        
        md_content += "## 3. Metric Definition\n"
        md_content += "- **SED**: The number of atomic operations (Text Edit, Move, Resize, Style, Add, Del, Connect) required to fix the image.\n"
        md_content += "- **Atomic Step**: Defined as a single, granular modification action."

        with open(OUTPUT_SUMMARY_PATH, "w") as f:
            f.write(md_content)
        print(f"✅ Markdown 总结已生成: {OUTPUT_SUMMARY_PATH}")

if __name__ == "__main__":
    evaluator = SEDEvaluator()
    evaluator.run()