"""
build_motif_listening_page.py — "모티브를 주면 음악이 이렇게 통제된다" 페이지

`experiments/motif_control.py` 의 결과를 읽어
  · WAV → OGG 압축 (ffmpeg)
  · 모티브마다 [모티브 패치] → [뼈대] → [변주 1] → [변주 2] 를
    **들판 그림 + 재생 버튼** 으로 나란히 놓는다
는 하나의 HTML 을 만든다.

들판 렌더링 규칙은 대시보드 `overlap-editor.js` 의 Persistent Bloom 과 동일하다
(활성=성장/비활성=감쇠 에너지 적분, 이웃 밀도가 색을 결정). 고정된 모티브 자리는
옅은 띠로 표시해 "여기는 내가 정한 곳"이 보이게 한다.

실행:  python tools/build_motif_listening_page.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
TDA_ROOT = os.path.dirname(TOOLS_DIR)
RESULTS = os.path.join(TDA_ROOT, "docs", "step3_data", "motif_control_results.json")
OUT_DIR = os.path.join(TDA_ROOT, "output", "topo_diffusion")
PAGE = os.path.join(OUT_DIR, "motif.html")

ROLE_INFO = {
    "skeleton": ("뼈대 — 모티브만", "내가 정한 것만 남기고 나머지는 비웠다. 이게 지시다."),
    "v1": ("변주 1", "같은 지시, 다른 씨앗. 모티브는 그대로 살아 있다."),
    "v2": ("변주 2", "또 다른 씨앗. 사이를 채운 내용만 달라진다."),
}


def to_ogg(wav_path: str, ogg_path: str, quality: int = 3) -> bool:
    # q:a 3 ≈ 110초에 0.7MB. 12트랙을 저장소에 올려도 10MB 이내.
    if not os.path.exists(wav_path) or not shutil.which("ffmpeg"):
        return False
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav_path,
                        "-c:a", "libvorbis", "-q:a", str(quality), ogg_path],
                       capture_output=True, text=True)
    return r.returncode == 0


HEAD = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>모티브를 주면 음악이 통제된다</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&family=Noto+Serif+KR:wght@500;600&display=swap" rel="stylesheet">
<style>
  :root{--bg:#f5f8f2;--fg:#1b2419;--muted:#5c6b57;--line:#d6e0cd;--card:#fff;
        --moss:#1f3d24;--grass:#4a7c4e;--sprout:#8fbf6a;--accent:#2f6b3a;--fix:#c9dfc0;}
  @media (prefers-color-scheme:dark){:root{--bg:#0f1410;--fg:#e6ede2;--muted:#8fa088;
        --line:#243021;--card:#161d15;--accent:#7fb069;--fix:#2b4a2c;}}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);line-height:1.7;
       font-family:"Noto Sans KR",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
  .wrap{max-width:900px;margin:0 auto;padding:48px 20px 90px}
  h1{font-family:"Noto Serif KR",Georgia,serif;font-size:clamp(24px,5.2vw,36px);
     margin:0 0 10px;letter-spacing:-.02em}
  .lede{color:var(--muted);margin:0 0 14px;font-size:15px}
  .howto{border:1px solid var(--line);border-radius:12px;padding:16px 18px;
         margin:0 0 36px;font-size:14px;background:var(--card)}
  .howto b{color:var(--accent)}
  .motif{margin:0 0 44px}
  .mhead{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:6px}
  .mname{font-family:"Noto Serif KR",Georgia,serif;font-size:22px;font-weight:600}
  .badge{font-size:11px;padding:3px 10px;border-radius:99px;border:1px solid var(--line);
         color:var(--muted)}
  .badge.alien{background:var(--accent);color:#fff;border-color:var(--accent)}
  .mdesc{color:var(--muted);font-size:14px;margin:0 0 14px}
  .patchrow{display:flex;align-items:center;gap:14px;margin-bottom:16px;flex-wrap:wrap}
  .patchrow canvas{width:130px;height:64px;border:1px solid var(--line);border-radius:8px;
                   background:var(--bg)}
  .patchrow .pl{font-size:12.5px;color:var(--muted)}
  .track{background:var(--card);border:1px solid var(--line);border-radius:12px;
         padding:16px 18px;margin-bottom:12px}
  .track.sk{border-style:dashed}
  .thead{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
  .ttitle{font-weight:600;font-size:16px}
  .tdesc{color:var(--muted);font-size:13.5px;margin:2px 0 12px}
  .track canvas{width:100%;height:120px;display:block;border-radius:8px;background:var(--bg);
                border:1px solid var(--line)}
  audio{width:100%;margin-top:12px}
  .stats{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}
  .stat{font-size:11.5px;color:var(--muted);border:1px solid var(--line);border-radius:6px;
        padding:4px 9px}
  .stat b{color:var(--fg);font-weight:600;font-variant-numeric:tabular-nums}
  table{width:100%;border-collapse:collapse;font-size:13.5px;margin:10px 0 0}
  th,td{text-align:right;padding:7px 10px;border-bottom:1px solid var(--line)}
  th:first-child,td:first-child{text-align:left}
  th{color:var(--muted);font-weight:500}
  td b{font-variant-numeric:tabular-nums}
  .sec{font-family:"Noto Serif KR",Georgia,serif;font-size:20px;font-weight:600;
       margin:52px 0 8px}
  .note{font-size:13px;color:var(--muted);border-left:3px solid var(--line);
        padding:3px 0 3px 14px;margin:14px 0 0}
  @media(max-width:480px){.wrap{padding:28px 14px 64px}.track canvas{height:96px}}
</style>
<div class="wrap">
<h1>모티브를 주면, 음악이 통제된다</h1>
<p class="lede">hibari 에서 뽑은 <b>중심 모티브</b>를 중첩행렬에 심고, 나머지는 디퓨전이 채웁니다.
   모티브는 그대로 남고 사이만 달라집니다.</p>
<div class="howto">
  <b>듣는 순서</b> — 각 모티브마다 ①<b>뼈대</b>(내가 정한 것만) → ②<b>변주 1</b> → ③<b>변주 2</b>.
  뼈대를 먼저 들으면 되풀이되는 몸짓이 귀에 박히고, 변주에서 그게 어떻게 살아남는지 들립니다.<br>
  <b>그림 읽는 법</b> — 줄기 하나가 위상적 고리 하나. 옅은 세로 띠가 <b>내가 고정한 자리</b>이고,
  그 밖은 모델이 채운 곳입니다.
</div>
__BODY__
</div>
<script>
const TRACKS = __DATA__;
const GROWTH = 0.30, MEMORY = 0.70;

function palette(){
  const cs = getComputedStyle(document.documentElement);
  const hx = n => { const s = cs.getPropertyValue(n).trim() || '#4a7c4e';
    return [parseInt(s.slice(1,3),16),parseInt(s.slice(3,5),16),parseInt(s.slice(5,7),16)]; };
  return {moss:hx('--moss'), grass:hx('--grass'), sprout:hx('--sprout'), fix:hx('--fix')};
}

function drawMeadow(cv, bits, T, K, maskBits){
  const dpr = Math.min(2, window.devicePixelRatio||1);
  // 폭이 0으로 잡히는 환경(정적 스냅샷 렌더러, 접힌 컨테이너 등)에서도
  // 빈 캔버스를 남기지 않도록 단계적으로 대체 폭을 찾는다.
  const w = cv.clientWidth || cv.offsetWidth
            || (cv.parentElement && cv.parentElement.clientWidth) || 760;
  const h = cv.clientHeight || cv.offsetHeight || 120;
  if(!w||!h) return;
  cv.width = w*dpr; cv.height = h*dpr;
  const g = cv.getContext('2d');
  g.setTransform(dpr,0,0,dpr,0,0); g.clearRect(0,0,w,h);
  const P = palette();

  // 고정 구간을 옅은 띠로 — "여기는 내가 정한 곳"
  if(maskBits){
    g.fillStyle = `rgba(${P.fix[0]},${P.fix[1]},${P.fix[2]},0.55)`;
    let run = -1;
    for(let t=0;t<=T;t++){
      let any = false;
      if(t<T) for(let c=0;c<K;c++) if(maskBits[t*K+c]==='1'){ any=true; break; }
      if(any && run<0) run = t;
      else if(!any && run>=0){ g.fillRect(run*w/T,0,(t-run)*w/T,h); run = -1; }
    }
  }

  const energy = new Float32Array(T*K);
  for(let c=0;c<K;c++){ let e=0;
    for(let t=0;t<T;t++){ e = bits[t*K+c]==='1' ? Math.min(1,e+GROWTH) : e*MEMORY;
      energy[t*K+c]=e; } }
  const dens = new Float32Array(T*K); let dMax=0;
  for(let c=0;c<K;c++) for(let t=0;t<T;t++){
    let s=0;
    for(let dt=-3;dt<=3;dt++) for(let dc=-1;dc<=1;dc++){
      const tt=t+dt, cc=c+dc;
      if(tt<0||tt>=T||cc<0||cc>=K) continue;
      s += energy[tt*K+cc];
    }
    dens[t*K+c]=s; if(s>dMax) dMax=s;
  }
  dMax = dMax||1;

  const cw = w/T, base = h-5, maxH = h-13;
  const lerp=(a,b,u)=>[a[0]+(b[0]-a[0])*u, a[1]+(b[1]-a[1])*u, a[2]+(b[2]-a[2])*u];
  for(let c=0;c<K;c++) for(let t=0;t<T;t++){
    const e = energy[t*K+c]; if(e<0.04) continue;
    const d = dens[t*K+c]/dMax;
    const col = d<0.5 ? lerp(P.sprout,P.grass,d/0.5) : lerp(P.grass,P.moss,(d-0.5)/0.5);
    const x = t*cw + cw*0.5;
    const bh = maxH*(0.25+0.75*e)*(0.55+0.45*(1-c/K));
    const wind = (Math.sin(x*0.013+c*1.7)+0.5*Math.sin(x*0.037))*bh*0.16;
    g.strokeStyle = `rgb(${col[0]|0},${col[1]|0},${col[2]|0})`;
    g.lineWidth = Math.max(0.9, cw*0.55); g.lineCap='round';
    g.beginPath(); g.moveTo(x,base);
    g.quadraticCurveTo(x+wind*0.4, base-bh*0.55, x+wind, base-bh); g.stroke();
    if(t>0 && bits[t*K+c]==='1' && bits[(t-1)*K+c]==='0'){
      g.fillStyle = `rgba(${P.sprout[0]},${P.sprout[1]},${P.sprout[2]},0.85)`;
      g.beginPath(); g.arc(x+wind, base-bh, Math.max(1.1,cw*0.5),0,6.284); g.fill();
    }
  }
}

function render(){
  document.querySelectorAll('canvas[data-bits]').forEach(cv=>{
    drawMeadow(cv, cv.dataset.bits, +cv.dataset.t, +cv.dataset.k, cv.dataset.mask||null);
  });
}
render();

// 레이아웃이 아직 폭을 주지 않은 상태(폰트 로딩 중, 접힌 컨테이너, 0폭 뷰포트 등)에서는
// drawMeadow 가 그냥 건너뛴다. 폭이 생기는 순간 다시 그리도록 관찰한다.
if (window.ResizeObserver){
  const ro = new ResizeObserver(entries=>{
    entries.forEach(en=>{
      const cv = en.target;
      if(cv.clientWidth > 0 && cv.clientHeight > 0){
        drawMeadow(cv, cv.dataset.bits, +cv.dataset.t, +cv.dataset.k, cv.dataset.mask||null);
      }
    });
  });
  document.querySelectorAll('canvas[data-bits]').forEach(cv=>ro.observe(cv));
}
addEventListener('load', render);
if (document.fonts && document.fonts.ready) document.fonts.ready.then(render);
addEventListener('resize', render);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', render);
document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>{
  document.querySelectorAll('audio').forEach(o=>{ if(o!==a) o.pause(); });
}));
</script>
"""


def main() -> None:
    if not os.path.exists(RESULTS):
        sys.exit(f"결과 없음: {RESULTS} — experiments/motif_control.py 를 먼저 실행")
    with open(RESULTS, "r", encoding="utf-8") as f:
        res = json.load(f)

    motifs = res["motifs"]
    control = res.get("control", {})
    tracks = res.get("tracks", [])
    by_motif = {}
    for t in tracks:
        by_motif.setdefault(t["motif"], []).append(t)

    body, data = [], []
    for name in sorted(by_motif.keys()):
        mo = motifs.get(name, {})
        ctl = control.get(name, {})
        alien = mo.get("synthetic")
        origin = ("hibari 밖에서 온 낯선 지시 — 원곡의 중심 모티브들이 한 번도 함께 쓰지 않는 고리 조합"
                  if alien else
                  f"hibari t={mo.get('source_t')} 에서 뽑은 몸짓 · 곡 안에서 {mo.get('recurrence',0):.0f}회 되풀이")
        body.append(f'<div class="motif"><div class="mhead"><span class="mname">모티브 {name}</span>'
                    f'<span class="badge{" alien" if alien else ""}">'
                    f'{"대조군" if alien else "hibari 중심 모티브"}</span>'
                    f'<span class="badge">고리 {mo.get("active_cycles")}</span></div>'
                    f'<p class="mdesc">{origin}</p>'
                    f'<div class="patchrow">'
                    f'<canvas data-bits="{mo.get("bits","")}" data-t="8" data-k="14"></canvas>'
                    f'<span class="pl">← 이 8스텝(1마디) 패치가 지시입니다.<br>'
                    f'32스텝마다 되풀이해 심었습니다 (시간의 26.7%).</span></div>')

        for role in ("skeleton", "v1", "v2"):
            tr = next((t for t in by_motif[name] if t.get("role") == role), None)
            if not tr:
                continue
            title, desc = ROLE_INFO[role]
            src = ""
            if tr.get("wav"):
                wav_abs = os.path.join(OUT_DIR, tr["wav"])
                ogg_abs = os.path.splitext(wav_abs)[0] + ".ogg"
                if to_ogg(wav_abs, ogg_abs):
                    src = os.path.basename(ogg_abs)
                    print(f"  {tr['track']:<20} → {src}  {os.path.getsize(ogg_abs)/1e6:.1f}MB")
                else:
                    src = tr["wav"]
            stats = [f"길이 <b>{tr.get('duration_sec',0):.0f}초</b>",
                     f"음 <b>{tr.get('n_notes',0)}</b>개",
                     f"협화도 <b>{tr.get('consonance',0):.3f}</b>",
                     f"음고 JS <b>{tr.get('js',0):.4f}</b>",
                     f"온도 <b>{tr.get('temperature',0):.1f}</b>"]
            body.append(
                f'<div class="track{" sk" if role=="skeleton" else ""}">'
                f'<div class="thead"><span class="ttitle">{title}</span></div>'
                f'<p class="tdesc">{desc}</p>'
                f'<canvas data-bits="{tr["om_bits"]}" data-t="{tr["om_T"]}" '
                f'data-k="{tr["om_K"]}" data-mask="{tr.get("mask_bits","")}"></canvas>'
                + (f'<audio controls preload="none" src="{src}"></audio>' if src else "")
                + '<div class="stats">' + "".join(f'<span class="stat">{s}</span>' for s in stats)
                + "</div></div>")

        if ctl:
            body.append(
                f'<table><tr><th>모티브 {name} 통제 지표</th><th>값</th><th>뜻</th></tr>'
                f'<tr><td>모티브 보존</td><td><b>{ctl.get("fidelity",0)*100:.1f}%</b></td>'
                f'<td>내가 정한 자리가 그대로 남았는가</td></tr>'
                f'<tr><td>자유영역 변주간 차이</td><td><b>{ctl.get("free_region_difference",0)*100:.1f}%</b></td>'
                f'<td>나머지는 매번 달라지는가 (통제 ≠ 복제)</td></tr>'
                f'<tr><td>시간 연속성</td><td><b>{ctl.get("temporal_autocorr",0):.3f}</b></td>'
                f'<td>원곡 0.814</td></tr>'
                f'<tr><td>고리당 활성 구간</td><td><b>{ctl.get("h0_runs_per_cycle",0):.2f}</b></td>'
                f'<td>원곡 5.68</td></tr></table>')
        body.append("</div>")

        data.append(name)

    cross = res.get("cross_motif_profile_js", {})
    if cross:
        rows = "".join(f"<tr><td>{k}</td><td><b>{v:.5f}</b></td></tr>" for k, v in cross.items())
        body.append('<div class="sec">모티브를 바꾸면 결과가 달라지는가</div>'
                    '<p class="mdesc">서로 다른 모티브가 만든 고리 활성 프로파일 사이의 '
                    'Jensen-Shannon 거리입니다. 클수록 지시가 결과를 실제로 갈랐다는 뜻입니다.</p>'
                    f'<table><tr><th>모티브 쌍</th><th>프로파일 JS</th></tr>{rows}</table>')

    knob = res.get("coverage_knob", {})
    if knob:
        rows = "".join(
            f'<tr><td>{k}</td><td><b>{v["mask_fraction"]*100:.1f}%</b></td>'
            f'<td><b>{v["fidelity"]*100:.1f}%</b></td>'
            f'<td><b>{v["free_region_difference"]*100:.1f}%</b></td></tr>'
            for k, v in knob.items())
        body.append('<div class="sec">통제 강도 노브</div>'
                    '<p class="mdesc">모티브를 얼마나 넓게 고정하느냐가 곧 통제의 세기입니다. '
                    '넓게 잡을수록 내 뜻대로지만 변주의 자유도는 줄어듭니다.</p>'
                    f'<table><tr><th>배치</th><th>고정 비율</th><th>모티브 보존</th>'
                    f'<th>자유영역 차이</th></tr>{rows}</table>')

    body.append('<p class="note">방법 — 학습된 디노이저는 그대로 두고, 매 디노이징 스텝에서 '
                '고정 영역만 원본 모티브로 덮어씁니다(RePaint). 재학습이 없으므로 '
                '모티브를 바꾸는 데 드는 비용은 0 입니다. 곡 길이는 30초 창으로 학습한 모델을 '
                'MultiDiffusion 으로 이어 붙여 얻었습니다.</p>')

    # 캔버스는 DOM 의 data-* 로 그리므로 별도 데이터 주입은 필요 없다
    html = HEAD.replace("__BODY__", "\n".join(body)).replace("__DATA__", json.dumps(data))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n페이지: {PAGE}  ({os.path.getsize(PAGE)/1024:.0f}KB)")


if __name__ == "__main__":
    main()
