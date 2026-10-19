"""
experiments/run_group_mdl.py — 곡마다 '가장 짧게 적는 군' 고르기(2번) · 정답을 아는 합성 곡에서 군 되찾기(3b) · 앞 절반 문법으로 뒤 절반 맞히기(3c).
(2026-10-19 사용자 프롬프트 2·3번. 3a(JKU 데이터)·3d(사람 시험)·1(악보·음원 대조)은 자료·사람이 필요해 여기서 하지 않는다.)

군 네 가지 (tools/group_grammar.py 의 cosiatec mode):
  time  시간 옮김만 (Zₙ — 같은 음높이로 되풀이)
  diat  시간 + 음계 자리 옮김 (온음계 Z₇ — 음높이를 곡의 장음계 자리 번호로 바꿔 옮김, 음계 밖 음은 낱말이 될 수 없다)
  chrom 시간 + 반음 옮김 (Z × Z)
  inv   chrom + 반전 p ↦ s − p (T/I)
길이(MDL 근사) L = Σ낱말 (음 수 + 옮김 수 + 반전 수) + 낱말 없이 남은 음 수 — 기호 하나를 같은 값으로 센다(근사, 좌표의 비트 수는 무시).
고르기: L 이 가장 작은 군, 1% 안이면 단순한 쪽(time < diat < chrom < inv).

사전 예측 (돌리기 전에 적음, 2026-10-19)
  M1 hibari 는 time 이 뽑힌다 (모든 되풀이가 같은 음높이 — 다른 군은 같거나 1% 안).
  M2 aqua · energy flow 는 옮김이 있는 군(diat·chrom·inv 중 최선)이 time 보다 L 을 10% 넘게 줄인다.
  M3 energy flow 는 diat 가 chrom 보다 짧다 (음계를 따라 내려가는 반복이라 반음 간격이 1·2 로 섞인다). aqua 는 예측하지 않는다.
  M4 반전(inv)은 세 곡 모두 chrom 보다 L 을 5% 넘게 줄이지 못한다 (이 곡들에 반전 되풀이는 드물다).
  S  (3b) 합성 곡: 참 군 네 가지 × 시드 10 — 각 참 군에서 MDL 이 참 군을 8/10 이상 고른다.
  H  (3c) 손마다 앞 절반 문법(chrom)의 옮김을 주기로 이어 뒤 절반을 맞힌다: hibari 재현율 ≥ 0.95 · aqua·energy flow 재현율 < 0.3 ·
     세 곡 모두 문법 정밀도 ≥ 대조(앞 절반 끝의 한 주기를 그대로 되풀이) 정밀도.

한계: L 은 기호 수 근사(좌표 크기·길이 정보 무시). 반전 후보는 횟수 상위만 본다. 합성 곡은 낱말 1개 + 잡음 10% 의 단순한 곡이다.
      예측(3c)은 같은 간격 되풀이를 잇는 규칙 하나뿐이다(곡의 큰 형식 — 반복 구간 A·B — 은 모른다).
산출: docs/step3_data/group_mdl.json
"""
import os, sys, json, time
import numpy as np
from collections import Counter
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'tools')]
import group_grammar as GG

ORDER = ['time', 'diat', 'chrom', 'inv']
SONGS = [('Ryuichi_Sakamoto_-_hibari.mid', 'hibari'), ('aqua-ryuichi-sakamoto-ryuichi-sakamoto.mid', 'aqua'), ('energy-flow-ryuichi-sakamoto.mid', 'energy flow')]

def length(D, mode, scale=None):
    """점 D(손 하나)를 군 mode 로 적은 길이 L 과 덮음."""
    D = np.asarray(D); extra = 0
    if mode == 'diat':
        D, out = GG.diatonic(D, scale); extra = len(out)
        words, rest = GG.cosiatec(D, mode='chrom')
    else:
        words, rest = GG.cosiatec(D, mode=mode)
    L = sum(len(w['P']) + len(w['T']) + len(w.get('I', [])) for w in words) + len(rest) + extra
    return L, words

def choose(Ls):
    best = min(Ls.values())
    return next(m for m in ORDER if Ls[m] <= best * 1.01)

def synth(true, seed, scale=(0, 2, 4, 5, 7, 9, 11)):
    """참 군 하나로 만든 곡: 낱말 8음 × 옮김 16 (+ inv 는 반을 반전) + 잡음 10%."""
    r = np.random.default_rng(seed); degs = [p for p in range(48, 85) if p % 12 in scale]; di = {p: i for i, p in enumerate(degs)}
    mt = np.sort(r.choice(16, 8, replace=False)); mp = r.choice(degs[5:-8], 8); P = list(zip(mt, mp)); pts = set()
    for k in range(16):
        t0 = 24 * k
        if true == 'time': q = [(t0 + t, p) for t, p in P]
        elif true == 'chrom': d = int(r.integers(-6, 7)); q = [(t0 + t, p + d) for t, p in P]
        elif true == 'diat': d = int(r.integers(-4, 5)); q = [(t0 + t, degs[min(max(di[p] + d, 0), len(degs) - 1)]) for t, p in P]
        else:
            if k % 2: s = 2 * 66 + int(r.integers(-6, 7)); q = [(t0 + t, s - p) for t, p in P]
            else: d = int(r.integers(-6, 7)); q = [(t0 + t, p + d) for t, p in P]
        pts |= set(q)
    n = len(pts)
    while len(pts) < int(n * 1.1): pts.add((int(r.integers(0, 24 * 16)), int(r.choice(degs))))
    return np.array(sorted(pts))

def extend(words, split, end):
    """앞 절반 문법 → 뒤 절반: 낱말마다 옮김의 가장 흔한 간격(Δt 차)과 그때의 Δp 차로 이어 간다."""
    pred = set()
    for w in words:
        T = sorted(w['T'])
        if len(T) < 2: continue
        gaps = Counter((b[0] - a[0], b[1] - a[1]) for a, b in zip(T, T[1:]))
        (gt, gp), _ = gaps.most_common(1)[0]
        if gt <= 0: continue
        ut, up = T[-1]
        while True:
            ut += gt; up += gp
            q = [(t + ut, p + up) for t, p in w['P']]
            if min(t for t, p in q) > end: break
            pred |= {(t, p) for t, p in q if split <= t <= end}
    return pred

def loop_baseline(first, split, end):
    """대조: 앞 절반에서 가장 흔한 '같은 음높이 시간 옮김' 주기 π 로, 앞 절반 끝 한 주기를 그대로 되풀이."""
    F = np.array(sorted(first)); dt = F[None, :, 0] - F[:, None, 0]; same = (F[None, :, 1] == F[:, None, 1]) & (dt >= 8)
    pi = Counter(dt[same].tolist()).most_common(1)[0][0]
    last = {(t, p) for t, p in first if t >= split - pi}; pred = set(); k = 1
    while True:
        q = {(t + k * pi, p) for t, p in last}
        if min(t for t, p in q) > end: break
        pred |= {(t, p) for t, p in q if split <= t <= end}; k += 1
    return pred, pi

if __name__ == '__main__':
    t0 = time.time(); out = {'songs': {}, 'synthetic': {}, 'half': {}}
    # ── 2: 곡마다 군 고르기 ──
    for f, name in SONGS:
        V = GG.voices(f); allp = [p for v in V for (t, p), d in v]; sc = GG.scale_of(allp)
        Ls = {m: 0 for m in ORDER}; cov = {}
        for v in V:
            D = np.array([k for k, _ in v])
            for m in ORDER:
                L, words = length(D, m, sc); Ls[m] += L
        n = sum(len(v) for v in V); ch = choose(Ls)
        out['songs'][name] = {'notes': n, 'scale_pcs': sc, 'L': Ls, 'compression': {m: round(n / Ls[m], 3) for m in ORDER}, 'chosen': ch}
        print(f'{name:12s} 음 {n} · 음계 {sc} · L ' + ' · '.join(f'{m} {Ls[m]}' for m in ORDER) + f' → {ch}', flush=True)
    # ── 3b: 합성 곡에서 군 되찾기 ──
    for true in ORDER:
        picks = []
        for seed in range(10):
            D = synth(true, 100 * ORDER.index(true) + seed); sc = list((0, 2, 4, 5, 7, 9, 11))
            Ls = {m: length(D, m, sc)[0] for m in ORDER}; picks.append(choose(Ls))
        out['synthetic'][true] = {'picks': picks, 'correct': picks.count(true)}
        print(f'합성 참 군 {true:5s}: 고른 군 {Counter(picks)} · 맞음 {picks.count(true)}/10', flush=True)
    # ── 3c: 앞 절반 → 뒤 절반 ──
    for f, name in SONGS:
        rec = []
        for h, v in enumerate(GG.voices(f)):
            pts = [k for k, _ in v]; end = max(t for t, p in pts); split = (min(t for t, p in pts) + end) // 2
            first = [(t, p) for t, p in pts if t < split]; second = {(t, p) for t, p in pts if t >= split}
            words, _ = GG.cosiatec(np.array(first), mode='chrom')
            g = extend(words, split, end); b, pi = loop_baseline(first, split, end)
            sc = lambda pr: (round(len(pr & second) / max(len(second), 1), 3), round(len(pr & second) / max(len(pr), 1), 3))
            rec.append({'hand': h, 'second_half_notes': len(second), 'grammar_recall_precision': sc(g), 'loop_recall_precision': sc(b), 'loop_period': int(pi)})
        out['half'][name] = rec
        print(f'{name:12s} 뒤 절반 맞히기 (재현율, 정밀도) 문법 ' + ' / '.join(str(r['grammar_recall_precision']) for r in rec) + ' · 대조 ' + ' / '.join(str(r['loop_recall_precision']) for r in rec), flush=True)
    S, H = out['songs'], out['half']
    best_tr = lambda s: min(S[s]['L'][m] for m in ('diat', 'chrom', 'inv'))
    out['verdict'] = {
        'M1': S['hibari']['chosen'] == 'time',
        'M2': all(best_tr(s) < 0.9 * S[s]['L']['time'] for s in ('aqua', 'energy flow')),
        'M3': S['energy flow']['L']['diat'] < S['energy flow']['L']['chrom'],
        'M4': all(S[s]['L']['inv'] > 0.95 * S[s]['L']['chrom'] for s in S),
        'S': all(v['correct'] >= 8 for v in out['synthetic'].values()),
        'H': all(r['grammar_recall_precision'][0] >= 0.95 for r in H['hibari']) and all(r['grammar_recall_precision'][0] < 0.3 for s in ('aqua', 'energy flow') for r in H[s])
             and all(r['grammar_recall_precision'][1] >= r['loop_recall_precision'][1] for s in H for r in H[s])}
    print('판정', out['verdict'], f'{time.time() - t0:.0f}s')
    out['script'] = 'experiments/run_group_mdl.py'
    json.dump(out, open(os.path.join(ROOT, 'docs', 'step3_data', 'group_mdl.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
