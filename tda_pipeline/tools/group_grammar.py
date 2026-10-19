"""
tools/group_grammar.py — 곡 = 손마다 '낱말(동기) + 옮김(군 원소)' 의 문법. 분해 · 다시 만들기 · 군 원소 적용 (2026-10-15 사용자:
  "hibari 두 손을 다른 획으로 나눠줘. group theory를 적용해 음악을 생성할 수 있도록, 표현할 수 있도록 하는 게 1순위").

점 = (시각, 음높이), 시각 단위 = 16분음표. 옮김 u = (Δ시각, Δ음높이) ∈ Z × Z. 낱말 P 와 옮김 집합 T 가 덮는 음 = P + T.
분해 = COSIATEC 최소 구현(Meredith 2002·2013; 파이썬 구현이 없다). 옮김으로 설명되지 않는 음 = rest (그대로 둔다).
길이(음가)는 점이 아니라 원곡에서 가져와 되풀이마다 붙인다(같은 낱말도 되풀이마다 길이가 조금씩 다르다 — aqua 13~31% 음). 옮겨도 길이는 따라간다.

군 원소를 곡에 적용 (문법 위에서, 음표가 아니라 옮김 집합을 바꾼다):
  shift(v, dt)            손 v 전체를 시간 옮김
  transpose(v, dp)        손 v 전체를 조옮김 (Z₁₂ 의 원소면 같은 음계류)
  invert(v, axis)         손 v 의 낱말을 음높이 축에 대해 뒤집기 (p → axis − p)
  reperiod(v, old, new)   손 v 의 '모듈 주기' 를 old → new 로: 옮김 t = t₀ + k·old + r  ↦  t₀ + k·new + r (k 번째 되풀이를 k 번째로 보내는 준동형)
                          hibari 왼손 66 → 64 면 두 손이 맞물려 어긋나지 않고(Z₃₂ × Z₃₂), 68 이면 모듈마다 두 박씩 어긋난다(Z₃₂ × Z₃₄).
"""
import os, sys, json, warnings
import numpy as np, pretty_midi
warnings.filterwarnings('ignore')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENC = 1000

def voices(f):
    """곡 → 손마다 [(시각, 음높이, 길이)] (16분). hibari 는 연구 전처리의 손 나누기(오른손 0박부터 · 왼손 33박부터, 8분 → ×2), 다른 곡은 MIDI 악기 순서(위 성부 먼저)."""
    if 'hibari' in f:
        sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments')]
        cwd = os.getcwd(); os.chdir(ROOT)
        import run_rings_h1_probe as P
        os.chdir(cwd)
        return [sorted({(2 * s, p): 2 * (e - s) for s, p, e in hand}.items()) for hand in P.piece(P.IDENT)]
    pm = pretty_midi.PrettyMIDI(os.path.join(ROOT, f)); q = pm.resolution / 4; out = []
    for ins in sorted([i for i in pm.instruments if not i.is_drum], key=lambda i: -np.mean([n.pitch for n in i.notes])):
        d = {}
        for n in ins.notes:
            s = round(pm.time_to_tick(n.start) / q); d[(s, n.pitch)] = max(d.get((s, n.pitch), 0), max(1, round(pm.time_to_tick(n.end) / q) - s))
        out.append(sorted(d.items()))
    return out

def tec(P, Dk):
    cand = Dk - (P[0, 0] * ENC + P[0, 1])
    for t, p in P[1:]: cand = cand[np.isin(cand + t * ENC + p, Dk)]
    return cand

def tec_inv(P, Dk):
    """반전 옮김 (Δt, s): 음 (t, p) ↦ (t + Δt, s − p). P 전체를 D 안으로 보내는 것 전부. 열쇠 = Δt·ENC + s (s ≥ 0)."""
    Dt, Dp = np.floor_divide(Dk + ENC // 2, ENC), None
    Dt = np.floor((Dk + ENC // 2) / ENC).astype(int); Dp = (Dk - Dt * ENC).astype(int)
    cand = (Dt - P[0, 0]) * ENC + (Dp + P[0, 1])
    for t, p in P[1:]:
        dt = np.floor_divide(cand, ENC); sv = cand - dt * ENC
        cand = cand[np.isin((t + dt) * ENC + (sv - p), Dk)]
    return cand

def cosiatec(D, K=60, stop=2.0, minp=5, mode='chrom'):
    """후보 옮김 = 자주 나는 K + 횟수×거리 K + 가장 멀리 뛰는 2K (멀리 뛰는 옮김 = 곡 앞머리만 남는 작은 낱말 × 많은 옮김).
       mode: 'time' = 시간 옮김만(Δ음높이 = 0) · 'chrom' = 시간 + 반음 옮김(Z × Z) · 'inv' = 여기에 반전(p ↦ s − p) 까지(T/I).
       음계 자리(온음계 Z₇)는 점의 음높이를 음계 자리 번호로 바꿔 'chrom' 으로 부른다 (diatonic())."""
    words, D = [], np.asarray(D).copy()
    while len(D) > 8:
        Dk = D[:, 0] * ENC + D[:, 1]
        dt, dp = D[None, :, 0] - D[:, None, 0], D[None, :, 1] - D[:, None, 1]
        m = (dt > 0) | ((dt == 0) & (dp > 0))
        if mode == 'time': m &= (dp == 0)
        v, c = np.unique(dt[m] * ENC + dp[m], return_counts=True)
        vt_all = np.floor((v + ENC // 2) / ENC); ok = np.where(c >= 4)[0]; best = None
        cands = [('T', k) for k in np.unique(np.r_[np.argsort(-c)[:K], ok[np.argsort(-(c[ok] * vt_all[ok]))][:K], ok[np.argsort(-vt_all[ok])][:2 * K]])]
        if mode == 'inv':
            sp = D[None, :, 1] + D[:, None, 1]; mi = (dt > 0) | ((dt == 0) & (dp != 0))
            vi, ci = np.unique(dt[mi] * ENC + sp[mi], return_counts=True); oki = np.where(ci >= 4)[0]
            cands += [('I', k) for k in np.unique(np.r_[np.argsort(-ci)[:K], oki[np.argsort(-(ci[oki] * (vi[oki] // ENC)))][:K]])]
        for kind_, k in cands:
            if kind_ == 'T':
                if c[k] < 3: continue
                vt = int(vt_all[k]); vp = int(v[k] - vt * ENC); P = D[np.isin(Dk + vt * ENC + vp, Dk)]   # MTP(v)
            else:
                if ci[k] < 3: continue
                vt = int(vi[k] // ENC); s_ = int(vi[k] - vt * ENC); P = D[np.isin((D[:, 0] + vt) * ENC + (s_ - D[:, 1]), Dk)]
            if len(P) < minp: continue
            T = tec(P, Dk)
            if mode == 'time': T = T[(T - np.floor((T + ENC // 2) / ENC) * ENC) == 0]
            Pk = P[:, 0] * ENC + P[:, 1]; cov = (Pk[:, None] + T[None, :]).ravel()
            I = tec_inv(P, Dk) if mode == 'inv' else np.array([], int)
            if len(I):
                idt = np.floor_divide(I, ENC); isv = I - idt * ENC
                cov = np.r_[cov, ((P[:, 0][:, None] + idt[None]) * ENC + (isv[None] - P[:, 1][:, None])).ravel()]
            cov = np.unique(cov); cr = len(cov) / (len(P) + len(T) + len(I) - 1)
            if best is None or cr > best[0]: best = (cr, P, T, I, cov)
        if best is None or best[0] < stop: break
        cr, P, T, I, cov = best
        Tt = np.floor((T + ENC // 2) / ENC).astype(int); Tp = (T - Tt * ENC).astype(int)
        w = {'P': P.tolist(), 'T': sorted(zip(Tt.tolist(), Tp.tolist())), 'cover': int(len(cov)), 'cr': round(float(cr), 2)}
        if len(I): idt = np.floor_divide(I, ENC); w['I'] = sorted(zip(idt.tolist(), (I - idt * ENC).tolist()))
        words.append(w)
        D = D[~np.isin(Dk, cov)]
    return words, D.tolist()

def scale_of(ps):
    """음높이들 → 가장 많은 음을 덮는 장음계(7음) 음이름 집합."""
    pc = np.bincount(np.asarray(ps) % 12, minlength=12); major = np.array([0, 2, 4, 5, 7, 9, 11])
    r = max(range(12), key=lambda r: pc[(major + r) % 12].sum()); return sorted(((major + r) % 12).tolist())

def diatonic(D, scale):
    """(t, p) → (t, 음계 자리 번호). 음계 밖의 음은 따로 돌려준다 (음계 자리 군으로는 옮길 수 없다)."""
    deg = {}; k = 0
    for p in range(0, 128):
        if p % 12 in scale: deg[p] = k; k += 1
    D = np.asarray(D); inn = np.array([p in deg for p in D[:, 1]])
    return np.c_[D[inn, 0], [deg[p] for p in D[inn, 1]]], D[~inn]

def decompose(f, mode='chrom'):
    """곡 → 문법: 손마다 낱말 목록(낱말 음에 길이를 붙인다) + 남은 음."""
    g = {'source': f, 'unit': '16분음표', 'voices': []}
    for notes in voices(f):
        dur = dict(notes); D = np.array([k for k, _ in notes]); words, rest = cosiatec(D, mode=mode)
        for w in words:
            w['durs'] = [[dur[(t + ut, p + up)] for t, p in w['P']] for ut, up in w['T']]   # 되풀이마다 길이(같은 낱말도 길이는 조금씩 다르다)
            if 'I' in w: w['idurs'] = [[dur[(t + ut, s_ - p)] for t, p in w['P']] for ut, s_ in w['I']]
        g['voices'].append({'notes': len(D), 'words': words, 'rest': [[t, p, dur[(t, p)]] for t, p in rest]})
    return g

def realize(g):
    """문법 → 손마다 [(시각, 음높이, 길이)]. 같은 (시각, 음높이) 는 하나로."""
    out = []
    for v in g['voices']:
        d = {}
        for w in v['words']:
            for (ut, up), ds in zip(w['T'], w['durs']):
                for (t, p), du in zip(w['P'], ds): d[(t + ut, p + up)] = max(d.get((t + ut, p + up), 0), du)
            for (ut, s_), ds in zip(w.get('I', []), w.get('idurs', [])):
                for (t, p), du in zip(w['P'], ds): d[(t + ut, s_ - p)] = max(d.get((t + ut, s_ - p), 0), du)
        for t, p, du in v['rest']: d[(t, p)] = max(d.get((t, p), 0), du)
        out.append(sorted((t, p, du) for (t, p), du in d.items() if t >= 0 and 21 <= p <= 108))
    return out

def _map(g, v, fw=None, fT=None, frest=None):
    g = json.loads(json.dumps(g)); V = g['voices'][v]
    for w in V['words']:
        if fw: w['P'] = [list(x) for x in fw(np.array(w['P'])).tolist()]
        if fT: w['T'] = [tuple(x) for x in fT(np.array(w['T'])).tolist()]
    if frest and V['rest']: V['rest'] = [list(x) for x in frest(np.array(V['rest'])).tolist()]
    return g

def shift(g, v, dt):
    return _map(g, v, fT=lambda T: T + [dt, 0], frest=lambda R: R + [dt, 0, 0])

def transpose(g, v, dp):
    return _map(g, v, fT=lambda T: T + [0, dp], frest=lambda R: R + [0, dp, 0])

def invert(g, v, axis):
    return _map(g, v, fw=lambda P: np.c_[P[:, 0], axis - P[:, 1]], fT=lambda T: np.c_[T[:, 0], -T[:, 1]],
                frest=lambda R: np.c_[R[:, 0], axis - R[:, 1], R[:, 2]])

def reperiod(g, v, old, new, t0=None):
    """k 번째 되풀이 → k 번째 되풀이 (주기만 old → new). t0 = 손이 시작하는 시각 (기본: 그 손의 가장 이른 음)."""
    if t0 is None:
        t0 = min([min(t for t, p in w['P']) + min(u for u, _ in w['T']) for w in g['voices'][v]['words']] + [r[0] for r in g['voices'][v]['rest']])
    def ft(t):
        k, r = np.divmod(np.asarray(t) - t0, old); return t0 + k * new + r
    g2 = json.loads(json.dumps(g)); V = g2['voices'][v]
    for w in V['words']:
        base = min(t for t, p in w['P']); w['T'] = [(int(ft(base + ut) - base), up) for ut, up in w['T']]
    if V['rest']: V['rest'] = [[int(ft(t)), p, d] for t, p, d in V['rest']]
    return g2

def to_midi(notes_by_voice, path, sec16=60 / 66 / 4):
    """16분음표 하나 = sec16 초 (hibari 원곡: 8분 1089개 ≈ 494초 → 8분 = 60/132 초)."""
    pm = pretty_midi.PrettyMIDI()
    for k, notes in enumerate(notes_by_voice):
        ins = pretty_midi.Instrument(0, name=['RH', 'LH'][k] if k < 2 else f'v{k}')
        for t, p, d in notes: ins.notes.append(pretty_midi.Note(velocity=72 if k == 0 else 64, pitch=int(p), start=t * sec16, end=(t + d) * sec16))
        pm.instruments.append(ins)
    pm.write(path)
