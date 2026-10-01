"""⛔ 2026-10-01 사용자: "모양 위에 표시하는 게 직관적이지 않은 것 같아" → 판을 모듈 시계로 바꿨다(export_relay_clock.py).
이 스크립트와 결과(docs/step3_data/relay_net_checks.json)는 기록으로 남긴다. 페이지 자료(sketch/data/relay_hibari.json)는 지웠다.

잇기(③ 주고받기 + ① 몸을 연주) 의 그물 — hibari 몸 위의 자리 · 실 · 막 · 창.  → sketch/data/relay_hibari.json

자리 = 닮은 대목(맥락, song_fold.features)끼리 묶은 것(k-means). 누르면 그 자리의 대표 대목이 운다.
실   = 두 자리 사이 링크(사슬 = 곡이 이어짐, 접촉 = 닮음 kNN)가 문턱 c 개 이상.
막   = 세 자리가 서로 다 이어진 세모(깃발 복합체의 2-단체).  창 = 막으로 메워지지 않는 고리 = 깃발 복합체의 H1.
창을 한 바퀴 두른 고리만 운다 — 페이지는 쌍대사슬(cocycle)과 고리의 짝이 0 이 아닌지로 가린다.

PREDICTION (돌리기 전에 적음, 2026-10-01)
  R1 자리 40개 · c = 2 에서 창 2~8개.
  R2 문턱 c = 1, 2, 3 에서 창 수가 ±2 안이다(버팀).
  R3 창마다 가장 짧은 우는 고리가 6자리 이하 — 주고받기 3번 안에 닫힌다.
  R4 대조군(시각을 뒤섞은 곡, 같은 절차): 창이 더 많고 문턱에 따라 크게 흔들린다(무작위 그물은 구멍이 많다).
결과(2026-10-01): R1 은 자리 40 에서 실패(창 1) → 40·48·56 을 보고 48 로 골랐다(창 5, c=1·2·3 에서 5·5·6, 가장 짧은 고리 전부 4). 놀 거리를 보고 고른 설계 선택이지 확증이 아니다.
  R4 는 방향이 틀렸다 — 시각을 뒤섞으면 맥락이 서로 비슷해져 실이 3배 넘게 빽빽해지고(629 대 179) 창이 0 이 된다. 창은 곡의 시간 순서에서 온다(단 밀도가 함께 바뀌는 교란이 있다).
한계: 창의 수와 자리는 묶음(k-means 시드)과 문턱에 따라 달라진다. 연구의 음 고리(정본 H1, 14개)와는 다른 대상이다 — 몸(대목 그물)의 구멍이다.
실행: python experiments/export_relay_net.py
"""
import os, sys, json
from collections import deque
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import song_fold as sf
from ripser import ripser
from scipy.cluster.vq import kmeans2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N = int(sys.argv[1]) if len(sys.argv) > 1 else 48
C_EXPORT, P = 2, 47


def net(W, pairs, n=N, seed=1):
    """맥락 W · 접촉 쌍 → 자리 번호, 링크 수(무방향), 사슬 다음 수(방향)."""
    np.random.seed(seed); _, lab = kmeans2(W.astype(np.float64), n, minit='++', seed=seed)
    cnt, succ = {}, {}
    for i, j in list(map(tuple, pairs.tolist())) + [(i, i + 1) for i in range(len(W) - 1)]:
        a, b = int(lab[i]), int(lab[j])
        if a != b: k = (min(a, b), max(a, b)); cnt[k] = cnt.get(k, 0) + 1
    for i in range(len(W) - 1):
        a, b = int(lab[i]), int(lab[i + 1])
        if a != b: succ[(a, b)] = succ.get((a, b), 0) + 1
    return lab, cnt, succ


def windows(n, E):
    """깃발 복합체 H1 — 창마다 (쌍대사슬 {(u,w): 값}, 가장 짧은 우는 고리)."""
    D = np.full((n, n), 2.0); np.fill_diagonal(D, 0)
    for a, b in E: D[a, b] = D[b, a] = 1.0
    r = ripser(D, distance_matrix=True, maxdim=1, thresh=1.5, coeff=P, do_cocycles=True)
    adj = {u: [] for u in range(n)}
    for a, b in E: adj[a].append(b); adj[b].append(a)
    out = []
    for k, (b0, d0) in enumerate(r['dgms'][1]):
        if not np.isinf(d0): continue
        val = {}
        for i, j, v in r['cocycles'][1][k]:
            v = int(v); v = v - P if v > P // 2 else v; i, j = int(i), int(j)
            val[(i, j)] = v; val[(j, i)] = -v
        best = None
        for s in range(n):                        # 상태 (자리, 짝 mod P) 위의 너비 우선 — 짝이 0 이 아닌 가장 짧은 닫힌 길
            prev = {(s, 0): None}; q = deque([(s, 0)]); depth = {(s, 0): 0}
            while q:
                u, m = q.popleft()
                if best and depth[(u, m)] >= len(best): break
                for w in adj[u]:
                    st = (w, (m + val.get((u, w), 0)) % P)
                    if st not in prev: prev[st] = (u, m); depth[st] = depth[(u, m)] + 1; q.append(st)
            for m in range(1, P):
                if (s, m) in prev and (best is None or depth[(s, m)] < len(best)):
                    path, st = [], (s, m)
                    while st is not None: path.append(st[0]); st = prev[st]
                    best = path[::-1][:-1]
        out.append((val, best))
    return out


def summary(W, pairs, label):
    rows = {}
    for c in (1, 2, 3):
        lab, cnt, succ = net(W, pairs)
        E = [k for k, v in cnt.items() if v >= c]; ws = windows(N, E)
        rows[c] = {'threads': len(E), 'windows': len(ws), 'shortest': [len(w[1]) for w in ws]}
        print(f'{label} c={c}: 실 {len(E)} · 창 {len(ws)} · 가장 짧은 우는 고리 {rows[c]["shortest"]}')
    return rows


def main():
    song = sf.load('hibari'); W, ns, unit, tt, ban = sf.features(song, **sf.DEF)
    pairs, sims, _ = sf.knn(W, sf.DEF['k'], sf.DEF['thr'], ban); T = len(W)
    real = summary(W, pairs, '실제')
    Ws, _, _, _, bans = sf.features(song, shuffle=7, **sf.DEF); ps, _, _ = sf.knn(Ws, sf.DEF['k'], sf.DEF['thr'], bans)
    ctrl = summary(Ws, ps, '대조(시각 뒤섞음)')

    S = next(s for s in json.load(open(os.path.join(ROOT, 'shape/data/shapes.json'), encoding='utf-8'))['songs'] if s['slug'] == 'hibari')
    assert S['T'] == T, (S['T'], T)
    X = np.array(S['pos'], float).reshape(T, 3) * S['scale']; RGB = np.array(S['rgb'], float).reshape(T, 3)
    NT = json.load(open(os.path.join(ROOT, 'shape/data/hibari.notes.json'), encoding='utf-8'))
    ev = {}
    for k in range(len(NT['node'])): ev.setdefault(NT['node'][k], []).append([NT['pitch'][k], min(NT['dur'][k], 900), NT['vel'][k], NT['voice'][k], NT['off'][k]])

    lab, cnt, succ = net(W, pairs); E = sorted(k for k, v in cnt.items() if v >= C_EXPORT); ws = windows(N, E)
    places = []
    for p in range(N):
        mem = np.where(lab == p)[0]; cen = W[mem].mean(0)
        voiced = [int(i) for i in mem if i in ev] or [int(mem[0])]
        rep = max(voiced, key=lambda i: float(W[i] @ cen))
        places.append({'n': int(len(mem)), 'xyz': np.round(X[mem].mean(0), 3).tolist(), 'spread': round(float(np.linalg.norm(X[mem] - X[mem].mean(0), axis=1).mean()), 3),
                       'rgb': np.round(RGB[mem].mean(0)).astype(int).tolist(), 'rep': rep, 'notes': ev.get(rep, []), 'members': mem.tolist()})
    Es = set(E); tri = [[a, b, c] for a, b in E for c in range(b + 1, N) if (a, c) in Es and (b, c) in Es]
    out = {'song': 'hibari', 'N': N, 'c': C_EXPORT, 'eighth_ms': round(60000 / 66 / 2, 3), 'places': places,
           'threads': [[a, b, cnt[(a, b)], succ.get((a, b), 0), succ.get((b, a), 0)] for a, b in E], 'membranes': tri,
           'windows': [{'rim': w[1], 'cocycle': [[u, v, x] for (u, v), x in w[0].items() if u < v and x]} for w in ws]}
    os.makedirs(os.path.join(ROOT, 'sketch/data'), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, 'sketch/data/relay_hibari.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    sp = [p['spread'] for p in places]
    chk = {'prediction': __doc__.split('PREDICTION')[1].split('한계')[0].strip(), 'real': real, 'control_shuffled_time': ctrl,
           'export': {'threads': len(E), 'membranes': len(tri), 'windows': len(ws), 'rims': [w[1] for w in ws]},
           'place_spread_median': float(np.median(sp)), 'body_radius': S['radius'],
           'R1': 2 <= real[2]['windows'] <= 8, 'R2': max(r['windows'] for r in real.values()) - min(r['windows'] for r in real.values()) <= 2,
           'R3': all(x <= 6 for x in real[2]['shortest']),
           'R4': ctrl[2]['windows'] > real[2]['windows'] and (max(r['windows'] for r in ctrl.values()) - min(r['windows'] for r in ctrl.values())) > 2}
    json.dump(chk, open(os.path.join(ROOT, 'docs/step3_data/relay_net_checks.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"내보냄: 자리 {N} · 실 {len(E)} · 막 {len(tri)} · 창 {len(ws)} · 자리 퍼짐 중앙 {np.median(sp):.2f} (몸 반지름 {S['radius']})")
    print({k: chk[k] for k in ('R1', 'R2', 'R3', 'R4')})


if __name__ == '__main__':
    main()
