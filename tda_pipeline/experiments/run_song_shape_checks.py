"""
run_song_shape_checks.py — "곡의 모양"(song_fold.py) 이 곡을 담는지, 아무 자료나 넣어도 나오는 그림인지 잰다.

⚠ 상태: song_fold.py 의 매개변수는 13곡 미리보기를 **눈으로 보고** 골랐다(탐색). 아래 예측은 이 스크립트를 돌리기 **전에** 적었다(2026-09-30).
   이미 본 것 — 시드 0 의 13곡 모양, 곡별 rec80, hibari 의 자리바꿈 짝 5개 모듈(2·5·8·12·15)의 중앙 지연.
   아직 안 본 것 — 시드 사이 안정성, 시간 섞기 대조군, 매개변수 민감도, 모듈 전체의 자리바꿈 짝.

PREDICTION
  P1 안정성      같은 곡을 초기 잡음만 달리해 다시 접으면(시드 1~5) 노드 쌍 거리의 상관 r 의 중앙값이
                 · 되풀이가 많은 6곡(rec80 ≥ 0.6: hibari·reich·mcml·aqua·ravel·solari) 에서 ≥ 0.7
                 · 13곡에 걸쳐 rec80 과 Spearman ≥ 0.5 (되풀이가 적으면 실타래의 꼴이 하나로 정해지지 않는다 — 그건 한계로 적는다)
  P2 구별        (곡, 시드) 78개 배치를 거리 분위수 서술자로 1-최근접 분류(하나 빼기)하면 정확도 ≥ 0.85
  P3 대조군      시각을 통째로 뒤섞으면(음 재료는 같고 순서만 깨진다) 13곡 모두 rec80 ≤ 0.10 으로 떨어지고,
                 원래 배치와의 거리 상관 r ≤ 0.2 (같은 노드 번호끼리 — 뒤섞인 뒤에는 뜻이 없다: 귀무 기준선)
  P3b 도막 섞기  4박 도막은 그대로 두고 도막의 순서만 섞으면 rec80 은 원래의 ±0.2 안에 남는다(재료는 같다).
                 그러나 모양은 달라진다: 거리 분위수 서술자 거리가 그 곡의 시드 간 거리의 중앙값보다 크다 — 13곡 중 ≥ 9곡
  P4 매개변수    맥락 길이 2·4·8박에서 rec80 의 곡 순위가 유지된다 (Spearman ≥ 0.85, 세 쌍 모두).
                 ρ·문턱을 ±30% 흔들어도 되풀이 많은 6곡의 배치는 기본 배치와 거리 상관 중앙값 ≥ 0.6
  P5 hibari      성부를 합치면(들리는 대로) 모듈 a 의 짝은 모듈 33−a 다: a = 1…15 의 모든 스텝 중 ≥ 90% 에서
                 가장 닮은 먼 시각의 지연이 1056 − 65a (±1), 닮음 ≥ 0.95.  성부를 가리면 그 짝이 사라지고 지연 528 이 된다(≥ 90%).
                 (두 손이 같은 무늬를 서로 다른 주기 32·33 으로 돌 때, 누가 쳤는지 가리지 않으면 상태 = 원 위의 순서 없는 두 점 = 뫼비우스 띠.)

한계 (재지 못하는 것)
  · 이 수치들은 "배치가 곡의 자기유사성을 반영한다" 까지만 말한다. "사람이 그 모양에서 곡을 알아본다" 는 재지 않았다.
  · 거리 상관은 회전·이동에 불변이지만 거울상은 구별하지 못한다.
  · reich 는 한 번 접는 데 1분이 넘어 시드 2개·변형 일부만 돌린다(아래 LIGHT).
원본: docs/step3_data/song_shape_checks.json
"""
import os, sys, json, time, datetime
import numpy as np
from scipy.stats import spearmanr
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import song_fold as sf

SEEDS = [0, 1, 2, 3, 4, 5]; LIGHT = {'reich': [0, 1, 2]}
M = 300                                                        # 거리 상관에 쓰는 노드 수 (시간상 고르게)
QS = np.arange(5, 100, 5)


def pdist(X, idx):
    P = X[idx]; D = np.linalg.norm(P[:, None] - P[None], axis=2)
    return D[np.triu_indices(len(idx), 1)]


def block_shuffle(song, seed, block_beats=4.0):
    """4박 도막의 순서만 섞은 곡 (도막 안의 음은 그대로)."""
    rng = np.random.default_rng(seed); nb = int(np.ceil(song['beats'] / block_beats)) + 1; perm = rng.permutation(nb)
    new = dict(song); new['voices'] = []
    for v in song['voices']:
        w = v.copy(); b = np.floor(w[:, 0] / block_beats).astype(int); w[:, 0] = perm[b] * block_beats + (w[:, 0] - b * block_beats)
        new['voices'].append(w[np.argsort(w[:, 0], kind='stable')])
    new['beats'] = float(max(x[:, 0].max() for x in new['voices']))
    return new


def fold_song(song, seed=0, shuffle=None, **kw):
    p = dict(sf.DEF); p.update(kw)
    W, ns, unit, tt, ban = sf.features(song, shuffle=shuffle, **p)
    X, info, _ = sf.fold(W, unit, ban, seed=seed, **kw)
    return X, info


def main():
    t00 = time.time(); out = {'songs': {}, 'params': sf.DEF}
    desc, lab = [], []
    for slug, *_ in sf.SONGS:
        t0 = time.time(); song = sf.load(slug); seeds = LIGHT.get(slug, SEEDS); R = {}
        X0, i0 = fold_song(song); T = len(X0); idx = np.unique(np.linspace(0, T - 1, min(M, T)).astype(int)); d0 = pdist(X0, idx)
        R['T'] = T; R['rec80'] = i0['rec80']; R['radius'] = i0['radius']
        D = {0: d0}
        for s in seeds[1:]: D[s] = pdist(fold_song(song, seed=s)[0], idx)
        rs = [float(np.corrcoef(D[a], D[b])[0, 1]) for a in D for b in D if a < b]
        R['seed_r'] = [round(x, 4) for x in rs]; R['seed_r_median'] = float(np.median(rs))
        q = {s: np.log(np.percentile(D[s], QS)) for s in D}
        for s in D: desc.append(q[s]); lab.append(slug)
        R['seed_desc_dist_median'] = float(np.median([np.linalg.norm(q[a] - q[b]) for a in q for b in q if a < b]))
        # 대조군 1: 시각 뒤섞기
        Xs, isf = fold_song(song, shuffle=1); ds = pdist(Xs, idx[idx < len(Xs)]) if len(Xs) == T else None
        R['shuffle'] = {'rec80': isf['rec80'], 'r_vs_original': float(np.corrcoef(d0, ds)[0, 1]) if ds is not None else None,
                        'desc_dist': float(np.linalg.norm(np.log(np.percentile(pdist(Xs, np.unique(np.linspace(0, len(Xs) - 1, min(M, len(Xs))).astype(int))), QS)) - q[0]))}
        # 대조군 2: 4박 도막 순서 섞기
        bs = block_shuffle(song, 1); Xb, ib = fold_song(bs)
        R['block_shuffle'] = {'rec80': ib['rec80'],
                              'desc_dist': float(np.linalg.norm(np.log(np.percentile(pdist(Xb, np.unique(np.linspace(0, len(Xb) - 1, min(M, len(Xb))).astype(int))), QS)) - q[0]))}
        # 매개변수
        R['L'] = {}
        for L in (2.0, 8.0):
            W, ns, unit, tt, ban = sf.features(song, **{**sf.DEF, 'Lbeats': L}); _, _, best = sf.knn(W, sf.DEF['k'], sf.DEF['thr'], ban)
            R['L'][str(L)] = float((best >= 0.8).mean())
        R['param_r'] = {}
        if slug not in LIGHT:
            for name, kw in (('rho-30%', {'rho': 4.6}), ('rho+30%', {'rho': 8.6}), ('thr0.4', {'thr': 0.4}), ('thr0.6', {'thr': 0.6})):
                R['param_r'][name] = float(np.corrcoef(d0, pdist(fold_song(song, **kw)[0], idx))[0, 1])
        out['songs'][slug] = R
        print(f"{slug:8s} T={T:5d} rec80={R['rec80']:.2f}  시드 r 중앙 {R['seed_r_median']:.3f}  섞기 rec80 {R['shuffle']['rec80']:.2f} r {R['shuffle']['r_vs_original']:.3f}  "
              f"도막섞기 rec80 {R['block_shuffle']['rec80']:.2f} 서술자거리 {R['block_shuffle']['desc_dist']:.2f} (시드 간 {R['seed_desc_dist_median']:.2f})  "
              f"L2/8 {R['L']['2.0']:.2f}/{R['L']['8.0']:.2f}  {time.time()-t0:.0f}s", flush=True)

    S = out['songs']; slugs = list(S)
    # P1
    big = [s for s in slugs if S[s]['rec80'] >= 0.6]
    p1a = {s: S[s]['seed_r_median'] for s in big}; rho1 = float(spearmanr([S[s]['rec80'] for s in slugs], [S[s]['seed_r_median'] for s in slugs]).statistic)
    # P2
    Dm = np.array(desc); ok = 0
    for i in range(len(Dm)):
        d = np.linalg.norm(Dm - Dm[i], axis=1); d[i] = np.inf; ok += lab[int(np.argmin(d))] == lab[i]
    # P4a
    r80 = {L: [S[s]['rec80'] if L == '4.0' else S[s]['L'][L] for s in slugs] for L in ('2.0', '4.0', '8.0')}
    p4a = {f'{a}-{b}': float(spearmanr(r80[a], r80[b]).statistic) for a, b in (('2.0', '4.0'), ('4.0', '8.0'), ('2.0', '8.0'))}
    p4b = {s: float(np.median(list(S[s]['param_r'].values()))) for s in big if S[s]['param_r']}
    # P5
    song = sf.load('hibari'); tt = sf.tatum(song); R0 = sf.roll(song, tt); p5 = {}
    for name, RR in (('merged', R0.sum(1, keepdims=True)), ('separate', R0)):
        W = sf.context(RR, 8, blur=1.0, chroma_w=0.0)[:1088]; G = W @ W.T
        for i in range(len(G)): G[i, max(0, i - 48):i + 49] = -1
        j = G.argmax(1); v = G.max(1); hit_swap = hit_528 = n = 0; per_mod = {}
        for a in range(1, 16):
            t = 32 * a + np.arange(32); lag = j[t] - t
            sw = (np.abs(lag - (1056 - 65 * a)) <= 1) & (v[t] >= 0.95); h5 = (np.abs(np.abs(lag) - 528) <= 1) & (v[t] >= 0.95)
            hit_swap += int(sw.sum()); hit_528 += int(h5.sum()); n += 32; per_mod[a] = [int(sw.sum()), int(h5.sum()), int(np.median(lag)), round(float(np.median(v[t])), 3)]
        p5[name] = {'frac_swap_twin': hit_swap / n, 'frac_lag528': hit_528 / n, 'per_module_[swap,528,median_lag,median_sim]': per_mod}
    V = {
        'P1a_seed_r_big6_min': float(min(p1a.values())), 'P1a_pass': bool(min(p1a.values()) >= 0.7), 'P1a_values': p1a,
        'P1b_spearman_rec80_vs_seed_r': rho1, 'P1b_pass': bool(rho1 >= 0.5),
        'P2_1nn_accuracy': ok / len(Dm), 'P2_pass': bool(ok / len(Dm) >= 0.85), 'P2_n': len(Dm),
        'P3_shuffle_rec80_max': float(max(S[s]['shuffle']['rec80'] for s in slugs)), 'P3_shuffle_r_max': float(max(S[s]['shuffle']['r_vs_original'] for s in slugs)),
        'P3_pass': bool(max(S[s]['shuffle']['rec80'] for s in slugs) <= 0.10 and max(S[s]['shuffle']['r_vs_original'] for s in slugs) <= 0.2),
        'P3b_rec80_within_0.2': int(sum(abs(S[s]['block_shuffle']['rec80'] - S[s]['rec80']) <= 0.2 for s in slugs)),
        'P3b_shape_differs': int(sum(S[s]['block_shuffle']['desc_dist'] > S[s]['seed_desc_dist_median'] for s in slugs)),
        'P3b_pass': bool(sum(abs(S[s]['block_shuffle']['rec80'] - S[s]['rec80']) <= 0.2 for s in slugs) == len(slugs) and sum(S[s]['block_shuffle']['desc_dist'] > S[s]['seed_desc_dist_median'] for s in slugs) >= 9),
        'P4a_spearman': p4a, 'P4a_pass': bool(min(p4a.values()) >= 0.85), 'P4b_param_r_median': p4b, 'P4b_pass': bool(min(p4b.values()) >= 0.6),
        'P5': p5, 'P5_pass': bool(p5['merged']['frac_swap_twin'] >= 0.9 and p5['separate']['frac_lag528'] >= 0.9),
    }
    out['verdict'] = V; out['generated_at'] = datetime.datetime.now().isoformat(timespec='seconds'); out['elapsed_s'] = round(time.time() - t00)
    out['prediction'] = __doc__[__doc__.index('PREDICTION'):__doc__.index('한계')].strip()
    dst = os.path.join(sf.ROOT, 'docs', 'step3_data', 'song_shape_checks.json')
    json.dump(out, open(dst, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print('\n판정'); [print(f'  {k:34s} {v}') for k, v in V.items() if not isinstance(v, dict) or len(str(v)) < 300]
    print('저장', dst)


if __name__ == '__main__':
    main()
