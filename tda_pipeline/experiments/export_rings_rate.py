"""
experiments/export_rings_rate.py — rate 를 바꿀 때 고리판의 원 9개가 hibari 의 모양을 각각 얼마나 흔드는가 (2026-10-08 사용자):
  "그 rate를 조절할 때 9개의 원에 나타나는 영향도 시각적으로 표현되었으면 좋겠다."

run_rings_vineyard_probe.py 는 rate 151점의 바코드 거리를 **평균(IW)** 으로만 남겼다. 여기서는 평균하지 않고 rate 마다 남긴다.
  판      다 맞춘 판(= hibari) 과, 원 하나를 k 사분(1·2·3) 돌린 판 27개.
  rate r  정본과 같은 거리 — intra(같은 손 다음 박의 다른 화음) + r × inter(다른 손 한 박 뒤 화음) → 역수 거리 → 25% 옥타브·길이 거리와 섞음(각각 [0,1] 정규화).
          그래서 r 이 달라도 거리의 눈금은 같다(compute_hybrid_distance 가 rate 마다 [0,1] 로 맞춘다) → rate 끼리 W 를 견줄 수 있다.
  W(r)    같은 r 에서 hibari H₁ 바코드와 돌린 판 H₁ 바코드의 1-Wasserstein (ripser + persim — run_rings_vineyard_probe.py 와 같은 함수).
  bars    rate 마다 hibari 와 각 판의 유한 H₁ 막대 [태어남, 죽음] — 페이지에서 두 모양을 겹쳐 그린다.

사전 예측 (돌리기 전에 적음, 2026-10-08)
  R0  (정합) 원마다 W(r) 의 rate 평균 = rings_vineyard_probe.json 의 IW (소수 4자리).
  R1  원의 순위가 rate 에 따라 바뀐다: rate 0 과 rate 1.5 에서 원 9개를 W(사분 1·2·3 평균)로 줄 세운 두 순위의 켄달 τ < 0.8.
      — 근거는 약하다(탐색). rate 0 은 같은 손의 이어짐만, rate 1.5 는 다른 손 한 박 뒤를 크게 본다. 허리 원(베이스)과 꽃잎 원이 두 관계를 다르게 흔들 수 있다.
  R2  (탐색, 판정 없음) 어느 원의 W 가 rate 와 함께 가장 크게 변하나.

한계
  - 다 맞춘 판에서 원 하나만 돌린 경우뿐 — 여러 번 돌린 판에서 원의 영향은 다르다(페이지는 '다 맞춘 판에서 이 원을 돌리면' 으로만 보인다).
  - 바코드 모양만 본다(어느 음이 고리인가는 버린다). 귀로 들리는가는 재지 않는다.

산출: sketch/rings-rate.json (페이지 sketch/rings-rate.html 이 읽는다)
"""
import sys, os, json, time, datetime
import numpy as np
from scipy.stats import kendalltau

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments')]
os.chdir(ROOT)
import run_rings_h1_probe as P
import run_rings_vineyard_probe as V

if __name__ == '__main__':
    t0 = time.time()
    H, _ = V.dgms(P.IDENT)
    W, bars = {}, {'hibari': [np.round(d, 4).tolist() for d in H]}
    for ring in range(9):
        for k in (1, 2, 3):
            S, _ = V.dgms(P.turn(P.IDENT, ring, k))
            W[f'{ring}:{k}'] = [round(V.W(a, b), 5) for a, b in zip(H, S)]
            bars[f'{ring}:{k}'] = [np.round(d, 4).tolist() for d in S]
    print(f'{len(W)} 판 × {len(V.RATES)} rate · {time.time() - t0:.0f}s')

    prev = {r['tag']: r['IW'] for r in json.load(open(os.path.join(ROOT, 'docs', 'step3_data', 'rings_vineyard_probe.json'), encoding='utf8'))['rows']}
    r0 = [(t, round(float(np.mean(v)), 4), round(prev[f'single r{t[0]}k{t[2]}'], 4)) for t, v in W.items()]
    mean = np.array([[np.mean([W[f'{g}:{k}'][i] for k in (1, 2, 3)]) for i in range(len(V.RATES))] for g in range(9)])   # 원 × rate
    tau = float(kendalltau(mean[:, 0], mean[:, -1])[0])
    swing = {g: round(float(mean[g].max() - mean[g].min()), 4) for g in range(9)}
    VERDICT = {'R0': {'pass': all(a == b for _, a, b in r0), 'mismatch': [x for x in r0 if x[1] != x[2]]},
               'R1': {'pass': tau < 0.8, 'kendall_tau_r0_vs_r15': round(tau, 3),
                      'rank_r0': [int(g) for g in np.argsort(-mean[:, 0])], 'rank_r15': [int(g) for g in np.argsort(-mean[:, -1])]},
               'R2': {'swing_max_minus_min': swing, 'note': '탐색'}}
    for k, v in VERDICT.items(): print(k, 'PASS' if v.get('pass', True) else 'FAIL', {a: b for a, b in v.items() if a != 'pass'})
    for g in range(9):
        print(f'  원 {g}: r=0 {mean[g, 0]:.3f} · 0.5 {mean[g, 50]:.3f} · 1.0 {mean[g, 100]:.3f} · 1.5 {mean[g, -1]:.3f} · 최대 {mean[g].max():.3f} (r={V.RATES[int(mean[g].argmax())]})')
    print('hibari 막대 수 r=0/0.5/1.0/1.5:', [len(H[i]) for i in (0, 50, 100, 150)])
    out = {'script': 'experiments/export_rings_rate.py', 'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
           'config': P.CFG, 'rates': V.RATES, 'W': W, 'bars': bars, 'verdict': VERDICT}
    path = os.path.join(ROOT, 'sketch', 'rings-rate.json')
    json.dump(out, open(path, 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
    print('저장', path, f'{os.path.getsize(path) / 1024:.0f} KB')
