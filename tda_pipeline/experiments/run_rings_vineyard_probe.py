"""
run_rings_vineyard_probe.py — run_rings_h1_probe.py 와 같은 판 73개를, 정본 rate 쓸기를 **vineyard** 로 보고 다시 잰다.

왜 다시 재나 (2026-10-07 사용자): "수학적인 계산을 수행할 때 brute force로 임하지 말고 github이나 논문 개제 사이트에서
최신 연구결과를 참고해서 항상 최단거리를 추구하는 버릇을 들이도록 해."
  - 앞 탐침은 정본 번들(build_overlap_bundle)을 판마다 통째로 돌렸다 — 병목은 topology.generate_barcode_numpy(pHcol, rate 151번 ≈ 5.4초/판),
    거리 계산은 151번 0.18초뿐이었다. 같은 행렬에서 ripser 는 151번 0.08초에 **같은 막대**를 낸다(확인함).
  - 고리 대표(음 집합)를 맞대는 비교는 불안정하다(대표는 유일하지 않다) — 바코드끼리의 Wasserstein 거리는 안정성 정리가 있다
    (Cohen-Steiner·Edelsbrunner·Harer 2007; 폴더의 Arulandu 외 2026 『Through the Grapevine』 정리 1·명제 2).
  - 정본의 rate 0→1.5 쓸기는 판 하나에서 같은 꼭짓점(음) 위의 거리 함수 족 = **vineyard**(Cohen-Steiner·Edelsbrunner·Morozov 2006, 폴더의 1137856.1137877.pdf).
    Arulandu 외의 vineyard distance(정의 6: 덩굴 길이의 합, 식 (2): 이웃한 바코드 사이 거리의 합)는 **같은 복합체 위의 족**에 정의된다 →
    판끼리는 음 집합이 달라 그대로 못 쓰고, 판 하나의 rate 쓸기에는 그대로 쓸 수 있다.

잰 것
  IW  = rate 151점에서 hibari 바코드와 이 판 바코드의 1-Wasserstein(persim, L∞ 바닥 거리) 평균 — '같은 rate 끼리 맞댄 두 vineyard 의 거리'.
        (Arulandu 외의 vineyard distance 가 아니다 — 그건 두 판 사이를 잇는 호모토피가 필요하다. 그들의 하한(persistence distance)을 rate 로 평균한 쪽에 가깝다)
  VL  = 이 판 자신의 rate vineyard 길이 Σ W(dgm(r_i), dgm(r_{i+1})) — Arulandu 외 식 (2) 의 균등 가중 근사(rate 0.01 간격). 'rate 를 올릴 때 위상이 얼마나 움직이나'.
  BOT = 같은 rate 끼리 bottleneck 거리의 평균.
  막대 = ripser H₁ (정본 pHcol 과 같은 막대 — 아래 V0 에서 다 맞춘 판으로 다시 확인).

사전 예측 (돌리기 전에 적음, 2026-10-07)
  V0  다 맞춘 판: IW = 0, 그리고 rate 151점 모두 ripser 막대 = 정본 pHcol 막대 (소수 6자리).
  V1  IW 중앙값이 수와 함께 커진다: 원 한 번 < 3수 < 10수 < 30수, 그리고 30수 ≥ 54개 섞기 중앙값의 0.8 배 (바닥에 다가간다).
      — 앞 탐침의 P2(남은 정확한 고리 수)는 10수에서 0 바닥에 붙어 실패했다. 막대 거리는 바닥에 붙지 않으리라 본다.
  V2  (탐색) 원 한 번의 IW 중앙값 < 무작위 칸 12개 섞기의 IW 중앙값.
  V3  두 잣대가 같은 쪽: IW 와 앞 탐침의 '닮음'(soft_keep) 스피어만 ρ < −0.5 (다 맞춘 판 뺀 72판).
  V4  판 73개 전부 한 프로세스에서 60초 안에 (앞 탐침: 일곱 프로세스 561초).

한계
  - IW 는 바코드 모양만 본다 — 어느 음이 고리를 이루는지(대표)는 버린다. 판 위에 고리를 그리려면 대표가 필요하다
    (빠른 정확한 대표: Čufar·Virk 2023 involuted PH, Ripserer.jl — 여기서는 쓰지 않는다).
  - 귀로 들리는가는 여전히 재지 않는다.

산출: docs/step3_data/rings_vineyard_probe.json
"""
import sys, os, io, json, time, contextlib, datetime
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments')]
os.chdir(ROOT)
import run_rings_h1_probe as P                       # 판·전처리·곡 만들기를 그대로 (main 은 돌지 않는다)
from ripser import ripser
from persim import wasserstein, bottleneck
from scipy.stats import spearmanr
suite = P.suite
RATES = []
rate = 0.0
while rate <= 1.5 + 1e-10:                           # 정본 번들과 같은 루프
    RATES.append(round(rate, 2)); rate += 0.01

def mats(st):
    d = P.data_from(*P.piece(st))
    inter = suite.compute_inter_weights(d['adn_i'][1][1], d['adn_i'][2][1], num_chords=d['num_chords'], lag=1)
    oor = suite.compute_out_of_reach(inter, power=-2)
    mus = suite.metric_distance_matrix(d['notes_label'], P.CFG['metric'], P.CFG['octave_weight'], P.CFG['duration_weight'])
    for r in RATES:
        fd = suite.compute_distance_matrix(d['intra'] + r * inter, d['notes_dict'], oor, num_notes=d['num_notes']).values
        yield r, np.asarray(suite.compute_hybrid_distance(fd, mus, alpha=P.CFG['alpha']), float)

def dgms(st):
    out, inf = [], 0
    for r, M in mats(st):
        D = ripser(M, maxdim=1, distance_matrix=True)['dgms'][1]
        inf += int(np.isinf(D[:, 1]).sum()); out.append(D[np.isfinite(D[:, 1])])
    return out, inf

def W(a, b):
    return 0.0 if len(a) == 0 and len(b) == 0 else float(wasserstein(a, b))
def Bn(a, b):
    return 0.0 if len(a) == 0 and len(b) == 0 else float(bottleneck(a, b))

if __name__ == '__main__':
    t0 = time.time()
    H, hinf = dgms(P.IDENT)
    # V0: 다 맞춘 판에서 ripser 막대 = 정본 pHcol 막대 (rate 151점 전부)
    same = 0
    for (r, M), D in zip(mats(P.IDENT), H):
        a = P.suite.generate_barcode_numpy(mat=M, listOfDimension=[1], exactStep=True, birthDeathSimplex=False, sortDimension=False)
        A = sorted((round(float(e[1][0]), 6), round(float(e[1][1]), 6)) for e in a if e[0] == 1 and e[1][1] != 'infty')
        B = sorted((round(float(x), 6), round(float(y), 6)) for x, y in D)
        same += A == B
    t1 = time.time()
    hl = sum(W(H[i], H[i + 1]) for i in range(len(H) - 1))
    print(f'V0 ripser = pHcol {same}/{len(RATES)} rate · hibari VL={hl:.4f} · 무한 막대 {hinf} · {t1 - t0:.1f}s (pHcol 대조 포함)', flush=True)

    prev = {r['tag']: r for r in json.load(open(os.path.join(ROOT, 'docs', 'step3_data', 'rings_h1_probe.json'), encoding='utf8'))['rows']}
    rows, t2 = [], time.time()
    for st, tag, kw in P.make_jobs():
        S, inf = dgms(st)
        iw = float(np.mean([W(a, b) for a, b in zip(H, S)])); bt = float(np.mean([Bn(a, b) for a, b in zip(H, S)]))
        vl = sum(W(S[i], S[i + 1]) for i in range(len(S) - 1))
        rec = {'tag': tag, 'group': kw.get('group', 'solved'), 'IW': round(iw, 5), 'BOT': round(bt, 5), 'VL': round(vl, 4), 'inf_bars': inf,
               'bars_mean': round(float(np.mean([len(x) for x in S])), 2), 'soft_keep': prev.get(tag, {}).get('soft_keep'),
               'kept': prev.get(tag, {}).get('kept'), 'steps_changed': prev.get(tag, {}).get('steps_changed')}
        rows.append(rec)
        print(f"  {tag:14s} IW={rec['IW']:.4f} BOT={rec['BOT']:.4f} VL={rec['VL']:.3f} 막대{rec['bars_mean']:5.1f} 닮음{rec['soft_keep']}", flush=True)
    t3 = time.time()

    def med(g, k='IW'):
        v = [r[k] for r in rows if r['group'] == g]; return float(np.median(v)) if v else None
    G = ('single', 'walk2', 'walk3', 'walk5', 'walk10', 'walk30', 'rand12', 'rand54')
    MI = {g: med(g) for g in G}
    nz = [r for r in rows if r['tag'] != 'solved' and r['soft_keep'] is not None]
    rho, pv = spearmanr([r['IW'] for r in nz], [r['soft_keep'] for r in nz])
    rho_s, pv_s = spearmanr([r['IW'] for r in nz], [r['steps_changed'] for r in nz])
    solved = next(r for r in rows if r['tag'] == 'solved')
    VERDICT = {
        'V0': {'pass': solved['IW'] == 0 and same == len(RATES), 'ripser_eq_phcol': f'{same}/{len(RATES)}', 'IW_solved': solved['IW']},
        'V1': {'pass': bool(MI['single'] < MI['walk3'] < MI['walk10'] < MI['walk30'] and MI['walk30'] >= 0.8 * MI['rand54']), 'medians_IW': MI},
        'V2': {'pass': MI['single'] < MI['rand12'], 'single': MI['single'], 'rand12': MI['rand12'], 'note': '탐색'},
        'V3': {'pass': bool(rho < -0.5), 'spearman_IW_softkeep': round(float(rho), 4), 'p': float(pv), 'n': len(nz),
               'spearman_IW_steps_changed (사후)': round(float(rho_s), 4)},
        'V4': {'pass': (t3 - t2) < 60, 'seconds_73_states': round(t3 - t2, 1), 'h1_probe_seconds_7proc': 561},
    }
    for k, v in VERDICT.items(): print(k, 'PASS' if v['pass'] else 'FAIL', {a: b for a, b in v.items() if a != 'pass'})
    POST = {g: {'BOT': med(g, 'BOT'), 'VL': med(g, 'VL'), 'bars': med(g, 'bars_mean')} for g in G}
    print('사후(중앙값) hibari VL', round(hl, 4), json.dumps(POST, ensure_ascii=False))
    ring = {}
    for r in rows:
        if r['group'] == 'single': ring.setdefault(r['tag'].split()[1][:2], []).append(r['IW'])
    print('원마다 IW (k=1·2·3):', {k: v for k, v in ring.items()})
    out = {'script': 'experiments/run_rings_vineyard_probe.py', 'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
           'config': P.CFG, 'rates': [RATES[0], RATES[-1], len(RATES)], 'hibari_VL': round(hl, 4), 'verdict': VERDICT,
           'posthoc_medians': POST, 'rows': rows,
           'refs': ['Cohen-Steiner, Edelsbrunner, Morozov (2006) Vines and vineyards by updating persistence in linear time',
                    'Arulandu, Gottschalk, Payne, Richardson, Weighill (2026) Through the Grapevine: vineyard distance, arXiv:2510.24472',
                    'Piekenbrock, Perea (2024) Move schedules, JACT 8:301-345',
                    'Bauer (2021) Ripser — ripser.py 0.6.14 / persim 0.3.8']}
    json.dump(out, open(os.path.join(ROOT, 'docs', 'step3_data', 'rings_vineyard_probe.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print('저장 docs/step3_data/rings_vineyard_probe.json', f'{time.time() - t0:.0f}s')
