# LiveFigure: Automated Scientific Figure Generation System

## Overview

LiveFigure is an automated system for generating publication-quality scientific diagrams from textual descriptions. The system employs a multi-stage pipeline that combines vision-language models (VLMs), code generation, and iterative refinement to produce high-quality scientific figures suitable for academic publications.

## Architecture

The system follows a modular architecture with the following key components:

### Core Components

1. **WorkflowManager** (`workflow_manager.py`)
   - Orchestrates the entire generation pipeline
   - Manages state across multiple stages
   - Handles both full pipeline and debug modes

2. **Coder** (`coder.py`)
   - Generates Python code from visual references using VLMs
   - Performs code debugging and refinement
   - Implements Actor-Critic pattern for iterative improvement

3. **APIManager** (`api_clients.py`)
   - Manages API interactions with LLMs and VLMs
   - Handles image generation requests
   - Provides unified interface for model communication

4. **PPTRenderer** (`ppt_renderer.py`)
   - Executes generated Python code
   - Converts PPTX to PDF and PNG formats
   - Handles error recovery and file management

5. **IconFactory** (`icon_factory.py`)
   - Generates complex icon assets in batch
   - Processes and slices sprite sheets
   - Manages icon asset library

6. **Tools** (`tools.py`)
   - High-level drawing utilities for python-pptx
   - Provides connectors, shapes, and text rendering functions
   - Handles advanced features like gradients and custom paths

## Workflow Pipeline

The system operates in four main stages:

### Step 1: Visual Concept Generation
- Uses Gemini API to generate a reference image based on the textual description
- Creates a high-quality visual blueprint for the target figure
- Ensures publication-quality aesthetic standards

### Step 1.5: Icon Asset Preparation (Optional)
- Analyzes the reference image to identify complex icons
- Generates icon descriptions using VLM
- Creates a sprite sheet containing all required icons
- Slices and processes individual icon assets

### Step 2 & 3: Initial Code Generation and Debugging
- Converts the reference image to executable Python code using VLM
- Implements automatic debugging loop with retry mechanism
- Handles syntax errors and runtime exceptions
- Produces initial working implementation

### Step 4: Actor-Critic Iterative Refinement
- **Critic Phase**: Analyzes differences between current output and reference
- Generates specific, actionable feedback on visual issues
- Focuses on boundaries, connectors, text integrity, and alignment
- **Actor Phase**: Applies surgical code modifications based on critique
- Preserves existing assets and structure
- Iterates for multiple rounds (configurable, default: 2)

## Key Design Principles

### 1. Modular Architecture
- Each component has a clear, single responsibility
- Easy to swap implementations or add new features
- Clean separation between API management, code generation, and rendering

### 2. Robust Error Handling
- Automatic code debugging with retry mechanisms
- File recovery strategies for edge cases
- Graceful degradation when components fail

### 3. Asset Management
- Pre-generation of complex icons for better quality
- Asset registry system for code generation
- Preservation of assets during refinement

### 4. Iterative Refinement
- Actor-Critic pattern for continuous improvement
- Surgical code modifications to preserve structure
- Focus on specific, actionable feedback

## Installation

### Prerequisites

- Python 3.8+
- LibreOffice (for PPTX to PDF conversion)
- Required Python packages (see `requirements.txt`)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd LiveFigure
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
export API_BASE="your_api_base_url"
export API_KEY="your_api_key"
export GEMINI_API_KEY="your_gemini_api_key"
export GEMINI_GEN_IMG_URL="your_gemini_image_generation_url"
export LIBREOFFICE_APP_PATH="/path/to/libreoffice/AppRun"
```

4. Update configuration in `App/config.py` if needed:
   - Model names
   - Canvas dimensions
   - Maximum iterations
   - Output directory paths

## Usage

### Basic Usage

```python
from App.workflow_manager import WorkflowManager

manager = WorkflowManager()
success, message = manager.run(
    user_requirement="Your figure description here",
    output_dir=None,  # Auto-create timestamped directory
    debug_from_step4=False  # Full pipeline
)
```

### Batch Processing

```python
from App.batch_runner import BatchRunner

runner = BatchRunner()
runner.run()
```

Configure batch processing in `App/batch_runner.py`:
- `DATASET_PATH`: Path to JSONL dataset file
- `OUTPUT_ROOT`: Root directory for batch outputs
- `TEST_LIMIT`: Number of cases to process

## Configuration

### Model Configuration

The system supports multiple models for different tasks:

- **MODEL_CODER**: Used for code generation and refinement
- **MODEL_VLM**: Vision-language model for image understanding
- **MODEL_PLANNER**: Used for icon planning and description extraction

### Runtime Parameters

- `MAX_ITERATIONS`: Number of Actor-Critic refinement rounds (default: 2)
- `PPT_WIDTH_Cm`: Canvas width in centimeters (default: 33.867)
- `PPT_HEIGHT_Cm`: Canvas height in centimeters (default: 19.05)

## File Structure

```
LiveFigure/
├── App/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config.py               # Configuration management
│   ├── workflow_manager.py     # Pipeline orchestration
│   ├── coder.py                # Code generation and refinement
│   ├── api_clients.py          # API management
│   ├── ppt_renderer.py         # Code execution and rendering
│   ├── icon_factory.py         # Icon asset generation
│   ├── tools.py                # Drawing utilities
│   ├── coder_prompts.py       # Prompt templates
│   ├── batch_runner.py         # Batch processing
│   ├── run_evaluation_ours.py # Evaluation scripts
│   └── run_evaluation_ours_edit.py
├── requirements.txt            # Python dependencies
└── README.md                  # This file
```

## Output Structure

Each task generates a timestamped directory containing:

```
task_YYYYMMDD_HHMMSS/
├── requirement.txt                    # Original user requirement
├── tools.py                          # Copy of drawing utilities
├── 00_reference_gemini.png           # Reference image (Step 1)
├── assets/                            # Icon assets (Step 1.5)
│   ├── assets_grid_sheet_raw.png
│   └── icon_*.png
├── 01_code_iter_0_*.py               # Initial code generation
├── 01_code_iter_0_*.pptx             # Generated presentations
├── 01_code_iter_0_*.png              # Rendered images
├── 02_critique_iter_1.txt            # Critic feedback
├── 02_code_iter_1_*.py               # Refined code
└── ...
```

## Evaluation

The system includes evaluation scripts for assessing generation quality:

- `run_evaluation_ours.py`: Comprehensive 9-metric evaluation
- `run_evaluation_ours_edit.py`: Semantic Edit Distance (SED) evaluation

## Technical Details

### Code Generation

The system uses VLMs to generate Python code that leverages the `python-pptx` library. The generated code:

- Uses high-level drawing tools from `tools.py`
- Handles complex layouts and connections
- Supports gradients, transparency, and custom paths
- Follows best practices to avoid common pitfalls

### Error Recovery

Multiple strategies ensure robust execution:

1. **Syntax Auto-Correction**: Fixes common syntax errors automatically
2. **File Recovery**: Handles cases where output files have unexpected names
3. **Debug Loop**: Automatic retry with error analysis
4. **Graceful Degradation**: Continues with partial results when possible

### Icon Generation

Complex icons are generated in batch:

1. Identify icons from reference image
2. Extract visual descriptions
3. Generate sprite sheet with all icons
4. Slice and process individual icons
5. Make icons available to code generator

## Limitations and Future Work

- Currently requires LibreOffice for PDF conversion
- Icon generation depends on external API availability
- Iteration count is fixed (could be adaptive)
- Limited support for multi-page figures

## Citation

If you use this code in your research, please cite:

```bibtex
@article{livefigure2024,
  title={LiveFigure: Automated Scientific Figure Generation},
  author={...},
  journal={...},
  year={2026}
}
```
