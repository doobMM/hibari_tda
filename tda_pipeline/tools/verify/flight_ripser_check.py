"""tools/verify/flight_ripser_check.py — 날갯짓(sketch/flight-core.js vrH1)의 VR H₁ 을 ripser 와 대조할 때 쓰는 쪽.

tools/verify_flight.mjs 가 부른다:  python tools/verify/flight_ripser_check.py  < 점구름.json  > 막대.json
  들어오는 것: {"clouds": [[[x, y, z], ...], ...]}
  나가는 것:   {"ripser": "0.6.14", "bars": [[[탄생, 죽음], ...], ...]}   (H₁, 지속 > 1e-9 만, (탄생, 죽음) 순으로 정렬)

거리는 JS 와 **같은 연산 순서**로 잰다: sqrt(dx*dx + dy*dy + dz*dz) (float64).
ripser 는 거리를 float32 로 다룬다 — JS 쪽도 Math.fround 로 같은 값을 쓰므로 막대가 비트까지 같아야 한다.
"""
import json
import math
import sys

import numpy as np
import ripser


def bars_of(cloud):
    n = len(cloud)
    D = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            dx = cloud[i][0] - cloud[j][0]
            dy = cloud[i][1] - cloud[j][1]
            dz = cloud[i][2] - cloud[j][2]
            D[i, j] = D[j, i] = math.sqrt(dx * dx + dy * dy + dz * dz)
    h1 = ripser.ripser(D, distance_matrix=True, maxdim=1)["dgms"][1]
    out = [[float(b), float(d)] for b, d in h1 if np.isfinite(d) and d - b > 1e-9]
    return sorted(out)


def main():
    data = json.load(sys.stdin)
    json.dump({"ripser": ripser.__version__, "bars": [bars_of(c) for c in data["clouds"]]}, sys.stdout)


if __name__ == "__main__":
    main()
