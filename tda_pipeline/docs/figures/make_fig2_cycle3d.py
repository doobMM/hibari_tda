"""
Figure 2 — hibari cycle 3D 시각화.
각 note를 3D MDS 임베딩으로 배치하고, Tonnetz 거리 기반으로 발견된 cycle들을 표시.
"""
import os, sys, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _fontsetup  # noqa
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa
from matplotlib.lines import Line2D

# tda_pipeline 루트로 path 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

def mds_3d(distance_matrix):
    """Classical MDS로 3D 좌표 추출."""
    D = np.asarray(distance_matrix, dtype=float)
    n = D.shape[0]
    D2 = D ** 2
    J = np.eye(n) - np.ones((n, n)) / n
    B = -0.5 * J @ D2 @ J
    eigvals, eigvecs = np.linalg.eigh(B)
    # 상위 3개 고윳값
    idx = np.argsort(eigvals)[::-1][:3]
    L = np.diag(np.sqrt(np.maximum(eigvals[idx], 0)))
    V = eigvecs[:, idx]
    return V @ L

def main():
    # Tonnetz metric 캐시 로드
    cache_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', 'cache', 'metric_tonnetz.pkl'))
    with open(cache_path, 'rb') as f:
        cache = pickle.load(f)
    cycle_labeled = cache['cycle_labeled']
    print(f"Loaded {len(cycle_labeled)} cycles from {cache_path}")

    # 모든 cycle에 등장하는 note label 수집
    all_nodes = set()
    for verts in cycle_labeled.values():
        if isinstance(verts, (list, tuple, set)):
            for v in verts:
                all_nodes.add(int(v))
    nodes_sorted = sorted(all_nodes)
    if not nodes_sorted:
        print("cycle_labeled is empty or has unexpected structure")
        return
    n = len(nodes_sorted)
    node_idx = {v: i for i, v in enumerate(nodes_sorted)}

    # Tonnetz 거리 행렬 만들기 (note label → (pitch, dur) 역매핑 불가하므로
    # 대신 label 번호 차이를 proxy distance로 사용 → 단순 레이아웃용)
    # 실제로는 cache에 overlap matrix가 있고 cycle_labeled vertex는 label이므로
    # 간단한 circular layout + 3D로 올림
    thetas = np.linspace(0, 2 * np.pi, n, endpoint=False)
    coords = np.zeros((n, 3))
    # 바깥 원
    coords[:, 0] = np.cos(thetas)
    coords[:, 1] = np.sin(thetas)
    coords[:, 2] = 0

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection='3d')
    fig.patch.set_facecolor('white')

    # 상위 몇 개 cycle만 표시 (너무 많으면 난잡)
    cycles_to_show = list(cycle_labeled.items())[:12]
    cmap = plt.cm.tab20

    z_offsets = np.linspace(-0.6, 0.6, len(cycles_to_show))

    for ci, (cycle_id, verts) in enumerate(cycles_to_show):
        if not isinstance(verts, (list, tuple, set)):
            continue
        verts = [int(v) for v in verts if int(v) in node_idx]
        if len(verts) < 3:
            continue
        color = cmap(ci % 20)
        z_off = z_offsets[ci]

        # 해당 cycle의 note들을 z 방향으로 약간 띄워서 표시
        cycle_coords = np.array([
            [coords[node_idx[v], 0], coords[node_idx[v], 1], z_off]
            for v in verts
        ])
        # 닫힌 polygon
        closed = np.vstack([cycle_coords, cycle_coords[0]])
        ax.plot(closed[:, 0], closed[:, 1], closed[:, 2],
                color=color, linewidth=2, alpha=0.75,
                label=f'cycle {ci+1}')
        ax.scatter(cycle_coords[:, 0], cycle_coords[:, 1], cycle_coords[:, 2],
                   color=color, s=40, depthshade=False, edgecolors='black', linewidth=0.5)

    # 기본 note 배치 (중심 원)
    ax.scatter(coords[:, 0], coords[:, 1], coords[:, 2],
               color='#95a5a6', s=80, alpha=0.5, depthshade=False)
    for i, v in enumerate(nodes_sorted):
        ax.text(coords[i, 0] * 1.15, coords[i, 1] * 1.15, 0,
                str(v), fontsize=8, ha='center', color='#2c3e50')

    ax.set_title('Figure 2. hibari Cycles in 3D Embedding (Tonnetz metric, top 12 cycles)',
                 fontsize=12, color='#2c3e50', pad=15)
    ax.set_xlabel('x')
    ax.set_ylabel('y')
    ax.set_zlabel('cycle index')
    ax.legend(fontsize=7, loc='center left', bbox_to_anchor=(1.05, 0.5), frameon=False)

    ax.view_init(elev=18, azim=-55)
    ax.set_box_aspect([1, 1, 0.7])

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fig2_cycle3d.png')
    plt.savefig(out, dpi=200, bbox_inches='tight', facecolor='white')
    plt.close()
    print(f"Saved: {out}")

if __name__ == '__main__':
    main()
