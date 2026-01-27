import requests
import json
import base64
import os
from openai import OpenAI
from config import Config

class APIManager:
    def __init__(self):
        self.client = OpenAI(base_url=Config.API_BASE, api_key=Config.API_KEY)

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

    def chat_with_vlm(self, prompt, image_paths=None, model=Config.MODEL_VLM):
        messages = [{"role": "user", "content": []}]
        messages[0]["content"].append({"type": "text", "text": prompt})
        
        if image_paths:
            if isinstance(image_paths, str): image_paths = [image_paths]
            for img_path in image_paths:
                if os.path.exists(img_path):
                    try:
                        with open(img_path, "rb") as image_file:
                            b64_img = base64.b64encode(image_file.read()).decode('utf-8')
                        messages[0]["content"].append({
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
                        })
                    except Exception as e:
                        print(f"❌ Image read failed: {img_path}, error: {e}")
                else:
                    print(f"⚠️ Image path does not exist: {img_path}")

        try:
            print(f"🔄 Calling VLM ({model})...")
            response = self.client.chat.completions.create(
                model=model, 
                messages=messages, 
                temperature=0.7,
            )
            content = response.choices[0].message.content
            print(f"✅ VLM returned {len(content)} characters")
            return content
        except Exception as e:
            print(f"❌ LLM call failed!")
            print(f"❌ Error type: {type(e).__name__}")
            print(f"❌ Error details: {e}")
            return None
        
    def chat_with_llm(self, prompt, system_prompt=None, model=Config.MODEL_CODER, json_mode=False):
        """
        Text-only conversation interface for logic planning, code modification (no images) scenarios.
        """
        messages = []
        
        # Add System Prompt
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        else:
            # Default system prompt to prevent model from going off-track
            messages.append({"role": "system", "content": "You are a helpful assistant."})
            
        # Add User Prompt
        messages.append({"role": "user", "content": prompt})

        # Construct parameters
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
        }
        
        # JSON mode support (useful for structured output)
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            print(f"💬 [LLM] Calling {model}...")
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            return content
        except Exception as e:
            print(f"❌ LLM call failed: {e}")
            return ""
