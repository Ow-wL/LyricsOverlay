r"""가이드·README용 스크린샷을 예시 데이터로 다시 만듭니다 (UI를 바꾼 뒤 실행).

프로젝트 루트에서 실행:
    venv\Scripts\python.exe docs\guide\make_screenshots.py

- 실제 감상 기록이나 설정 파일은 읽지도 쓰지도 않습니다 (임시 폴더 사용).
- 재생 버튼은 미디어 키를 보내지 않도록 막아 둡니다. 네트워크(업데이트 확인·가사 검색)도 쓰지 않습니다.
- 가사 문장과 플레이어 화면은 예시용으로 지어내거나 그린 것입니다.
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

import numpy as np  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QBrush, QColor, QEnterEvent, QFont, QImage, QLinearGradient, QPainter, QRadialGradient,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)

import gui.widgets.media_controls as media_controls  # noqa: E402

media_controls._BUTTONS = tuple(
    (key, glyph, tip, (lambda: None)) for key, glyph, tip, _ in media_controls._BUTTONS
)

from core.updater import ReleaseInfo  # noqa: E402
from core.version import APP_VERSION  # noqa: E402
from gui.main_window import MainWindow  # noqa: E402
from gui.roi_selector import RoiSelectDialog  # noqa: E402
from gui.update_dialog import UpdateDialog  # noqa: E402

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
    ts = now - timedelta(days=random.randint(0, 40), hours=random.randint(0, 20), minutes=random.randint(0, 59))
    history.append({
        "title": title, "artist": artist, "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "play_time_sec": random.randint(150, 240), "lines": random.randint(20, 45),
    })
history.sort(key=lambda e: e["timestamp"], reverse=True)

tmp_dir = tempfile.mkdtemp()


class _SampleConfig:
    data_dir = tmp_dir
    record_history = True
    auto_update_check = True
    skipped_version = ""
    auto_backfill = False
    diagnostic_log = True

    def set_data_dir(self, new_dir, overwrite_existing=False):
        return True

    def add_listener(self, fn):
        pass


window = MainWindow(
    stats={"play_history": history, "total_lines": 0, "total_play_time_sec": 0},
    app_config=_SampleConfig(),
)
window.resize(1280, 760)
window.music_page.set_history(history)
window.show()

dash = window.dashboard_page
dash.update_stats(
    {"play_count": 12, "session_lines": 340, "session_duration": 2580, "lines": 0}, history
)
for t, msg in [
    ("12:04:17", "프로그램 시작"),
    ("12:04:21", "새로운 곡 감지: Supernova - aespa"),
    ("12:04:22", "가사 불러옴: Supernova - aespa (52줄)"),
    ("12:04:23", "멜론 창: 숨김"),
]:
    dash.log_list.addItem(f"[{t}] {msg}")


def settle() -> None:
    for _ in range(4):
        app.processEvents()


def save(img, name: str, readme: bool = False) -> None:
    targets = [GUIDE_IMAGES / name] + ([README_IMAGES / name] if readme else [])
    for path in targets:
        img.save(str(path))
        print("saved", path.relative_to(ROOT))


def shot(name: str, widget=None, readme: bool = False) -> None:
    settle()
    save((widget or window).grab(), name, readme)


def set_theme(name: str) -> None:
    if window.theme_manager.current_theme["name"] != name:
        window.toggle_theme()


def desktop_backdrop(w: int, h: int) -> QImage:
    """오버레이를 올려 보여 줄 바탕화면 느낌의 배경."""
    canvas = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(canvas)
    bg = QLinearGradient(0, 0, w, h)
    bg.setColorAt(0, QColor("#2B3A67"))
    bg.setColorAt(0.5, QColor("#5B4B8A"))
    bg.setColorAt(1, QColor("#1F6F8B"))
    p.fillRect(canvas.rect(), bg)
    glow = QRadialGradient(QPointF(w * 0.8, h * 0.2), 260)
    glow.setColorAt(0, QColor(255, 180, 120, 120))
    glow.setColorAt(1, QColor(255, 180, 120, 0))
    p.fillRect(canvas.rect(), QBrush(glow))
    p.end()
    return canvas


def overlay_on_desktop(name: str, readme: bool = False) -> None:
    settle()
    grab = window.overlay.grab().toImage()
    canvas = desktop_backdrop(900, 240)
    p = QPainter(canvas)
    p.drawImage(QPoint((canvas.width() - grab.width()) // 2, (canvas.height() - grab.height()) // 2), grab)
    p.end()
    save(canvas, name, readme)


def mock_player_capture() -> np.ndarray:
    """가사 영역 지정 화면에 쓸 '음악 플레이어 창' 예시 그림 (실제 프로그램 화면이 아님)."""
    w, h = 320, 420
    img = QImage(w, h, QImage.Format_RGB888)
    img.fill(QColor("#1E1F24"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.fillRect(0, 0, w, 34, QColor("#2A2B31"))
    f = QFont("Pretendard")
    f.setPixelSize(12)
    p.setFont(f)
    p.setPen(QColor("#9A9CA8"))
    p.drawText(QRectF(12, 0, w, 34), Qt.AlignVCenter, "Supernova - aespa")
    cover = QLinearGradient(60, 50, 260, 200)
    cover.setColorAt(0, QColor("#6C5CF6"))
    cover.setColorAt(1, QColor("#1F6F8B"))
    p.setBrush(cover)
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(90, 52, 140, 140), 10, 10)
    f.setPixelSize(13)
    f.setBold(True)
    p.setFont(f)
    p.setPen(QColor("#FFFFFF"))
    p.drawText(QRectF(0, 216, w, 22), Qt.AlignHCenter, SAMPLE_LYRIC)
    f.setBold(False)
    f.setPixelSize(13)
    p.setFont(f)
    p.setPen(QColor("#8D8FA0"))
    p.drawText(QRectF(0, 240, w, 20), Qt.AlignHCenter, SAMPLE_NEXT)
    p.setBrush(QColor("#3A3B42"))
    p.drawRoundedRect(QRectF(30, 300, w - 60, 4), 2, 2)
    p.setBrush(QColor("#6C5CF6"))
    p.drawRoundedRect(QRectF(30, 300, (w - 60) * 0.42, 4), 2, 2)
    for i, cx in enumerate((110, 160, 210)):
        p.setBrush(QColor("#FFFFFF") if i == 1 else QColor("#55576A"))
        p.drawEllipse(QPointF(cx, 350), 16 if i == 1 else 11, 16 if i == 1 else 11)
    p.end()
    ptr = img.constBits()
    arr = np.frombuffer(ptr, np.uint8).reshape(h, img.bytesPerLine())[:, : w * 3].reshape(h, w, 3)
    return arr[:, :, ::-1].copy()  # RGB → BGR (앱이 쓰는 형식)


GUIDE_IMAGES.mkdir(parents=True, exist_ok=True)
README_IMAGES.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ #
# 라이트 모드
# ------------------------------------------------------------------ #
set_theme("light")

# 첫 실행 시작 안내
window.switch_page(0)
dash.set_status("warn", "멜론을 찾고 있어요", "멜론 PC 플레이어를 실행하고 가사가 보이게 띄워 주세요.")
shot("dashboard_onboarding_light.png")

# 일반 대시보드
dash.finish_onboarding()
window.set_now_playing("Supernova", "aespa")
dash.set_status("ok", "가사를 인식하고 있어요")
dash.curr_lyric.setText(SAMPLE_LYRIC)
shot("dashboard_light.png", readme=True)

# 업데이트 알림
release = ReleaseInfo(
    version="1.3.0", html_url="https://github.com/Ow-wL/LyricsOverlay/releases",
    notes="1. (예시) 새 기능 설명\n2. (예시) 버그 수정 내용",
    exe_url="https://github.com/Ow-wL/LyricsOverlay/releases/download/1.3.0/LyricsOverlay.exe",
    exe_size=125 * 1024 * 1024, exe_sha256="0" * 64,
)
window._can_self_update = staticmethod(lambda: True)
window.show_update_available(release, manual=True)
shot("update_banner_light.png")
dlg = UpdateDialog(release, window)
dlg.show()
shot("update_dialog_light.png", dlg)
dlg.close()
dash.update_banner.hide()

# 감상 기록
window.switch_page(1)
shot("history_light.png", readme=True)

# 설정
window.switch_page(3)
sp = window.setting_page
sp._switch_page(0)
shot("settings_appearance_light.png")
sp._switch_page(1)
shot("settings_behavior_light.png")
behavior = sp.stack.widget(1)
behavior.verticalScrollBar().setValue(behavior.verticalScrollBar().maximum())
shot("settings_behavior_roi_light.png")
behavior.verticalScrollBar().setValue(0)
sp._switch_page(2)
shot("settings_hotkeys_light.png")
sp._switch_page(3)
# 실제 임시 폴더 경로(PC 사용자 이름 포함)가 찍히지 않게 예시 경로로 바꿉니다.
sp.lbl_data_path.setText(r"C:\Users\사용자\Documents\LyricsOverlay")
shot("settings_system_light.png")

# 가사 인식 영역 지정
roi = RoiSelectDialog(mock_player_capture(), [24, 210, 272, 54], window)
roi.show()
shot("roi_select_light.png", roi, readme=True)
roi.close()

# 정보 (업데이트 확인)
window.switch_page(4)
window.info_page.set_update_status(f"최신 버전을 쓰고 있어요 ({APP_VERSION})")
shot("info_light.png")

# ------------------------------------------------------------------ #
# 다크 모드
# ------------------------------------------------------------------ #
set_theme("dark")
window.switch_page(2)
shot("stats_dark.png")
window.switch_page(3)
sp._switch_page(0)
shot("settings_dark.png", readme=True)

# ------------------------------------------------------------------ #
# 오버레이 (바탕화면 느낌의 배경 위에 합성)
# ------------------------------------------------------------------ #
overlay = window.overlay
overlay.config.font_family = "Pretendard"
overlay.config.visible = True
overlay.sync_with_config()
overlay.set_ghost_mode(False)
overlay.resize(760, 140)
overlay.update_song_info("Supernova", "aespa")
overlay.update_lyrics(SAMPLE_LYRIC, SAMPLE_NEXT)
QApplication.sendEvent(overlay, QEnterEvent(QPointF(10, 10), QPointF(10, 10), QPointF(10, 10)))
overlay_on_desktop("overlay.png", readme=True)

overlay.media_controls.hide()
overlay.set_edit_mode(True)
overlay_on_desktop("overlay_edit.png")
overlay.set_edit_mode(False)

overlay.close()
window.close()
