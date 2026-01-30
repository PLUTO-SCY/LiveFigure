# LiveFigure: Automated Scientific Figure Generation System

## Overview

LiveFigure is an agentic framework that simulates the cognitive workflow of expert human designers to generate publication-quality scientific diagrams from textual descriptions. The system decomposes the figure generation task into three specialized stages that work together to produce editable PowerPoint figures with both semantic alignment and visual clarity.

## Architecture

The system follows a modular architecture organized around the three-stage pipeline. Each stage employs specialized components that work together to transform textual input into editable PowerPoint figures.

### Stage I Components: Visual Planning

- **VisualDeepResearcher** (`visual_researcher.py`)
  - Performs semantic search in vector database for reference images
  - Extracts design styles from retrieved images using VLM
  - Synthesizes multiple style analyses into unified style guide
  - Optional component that enhances generation quality when enabled

- **IconFactory** (`icon_factory.py`)
  - Generates complex icon assets in batch using grid-based strategy
  - Processes and slices sprite sheets
  - Manages icon asset library with style consistency

- **APIManager** (`api_clients.py`)
  - Handles image generation requests for blueprint creation
  - Provides unified interface for VLM communication

### Stage II Components: Procedural Generation

- **Tools** (`tools.py`)
  - Standardized skills library with high-level drawing utilities
  - Provides connectors, shapes, and text rendering functions
  - Handles advanced features like gradients and custom paths
  - Pre-validated atomic primitives that guarantee executability

- **Coder** (`coder.py`)
  - Generates Python code from visual references using VLMs
  - Incorporates experience-driven constraints from best practices
  - Implements self-correcting execution loop with error recovery

- **CoderPrompts** (`coder_prompts.py`)
  - Contains PPTX best practices and negative constraints
  - Evolving experience repository that prevents known error patterns

- **PPTRenderer** (`ppt_renderer.py`)
  - Executes generated Python code
  - Converts PPTX to PDF and PNG formats
  - Handles error recovery and file management

### Stage III Components: Visual Refinement

- **Coder** (`coder.py`)
  - Implements Actor-Critic pattern for iterative improvement
  - Generates visual critiques and applies surgical code modifications
  - Performs targeted refinement based on visual diagnostics

### Pipeline Orchestration

- **WorkflowManager** (`workflow_manager.py`)
  - Orchestrates the entire three-stage generation pipeline
  - Manages state and data flow across stages
  - Coordinates component interactions

## Workflow Pipeline

The following diagram illustrates the complete workflow of the LiveFigure system:

![Workflow Diagram](assets/workflow.png)

Formally, let $\mathcal{T}_{in}$ denote the input methodological text. Our objective is to synthesize an editable PowerPoint figure $\mathcal{F}_{final}$ that maximizes both semantic alignment and visual clarity. The generation pipeline is formulated as a sequential composition of three specialized mapping functions:

$$\mathcal{F}_{final} = \Psi_{refine} \circ \Psi_{assemble} \circ \Psi_{plan} (\mathcal{T}_{in})$$

The system operates in three main stages:

### Stage I: Visual Planning via Prior Induction ($\Psi_{plan}$)

This stage aims to uncover high-quality design patterns from top-tier conferences, establishing reliable priors for visual layout in figure-generation tasks. The mapping function $\Psi_{plan}: \mathcal{T}_{in} \to \mathcal{B}$ transforms the input text into a visual blueprint $\mathcal{B}$.

#### Visual Prior Induction

To facilitate effective visual prior induction, the system leverages a **figure-text knowledge base** $\mathbb{K} = \{(v_i, c_i, d_i)\}_{i=1}^N$ focused on scientific figures, where $v_i$ is the figure, $c_i$ is the caption, and $d_i$ represents the dense technical description.

**Reference Retrieval**: The retrieve agent first fetches the top-$k$ most semantically relevant reference figures from $\mathbb{K}$:
$$\mathcal{R} = \operatorname*{TopK}_{k \in \mathbb{K}} \text{sim}(E(\mathcal{T}_{in}), E(k))$$

where $E(\cdot)$ denotes the embedding function (e.g., Qwen3-Embedding).

**Structural Plan Generation**: A VLM jointly analyzes the retrieved references $\mathcal{R}$ and the user input $\mathcal{T}_{in}$, examining the layout organization and visual composition. By abstracting and distilling their underlying design principles, the model produces a tailored structural plan:
$$\mathcal{S}_{plan} = \text{VLM}_{reason}(\mathcal{T}_{in}, \mathcal{R})$$

**Blueprint Generation**: The blueprint agent takes both the original context and the structural plan as prompts to generate the visual blueprint:
$$\mathcal{B} = \text{Gen}_{img}(\mathcal{T}_{in}, \mathcal{S}_{plan})$$

This blueprint provides spatial guidance for downstream procedural generation.

#### Asset Generation for Complex Entities

For domain-specific entities $\mathcal{E}_{entity}$ (e.g., "microscope," "robotic arm") whose visual complexity exceeds basic geometric primitives, an asset generation module synthesizes style-consistent assets using a **grid-based batch generation strategy**. Instead of synthesizing assets individually, the system generates a composite image containing an $M \times N$ grid of icons in a single pass, strictly conditioned on the visual style of $\mathcal{S}_{plan}$:

$$\mathbb{A} = \Phi_{post}\left( \text{Gen}_{grid}(\mathcal{E}_{entity} \mid \mathcal{S}_{plan}) \right)$$

where $\Phi_{post}$ performs grid cropping and background removal. This mechanism ensures that complex scientific entities are visually consistent and ready for seamless integration.

**Key Components:**
- **VisualDeepResearcher** (`visual_researcher.py`): Performs semantic search and style extraction
- **IconFactory** (`icon_factory.py`): Generates complex icon assets in batch using grid-based strategy

### Stage II: Procedural Figure Generation via Skills and Experience ($\Psi_{assemble}$)

After establishing the visual blueprint $\mathcal{B}$ and the asset library $\mathbb{A}$, this stage procedurally generates an editable figure. We formalize this process as a mapping $\Psi_{assemble}: (\mathcal{B}, \mathbb{A}) \to \mathcal{F}_{init}$, where $\mathcal{F}_{init}$ represents the initial editable PowerPoint figure.

#### Why PowerPoint?

We choose **Microsoft PowerPoint** as the carrier for editable figures based on careful consideration of user accessibility and automation feasibility. PowerPoint offers a rare combination of broad user accessibility and developer-level openness, with rich programmatic interfaces (via OpenXML) that enable fine-grained manipulation of graphical primitives while supporting seamless export to standard vector formats.

#### Standardized Skills as Atomic Primitives

We construct a Python library of **Standardized Skills**, denoted as $\mathbb{S} = \{s_1, s_2, \dots, s_M\}$. Each skill $s_j$ is pre-debugged and rigorously validated, encapsulating complex rendering logic (such as connector routing and nested text-shape composition) into high-level semantic interfaces.

The procedural generation process $\mathcal{M}_{gen}$ synthesizes an executable Python script $\mathcal{C}_{init}$ conditioned on the visual blueprint $\mathcal{B}$ and the skill library $\mathbb{S}$:

$$\mathcal{F}_{init} = \text{Exec}(\mathcal{C}_{init}), \quad \mathcal{C}_{init} \sim \mathcal{M}_{gen}(\cdot \mid \mathcal{B}, \mathbb{S})$$

This abstraction serves two critical purposes:
1. **Guarantees Executability**: By constraining the model's action space to a curated set of verified atomic functions, we substantially reduce syntax errors and API hallucinations.
2. **Enables Cognitive Offloading**: The abstraction decouples high-level layout reasoning from low-level implementation details, allowing the model to focus on semantic layout decisions without explicitly computing anchor points or pixel-level routing coordinates.

#### Experience-Driven Constraint Injection

To systematically mitigate API hallucinations and invalid parameter combinations, we introduce an **Evolving Experience Injection** mechanism, which distills debugging experiences accumulated during development into formalized negative constraints $\mathbb{E}_{neg}$. As the system processes an increasing number of generation cases, the experience repository is continuously updated by capturing newly observed runtime errors. Prohibitive rules are automatically incorporated into the prompt (e.g., "NEVER use `slide.shapes.add_shape(MSO_SHAPE.LINE, ...)` directly; use `add_connector` instead"), performing pre-pruning over the generation search space.

#### Self-Correcting Execution Loop

While standardized skills and experience constraints significantly reduce error rates, we incorporate a runtime feedback-based iterative debugging mechanism to handle sporadic complex logic conflicts. Upon execution failure, the system captures the error stack trace $\epsilon$ and feeds it back to the model. We define the debugging iteration sequence $\{\mathcal{C}_{debug}^{(t)}\}$ initialized with $\mathcal{C}_{debug}^{(0)} = \mathcal{C}_{draft}$:

$$\mathcal{C}_{debug}^{(t+1)} = \text{Refine}(\mathcal{C}_{debug}^{(t)}, \epsilon^{(t)}), \quad \text{s.t. } t < T_{max}$$

This loop terminates upon successful execution, yielding the validated executable script $\mathcal{C}_{exec}$.

**Key Components:**
- **Tools** (`tools.py`): Standardized skill library with high-level drawing utilities
- **Coder** (`coder.py`): Code generation with experience-driven constraints
- **CoderPrompts** (`coder_prompts.py`): Contains PPTX best practices and negative constraints
- **PPTRenderer** (`ppt_renderer.py`): Executes generated code and handles error recovery

### Stage III: Targeted Refinement via Visual Diagnostics ($\Psi_{refine}$)

Although the script $\mathcal{C}_{exec}$ obtained from Stage II is valid and executable, the resulting figure $\mathcal{F}_{init}$ often exhibits subtle visual defects invisible to code-level logic, such as element occlusion or inconsistent styling. To bridge the gap between code logic and visual perception, we design a **Visual Diagnosis-Driven Refinement** closed-loop, formally modeled as an optimization mapping $\Psi_{refine}: \mathcal{F}_{init} \to \mathcal{F}_{final}$.

#### Observe-Diagnose-Refine Process

We formulate this phase as an iterative "observe-diagnose-refine" process. Let $\mathcal{C}^{(0)} = \mathcal{C}_{exec}$ denote the starting script inherited from Stage II. At each iteration $k$, the system:

1. **Observes**: Renders the current script into a visual snapshot $I^{(k)}$
2. **Diagnoses**: A VLM acts as a "visual critic" to perform diagnosis, outputting a structured **Actionable Issue List** $\mathcal{L}_{issue}$ that precisely localizes specific flaws:
   $$\mathcal{L}_{issue}^{(k)} = \text{VLM}_{critic}(I^{(k)})$$
3. **Refines**: The agent executes targeted refinement, applying incremental updates to the code conditioned on the feedback list:
   $$\mathcal{C}^{(k+1)} = \text{Refine}(\mathcal{C}^{(k)}, \mathcal{L}_{issue}^{(k)})$$

This loop continues until the issue list is empty or convergence is reached. The final publication-ready figure is obtained as $\mathcal{F}_{final} = \text{Exec}(\mathcal{C}_{final})$.

**Key Features:**
- **Surgical Modifications**: Instead of regenerating the entire script, applies incremental updates
- **Preserves Structure**: Maintains existing assets and overall layout during refinement
- **Multi-Modal Feedback**: Uses visual comparison between current output and reference blueprint
- **Iterative Optimization**: Continues until visual quality meets publication standards

**Key Components:**
- **Coder** (`coder.py`): Implements Actor-Critic pattern with `generate_critique()` and `refine_code_with_critique()` methods

## Key Design Principles

### 1. Visual Prior Induction
- Leverages high-quality exemplars from top-tier conferences
- Establishes reliable visual priors through semantic search and style extraction
- Ensures consistency with publication-quality design patterns

### 2. Standardized Skills and Experience
- Pre-debugged atomic primitives guarantee code executability
- Cognitive offloading enables focus on semantic layout decisions
- Evolving experience injection prevents known error patterns

### 3. Visual Diagnosis-Driven Refinement
- Multi-modal closed-loop feedback mechanism
- Surgical code modifications preserve structure
- Iterative optimization until visual quality meets standards

### 4. Modular Architecture
- Each component has a clear, single responsibility
- Clean separation between planning, generation, and refinement stages
- Easy to extend and maintain

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

# Optional: Visual Deep Research configuration
export ENABLE_DEEP_RESEARCH="true"  # Enable reference retrieval and style extraction
export RESEARCHER_META_PATH="path/to/metadata.json"  # Path to reference metadata
export RESEARCHER_INDEX_PATH="path/to/index.npy"  # Path to vector index
export EMBEDDING_API_BASE="your_embedding_api_base"  # Embedding API endpoint
export EMBEDDING_API_KEY="your_embedding_api_key"  # Embedding API key
export EMBEDDING_MODEL_NAME="text-embedding-3-large"  # Embedding model name
export RETRIEVAL_TOP_K="3"  # Number of reference images to retrieve
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
    output_dir=None  # Auto-create timestamped directory
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
- **EMBEDDING_MODEL_NAME**: Used for semantic search in Visual Deep Research

### Visual Deep Research Configuration

When `ENABLE_DEEP_RESEARCH` is enabled, the system requires:

- **RESEARCHER_META_PATH**: Path to JSON file containing reference image metadata
- **RESEARCHER_INDEX_PATH**: Path to NumPy array file containing pre-computed embeddings
- **EMBEDDING_API_BASE**: API endpoint for embedding computation
- **EMBEDDING_API_KEY**: API key for embedding service
- **RETRIEVAL_TOP_K**: Number of top reference images to retrieve (default: 3)

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
│   ├── coder.py                # Code generation and refinement (Stage II & III)
│   ├── api_clients.py          # API management
│   ├── ppt_renderer.py         # Code execution and rendering (Stage II)
│   ├── icon_factory.py         # Icon asset generation (Stage I)
│   ├── visual_researcher.py   # Visual Deep Research module (Stage I)
│   ├── tools.py                # Standardized skills library (Stage II)
│   ├── coder_prompts.py       # Experience-driven constraints (Stage II)
│   ├── batch_runner.py         # Batch processing
│   ├── run_evaluation_ours.py # Evaluation scripts
│   └── run_evaluation_ours_edit.py
├── assets/
│   └── workflow.png            # Workflow diagram
├── requirements.txt            # Python dependencies
├── README.md                  # This file
└── SETUP.md                   # Setup instructions
```

## Output Structure

Each task generates a timestamped directory containing:

```
task_YYYYMMDD_HHMMSS/
├── requirement.txt                    # Original user requirement (Stage I input)
├── tools.py                          # Copy of standardized skills library
├── style_guide.json                  # Design style guide from Visual Prior Induction (Stage I)
├── 00_reference_gemini.png           # Visual blueprint (Stage I output)
├── assets/                            # Icon asset library (Stage I)
│   ├── assets_grid_sheet_raw.png
│   └── icon_*.png
├── 01_code_iter_0_*.py               # Initial executable script (Stage II)
├── 01_code_iter_0_*.pptx             # Initial editable figure (Stage II output)
├── 01_code_iter_0_*.png              # Rendered images
├── 02_critique_iter_1.txt            # Visual diagnosis feedback (Stage III)
├── 02_code_iter_1_*.py               # Refined script (Stage III)
├── 02_code_iter_1_*.pptx             # Final refined figure (Stage III output)
└── ...
```

## Evaluation

The system includes evaluation scripts for assessing generation quality:

- `run_evaluation_ours.py`: Comprehensive 9-metric evaluation
- `run_evaluation_ours_edit.py`: Semantic Edit Distance (SED) evaluation

## Technical Details

### Standardized Skills Library

The `tools.py` module provides a comprehensive library of standardized skills that encapsulate complex rendering logic:

- **Connection Tools**: `add_connector()`, `add_free_arrow()`, `add_custom_route_arrow()` - Handle intelligent routing, gradients, and custom paths
- **Shape Tools**: `add_block()`, `add_label()`, `add_container()` - Support various shapes with automatic text centering, transparency, and styling
- **Advanced Features**: Gradient lines, custom polyline paths, alpha transparency, automatic arrow sizing

Each skill is pre-validated and handles edge cases internally, significantly reducing code complexity and error rates.

### Experience-Driven Constraints

The system maintains an evolving repository of negative constraints (`PPTX_BEST_PRACTICES` in `coder_prompts.py`) that prevent known error patterns:

- API misuse prevention (e.g., never use `add_shape` for lines)
- Color assignment safety (only RGBColor objects accepted)
- Coordinate precision requirements (integers only, no float calculations)
- Import and enum constraints

These constraints are automatically injected into generation prompts, performing pre-pruning over the search space.

### Self-Correcting Execution Loop

The system implements a robust execution and debugging mechanism:

1. **Syntax Auto-Correction**: Fixes common syntax errors (e.g., "import from" → "from")
2. **Error Capture**: Extracts detailed error logs from execution failures
3. **Iterative Debugging**: Feeds error information back to the model for targeted fixes
4. **File Recovery**: Handles cases where output files have unexpected names
5. **Timeout Protection**: Prevents infinite execution loops

### Visual Diagnosis Mechanism

The refinement stage employs a structured visual inspection process:

1. **Structured Checklist**: Evaluates four critical dimensions:
   - Canvas & Boundaries (content clipping)
   - Connector Logic & Style (routing, arrow sizes)
   - Text Integrity (spilling, font size, color)
   - Visual Alignment & Style (layout consistency)

2. **Actionable Feedback**: Generates specific, element-bound modification suggestions rather than vague advice

3. **Surgical Refinement**: Applies only the necessary changes while preserving 95% of the original code structure
