"""
add_cycle_traversal.py
──────────────────────
기존 cycles_metadata.json에 **실제 cycle 연결 순서** (traversal order) 필드를 추가.

배경:
  - cycle_labeled 의 튜플은 vertex 정렬 후 저장되어 있고,
    overlap.py의 _parse_cycle_1d 는 closing edge 처리에서 fallback 이 발동해
    traversal 이 유실된다.
  - 이 스크립트는 export_hibari_data.py 와 동일한 설정 (DFT α=0.25, ow=0.3, dw=1.0,
    decayed lag 1~4) 으로 barcode 를 모든 rate 에서 재생성하고,
    각 cycle 의 raw edge 목록에서 traversal 순서를 직접 복원한다.
  - 복원된 순서를 `traversal_0idx` / `traversal_1idx` 필드로 JSON 에 추가한다.
    기존 `vertices_0idx`, `note_labels_1idx` 등은 유지 (downstream 호환).

안전성:
  - 기존 필드를 수정하지 않음 (순수 additive)
  - 실패 시 해당 cycle 은 traversal_* 를 null 로 둠 → UI 에서는 sorted fallback 으로 재생
"""

from __future__ import annotations
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
HIBARI_DASH = HERE.parent
TDA_ROOT = HIBARI_DASH.parent
sys.path.insert(0, str(TDA_ROOT))
sys.path.insert(0, str(TDA_ROOT / 'experiments'))

import experiments.run_dft_gap0_suite as _suite  # noqa: E402
# MIDI 는 프로젝트 루트에 있음 — suite 의 BASE_DIR 경로(experiments/) 대신 루트로 교정
_ROOT_MIDI = TDA_ROOT / 'Ryuichi_Sakamoto_-_hibari.mid'
if _ROOT_MIDI.exists():
    _suite.MIDI_FILE = str(_ROOT_MIDI)

from experiments.run_dft_gap0_suite import (  # noqa: E402
    setup_hibari, metric_distance_matrix,
)
from weights import (  # noqa: E402
    compute_inter_weights_decayed, compute_out_of_reach,
)
from musical_metrics import compute_hybrid_distance  # noqa: E402
from topology import generate_barcode_numpy  # noqa: E402
from pipeline import compute_distance_matrix  # noqa: E402


JSON_PATH = HIBARI_DASH / 'data' / 'cycles_metadata.json'


def parse_edges(edges_str: str) -> set[tuple[int, int]]:
    """edges_str → 정규화된 edge 집합 (min,max 튜플)."""
    edges_raw = re.findall(r'([+-])?\s*\(\s*(\d+)\s*,\s*(\d+)\)', edges_str)
    edges: set[tuple[int, int]] = set()
    for _sign, v1, v2 in edges_raw:
        a, b = int(v1), int(v2)
        edges.add((min(a, b), max(a, b)))
    return edges


def traverse_cycle(edges: set[tuple[int, int]]) -> list[int] | None:
    """Edge 집합 → 연결된 순서대로 vertex 리스트.

    단순 cycle (각 vertex degree=2) 만 지원. 그 외엔 None.
    """
    if not edges:
        return None
    adj: dict[int, set[int]] = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    # 단순 cycle 검증
    for v, nbrs in adj.items():
        if len(nbrs) != 2:
            return None
    start = min(adj.keys())
    traversal: list[int] = [start]
    prev = None
    current = start
    visited = {start}
    while True:
        next_v = None
        for n in adj[current]:
            if n == prev:
                continue
            if n == start and len(traversal) >= 3:
                # 루프를 닫음 — start 를 다시 추가하지 않음
                return traversal
            if n not in visited:
                next_v = n
                break
        if next_v is None:
            # 단절 — 실패
            return None
        traversal.append(next_v)
        visited.add(next_v)
        prev = current
        current = next_v


def collect_traversals() -> dict[frozenset[int], list[int]]:
    """모든 rate 에서 cycle 을 수집하고 vertex set → traversal 매핑 반환."""
    data = setup_hibari()
    inter = compute_inter_weights_decayed(
        data['adn_i'], max_lag=4, num_chords=data['num_chords'],
    )
    oor = compute_out_of_reach(inter, power=-2)
    musical_dist = metric_distance_matrix(
        data['notes_label'], 'dft', 0.3, 1.0,
    )

    traversal_by_vset: dict[frozenset[int], list[int]] = {}
    rate = 0.0
    n_total = 0
    while rate <= 1.5 + 1e-10:
        timeflow_w = data['intra'] + rate * inter
        freq_dist = compute_distance_matrix(
            timeflow_w, data['notes_dict'], oor,
            num_notes=data['num_notes'],
        ).values
        final_dist = compute_hybrid_distance(freq_dist, musical_dist, alpha=0.25)
        bd = generate_barcode_numpy(
            mat=final_dist, listOfDimension=[1],
            exactStep=True, birthDeathSimplex=False, sortDimension=False,
        )
        for entry in bd:
            if not isinstance(entry, list) or len(entry) < 3:
                continue
            if entry[0] != 1:
                continue
            edges_str = str(entry[2]).strip()
            edges = parse_edges(edges_str)
            if not edges:
                continue
            vset = frozenset(v for e in edges for v in e)
            if vset in traversal_by_vset:
                continue
            trav = traverse_cycle(edges)
            if trav is not None and set(trav) == vset:
                traversal_by_vset[vset] = trav
                n_total += 1
        rate = round(rate + 0.01, 2)

    print(f'[collect] unique traversals = {n_total}')
    return traversal_by_vset


def main() -> int:
    if not JSON_PATH.exists():
        print(f'[err] {JSON_PATH} 없음 — 먼저 export_hibari_data.py 실행하세요.')
        return 1

    with open(JSON_PATH, encoding='utf-8') as f:
        payload = json.load(f)

    traversal_by_vset = collect_traversals()

    matched = 0
    for c in payload['cycles']:
        verts = frozenset(c['vertices_0idx'])
        trav = traversal_by_vset.get(verts)
        if trav is not None:
            c['traversal_0idx'] = trav
            c['traversal_1idx'] = [v + 1 for v in trav]
            matched += 1
        else:
            c['traversal_0idx'] = None
            c['traversal_1idx'] = None
            print(f'  [miss] cycle {c["cycle_idx"]} verts={sorted(verts)} — traversal 미발견')

    # description 업데이트
    extra = (
        ' traversal_1idx 는 cycle edge 를 따라 연결된 순서 (단순 cycle 가정). '
        'UI 미리듣기 재생 순서로 사용.'
    )
    if 'traversal' not in payload.get('description', ''):
        payload['description'] = payload.get('description', '') + extra

    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'[save] {JSON_PATH}  matched={matched}/{len(payload["cycles"])}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
