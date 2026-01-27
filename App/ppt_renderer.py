import os
import re
import shutil
import subprocess
import fitz  # PyMuPDF
from config import Config

class PPTRenderer:
    
    def render_pipeline(self, code_str, output_dir, filename_base):
        """
        Returns: (pptx_path, pdf_path, png_path, error_msg)
        If successful, error_msg is None; if failed, error_msg is error string.
        """
        # 1. Generate and run code -> PPTX
        pptx_path, error_msg = self._execute_code(code_str, output_dir, filename_base)
        
        if error_msg:
            # Error occurred, return failure directly
            return None, None, None, error_msg
            
        if not pptx_path:
            return None, None, None, "Unknown Error: PPTX file not found."
            
        # 2. PPTX -> PDF
        pdf_path = self._convert_to_pdf(pptx_path)
        if not pdf_path:
            # This step failure is usually not a code issue, but an environment issue, but still return
            return pptx_path, None, None, "PDF Conversion Failed"
            
        # 3. PDF -> PNG
        png_path = self._convert_to_png(pdf_path)
        
        return pptx_path, pdf_path, png_path, None
    

    def _execute_code(self, code_str, output_dir, filename_base):
        """
        Save and run generated Python code.
        
        Args:
            code_str: LLM-generated Python code string
            output_dir: Task output directory
            filename_base: Expected filename base (no extension)
            
        Returns:
            tuple: (final_pptx_path, error_message)
                   - Success: (absolute path, None)
                   - Failure: (None, error string)
        """
        # 1. Code cleaning (remove Markdown markers)
        if code_str.startswith("```"):
            lines = code_str.split("\n")
            # Remove first line ```python or ```
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            # Remove last line ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            code_str = "\n".join(lines)
        

        # ==============================================================================
        # Syntax Auto-Correction
        # ==============================================================================
        # For: "import from pptx import ..." stuttering syntax
        # Explanation: ^import\s+from matches "import from" at line start (with space)
        # Replace with: "from"
        code_str = re.sub(r'^import\s+from\s+', 'from ', code_str, flags=re.MULTILINE)

        # For: possible "import import" stuttering
        code_str = re.sub(r'^import\s+import\s+', 'import ', code_str, flags=re.MULTILINE)
        # ==============================================================================
        
        code_str = code_str.strip()
        
        # 2. Prepare path variables
        # Convention: Prompt requires model to save as "temp_render.pptx"
        TEMP_FILENAME = "temp_render.pptx"
        
        script_name = f"{filename_base}_script.py"
        script_path = os.path.join(output_dir, script_name)
        
        # Final expected PPTX path
        final_pptx_name = f"{filename_base}.pptx"
        final_pptx_path = os.path.join(output_dir, final_pptx_name)

        # 3. Write Python script
        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code_str)
        except Exception as e:
            return None, f"Script Write Error: {str(e)}"

        # 4. Run script
        print(f"    Running script: {script_name} ...")
        try:
            # cwd=output_dir is crucial to ensure relative paths in code save correctly
            result = subprocess.run(
                ["python", script_name],
                cwd=output_dir,
                capture_output=True,
                text=True,
                timeout=60  # Timeout protection
            )
            
            # === Core logic: Check execution status ===
            if result.returncode != 0:
                # Extract error log: prioritize stderr, if not available use stdout
                error_log = result.stderr.strip()
                if not error_log:
                    error_log = result.stdout.strip()
                
                # If still empty, give generic message
                if not error_log:
                    error_log = "Unknown runtime error (exit code non-zero but no log)."
                
                print(f"❌ Code execution error:\n{error_log}")
                return None, error_log

            # 5. === Find output and rename (File Recovery Strategy) ===
            temp_path = os.path.join(output_dir, TEMP_FILENAME)
            
            # [Case A]: Found temp_render.pptx (model followed instructions)
            if os.path.exists(temp_path):
                # If target file exists (possibly from previous round), delete first
                if os.path.exists(final_pptx_path):
                    os.remove(final_pptx_path)
                
                os.rename(temp_path, final_pptx_path)
                print(f"✅ PPT generation successful (renamed): {final_pptx_path}")
                return final_pptx_path, None
            
            # [Case B]: Didn't find temp, but found final file directly (model may have hardcoded name)
            elif os.path.exists(final_pptx_path):
                print(f"✅ PPT generation successful (direct hit): {final_pptx_path}")
                return final_pptx_path, None
                
            # [Case C]: Neither found, try "blind recovery"
            # Check if directory has other oddly named pptx files
            else:
                files = os.listdir(output_dir)
                # Exclude other iteration results, only look for possibly generated this time
                # Logic is simple: find all .pptx files
                # Strictly speaking should sort by creation time, simplified here
                pptx_files = [f for f in files if f.endswith(".pptx")]
                
                print(f"⚠️ Expected file '{TEMP_FILENAME}' or '{final_pptx_name}' not found. Files in directory: {pptx_files}")
                
                # If directory has exactly one pptx (and not the one we haven't generated), assume it's it
                # Or if multiple, but one is just generated (simplified to uniqueness check here)
                # For safety, if cannot determine, report error
                if len(pptx_files) > 0:
                     # Can add more complex logic here, e.g., check file modification time
                     # Currently to prevent misoperation, if cannot find clear target, treat as failure
                     pass
                     
                return None, f"Execution successful but output file not found. Expected '{TEMP_FILENAME}'."
                
        except subprocess.TimeoutExpired:
            return None, "Execution Timeout (exceeded 60s)."
        except Exception as e:
            print(f"❌ Execution environment exception: {e}")
            return None, f"Environment Exception: {str(e)}"

    def _convert_to_pdf(self, pptx_path):
        """
        Convert PPTX to PDF using fixed logic, PDF output to same directory as PPTX.
        Returns PDF file path, raises exception if failed.
        """
        pptx_path = os.path.abspath(pptx_path)
        output_dir = os.path.dirname(pptx_path)
        pdf_file_name = os.path.splitext(os.path.basename(pptx_path))[0] + ".pdf"
        # NOTE: Update this path according to your LibreOffice installation
        pdf_temp_path = os.path.join(os.path.dirname(Config.LIBREOFFICE_APP_PATH), "usr", pdf_file_name)
        pdf_out_path = os.path.join(output_dir, pdf_file_name)

        # Call AppImage to convert to PDF
        subprocess.run([
            Config.LIBREOFFICE_APP_PATH,
            f"-env:UserInstallation=file:///tmp/lo_test/profile",
            "--headless",
            "--nologo",
            "--convert-to", "pdf",
            pptx_path
        ], check=True)

        # Move PDF to same directory as PPTX
        if os.path.exists(pdf_temp_path):
            shutil.move(pdf_temp_path, pdf_out_path)
            print(f"✅ PDF moved to: {pdf_out_path}")
            return pdf_out_path
        else:
            raise FileNotFoundError(f"PDF not generated: {pdf_temp_path}")

    def _convert_to_png(self, pdf_path):
        """
        Render first page of PDF to PNG, output fixed name final_check.png.
        Returns PNG file path, raises exception if failed.
        """
        pdf_path = os.path.abspath(pdf_path)
        output_dir = os.path.dirname(pdf_path)

        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        png_path = os.path.join(output_dir, f"{base_name}.png")
        try:
            doc = fitz.open(pdf_path)
            page = doc.load_page(0)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom
            pix.save(png_path)
            doc.close()
            print(f"✅ PNG generated: {png_path}")
            return png_path
        except Exception as e:
            raise RuntimeError(f"PDF to PNG conversion failed: {e}")
