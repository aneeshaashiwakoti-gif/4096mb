import json

with open('output/chunks.json', encoding='utf-8') as f:
    chunks = json.load(f)

samples = []
for c in chunks:
    if 'src/click/core.py' in c['file_path'] and 'class Command' in c['text']:
        samples.append(('src/click/core.py (Command class)', c))
        break

for c in chunks:
    if 'src/click/decorators.py' in c['file_path'] and 'def option' in c['text']:
        samples.append(('src/click/decorators.py (option decorator)', c))
        break

for c in chunks:
    if 'tests/test_basic.py' in c['file_path'] and 'def test_' in c['text']:
        samples.append(('tests/test_basic.py (unit test)', c))
        break

for label, c in samples:
    print('='*70)
    print(f"SAMPLE CHUNK: {label} [L{c['start_line']}-L{c['end_line']}] ({len(c['text'])} chars, {c['end_line']-c['start_line']+1} lines)")
    print('='*70)
    print(c['text'].strip()[:600])
    print('...\n')
