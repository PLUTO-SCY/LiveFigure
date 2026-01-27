import os
import json
import base64
import requests
import math
import cv2
import numpy as np
from datetime import datetime
from config import Config

class BatchIconFactory:
    def __init__(self, api_key=None):
        self.api_key = api_key or Config.GEMINI_API_KEY
        # Reuse configuration from Config
        self.gen_img_url = Config.GEMINI_GEN_IMG_URL
        
    def _encode_image(self, image_path):
        with open(image_path, "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')

    def _make_transparent(self, cv2_img, threshold=240):
        gray = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
        mask_inv = cv2.bitwise_not(mask)
        b, g, r = cv2.split(cv2_img)
        rgba = cv2.merge([b, g, r, mask_inv])
        return rgba

    def _trim_whitespace(self, cv2_bgra_img):
        alpha = cv2_bgra_img[:, :, 3]
        points = cv2.findNonZero(alpha)
        if points is None: return cv2_bgra_img
        x, y, w, h = cv2.boundingRect(points)
        pad = 5
        img_h, img_w = cv2_bgra_img.shape[:2]
        x1, y1 = max(0, x - pad), max(0, y - pad)
        x2, y2 = min(img_w, x + w + pad), min(img_h, y + h + pad)
        return cv2_bgra_img[y1:y2, x1:x2]

    def _get_optimal_layout_and_ar(self, count):
        cols = math.ceil(math.sqrt(count))
        rows = math.ceil(count / cols)
        if count == 8: rows, cols = 2, 4
        if count == 12: rows, cols = 3, 4
        
        target_ratio = cols / rows
        supported_ratios = {"1:1": 1.0, "4:3": 1.333, "3:4": 0.75, "16:9": 1.778, "9:16": 0.562}
        best_ar = min(supported_ratios.keys(), key=lambda k: abs(target_ratio - supported_ratios[k]))
        return rows, cols, best_ar

    def generate_grid_sheet(self, descriptions_dict, output_dir):
        """
        Generate sprite sheet containing multiple icons (4K).
        [Fixed] Fully preserved Prompt details about segmentation, icon combination and negative constraints.
        """
        count = len(descriptions_dict)
        if count == 0: return None
        
        # 1. Calculate layout
        rows, cols, aspect_ratio = self._get_optimal_layout_and_ar(count)
        
        total_slots = rows * cols
        empty_slots = total_slots - count
        
        print(f"🎨 [Icon Factory] Requesting {rows}x{cols} Grid (4K, {aspect_ratio})...")

        # 2. Build icon description list
        grid_desc_str = ""
        for i, (name, desc) in enumerate(descriptions_dict.items()):
            grid_desc_str += f"Slot {i+1} (Target: {name}): {desc}\n"

        # 3. Build complete Prompt (fully restore original logic)
        prompt = f"""
        Generate a high-resolution Sprite Sheet Image containing exactly {count} distinct icons.
        
        Layout Configuration:
        - CANVAS: Aspect Ratio {aspect_ratio}.
        - GRID: {rows} Rows x {cols} Columns.
        - TOTAL SLOTS: {total_slots}.
        - FILLED: Slots 1 to {count} (Row by row, Left to Right).
        - EMPTY: Leave the last {empty_slots} slots strictly EMPTY/WHITE.
        
        Background: Pure White (#FFFFFF).
        Spacing: Wide white gaps between every icon.
        
        ----------
        🛡️ SEGMENTATION REQUIREMENTS (CRITICAL):
        1. **CLEAR BOUNDARIES**: Every icon MUST have a distinct, continuous edge or outline (e.g., a thin dark grey or black stroke). 
        2. **NO FADING**: Do not let icon colors fade or gradient into the white background. The edge must be sharp.
        3. **COMPOUND ICONS**: If a single icon is described as having multiple parts (e.g., "a palette AND a printer"), these parts MUST be visually touching, overlapping, or connected by a base. Do NOT leave a complete white gap that separates the parts of a single icon.
        ----------

        🚫 NEGATIVE CONSTRAINTS:
        1. NO TEXT, LABELS, or NUMBERS.
        2. NO BOXES or FRAMES around the grid cells.
        3. NO SHADOWS that extend far from the icon.

        Items to draw:
        {grid_desc_str}
        
        Style: Flat vector icon, clean lines, professional scientific style, consistent palette.
        """

        # 4. Construct request Payload
        payload = json.dumps({
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "imageSize": "4K",
                    "aspectRatio": aspect_ratio
                }
            }
        })
        
        headers = {
            'Authorization': f'Bearer {self.api_key}', 
            'Content-Type': 'application/json'
        }

        try:
            # 5. Call API
            response = requests.post(self.gen_img_url, headers=headers, data=payload)
            response.raise_for_status()
            response_json = response.json()
            
            # 6. Parse results
            if "candidates" in response_json and len(response_json["candidates"]) > 0:
                candidate = response_json["candidates"][0]
                if "content" in candidate:
                    parts = candidate["content"].get("parts", [])
                    for part in parts:
                        if "inlineData" in part:
                            # Decode and save
                            b64_data = part["inlineData"]["data"]
                            img_bytes = base64.b64decode(b64_data)
                            
                            # Save original sprite sheet for debugging
                            sheet_filename = "assets_grid_sheet_raw.png"
                            sheet_path = os.path.join(output_dir, sheet_filename)
                            
                            with open(sheet_path, "wb") as f:
                                f.write(img_bytes)
                                
                            print(f"✅ [Icon Factory] Original sheet saved: {sheet_path}")
                            return sheet_path
                        elif "text" in part:
                             print(f"❌ Model returned text instead of image: '{part['text']}'")
            return None

        except Exception as e:
            print(f"❌ Icon Gen API Error: {e}")
            return None
        

    def slice_and_process(self, sheet_path, requirements, output_dir):
        if not sheet_path or not os.path.exists(sheet_path): return {}
        
        img_bgr = cv2.imread(sheet_path)
        if img_bgr is None: return {}
        
        h, w = img_bgr.shape[:2]
        count = len(requirements)
        rows, cols, _ = self._get_optimal_layout_and_ar(count)
        cell_w, cell_h = w // cols, h // rows
        
        result_map = {}
        assets_dir = os.path.join(output_dir, "assets")
        if not os.path.exists(assets_dir): os.makedirs(assets_dir)

        for i in range(count):
            req_name = requirements[i]
            row, col = divmod(i, cols)
            x1, y1 = col * cell_w, row * cell_h
            x2, y2 = min(x1 + cell_w, w), min(y1 + cell_h, h)
            
            margin = 5
            cell_roi = img_bgr[y1+margin:y2-margin, x1+margin:x2-margin]
            if cell_roi.size == 0: continue
            
            final_icon = self._trim_whitespace(self._make_transparent(cell_roi))
            
            # Use simple filename for easy LLM reference
            safe_name = "".join([c if c.isalnum() else "_" for c in req_name])[:20]
            filename = f"icon_{i}_{safe_name}.png"
            save_path = os.path.join(assets_dir, filename)
            
            cv2.imwrite(save_path, final_icon)
            # Return absolute path for safety (PPT generation needs absolute paths)
            result_map[req_name] = save_path
            print(f"   ✨ Icon Ready: {req_name} -> {filename}")
            
        return result_map