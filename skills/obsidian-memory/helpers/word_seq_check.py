"""Verify a formatting-only edit: word sequence must be identical.
Usage: python3 word_seq_check.py <before_file> <after_file>"""
import sys, re
def words(p):
    s = open(p).read()
    return re.findall(r"[\w§✅❌⚠💡🔑🔓✨🗣⏰👀]+", s, re.UNICODE)
a, b = words(sys.argv[1]), words(sys.argv[2])
if a == b:
    print("OK: word sequence identical", len(a), "tokens")
else:
    # find first divergence
    for i,(x,y) in enumerate(zip(a,b)):
        if x != y:
            print(f"DIVERGE at token {i}: before={x!r} after={y!r}  context_before={' '.join(a[max(0,i-5):i+3])!r}")
            sys.exit(1)
    print(f"LENGTH MISMATCH: before={len(a)} after={len(b)}; tail_before={a[len(b):len(b)+8] if len(a)>len(b) else ''} tail_after={b[len(a):len(a)+8] if len(b)>len(a) else ''}")
    sys.exit(1)
