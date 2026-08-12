# JS RePaint 샘플러 결정적 동치 검증

생성: 2026-08-10T13:47:45.087Z (자동 생성 — `tools/verify_js_sampler.mjs`)

## 배경

`hibari_dashboard/public/js/motif-diffusion.js` 는 `experiments/motif_control.py`
의 `sample_with_motif()` 를 브라우저용으로 이식한 RePaint 샘플러다. 지금까지
검증된 것은 스케줄 상수뿐이었고(파이썬 대비 7.2e-8), 샘플링 루프 자체
(MultiDiffusion 창 융합 + RePaint 마스킹 + x̂₀ 클리핑 사후평균)는 미검증이었다.
이 문서는 그 루프를 실제로 실행해 대조한 결과다.

## 검증 방식 — 왜 (B) "노이즈=0 결정적 경로"를 택했는가

과제가 제시한 두 방법 중 (A) "양쪽에 동일한 고정 노이즈 배열 주입"은 실행
불가능했다: `motif-diffusion.js` 의 `randn` 은 `sampleWithMotif()` 호출마다
새로 만들어지는 **비공개 클로저**(`makeRandn(seed)`, mulberry32+Box-Muller)이고,
외부에서 개별 draw 값을 주입할 공개 인터페이스가 없다. 이를 가능하게 하려면
배포 중인 `motif-diffusion.js` 자체를 고쳐야 하는데, 그러면 "실제 배포된
코드"가 아니라 "테스트를 위해 바뀐 코드"를 검증하게 되어 본말이 전도된다.
반대로 파이썬 쪽 `torch.Generator` 는 Philox 계열 PRNG 라 mulberry32 와
애초에 같은 난수 스트림을 낼 수 없다 — 이는 버그가 아니라 서로 다른 PRNG 를
쓴 결과이며 검증 대상이 아니다.

그래서 (B) 를 택했다: 모든 노이즈 항(사후분산 항 `sig*noise`, RePaint 안다는
영역의 `k1m*randn()`, 되돌림 재샘플링의 `sqrt(betas)*randn()`)을 0으로 두고
**평균-전용(ODE) 결정적 경로**만 비교했다. 이렇게 하면 실제로 미검증이었던
4가지 결정적 산술 — (i) 윈도우 크롭+Hann 융합, (ii) x̂₀ 클리핑+사후평균 계수,
(iii) RePaint 마스크 블렌딩, (iv) respace() 재배치 — 을 노이즈에 가려지지
않고 그대로 비교할 수 있다.

모델도 같은 이유로 실제 ONNX 대신 **두 언어가 공유하는 더미 함수**를 썼다:

```
eps[c,j] = tanh(0.3*crop + 0.01*(j-win/2) - 0.002*t + 0.05*sin(0.7*c+0.02*t))
```

ONNX 모델 자체(PyTorch↔ONNXRuntime)의 수치 일치는 `tools/export_topo_onnx.py`
가 이미 별도로 검증했다(모든 배치/시간축 조합에서 max|diff| ≤ 3.1e-6,
`topo_denoiser_meta.json`.`parity_max_abs_diff` 참조) — 여기서 다시 검증할
필요가 없었다. 오히려 실제 모델을 쓰면 "모델이 무엇을 예측하든 창 경계에서
올바르게 합성/클리핑/마스킹하는가"라는 진짜 검증 대상이 모델 예측값 자체의
변동에 가려진다.

## onnxruntime-node 설치 여부

`npm ls onnxruntime-node` → `(empty)`. 이 레포에는 설치돼 있지 않았고,
지시대로 설치하지 않았다. 대신 위에서 설명한 "더미 eps 주입" 대안을 썼다.

## 코드 재사용 범위

- `MotifDiffusion._cosineSchedule` / `MotifDiffusion._respace` — motif-diffusion.js
  를 **수정 없이 그대로 로드**해서 직접 호출한 실제 배포 코드.
- Hann 창 계산(`motif-diffusion.js:235-238`)과 스텝 산술
  (`motif-diffusion.js:266-330`)은 class 내부 클로저라 외부에서 직접 호출할
  수 없어 **검증 전용 사본**으로 옮겨 썼다. 노이즈 항만 제거했고, 변수명·
  연산 순서·분기 조건은 원본과 동일하게 유지했다(`tools/verify_js_sampler.mjs`
  주석에 원본 라인 번호를 인용).
- 파이썬 쪽은 `experiments/motif_control.py` (읽기 전용, 수정하지 않음)의
  `_fused_eps` / `sample_with_motif` 를 그대로 베낀 사본을
  `tools/verify/gen_reference.py` 에 두었다(모델 호출만 더미로, 노이즈 항만
  제거).
- `respace()` 는 파이썬 원본이 없다(JS 전용 최적화) — 알고리즘 설명을 보고
  독립 재구현(`respace_py`)해 교차검증했다.

## 결과

| 항목 | 비교 대상 | max\|diff\| | 판정 |
|---|---|---|---|
| item1 | hann60(전체60개) | 1.788e-7 | PASS |
| item5-pre | cosineSchedule(200).betas vs 재계산 cosine_beta_schedule(200) | 2.112e-8 | PASS |
| item5-pre | cosineSchedule(200).betas vs 배포된 topo_denoiser_meta.json betas | 2.112e-8 | PASS |
| item5-pre | cosineSchedule(200).postC0 vs 실제 DDPM(200).post_c0 | 6.288e-5 | PASS |
| item5-pre | cosineSchedule(200).postCt vs 실제 DDPM(200).post_ct | 3.103e-5 | PASS |
| item5-pre | cosineSchedule(200).postVar vs 실제 DDPM(200).post_var | 4.788e-8 | PASS |
| item5 | respace(50).betas vs 독립재구현 respace_py | 8.502e-9 | PASS |
| item5 | respace(50).postC0 | 8.628e-9 | PASS |
| item5 | respace(50).postCt | 8.628e-9 | PASS |
| item5 | respace(50).postVar | 8.457e-9 | PASS |
| item5 | respace(5).postC0 (item6 용 스케줄) | 1.718e-9 | PASS |
| item5 | respace(5).postCt (item6 용 스케줄) | 1.379e-9 | PASS |
| 설정확인 | 창 시작점(13개) JS vs PY | 0.000e+0 | PASS |
| item2 | MultiDiffusion 융합 eps @ i=100 (K×T=14×240) | 1.192e-7 | PASS |
| item3 | x̂₀ 클리핑 값 @ i=100 | 1.788e-7 | PASS |
| item3 | 사후평균(mean) @ i=100 | 4.768e-7 | PASS |
| item4 | RePaint 마스크 적용 후 x @ i=100 | 4.768e-7 | PASS |
| item6 | 최종 출력 x_out (T×K=240×14, [0,1]) | 1.997e-6 | PASS |

판정 기준: 1e-4 초과 시 FAIL.

**전 항목 통과.** MultiDiffusion 융합·x̂₀ 클리핑 사후평균·RePaint 마스킹·respace 스케줄 재계산 모두 파이썬 기준값과 1e-4 이내로 일치했다.

## 재현 명령

```bash
python tools/verify/gen_reference.py   # 파이썬 기준값 생성 → tools/verify/reference.json
node tools/verify_js_sampler.mjs       # 이 리포트 재생성
```

## 남은 검증 공백 (참고)

- **RNG 자체의 등가성은 검증하지 않았다** — mulberry32(JS) vs torch.Generator
  (Python)는 설계상 다른 스트림을 낸다. 실제 배포 코드의 시각적/청각적 품질은
  난수가 켜진 상태에서 결정되므로, 이 문서의 결과는 "결정적 배관이 새지
  않는다"는 것만 보장하고 "노이즈가 켜졌을 때도 감각적으로 그럴듯한 분포를
  낸다"는 것까지는 보장하지 않는다.
- 실제 ONNX 모델 호출 코드 경로(`session.run(feeds)`, `ort.Tensor` 구성)는
  onnxruntime-node 부재로 이 검증에서 실행되지 않았다 — 더미 함수로 대체됐다.
  단, 텐서 shape/dtype 규약(`float32`/`int64`, `[batch,K,win]`)은
  `tools/export_topo_onnx.py` 의 export 시 검증된 것과 동일 규약을 그대로
  썼다.
