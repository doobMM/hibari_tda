"""run_life_mi.py — 살아 있는 격자(3판)의 조작이 "먹히나" 를 상호정보량으로 잰다 (docs/tonnetz_lenia_spec.md §10.5)

원자료: `node tools/verify_life.mjs X1|X2|X3|X4` → docs/step3_data/life_raw_X*.json
채점기(이 파일)는 **원자료를 보기 전에** 쓴다. 판정은 `run_knob_mi.analyse` / `ceilings` 그대로 쓴다
(순열 귀무를 뺀 MI_adj, 방향 = Spearman ρ, 천장 = 완벽한 계단을 **같은 경로로** 통과시킨 값 — 2026-09-05 교훈).
표본이 작아(눈금당 20) 구간 수만 8 로 줄인다. 천장도 같은 구간 수로 구한다.

왜 JS 가 아닌가: JS 는 "닮음" 을 잰다. 여기서 묻는 것은 "내 조작이 출력을 바꾸나" = 의존성이다 (spec §10.4).

PREDICTION (실행 전, spec §10.5)
  X1  몰기 방향(4) → 이동 방향: MI_adj/천장 ≥ 0.5, 순열 p < 0.01, 목표 ±45° 적중 ≥ 70%
  X2  rate(4) → 찾은 고리 수: p < 0.01, |ρ| ≥ 0.5 · rate → 음높이 평균: 귀무와 구별되지 않는다(p ≥ 0.05)
  X3  가중치(실제/섞음) → 지나간 칸: 특징 3개(검은 건반 비율·음높이 평균·가장 많이 머문 음이름) 중 하나라도 Holm p < 0.05
  X4  방치 20/20 이 5분 안에 사그라진다 · 돌봄 ≥ 16/20 이 5분을 산다

2회차 (spec §10.9, 실행 전) — X1b·X2b·X4b 는 위와 같다. X3b(메커니즘):
  칸을 옮길 때의 전이 점수(실제 intra_right, 0 = 무작위 이웃) — 같은 시드 짝지음, Wilcoxon 한쪽(실제 > 끔, 실제 > 섞음), Holm p < 0.05 둘 다.
  원래 특징 3개(실제 vs 섞음)는 귀무 예측(Holm p ≥ 0.05). 실제 팔 2분 생존 ≥ 17/20.

산출: docs/step3_data/life_mi.json (2회차) · `python experiments/run_life_mi.py life_raw_r1_` → life_mi_r1.json (1회차)
"""
import json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'experiments'))
import run_knob_mi as K

K.NBINS = 8
SRC = os.path.join(ROOT, 'docs', 'step3_data')
PRE = sys.argv[1] if len(sys.argv) > 1 else 'life_raw_'          # 1회차: life_raw_r1_
OUT = 'life_mi.json' if PRE == 'life_raw_' else 'life_mi_' + PRE.replace('life_raw_', '').strip('_') + '.json'

def load(x):                                       # 나눠 돌린 조각(life_raw_X2_0.json …)도 모은다
    import glob
    fs = sorted(glob.glob(os.path.join(SRC, f'{PRE}{x}.json')) + glob.glob(os.path.join(SRC, f'{PRE}{x}_*.json'))
                + glob.glob(os.path.join(SRC, f'{PRE}{x}h[0-9].json')))                  # 반씩 나눈 조각(…X1h0.json)
    if not fs: return None
    rows = []
    for f in fs: rows += json.load(open(f, encoding='utf8'))['rows']
    return {'rows': rows, 'files': [os.path.basename(f) for f in fs]}

def mi(levels, lv, y):
    ok = np.array([v is not None for v in y])
    lv, y = np.asarray(lv)[ok], np.asarray([v for v in y if v is not None], float)
    r = K.analyse(levels, lv, y)
    n_per = int(np.bincount(lv).min()) if len(lv) else 0
    _, ceil = K.ceilings(levels, max(1, n_per))
    r['ceiling_mi'] = ceil
    r['frac_of_ceiling'] = r['mi_adj'] / ceil if ceil > 0 else None
    r['n'] = int(len(y))
    return r

def holm(ps):
    order = np.argsort(ps); out = [None] * len(ps); m = len(ps); run = 0
    for i, j in enumerate(order):
        run = max(run, (m - i) * ps[j]); out[j] = min(1.0, run)
    return out

res = {'script': 'experiments/run_life_mi.py ' + PRE, 'nbins': K.NBINS, 'nperm': K.NPERM}
d = load('X1')
if d:
    rows = d['rows']
    lv = [r['dir'] for r in rows]; ang = [r['angle'] for r in rows]
    r1 = mi([0, 1, 2, 3], lv, ang)
    errs = [abs(r['err']) for r in rows if r['err'] is not None]
    res['X1'] = {'mi': r1, 'hit_45': float(np.mean([e <= 45 for e in errs])) if errs else None,
                 'median_abs_err_deg': float(np.median(errs)) if errs else None, 'alive': sum(r['alive'] for r in rows), 'n': len(rows),
                 'pass': bool(r1['perm_p'] < 0.01 and (r1['frac_of_ceiling'] or 0) >= 0.5 and errs and np.mean([e <= 45 for e in errs]) >= 0.7)}
d = load('X2')
if d:
    rows = d['rows']; rates = sorted({r['rate'] for r in rows}); lv = [rates.index(r['rate']) for r in rows]
    rf = mi(list(range(len(rates))), lv, [r['found'] for r in rows])
    rp = mi(list(range(len(rates))), lv, [r['meanPitch'] for r in rows])
    res['X2'] = {'found': rf, 'meanPitch': rp,
                 'found_by_rate': {str(rt): [r['found'] for r in rows if r['rate'] == rt] for rt in rates},
                 'pass_found': bool(rf['perm_p'] < 0.01 and abs(rf['spearman_rho']) >= 0.5),
                 'pass_pitch_null': bool(rp['perm_p'] >= 0.05)}
d = load('X3')
if d:
    rows = d['rows']; lv = [r['shuffled'] for r in rows]
    feats = {'blackFrac': [r['blackFrac'] for r in rows], 'meanPitch': [r['meanPitch'] for r in rows],
             'topPC': [int(np.argmax(r['pcMass'])) if r['pcMass'] else None for r in rows]}
    out = {k: mi([0, 1], lv, v) for k, v in feats.items()}
    hp = holm([out[k]['perm_p'] for k in feats])
    for k, h in zip(feats, hp): out[k]['holm_p'] = h
    res['X3'] = {**out, 'pass': bool(min(hp) < 0.05)}
d = load('X3b')
if d:
    from scipy import stats
    rows = d['rows']; by = {a: {r['seed']: r for r in rows if r['arm'] == a} for a in ('real', 'shuf', 'off')}
    def paired(a, b):
        ks = [k for k in by[a] if k in by[b] and by[a][k]['score'] is not None and by[b][k]['score'] is not None]
        x = np.array([by[a][k]['score'] for k in ks]); y = np.array([by[b][k]['score'] for k in ks])
        w = stats.wilcoxon(x, y, alternative='greater') if len(ks) >= 5 else None
        return {'n_pairs': len(ks), 'mean_a': float(x.mean()) if len(ks) else None, 'mean_b': float(y.mean()) if len(ks) else None,
                'a_gt_b': int((x > y).sum()), 'wilcoxon_p': float(w.pvalue) if w else None}
    ro, rs_ = paired('real', 'off'), paired('real', 'shuf')
    hp2 = holm([ro['wilcoxon_p'], rs_['wilcoxon_p']]); ro['holm_p'], rs_['holm_p'] = hp2
    sub = [r for r in rows if r['arm'] in ('real', 'shuf')]; lv = [0 if r['arm'] == 'real' else 1 for r in sub]
    feats = {'blackFrac': [r['blackFrac'] for r in sub], 'meanPitch': [r['meanPitch'] for r in sub],
             'topPC': [int(np.argmax(r['pcMass'])) if r['pcMass'] and sum(r['pcMass']) > 0 else None for r in sub]}
    fo = {k: mi([0, 1], lv, v) for k, v in feats.items()}
    hp3 = holm([fo[k]['perm_p'] for k in feats])
    for k, h in zip(feats, hp3): fo[k]['holm_p'] = h
    alive = {a: f"{sum(r['alive'] for r in by[a].values())}/{len(by[a])}" for a in by}
    res['X3b'] = {'real_vs_off': ro, 'real_vs_shuf': rs_, 'features_real_vs_shuf': fo, 'alive_2min': alive,
                  'mean_score': {a: float(np.mean([r['score'] for r in by[a].values() if r['score'] is not None])) for a in by},
                  'pass_mechanism': bool(ro['holm_p'] < 0.05 and rs_['holm_p'] < 0.05),
                  'pass_features_null': bool(min(hp3) >= 0.05),
                  'pass_alive': bool(sum(r['alive'] for r in by['real'].values()) >= 17)}
d = load('X4')
if d:
    rows = d['rows']
    neg = [r for r in rows if r['care'] == 0]; care = [r for r in rows if r['care'] == 1]
    res['X4'] = {'neglect_quiet_5min': f"{sum(not r['alive5min'] for r in neg)}/{len(neg)}",
                 'care_alive_5min': f"{sum(r['alive5min'] for r in care)}/{len(care)}",
                 'neglect_died_beat': sorted([r['died'] for r in neg if r['died'] is not None]),
                 'pass': bool(sum(not r['alive5min'] for r in neg) == len(neg) and sum(r['alive5min'] for r in care) >= 16)}
json.dump(res, open(os.path.join(SRC, OUT), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print('→', OUT)
for k, v in res.items():
    if isinstance(v, dict): print(k, json.dumps({a: (b if not isinstance(b, dict) else {c: b[c] for c in ('mi_adj', 'frac_of_ceiling', 'perm_p', 'spearman_rho', 'holm_p') if c in b}) for a, b in v.items()}, ensure_ascii=False)[:900])
