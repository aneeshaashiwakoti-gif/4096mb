import json

data = json.load(open("output/chunks.json", encoding="utf-8"))
print(f"Total chunks: {len(data)}\n")
for i, c in enumerate(data):
    emb_info = f"dim={len(c['embedding'])}" if c["embedding"] else "None"
    print(f"[{i:>2}] {c['file_path']:<22} lines {c['start_line']:>3}-{c['end_line']:<3}  {len(c['text']):>5} chars  embedding={emb_info}")

# Show first chunk JSON structure
print("\n--- First chunk (keys) ---")
print(list(data[0].keys()))
