import argparse
import base64
import sys
import os
from openai import OpenAI

# Configuration
API_BASE = "http://localhost:8080/v1"
API_KEY = "sk-no-key-required"

def encode_image(image_path):
    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        sys.exit(1)
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def main():
    parser = argparse.ArgumentParser(description="Qwen3-VL Client")
    parser.add_argument("image_path", help="Path to the image file")
    parser.add_argument("--prompt", default="Describe this image in detail.", help="Text prompt")
    parser.add_argument("--system", default="You are a helpful assistant.", help="System prompt")
    args = parser.parse_args()

    print(f"Connecting to Qwen3-VL server at {API_BASE}...")
    client = OpenAI(base_url=API_BASE, api_key=API_KEY)

    try:
        # Encode image
        print(f"Encoding image: {args.image_path}")
        base64_image = encode_image(args.image_path)
        data_url = f"data:image/jpeg;base64,{base64_image}"

        print("Sending request...")
        response = client.chat.completions.create(
            model="qwen3-vl", # Model name ignored by server
            messages=[
                {"role": "system", "content": args.system},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": args.prompt},
                    ],
                }
            ],
            max_tokens=1024,
            temperature=0.7,
        )

        print("\n--- Response ---")
        print(response.choices[0].message.content)
        print("----------------")

    except Exception as e:
        print(f"\nError: {e}")
        print("Ensure the server is running: ./run_qwen_server.sh")

if __name__ == "__main__":
    main()