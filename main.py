"""
LyricsOverlay — 엔트리 포인트
실행: python main.py
"""

import asyncio
import queue
import sys
import time
import os
import ctypes

# 콘솔 출력이 파이프/cp949일 때 이모지 로그 하나로 프로그램이 죽지 않도록 합니다.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

if os.name == 'nt':
    try:
        myappid = 'owwl.lyricsoverlay.app.1.0'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass

import cv2
from PySide6.QtCore import QSize  # type: ignore
from PySide6.QtWidgets import QApplication, QLabel, QListWidgetItem  # type: ignore

from core.hotkey_manager import HotkeyManager
from core.ocr_engine import OCR_HELP, OCR_KOREAN, OCR_STATUS, ocr_available, windows_native_ocr_split
from core.stats_manager import load_stats, make_session_stats, parse_song_info, save_stats
from core.window_capture import WindowStyleGuard, capture_covered_window, find_melon_window, is_melon_minimized
from gui.main_window import MainWindow
from lyrics.matcher import LyricMatcher
from core.app_config import AppConfig
from core.single_instance import SingleInstance
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

# 전역 단축키(keyboard 스레드)에서 메인 스레드로 넘길 작업
_pending_actions: "queue.SimpleQueue" = queue.SimpleQueue()


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
    if _window.overlay.editing:
        _window.finish_overlay_edit()  # 위치 조정 중 F9 → 조정을 끝내고 원래 모드로
        return
    cfg.set_ghost_mode(not cfg.ghost_mode)
    _window.sync_controls()  # 대시보드·설정 화면 스위치도 함께 맞춤
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
    app.setQuitOnLastWindowClosed(False)  # 창을 트레이로 숨겨도 계속 실행

    # 이미 실행 중이면 그 창을 앞으로 불러오고 끝냅니다.
    instance = SingleInstance()
    if not instance.acquire():
        print("[ℹ️] 이미 실행 중입니다. 기존 창을 엽니다.")
        return
    
    _app_config = AppConfig()

    # 지난번 강제 종료로 투명하게 남은 멜론 창이 있으면 가장 먼저 복구합니다.
    # (이후 단계에서 무엇이 실패해도 멜론 창은 원래대로 돌아오게)
    style_guard = WindowStyleGuard(_app_config.data_dir)
    recovered = style_guard.recover_from_file()

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
    window.quit_requested.connect(_on_quit)
    instance.activate_requested.connect(window.show_from_tray)

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
    hotkey_mgr = HotkeyManager(
        on_ghost_toggle=lambda: _pending_actions.put(_on_toggle_mode),
        on_quit=lambda: _pending_actions.put(_on_quit),
    )

    def refresh_hotkeys() -> None:
        hotkey_mgr.refresh(
            config_manager.hotkey_ghost,
            config_manager.hotkey_quit,
            hotkey_next=config_manager.hotkey_next,
            hotkey_prev=config_manager.hotkey_prev,
            hotkey_pause=config_manager.hotkey_pause,
            log_fn=add_log,
        )

    window.setting_page.hotkeys_changed.connect(refresh_hotkeys)
    refresh_hotkeys()

    # 재생 버튼 (대시보드 / 오버레이)
    media_labels = {"prev": "이전 곡", "play_pause": "재생/일시정지", "next": "다음 곡"}
    def on_media_action(key: str) -> None:
        add_log(f"미디어 제어: {media_labels.get(key, key)}")
    window.dashboard_page.media_controls.action_triggered.connect(on_media_action)
    overlay.media_controls.action_triggered.connect(on_media_action)
    
    # 대시보드 통계 초기 업데이트
    window.dashboard_page.update_stats(session_stats, persistent_stats.get("play_history", []))

    print("=" * 50)
    print("🎤 가사 대시보드 및 오버레이 실행 중")
    print("=" * 50)
    add_log("프로그램 시작")


    # 데이터 경로가 바뀌면 통계·설정·창 복구 기록을 모두 새 경로로 옮깁니다.
    def on_data_dir_changed(new_dir: str) -> None:
        save_stats(persistent_stats, new_dir)
        add_log(f"데이터 경로 변경: {new_dir}")

    _app_config.add_listener(config_manager.set_data_dir)
    _app_config.add_listener(style_guard.set_data_dir)
    _app_config.add_listener(on_data_dir_changed)
    if recovered:
        add_log(f"이전 실행에서 남은 창 상태 {recovered}개 복구")

    applied_hwnd = None       # 고스트 모드 상태를 마지막으로 맞춘 멜론 창
    applied_mode = None
    overlay_mode = None
    last_song_title = ""
    last_lyric_text = ""
    last_save_time = time.monotonic()
    style_retry_at = 0.0
    last_text_seen = time.monotonic()
    melon_missing_since: float | None = None

    # 지금 가사 인식이 왜 되거나 안 되는지 대시보드에 보여 줍니다 (바뀔 때만 갱신).
    last_status: tuple = ()

    def set_status(level: str, title: str, detail: str = "") -> None:
        nonlocal last_status
        if (level, title, detail) == last_status:
            return
        last_status = (level, title, detail)
        window.dashboard_page.set_status(level, title, detail)
        if level != "ok":
            add_log(title)

    current_song_info = None
    current_song_start_time = 0.0
    current_song_lines = 0

    try:
        while is_running:
            app.processEvents()

            # 단축키 콜백은 keyboard 스레드에서 들어오므로, 실제 처리는 여기(메인 스레드)에서 합니다.
            while True:
                try:
                    action = _pending_actions.get_nowait()
                except queue.Empty:
                    break
                action()
            if not is_running:
                break

            is_ghost_mode = config_manager.ghost_mode
            if is_ghost_mode != overlay_mode:
                overlay.set_ghost_mode(is_ghost_mode)
                overlay_mode = is_ghost_mode
            # 멜론 창은 '고스트 모드 + 멜론 창 숨기기'일 때만 투명하게 만듭니다.
            hide_melon = is_ghost_mode and config_manager.hide_melon_window

            # 멜론 프로세스의 창만 대상으로 삼습니다 (다른 프로그램 창을 건드리지 않도록).
            target_win = find_melon_window()
            now = time.monotonic()

            if target_win is None and applied_hwnd is not None and not hide_melon:
                # 멜론이 최소화되거나 숨겨진 상태에서 일반 모드로 바꾼 경우
                if style_guard.restore(applied_hwnd):
                    applied_hwnd, applied_mode = None, None

            if target_win is None:
                # 멜론이 사라지면 이전 가사가 계속 떠 있지 않도록 잠시 뒤 지웁니다.
                if melon_missing_since is None:
                    melon_missing_since = now
                    if is_melon_minimized():
                        set_status("warn", "멜론 창이 최소화돼 있어요",
                                   "최소화하면 가사를 읽을 수 없어요. 다른 창 뒤에 두거나 고스트 모드로 숨겨 주세요.")
                    else:
                        set_status("warn", "멜론을 찾고 있어요",
                                   "멜론 PC 플레이어를 실행하고 가사가 보이게 띄워 주세요.")
                elif now - melon_missing_since > 3 and last_lyric_text != "":
                    overlay.update_lyrics("", "")
                    window.dashboard_page.curr_lyric.setText("")
                    last_lyric_text = ""
            else:
                melon_missing_since = None

            if target_win:
                hwnd = target_win.hwnd

                # 대상 창이나 모드가 바뀌었으면 창 스타일 적용 (실패하면 5초 뒤 재시도)
                if (hwnd != applied_hwnd or hide_melon != applied_mode) and now >= style_retry_at:
                    ok = True
                    if applied_hwnd is not None and hwnd != applied_hwnd:
                        ok = style_guard.restore(applied_hwnd)
                    ok = style_guard.set_ghost(hwnd, hide_melon) and ok
                    if ok:
                        applied_hwnd, applied_mode = hwnd, hide_melon
                        add_log(f"멜론 창: {'숨김' if hide_melon else '표시'}")
                    else:
                        style_retry_at = now + 5.0
                        add_log("창 스타일 변경 실패 (5초 뒤 재시도)")

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

                        # 오버레이에 곡 정보 업데이트
                        overlay.update_song_info(title, artist)
                        window.dashboard_page.set_now_playing(title, artist)

                        item = QListWidgetItem(f"{current_song_title} ({timestamp_short})")
                        item.setSizeHint(QSize(0, 60))
                        window.music_page.music_list.insertItem(0, item)

                        persistent_stats["play_history"].insert(0, current_song_info)
                        add_log(f"새로운 곡 감지: {current_song_title}")
                        save_stats(persistent_stats, _app_config.data_dir)

                # 캡처 및 OCR
                full_img = capture_covered_window(hwnd)
                roi = None
                if not ocr_available():
                    set_status("error", "OCR을 사용할 수 없어요", f"{OCR_STATUS}. {OCR_HELP}")
                elif full_img is None:
                    set_status("warn", "멜론 창을 캡처하지 못했어요", "잠시 후 다시 시도합니다.")
                else:
                    rx, ry, rw, rh = config_manager.roi
                    img_h, img_w = full_img.shape[:2]
                    # 창 밖으로 나간 부분은 잘라내고, 절반 이상 벗어나면 영역이 어긋난 것으로 봅니다.
                    x0, y0 = max(rx, 0), max(ry, 0)
                    x1, y1 = min(rx + rw, img_w), min(ry + rh, img_h)
                    if (x1 - x0) * (y1 - y0) < rw * rh * 0.5:
                        set_status(
                            "error", "가사 인식 영역이 멜론 창을 벗어났어요",
                            "설정 → 동작 → 가사 인식 영역에서 영역을 다시 지정하세요.",
                        )
                    else:
                        roi = full_img[y0:y1, x0:x1]
                if roi is not None:
                    scaled = cv2.resize(roi, None, fx=5, fy=5, interpolation=cv2.INTER_LANCZOS4)

                    lines = await windows_native_ocr_split(scaled)
                    if lines:
                        last_text_seen = now
                        set_status("ok", "가사를 인식하고 있어요", "" if OCR_KOREAN else OCR_STATUS)
                    elif now - last_text_seen > 8:
                        set_status(
                            "warn", "가사 영역에서 글자를 찾지 못했어요",
                            "간주 중이거나 가사가 없는 곡일 수 있어요. 계속 이러면 설정에서 "
                            "가사 인식 영역을 다시 지정해 보세요.",
                        )

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

                    QApplication.processEvents()

            # 1분마다 자동 저장 (멜론 창이 없어도)
            if now - last_save_time >= 60:
                save_stats(persistent_stats, _app_config.data_dir)
                last_save_time = now

            await asyncio.sleep(0.05)

    finally:
        hotkey_mgr.unhook_all()
        if window.tray is not None:
            window.tray.hide()
        config_manager.save_now()
        print("\n[🧹] 멜론 창 상태 원복 중...")
        style_guard.restore_all()
        if _app_config:
            save_stats(persistent_stats, _app_config.data_dir)
        matcher.searcher.shutdown()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    asyncio.run(main())
