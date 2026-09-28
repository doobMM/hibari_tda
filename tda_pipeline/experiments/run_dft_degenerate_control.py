"""
run_dft_degenerate_control.py — "DFT 거리" 가 옥타브·길이 거리와 비트 단위로 같은가

배경 (2026-09-28)
  musical_metrics._build_dft_cache 는 음높이 류 하나를 원-핫 12차원으로 FFT 해 |f̂(k)|, k=1..6 을 쓴다.
  한 점짜리 신호의 푸리에 계수 크기는 모든 k·모든 음높이 류에서 1 → pitch_class_dft(pc) 가 12개 전부
  [1,1,1,1,1,1] (비트 단위 동일) → dft_note_distance 의 DFT 항은 **정확히 0.0**.
  |DFT| 는 전조 불변량이고 단일 음들은 서로의 전조이므로, 원리적으로 구별할 수 없다.

사전 예측 (실행 전에 적었다)
  P1  음악거리 행렬: metric='dft' == 옥타브·길이 함수 — 비트 단위 동일 (np.array_equal 과 바이트 비교 둘 다)
  P2  build_overlap_bundle 안에서 generate_barcode_numpy 가 받은 입력 행렬 151개(rate 0~1.5)가 비트 단위 동일
  P3  그 출력 바코드 151개가 동일 (repr 비교)
  P4  번들 산출물 — cycle_labeled · activation_binary · activation_continuous · overlap_binary — 동일
  P5  헤드라인 Algorithm 1 (per-cycle τ = tau_profile, seed_base 125000, N=20) JS 20개가 동일
      → 헤드라인 JS=0.00902 가 "옥타브·길이 + 빈도 하이브리드" 로 그대로 재현된다

양성 대조 (비교가 '같다' 를 거저 내주지 않는지)
  C1  옥타브·길이 함수의 길이 가중치만 1.0 → 0.99 로 바꾼 팔 — P1·P2 가 **달라야** 한다

방법
  거리 함수를 바꾸지 않는다. 이 스크립트 안에서만 musical_metrics.METRICS 등록부에 함수를 추가한다
  (compute_note_distance_matrix 가 호출 시점에 get_metric 으로 찾으므로 번들 경로를 그대로 탄다).
  suite.metric_distance_matrix 는 'dft'·'tonnetz' 에만 ow·dw 를 넘기므로, 추가 함수는 기본값으로
  정본 값(ow=0.3, dw=1.0)을 갖게 하고 그 사실을 assert 한다.
  generate_barcode_numpy 를 기록용 래퍼로 감싸 번들이 실제로 계산한 입력·출력을 모은다.

한계
  · hibari 한 곡만 쟀다. 다른 곡도 같은 이유(단일 음 |DFT| 불변)로 같아야 하나 여기선 재지 않았다.
  · note_reassign.dft_set_distance(음 집합의 DFT)는 퇴화하지 않는다 — 이 실험의 대상이 아니다.

실행: python experiments/run_dft_degenerate_control.py   (≈ 1분, 캐시 불필요)
산출: docs/step3_data/dft_degenerate_control.json
"""
import sys, os, io, json, contextlib, datetime, inspect
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [ROOT, os.path.join(ROOT, 'experiments')]
os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    import run_dft_gap0_suite as suite
    data = suite.setup_hibari()
import musical_metrics as mm

ALPHA, OW, DW = 0.25, 0.3, 1.0


def make_octdur(ow_default, dw_default):
    """DFT 항을 뺀 dft_note_distance — 같은 연산 순서. (0.0 + A) + B == A + B 는 IEEE 에서 정확하다."""
    def octdur_note_distance(note1, note2, octave_weight=ow_default, duration_weight=dw_default):
        p1, d1 = note1
        p2, d2 = note2
        oct_diff = abs(p1 // 12 - p2 // 12)
        max_dur = max(d1, d2, 1)
        dur_diff = abs(d1 - d2) / max_dur
        return octave_weight * oct_diff + duration_weight * dur_diff
    return octdur_note_distance

mm.METRICS['octdur'] = make_octdur(OW, DW)           # 정본 값과 같은 기본값
mm.METRICS['octdur_dw099'] = make_octdur(OW, 0.99)   # 양성 대조 C1
sig = inspect.signature(mm.METRICS['octdur']).parameters
assert sig['octave_weight'].default == OW and sig['duration_weight'].default == DW

# ── generate_barcode_numpy 기록 래퍼 ─────────────────────────────────
REC = {}
_orig = suite.generate_barcode_numpy
def recorder(tag):
    def wrapped(mat, **kw):
        bd = _orig(mat=mat, **kw)
        REC.setdefault(tag, []).append((np.array(mat, dtype=float, copy=True), repr(bd)))
        return bd
    return wrapped

bundles = {}
for tag in ('dft', 'octdur', 'octdur_dw099'):
    suite.generate_barcode_numpy = recorder(tag)
    with contextlib.redirect_stdout(io.StringIO()):
        bundles[tag] = suite.build_overlap_bundle(data, tag, alpha=ALPHA, octave_weight=OW,
                                                  duration_weight=DW, use_decayed=False, threshold=0.35)
suite.generate_barcode_numpy = _orig

out = {'script': 'experiments/run_dft_degenerate_control.py',
       'run_at': datetime.datetime.now().isoformat(timespec='seconds'),
       'config': {'alpha': ALPHA, 'octave_weight': OW, 'duration_weight': DW, 'use_decayed': False, 'threshold': 0.35}}

# ── 단일 음 |DFT| 캐시 ───────────────────────────────────────────────
C = np.array([mm.pitch_class_dft(p) for p in range(12)])
out['dft_cache'] = {'unique_rows_bytewise': len({r.tobytes() for r in C}), 'row': C[0].tolist(),
                    'all_pair_dft_terms_exactly_zero': bool(all(np.linalg.norm(C[i] - C[j]) == 0.0
                                                                 for i in range(12) for j in range(12)))}

# ── P1 음악거리 행렬 ─────────────────────────────────────────────────
M = {t: np.asarray(suite.metric_distance_matrix(data['notes_label'], t, OW, DW), float)
     for t in ('dft', 'octdur', 'octdur_dw099')}
iu = np.triu_indices(M['dft'].shape[0], 1)
def same(a, b): return bool(np.array_equal(a, b) and a.tobytes() == b.tobytes())
out['P1_musical_matrix'] = {
    'dft_eq_octdur_bitwise': same(M['dft'], M['octdur']),
    'max_abs_diff_dft_octdur': float(np.max(np.abs(M['dft'] - M['octdur']))),
    'distinct_values_upper': int(len(np.unique(M['dft'][iu]))), 'pairs': int(len(iu[0])),
    'C1_dft_eq_dw099': same(M['dft'], M['octdur_dw099']),
    'C1_max_abs_diff': float(np.max(np.abs(M['dft'] - M['octdur_dw099'])))}

# ── P2·P3 번들 안의 바코드 입력·출력 151개 ──────────────────────────────
def cmp_rec(a, b):
    ra, rb = REC[a], REC[b]
    n = min(len(ra), len(rb))
    in_same = sum(same(ra[i][0], rb[i][0]) for i in range(n))
    out_same = sum(ra[i][1] == rb[i][1] for i in range(n))
    return {'n_a': len(ra), 'n_b': len(rb), 'inputs_bitwise_equal': in_same, 'outputs_equal': out_same}
out['P2_P3_barcodes'] = {'dft_vs_octdur': cmp_rec('dft', 'octdur'), 'C1_dft_vs_dw099': cmp_rec('dft', 'octdur_dw099')}

# ── P4 번들 산출물 ───────────────────────────────────────────────────
def bundle_eq(a, b):
    A, Bb = bundles[a], bundles[b]
    r = {'cycle_labeled': {k: tuple(v) for k, v in A['cycle_labeled'].items()} ==
                          {k: tuple(v) for k, v in Bb['cycle_labeled'].items()},
         'K_a': len(A['cycle_labeled']), 'K_b': len(Bb['cycle_labeled'])}
    for key in ('activation_binary', 'activation_continuous', 'overlap_binary'):
        x, y = A[key], Bb[key]
        r[key] = bool(list(x.columns) == list(y.columns) and x.shape == y.shape and same(x.values.astype(float), y.values.astype(float)))
    return r
out['P4_bundle'] = {'dft_vs_octdur': bundle_eq('dft', 'octdur'), 'C1_dft_vs_dw099': bundle_eq('dft', 'octdur_dw099')}

# ── P5 헤드라인 Algorithm 1 ───────────────────────────────────────────
grid = json.load(open('docs/step3_data/percycle_tau_dft_gap0_alpha_grid_results.json', encoding='utf8'))
r025 = next(r for r in grid['results'] if abs(float(r['alpha']) - ALPHA) < 1e-9)
TAU = np.array(r025['tau_profile'])
def headline_js(tag):
    b = bundles[tag]; keys = list(b['cycle_labeled'].keys())
    U = b['activation_continuous'][keys].values.astype(np.float64)
    OM = (U >= TAU).astype(np.float32) if U.shape[1] == len(TAU) else None
    if OM is None: return None
    with contextlib.redirect_stdout(io.StringIO()):
        tr = suite.run_algo1_trials(data, OM, b['cycle_labeled'], n_repeats=20, seed_base=125000, min_onset_gap=0)
    return [t['js_divergence'] for t in tr]
js_dft, js_oct = headline_js('dft'), headline_js('octdur')
out['P5_headline_algo1'] = {
    'recorded_js_mean': r025['js_mean'], 'dft_js_mean': float(np.mean(js_dft)), 'octdur_js_mean': float(np.mean(js_oct)),
    'dft_vs_octdur_max_abs_diff': float(np.max(np.abs(np.array(js_dft) - np.array(js_oct)))),
    'dft_vs_recorded_all_js_max_abs_diff': float(np.max(np.abs(np.array(js_dft) - np.array(r025['all_js']))))}

ok = lambda c: '✅' if c else '❌'
p1, p23, p4, p5 = out['P1_musical_matrix'], out['P2_P3_barcodes'], out['P4_bundle'], out['P5_headline_algo1']
d = p23['dft_vs_octdur']; c = p23['C1_dft_vs_dw099']
verdict = {
  'P1': p1['dft_eq_octdur_bitwise'],
  'P2': d['inputs_bitwise_equal'] == d['n_a'] == d['n_b'] == 151,
  'P3': d['outputs_equal'] == 151,
  'P4': all(v for k, v in p4['dft_vs_octdur'].items() if isinstance(v, bool)),
  'P5': p5['dft_vs_octdur_max_abs_diff'] == 0.0,
  'C1_detects_difference': (not p1['C1_dft_eq_dw099']) and c['inputs_bitwise_equal'] < 151}
out['verdict'] = verdict
json.dump(out, open('docs/step3_data/dft_degenerate_control.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)

print(f"단일 음 |DFT| 캐시: 바이트 단위 고유 행 {out['dft_cache']['unique_rows_bytewise']} · 값 {out['dft_cache']['row']} · 모든 쌍 DFT 항 == 0.0 {out['dft_cache']['all_pair_dft_terms_exactly_zero']}")
print(f"{ok(verdict['P1'])} P1 음악거리 행렬 dft == 옥타브·길이 (비트)   최대 차 {p1['max_abs_diff_dft_octdur']:.1e} · 253쌍 중 서로 다른 값 {p1['distinct_values_upper']}")
print(f"{ok(verdict['P2'])} P2 번들 안 바코드 입력 {d['inputs_bitwise_equal']}/{d['n_a']} 비트 동일")
print(f"{ok(verdict['P3'])} P3 번들 안 바코드 출력 {d['outputs_equal']}/{d['n_a']} 동일")
print(f"{ok(verdict['P4'])} P4 번들 산출물 {p4['dft_vs_octdur']}")
print(f"{ok(verdict['P5'])} P5 헤드라인 Algo1 JS 20개 — dft {p5['dft_js_mean']:.6f} · 옥타브·길이 {p5['octdur_js_mean']:.6f} · 최대 차 {p5['dft_vs_octdur_max_abs_diff']:.1e} (기록 {p5['recorded_js_mean']:.6f}, 기록 대비 {p5['dft_vs_recorded_all_js_max_abs_diff']:.1e})")
print(f"{ok(verdict['C1_detects_difference'])} C1 양성 대조 (dw 0.99): 음악거리 최대 차 {p1['C1_max_abs_diff']:.3f} · 바코드 입력 동일 {c['inputs_bitwise_equal']}/{c['n_a']} · 출력 동일 {c['outputs_equal']}/{c['n_a']} · 번들 K {p4['C1_dft_vs_dw099']['K_a']} vs {p4['C1_dft_vs_dw099']['K_b']}")
print('저장: docs/step3_data/dft_degenerate_control.json')
