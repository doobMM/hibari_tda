"""
export_song_shapes.py — 13곡을 접어(song_fold.py) 웹 페이지 shape/ 가 읽는 자료를 만든다.

산출
  shape/data/shapes.json          곡마다 노드 자리(정수 ×scale)·색·시각(ms)·통계        ← 첫 화면이 읽는다
  shape/data/<slug>.notes.json    곡마다 음표(노드 번호·노드 안 어긋남 ms·음높이·길이 ms·세기·성부)와 건너뛰기 짝(닮음 ≥ 0.9)   ← 들을 때 읽는다
  docs/step3_data/song_shapes.json  매개변수와 곡별 수치 (원본 기록)

사용:  python experiments/export_song_shapes.py            # 13곡 전부
       python experiments/export_song_shapes.py hibari reich
"""
import os, sys, json, time, datetime
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import song_fold as sf

OUT = os.path.join(sf.ROOT, 'shape', 'data')
JUMP_SIM, JUMP_TOP = 0.9, 3


def export(slug):
    t0 = time.time()
    song, X, info, (rec, rsim, best, ns, tt) = sf.run(slug)
    T = len(X); col = sf.colors(song, ns, T, tt)
    sec = np.array([song['sec_at'](i * ns * tt) for i in range(T)])
    scale = float(np.abs(X).max() / 32000)
    geo = {'slug': slug, 'title': song['title'], 'composer': song['composer'], 'T': T, 'unit': info['unit'], 'scale': scale,
           'pos': np.round(X / scale).astype(int).ravel().tolist(),
           'rgb': np.round(col * 255).astype(int).ravel().tolist(),
           'ms': np.round(sec * 1000).astype(int).tolist(),
           'best': np.round(best * 100).astype(int).tolist(),          # 노드마다 가장 닮은 다른 시각과의 닮음 ×100
           'seconds': round(song['seconds'], 1), 'rec80': round(info['rec80'], 3), 'rec95': round(info['rec95'], 3),
           'radius': round(info['radius'], 2), 'voices': len(song['voices'])}
    # 음표
    N = {'node': [], 'off': [], 'pitch': [], 'dur': [], 'vel': [], 'voice': []}
    ev = sorted((float(b), int(p), float(s), float(ds), int(v), vi) for vi, vc in enumerate(song['voices']) for b, d, p, s, ds, v in vc)
    for b, p, s, ds, v, vi in ev:
        i = min(T - 1, int(round(b / tt)) // ns)
        N['node'].append(i); N['off'].append(int(round((s - sec[i]) * 1000))); N['pitch'].append(p)
        N['dur'].append(int(round(ds * 1000))); N['vel'].append(v); N['voice'].append(vi)
    # 건너뛰기 짝: 닮음 ≥ 0.9 인 짝을 노드마다 위에서 셋까지 (양방향)
    by = {}
    for (i, j), s in zip(rec, rsim):
        if s >= JUMP_SIM: by.setdefault(int(i), []).append((float(s), int(j))); by.setdefault(int(j), []).append((float(s), int(i)))
    ja, jb = [], []
    for i in sorted(by):
        for s, j in sorted(by[i], reverse=True)[:JUMP_TOP]: ja.append(i); jb.append(j)
    N['jump_a'] = ja; N['jump_b'] = jb
    json.dump(N, open(os.path.join(OUT, f'{slug}.notes.json'), 'w', encoding='utf8'), separators=(',', ':'))
    info.update({'notes': len(ev), 'jump_pairs': len(ja), 'jump_nodes': len(by), 'elapsed_s': round(time.time() - t0, 1)})
    print(f"{slug:8s} T={T:5d} 음표={len(ev):5d} 되풀이(≥0.8) {info['rec80']:.2f}  반지름 {info['radius']:.1f}  풀기 {info['iters']}회 (마지막 움직임 {info['move']:.4f})  "
          f"사슬 늘어남 p95 {info['chain_stretch_p95']:.2f}  {info['elapsed_s']}s", flush=True)
    return geo, info


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    want = sys.argv[1:] or [s[0] for s in sf.SONGS]
    path = os.path.join(OUT, 'shapes.json')
    old = json.load(open(path, encoding='utf8')) if os.path.exists(path) and sys.argv[1:] else {'songs': []}
    rec_path = os.path.join(sf.ROOT, 'docs', 'step3_data', 'song_shapes.json')
    oldrec = json.load(open(rec_path, encoding='utf8')) if os.path.exists(rec_path) and sys.argv[1:] else {'songs': {}}
    geos = {g['slug']: g for g in old['songs']}; infos = dict(oldrec['songs'])
    for slug in want:
        g, info = export(slug); geos[slug] = g; infos[slug] = {k: (round(v, 5) if isinstance(v, float) else v) for k, v in info.items()}
    order = [s[0] for s in sf.SONGS if s[0] in geos]
    json.dump({'unit': '8분음표 = 1', 'songs': [geos[s] for s in order]}, open(path, 'w', encoding='utf8'), ensure_ascii=False, separators=(',', ':'))
    json.dump({'generated_at': datetime.datetime.now().isoformat(timespec='seconds'), 'script': 'experiments/export_song_shapes.py + song_fold.py',
               'params': sf.DEF, 'status': '탐색적 — 매개변수는 미리보기를 눈으로 보고 골랐다. 견고성은 song_shape_checks.json',
               'songs': {s: infos[s] for s in order}}, open(rec_path, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print('저장', path, os.path.getsize(path), 'bytes ·', rec_path)
