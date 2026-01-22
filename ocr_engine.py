"""
OCR Engine Module for Qwen3-VL.

This module handles the core OCR functionality:
1. Lazy loading of the MLX model (Singleton pattern).
2. Memory-safe image resizing (max 1024px).
3. Deterministic text generation.

Interface:
    transcribe_image(image_source: Union[str, Path, Image.Image], temp_dir: Optional[Path] = None) -> str
"""

import time
import sys
import mlx.core as mx
from pathlib import Path
from typing import Optional, Tuple, Union, Any
from PIL import Image

from mlx_vlm import load, generate
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config

# Configuration
MODEL_PATH = "mlx-community/Qwen3-VL-8B-Instruct-4bit"
MAX_IMAGE_DIM = 1024
DEFAULT_PROMPT = "Transcribe the text in this image to Markdown format. Preserve the layout, prices, and structure as accurately as possible."

# Singleton State
_MODEL = None
_PROCESSOR = None
_CONFIG = None

def _load_model_if_needed() -> None:
    """Lazy loads the model components if they are not already in memory."""
    global _MODEL, _PROCESSOR, _CONFIG
    if _MODEL is None:
        print(f"🔧 MLX Device: {mx.default_device()}")
        print(f"🚀 Loading Model: {MODEL_PATH}...")
        try:
            _MODEL, _PROCESSOR = load(MODEL_PATH)
            _CONFIG = load_config(MODEL_PATH)
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            sys.exit(1)

def _resize_image_if_needed(image: Image.Image, max_dim: int = MAX_IMAGE_DIM) -> Image.Image:
    """
    Resizes PIL image if it exceeds max dimensions to prevent OOM.
    Returns the processed PIL Image object.
    """
    width, height = image.size
    longest_side = max(width, height)
    
    if longest_side > max_dim:
        scale = max_dim / longest_side
        new_size = (int(width * scale), int(height * scale))
        print(f"    📉 Resizing {width}x{height} -> {new_size[0]}x{new_size[1]} (Memory Optimization)")
        
        # Handle modes that don't resize or save well (like P or RGBA if destined for JPEG)
        if image.mode in ("P", "RGBA"):
            image = image.convert("RGB")
            
        return image.resize(new_size, Image.Resampling.LANCZOS)
    
    return image

def transcribe_image(
    image_source: Union[str, Path, Image.Image],
    temp_dir: Path,
    prompt: str = DEFAULT_PROMPT
) -> Optional[str]:
    """
    Main entry point for OCR.
    
    Args:
        image_source: File path (str/Path) or PIL Image object.
        temp_dir: Directory to save intermediate resized file (required by MLX API).
        prompt: The instruction for the model.
        
    Returns:
        The transcribed text or None if failed.
    """
    _load_model_if_needed()
    
    temp_file_path = None
    
    try:
        # 1. Load and Standardize Image
        if isinstance(image_source, (str, Path)):
            img = Image.open(image_source)
            original_name = Path(image_source).name
        else:
            img = image_source
            original_name = "in_memory_image"

        # 2. Resize/Safe-guard
        processed_img = _resize_image_if_needed(img)
        
        # 3. Save to temp file (MLX generate expects a file path)
        # We assume processed_img is ready to be saved as JPEG
        if processed_img.mode != "RGB":
            processed_img = processed_img.convert("RGB")
            
        temp_file_path = temp_dir / f"ocr_temp_{int(time.time()*1000)}.jpg"
        processed_img.save(temp_file_path)

        # 4. Prepare Prompt
        formatted_prompt = apply_chat_template(
            _PROCESSOR, 
            _CONFIG, 
            prompt, 
            num_images=1
        )
        
        # 5. Generate
        t_start = time.time()
        
        output = generate(
            _MODEL,
            _PROCESSOR,
            formatted_prompt,
            image=[str(temp_file_path)],
            verbose=False,
            max_tokens=2048,
            temperature=0.0
        )
        
        duration = time.time() - t_start
        text = output.text
        
        # Stats
        char_count = len(text)
        tps = (char_count / 4) / duration if duration > 0 else 0
        print(f"    ⚡️ Generated {char_count} chars in {duration:.2f}s (~{tps:.1f} TPS)")
        
        return text

    except Exception as e:
        print(f"    ❌ Error processing {original_name if 'original_name' in locals() else 'image'}: {e}")
        return None
        
    finally:
        # Cleanup specific temp file for this inference
        if temp_file_path and temp_file_path.exists():
            try:
                temp_file_path.unlink()
            except OSError:
                pass
