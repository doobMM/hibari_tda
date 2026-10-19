"""
tools/group_demo_video.py — 손짓 하나 = 군 생성원 하나: hibari 왼손 고리를 한 칸 돌리면(g) 원형문자와 소리가 함께 바뀌고, 되돌리면(g⁻¹) 돌아온다. 20초 영상(소리 포함).
(2026-10-19 사용자 프롬프트 0번: "먼저 움직이는 그림 하나: 손짓 하나(예: 왼손 가닥을 한 칸 돌리기) → 원형문자가 바뀌고 → 소리가 바뀌는 20초짜리 화면 녹화(소리 포함)")

군: hibari 두 손은 **같은 낱말**(모듈 59음, 자료로 확인)을 오른손 Z₃₂ · 왼손 Z₃₃ 으로 돈다. 생성원 g = 왼손 시계를 한 칸 늦추기(쉼 한 칸 끼우기), g⁻¹ = 한 칸 당기기.
그림: 같은 낱말을 새긴 먹 고리 둘 — 바깥 오른손(32칸) · 안쪽 왼손(33칸, 한 칸은 빈 쉼). 각자 제 주기로 돌고 12시 바늘 아래 칸이 운다.
      울리는 음은 희게 빛나고, 두 손이 같은 박에 같은 음을 내면 금빛 · 낱말 획 = 화음(굵은 덩이) · 선율(바깥으로 튀는 획, 길수록 높다) · 베이스(안쪽 짧은 획).
구간: 8분 515박째부터 44박(20초, 반 모듈 어긋난 대목). 같은 음이 g 전 17 · g 뒤 3 · g⁻¹ 뒤 12 — g 를 걸면 금빛이 사라지고 되돌리면 돌아온다.
      (처음 509박째 창은 같은 음이 대부분 g⁻¹ 뒤에 몰려 g 의 효과가 보이지 않았다 3·3·22). 8초에 g, 15초에 g⁻¹.
산출: output/group_music/demo_g.mp4  (python tools/group_demo_video.py)
"""
import os, sys, subprocess, tempfile, shutil
import numpy as np
from scipy.ndimage import gaussian_filter, rotate
from PIL import Image, ImageDraw, ImageFont
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [os.path.join(ROOT, 'tools')]
import group_grammar as GG
import logogram_cosiatec as LC
from wav_renderer import render_midi_to_wav

SEC = 60 / 132                                                           # 8분 하나 (원곡 494초 / 1089박)
T0, STEPS, FPS = 515, 44, 24
KG, KU = 18, 33                                                          # g 를 거는 박 · g⁻¹ 을 거는 박 (구간 안)
R16, L16 = GG.voices('Ryuichi_Sakamoto_-_hibari.mid')
MOD = sorted((s // 2, p, d / 2) for (s, p), d in R16 if s < 64)          # 두 손 같은 낱말 (8분 박, 음높이, 길이)
assert MOD == sorted((s // 2 - 33, p, d / 2) for (s, p), d in L16 if 66 <= s < 132)
HAND = {'R': dict(P=32, t0=0, rad=1.0, sc=1.0), 'L': dict(P=33, t0=33, rad=0.60, sc=0.75)}

def shift_at(k):                                                         # 왼손 시계를 늦춘 칸 수 (g 뒤 1, g⁻¹ 뒤 0)
    return 1 if KG <= k < KU else 0

# ── 소리: 박마다 두 손이 모듈의 어느 칸을 읽나 ───────────────────────────
notes = {'R': [], 'L': []}
for k in range(STEPS):
    for h, H in HAND.items():
        j = (T0 + k - H['t0'] - (shift_at(k) if h == 'L' else 0)) % H['P']
        if h == 'L' and k in (KG,): continue                             # g = 쉼 한 칸 끼우기 (이미 친 칸을 다시 치지 않는다)
        for s, p, d in MOD:
            if s == j: notes[h].append((k, p, min(d, STEPS - k)))
uni = lambda a, b: len({(k, p) for k, p, d in a} & {(k, p) for k, p, d in b})
same = {seg: uni([n for n in notes['R'] if lo <= n[0] < hi], [n for n in notes['L'] if lo <= n[0] < hi]) for seg, (lo, hi) in {'g 전': (0, KG), 'g 뒤': (KG, KU), 'g⁻¹ 뒤': (KU, STEPS)}.items()}
print('두 손 같은 음(박 수):', same)
od = os.path.join(ROOT, 'output', 'group_music'); os.makedirs(od, exist_ok=True)
mid, wav = os.path.join(od, 'demo_g.mid'), os.path.join(od, 'demo_g.wav')
GG.to_midi([[(2 * k, p, 2 * d) for k, p, d in notes[h]] for h in 'RL'], mid)
render_midi_to_wav(mid, wav)

# ── 그림: 고리 하나 = 낱말을 새긴 먹 고리 (한 번 그려 두고 돌린다) ─────────
LC.G, LC.L = 900, 1.6
def ring(H):
    F = np.zeros((LC.G, LC.G)); P, R, sc = H['P'], H['rad'], H['sc']
    ang = lambda j: np.pi / 2 - 2 * np.pi * j / P                        # 칸 j: 12시에서 시계 방향
    dens = np.zeros(P)
    for s, p, d in MOD:
        for q in range(int(s), int(s + d)): dens[q % P] += 1
    u = np.linspace(0, P, 1600, endpoint=False); a = ang(u)
    LC.brush(F, np.c_[R * np.cos(a), R * np.sin(a)], 0.020 * sc + 0.004, 0.004, press=0.35 + 0.75 * (dens[u.astype(int)] / dens.max()) ** 1.2)
    by = {}
    for s, p, d in MOD: by.setdefault(s, []).append(p)
    for s, ps in by.items():
        a = ang(s); c, sn = np.cos(a), np.sin(a); ps = sorted(ps)
        if len(ps) >= 3:                                                 # 화음 = 고리 위 굵은 덩이 + 베이스 = 안쪽 짧은 획
            LC.brush(F, [(c * (R - 0.01), sn * (R - 0.01)), (c * (R + 0.05 * sc), sn * (R + 0.05 * sc))], 0.030 * sc, 0.012 * sc)
            LC.brush(F, [(c * R, sn * R), (c * (R - 0.08 * sc), sn * (R - 0.08 * sc))], 0.012 * sc, 0.004)
        top = ps[-1]; ln = (0.06 + 0.012 * (top - 64)) * sc                # 선율 = 바깥으로 튀는 획(길수록 높다), 살짝 시계 방향으로 휜다
        b = [a - 0.10 * t for t in np.linspace(0, 1, 6)]
        LC.brush(F, [((R + 0.04 * sc + ln * t) * np.cos(bb), (R + 0.04 * sc + ln * t) * np.sin(bb)) for t, bb in zip(np.linspace(0, 1, 6), b)], 0.014 * sc, 0.003)
    return np.flipud(np.clip((gaussian_filter(F, 1.0) - 0.2) / 0.06, 0, 1))  # 위가 위로

MASK = {h: ring(H) for h, H in HAND.items()}
G = LC.G; px = (G - 1) / (2 * LC.L)
toxy = lambda a, r: (G / 2 + r * np.cos(a) * px, G / 2 - r * np.sin(a) * px)
yy, xx = np.mgrid[0:G, 0:G]; rr = np.hypot(xx - G / 2, yy - G / 2) / (G / 2)
PAPER = (np.array([240, 238, 233]) / 255 * (1 - 0.08 * rr[..., None] ** 2) * 255).astype(np.float32)
FONT = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 26); SMALL = ImageFont.truetype('C:/Windows/Fonts/malgun.ttf', 20)

def ease(x): x = np.clip(x, 0, 1); return x * x * (3 - 2 * x)
def lshift(tau):                                                         # 그림 속 왼손 늦춤: 0.35초 동안 부드럽게
    return ease((tau - KG * SEC) / 0.35) - ease((tau - KU * SEC) / 0.35)

tmp = tempfile.mkdtemp()
for f in range(STEPS * FPS * SEC.__ceil__() if False else int(STEPS * SEC * FPS)):
    tau = f / FPS; u = tau / SEC; k = int(u)
    img = PAPER.copy()
    for h, H in HAND.items():
        ph = (T0 + u - H['t0'] - (lshift(tau) if h == 'L' else 0)) % H['P']
        m = rotate(MASK[h], ph * 360 / H['P'], reshape=False, order=1)   # 지금 칸이 12시로 오게 돈다
        img = img * (1 - m[..., None]) + np.array([14, 15, 17], np.float32) * m[..., None]
    im = Image.fromarray(img.astype(np.uint8)); dr = ImageDraw.Draw(im, 'RGBA')
    x0, y0 = toxy(np.pi / 2, 1.38); x1, y1 = toxy(np.pi / 2, 1.24)
    dr.line([(x0, y0), (x1, y1)], fill=(150, 62, 28, 220), width=4)       # 바늘
    sounding = {}
    for h, H in HAND.items():
        for kk, p, d in notes[h]:
            if kk <= u < kk + d: sounding.setdefault(h, set()).add((kk, p))
    both = {(kk, p) for kk, p in sounding.get('R', set()) if (kk, p) in sounding.get('L', set()) and kk == k}
    for h, H in HAND.items():
        ph = (T0 + u - H['t0'] - (lshift(tau) if h == 'L' else 0)) % H['P']
        for kk, p in sounding.get(h, ()):
            j = (T0 + kk - H['t0'] - (shift_at(kk) if h == 'L' else 0)) % H['P']
            a = np.pi / 2 - 2 * np.pi * (j - ph) / H['P']; age = u - kk
            r_ = H['rad'] + (0.06 + 0.012 * (p - 64)) * H['sc'] * 0.6
            x, y = toxy(a, r_); g = max(0.0, 1 - age / 2.5); rad = 7 + 10 * g
            col = (232, 176, 40, int(230 * g + 25)) if (kk, p) in both or (age < 1 and (kk, p) in {(b0, b1) for b0, b1 in both}) else (255, 255, 255, int(200 * g))
            dr.ellipse([x - rad, y - rad, x + rad, y + rad], fill=col)
    for kk, p in both:
        x, y = toxy(np.pi / 2, 0.82); dr.ellipse([x - 26, y - 26, x + 26, y + 26], outline=(232, 176, 40, 200), width=4)
    # 손: g 와 g⁻¹ 을 거는 순간 왼손 고리를 잡고 한 칸 끈다
    for tg, sign, txt in ((KG * SEC, 1, '왼손 고리를 한 칸 돌린다 — g'), (KU * SEC, -1, '되돌린다 — g 의 역원')):
        if tg - 0.9 < tau < tg + 2.6:
            a0 = np.deg2rad(30); prog = ease((tau - tg) / 0.35); a = a0 - sign * prog * 2 * np.pi / 33
            x, y = toxy(a, 0.60); dr.ellipse([x - 22, y - 22, x + 22, y + 22], fill=(47, 107, 79, 120), outline=(47, 107, 79, 230), width=3)
            dr.text((40, G - 74), txt, font=FONT, fill=(34, 48, 42, 255))
    dr.text((40, 30), 'hibari · 같은 낱말, 오른손 32칸 · 왼손 33칸', font=SMALL, fill=(90, 96, 92, 255))
    dr.text((40, 58), '금빛 = 두 손이 같은 박에 같은 음', font=SMALL, fill=(150, 120, 40, 255))
    im.save(os.path.join(tmp, f'{f:04d}.png'))
mp4 = os.path.join(od, 'demo_g.mp4'); dur = STEPS * SEC
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-framerate', str(FPS), '-i', os.path.join(tmp, '%04d.png'), '-i', wav, '-t', f'{dur:.2f}',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '22', '-c:a', 'aac', '-b:a', '160k', '-shortest', mp4], check=True)
shutil.copy(os.path.join(tmp, f'{int((KG * SEC + 1.0) * FPS):04d}.png'), os.path.join(od, 'demo_g_frame.png'))
shutil.rmtree(tmp); print('저장', mp4, f'{dur:.1f}초')
