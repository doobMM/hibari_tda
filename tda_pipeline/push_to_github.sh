#!/bin/bash
# ─────────────────────────────────────────────────────
# TDA Music Pipeline - GitHub Push Helper
# ─────────────────────────────────────────────────────
# 이 스크립트를 기존 WK14 저장소 루트에서 실행하세요.
#
# 사용법:
#   chmod +x push_to_github.sh
#   ./push_to_github.sh
# ─────────────────────────────────────────────────────

set -e

echo "╔══════════════════════════════════════════════╗"
echo "║  TDA Music Pipeline - GitHub Push            ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# 1. 새 파일들을 올바른 위치에 복사
PIPELINE_DIR="tda_music_pipeline"

if [ ! -d "$PIPELINE_DIR" ]; then
    echo "⚠ '$PIPELINE_DIR' 디렉토리를 찾을 수 없습니다."
    echo "  → 다운로드한 파일들을 '$PIPELINE_DIR/' 폴더에 넣어주세요."
    exit 1
fi

# 2. 기존 professor.py를 파이프라인 디렉토리에 복사 (심볼릭 링크)
if [ -f "WK14/professor.py" ]; then
    cp WK14/professor.py "$PIPELINE_DIR/professor.py"
    echo "✓ professor.py 복사됨"
elif [ -f "professor.py" ]; then
    cp professor.py "$PIPELINE_DIR/professor.py"
    echo "✓ professor.py 복사됨"
else
    echo "⚠ professor.py를 찾을 수 없습니다. 수동으로 복사해주세요."
fi

# 3. pickle 디렉토리 링크
if [ -d "WK14/pickle" ]; then
    if [ ! -d "$PIPELINE_DIR/pickle" ]; then
        cp -r WK14/pickle "$PIPELINE_DIR/pickle"
        echo "✓ pickle 디렉토리 복사됨"
    fi
fi

# 4. MIDI 파일 링크
MIDI_FILE="Ryuichi_Sakamoto_-_hibari.mid"
if [ -f "WK14/$MIDI_FILE" ]; then
    cp "WK14/$MIDI_FILE" "$PIPELINE_DIR/$MIDI_FILE"
    echo "✓ MIDI 파일 복사됨"
elif [ -f "$MIDI_FILE" ]; then
    cp "$MIDI_FILE" "$PIPELINE_DIR/$MIDI_FILE"
    echo "✓ MIDI 파일 복사됨"
else
    echo "⚠ MIDI 파일을 찾을 수 없습니다. 수동으로 복사해주세요."
fi

# 5. Git 작업
echo ""
echo "─── Git 작업 ───"

git add "$PIPELINE_DIR/"
git status

echo ""
echo "위 파일들을 커밋하시겠습니까? (y/n)"
read -r response

if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
    git commit -m "feat: TDA music pipeline restructured with optimizations

- refine_connectedness: 4중 루프 → numpy 행렬 곱 (~10-50x 속도 향상)
- Algorithm 1: onset_checker set 기반, 무한루프 방지, inst_len 버그 수정
- Algorithm 2: 미니배치 학습, 데이터 정합성 수정
- 파이프라인 캐싱으로 부분 재실행 지원
- 모듈 분리로 순환 의존성 제거"

    echo ""
    echo "push하시겠습니까? (y/n)"
    read -r push_response
    
    if [ "$push_response" = "y" ] || [ "$push_response" = "Y" ]; then
        git push
        echo "✓ Push 완료!"
    else
        echo "→ 나중에 'git push'로 push할 수 있습니다."
    fi
else
    echo "→ 나중에 수동으로 커밋/push할 수 있습니다."
fi

echo ""
echo "완료! 테스트하려면:"
echo "  cd $PIPELINE_DIR"
echo "  python run_test.py"
echo ""
