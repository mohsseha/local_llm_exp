import sys
import base64
from io import BytesIO
from PIL import Image, ImageDraw

# Generate Dummy Image
print("Generating test image...")
img = Image.new('RGB', (1024, 1024), color='white')
d = ImageDraw.Draw(img)
# Draw some text and shapes
d.text((50, 50), "Sanity Check Passed: 2026", fill=(0, 0, 0))
d.rectangle([100, 100, 300, 300], outline="red", width=5)
d.text((120, 150), "Red Box", fill=(255, 0, 0))

# Convert to Base64
buffered = BytesIO()
img.save(buffered, format="JPEG")
img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
data_uri = f"data:image/jpeg;base64,{img_b64}"

print("Importing llama_cpp...")
from llama_cpp import Llama
from llama_cpp.llama_chat_format import Llava15ChatHandler

# Attempt to locate Qwen2VL specific handler if available in this build
try:
    from llama_cpp.llama_chat_format import Qwen2VLChatHandler
    print("Success: Qwen2VLChatHandler is available.")
    HandlerClass = Qwen2VLChatHandler
except ImportError:
    print("Warning: Qwen2VLChatHandler not found. Falling back to Llava15ChatHandler (may be incompatible).")
    HandlerClass = Llava15ChatHandler

# Initialize Handler
# Note: min_pixel/max_pixel logic is often handled inside the handler or default to sensible values.
# For Qwen2/3, ensuring the image is resized to factor of 32 is crucial, but let's see if the handler does it.
chat_handler = HandlerClass(clip_model_path="./models/mmproj-Qwen3VL-32B-Instruct-Q8_0.gguf")

# Initialize Model
print("Loading Model (this may take time on CPU)...")
llm = Llama(
    model_path="./models/Qwen3VL-32B-Instruct-Q8_0.gguf",
    chat_handler=chat_handler,
    n_ctx=2048,  # Small context for speed
    n_gpu_layers=0,
    verbose=False # Keep it clean
)

# Test Prompts
prompts = [
    "qwenvl markdown",
    "Describe this image."
]

for p in prompts:
    print(f"\n\n--- Testing Prompt: '{p}' ---")
    messages = [
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": data_uri}},
            {"type": "text", "text": p}
        ]}
    ]
    
    try:
        response = llm.create_chat_completion(messages=messages, max_tokens=200, temperature=0.1)
        print("Response Content:")
        print(response['choices'][0]['message']['content'])
    except Exception as e:
        print(f"Error during inference: {e}")

print("\nSanity Check Complete.")
