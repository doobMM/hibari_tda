"""
run_classical_contrast.py — §7.2 확장: 클래식 대조군 실험
=============================================================

"전통적 선율 인과가 강한 곡"에서 거리 함수 패턴을 확인.
  - Ravel Pavane pour une infante défunte (조화로운 화성, 강한 선율)
  - Bach Toccata and Fugue in D minor (대위법, voice-leading 중심)

비교:
  - frequency / tonnetz / voice_leading 세 metric으로 Algo1 JS (N=10)
  - hibari(tonnetz 우위), solari(voice_leading 우위)와 패턴 대비

결과: docs/step3_data/classical_contrast_results.json
"""

import sys, os, json, time, random
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# run_any_track.py의 헬퍼 함수 재사용
from run_any_track import process_one

TRACKS = [
    ("ravel_pavane",  "maurice-ravel-pavane-pour-une-infante-defunte-m-19.mid"),
    ("bach_fugue",    "bach-toccata-and-fugue-in-d-minor-piano-solo.mid"),
]

# 비교 참조값 (논문 §3.1, §7.2)
REFS = {
    "hibari":  {"frequency": 0.0753, "tonnetz": 0.0398, "voice_leading": None,
                "best": "tonnetz",   "note": "diatonic, entropy 0.974"},
    "solari":  {"frequency": 0.0643, "tonnetz": 0.0816, "voice_leading": 0.0631,
                "best": "voice_leading", "note": "chromatic, strong melody"},
    "aqua":    {"frequency": 0.1249, "tonnetz": 0.0920, "voice_leading": None,
                "best": "tonnetz",   "note": "chromatic, Tonnetz 우위"},
}


def main():
    print("=" * 70)
    print("  클래식 대조군 실험: Ravel Pavane + Bach Fugue")
    print("  vs hibari(Tonnetz) / solari(VoiceLeading) 패턴 비교")
    print("=" * 70)

    results = {}

    for name, midi in TRACKS:
        print(f"\n\n{'='*70}")
        print(f"  {name}: {midi}")
        print(f"{'='*70}")

        if not os.path.exists(midi):
            print(f"  MIDI 파일 없음: {midi}")
            results[name] = {'error': f'file not found: {midi}'}
            continue

        result = process_one(name, midi)
        results[name] = result

    # 요약 출력
    print("\n\n" + "=" * 90)
    print("  최종 요약 — 거리 함수별 JS divergence 비교")
    print("=" * 90)

    def fmt_js(r, metric):
        if r and metric in r and isinstance(r[metric], dict) and 'js_mean' in r[metric]:
            return f"{r[metric]['js_mean']:.4f}"
        return "  —   "

    print(f"\n  참조값 (논문 §3.1, §7.2):")
    print(f"  {'곡':20s}  {'freq':>8s}  {'tonnetz':>8s}  {'voice_l':>8s}  {'best':>12s}  비고")
    print("  " + "─" * 78)
    for name, ref in REFS.items():
        f = f"{ref['frequency']:.4f}" if ref['frequency'] else "  —   "
        t = f"{ref['tonnetz']:.4f}"   if ref['tonnetz'] else "  —   "
        v = f"{ref['voice_leading']:.4f}" if ref['voice_leading'] else "  —   "
        print(f"  {name:20s}  {f:>8s}  {t:>8s}  {v:>8s}  {ref['best']:>12s}  {ref['note']}")

    print(f"\n  이번 실험:")
    print(f"  {'곡':20s}  {'freq':>8s}  {'tonnetz':>8s}  {'voice_l':>8s}  {'best':>12s}")
    print("  " + "─" * 70)
    for name, r in results.items():
        if 'error' in r:
            print(f"  {name:20s}  ERROR: {r['error']}")
            continue
        freq_s = fmt_js(r, 'frequency')
        tonn_s = fmt_js(r, 'tonnetz')
        vl_s   = fmt_js(r, 'voice_leading')
        best   = r.get('best_metric', '?')
        print(f"  {name:20s}  {freq_s:>8s}  {tonn_s:>8s}  {vl_s:>8s}  {best:>12s}")

    # JSON 저장
    od = 'docs/step3_data'
    os.makedirs(od, exist_ok=True)
    out = f'{od}/classical_contrast_results.json'

    save_data = {
        'tracks': {name: results[name] for name in results},
        'refs': REFS,
        'interpretation': {
            'hypothesis': (
                "'전통적 선율 인과가 강한 곡'(Bach)에서는 voice_leading이 우위를 가지고, "
                "diatonic 화성이 명확한 곡(Ravel)에서는 tonnetz가 우위를 가질 것"
            ),
        }
    }
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    print(f"\nJSON 저장: {out}")

    # 가설 검증
    print("\n[가설 검증]")
    for name, r in results.items():
        if 'error' in r or 'best_metric' not in r:
            continue
        best = r['best_metric']
        if best == 'voice_leading':
            print(f"  {name}: voice_leading 우위 → 선율/대위법 패턴 확인")
        elif best == 'tonnetz':
            print(f"  {name}: tonnetz 우위 → 화성적 구조 패턴 확인")
        elif best == 'frequency':
            print(f"  {name}: frequency 우위 → 특이 패턴 (추가 분석 필요)")


if __name__ == "__main__":
    main()
