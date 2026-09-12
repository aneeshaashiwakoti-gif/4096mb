import os
from pathlib import Path

base = Path('test_edge_cases')
base.mkdir(exist_ok=True)

# 1. Empty .py file (0 bytes)
(base / 'empty.py').write_bytes(b'')

# 2. Whitespace / comments only
(base / 'comments_only.py').write_text('# Just a comment line\n   \n\t\n# Another comment\n', encoding='utf-8')

# 3. Very large file (~5000+ lines)
large_lines = []
for i in range(1200):
    large_lines.append(f'def generated_fn_{i}(x):\n    """Docstring for fn {i}"""\n    y = x + {i}\n    return y * 2\n')
(base / 'large_generated.py').write_text('\n'.join(large_lines), encoding='utf-8')

# 4. Non-code binary renamed as .py (PNG header + null bytes)
fake_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00\x00\x00\x01\x00\x08\x06\x00\x00\x00' + b'\x00' * 50
(base / 'fake_binary.py').write_bytes(fake_png)

# 5. Invalid / malformed syntax (unclosed brackets, broken indentation)
malformed_code = '''def broken_fn(x, y:
    if x > 0:
      a = [1, 2, 3
    print('missing brackets')
\t return a
'''
(base / 'malformed_syntax.py').write_text(malformed_code, encoding='utf-8')

# 6. Non-UTF-8 / Latin-1 encoding with high-byte special characters
latin1_text = '# Latin-1 special characters: résumé, café, naïve, ñ, ü, ß\ndef get_location():\n    return "München, Großraum"\n'
(base / 'latin1_encoded.py').write_bytes(latin1_text.encode('latin-1'))

# 7. Empty directory
empty_dir = base / 'empty_directory'
empty_dir.mkdir(exist_ok=True)

# 8. Deeply nested directory structure (6 levels) with small file at bottom
deep_dir = base / 'lvl1' / 'lvl2' / 'lvl3' / 'lvl4' / 'lvl5' / 'lvl6'
deep_dir.mkdir(parents=True, exist_ok=True)
(deep_dir / 'deep_nested.py').write_text('def deep_fn():\n    return "I survived nesting!"\n', encoding='utf-8')

print("test_edge_cases scaffolding complete.")
