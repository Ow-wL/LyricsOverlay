"""
LyricsOverlay — 엔트리 포인트
실행: python main.py
"""

import asyncio
import sys
import time
import os
import ctypes

if os.name == 'nt':
    try:
        myappid = 'owwl.lyricsoverlay.app.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

import cv2
import pygetwindow as gw  # type: ignore
from PySide6.QtCore import QSize  # type: ignore
from PySide6.QtWidgets import QApplication, QLabel, QListWidgetItem  # type: ignore

from core.hotkey_manager import HotkeyManager
from core.ocr_engine import windows_native_ocr_split
from core.stats_manager import load_stats, make_session_stats, parse_song_info, save_stats
from core.window_capture import apply_transparency, capture_covered_window
from gui.main_window import MainWindow
from lyrics.matcher import LyricMatcher
from core.app_config import AppConfig
from overlay.config_manager import OverlayConfigManager

# ------------------------------------------------------------------ #
# 전역 상태
# ------------------------------------------------------------------ #
log_history: list[str] = []
is_running: bool = True
_window: MainWindow | None = None

persistent_stats: dict = {}
session_stats: dict = {}
_app_config: AppConfig | None = None


# ------------------------------------------------------------------ #
# 로그
# ------------------------------------------------------------------ #

def add_log(message: str) -> None:
    """최근 5개 로그를 유지하며 GUI 리스트에도 연동합니다."""
    global log_history, _window
    timestamp = time.strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    log_history.append(log_msg)
    if len(log_history) > 5:
        log_history.pop(0)

    if _window:
        _window.dashboard_page.log_list.addItem(log_msg)
        if _window.dashboard_page.log_list.count() > 50:
            _window.dashboard_page.log_list.takeItem(0)
        _window.dashboard_page.log_list.scrollToBottom()


# ------------------------------------------------------------------ #
# 단축키 콜백
# ------------------------------------------------------------------ #

def _on_toggle_mode() -> None:
    if _window is None:
        return
    cfg: OverlayConfigManager = _window.config_manager
    cfg.set_ghost_mode(not cfg.ghost_mode)
    mode_name = "반투명 + 클릭통과" if cfg.ghost_mode else "불투명 + 클릭가능"
    print(f"\n[🔔] 모드 전환: {mode_name}")
    add_log(f"모드 전환: {mode_name}")


def _on_quit() -> None:
    global is_running
    is_running = False
    print("\n[🔔] 프로그램 종료 요청됨.")
    add_log("프로그램 종료 요청됨")
    QApplication.quit()


# ------------------------------------------------------------------ #
# 메인 루프
# ------------------------------------------------------------------ #

async def main() -> None:
    global _window, is_running, persistent_stats, session_stats, _app_config

    app = QApplication(sys.argv)
    
    _app_config = AppConfig()
    persistent_stats = load_stats(_app_config.data_dir)
    session_stats = make_session_stats(persistent_stats)

    # 메인 윈도우 생성
    initial_theme = persistent_stats.get("theme", "light")
    window = MainWindow(stats=persistent_stats, app_config=_app_config, initial_theme=initial_theme)
    _window = window

    # 테마 저장
    def on_theme_changed(theme_name: str) -> None:
        persistent_stats["theme"] = theme_name
        save_stats(persistent_stats, _app_config.data_dir)
        add_log(f"테마 변경: {theme_name}")

    window.theme_changed.connect(on_theme_changed)

    def on_window_closed() -> None:
        global is_running
        is_running = False
        print("\n[🔔] GUI 종료 감지. 백그라운드 루프 중지...")

    window.window_closed.connect(on_window_closed)

    # 히스토리 목록 초기화
    for entry in persistent_stats.get("play_history", []):
        full_title = f"{entry['title']} - {entry['artist']}"
        try:
            date_part = entry["timestamp"].split(" ")[0][2:].replace("-", ".")
        except Exception:
            date_part = entry.get("timestamp", "")
        item = QListWidgetItem(f"{full_title} ({date_part})")
        item.setSizeHint(QSize(0, 60))
        window.music_page.music_list.addItem(item)

    window.show()

    overlay = window.overlay
    config_manager = window.config_manager
    matcher = LyricMatcher()

    # 단축키 매니저
    hotkey_mgr = HotkeyManager(on_ghost_toggle=_on_toggle_mode, on_quit=_on_quit)

    def refresh_hotkeys() -> None:
        hotkey_mgr.refresh(
            config_manager.hotkey_ghost,
            config_manager.hotkey_quit,
            log_fn=add_log,
        )

    window.setting_page.settings_changed.connect(window.update_overlay)
    window.setting_page.hotkeys_changed.connect(refresh_hotkeys)
    refresh_hotkeys()
    
    # 대시보드 통계 초기 업데이트
    window.dashboard_page.update_stats(session_stats, persistent_stats.get("play_history", []))

    print("=" * 50)
    print("🎤 가사 대시보드 및 오버레이 실행 중")
    print("=" * 50)
    add_log("프로그램 시작")

    exclude = [
        "Visual Studio Code", "Whale", "Gemini", "OBS", "Overlay",
        "Discord", "파일 탐색기", "메모장", "PowerPoint", "한글",
        "Hancom", "Hwp", "Edge", "Antigravity"
    ]

    last_hwnd = None
    last_song_title = ""
    last_lyric_text = ""
    last_applied_mode = None
    save_timer = 0.0
    
    current_song_info = None
    current_song_start_time = 0.0
    current_song_lines = 0

    try:
        while is_running:
            app.processEvents()

            target_win = None
            all_windows = gw.getAllWindows()

            # 1순위: 'Melon' 포함 창
            for w in all_windows:
                if "Melon" in w.title and not any(ex in w.title for ex in exclude):
                    if w.width > 200 and not w.isMinimized:
                        target_win = w
                        break

            # 2순위: ' - ' 형식
            if not target_win:
                for w in all_windows:
                    if " - " in w.title and not any(ex in w.title for ex in exclude):
                        if w.width > 200 and not w.isMinimized:
                            target_win = w
                            break

            if target_win:
                hwnd = target_win._hWnd
                last_hwnd = hwnd
                is_ghost_mode = config_manager.ghost_mode

                # 모드 변경 시 창 스타일 적용
                if is_ghost_mode != last_applied_mode:
                    apply_transparency(hwnd, is_ghost_mode)
                    overlay.set_ghost_mode(is_ghost_mode)
                    last_applied_mode = is_ghost_mode
                    add_log(f"창 스타일 변경 완료: {'고스트' if is_ghost_mode else '일반'}")

                # 곡 변경 감지
                current_song_title = target_win.title.replace(" - Melon", "").strip()
                if current_song_title != last_song_title:
                    last_song_title = current_song_title
                    if current_song_title:
                        session_stats["play_count"] += 1
                        title, artist = parse_song_info(current_song_title)
                        timestamp_full = time.strftime("%Y-%m-%d %H:%M:%S")
                        timestamp_short = time.strftime("%y.%m.%d")
                        
                        current_song_start_time = time.time()
                        current_song_lines = 0
                        matcher.reset_recent()  # 새 곡 시작 시 매핑 이력 초기화
                        current_song_info = {
                            "title": title,
                            "artist": artist,
                            "timestamp": timestamp_full,
                            "play_time_sec": 0,
                            "lines": 0
                        }

                        item = QListWidgetItem(f"{current_song_title} ({timestamp_short})")
                        item.setSizeHint(QSize(0, 60))
                        window.music_page.music_list.insertItem(0, item)

                        persistent_stats["play_history"].insert(0, current_song_info)
                        add_log(f"새로운 곡 감지: {current_song_title}")
                        save_stats(persistent_stats, _app_config.data_dir)

                # 캡처 및 OCR
                full_img = capture_covered_window(hwnd)
                if full_img is not None:
                    roi = full_img[216:216 + 46, 28:28 + 251]
                    scaled = cv2.resize(roi, None, fx=5, fy=5, interpolation=cv2.INTER_LANCZOS4)

                    lines = await windows_native_ocr_split(scaled)

                    fixed_lines: list[str] = []
                    for line in lines:
                        fixed_text, status = matcher.get_best_match(line, target_win.title)
                        if status:
                            add_log(status)
                        fixed_lines.append(fixed_text)

                    # 터미널 출력
                    print("\033[H\033[J")
                    mode_status = "👻 게임 모드" if is_ghost_mode else "🖱️  조작 모드"
                    print(f"상태: {mode_status} | 대상: {target_win.title}")
                    print("-" * 40)

                    curr = fixed_lines[0] if len(fixed_lines) > 0 else "..."
                    nxt = fixed_lines[1] if len(fixed_lines) > 1 else ""

                    if curr != "..." and curr != last_lyric_text:
                        session_stats["lines"] += 1
                        session_stats["session_lines"] += 1
                        last_lyric_text = curr
                        persistent_stats["total_lines"] = session_stats["lines"]
                        
                        if current_song_info is not None:
                            current_song_lines += 1
                            current_song_info["lines"] = current_song_lines

                    if current_song_info is not None:
                        current_song_info["play_time_sec"] = int(time.time() - current_song_start_time)

                    print(f"🔥 현재: {curr}")
                    print(f"💤 다음: {nxt}")
                    print("-" * 40)
                    print("[ 시스템 로그 ]")
                    for log in log_history:
                        print(f" > {log}")

                    # 오버레이 + 대시보드 업데이트
                    overlay.update_lyrics(curr, nxt)
                    window.dashboard_page.curr_lyric.setText(curr)

                    session_duration = time.time() - session_stats["start_time"]
                    session_stats["session_duration"] = session_duration
                    total_play_time_sec = session_stats["base_play_time"] + session_duration
                    persistent_stats["total_play_time_sec"] = int(total_play_time_sec)

                    window.dashboard_page.update_stats(session_stats, persistent_stats.get("play_history", []))

                    # 1분마다 자동 저장
                    save_timer += 0.05
                    if save_timer >= 60:
                        save_stats(persistent_stats, _app_config.data_dir)
                        save_timer = 0.0

                    QApplication.processEvents()

            await asyncio.sleep(0.05)

    finally:
        if _app_config:
            save_stats(persistent_stats, _app_config.data_dir)
        if last_hwnd:
            print("\n[🧹] 멜론 창 상태 원복 중...")
            apply_transparency(last_hwnd, False)
        hotkey_mgr.unhook_all()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    asyncio.run(main())
