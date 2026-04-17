with open('academic_paper_full.md', 'r', encoding='utf-8') as f:
    content = f.read()

start_marker = '## 4.5a Experiment 4 — Continuous overlap + Algorithm 2 (FC)'
end_marker = '---\n\n## 4.6 종합 논의'

start_idx = content.index(start_marker)
end_idx = content.index(end_marker)

new_section = r"""## 4.5a Experiment 4 — Continuous overlap + Algorithm 2 (FC)

본 절은 §4.5의 DL 모델 비교에서 FC-cont의 압도적 우위를 확인한 후, **입력 유형(이진 vs 연속값)의 효과만 분리**하여 재현성을 검증한다. FC 모델을 고정한 채 학습 입력 데이터만 두 가지로 바꾸어 비교하는 controlled experiment이다. 실험 조건: DFT, $w_o = 0.3$, $w_d = 1.0$, $N = 10$ (`fc_cont_dft_gap0_results.json`).

### 실험 설계

__FC-bin (baseline)__: `build_activation_matrix(continuous=False)`로 얻은 이진 활성행렬 $X_{\text{bin}} \in \{0,1\}^{T \times K}$를 FC의 입력으로 사용.

__FC-cont__: 희귀도 가중치가 적용된 연속값 활성행렬 $X_{\text{cont}}[t, c] = a_{c,t}$ ($w(n) = 1/N_{\text{cyc}}(n)$)를 FC의 학습 입력으로 직접 사용. 모델 아키텍처, learning rate, epochs, batch size, train/valid split은 FC-bin과 완전히 동일.

### 결과

DFT, $w_o = 0.3$, $w_d = 1.0$, $N = 10$.

| 설정 | JS (mean ± std) | validation loss (mean) |
|---|---|---|
| __FC-bin__ (이진 입력 baseline) | $0.00217 \pm 0.00056$ | $0.339$ |
| __FC-cont__ ★ | $\mathbf{0.00035 \pm 0.00015}$ | $\mathbf{0.023}$ |

__해석 — FC-cont 통계 확정 (Welch $p = 1.50 \times 10^{-6}$).__ FC-cont가 JS $0.00035$로 FC-bin ($0.00217$) 대비 $83.9\%$ 개선되었다. DFT 이진 OM은 자체적으로 sparse하지만 (density $0.313$), 연속값으로 전환할 때 FC의 cell-wise 표현력이 cycle 활성 강도 차이를 세밀하게 반영하여 생성 분포를 크게 개선한다. Validation loss의 동시 감소 ($0.339 \to 0.023$, $-93\%$)는 연속값 입력이 FC의 학습 signal 자체를 개선함을 보여준다.

### 왜 이렇게 큰 개선이 나오는가 — 음악적 해석
> **⚠ SHORT 미포함**

__이진화는 "있다/없다" 만 말하지만, 연속값은 "얼마나 확신하는가" 를 말한다.__ 이진 $X_{\text{bin}}[t, c]$ 는 "시점 $t$ 에 cycle $c$ 의 vertex 중 *하나라도* 울리면 $1$"이다. 반면 연속값 $X_{\text{cont}}[t, c] = a_{c, t}$ 는 "cycle $c$ 의 vertex 중 *희귀도 가중치 기준으로 몇 퍼센트가* 활성인가"를 $[0, 1]$ 실수로 표현한다. FC 모델은 이 연속값 강도 정보를 학습하여 "오직 common note만 활성 (낮은 값)" vs "rare note 포함 전체가 활성 (높은 값)"을 구별하고, 원곡의 pitch 분포에 더 가까운 결과를 출력한다.

> **역사적 맥락.** FC-cont 아이디어는 §7의 "개선 F"로 최초 제안되었으며, 초기 검증은 Tonnetz 거리 함수 조건 (N=5, `step_improvementF_results.json`)에서 FC-bin $0.0014 \to$ FC-cont $0.0006$의 $57\%$ 개선으로 확인되었다. 본 절은 이 결과를 최종 조건 (DFT, gap=0, N=10)에서 재확인하여 통계적으로 확정한다.

### 기존 모든 결과와의 통합 비교

| 실험 | 설정 | JS divergence | 출처 |
|---|---|---|---|
| §4.1 Algo 1 | frequency baseline | $0.0344$ | §4.1 |
| §4.1 Algo 1 | DFT (최적) | $0.0213$ | §4.1 |
| §4.4 Algo 1 | DFT binary (최적 파라미터) | $\mathbf{0.0157 \pm 0.0018}$ ★ | §4.4 |
| §7.5 Algo 1 | P3 + C (module-level) | $0.0590$ | §7 |
| §7.7 Algo 1 | P3 + C, best trial (seed 9302) | $\mathbf{0.0258}$ | §7 |
| §4.5 Algo 2 FC | DFT binary | $0.00217$ | §4.5 |
| __§4.5a Algo 2 FC__ | __DFT continuous__ | $\mathbf{0.00035 \pm 0.00015}$ ★ | __본 절__ |

> **§7.5 / §7.7 항목 요약 (세부 내용은 §7 참조).** §7은 hibari의 32-timestep 모듈 구조를 직접 활용하는 **모듈 단위 생성** 실험이다. **P3** 전략은 원곡 첫 모듈($t \in [0, 32)$)을 prototype으로 사용하고, **C** 전략(best-of-$k$ selection)을 결합하여 JS를 최소화한다. §7.5 결과($N = 10$ 평균): JS $0.0590$. §7.7에서 최적 seed(9302)에서는 JS $\mathbf{0.0258}$을 달성하였다. 이는 full-song DFT baseline ($0.0213$)보다 높은 값으로, 모듈 단위 생성이 full-song Algorithm 2 (DL)를 대체하기보다 보완하는 위치임을 보여준다.

**§4.5a의 FC-cont (DFT, gap=0)는 본 연구의 full-song 생성에서 관측된 최저 JS divergence**이며, 이론적 최댓값 $\log 2 \approx 0.693$의 약 $0.05\%$에 해당한다.

### 후속 과제

1. __(완료 — §6.7.2) LSTM / Transformer 에도 FC-cont 확장__: FC-cont $\text{JS} = 0.0004$, Transformer-cont $\text{JS} = 0.0007$. FC > Transformer 우위가 continuous 입력에서도 유지됨을 확인. LSTM 은 continuous 입력에서 소폭 악화.
2. __Continuous + module-local (P3)__: §7의 P3 + C와 FC-cont를 결합하여 "module-local continuous activation을 FC에 입력"하는 실험은 향후 과제로 남는다.
3. __(완료 — §6.7.1) Per-cycle τ 최적화__: FC-cont 대신 per-cycle 임계값을 최적화하여 Algorithm 1에서 추가 개선을 달성 (§6.7.1, +58.7% vs uniform τ).

"""

new_content = content[:start_idx] + new_section + content[end_idx:]

with open('academic_paper_full.md', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Done. Lines:', new_content.count('\n'))
