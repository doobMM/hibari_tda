"""
build_topo_listening_page.py — "보이는 들판 = 들리는 음악" 비교 페이지

`make_topo_music.py` 가 남긴 매니페스트를 읽어
  · WAV → OGG 압축 (ffmpeg)
  · 트랙별 **중첩행렬을 들판으로 그린 그림 + 그 들판이 만든 음악의 재생 버튼**
을 하나의 HTML 로 묶는다.

들판 렌더링은 대시보드 `overlap-editor.js` 의 Persistent Bloom 과 동일한 규칙
(활성=성장 / 비활성=감쇠 에너지 적분, 이웃 밀도가 색을 결정)을 따른다.
같은 데이터를 같은 방식으로 그리므로, 대시보드에서 본 들판과 여기 들판은
읽는 법이 같다.

실행:  python tools/build_topo_listening_page.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
TDA_ROOT = os.path.dirname(TOOLS_DIR)
MANIFEST = os.path.join(TDA_ROOT, "docs", "step3_data", "topo_music_manifest.json")
OUT_DIR = os.path.join(TDA_ROOT, "output", "topo_diffusion")
PAGE = os.path.join(OUT_DIR, "listen.html")

TRACK_INFO = {
    "REAL_30": ("원곡의 들판 · 30초", "기준선",
                "hibari 자신의 중첩행렬 한 조각. 지금까지 우리가 가지고 있던 것."),
    "CONV_30": ("1D-conv 디노이저 · 30초", "아키텍처만",
                "시간축을 conv 로 본 디노이저. 위상 손실은 아직 없음 — 아키텍처 교체 효과만."),
    "FULL_30": ("위상 손실 디퓨전 · 30초", "이번 접목",
                "매 디노이징 스텝마다 persistent homology 를 손실로 되먹인 결과."),
    "FULL_LONG": ("위상 손실 + MultiDiffusion · 1분 50초", "★ 본편",
                  "30초 창으로 학습한 모델이 겹치는 창들을 융합해 이어붙인 긴 들판."),
    "REAL_LONG": ("원곡의 들판 · 1분 50초", "본편의 기준선",
                  "같은 길이의 원곡 중첩행렬. 본편과 직접 비교용."),
}
ORDER = ["FULL_LONG", "REAL_LONG", "FULL_30", "CONV_30", "REAL_30"]


def to_ogg(wav_path: str, ogg_path: str, quality: int = 4) -> bool:
    if not os.path.exists(wav_path):
        return False
    if not shutil.which("ffmpeg"):
        print("  ffmpeg 없음 — WAV 그대로 사용")
        return False
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path,
                        "-c:a", "libvorbis", "-q:a", str(quality), ogg_path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ffmpeg 실패: {r.stderr.strip()[:160]}")
        return False
    return True


PAGE_TMPL = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>들판과 그 소리 — 위상 손실 디퓨전</title>
<style>
  :root {
    --bg:#f5f8f2; --fg:#1b2419; --muted:#5c6b57; --line:#d6e0cd;
    --card:#ffffff; --moss:#1f3d24; --grass:#4a7c4e; --sprout:#8fbf6a;
    --accent:#2f6b3a;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0f1410; --fg:#e6ede2; --muted:#8fa088; --line:#243021;
            --card:#161d15; --accent:#7fb069; }
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font-family:"Noto Sans KR",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
         line-height:1.7; }
  .wrap { max-width:860px; margin:0 auto; padding:48px 20px 80px; }
  h1 { font-family:"Noto Serif KR",Georgia,serif; font-size:clamp(24px,5vw,34px);
       margin:0 0 8px; letter-spacing:-.02em; }
  .lede { color:var(--muted); margin:0 0 40px; font-size:15px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:14px;
          padding:22px; margin-bottom:26px; }
  .card.hero { border-color:var(--accent); border-width:2px; }
  .head { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin-bottom:4px; }
  .title { font-family:"Noto Serif KR",Georgia,serif; font-size:19px; font-weight:600; }
  .tag { font-size:11px; padding:2px 9px; border-radius:99px; background:var(--accent);
         color:#fff; white-space:nowrap; }
  .desc { color:var(--muted); font-size:14px; margin:6px 0 16px; }
  canvas { width:100%; height:150px; display:block; border-radius:9px;
           background:var(--bg); border:1px solid var(--line); }
  audio { width:100%; margin-top:14px; }
  .stats { display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }
  .stat { font-size:12px; color:var(--muted); border:1px solid var(--line);
          border-radius:7px; padding:5px 10px; }
  .stat b { color:var(--fg); font-weight:600; font-variant-numeric:tabular-nums; }
  .note { font-size:13px; color:var(--muted); border-left:3px solid var(--line);
          padding:2px 0 2px 14px; margin:40px 0 0; }
  @media (max-width:480px) { .wrap { padding:28px 14px 60px; } canvas { height:120px; } }
</style>
<div class="wrap">
  <h1>들판과 그 소리</h1>
  <p class="lede">각 카드의 그림은 <b>중첩행렬</b>이고, 그 아래 소리는 <b>바로 그 중첩행렬로 만든 음악</b>입니다.
     줄기 하나가 위상적 고리 하나 — 깨어 있으면 자라고, 잠들면 낮아집니다.
     그림이 성길수록 소리도 성기고, 짙게 겹친 곳에서 화음이 두꺼워집니다.</p>
  __CARDS__
  <p class="note">선별 방식 — 트랙마다 40개를 생성해, 원곡과의 음고분포 충실도(JS) 상위 절반만 남기고
     그중 <b>협화도</b>가 가장 높은 하나를 골랐습니다. 협화도는 이전 미적 지표 실험에서
     유일하게 검증을 통과한 성분이라 이것만 씁니다.<br>
     30초 트랙의 JS 가 전곡 기록(0.009)보다 큰 것은 정상입니다 — 짧을수록 음고분포 추정이 거칠어집니다.
     같은 길이끼리만 비교하세요.</p>
</div>
<script>
const TRACKS = __DATA__;

// 대시보드 Persistent Bloom 과 동일 규칙
const GROWTH = 0.30, MEMORY = 0.70;

function drawMeadow(cv, bits, T, K) {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const w = cv.clientWidth, h = cv.clientHeight;
  cv.width = w * dpr; cv.height = h * dpr;
  const g = cv.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);

  const cs = getComputedStyle(document.documentElement);
  const moss = cs.getPropertyValue('--moss').trim() || '#1f3d24';
  const grass = cs.getPropertyValue('--grass').trim() || '#4a7c4e';
  const sprout = cs.getPropertyValue('--sprout').trim() || '#8fbf6a';
  const hex = s => [parseInt(s.slice(1,3),16), parseInt(s.slice(3,5),16), parseInt(s.slice(5,7),16)];
  const [m0,m1,m2] = hex(moss), [g0,g1,g2] = hex(grass), [s0,s1,s2] = hex(sprout);

  // 에너지 적분 — 활성이면 자라고 비활성이면 감쇠
  const energy = new Float32Array(T * K);
  for (let c = 0; c < K; c++) {
    let e = 0;
    for (let t = 0; t < T; t++) {
      const a = bits[t * K + c] === '1';
      e = a ? Math.min(1, e + GROWTH) : e * MEMORY;
      energy[t * K + c] = e;
    }
  }
  // 이웃 밀도 (수평 ±3 / 수직 ±1)
  const dens = new Float32Array(T * K);
  let dMax = 0;
  for (let c = 0; c < K; c++) for (let t = 0; t < T; t++) {
    let s = 0;
    for (let dt = -3; dt <= 3; dt++) for (let dc = -1; dc <= 1; dc++) {
      const tt = t + dt, cc = c + dc;
      if (tt < 0 || tt >= T || cc < 0 || cc >= K) continue;
      s += energy[tt * K + cc];
    }
    dens[t * K + c] = s;
    if (s > dMax) dMax = s;
  }
  dMax = dMax || 1;

  const cw = w / T, base = h - 6, maxH = h - 16;
  for (let c = 0; c < K; c++) {
    for (let t = 0; t < T; t++) {
      const e = energy[t * K + c];
      if (e < 0.04) continue;
      const d = dens[t * K + c] / dMax;
      // 빽빽하면 짙은 이끼, 홀로 서면 밝은 새싹
      let r, gg, b;
      if (d < 0.5) { const u = d / 0.5;
        r = s0 + (g0-s0)*u; gg = s1 + (g1-s1)*u; b = s2 + (g2-s2)*u; }
      else { const u = (d - 0.5) / 0.5;
        r = g0 + (m0-g0)*u; gg = g1 + (m1-g1)*u; b = g2 + (m2-g2)*u; }
      const x = t * cw + cw * 0.5;
      const bh = maxH * (0.25 + 0.75 * e) * (0.55 + 0.45 * (1 - c / K));
      const wind = (Math.sin(x * 0.013 + c * 1.7) + 0.5 * Math.sin(x * 0.037)) * bh * 0.16;
      g.strokeStyle = `rgb(${r|0},${gg|0},${b|0})`;
      g.lineWidth = Math.max(0.9, cw * 0.55);
      g.lineCap = 'round';
      g.beginPath();
      g.moveTo(x, base);
      g.quadraticCurveTo(x + wind * 0.4, base - bh * 0.55, x + wind, base - bh);
      g.stroke();
      // 새로 켜진 자리에 꽃
      if (t > 0 && bits[t*K+c] === '1' && bits[(t-1)*K+c] === '0') {
        g.fillStyle = `rgba(${s0},${s1},${s2},0.85)`;
        g.beginPath(); g.arc(x + wind, base - bh, Math.max(1.1, cw*0.5), 0, 6.284); g.fill();
      }
    }
  }
}

function render() {
  document.querySelectorAll('canvas[data-track]').forEach(cv => {
    const t = TRACKS.find(x => x.track === cv.dataset.track);
    if (t) drawMeadow(cv, t.om_bits, t.om_T, t.om_K);
  });
}
render();
addEventListener('resize', render);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', render);
// 재생 중인 트랙은 하나만
document.querySelectorAll('audio').forEach(a => a.addEventListener('play', () => {
  document.querySelectorAll('audio').forEach(o => { if (o !== a) o.pause(); });
}));
</script>
"""


def main() -> None:
    if not os.path.exists(MANIFEST):
        sys.exit(f"매니페스트 없음: {MANIFEST} — make_topo_music.py 를 먼저 실행")
    with open(MANIFEST, "r", encoding="utf-8") as f:
        man = json.load(f)

    tracks = {t["track"]: t for t in man["tracks"]}
    cards, data = [], []

    for name in ORDER:
        t = tracks.get(name)
        if not t:
            continue
        title, tag, desc = TRACK_INFO.get(name, (name, "", ""))

        audio_src = ""
        wav_rel = t.get("wav")
        if wav_rel:
            wav_abs = os.path.join(TDA_ROOT, wav_rel)
            ogg_abs = os.path.splitext(wav_abs)[0] + ".ogg"
            if to_ogg(wav_abs, ogg_abs):
                audio_src = os.path.basename(ogg_abs)
                print(f"  {name:<10} → {audio_src}  {os.path.getsize(ogg_abs)/1e6:.1f}MB")
            else:
                audio_src = os.path.basename(wav_abs)

        st = t.get("om_stats", {})
        stats = [
            f"길이 <b>{t.get('duration_sec', 0):.0f}초</b>",
            f"음 <b>{t.get('n_notes', 0)}</b>개",
            f"협화도 <b>{t.get('consonance', 0):.3f}</b>",
            f"음고 JS <b>{t.get('js', 0):.4f}</b>",
            f"스텝당 밀도 <b>{st.get('density_per_step', 0):.2f}</b>",
            f"시간 연속성 <b>{st.get('temporal_autocorr', 0):.3f}</b>",
        ]
        cards.append(
            f'<div class="card{" hero" if name == "FULL_LONG" else ""}">'
            f'<div class="head"><span class="title">{title}</span>'
            f'<span class="tag">{tag}</span></div>'
            f'<p class="desc">{desc}</p>'
            f'<canvas data-track="{name}"></canvas>'
            + (f'<audio controls preload="none" src="{audio_src}"></audio>' if audio_src else "")
            + '<div class="stats">' + "".join(f'<span class="stat">{s}</span>' for s in stats)
            + "</div></div>"
        )
        data.append({"track": name, "om_bits": t["om_bits"],
                     "om_T": t["om_T"], "om_K": t["om_K"]})

    html = (PAGE_TMPL
            .replace("__CARDS__", "\n  ".join(cards))
            .replace("__DATA__", json.dumps(data, ensure_ascii=False)))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n페이지: {PAGE}  ({os.path.getsize(PAGE)/1024:.0f}KB)")


if __name__ == "__main__":
    main()
