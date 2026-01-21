
import subprocess
import time
import requests
import sys
import os
import signal
import base64
from io import BytesIO
from PIL import Image, ImageDraw
from openai import OpenAI

# Configuration
MODEL_PATH = "models/Qwen3VL-32B-Instruct-Q8_0.gguf"
MMPROJ_PATH = "models/mmproj-Qwen3VL-32B-Instruct-Q8_0.gguf"
SERVER_BIN = "./llama.cpp/build/bin/llama-server"
HOST = "127.0.0.1"
PORT = 8080
API_BASE = f"http://{HOST}:{PORT}/v1"

# Generate Dummy Image
def generate_image():
    print("Generating test image...")
    img = Image.new('RGB', (1024, 1024), color='white')
    d = ImageDraw.Draw(img)
    d.text((50, 50), "Sanity Check Passed: 2026", fill=(0, 0, 0))
    d.rectangle([100, 100, 300, 300], outline="red", width=5)
    d.text((120, 150), "Red Box", fill=(255, 0, 0))
    
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return f"data:image/jpeg;base64,{img_b64}"

def wait_for_server():
    print("Waiting for server to become healthy...")
    for i in range(120): # Wait up to 2 minutes
        try:
            response = requests.get(f"http://{HOST}:{PORT}/health")
            if response.status_code == 200:
                print("Server is ready!")
                return True
        except requests.ConnectionError:
            pass
        time.sleep(1)
        if i % 10 == 0:
            print(f"Still waiting... ({i}s)")
    return False

def main():
    # 1. Start Server
    print(f"Starting server with model: {MODEL_PATH}")
    
    # Use stdbuf to unbuffer output so we see logs immediately
    cmd = [
        SERVER_BIN,
        "--model", MODEL_PATH,
        "--mmproj", MMPROJ_PATH,
        "--host", HOST,
        "--port", str(PORT),
        "--n-gpu-layers", "0",
        "--ctx-size", "2048",
        "--log-disable" # reduce noise
    ]
    
    # Start process
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL, # Mute stdout for cleaner output
        stderr=subprocess.PIPE     # Capture stderr for errors
    )
    
    try:
        if not wait_for_server():
            print("Server failed to start.")
            # Print stderr
            _, stderr = process.communicate(timeout=1)
            print(stderr.decode())
            return

        # 2. Run Test
        client = OpenAI(base_url=API_BASE, api_key="sk-no-key-required")
        
        image_uri = generate_image()
        
        print("\n--- Sending Request ---")
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo", # Model name is ignored by default server
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_uri}},
                            {"type": "text", "text": "Describe this image in detail. What text and shapes do you see?"}
                        ]
                    }
                ],
                max_tokens=50
            )
            print("\nResponse:")
            print(response.choices[0].message.content)
            
        except Exception as e:
            print(f"Request failed: {e}")

    finally:
        # 3. Cleanup
        print("\nStopping server...")
        process.terminate()
        process.wait()
        print("Done.")

if __name__ == "__main__":
    main()
