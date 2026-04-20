## 8. 결론

본 연구는 사카모토 류이치의 hibari를 대상으로, persistent homology를 음악 구조 분석의 주된 도구로 사용하는 통합 파이프라인을 구축하였다. 수학적 배경 (§2), 두 가지 생성 알고리즘 (§3), 네 거리 함수 및 연속값 OM의 통계적 비교 (§4), scale 제약 · note 선택 · $\alpha$-grid 정교화 (§5), 블록 단위 생성 및 기준 블록 탐색 (§6)을 일관된 흐름으로 제시하였다.

**핵심 경험적 결과:**

1. **거리 함수 선택의 효과.** hibari Algorithm 1에서 DFT는 frequency 대비 JS $-38.2\%$ ($N=20$). 곡에 따라 최적 거리 함수가 다르다 — aqua·Bach (Tonnetz), Ravel (frequency), solari (Tonnetz, frequency).

2. **곡의 성격이 최적 모델을 결정한다.** hibari(diatonic, entropy $0.974$) : FC ↔ solari(chromatic) : Transformer.

3. **본 연구 최저 수치.** Algorithm 1: DFT $\alpha = 0.25$ per-cycle $\tau_c$로 JS $= 0.00902 \pm 0.00170$ ($N=20$, $\log 2$의 약 $1.30\%$). Algorithm 2: DFT $\alpha = 0.5$ FC-continuous로 JS $= 0.00035 \pm 0.00015$ ($N=10$, $\log 2$의 약 $0.05\%$). §5.8.2 Phase 2에서 Algo2의 $\alpha = 0.25$ 재실험은 유의 개선 없음 확인.

4. **위상 보존 음악 변주.** 화성 제약 + 시간 재배치 + 연속값 OM 결합으로 원곡과 위상적 유사·선율적으로 다른 변주 생성 (§5.4~§5.6).

5. **거리 함수 × 음악적 목적의 정합성.** 위상구조 재현 목적에서는 DFT, scale 제약 변주·화성 일관성 목적에서는 Tonnetz가 유리 (§5.6.1 vs §5.6.2).

6. **마디 단위 생성.** §6 P3+best-$k$로 한 마디 생성 + $65$회 복제 방식이 full-song Algorithm 1 Phase 1 수준(JS $0.01479$, §5.8.1 Phase 1 $0.01489$)과 수치적 동등.

7. **위상구조를 보존한 음악의 심미적 유효성 (Q4).** 청취 실험은 후속 과제로 남김 — QR코드로 데모 제공.

**후속 과제:**

- Transposition-invariance 증명 .
- **Void ($H_2$ 구멍) 의 음악적 의미.** 본 연구는 $H_1$ 중심이나, PH는 $H_2$ (2차원 void, 3-simplex 경계로 둘러싸인 공동) 를 원리적으로 제공하며 실제로 연구 과정에서 일부 발견되었다. 음악 네트워크 위에서 $H_2$가 포착하는 구조와 그 생성 seed로서의 유용성 검증 및 증명. 그러나 
- **감쇄 lag × 거리 함수 상호작용의 이론적 설명.** §4.1c 해석 4에서 DFT에서만 감쇄 lag가 개선(−7.1%), Tonnetz에서는 악화(+4.8%)임을 경험적으로 관찰했다. DFT의 pitch class 스펙트럼 표현과 시간 lag 상호작용의 정합성에 대한 분석이 가능하다.
- **($\alpha_\text{note}, \beta_\text{diss}, \gamma_\text{icv}$) grid search.** §5.5 휴리스틱 기본값 $(0.5, 0.3, 0.3)$에 대한 체계적 grid search.
- **Per-cycle $\tau_c$ + Algorithm 2 통합.** per-cycle $\tau_c$로 binarize한 OM을 Algorithm 2 (FC/Transformer)에 입력하는 확장 실험.
- **Per-cycle $\tau_c$ 전역 최적 탐색.** 1-pass greedy coordinate descent는 전역 최적을 보장하지 않으므로, 베이지안 최적화·블록 좌표 전수 탐색 등으로 §5.8.1 결과를 재검증.

본 연구는 "단일곡의 위상구조를 보존한 재생성"에서 출발하여, "위상구조를 보존한 음악적 변주"까지 확장되었다. 이 확장은 TDA가 음악 분석 도구일 뿐 아니라 **음악 창작의 제약 조건 생성기**로 기능할 수 있음을 시사한다.

---

## 감사의 글

본 연구는 KIAS 초학제 독립연구단 정재훈 교수님의 지도 아래 진행되었다. pHcol 알고리즘 구현 및 선행 파이프라인의 많은 부분을 계승하였음을 밝힌다. Ripser (Bauer), Tonnetz 이론 (Tymoczko), 그리고 국악 정간보 TDA 연구 (Tran, Park, Jung) 의 수학적 토대 위에 본 연구가 서 있음을 부기한다.

## 참고문헌

- Bauer, U. (2021). "Ripser: efficient computation of Vietoris–Rips persistence barcodes". *Journal of Applied and Computational Topology*, 5, 391–423.
- Carlsson, G. (2009). "Topology and data". *Bulletin of the American Mathematical Society*, 46(2), 255–308.
- Catanzaro, M. J. (2016). "Generalized Tonnetze". *arXiv preprint arXiv:1612.03519*.
- Chuan, C.-H., & Herremans, D. (2018). "Modeling temporal tonal relations in polyphonic music through deep networks with a novel image-based representation". *Proceedings of AAAI*, 32(1).
- cifkao. (2015). *tonnetz-viz: Interactive Tonnetz visualization*. GitHub. https://github.com/cifkao/tonnetz-viz
- Heo, E., Choi, B., & Jung, J.-H. (2025). "Persistent Homology with Path-Representable Distances on Graph Data". *arXiv:2501.03553*.
- Cohen, J. (1988). *Statistical Power Analysis for the Behavioral Sciences* (2nd ed.). Lawrence Erlbaum.
- Cohen-Steiner, D., Edelsbrunner, H., & Harer, J. (2007). "Stability of persistence diagrams". *Discrete & Computational Geometry*, 37(1), 103–120.
- Edelsbrunner, H., & Harer, J. (2010). *Computational Topology: An Introduction*. AMS.
- Hochreiter, S., & Schmidhuber, J. (1997). "Long Short-Term Memory". *Neural Computation*, 9(8), 1735–1780.
- Kingma, D. P., & Ba, J. (2015). "Adam: A method for stochastic optimization". *ICLR*.
- Nemhauser, G. L., Wolsey, L. A., & Fisher, M. L. (1978). "An analysis of approximations for maximizing submodular set functions". *Mathematical Programming*, 14(1), 265–294.
- Nielsen, F. (2019). "On the Jensen–Shannon symmetrization of distances". *Entropy*, 21(5), 485.
- Sakamoto, R. (2009). *out of noise* [Album]. commmons.
- Satterthwaite, F. E. (1946). "An approximate distribution of estimates of variance components". *Biometrics Bulletin*, 2(6), 110–114.
- Tran, M. L., Park, C., & Jung, J.-H. (2021). "Topological Data Analysis of Korean Music in Jeongganbo". *arXiv:2103.06620*.
- Tymoczko, D. (2008). "Set-Class Similarity, Voice Leading, and the Fourier Transform". *Journal of Music Theory*, 52(2).
- Tymoczko, D. (2011). *A Geometry of Music: Harmony and Counterpoint in the Extended Common Practice*. Oxford University Press.
- Tymoczko, D. (2012). "The Generalized Tonnetz". *Journal of Music Theory*, 56(1).
- Vaswani, A., et al. (2017). "Attention is all you need". *NeurIPS*.
- Welch, B. L. (1947). "The generalization of 'Student's' problem when several different population variances are involved". *Biometrika*, 34(1/2), 28–35.
- 이동진, Tran, M. L., 정재훈 (2024). "국악의 기하학적 구조와 인공지능 작곡".
