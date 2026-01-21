from huggingface_hub import list_repo_files

repo_id = "Qwen/Qwen3-VL-32B-Instruct-GGUF"
files = list_repo_files(repo_id)
print(f"Files in {repo_id}:")
for f in files:
    if f.endswith(".gguf"):
        print(f)
