import json
from pathlib import Path

with open('output/chunks.json', encoding='utf-8') as f:
    chunks = json.load(f)

print(f"Total chunks: {len(chunks)}")
assert len(chunks) == 41

# (a) Check schema
expected_keys = {'text', 'file_path', 'start_line', 'end_line', 'embedding'}
for i, c in enumerate(chunks):
    assert set(c.keys()) == expected_keys, f"Schema mismatch in chunk {i}"
print("(a) Schema verified: exactly the 5 locked fields in all 41 chunks.")

# (b) Check embeddings
emb_dims = set()
for i, c in enumerate(chunks):
    emb = c['embedding']
    assert emb is not None and isinstance(emb, list) and len(emb) == 3072
    assert all(isinstance(v, float) for v in emb)
    emb_dims.add(len(emb))
print(f"(b) Embeddings verified: all 41 non-null float arrays of dimension {emb_dims}.")

# (c) Spot check model.py individual function/class chunks
print("\n(c) Inspecting model.py chunks in output/chunks.json:")
model_chunks = [c for c in chunks if 'model.py' in c['file_path']]
print(f"model.py chunk count: {len(model_chunks)} (previously 1 giant chunk)")
for i, c in enumerate(model_chunks):
    lines = c['text'].strip().splitlines()
    first = lines[0][:60]
    last = lines[-1][:60]
    print(f"  • Chunk {i:>2} [L{c['start_line']:>3}-L{c['end_line']:<3}] ({c['end_line'] - c['start_line'] + 1} lines, {len(c['text'])} chars)")
    print(f"      Starts: {first!r}")
    print(f"      Ends:   {last!r}")
