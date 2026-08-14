"""
make_ab_check.py — "지표가 귀와 맞는가" 10분짜리 블라인드 A/B 점검

왜 필요한가
──────────
2026-08-13 현재 이 연구의 모든 판단이 **음고 JS·협화도라는 대리 지표**로 내려졌다.
그런데 오늘만 해도 "개선"이 두 번 무너졌고(위상 손실 / τ-leaping), 살아남은 개선조차
**협화도를 거의 같은 크기로 깎으면서** 얻은 것이다. 그 맞바꿈이 귀에 어떻게 들리는지는
아무도 모른다. 대리 지표만으로는 답이 안 나온다.

기존 `protocol.md`(Task 45)는 피험자 10명 규모의 정식 실험이다. 여기서는 그게 아니라
**연구자 본인이 10분 안에 끝낼 수 있는 최소 점검**을 만든다.

5쌍 · 각 약 27초 · 완전 블라인드
────────────────────────────────
  P1  NodePool 인덱스 수정 전 vs 후        (JS −4.3% / 협화도 −1.2% 맞바꿈)
  P2  교집합 균일추출 vs 곡빈도+온도        (JS −6.2% / 협화도 −0.011 맞바꿈)
  P3  모티브 뼈대 vs 디퓨전이 채운 변주      (채우면 풍성해지나 탁해지나)
  P4  원곡 OM vs 디퓨전 OM                 (디퓨전 라인 전체의 존재 이유)
  P5  모티브 A vs 모티브 D                 (지표는 가장 멀다 했다 — 귀로 구별되나)

각 쌍에서 어느 쪽이 A 가 될지는 **시드로 섞는다**. 정답표는 별도 JSON 에만 있고
페이지에는 들어가지 않는다. 답을 다 고르면 페이지가 짧은 코드 문자열을 주고,
그걸 붙여넣으면 이쪽에서 해독한다.

실행:  python listening_test/make_ab_check.py
출력:  output/ab_check/  (ogg 10개 + index.html + answer_key.json)
"""

from __future__ import annotations

# --- path_bootstrap ---
import os as _rp_os, sys as _rp_sys
_ROOT = _rp_os.path.dirname(_rp_os.path.dirname(_rp_os.path.abspath(__file__)))
_rp_sys.path.insert(0, _ROOT)
_rp_sys.path.insert(0, _rp_os.path.join(_ROOT, "experiments"))
_rp_sys.path.insert(0, _rp_os.path.join(_ROOT, "tools"))
# --- end path_bootstrap ---

import json
import os
import pickle
import random
import shutil
import subprocess

import numpy as np

import generation as G
import run_dft_gap0_suite as suite
from run_topo_diffusion import (
    CACHE_DIR, CACHE_NAME, MODULES, REAL_TAU, TDA_ROOT, load_continuous_om,
)
from make_topo_music import SEC_PER_8TH, render_wav, write_midi

OUT = os.path.join(TDA_ROOT, "output", "ab_check")
MOTIF_JSON = os.path.join(TDA_ROOT, "docs", "step3_data", "motif_control_results.json")
T = 60                       # 약 27초
SEED = 4242
SHUFFLE_SEED = 20260813


class OldPool(G.NodePool):
    """수정 전 동작 — 풀을 1-indexed 로 되돌린다."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.pool = self.pool + 1


def freq_weights(data, temperature):
    inv = {lbl: note for note, lbl in data["notes_label"].items()}
    return {lbl - 1: max(1e-6, float(data["notes_counts"].get(note, 1)) ** (1.0 / temperature))
            for lbl, note in inv.items()}


def gen(data, cycle_labeled, om_bin, seed, *, pool_cls=G.NodePool,
        temperature=3.0, weighted_intersect=False):
    """Algorithm 1 한 판. generation.py 는 수정하지 않고 인자·훅만 바꾼다."""
    random.seed(seed)
    np.random.seed(seed)
    n = om_bin.shape[0]
    inst = (MODULES * (n // len(MODULES) + 2))[:n]
    pool = pool_cls(data["notes_label"], data["notes_counts"],
                    num_modules=65, temperature=temperature)
    saved = G.random.choice
    if weighted_intersect:
        w = freq_weights(data, temperature)
        rnd = random.Random(seed ^ 0x5EED)

        def pick(seq):
            ws = [w.get(int(z), 1.0) for z in seq]
            tot = sum(ws)
            if tot <= 0:
                return rnd.choice(seq)
            r = rnd.random() * tot
            acc = 0.0
            for z, wi in zip(seq, ws):
                acc += wi
                if r <= acc:
                    return z
            return seq[-1]
        G.random.choice = pick
    try:
        return G.algorithm1_optimized(pool, list(inst), om_bin.astype(np.float32),
                                      G.CycleSetManager(cycle_labeled),
                                      max_resample=50, verbose=False, min_onset_gap=0)
    finally:
        G.random.choice = saved


def bits(s, n, k):
    return (np.frombuffer(s.encode("ascii"), dtype=np.uint8) == ord("1")).reshape(n, k)


def to_ogg(wav, ogg, q=4):
    if not shutil.which("ffmpeg"):
        return False
    return subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav,
                           "-c:a", "libvorbis", "-q:a", str(q), ogg],
                          capture_output=True).returncode == 0


PAIRS_META = [
    ("P1", "같은 지시, 만드는 방식만 다름",
     "둘 다 원곡 중첩행렬에서 나왔습니다. 음을 고르는 내부 배선만 다릅니다."),
    ("P2", "같은 지시, 음 고르는 규칙만 다름",
     "한쪽은 활성 고리 안에서 균일하게, 다른 쪽은 곡에서 자주 나온 음을 더 자주 고릅니다."),
    ("P3", "뼈대 vs 채운 것",
     "한쪽은 모티브만 남긴 뼈대, 다른 쪽은 그 사이를 디퓨전이 채운 것입니다."),
    ("P4", "출처가 다른 두 골격",
     "한쪽은 원곡의 중첩행렬, 다른 쪽은 모델이 새로 만든 중첩행렬입니다."),
    ("P5", "서로 다른 두 모티브",
     "지시가 다릅니다. 지표상으로는 이 둘이 가장 멀다고 나왔습니다."),
]

PAGE = """<!doctype html>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>귀로 확인하기 — 10분 A/B</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&family=Noto+Serif+KR:wght@600&display=swap" rel="stylesheet">
<style>
 :root{--bg:#f5f8f2;--fg:#1b2419;--muted:#5c6b57;--line:#d6e0cd;--card:#fff;--accent:#2f6b3a}
 @media(prefers-color-scheme:dark){:root{--bg:#0f1410;--fg:#e6ede2;--muted:#8fa088;--line:#243021;--card:#161d15;--accent:#7fb069}}
 *{box-sizing:border-box}
 body{margin:0;background:var(--bg);color:var(--fg);line-height:1.65;
      font-family:"Noto Sans KR",-apple-system,BlinkMacSystemFont,sans-serif}
 .wrap{max-width:680px;margin:0 auto;padding:36px 18px 90px}
 h1{font-family:"Noto Serif KR",serif;font-size:clamp(21px,5vw,29px);margin:0 0 8px}
 .lede{color:var(--muted);font-size:14.5px;margin:0 0 8px}
 .why{border:1px solid var(--line);border-radius:11px;padding:14px 16px;background:var(--card);
      font-size:13.5px;color:var(--muted);margin:0 0 28px}
 .why b{color:var(--fg)}
 .pair{background:var(--card);border:1px solid var(--line);border-radius:14px;
       padding:18px;margin-bottom:16px}
 .pn{font-size:11.5px;color:var(--accent);font-weight:700;letter-spacing:.05em}
 .pt{font-family:"Noto Serif KR",serif;font-size:17px;font-weight:600;margin:2px 0 4px}
 .pd{font-size:13px;color:var(--muted);margin:0 0 14px}
 .side{margin-bottom:10px}
 .side label{font-size:13px;font-weight:600;display:block;margin-bottom:4px}
 audio{width:100%}
 .choices{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
 .choices button{flex:1 1 30%;font:inherit;font-size:14px;padding:10px 8px;border-radius:9px;
   border:1px solid var(--line);background:transparent;color:var(--fg);cursor:pointer}
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
<h1>귀로 확인하기</h1>
<p class="lede">5쌍 · 각 27초 · 약 10분. 어느 쪽이 무엇인지는 <b>가려져 있습니다</b>.</p>
<div class="why">
 지금까지 이 연구의 모든 판단은 <b>음고 분포·협화도라는 대리 지표</b>로 내려졌습니다.
 그런데 최근 "개선" 두 개가 검증에서 무너졌고, 살아남은 개선조차 <b>협화도를 거의 같은 크기로
 깎으면서</b> 얻은 것입니다. 그 맞바꿈이 실제로 어떻게 들리는지는 아직 아무도 모릅니다.<br><br>
 <b>정답은 없습니다.</b> "그냥 이쪽이 낫다"면 그걸로 충분하고, 모르겠으면 모르겠다고 하시면 됩니다 —
 <b>구별이 안 된다는 것 자체가 중요한 결과</b>입니다.
</div>
__PAIRS__
<div class="done">
 <button id="fin" disabled>답 정리하기</button>
 <textarea id="code" hidden readonly rows="3"></textarea>
 <p class="hint" id="hint">5쌍 모두 고르면 활성화됩니다.</p>
</div>
</div>
<script>
const N=5, ans={}, note={};
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
  ta.hidden=false; ta.value='AB-CHECK ' + payload;
  ta.select();
  try{ navigator.clipboard.writeText(ta.value); }catch(e){}
  document.getElementById('hint').textContent='복사됐습니다. 그대로 붙여넣어 주세요.';
};
// 한 번에 하나만 재생
document.querySelectorAll('audio').forEach(a=>a.addEventListener('play',()=>{
  document.querySelectorAll('audio').forEach(o=>{ if(o!==a) o.pause(); });
}));
</script>
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    data = suite.setup_hibari()
    with open(os.path.join(CACHE_DIR, CACHE_NAME), "rb") as f:
        cyc = pickle.load(f)["cycle_labeled"]

    om_full = load_continuous_om()
    real_om = (om_full[200:200 + T] >= REAL_TAU).astype(np.float32)

    with open(MOTIF_JSON, encoding="utf-8") as f:
        mres = json.load(f)
    tr = {t["track"]: t for t in mres["tracks"]}

    def head(track):
        t = tr[track]
        return bits(t["om_bits"], t["om_T"], t["om_K"])[:T].astype(np.float32)

    # 각 쌍의 두 후보 (라벨은 정답표에만 남는다)
    cands = {
        "P1": (("수정 전 (1-indexed 풀)", gen(data, cyc, real_om, SEED, pool_cls=OldPool)),
               ("수정 후 (0-indexed 풀)", gen(data, cyc, real_om, SEED))),
        "P2": (("교집합 균일추출", gen(data, cyc, real_om, SEED + 1)),
               ("교집합 곡빈도+온도", gen(data, cyc, real_om, SEED + 1, weighted_intersect=True))),
        "P3": (("모티브 A 뼈대", gen(data, cyc, head("motifA_skeleton"), SEED + 2)),
               ("모티브 A 변주1", gen(data, cyc, head("motifA_v1"), SEED + 2))),
        "P4": (("원곡 OM", gen(data, cyc, real_om, SEED + 3)),
               ("디퓨전 OM (모티브 A 변주2)", gen(data, cyc, head("motifA_v2"), SEED + 3))),
        "P5": (("모티브 A 변주1", gen(data, cyc, head("motifA_v1"), SEED + 4)),
               ("모티브 D 변주1", gen(data, cyc, head("motifD_v1"), SEED + 4))),
    }

    rng = random.Random(SHUFFLE_SEED)
    key, blocks = {}, []
    for pid, title, desc in PAIRS_META:
        (n0, g0), (n1, g1) = cands[pid]
        flip = rng.random() < 0.5
        sides = [(n1, g1), (n0, g0)] if flip else [(n0, g0), (n1, g1)]
        key[pid] = {"A": sides[0][0], "B": sides[1][0]}
        for letter, (name, notes) in zip("AB", sides):
            stem = f"{pid}{letter}"
            mid = os.path.join(OUT, stem + ".mid")
            wav = os.path.join(OUT, stem + ".wav")
            write_midi(notes, mid)
            render_wav(mid, wav)
            to_ogg(wav, os.path.join(OUT, stem + ".ogg"))
            os.remove(wav)
            # ⚠ 여기서 `name` 을 찍으면 터미널 스크롤만으로 블라인드가 깨진다.
            # 무엇이 A/B 가 됐는지는 answer_key.json 에만 남긴다.
            print(f"  {pid}{letter}  {len(notes):4d}음")
        blocks.append(
            f'<div class="pair"><div class="pn">{pid}</div><div class="pt">{title}</div>'
            f'<p class="pd">{desc}</p>'
            f'<div class="side"><label>A</label><audio controls preload="none" src="{pid}A.ogg"></audio></div>'
            f'<div class="side"><label>B</label><audio controls preload="none" src="{pid}B.ogg"></audio></div>'
            f'<div class="choices">'
            f'<button data-pair="{pid}" data-val="A">A가 낫다</button>'
            f'<button data-pair="{pid}" data-val="B">B가 낫다</button>'
            f'<button data-pair="{pid}" data-val="?">구별 안 됨</button></div>'
            f'<textarea data-pair="{pid}" placeholder="한 줄 인상 (선택)"></textarea></div>')

    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(PAGE.replace("__PAIRS__", "\n".join(blocks)))
    with open(os.path.join(OUT, "answer_key.json"), "w", encoding="utf-8") as f:
        json.dump({"shuffle_seed": SHUFFLE_SEED, "key": key,
                   "note": "이 파일을 먼저 열지 마세요 — 블라인드가 깨집니다."},
                  f, ensure_ascii=False, indent=2)
    print(f"\n페이지: {os.path.join(OUT, 'index.html')}")
    print("정답표: answer_key.json (열지 말 것)")


if __name__ == "__main__":
    main()
