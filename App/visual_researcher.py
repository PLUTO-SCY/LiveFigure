import json
import os
import numpy as np
from typing import List, Dict, Any, Optional
from openai import OpenAI
from config import Config
from api_clients import APIManager


class VisualDeepResearcher:
    """
    Visual Deep Researcher: Retrieves reference images from database and extracts design styles.
    
    Workflow:
    1. Search references: Query embedding -> Vector similarity search -> Top-K results
    2. Extract design style: Analyze retrieved images with VLM -> Synthesize style guide
    """
    
    def __init__(self):
        """
        Initialize: Load index data and Embedding API client
        """
        print(f"[Researcher] Initializing retrieval module...")
        
        # 1. Load metadata (JSON)
        meta_path = os.getenv("RESEARCHER_META_PATH", "")
        if meta_path and os.path.exists(meta_path):
            self.metadata = self._load_metadata(meta_path)
        else:
            print(f"[Researcher] Warning: Metadata path not configured or not found. Using empty metadata.")
            self.metadata = []
        
        # 2. Load vector index (Numpy)
        # Normalize during loading so subsequent dot product equals cosine similarity
        index_path = os.getenv("RESEARCHER_INDEX_PATH", "")
        if index_path and os.path.exists(index_path):
            self.index_vectors = self._load_index(index_path)
        else:
            print(f"[Researcher] Warning: Index path not configured or not found. Using empty index.")
            self.index_vectors = np.array([])
        
        # 3. Initialize Embedding API client
        embedding_api_base = os.getenv("EMBEDDING_API_BASE", Config.API_BASE)
        embedding_api_key = os.getenv("EMBEDDING_API_KEY", Config.API_KEY)
        self.embedding_client = OpenAI(
            base_url=embedding_api_base,
            api_key=embedding_api_key
        )
        
        # 4. Initialize VLM Client (for style extraction)
        self.api_manager = APIManager()
        
        # Configuration
        self.retrieval_top_k = int(os.getenv("RETRIEVAL_TOP_K", "3"))
        self.embedding_model = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-large")

    def _load_metadata(self, path: str) -> List[Dict]:
        """Load metadata JSON file"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Metadata file not found: {path}")
        print(f"[Researcher] Loading metadata: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_index(self, path: str) -> np.ndarray:
        """Load vector index file and normalize"""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Vector index file not found: {path}")
        print(f"[Researcher] Loading vector index: {path}")
        try:
            index = np.load(path)
            print(f"[Researcher] Index dimensions: {index.shape}")
            # Pre-normalize index vectors
            norm = np.linalg.norm(index, axis=1, keepdims=True)
            # Avoid division by zero
            return index / (norm + 1e-10)
        except Exception as e:
            raise RuntimeError(f"Failed to load or normalize index: {e}")

    def _get_query_embedding(self, query: str) -> np.ndarray:
        """
        Call API to compute query embedding
        """
        try:
            response = self.embedding_client.embeddings.create(
                input=query,
                model=self.embedding_model
            )
            # Extract vector
            embedding = response.data[0].embedding
            
            # Convert to numpy array
            embedding_np = np.array(embedding)
            
            # Normalize query vector
            norm = np.linalg.norm(embedding_np)
            if norm > 0:
                embedding_np = embedding_np / norm
                
            return embedding_np
            
        except Exception as e:
            print(f"[Researcher Error] Embedding API call failed: {e}")
            raise e

    def search_references(self, query: str, top_k: Optional[int] = None) -> List[Dict]:
        """
        Execute RAG retrieval
        """
        if top_k is None:
            top_k = self.retrieval_top_k
            
        if len(self.metadata) == 0 or len(self.index_vectors) == 0:
            print(f"[Researcher] Warning: Empty metadata or index. Returning empty results.")
            return []
            
        print(f"[Researcher] Searching for query: '{query}' ...")
        
        # 1. Compute query vector
        query_vec = self._get_query_embedding(query)  # shape (d,)
        
        # 2. Compute cosine similarity (Matrix Multiplication)
        # index shape: (N, d), query shape: (d,) -> scores shape: (N,)
        if query_vec.shape[0] != self.index_vectors.shape[1]:
            print(f"[Researcher] Error: Dimension mismatch. Query: {query_vec.shape[0]}, Index: {self.index_vectors.shape[1]}")
            return []
            
        scores = np.dot(self.index_vectors, query_vec)
        
        # 3. Get Top-K indices
        top_k_indices = np.argsort(scores)[::-1][:top_k]
        
        # 4. Assemble results
        results = []
        print(f"[Researcher] Retrieval complete, Top-{top_k} results:")
        for idx in top_k_indices:
            # Bounds check
            if idx >= len(self.metadata):
                continue
                
            meta = self.metadata[idx]
            score = scores[idx]
            
            # Record key information
            result_item = {
                "score": float(score),
                "paper_name": meta.get("paper_name", "Unknown Paper"),
                "figure_label": meta.get("figure_label", "Unknown Figure"),
                "caption": meta.get("caption", ""),
                "description": meta.get("description", ""),  # Clean description extracted by LLM
                "image_path": meta.get("image_abs_path", ""),  # Absolute path
                "used_text": meta.get("embedding_text_used", "")  # For debugging
            }
            results.append(result_item)
            print(f"   - [Score: {score:.4f}] {result_item['figure_label']} from {result_item['paper_name']}")
            
        return results

    def extract_design_style(self, reference_results: List[Dict]) -> Dict:
        """
        Business logic: Analyze multiple images -> Summarize into pixel-level design guide
        """
        if not reference_results:
            return self._get_default_style()

        print(f"[Researcher] Starting deep analysis of {len(reference_results)} reference images...")
        
        valid_results = []
        
        for i, item in enumerate(reference_results):
            image_path = item.get("image_path")
            description = item.get("description", "")
            
            if not image_path or not os.path.exists(image_path):
                print(f"[Researcher] Warning: Image path not found: {image_path}")
                continue

            # Enhanced Prompt
            system_prompt = """
            You are a Senior Design System Architect for scientific publications. 
            Your task is to reverse-engineer the visual design language of a scientific diagram into a structured Design System JSON.
            Focus on granular details that can be translated into rendering code (SVG/CSS/Graphviz).
            """
            
            user_prompt = f"""
            Context: {description}
            
            Analyze this image and extract the visual design system. 
            Don't just say "Left-to-Right". Be specific about alignment, spacing, and shapes.

            Output strictly JSON with the following structure:
            {{
                "layout_engine": {{
                    "topology": "String (e.g., 'Multi-stage Pipeline', 'Hierarchical Tree', 'Central Hub-Spoke')",
                    "flow_direction": "String (e.g., 'Left-to-Right', 'Top-Down', 'Circular')",
                    "alignment": "String (e.g., 'Center-aligned backbone', 'Top-aligned branches')",
                    "density": "String (e.g., 'Compact with tight spacing', 'Airy with large whitespace')",
                    "grouping_style": "String (e.g., 'Submodules enclosed in dashed rounded rectangles')"
                }},
                "node_style": {{
                    "shape_primitive": "String (e.g., 'Rounded Rectangle', 'Cylinder', 'Circle')",
                    "corner_radius": "String (e.g., 'Small (2px)', 'Large (10px)', 'None')",
                    "fill_style": "String (e.g., 'Solid pastel fill', 'White with colored border', 'Vertical gradient')",
                    "stroke_width": "String (e.g., 'Thin (1px)', 'Thick (3px)')",
                    "stroke_style": "String (e.g., 'Solid', 'Dashed', 'Double-line')",
                    "shadow": "String (e.g., 'No shadow', 'Soft drop shadow', 'Hard isometric shadow')"
                }},
                "edge_style": {{
                    "type": "String (e.g., 'Orthogonal (Manhattan)', 'Straight', 'Bezier Curve')",
                    "arrow_head": "String (e.g., 'Filled Triangle', 'Open V', 'Diamond')",
                    "stroke_color": "String (e.g., 'Gray #888', 'Black #000')",
                    "routing": "String (e.g., 'Avoids node crossing', 'Direct connection')"
                }},
                "typography": {{
                    "font_family": "String (e.g., 'Sans-serif (Arial/Helvetica)', 'Serif (Times)')",
                    "label_position": "String (e.g., 'Centered inside nodes', 'Floating above edges')",
                    "casing": "String (e.g., 'Title Case', 'UPPERCASE', 'Sentence case')"
                }},
                "color_palette": [
                    {{ "hex": "#HEX", "usage": "Background/Primary Node/Highlight" }}
                ]
            }}
            """

            # Call VLM interface
            try:
                result_text = self.api_manager.chat_with_vlm(
                    prompt=user_prompt,
                    image_paths=[image_path],
                    model=Config.MODEL_VLM
                )
                
                if result_text:
                    # Parse JSON from response
                    try:
                        # Try to extract JSON from markdown code blocks
                        json_str = result_text.replace("```json", "").replace("```", "").strip()
                        result = json.loads(json_str)
                        valid_results.append(result)
                    except json.JSONDecodeError:
                        print(f"[Researcher] Warning: Failed to parse JSON from VLM response for image {i+1}")
                        continue
                        
            except Exception as e:
                print(f"[Researcher] Error analyzing image {i+1}: {e}")
                continue

        if not valid_results:
            return self._get_default_style()

        # If only one result, return directly
        if len(valid_results) == 1:
            print("[Researcher] Design style extraction complete (Single Source).")
            return valid_results[0]
            
        # Multiple results synthesis logic
        return self._synthesize_styles([json.dumps(r) for r in valid_results])
    

    def _synthesize_styles(self, analyses_texts: List[str]) -> Dict:
        """
        Internal method: Call text-only LLM to merge multiple analysis results into one unified Style Guide
        """
        context_block = "\n".join(analyses_texts)
        
        system_prompt = """
        You are a Senior Design Director. 
        Your task is to synthesize multiple design analysis reports into ONE unified, coherent Design Style Guide for a new scientific diagram.
        Resolve conflicts by choosing the most common or scientifically professional option.
        Output strictly JSON.
        """
        
        user_prompt = f"""
        Here are the analysis reports from the reference images:
        {context_block}

        Please synthesize them into a single JSON with these keys:
        1. "layout_engine": (The most suitable layout structure)
        2. "color_palette": (A unified list of 3-5 harmonious hex codes)
        3. "node_style": (Unified geometric style)
        4. "edge_style": (Unified connector style)
        """

        # Call text-only interface
        try:
            response_text = self.api_manager.chat_with_llm(
                prompt=user_prompt,
                system_prompt=system_prompt,
                model=Config.MODEL_PLANNER,
                json_mode=True
            )
            
            if isinstance(response_text, str):
                try:
                    json_str = response_text.replace("```json", "").replace("```", "").strip()
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
            
            # If already a dict (from json_mode)
            if isinstance(response_text, dict):
                return response_text
                
            return self._get_default_style()
            
        except Exception as e:
            print(f"[Researcher Error] Style synthesis failed: {e}")
            return self._get_default_style()

    def _get_default_style(self):
        """Return default style guide when no references are available"""
        return {
            "layout_engine": {
                "topology": "Left-to-Right Pipeline",
                "flow_direction": "Left-to-Right",
                "alignment": "Center-aligned",
                "density": "Moderate spacing",
                "grouping_style": "Standard grouping"
            },
            "color_palette": [
                {"hex": "#E6F3FF", "usage": "Background"},
                {"hex": "#333333", "usage": "Primary Node"}
            ],
            "node_style": {
                "shape_primitive": "Rounded Rectangle",
                "corner_radius": "Small",
                "fill_style": "Solid pastel fill",
                "stroke_width": "Thin (1px)",
                "stroke_style": "Solid",
                "shadow": "No shadow"
            },
            "edge_style": {
                "type": "Straight",
                "arrow_head": "Filled Triangle",
                "stroke_color": "Gray #888",
                "routing": "Direct connection"
            },
            "typography": {
                "font_family": "Sans-serif",
                "label_position": "Centered inside nodes",
                "casing": "Title Case"
            }
        }
