import json
from pathlib import Path

with open('output/chunks.json', encoding='utf-8') as f:
    chunks = json.load(f)

print(f"Total chunks in output/chunks.json: {len(chunks)}")

# (a) Check schema
expected_keys = {'text', 'file_path', 'start_line', 'end_line', 'embedding'}
for i, c in enumerate(chunks):
    assert set(c.keys()) == expected_keys, f"Schema mismatch at chunk {i}"
print("(a) Schema verified: exactly the 5 locked fields across all chunks.")

# (b) Check embeddings
emb_dims = set()
for i, c in enumerate(chunks):
    emb = c['embedding']
    assert emb is not None and isinstance(emb, list) and len(emb) == 3072, f"Invalid embedding at chunk {i}"
    assert all(isinstance(v, float) for v in emb), f"Non-float value in embedding at chunk {i}"
    emb_dims.add(len(emb))
print(f"(b) Embeddings verified: all {len(chunks)} chunks have non-null float arrays of dimension {emb_dims}.")

# (c) Spot check 6 line citations across different click modules
spot_checks = [10, 50, 150, 250, 400, 600]
print("\n(c) Spot-checking line citations across different click modules:")
for idx in spot_checks:
    if idx < len(chunks):
        c = chunks[idx]
        file_p = Path('click') / c['file_path']
        lines = file_p.read_text(encoding='utf-8', errors='replace').splitlines()
        start = c['start_line']
        end = c['end_line']
        c_lines = c['text'].strip().splitlines()
        first_c = c_lines[0].strip()
        last_c = c_lines[-1].strip()
        first_actual = lines[start-1].strip() if start <= len(lines) else ""
        last_actual = lines[end-1].strip() if end <= len(lines) else ""
        print(f"  • Chunk {idx:>3} ({c['file_path']} L{start}-L{end}):")
        print(f"      First line: {first_c[:50]!r} == {first_actual[:50]!r} (Match: {first_c == first_actual})")
        print(f"      Last line:  {last_c[:50]!r} == {last_actual[:50]!r} (Match: {last_c == last_actual})")
