from original_paths import project_path
import os
files = os.listdir(project_path('data/raw_pdfs/social_welfare'))
target = [f for f in files if 'শিক্ষা উপবৃত্তি_23-24' in f]
for f in target:
    print(repr(f))
    for c in f:
        if ord(c) > 127 and not (0x980 <= ord(c) <= 0x9FF):
            print(f"  non-Bengali non-ASCII char: {repr(c)} = U+{ord(c):04X}")