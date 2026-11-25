"""가이드·README용 스크린샷을 예시 데이터로 다시 만듭니다 (UI를 바꾼 뒤 실행).

프로젝트 루트에서 실행:
    venv\\Scripts\\python.exe docs\\guide\\make_screenshots.py

- 실제 감상 기록이나 설정 파일은 읽지도 쓰지도 않습니다 (임시 폴더 사용).
- 재생 버튼은 미디어 키를 보내지 않도록 막아 둡니다.
- 결과: docs/guide/images/*.png, asset/screenshots/*.png
"""

import os
import random
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE_IMAGES = Path(__file__).resolve().parent / "images"
README_IMAGES = ROOT / "asset" / "screenshots"
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from PySide6.QtCore import QPoint, QPointF  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QBrush, QColor, QEnterEvent, QImage, QLinearGradient, QPainter, QRadialGradient,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import gui.widgets.media_controls as media_controls  # noqa: E402

media_controls._BUTTONS = tuple(
    (key, glyph, tip, (lambda: None)) for key, glyph, tip, _ in media_controls._BUTTONS
)

from gui.main_window import MainWindow  # noqa: E402

# ------------------------------------------------------------------ #
# 예시 데이터
# ------------------------------------------------------------------ #
SAMPLE_SONGS = [
    ("Hype Boy", "NewJeans"), ("Love wins all", "아이유"), ("Supernova", "aespa"),
    ("Magnetic", "아일릿"), ("밤양갱", "비비"), ("To. X", "태연"), ("Drama", "aespa"),
]
# 화면용으로 지어낸 문장입니다 (실제 가사 아님).
SAMPLE_LYRIC = "문득 마주친 너의 눈빛 그 안에서 빛나는 별"
SAMPLE_NEXT = "끝없이 펼쳐진 밤하늘 위로"

random.seed(3)
now = datetime.now()
history = []
for _ in range(60):
    title, artist = random.choice(SAMPLE_SONGS)
    ts = now - timedelta(days=random.randint(0, 40), hours=random.randint(0, 20))
    history.append({
        "title": title, "artist": artist, "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "play_time_sec": 200, "lines": 30,
    })
history.sort(key=lambda e: e["timestamp"], reverse=True)

tmp_dir = tempfile.mkdtemp()


class _SampleConfig:
    data_dir = tmp_dir

    def set_data_dir(self, new_dir):
        return True


window = MainWindow(
    stats={"play_history": history, "total_lines": 0, "total_play_time_sec": 0},
    app_config=_SampleConfig(),
)
window.music_page.set_history(history[:20])
window.show()

dash = window.dashboard_page
dash.update_stats(
    {"play_count": 12, "session_lines": 340, "session_duration": 2580, "lines": 0}, history
)
dash.set_now_playing("Supernova", "aespa")
dash.curr_lyric.setText(SAMPLE_LYRIC)
for t, msg in [
    ("12:04:17", "프로그램 시작"),
    ("12:04:21", "새로운 곡 감지: Supernova - aespa"),
    ("12:04:22", "✅ 로드 성공: Supernova - aespa (52줄)"),
    ("12:04:23", "멜론 창: 숨김"),
]:
    dash.log_list.addItem(f"[{t}] {msg}")


def settle() -> None:
    for _ in range(3):
        app.processEvents()


def shot(path: Path) -> None:
    settle()
    window.grab().save(str(path))
    print("saved", path.relative_to(ROOT))


def set_theme(name: str) -> None:
    if window.theme_manager.current_theme["name"] != name:
        window.toggle_theme()


GUIDE_IMAGES.mkdir(parents=True, exist_ok=True)
README_IMAGES.mkdir(parents=True, exist_ok=True)

# 라이트 모드
set_theme("light")
window.switch_page(0)
shot(GUIDE_IMAGES / "dashboard_light.png")
shot(README_IMAGES / "dashboard_light.png")
window.switch_page(3)
window.setting_page._switch_page(0)
shot(GUIDE_IMAGES / "settings_appearance_light.png")
window.setting_page._switch_page(1)
shot(GUIDE_IMAGES / "settings_behavior_light.png")

# 다크 모드
set_theme("dark")
window.switch_page(2)
shot(GUIDE_IMAGES / "stats_dark.png")
window.switch_page(3)
window.setting_page._switch_page(1)
shot(README_IMAGES / "settings_dark.png")

# ------------------------------------------------------------------ #
# 오버레이 (바탕화면 느낌의 배경 위에 합성)
# ------------------------------------------------------------------ #
overlay = window.overlay
overlay.config.font_family = "Pretendard"
overlay.sync_with_config()
overlay.set_ghost_mode(False)
overlay.resize(760, 140)
overlay.update_song_info("Supernova", "aespa")
overlay.update_lyrics(SAMPLE_LYRIC, SAMPLE_NEXT)
QApplication.sendEvent(overlay, QEnterEvent(QPointF(10, 10), QPointF(10, 10), QPointF(10, 10)))
settle()

grab = overlay.grab().toImage()
W, H = 900, 240
canvas = QImage(W, H, QImage.Format_ARGB32)
p = QPainter(canvas)
bg = QLinearGradient(0, 0, W, H)
bg.setColorAt(0, QColor("#2B3A67"))
bg.setColorAt(0.5, QColor("#5B4B8A"))
bg.setColorAt(1, QColor("#1F6F8B"))
p.fillRect(canvas.rect(), bg)
glow = QRadialGradient(QPointF(W * 0.8, H * 0.2), 260)
glow.setColorAt(0, QColor(255, 180, 120, 120))
glow.setColorAt(1, QColor(255, 180, 120, 0))
p.fillRect(canvas.rect(), QBrush(glow))
p.drawImage(QPoint((W - grab.width()) // 2, (H - grab.height()) // 2), grab)
p.end()
canvas.save(str(GUIDE_IMAGES / "overlay.png"))
print("saved", (GUIDE_IMAGES / "overlay.png").relative_to(ROOT))

overlay.close()
window.close()
