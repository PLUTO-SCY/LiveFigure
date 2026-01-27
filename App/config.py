import os
from datetime import datetime

class Config:
    # ================= Base Path Configuration =================
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Global output root directory for all tasks
    GLOBAL_OUTPUT_ROOT = os.path.join(BASE_DIR, "output")
    
    # ================= External Tool Paths =================
    # LibreOffice AppImage path
    # NOTE: Update this path to your LibreOffice installation
    LIBREOFFICE_APP_PATH = os.getenv("LIBREOFFICE_APP_PATH", "/path/to/libreoffice/AppRun")
    
    # ================= API Configuration =================
    # NOTE: Replace with your API endpoint and key
    # For anonymous submission, set these via environment variables
    API_BASE = os.getenv("API_BASE", "YOUR_API_BASE_URL")
    API_KEY = os.getenv("API_KEY", "YOUR_API_KEY_HERE")
    
    GEMINI_GEN_IMG_URL = os.getenv("GEMINI_GEN_IMG_URL", "YOUR_GEMINI_API_URL")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", API_KEY)
    
    # ================= Model Names =================
    MODEL_CODER = "gemini-3-pro-preview-thinking"
    MODEL_VLM = "gpt-5"
    MODEL_PLANNER = "gemini-3-pro-preview-thinking"
    
    # ================= Runtime Parameters =================
    MAX_ITERATIONS = 2
    PPT_WIDTH_Cm = 33.867
    PPT_HEIGHT_Cm = 19.05

    @staticmethod
    def create_run_directory():
        """Create a timestamped independent run directory"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = os.path.join(Config.GLOBAL_OUTPUT_ROOT, f"task_{timestamp}")
        os.makedirs(run_dir, exist_ok=True)
        print(f"📂 Task output directory: {run_dir}")
        return run_dir
