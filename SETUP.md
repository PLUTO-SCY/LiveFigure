# Setup Instructions

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment Variables**
   
   Create a `.env` file or set environment variables:
   ```bash
   export API_BASE="your_api_base_url"
   export API_KEY="your_api_key"
   export GEMINI_API_KEY="your_gemini_api_key"
   export GEMINI_GEN_IMG_URL="your_gemini_image_generation_url"
   export LIBREOFFICE_APP_PATH="/path/to/libreoffice/AppRun"
   ```

3. **Update Configuration** (if needed)
   
   Edit `App/config.py` to adjust:
   - Model names
   - Canvas dimensions
   - Maximum iterations

4. **Run**
   ```bash
   cd App
   python main.py
   ```

## Notes

- Ensure LibreOffice is installed and accessible at the path specified in `LIBREOFFICE_APP_PATH`
- API keys should be set via environment variables for security
- Output directories are automatically created with timestamps
