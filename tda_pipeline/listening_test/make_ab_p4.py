"""make_ab_p4.py — P4 반복 검정: 원곡 OM vs 디퓨전 OM, 6쌍

왜 다시 하는가
──────────────
2026-08-15 블라인드 A/B 의 P4 에서 **원곡 OM 이 디퓨전 OM 을 이겼다.**
디퓨전 라인 전체의 존재 이유에 직결되는 쌍인데 **관측이 1회뿐**이라
"그 시드가 유난히 잘/못 나온 연주" 였을 가능성을 배제할 수 없다.

설계 (이전 판에서 고친 것)
──────────────────────────
1. **temperature=1.0.** 이전 자극은 전부 T=3.0 이었는데 그 값의 근거는 철회됐고
   (§7.7.3 은 풀을 한 번도 뽑지 않은 설정이었다), 풀이 실제로 열리는 설정에서는
   T=1.0 이 단조 우세하다. 디퓨전 OM 쪽이 zero-row 가 많아 **비대칭으로 개입**했다.

2. **쌍이 분석 단위다.** 각 쌍은 창·시드·instLen 을 두 팔이 **공유**하고
   **OM 출처만 다르다.** 창과 모티브는 쌍마다 바꾼다 — 쌍 내부 대조는 그대로 통제되고
   쌍 사이로는 일반화가 넓어진다(같은 14.5초를 6번 듣는 지루함도 없다).

3. **T=32 = 정확히 한 구조 주기** (MODULES 32개), 약 14.5초.
   6쌍이면 오디오 약 3분 — 남에게 부탁할 수 있는 길이다. 이전 판은 5쌍×27초로 10분이었다.

4. 원곡 창은 **32의 배수**(BASE=192)에서 잘라 위상을 맞춘다.
   디퓨전 창도 모티브 배치 지점(0,32,64,…)에 맞춰 각 창이 모티브 1회를 포함한다.

실행:
  python listening_test/make_ab_p4.py                     # 기본 시드
  python listening_test/make_ab_p4.py --seeds 11,22,33,44,55,66
  python listening_test/make_ab_p4.py --shuffle-seed 777  # A/B 배치만 다시 섞기
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_ROOT = _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__)))
_rp_sys.path.insert(0, _ROOT)
_rp_sys.path.insert(0, _rp_os.path.join(_ROOT, "experiments"))
_rp_sys.path.insert(0, _rp_os.path.join(_ROOT, "tools"))
_rp_sys.path.insert(0, _rp_os.path.dirname(_rp_os.path.abspath(__file__)))
# --- end path_bootstrap ---

import argparse
import json
import os
import pickle
import random

import numpy as np

from run_topo_diffusion import CACHE_DIR, CACHE_NAME, REAL_TAU, TDA_ROOT, load_continuous_om
import run_dft_gap0_suite as suite
from make_topo_music import SEC_PER_8TH, render_wav, write_midi
from make_ab_check import bits, gen, to_ogg

OUT = os.path.join(TDA_ROOT, "output", "ab_p4")
MOTIF_JSON = os.path.join(TDA_ROOT, "docs", "step3_data", "motif_control_results.json")

T = 32                      # 한 구조 주기 = 약 14.5초
TEMPERATURE = 1.0
BASE = 192                  # 32의 배수 → 원곡 창의 위상 정렬
WINDOWS = [0, 32, 64, 96, 128, 160]
TRACKS = ["motifA_v1", "motifA_v2", "motifB_v1",
          "motifB_v2", "motifC_v1", "motifC_v2"]
DEFAULT_SEEDS = [5101, 5202, 5303, 5404, 5505, 5606]
DEFAULT_SHUFFLE = 20260815

PAGE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>어느 쪽이 더 음악 같나요 — 5분 듣기</title>
<style>
 :root{--bg:#f5f8f2;--fg:#1b2419;--muted:#5c6b57;--line:#d6e0cd;--card:#fff;--accent:#2f6b3a}
 @media(prefers-color-scheme:dark){:root{--bg:#0f1410;--fg:#e6ede2;--muted:#8fa088;--line:#243021;--card:#161d15;--accent:#7fb069}}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--fg);line-height:1.65;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans KR",sans-serif}
 .wrap{max-width:680px;margin:0 auto;padding:32px 18px 90px}
 h1{font-size:clamp(20px,5vw,27px);margin:0 0 8px;font-weight:700}
 .lede{color:var(--muted);font-size:14.5px;margin:0 0 8px}
 .why{border:1px solid var(--line);border-radius:11px;padding:14px 16px;background:var(--card);
      font-size:13.5px;color:var(--muted);margin:0 0 28px}
 .why b{color:var(--fg)}
 .pair{background:var(--card);border:1px solid var(--line);border-radius:14px;
       padding:18px;margin-bottom:16px}
 .pn{font-size:11.5px;color:var(--accent);font-weight:700;letter-spacing:.05em}
 .pt{font-size:16px;font-weight:600;margin:2px 0 12px}
 .side{margin-bottom:10px}
 .side label{font-size:13px;font-weight:600;display:block;margin-bottom:4px}
 audio{width:100%}
 .choices{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
 .choices button{flex:1 1 30%;font:inherit;font-size:14px;padding:11px 8px;border-radius:9px;
   border:1px solid var(--line);background:transparent;color:var(--fg);cursor:pointer;min-height:44px}
 .choices button:hover{border-color:var(--accent)}
 .choices button.sel{background:var(--accent);color:#fff;border-color:var(--accent);font-weight:600}
 textarea{width:100%;margin-top:10px;font:inherit;font-size:13px;padding:8px;border-radius:8px;
   border:1px solid var(--line);background:var(--bg);color:var(--fg);min-height:44px}
 .done{position:sticky;bottom:0;background:var(--bg);padding:14px 0 6px;border-top:1px solid var(--line)}
 .done button{width:100%;font:inherit;font-size:15px;font-weight:700;padding:13px;border-radius:10px;
   border:none;background:var(--accent);color:#fff;cursor:pointer}
 .done button:disabled{opacity:.4;cursor:not-allowed}
 #code{width:100%;margin-top:12px;font-family:ui-monospace,monospace;font-size:12.5px;
   padding:10px;border-radius:8px;border:1px solid var(--accent);background:var(--card);color:var(--fg)}
 .hint{font-size:12.5px;color:var(--muted);margin-top:8px}
</style>
<div class="wrap">
<h1>어느 쪽이 더 음악 같나요</h1>
<p class="lede">__N__쌍 · 각 약 15초 · <b>5분이면 끝납니다</b>. 어느 쪽이 무엇인지는 가려져 있습니다.</p>
<div class="why">
 두 짧은 피아노 연주를 듣고 <b>그냥 더 마음에 드는 쪽</b>을 고르시면 됩니다.
 음악 지식은 전혀 필요 없습니다.<br><br>
 <b>정답은 없습니다.</b> 구별이 안 되면 "모르겠다"를 눌러 주세요 —
 <b>구별이 안 된다는 것 자체가 중요한 결과</b>입니다.
 이유를 한 줄 적어 주시면 큰 도움이 되지만, 비워 두셔도 됩니다.<br><br>
 다 고르시면 아래 버튼이 켜지고, <b>짧은 코드</b>가 자동으로 복사됩니다. 그것만 보내 주세요.
</div>
__PAIRS__
<div class="done">
 <button id="fin" disabled>답 정리하기</button>
 <textarea id="code" hidden readonly rows="3"></textarea>
 <p class="hint" id="hint">__N__쌍 모두 고르면 활성화됩니다.</p>
</div>
</div>
<script>
const N=__N__, ans={}, note={};
document.querySelectorAll('.choices button').forEach(b=>{
  b.onclick=()=>{
    const p=b.dataset.pair;
    document.querySelectorAll(`.choices button[data-pair="${p}"]`).forEach(x=>x.classList.remove('sel'));
    b.classList.add('sel'); ans[p]=b.dataset.val; check();
  };
});
document.querySelectorAll('textarea[data-pair]').forEach(t=>{
  t.oninput=()=>{ note[t.dataset.pair]=t.value.trim(); };
});
function check(){
  const n=Object.keys(ans).length;
  document.getElementById('fin').disabled = n<N;
  document.getElementById('hint').textContent = n<N ? `${n}/${N} 선택됨` : '이제 정리할 수 있습니다.';
}
document.getElementById('fin').onclick=()=>{
  const payload = Object.keys(ans).sort().map(p=>`${p}:${ans[p]}${note[p]?'|'+note[p].replace(/[\\n|]/g,' '):''}`).join(' ; ');
  const ta=document.getElementById('code');
  ta.hidden=false; ta.value='AB-P4 ' + payload;
  ta.select();
  try{ navigator.clipboard.writeText(ta.value); }catch(e){}
  document.getElementById('hint').textContent='복사됐습니다. 그대로 보내 주세요.';
};
document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>{
  document.querySelectorAll('audio').forEach(o=>{ if(o!==a) o.pause(); });
}));
</script>
"""


def zero_rows(om):
    return int((om.sum(1) == 0).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=str, default=",".join(map(str, DEFAULT_SEEDS)),
                    help="쌍마다 하나씩. 같은 쌍의 두 팔은 이 시드를 공유한다")
    ap.add_argument("--shuffle-seed", type=int, default=DEFAULT_SHUFFLE,
                    help="어느 쪽이 A 가 될지만 결정 (생성에는 영향 없음)")
    args = ap.parse_args()
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    n_pairs = min(len(seeds), len(WINDOWS), len(TRACKS))

    os.makedirs(OUT, exist_ok=True)
    data = suite.setup_hibari()
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cyc = pickle.load(f)["cycle_labeled"]
    om_full = load_continuous_om()
    with open(MOTIF_JSON, encoding="utf-8") as f:
        tr = {t["track"]: t for t in json.load(f)["tracks"]}

    print(f"P4 반복 — {n_pairs}쌍 · 각 {T}스텝({T*SEC_PER_8TH:.1f}초) · temperature={TEMPERATURE}")
    print(f"{'쌍':4} {'창':>10} {'디퓨전 트랙':16} {'시드':>7} "
          f"{'원곡 zero-row':>14} {'디퓨전 zero-row':>16}")

    rng = random.Random(args.shuffle_seed)
    key, blocks, exposure = {}, [], {}
    for i in range(n_pairs):
        off, track, seed = WINDOWS[i], TRACKS[i], seeds[i]
        pid = f"Q{i+1}"

        real_om = (om_full[BASE + off: BASE + off + T] >= REAL_TAU).astype(np.float32)
        diff_om = bits(tr[track]["om_bits"], int(tr[track]["om_T"]),
                       int(tr[track]["om_K"]))[off: off + T].astype(np.float32)

        zr_r, zr_d = zero_rows(real_om), zero_rows(diff_om)
        exposure[pid] = {"real_zero_rows": zr_r, "diffusion_zero_rows": zr_d, "T": T}
        print(f"{pid:4} {f'[{off}:{off+T}]':>10} {track:16} {seed:>7} "
              f"{f'{zr_r}/{T}':>14} {f'{zr_d}/{T}':>16}")

        cands = [("원곡 OM", gen(data, cyc, real_om, seed, temperature=TEMPERATURE)),
                 (f"디퓨전 OM ({track})", gen(data, cyc, diff_om, seed, temperature=TEMPERATURE))]
        if rng.random() < 0.5:
            cands.reverse()
        key[pid] = {"A": cands[0][0], "B": cands[1][0],
                    "window": [BASE + off, BASE + off + T], "seed": seed,
                    "temperature": TEMPERATURE}

        for letter, (name, notes) in zip("AB", cands):
            stem = f"{pid}{letter}"
            mid = os.path.join(OUT, stem + ".mid")
            wav = os.path.join(OUT, stem + ".wav")
            write_midi(notes, mid)
            render_wav(mid, wav)
            to_ogg(wav, os.path.join(OUT, stem + ".ogg"))
            os.remove(wav)
            # ⚠ name 을 찍으면 터미널 스크롤만으로 블라인드가 깨진다.
            print(f"     {stem}  {len(notes):3d}음")

        blocks.append(
            f'<div class="pair"><div class="pn">{pid} / {n_pairs}</div>'
            f'<div class="pt">어느 쪽이 더 마음에 드나요?</div>'
            f'<div class="side"><label>A</label><audio controls preload="none" src="{pid}A.ogg"></audio></div>'
            f'<div class="side"><label>B</label><audio controls preload="none" src="{pid}B.ogg"></audio></div>'
            f'<div class="choices">'
            f'<button data-pair="{pid}" data-val="A">A</button>'
            f'<button data-pair="{pid}" data-val="B">B</button>'
            f'<button data-pair="{pid}" data-val="?">모르겠다</button></div>'
            f'<textarea data-pair="{pid}" placeholder="이유 한 줄 (선택)"></textarea></div>')

    page = PAGE.replace("__PAIRS__", "\n".join(blocks)).replace("__N__", str(n_pairs))
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    with open(os.path.join(OUT, "answer_key.json"), "w", encoding="utf-8") as f:
        json.dump({"experiment": "P4 반복 — 원곡 OM vs 디퓨전 OM",
                   "n_pairs": n_pairs, "T_steps": T,
                   "seconds_each": round(T * SEC_PER_8TH, 1),
                   "temperature": TEMPERATURE, "shuffle_seed": args.shuffle_seed,
                   "generation_seeds": seeds[:n_pairs],
                   "key": key, "pool_exposure": exposure,
                   "note": "이 파일을 먼저 열지 마세요 — 블라인드가 깨집니다."},
                  f, ensure_ascii=False, indent=2)
    print(f"\n페이지: {os.path.join(OUT, 'index.html')}")
    print("정답표: answer_key.json (열지 말 것)")


if __name__ == "__main__":
    main()
