# tools/verify/xcheck_ripser_h1.py — 검산용: JSON 점구름들 → ripser H1 막대. 사용: python ripser_h1.py in.json out.json
import json, sys
import numpy as np
from ripser import ripser

src, dst = sys.argv[1], sys.argv[2]
clouds = json.load(open(src, encoding='utf-8'))
out = []
for pts in clouds:
    X = np.asarray(pts, dtype=float)
    dg = ripser(X, maxdim=1)['dgms'][1]
    bars = sorted([[float(b), float(d)] for b, d in dg if d - b > 1e-9], key=lambda x: (x[0], x[1]))
    out.append(bars)
json.dump(out, open(dst, 'w', encoding='utf-8'))
print('clouds', len(clouds), 'bars', sum(len(b) for b in out))
