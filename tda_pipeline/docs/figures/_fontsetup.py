"""figure 공통 폰트 설정 — NanumGothic 사용."""
import os
import matplotlib as mpl
from matplotlib import font_manager

NANUM = os.path.expanduser('~/AppData/Local/Microsoft/Windows/Fonts/NanumGothic.ttf')
if os.path.exists(NANUM):
    font_manager.fontManager.addfont(NANUM)
    # 폰트 이름 확인
    fp = font_manager.FontProperties(fname=NANUM)
    name = fp.get_name()
    mpl.rcParams['font.family'] = name
    mpl.rcParams['axes.unicode_minus'] = False
else:
    mpl.rcParams['font.family'] = 'Malgun Gothic'
    mpl.rcParams['axes.unicode_minus'] = False
