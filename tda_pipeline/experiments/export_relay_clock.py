"""잇기 — 모듈 시계 판. hibari 의 시간(오른손 32 × 왼손 33)을 고리 모양 판으로 편다.  → sketch/data/relay_clock.json

칸 = (모듈 안 자리 4스텝 = 2박) × (곡의 어디쯤 — 왼손이 돈 바퀴 수 δ 를 8씩 묶은 띠).  각도 = 모듈 자리, 반지름 = 곡의 앞 → 뒤.
대목 t(8분음표 하나)에서 오른손 자리 a = t mod 32, 왼손 자리 b = t mod 33, δ = ⌊t / 33⌋ (어긋남 = (a − b) mod 32 = δ mod 32).
칸의 소리 = 그 띠의 첫 모듈(δ = 0·8·16·24)에서 그 자리부터 4스텝(원곡 음 그대로). 칸의 색 = 그 칸에 드는 대목들의 몸(shape/) 색 평균.
소리가 없는 칸(두 손이 함께 쉬는 곳)은 판에서 뺀다 → 구멍. 가운데도 구멍(모듈 한 바퀴). 고리가 구멍을 감으면(감김수 ≠ 0) 운다.
hibari 의 대답 무게 = 곡에서 그 칸 다음으로 실제로 넘어간 횟수(+ 바닥값은 페이지 쪽).

PREDICTION (돌리기 전에 적음, 2026-10-01)
  C1 칸 32개(8 × 4) 중 소리 없는 칸은 정확히 4개: (자리 3, 띠 0) · (7, 0) · (3, 2) · (7, 2) — 성부 0 의 쉼 12–15·28–31 이 δ = 0 과 16 에서 왼손의 쉼과 겹친다.
  C2 그중 띠 2 의 둘이 안쪽 구멍(창)이고, 띠 0 의 둘은 가운데 구멍에 붙는다 → 구멍은 가운데 + 창 2.
  C3 곡에서 칸이 바뀌는 넘어감의 95% 이상이 시계 방향(다음 자리)이다.
  C4 쉼이 아닌 여섯 자리의 베이스가 모듈 순서대로 미 · 파 · 솔 · 라 · 시 · 도.
결과(2026-10-01): C1·C2·C3 맞음(시계 방향 267/270 = 0.989). C4 틀림 — 한 칸에 화음이 둘(2박)이라 칸마다 베이스가 둘이다:
  첫 반 미·파 | 솔·라 | 시·도, 둘째 반 미·파 | 솔·라 | 시·라 (둘째 반은 도가 아니라 라로 내려앉는다). 판의 이름표는 두 베이스를 함께 적는다.
한계: 판의 큰 구멍은 PH 로 찾은 것이 아니라 악보의 주기(32)가 만든다(닮음 공간의 VR 에서는 모듈이 두드러진 구멍이 아니었다 — 2026-10-01 탐색).
      칸의 소리는 원곡 조각이다 — 새로운 것은 잇는 순서와 서로 다른 띠의 겹침이다.
실행: python experiments/export_relay_clock.py
"""
import os, json
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S, R, STEP, BAND = 8, 4, 4, 8
SOL = ['도', '도#', '레', '레#', '미', '파', '파#', '솔', '솔#', '라', '라#', '시']


def main():
    NT = json.load(open(os.path.join(ROOT, 'shape/data/hibari.notes.json'), encoding='utf-8'))
    G = next(s for s in json.load(open(os.path.join(ROOT, 'shape/data/shapes.json'), encoding='utf-8'))['songs'] if s['slug'] == 'hibari')
    T = G['T']; RGB = np.array(G['rgb'], float).reshape(T, 3)
    ev = {}
    for k in range(len(NT['node'])): ev.setdefault(NT['node'][k], []).append((NT['pitch'][k], NT['dur'][k], NT['vel'][k], NT['voice'][k], NT['off'][k]))
    a = np.arange(T) % 32; d = np.minimum(np.arange(T) // 33, 32)
    sec = a // STEP; band = np.minimum(d // BAND, R - 1); tile = band * S + sec

    tiles = []
    for r in range(R):
        for s in range(S):
            d0 = r * BAND; b = (s * STEP - d0) % 32; t0 = 33 * d0 + b          # 띠의 첫 모듈에서 오른손이 자리 s·4 에 있는 대목
            notes = [[i, p, int(du), int(v), int(vo), int(o)] for i in range(STEP) for (p, du, v, vo, o) in ev.get(t0 + i, [])]
            mem = np.where(tile == r * S + s)[0]
            bass = [SOL[min(p for i2, p, du, v, vo, o in notes if i2 == i and vo == 0) % 12] for i in range(0, STEP, 2) if any(i2 == i and vo == 0 for i2, p, du, v, vo, o in notes)]
            tiles.append({'s': s, 'r': r, 't0': int(t0), 'notes': notes, 'rgb': np.round(RGB[mem].mean(0)).astype(int).tolist(), 'n': int(len(mem)),
                          'bass': '·'.join(bass) or None})
    silent = [i for i, t in enumerate(tiles) if not t['notes']]
    succ = {}
    for t in range(T - 1):
        x, y = int(tile[t]), int(tile[t + 1])
        if x != y: succ[(x, y)] = succ.get((x, y), 0) + 1
    cw = sum(v for (x, y), v in succ.items() if y // S == x // S and (y % S) == (x % S + 1) % S); tot = sum(succ.values())
    lab0 = [tiles[s]['bass'] for s in range(S)]                        # 띠 0 (어긋남 0 = 두 손이 같이) 의 자리별 베이스
    out = {'song': 'hibari', 'sectors': S, 'rings': R, 'step': STEP, 'band': BAND, 'eighth_ms': round(60000 / 66 / 2, 3), 'tiles': tiles, 'silent': silent,
           'succ': [[x, y, v] for (x, y), v in sorted(succ.items())], 'bass_by_sector': lab0}
    os.makedirs(os.path.join(ROOT, 'sketch/data'), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, 'sketch/data/relay_clock.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    want = [3 + 0 * S, 7 + 0 * S, 3 + 2 * S, 7 + 2 * S]
    chk = {'prediction': __doc__.split('PREDICTION')[1].split('한계')[0].strip(),
           'silent_tiles': [[tiles[i]['s'], tiles[i]['r']] for i in silent], 'clockwise_share': round(cw / tot, 4), 'transitions': tot,
           'bass_by_sector': lab0, 'notes_per_tile': [len(t['notes']) for t in tiles],
           'C1': sorted(silent) == sorted(want), 'C2': sorted(i for i in silent if tiles[i]['r'] not in (0,)) == sorted([3 + 2 * S, 7 + 2 * S]),
           'C3': cw / tot >= 0.95, 'C4': [x for x in lab0 if x] == ['미', '파', '솔', '라', '시', '도'],
           'C4_note': '틀림 — 한 칸(4스텝)에 화음이 둘이라 칸마다 베이스가 둘이다. 첫 반 미·파|솔·라|시·도, 둘째 반 미·파|솔·라|시·라'}
    json.dump(chk, open(os.path.join(ROOT, 'docs/step3_data/relay_clock_checks.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('소리 없는 칸 (자리, 띠):', chk['silent_tiles'])
    print(f'시계 방향 넘어감 {cw}/{tot} = {cw / tot:.3f}')
    print('띠 0 자리별 베이스:', lab0)
    print('칸마다 음 수:', chk['notes_per_tile'])
    print({k: chk[k] for k in ('C1', 'C2', 'C3', 'C4')})


if __name__ == '__main__':
    main()
