"""
tools/group_music.py — 군 원소로 hibari 를 다시 쓴다: 문법(손마다 낱말 + 옮김) 위에 군 원소를 걸어 새 곡을 만들고, 같은 규칙의 원형문자로 그린다 (2026-10-15 사용자:
  "hibari 두 손을 다른 획으로 나눠줘. group theory를 적용해 음악을 생성할 수 있도록, 표현할 수 있도록 하는 게 1순위니까 디자인은 살짝 미룰게").

문법: docs/step3_data/group_grammar.json (tools/group_grammar.py). hibari = 손마다 낱말 둘이 100%:
  오른손 22음 × 66 옮김 + 15음 × 33 옮김 (주기 64 = 8분 32박) · 왼손 22음 × 64 + 15음 × 32 (주기 66 = 8분 33박, 33박째 시작).
  두 손 위상 짝 (오른손 mod 64, 왼손 mod 66) — 곡 = Z₃₂ × Z₃₃ ≅ Z₁₀₅₆ 을 한 바퀴 (8분 단위).

변주 (전부 문법 위의 군 원소 — 음표를 고치지 않고 옮김 집합을 바꾼다):
  원곡        항등원 — 다시 만들기가 원곡과 음·길이까지 같은지 확인
  맞물림      왼손 주기 66 → 64 : Z₃₂ × Z₃₂ — 두 손이 한 박 늦은 채로 끝까지 어긋나지 않는다
  두 배 어긋남 왼손 주기 66 → 68 : Z₃₂ × Z₃₄ (gcd 2) — 모듈마다 두 박씩 밀려 곡 절반에서 이미 위상이 다시 맞는다
  옥타브 아래  왼손 −12 : Z₁₂ 의 항등 류(같은 음 이름) — 화성은 그대로, 음역만
  거울        오른손을 음높이 축(오른손 중앙값)에 대해 뒤집기 : 반전 I — 선율 윤곽이 거꾸로
그림 규칙(같은 규칙으로 다섯 판): 고리 두 가닥 = 바깥 오른손 · 안쪽 왼손, 가닥 굵기 = 그 손의 음 밀도,
  **두 가닥 사이 = 두 손의 위상 차**(반 모듈 단위로 맞으면 붙고 4분의 1 어긋나면 가장 벌어진다) · **손 전체 조옮김 = 그 가닥이 안팎으로**(반음 0.011) ·
  오른손 낱말은 바깥 12·4·8시, 왼손 낱말은 안쪽 2·6·10시 붓획(굵기 = 되풀이 횟수, 곁획 = 조옮김, 모양 = 선율 윤곽이라 반전하면 뒤집힌다).
  python tools/group_music.py [--fig]  (--fig = 그림만)
산출: output/group_music/*.mid · *.wav · docs/figures/group_music.png · docs/step3_data/group_music.json
한계: 귀로 들어 고르지 않았다. 변주는 군 원소의 예시이지 '좋은 곡' 을 고른 것이 아니다.
"""
import os, sys, json
import numpy as np
from scipy.ndimage import gaussian_filter, gaussian_filter1d
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, 'tools')]
import group_grammar as GG
import logogram_cosiatec as LC
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Malgun Gothic'

G0 = json.load(open(os.path.join(ROOT, 'docs', 'step3_data', 'group_grammar.json'), encoding='utf8'))['songs']['hibari']
RH, LH = 0, 1
T0 = {RH: 0, LH: 66}; PER = {RH: 64, LH: 66}
med = int(np.median([p for w in G0['voices'][RH]['words'] for t, p in w['P']]))
VAR = [('원곡', '항등원', G0, PER[LH]),
       ('맞물림', '왼손 주기 66 → 64 · Z₃₂×Z₃₂', GG.reperiod(G0, LH, 66, 64, t0=66), 64),
       ('두 배 어긋남', '왼손 주기 66 → 68 · Z₃₂×Z₃₄', GG.reperiod(G0, LH, 66, 68, t0=66), 68),
       ('옥타브 아래', '왼손 -12', GG.transpose(G0, LH, -12), PER[LH]),
       ('거울', f'오른손 반전 (축 {med})', GG.invert(G0, RH, 2 * med), PER[LH])]

def draw_hands(g, perL):
    """고리 두 가닥 + 손마다 낱말 붓획 (LC 의 납작붓)."""
    LC.G, LC.L = 760, 1.6; G = LC.G; F = np.zeros((G, G)); notes = GG.realize(g)
    Ttot = max(t + d for v in notes for t, p, d in v)
    th = np.linspace(np.pi / 2, np.pi / 2 - 2 * np.pi, 2600); tt = ((np.pi / 2 - th) / (2 * np.pi) * Ttot).astype(int) % Ttot
    ph = lambda t, h: ((t - T0[h]) % (PER[h] if h == RH else perL))
    d = (ph(tt, RH) - ph(tt, LH)) % 32                                   # 두 손 위상 차 (반 모듈 = 32 단위 — 두 구절 화음이 같다)
    on = (tt >= 66)                                                      # 왼손이 들어오기 전엔 한 가닥
    sep = np.where(on, 0.02 + 0.16 * np.sin(np.pi * d / 32) ** 2, 0.0)
    for h, sg in ((RH, 1), (LH, -1)):
        dens = np.zeros(Ttot + 1)
        for t, p, du in notes[h]: dens[t:t + du] += 1
        dens = gaussian_filter1d(dens, 8)[tt]; dens /= dens.max() + 1e-9
        ups = [u for w in g['voices'][h]['words'] for _, u in w['T']]; shift = 0.011 * np.median(ups) if ups else 0.0   # 손 전체 조옮김 = 가닥이 안팎으로 (반음 = 0.011)
        rr = 1.0 + sg * sep / 2 + shift
        LC.brush(F, np.c_[rr * np.cos(th), rr * np.sin(th)], 0.022, 0.004, press=0.3 + 0.8 * dens ** 1.2)
    for h, sg in ((RH, 1), (LH, -1)):
        V = g['voices'][h]; tot = sum(w['cover'] for w in V['words'])
        for j, w in enumerate(V['words'][:3]):                           # 자리: 오른손 낱말 = 바깥 12·4·8시, 왼손 = 안쪽 2·6·10시 (고르게)
            P = np.array(w['P']); T = np.array(w['T'])
            a = np.pi / 2 - 2 * np.pi * j / 3 - (0.0 if h == RH else np.pi / 3)
            size = 0.30 + 0.35 * np.sqrt(w['cover'] / tot)
            base = 1.0 + sg * (0.16 + 0.16 * size)
            frame = lambda x, y, a=a, base=base: (base * np.cos(a) + x * np.sin(a) + y * np.cos(a), base * np.sin(a) - x * np.cos(a) + y * np.sin(a))
            LC.glyph(F, P, T[:, 1].tolist(), len(T), 0.0, frame, size)
    B = gaussian_filter(F, 1.0); core = np.clip((B - 0.2) / 0.06, 0, 1)
    yy, xx = np.mgrid[0:G, 0:G].astype(float); r = np.hypot(xx - G / 2, yy - G / 2) / (G / 2)
    halo = gaussian_filter(B, 18); halo = np.clip(halo / (halo.max() + 1e-9) * (0.6 + 0.5 * LC.fbm(((30, 1.0), (10, 0.6)))), 0, 1)
    out = np.array([240, 238, 233]) / 255 * (1 - 0.08 * r[..., None] ** 2)
    out = out * (1 - 0.28 * halo[..., None]) + np.array([150, 156, 160]) / 255 * (0.28 * halo[..., None])
    return np.clip(out * (1 - core[..., None]) + np.array([14, 15, 17]) / 255 * core[..., None], 0, 1)

if __name__ == '__main__':
    FIG = '--fig' in sys.argv                                            # 그림만 (음향 렌더링 10분을 건너뛴다)
    od = os.path.join(ROOT, 'output', 'group_music'); os.makedirs(od, exist_ok=True)
    orig = [sorted((tp[0], tp[1], d) for tp, d in v) for v in GG.voices('Ryuichi_Sakamoto_-_hibari.mid')]
    rec = []; fig = plt.figure(figsize=(18, 4.9), facecolor='#eeece6')
    sys.path.insert(0, os.path.join(ROOT, 'tools')); from wav_renderer import render_midi_to_wav
    for k, (name, desc, g, perL) in enumerate(VAR):
        notes = GG.realize(g); mid = os.path.join(od, f'{k}_{name}.mid'); wav = mid[:-4] + '.wav'
        if FIG: sec = 0.0
        else: GG.to_midi(notes, mid); sec = render_midi_to_wav(mid, wav)
        same = [len(set(n) & set(o)) / len(o) for n, o in zip(notes, orig)]
        uni = len({(t, p) for t, p, d in notes[RH]} & {(t, p) for t, p, d in notes[LH]})
        rec.append({'name': name, 'op': desc, 'notes': [len(n) for n in notes], 'same_as_original_frac': [round(x, 3) for x in same],
                    'unison_onsets': uni, 'seconds': round(sec, 1), 'midi': os.path.relpath(mid, ROOT)})
        print(f'{name:8s} {desc:28s} 음 {[len(n) for n in notes]} · 원곡과 같은 음 {[f"{x:.0%}" for x in same]} · 두 손 같은 음 {uni} · {sec:.0f}초')
        ax = fig.add_axes([0.003 + k * 0.2, 0.16, 0.194, 0.8]); ax.imshow(draw_hands(g, perL), origin='lower'); ax.axis('off')
        fig.text(0.01 + k * 0.2, 0.09, name, fontsize=13, color='#1d201e'); fig.text(0.01 + k * 0.2, 0.04, desc, fontsize=9.5, color='#5d655f')
    fig.savefig(os.path.join(ROOT, 'docs', 'figures', 'group_music.png'), dpi=100, facecolor='#eeece6')
    if not FIG: json.dump({'script': 'tools/group_music.py', 'grammar': 'docs/step3_data/group_grammar.json', 'variants': rec}, open(os.path.join(ROOT, 'docs', 'step3_data', 'group_music.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print('저장 docs/figures/group_music.png · docs/step3_data/group_music.json · output/group_music/')
