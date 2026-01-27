import os
import json
import base64
import pandas as pd
import re
import glob
from tqdm import tqdm
from openai import OpenAI

# ================= ⚙️ 配置区域 =================
# 你们自己方案的输出根目录
EVAL_ROOT = "/data5/shaochenyang/Workspace/AutoSciFigure2/Eval/Our_Batch_Generation/Batch_Run_01"

# 数据集路径
DATASET_PATH = "/data5/shaochenyang/AI_Scientist/AutoSciFigure/VisualDeepResearch/Construct/output/iclr_2024_figures_dataset.jsonl"

# 模型名称
model_name = "LiveFigure_Ours"

# 输出路径
OUTPUT_REPORT_PATH = f"/data5/shaochenyang/Workspace/AutoSciFigure2/Eval/Evaluation/evaluation_report_9metric_{model_name}.csv"
OUTPUT_SUMMARY_PATH = f"/data5/shaochenyang/Workspace/AutoSciFigure2/Eval/Evaluation/evaluation_summary_9metrics_{model_name}.md"

# 【开关】是否开启 V2 vs V1 的胜率评估
ENABLE_PAIRWISE = True

JUDGE_MODEL = "gpt-4o"

class Config:
    API_KEY = os.getenv("API_KEY", "YOUR_API_KEY_HERE")
    API_BASE = os.getenv("API_BASE", "YOUR_API_BASE_URL") 
# ==============================================

class AutoEvaluator:
    def __init__(self):
        print(f"🔧 [Init] 初始化评估裁判: {JUDGE_MODEL} | 目标模型: {model_name}")
        self.client = OpenAI(
            api_key=Config.API_KEY, 
            base_url=Config.API_BASE
        )
        self.results = []
        self.pairwise_results = {"V1_Wins": 0, "V2_Wins": 0, "Tie": 0, "Total": 0}
        
        self.prompt_lookup = self._load_dataset_prompts()

    def _clean_filename(self, text):
        if not text: return "Unknown"
        clean_text = re.sub(r'[\\/*?:"<>|]', '_', text)
        clean_text = clean_text.replace(" ", "_")
        clean_text = re.sub(r'_+', '_', clean_text)
        return clean_text.strip()[:100]

    def _load_dataset_prompts(self):
        print(f"📖 Loading prompts from dataset...")
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

    # =========================================================================
    # 核心逻辑：智能查找最新的 iter 图片
    # =========================================================================
    def _find_best_image(self, folder_path):
        if not os.path.exists(folder_path):
            return None
        
        # 获取所有 png 文件
        all_files = [f for f in os.listdir(folder_path) if f.endswith(".png")]
        
        # 优先级规则: iter_2 > iter_1 > iter_0
        for target_iter in ["iter_2", "iter_1", "iter_0"]:
            # 筛选出包含当前 iter 关键字的文件
            candidates = [f for f in all_files if target_iter in f]
            
            # 排除掉 reference 图片 (如 00_reference_gemini.png) 和 assets
            candidates = [f for f in candidates if "reference" not in f and "assets" not in f]
            
            if candidates:
                # 如果有多个 (例如 try_0, try_1)，按字母排序取最后一个 (通常代表最新尝试)
                candidates.sort()
                best_img = candidates[-1]
                return os.path.join(folder_path, best_img)
        
        return None

    # =========================================================================
    # Task 1: 9-Metric Scoring (完全一致的 Prompts)
    # =========================================================================
    def evaluate_comprehensive(self, gt_path, gen_path, prompt_text):
        if not os.path.exists(gen_path): return None
        
        base64_gen = self.encode_image(gen_path)
        base64_gt = None
        
        if os.path.exists(gt_path):
            base64_gt = self.encode_image(gt_path)
        else:
            gt_png = gt_path.replace(".jpg", ".png")
            if os.path.exists(gt_png):
                base64_gt = self.encode_image(gt_png)

        # ✅ 【完全一致】Prompt
        system_prompt = """
        You are a Senior Scientific Reviewer. Evaluate the "Generated Scientific Diagram" based on the Input Text and Ground Truth (if provided).
        
        Score the diagram (1-10) across 3 Dimensions and 9 Specific Metrics:

        **Dimension 1: Visual Design Excellence**
        1. Aesthetic Quality: Color harmony, layout modernity, visual appeal.
        2. Visual Expressiveness: Use of meaningful icons/metaphors vs simple boxes.
        3. Professional Polish: Alignment, spacing, vector-quality details.

        **Dimension 2: Communication Effectiveness**
        4. Clarity: Visual hierarchy, ease of understanding, lack of clutter.
        5. Logical Flow: Narrative direction (e.g. left-to-right), clear input-output path.
        6. Text Legibility: Text readability, no gibberish, correct spelling.

        **Dimension 3: Content Fidelity**
        7. Accuracy: Correct topology and relationships vs Ground Truth/Text.
        8. Completeness: No missing key modules/steps mentioned in text.
        9. Appropriateness: Style matches the target audience (scientific paper).

        Return JSON format ONLY:
        {
            "scores": {
                "aesthetic_quality": int,
                "visual_expressiveness": int,
                "professional_polish": int,
                "clarity": int,
                "logical_flow": int,
                "text_legibility": int,
                "accuracy": int,
                "completeness": int,
                "appropriateness": int
            },
            "reasoning": "string"
        }
        """

        # ✅ 【完全一致】User Content
        user_content = [
            {"type": "text", "text": f"Input Prompt Context:\n{prompt_text[:1000]}"},
            {"type": "text", "text": "Generated Diagram (Target):"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_gen}"}}
        ]
        
        if base64_gt:
            user_content.insert(1, {"type": "text", "text": "Ground Truth (Reference):"})
            user_content.insert(2, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_gt}"}})

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
            print(f"  ⚠️ Scoring Error: {e}")
            return None

    # =========================================================================
    # Task 2: Pairwise Win-Rate (完全一致的 Prompts)
    # =========================================================================
    def evaluate_pairwise(self, gt_path, v1_path, v2_path, prompt_text):
        if not os.path.exists(v1_path) or not os.path.exists(v2_path): return None
        
        b64_v1 = self.encode_image(v1_path)
        b64_v2 = self.encode_image(v2_path)
        
        b64_gt = None
        if os.path.exists(gt_path):
            b64_gt = self.encode_image(gt_path)
        else:
            gt_png = gt_path.replace(".jpg", ".png")
            if os.path.exists(gt_png):
                b64_gt = self.encode_image(gt_png)

        system_prompt = """
        You are an expert Art Director. Compare Image A (V1) and Image B (V2) against the Ground Truth.
        Which image is better for a scientific paper?
        Return JSON: {"winner": "A" or "B" or "Tie", "reason": "short explanation"}
        """
        
        user_content = [
            {"type": "text", "text": f"Context:\n{prompt_text[:500]}"},
            {"type": "text", "text": "Image A (Option 1):"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_v1}"}},
            {"type": "text", "text": "Image B (Option 2):"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_v2}"}}
        ]
        
        if b64_gt:
            user_content.insert(1, {"type": "text", "text": "Ground Truth (Reference):"})
            user_content.insert(2, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_gt}"}})

        try:
            response = self.client.chat.completions.create(
                model=JUDGE_MODEL,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_content}],
                response_format={"type": "json_object"}, temperature=0.1
            )
            result = json.loads(response.choices[0].message.content)
            return result.get("winner", "Tie")
        except: return "Tie"

    # =========================================================================
    # Main Execution
    # =========================================================================
    def run(self):
        if not os.path.exists(EVAL_ROOT):
            print(f"❌ 路径不存在: {EVAL_ROOT}")
            return

        cases = sorted([d for d in os.listdir(EVAL_ROOT) if os.path.isdir(os.path.join(EVAL_ROOT, d))])
        print(f"🚀 开始评估 Ours 方案 | 共 {len(cases)} 个 Case")

        for case_name in tqdm(cases, desc="Judging"):
            case_dir = os.path.join(EVAL_ROOT, case_name)
            
            # Ground Truth 通常在 Case 根目录下 (或者在 Dataset 结构里)
            # 你的目录结构里，GT 如果不在根目录，可能需要额外指定
            # 这里假设它和之前 Baseline 的逻辑一致，GT 在 case_dir 下
            # 或者我们可以复用 V1 下面的 `00_reference_gemini.png` 作为伪 GT？
            # 按照你之前的 Baseline 代码，GT 是 `case_dir/ground_truth.jpg`。
            # 你的新目录里似乎没有直接放 GT，如果需要严格评估，请确保 GT 文件存在。
            # 这里我保持原逻辑，尝试在 case_dir 下找 GT。
            gt_path = os.path.join(case_dir, "ground_truth.jpg")
            if not os.path.exists(gt_path): 
                gt_path = os.path.join(case_dir, "ground_truth.png")
            
            # 获取 Prompt
            case_data = self.prompt_lookup.get(case_name, {})
            raw_caption = case_data.get("caption", "")
            raw_desc = case_data.get("description", "")

            # 1. 独立打分
            # 这里的路径查找逻辑变了，使用了 _find_best_image
            v1_dir = os.path.join(case_dir, "V1_CaptionOnly")
            v2_dir = os.path.join(case_dir, "V2_WithContext")
            
            v1_img_path = self._find_best_image(v1_dir)
            v2_img_path = self._find_best_image(v2_dir)

            for ver, img_path, label in [(v1_dir, v1_img_path, "V1"), (v2_dir, v2_img_path, "V2")]:
                if not img_path: 
                    # print(f"⚠️ {case_name} {label} 没找到有效图片，跳过")
                    continue
                
                # 构造 Prompt (完全一致)
                prompt = raw_caption if label == "V1" else f"Caption: {raw_caption}\nContext: {raw_desc[:1000]}"

                res = self.evaluate_comprehensive(gt_path, img_path, prompt)
                
                if res and "scores" in res:
                    scores = res["scores"]
                    record = {
                        "CaseID": case_name, "Version": label,
                        **scores, 
                        "Reasoning": res.get("reasoning", "")[:100],
                        "UsedImage": os.path.basename(img_path) # 记录用了哪张图 (iter_2 还是 iter_1)
                    }
                    self.results.append(record)

            # 2. 胜率对比
            if ENABLE_PAIRWISE:
                if v1_img_path and v2_img_path:
                    winner = self.evaluate_pairwise(gt_path, v1_img_path, v2_img_path, raw_caption)
                    if winner:
                        self.pairwise_results["Total"] += 1
                        if winner == "A": self.pairwise_results["V1_Wins"] += 1
                        elif winner == "B": self.pairwise_results["V2_Wins"] += 1
                        else: self.pairwise_results["Tie"] += 1

        self.save_reports()

    def save_reports(self):
        if not self.results: return
        df = pd.DataFrame(self.results)
        df.to_csv(OUTPUT_REPORT_PATH, index=False)
        print(f"\n✅ 详细数据已保存: {OUTPUT_REPORT_PATH}")

        # 聚合平均分
        metrics = [
            "aesthetic_quality", "visual_expressiveness", "professional_polish",
            "clarity", "logical_flow", "text_legibility",
            "accuracy", "completeness", "appropriateness"
        ]
        
        valid_metrics = [m for m in metrics if m in df.columns]
        summary = df.groupby("Version")[valid_metrics].mean().round(2)

        print("\n" + "="*60)
        print(f"📊 Evaluation Summary: {model_name}")
        print("="*60)
        print(summary.to_string())

        # 生成 Markdown
        md_content = f"# Evaluation Report: {model_name}\n\n## 1. Metrics Score\n{summary.to_markdown()}"
        
        if ENABLE_PAIRWISE and self.pairwise_results["Total"] > 0:
            total = self.pairwise_results["Total"]
            v1_rate = (self.pairwise_results["V1_Wins"] / total) * 100
            v2_rate = (self.pairwise_results["V2_Wins"] / total) * 100
            tie_rate = (self.pairwise_results["Tie"] / total) * 100
            
            print("\n" + "="*60)
            print(f"🏆 Pairwise Win-Rate (V2 Context vs V1 Caption)")
            print(f"   - V1 Wins: {v1_rate:.1f}%")
            print(f"   - V2 Wins: {v2_rate:.1f}%")
            print(f"   - Tie:     {tie_rate:.1f}%")
            print("="*60)
            
            md_content += f"\n\n## 2. Pairwise Win-Rate\n- **V1 Wins**: {v1_rate:.1f}%\n- **V2 Wins**: {v2_rate:.1f}%\n- **Tie**: {tie_rate:.1f}%"

        with open(OUTPUT_SUMMARY_PATH, "w") as f:
            f.write(md_content)
        print(f"✅ Markdown 报告已生成: {OUTPUT_SUMMARY_PATH}")

if __name__ == "__main__":
    evaluator = AutoEvaluator()
    evaluator.run()

