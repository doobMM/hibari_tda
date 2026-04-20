#!/usr/bin/env python3
"""gen_dashboard.py — TDA Pipeline JARVIS 코드 탐색 대시보드

3-panel 인터랙티브 코드 탐색기:
  Left  : 파이프라인 계층 트리 (클릭 → 모듈/함수 탐색)
  Center: 신택스 하이라이팅된 코드 뷰어
  Right : 함수 역할·입력·출력 분석 패널

Usage:
    python tda_pipeline/tools/gen_dashboard.py
Output:
    tda_pipeline/docs/pipeline_dashboard.html
"""
import ast
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
TDA  = ROOT / "tda_pipeline"
DOCS = TDA / "docs"

# ── 모듈 파일 경로 ────────────────────────────────────────────────────────────
MODULE_FILES = {
    "pipeline":        TDA / "pipeline.py",
    "config":          TDA / "config.py",
    "preprocessing":   TDA / "preprocessing.py",
    "weights":         TDA / "weights.py",
    "topology":        TDA / "topology.py",
    "musical_metrics": TDA / "musical_metrics.py",
    "overlap":         TDA / "overlap.py",
    "cycle_selector":  TDA / "cycle_selector.py",
    "temporal_reorder":TDA / "temporal_reorder.py",
    "generation":      TDA / "generation.py",
    "eval_metrics":    TDA / "eval_metrics.py",
}

# ── 파이프라인 계층 트리 ───────────────────────────────────────────────────────
PIPELINE_TREE = [
    {"id":"pipeline",  "label":"pipeline.py",  "module":"pipeline",  "color":"#4361ee","icon":"◉"},
    {"id":"config",    "label":"config.py",     "module":"config",    "color":"#8d99ae","icon":"⚙"},
    {"id":"stage1","label":"STAGE 1 — 전처리","color":"#3a86ff","icon":"①","children":[
        {"id":"preprocessing","label":"preprocessing.py","module":"preprocessing","color":"#3a86ff"},
    ]},
    {"id":"stage2","label":"STAGE 2 — Homology","color":"#06d6a0","icon":"②","children":[
        {"id":"weights",        "label":"weights.py",        "module":"weights",        "color":"#06d6a0"},
        {"id":"topology",       "label":"topology.py",       "module":"topology",       "color":"#f7b731"},
        {"id":"musical_metrics","label":"musical_metrics.py","module":"musical_metrics","color":"#e76f51"},
    ]},
    {"id":"stage3","label":"STAGE 3 — 중첩행렬","color":"#8338ec","icon":"③","children":[
        {"id":"overlap","label":"overlap.py","module":"overlap","color":"#8338ec"},
    ]},
    {"id":"stage35","label":"STAGE 3.5 — 선택적","color":"#9b5de5","icon":"⊕","children":[
        {"id":"cycle_selector",  "label":"cycle_selector.py",  "module":"cycle_selector",  "color":"#9b5de5"},
        {"id":"temporal_reorder","label":"temporal_reorder.py","module":"temporal_reorder","color":"#b5838d"},
    ]},
    {"id":"stage4","label":"STAGE 4 — 생성","color":"#f4511e","icon":"④","children":[
        {"id":"generation","label":"generation.py","module":"generation","color":"#f4511e"},
    ]},
    {"id":"eval","label":"평가","color":"#ffd166","icon":"✓","children":[
        {"id":"eval_metrics","label":"eval_metrics.py","module":"eval_metrics","color":"#ffd166"},
    ]},
]


# ─────────────────────────────────────────────────────────────────────────────
# AST 파싱
# ─────────────────────────────────────────────────────────────────────────────

def _parse_docstring_sections(doc: str) -> dict:
    if not doc:
        return {"description": "", "args": {}, "returns": ""}
    lines = doc.strip().split("\n")
    desc, args, returns = [], {}, []
    section = "desc"
    cur_arg = None
    for line in lines:
        s = line.strip()
        if s in ("Args:", "Arguments:"):
            section = "args"; continue
        if s in ("Returns:", "Return:", "Yields:"):
            section = "ret"; cur_arg = None; continue
        if section == "args":
            m = re.match(r"^(\w+)\s*(?:\(.*?\))?\s*:\s*(.*)", s)
            if m:
                cur_arg = m.group(1)
                args[cur_arg] = m.group(2).strip()
            elif cur_arg and s:
                args[cur_arg] = (args[cur_arg] + " " + s).strip()
        elif section == "ret":
            if s: returns.append(s)
        else:
            desc.append(s)
    return {
        "description": "\n".join(l for l in desc if l).strip(),
        "args": args,
        "returns": " ".join(returns).strip(),
    }


def _extract_func(node, source_lines: list, class_name):
    doc = ast.get_docstring(node) or ""
    secs = _parse_docstring_sections(doc)
    end = getattr(node, "end_lineno", node.lineno)

    params = []
    all_args = node.args.args
    defaults = node.args.defaults
    n_defs = len(defaults)
    n_args = len(all_args)
    for i, arg in enumerate(all_args):
        if arg.arg == "self": continue
        p = {"name": arg.arg, "type": "", "default": "", "desc": ""}
        if arg.annotation:
            try: p["type"] = ast.unparse(arg.annotation)
            except Exception: p["type"] = "?"
        di = i - (n_args - n_defs)
        if di >= 0:
            try: p["default"] = ast.unparse(defaults[di])
            except Exception: p["default"] = "?"
        p["desc"] = secs["args"].get(arg.arg, "")
        params.append(p)

    ret_type = ""
    if node.returns:
        try: ret_type = ast.unparse(node.returns)
        except Exception: ret_type = "?"

    return {
        "name": node.name,
        "qual": f"{class_name}.{node.name}" if class_name else node.name,
        "class": class_name or "",
        "lineno": node.lineno,
        "end_lineno": end,
        "doc_short": doc.split("\n")[0].strip() if doc else "",
        "description": secs["description"],
        "params": params,
        "return_type": ret_type,
        "returns_desc": secs["returns"],
        "recently_modified": False,
    }


def _get_recent_lines(filepath: Path, days: int = 30) -> set:
    try:
        r = subprocess.run(
            ["git", "log", f"--since={days} days ago", "--unified=0",
             "--pretty=format:", "--", str(filepath)],
            capture_output=True, text=True, cwd=ROOT, timeout=10
        )
        changed = set()
        for line in r.stdout.splitlines():
            m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            if m:
                s, c = int(m.group(1)), int(m.group(2) or "1")
                changed.update(range(s, s + max(c, 1)))
        return changed
    except Exception:
        return set()


def parse_module(name: str, filepath: Path) -> dict:
    if not filepath.exists():
        return {"name": name, "filename": filepath.name, "exists": False,
                "source": f"# {filepath.name} not found", "line_count": 0, "functions": []}
    source = filepath.read_text(encoding="utf-8")
    lines = source.splitlines()
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"name": name, "filename": filepath.name, "exists": True,
                "source": source, "line_count": len(lines), "functions": [],
                "error": str(e)}

    funcs = []
    seen = set()
    # class methods first
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcs.append(_extract_func(item, lines, node.name))
                    seen.add((node.name, item.name))
    # top-level functions
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (None, node.name) not in seen and node.name not in {q[1] for q in seen}:
                funcs.append(_extract_func(node, lines, None))

    funcs.sort(key=lambda f: f["lineno"])

    recent = _get_recent_lines(filepath)
    for f in funcs:
        f["recently_modified"] = bool(
            any(f["lineno"] <= ln <= f["end_lineno"] for ln in recent)
        )

    return {
        "name": name, "filename": filepath.name, "exists": True,
        "source": source, "line_count": len(lines), "functions": funcs,
    }


# ─────────────────────────────────────────────────────────────────────────────
# HTML 생성
# ─────────────────────────────────────────────────────────────────────────────

def build_html(modules_data: dict, tree_data: list, timestamp: str) -> str:
    mj = json.dumps(modules_data, ensure_ascii=False)
    tj = json.dumps(tree_data, ensure_ascii=False)

    # NOTE: 이 문자열은 Python format string이 아님.
    # %%MODULES%%, %%TREE%%, %%TS%% 는 .replace()로 치환.
    template = _HTML_TEMPLATE
    return (template
            .replace("%%MODULES%%", mj)
            .replace("%%TREE%%", tj)
            .replace("%%TS%%", timestamp))


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>TDA PIPELINE SYSTEM</title>
<link rel="stylesheet"
  href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css">
<style>
:root{
  --bg:#06090f;--bg2:#0a1020;--bg3:#0e1828;
  --acc:#00c8ff;--acc2:#00ff9f;--warn:#e63946;
  --txt:#9ab8cc;--txtb:#cce0f0;
  --bdr:rgba(0,200,255,.18);--glow:0 0 8px rgba(0,200,255,.25);
}
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:100%;overflow:hidden;}
body{
  background:var(--bg);color:var(--txt);
  font-family:'Courier New',monospace;font-size:13px;
  display:flex;flex-direction:column;
  background-image:
    linear-gradient(rgba(0,200,255,.018) 1px,transparent 1px),
    linear-gradient(90deg,rgba(0,200,255,.018) 1px,transparent 1px);
  background-size:44px 44px;
}

/* ── HEADER ───────────────────────────────── */
#hdr{
  height:46px;flex-shrink:0;z-index:100;
  background:linear-gradient(135deg,#070d1c,#0c1830);
  border-bottom:1px solid var(--bdr);
  box-shadow:0 2px 14px rgba(0,0,0,.7);
  display:flex;align-items:center;padding:0 20px;gap:18px;
}
.sys-title{color:var(--acc);font-size:14px;font-weight:bold;
  letter-spacing:4px;text-shadow:0 0 10px var(--acc);}
.sys-sub{color:rgba(0,200,255,.4);font-size:9px;letter-spacing:2px;margin-top:2px;}
.hdr-right{margin-left:auto;display:flex;align-items:center;gap:10px;
  font-size:10px;color:var(--acc2);letter-spacing:1px;}
.blink{width:7px;height:7px;border-radius:50%;background:var(--acc2);
  box-shadow:0 0 6px var(--acc2);animation:blink 2s infinite;}
@keyframes blink{0%,100%{opacity:1;}50%{opacity:.35;}}

/* ── LAYOUT ───────────────────────────────── */
#main{display:flex;flex:1;overflow:hidden;min-height:0;}

/* ── SIDEBAR ──────────────────────────────── */
#sb{
  width:21%;min-width:190px;max-width:290px;flex-shrink:0;
  background:var(--bg2);border-right:1px solid var(--bdr);
  display:flex;flex-direction:column;overflow:hidden;
}
.sb-hdr{
  padding:9px 14px 7px;font-size:9px;letter-spacing:2px;
  color:var(--acc);text-transform:uppercase;
  border-bottom:1px solid var(--bdr);
  background:linear-gradient(135deg,#080f1e,#0a1525);flex-shrink:0;
}
#srch{padding:7px 10px;border-bottom:1px solid rgba(0,200,255,.08);flex-shrink:0;}
#srch input{
  width:100%;background:rgba(0,200,255,.05);
  border:1px solid rgba(0,200,255,.2);color:var(--txtb);
  padding:5px 8px;font-family:monospace;font-size:11px;
  outline:none;border-radius:2px;
}
#srch input:focus{border-color:var(--acc);box-shadow:0 0 4px rgba(0,200,255,.3);}
#tree{overflow-y:auto;flex:1;padding:4px 0;}

.stage-grp{}
.stage-hdr{
  padding:7px 12px;font-size:9px;letter-spacing:1.5px;
  color:rgba(154,184,204,.45);text-transform:uppercase;
  cursor:pointer;display:flex;align-items:center;gap:6px;
  border-left:2px solid transparent;transition:all .12s;
  position:sticky;top:0;background:var(--bg2);z-index:1;user-select:none;
}
.stage-hdr:hover{color:var(--txt);background:var(--bg3);}
.stage-hdr.open{color:var(--acc);border-left-color:var(--acc);}
.arr{margin-left:auto;font-size:8px;transition:transform .2s;}
.closed .arr{transform:rotate(-90deg);}
.closed .sc{display:none;}

.mod-item{
  padding:6px 12px 6px 22px;cursor:pointer;font-size:11px;
  border-left:2px solid transparent;transition:all .1s;
  display:flex;align-items:center;justify-content:space-between;gap:6px;
}
.mod-item:hover{background:rgba(0,200,255,.06);border-left-color:rgba(0,200,255,.3);}
.mod-item.sel{background:rgba(0,200,255,.12);border-left-color:var(--acc);color:var(--acc);}
.mod-item.dead{opacity:.35;cursor:not-allowed;}
.fc{font-size:9px;background:rgba(0,200,255,.12);color:rgba(0,200,255,.65);
  padding:1px 5px;border-radius:8px;flex-shrink:0;}

.fn-list{display:none;background:rgba(0,0,0,.18);
  border-left:1px solid rgba(0,200,255,.08);margin-left:22px;}
.fn-list.vis{display:block;}
.fn-item{
  padding:4px 10px;font-size:10px;color:rgba(154,184,204,.55);
  cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
  border-left:2px solid transparent;transition:all .1s;
  display:flex;align-items:center;gap:5px;
}
.fn-item:hover{color:var(--txtb);border-left-color:rgba(0,200,255,.4);background:rgba(0,200,255,.04);}
.fn-item.sel{color:var(--acc);border-left-color:var(--acc);background:rgba(0,200,255,.08);}
.rdot{width:5px;height:5px;border-radius:50%;background:var(--warn);flex-shrink:0;}
.gdot{width:5px;height:5px;flex-shrink:0;}

/* ── CODE PANEL ───────────────────────────── */
#cp{
  flex:1;background:#0c1a28;
  display:flex;flex-direction:column;overflow:hidden;min-width:0;
}
.ph{
  padding:8px 16px;flex-shrink:0;
  background:linear-gradient(135deg,#08101e,#0c1b30);
  border-bottom:1px solid var(--bdr);
  display:flex;align-items:center;gap:12px;font-size:10px;
}
.plbl{color:var(--acc);font-size:9px;letter-spacing:2px;text-transform:uppercase;}
#fn-lbl{color:var(--txtb);font-size:13px;}
.li{color:rgba(154,184,204,.35);font-size:10px;}
.rbdg{background:var(--warn);color:#fff;font-size:9px;
  padding:1px 6px;border-radius:2px;letter-spacing:.5px;}
#cw{flex:1;overflow:auto;position:relative;}
#cw pre{margin:0!important;padding:16px!important;
  background:transparent!important;min-height:100%;
  font-size:12.5px!important;line-height:1.68!important;tab-size:4;}
#cw code{font-family:'Courier New',monospace!important;white-space:pre!important;}
.hi-line{
  position:absolute;left:0;right:0;
  background:rgba(0,200,255,.07);border-left:3px solid var(--acc);
  pointer-events:none;
}

/* ── DOC PANEL ────────────────────────────── */
#dp{
  width:27%;min-width:250px;max-width:400px;flex-shrink:0;
  background:var(--bg2);border-left:1px solid var(--bdr);
  display:flex;flex-direction:column;overflow:hidden;
}
#dc{flex:1;overflow-y:auto;padding:16px;}
.empty{padding:40px 16px;text-align:center;
  color:rgba(154,184,204,.3);font-size:11px;line-height:2.2;}

.fn-name{color:var(--acc);font-size:17px;font-weight:bold;
  text-shadow:0 0 8px rgba(0,200,255,.35);word-break:break-all;}
.fn-meta{font-size:10px;color:rgba(154,184,204,.4);
  margin:4px 0 12px;letter-spacing:.4px;}
.fn-sig{
  background:rgba(0,200,255,.05);border:1px solid rgba(0,200,255,.15);
  border-radius:4px;padding:8px 10px;font-size:11px;
  color:#9ad4b4;margin-bottom:14px;line-height:1.65;word-break:break-all;
}
.ret-t{color:#ffd166;}

.sec{font-size:9px;letter-spacing:2px;color:var(--acc);
  text-transform:uppercase;border-bottom:1px solid rgba(0,200,255,.12);
  padding-bottom:4px;margin:14px 0 8px;}
.desc{font-size:12px;color:var(--txt);line-height:1.75;white-space:pre-wrap;}

.pt{width:100%;border-collapse:collapse;font-size:11px;}
.pt th{text-align:left;padding:3px 6px;color:rgba(0,200,255,.6);
  font-size:9px;letter-spacing:1px;border-bottom:1px solid rgba(0,200,255,.12);}
.pt td{padding:5px 6px;border-bottom:1px solid rgba(255,255,255,.04);vertical-align:top;}
.pn{color:#9ad4b4;}.pt_t{color:#ffd166;font-size:10px;}
.pd{color:rgba(154,184,204,.45);font-size:10px;}.pdc{color:var(--txt);line-height:1.4;}

.ret-box{
  background:rgba(0,255,159,.04);border:1px solid rgba(0,255,159,.15);
  border-radius:4px;padding:8px 10px;font-size:11px;margin-top:4px;
}
.ret-tl{color:var(--acc2);font-size:10px;margin-bottom:4px;}
.ret-d{color:var(--txt);line-height:1.5;}

.chip-wrap{display:flex;flex-wrap:wrap;gap:5px;margin-top:4px;}
.chip{
  background:rgba(0,200,255,.08);border:1px solid rgba(0,200,255,.2);
  color:var(--acc);font-size:10px;padding:2px 8px;border-radius:2px;
  cursor:pointer;transition:all .1s;
}
.chip:hover{background:rgba(0,200,255,.18);}

/* ── STATUSBAR ────────────────────────────── */
#stb{
  flex-shrink:0;background:#040710;
  border-top:1px solid var(--bdr);padding:4px 16px;
  font-size:10px;color:rgba(154,184,204,.35);
  display:flex;gap:20px;letter-spacing:.4px;
}
#stb span:last-child{margin-left:auto;}

::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:rgba(0,200,255,.18);border-radius:3px;}
::-webkit-scrollbar-thumb:hover{background:rgba(0,200,255,.35);}
</style>
</head>
<body>

<div id="hdr">
  <div>
    <div class="sys-title">TDA PIPELINE SYSTEM</div>
    <div class="sys-sub">TOPOLOGICAL DATA ANALYSIS · MUSIC GENERATION · SAKAMOTO RYUICHI</div>
  </div>
  <div class="hdr-right">
    <div class="blink"></div>
    <span>ONLINE</span>
    <span style="opacity:.3">|</span>
    <span id="htime">%%TS%%</span>
  </div>
</div>

<div id="main">

  <!-- LEFT -->
  <div id="sb">
    <div class="sb-hdr">▶ MODULE HIERARCHY</div>
    <div id="srch"><input id="si" placeholder="함수 검색 (이름 일부)..." oninput="filterFns(this.value)"></div>
    <div id="tree"></div>
  </div>

  <!-- CENTER -->
  <div id="cp">
    <div class="ph">
      <span class="plbl">SOURCE</span>
      <span id="fn-lbl">—</span>
      <span class="li" id="li-lbl"></span>
      <span class="rbdg" id="rbdg" style="display:none">● 최근 수정</span>
    </div>
    <div id="cw">
      <pre><code id="cd" class="language-python"># ← 왼쪽 트리에서 모듈을 선택하세요</code></pre>
    </div>
  </div>

  <!-- RIGHT -->
  <div id="dp">
    <div class="ph"><span class="plbl">FUNCTION ANALYSIS</span></div>
    <div id="dc">
      <div class="empty">◉ 왼쪽 트리에서<br>함수를 클릭하면<br>역할·입력·출력이<br>여기에 분석됩니다</div>
    </div>
  </div>

</div>

<div id="stb">
  <span id="sb-m">MODULE: —</span>
  <span id="sb-f">FUNC: —</span>
  <span id="sb-l">—</span>
  <span id="sb-c"></span>
</div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-python.min.js"></script>
<script>
const MODULES = %%MODULES%%;
const TREE    = %%TREE%%;
let curMod = null, curFn = null;

// ── Clock ────────────────────────────────────────────────────────────────────
setInterval(()=>{
  document.getElementById('sb-c').textContent =
    new Date().toLocaleTimeString('ko-KR',{hour12:false});
},1000);

// ── Tree build ───────────────────────────────────────────────────────────────
function buildTree(){
  const t=document.getElementById('tree');
  t.innerHTML='';
  for(const n of TREE){
    if(n.module){
      t.appendChild(makeModWrap(n,false));
    } else if(n.children){
      const g=document.createElement('div');
      g.className='stage-grp';
      const h=document.createElement('div');
      h.className='stage-hdr open';
      h.innerHTML=`<span>${n.icon||''}</span><span>${n.label}</span><span class="arr">▼</span>`;
      h.style.color=n.color;
      h.addEventListener('click',()=>{g.classList.toggle('closed');h.classList.toggle('open');});
      const sc=document.createElement('div');
      sc.className='sc';
      for(const c of n.children) sc.appendChild(makeModWrap(c,true));
      g.appendChild(h);g.appendChild(sc);
      t.appendChild(g);
    }
  }
}

function makeModWrap(node,indent){
  const mod=MODULES[node.module];
  const wrap=document.createElement('div');

  const item=document.createElement('div');
  item.className='mod-item'+(mod&&mod.exists?'':' dead');
  item.id='m-'+node.module;
  if(!indent) item.style.paddingLeft='12px';

  const cnt=mod?mod.functions.length:0;
  item.innerHTML=`<span style="color:${node.color};flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${node.label||node.module+'.py'}</span><span class="fc">${cnt}f</span>`;

  if(mod&&mod.exists){
    item.addEventListener('click',e=>{
      e.stopPropagation();
      selectMod(node.module);
      toggleFnList(node.module);
    });
  }

  const fl=document.createElement('div');
  fl.className='fn-list';
  fl.id='fl-'+node.module;
  if(mod&&mod.functions){
    for(const f of mod.functions){
      const fi=document.createElement('div');
      fi.className='fn-item';
      fi.dataset.mod=node.module;fi.dataset.fn=f.name;
      fi.innerHTML=`${f.recently_modified?'<span class="rdot"></span>':'<span class="gdot"></span>'}<span style="overflow:hidden;text-overflow:ellipsis">${f.name}()</span>`;
      fi.title=f.doc_short||'';
      fi.addEventListener('click',e=>{e.stopPropagation();selectMod(node.module);selectFn(node.module,f.name);});
      fl.appendChild(fi);
    }
  }
  wrap.appendChild(item);wrap.appendChild(fl);
  return wrap;
}

function toggleFnList(name){
  document.querySelectorAll('.fn-list').forEach(e=>{if(e.id!=='fl-'+name)e.classList.remove('vis');});
  const el=document.getElementById('fl-'+name);
  if(el)el.classList.toggle('vis');
}

// ── Module select ─────────────────────────────────────────────────────────────
function selectMod(name){
  if(!MODULES[name]||!MODULES[name].exists)return;
  curMod=name;curFn=null;
  const mod=MODULES[name];
  document.querySelectorAll('.mod-item').forEach(e=>e.classList.remove('sel'));
  const el=document.getElementById('m-'+name);if(el)el.classList.add('sel');
  // load code
  const cd=document.getElementById('cd');
  cd.textContent=mod.source;
  Prism.highlightElement(cd);
  // header
  document.getElementById('fn-lbl').textContent=mod.filename;
  document.getElementById('li-lbl').textContent=`${mod.line_count} lines · ${mod.functions.length} functions`;
  const hasR=mod.functions.some(f=>f.recently_modified);
  document.getElementById('rbdg').style.display=hasR?'':'none';
  // statusbar
  document.getElementById('sb-m').textContent='MODULE: '+mod.filename;
  document.getElementById('sb-f').textContent='FUNC: —';
  document.getElementById('sb-l').textContent='—';
  // doc panel
  document.getElementById('dc').innerHTML=`<div class="empty">◎ <strong style="color:var(--txtb)">${mod.filename}</strong><br>${mod.functions.length}개 함수 발견<br><br>← 함수를 클릭하세요</div>`;
}

// ── Function select ───────────────────────────────────────────────────────────
function selectFn(modName,fnName){
  if(modName!==curMod)selectMod(modName);
  curFn=fnName;
  const mod=MODULES[modName];
  const fn=mod.functions.find(f=>f.name===fnName);if(!fn)return;
  document.querySelectorAll('.fn-item').forEach(e=>e.classList.remove('sel'));
  const el=document.querySelector(`.fn-item[data-mod="${modName}"][data-fn="${fnName}"]`);
  if(el)el.classList.add('sel');
  scrollToLine(fn.lineno,fn.end_lineno,mod.line_count);
  renderDoc(fn,modName);
  document.getElementById('sb-f').textContent='FUNC: '+fn.name;
  document.getElementById('sb-l').textContent=`L${fn.lineno}–${fn.end_lineno}`;
}

function scrollToLine(start,end,total){
  const cw=document.getElementById('cw');
  const pre=cw.querySelector('pre');if(!pre)return;
  const lh=pre.scrollHeight/(total||1);
  cw.scrollTo({top:(start-4)*lh,behavior:'smooth'});
  // highlight
  document.querySelectorAll('.hi-line').forEach(e=>e.remove());
  const hl=document.createElement('div');
  hl.className='hi-line';
  hl.style.top=(start-1)*lh+'px';
  hl.style.height=(end-start+1)*lh+'px';
  pre.style.position='relative';
  pre.appendChild(hl);
}

// ── Doc render ────────────────────────────────────────────────────────────────
function renderDoc(fn,modName){
  const paramRows=fn.params.map(p=>`
    <tr>
      <td class="pn">${esc(p.name)}</td>
      <td class="pt_t">${esc(p.type||'—')}</td>
      <td class="pd">${esc(p.default||'—')}</td>
      <td class="pdc">${esc(p.desc||'')}</td>
    </tr>`).join('');

  const sigParts=fn.params.map(p=>{
    let s=p.name;
    if(p.type)s+=': '+p.type;
    if(p.default)s+=' = '+p.default;
    return s;
  });
  const sig=fn.name+'(\n  '+sigParts.join(',\n  ')+'\n)';
  const ret=fn.return_type?` → <span class="ret-t">${esc(fn.return_type)}</span>`:'';

  const rbadge=fn.recently_modified
    ?`<span style="background:var(--warn);color:#fff;font-size:9px;padding:1px 6px;border-radius:2px;margin-left:8px;letter-spacing:.5px">● 최근 수정</span>`:'';

  let html=`
    <div class="fn-name">${esc(fn.name)}()${rbadge}</div>
    <div class="fn-meta">${fn.class?fn.class+'.':''}${fn.name} &nbsp;·&nbsp; ${modName}.py &nbsp;·&nbsp; L${fn.lineno}–${fn.end_lineno}</div>
    <div class="fn-sig"><code>${esc(sig)}</code>${ret}</div>`;

  if(fn.description){
    html+=`<div class="sec">DESCRIPTION</div><div class="desc">${esc(fn.description)}</div>`;
  }

  if(fn.params.length){
    html+=`<div class="sec">PARAMETERS</div>
    <table class="pt">
      <tr><th>NAME</th><th>TYPE</th><th>DEFAULT</th><th>DESC</th></tr>
      ${paramRows}
    </table>`;
  }

  if(fn.return_type||fn.returns_desc){
    html+=`<div class="sec">RETURNS</div>
    <div class="ret-box">
      ${fn.return_type?`<div class="ret-tl">${esc(fn.return_type)}</div>`:''}
      ${fn.returns_desc?`<div class="ret-d">${esc(fn.returns_desc)}</div>`:''}
    </div>`;
  }

  document.getElementById('dc').innerHTML=html;
}

// ── Search ────────────────────────────────────────────────────────────────────
function filterFns(q){
  q=q.toLowerCase().trim();
  document.querySelectorAll('.fn-item').forEach(el=>{
    const name=(el.dataset.fn||'').toLowerCase();
    el.style.display=(!q||name.includes(q))?'':'none';
  });
  if(q)document.querySelectorAll('.fn-list').forEach(e=>e.classList.add('vis'));
}

function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

// ── Init ──────────────────────────────────────────────────────────────────────
buildTree();
selectMod('pipeline');
// auto-open pipeline func list
const pfl=document.getElementById('fl-pipeline');if(pfl)pfl.classList.add('vis');
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("=== TDA Pipeline Dashboard 생성기 ===")
    modules_data = {}
    for name, path in MODULE_FILES.items():
        print(f"  파싱: {path.name} ...", end=" ", flush=True)
        data = parse_module(name, path)
        modules_data[name] = data
        status = f"{data['line_count']}줄 · {len(data['functions'])}함수"
        recent = sum(1 for f in data["functions"] if f.get("recently_modified"))
        if recent:
            status += f" · 🔴{recent}개 최근수정"
        print(status)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\nHTML 생성 중...")
    html = build_html(modules_data, PIPELINE_TREE, ts)

    out = DOCS / "pipeline_dashboard.html"
    out.write_text(html, encoding="utf-8")
    size = out.stat().st_size / 1024
    print(f"\n✅ 완료: {out}")
    print(f"   크기: {size:.0f} KB")
    print(f"   열기: file:///{out.as_posix()}")


if __name__ == "__main__":
    main()
