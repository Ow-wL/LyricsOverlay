import sys
import cv2
import numpy as np
import pygetwindow as gw # type: ignore
import asyncio
import win32gui, win32ui, win32con
import time
import keyboard # type: ignore
import ctypes
from PySide6.QtWidgets import QApplication, QListWidgetItem, QLabel # type: ignore
from PySide6.QtCore import QSize
import threading

# 윈도우 SDK 및 모듈 임포트
from winsdk.windows.media.ocr import OcrEngine # type: ignore
from winsdk.windows.graphics.imaging import BitmapDecoder # type: ignore
from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter # type: ignore

# 우리가 만든 모듈들
from lyrics_overlay import LyricsOverlay, OverlayConfigManager
from lyrics_matcher import LyricMatcher
from gui.main_window import MainWindow
import json
import os

# --- 설정 및 경로 ---
STATS_FILE_PATH = "lyrics_stats.json"

# 전역 변수 설정
log_history = []
is_running = True # 프로그램 실행 상태 플래그 추가
engine = OcrEngine.try_create_from_user_profile_languages()
_window = None # GUI 연동을 위한 전역 변수

def load_stats():
    """파일에서 통계 데이터를 로드합니다."""
    default_stats = {
        "songs": [], # [(title, date), ...]
        "total_lines": 0,
        "total_play_time_sec": 0,
        "theme": "light"
    }
    if os.path.exists(STATS_FILE_PATH):
        try:
            with open(STATS_FILE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 누락된 필드 보정
                for key, val in default_stats.items():
                    if key not in data:
                        data[key] = val
                return data
        except Exception as e:
            print(f"[⚠️] 통계 로드 실패: {e}")
    return default_stats

def save_stats(stats):
    """통계 데이터를 파일에 저장합니다."""
    try:
        with open(STATS_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[⚠️] 통계 저장 실패: {e}")

# 세션 초기 데이터 로드
persistent_stats = load_stats()
session_stats = {
    "unique_songs": {s[0] for s in persistent_stats.get("songs", [])},
    "lines": persistent_stats.get("total_lines", 0),
    "base_play_time": persistent_stats.get("total_play_time_sec", 0),
    "start_time": time.time()
}

def add_log(message):
    """최근 로그 5개만 유지하며 GUI에 연동하는 함수"""
    global log_history, _window
    timestamp = time.strftime("%H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    log_history.append(log_msg)
    if len(log_history) > 5:
        log_history.pop(0)
    
    # GUI 리스트 위젯에 로그 추가
    if _window:
        _window.dashboard_page.log_list.addItem(log_msg)
        if _window.dashboard_page.log_list.count() > 50:
            _window.dashboard_page.log_list.takeItem(0)
        _window.dashboard_page.log_list.scrollToBottom()

def exit_program():
    """프로그램 종료 플래그를 설정하고 루프를 탈출합니다."""
    global is_running
    is_running = False
    print("\n[🔔] 프로그램 종료 요청됨.")
    add_log("프로그램 종료 요청됨")
    # Qt 이벤트 루프 종료를 통해 즉각적인 피드백 제공
    QApplication.quit()

def refresh_hotkeys():
    global _window
    try:
        # 기존 등록된 모든 단축키 해제
        try:
            keyboard.unhook_all()
        except:
            pass
        
        if not _window or not _window.config_manager:
            return

        hk_ghost = _window.config_manager.hotkey_ghost
        hk_quit = _window.config_manager.hotkey_quit
        
        # 유효한 단축키 문자열인지 확인 후 등록
        if hk_ghost and hk_ghost.strip():
            try:
                # hotkey 가 올바른 형식인지 검증 겸 등록
                keyboard.add_hotkey(hk_ghost.strip(), toggle_mode)
                print(f"[⌨️] 고스트 모드 단축키 등록: {hk_ghost}")
            except Exception as e:
                print(f"[⚠️] 고스트 단축키 등록 실패 ({hk_ghost}): {e}")
                add_log(f"고스트 단축키 등록 실패: {hk_ghost}")
        
        if hk_quit and hk_quit.strip():
            try:
                keyboard.add_hotkey(hk_quit.strip(), exit_program)
                print(f"[⌨️] 프로그램 종료 단축키 등록: {hk_quit}")
            except Exception as e:
                print(f"[⚠️] 종료 단축키 등록 실패 ({hk_quit}): {e}")
                add_log(f"종료 단축키 등록 실패: {hk_quit}")
        
        add_log(f"단축키 갱신 완료: {hk_ghost} / {hk_quit}")
    except Exception as e:
        print(f"[⚠️] 단축키 시스템 오류: {e}")
        add_log(f"단축키 시스템 오류")

def toggle_mode():
    config_manager = _window.config_manager
    config_manager.set_ghost_mode(not config_manager.ghost_mode)
    mode_name = "반투명 + 클릭통과" if config_manager.ghost_mode else "불투명 + 클릭가능"
    print(f"\n[🔔] 모드 전환: {mode_name}")
    add_log(f"모드 전환: {mode_name}")

async def windows_native_ocr_split(image):
    try:
        is_success, buffer = cv2.imencode(".bmp", image)
        if not is_success: return []
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(buffer.tobytes())
        await writer.store_async()
        await writer.flush_async()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        software_bitmap = await decoder.get_software_bitmap_async()
        result = await engine.recognize_async(software_bitmap)
        return [line.text for line in result.lines]
    except:
        return []

def apply_transparency(hwnd, ghost):
    try:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        if ghost:
            new_style = style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 1, win32con.LWA_ALPHA)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
        else:
            new_style = (style | win32con.WS_EX_LAYERED) & ~win32con.WS_EX_TRANSPARENT
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)
            win32gui.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_NOZORDER)
    except:
        pass

def capture_covered_window(hwnd):
    try:
        left, top, right, bot = win32gui.GetWindowRect(hwnd)
        w, h = max(right - left, 1), max(bot - top, 1)
        hwndDC = win32gui.GetWindowDC(hwnd)
        mfcDC = win32ui.CreateDCFromHandle(hwndDC)
        saveDC = mfcDC.CreateCompatibleDC()
        saveBitMap = win32ui.CreateBitmap()
        saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
        saveDC.SelectObject(saveBitMap)
        ctypes.windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)
        bmpinfo = saveBitMap.GetInfo()
        bmpstr = saveBitMap.GetBitmapBits(True)
        img = np.frombuffer(bmpstr, dtype='uint8')
        img.shape = (bmpinfo['bmHeight'], bmpinfo['bmWidth'], 4)
        win32gui.DeleteObject(saveBitMap.GetHandle())
        saveDC.DeleteDC()
        mfcDC.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwndDC)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    except:
        return None

async def main():
    # --- 1. 가사 및 UI 엔진 초기화 ---
    app = QApplication(sys.argv)
    
    # 메인 윈도우 생성
    initial_theme = persistent_stats.get("theme", "light")
    window = MainWindow(initial_theme=initial_theme)
    global _window
    _window = window
    
    # 테마 변경 시 자동 저장
    def on_theme_changed(theme_name):
        persistent_stats["theme"] = theme_name
        save_stats(persistent_stats)
        add_log(f"테마 변경: {theme_name}")

    window.theme_changed.connect(on_theme_changed)
    
    # 히스토리 데이터로 GUI 목록 초기화
    for song_title, date in persistent_stats.get("songs", []):
        item = QListWidgetItem(f"{song_title} ({date})")
        item.setSizeHint(QSize(0, 60))
        window.music_page.music_list.addItem(item)
    
    window.show()
    
    overlay = window.overlay
    config_manager = window.config_manager
    matcher = LyricMatcher() 

    last_applied_mode = None 
    
    # 설정 변경 시 오버레이 업데이트
    window.setting_page.settings_changed.connect(window.update_overlay)
    # 단축키 변경 시에만 단축키 갱신
    window.setting_page.hotkeys_changed.connect(refresh_hotkeys)
    refresh_hotkeys()

    print("=" * 50)
    print("🎤 가사 대시보드 및 오버레이 실행 중")
    print("=" * 50)
    add_log("프로그램 시작")
    
    exclude = ["Visual Studio Code", "Whale", "Gemini", "OBS", "Overlay", "Discord", "파일 탐색기", "메모장", "PowerPoint", "한글", "Hancom", "Hwp", "Edge"]
    
    last_hwnd = None
    last_song_title = ""
    last_lyric_text = ""
    save_timer = 0
    
    try:
        while is_running: # is_running 플래그를 사용하여 루프 제어
            app.processEvents()

            target_win = None
            all_windows = gw.getAllWindows()
            
            # 1순위: 'Melon'이 제목에 명시적으로 포함된 창
            for w in all_windows:
                if "Melon" in w.title and not any(ex in w.title for ex in exclude):
                    if w.width > 200 and not w.isMinimized:
                        target_win = w
                        break
            
            # 2순위: 'Melon'은 없지만 ' - ' 형식을 가진 창 (기존 호환성 유지)
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
                    overlay.set_ghost_mode(is_ghost_mode) # 오버레이 모드도 함께 변경
                    last_applied_mode = is_ghost_mode
                    add_log(f"창 스타일 변경 완료: {'고스트' if is_ghost_mode else '일반'}")

                # 가사 목록 업데이트 (곡이 바뀌었을 때)
                current_song_title = target_win.title.replace(" - Melon", "").strip()
                if current_song_title != last_song_title:
                    last_song_title = current_song_title
                    if current_song_title and current_song_title not in session_stats["unique_songs"]:
                        session_stats["unique_songs"].add(current_song_title)
                        timestamp = time.strftime("%y.%m.%d")
                        
                        # 리스트 위젯에 추가
                        item = QListWidgetItem(f"{current_song_title} ({timestamp})")
                        item.setSizeHint(QSize(0, 60))
                        window.music_page.music_list.insertItem(0, item)
                        
                        # 영구 저장용 리스트에 추가
                        persistent_stats["songs"].insert(0, (current_song_title, timestamp))
                        add_log(f"새로운 곡 감지: {current_song_title}")
                        save_stats(persistent_stats) # 곡 변경 시 즉시 저장

                full_img = capture_covered_window(hwnd)
                if full_img is not None:
                    roi = full_img[216:216+46, 28:28+251]
                    scaled = cv2.resize(roi, None, fx=5, fy=5, interpolation=cv2.INTER_LANCZOS4)
                    
                    lines = await windows_native_ocr_split(scaled)
                    
                    fixed_lines = []
                    for line in lines:
                        fixed_text, status = matcher.get_best_match(line, target_win.title)
                        if status:
                            add_log(status)
                        fixed_lines.append(fixed_text)

                    # --- 터미널 출력 영역 ---
                    print("\033[H\033[J") 
                    mode_status = "👻 게임 모드" if is_ghost_mode else "🖱️  조작 모드"
                    print(f"상태: {mode_status} | 대상: {target_win.title}")
                    print("-" * 40)
                    
                    curr = fixed_lines[0] if len(fixed_lines) > 0 else "..."
                    nxt = fixed_lines[1] if len(fixed_lines) > 1 else ""
                    
                    # 가사 라인 수 업데이트 (가사가 실제로 바뀌었을 때만)
                    if curr != "..." and curr != last_lyric_text:
                        session_stats["lines"] += 1
                        last_lyric_text = curr
                        persistent_stats["total_lines"] = session_stats["lines"]

                    print(f"🔥 현재: {curr}")
                    print(f"💤 다음: {nxt}")
                    print("-" * 40)
                    print("[ 시스템 로그 ]")
                    for log in log_history:
                        print(f" > {log}")

                    # --- 오버레이 및 대시보드 업데이트 영역 ---
                    overlay.update_lyrics(curr, nxt)
                    window.dashboard_page.curr_lyric.setText(curr)
                    
                    # 통계 데이터 업데이트 및 저장
                    session_duration = time.time() - session_stats["start_time"]
                    total_play_time_sec = session_stats["base_play_time"] + session_duration
                    persistent_stats["total_play_time_sec"] = int(total_play_time_sec)
                    
                    window.dashboard_page.stat1.findChild(QLabel, "StatValue").setText(f"{len(session_stats['unique_songs'])}곡")
                    window.dashboard_page.stat2.findChild(QLabel, "StatValue").setText(f"{int(total_play_time_sec // 60)}분")
                    window.dashboard_page.stat3.findChild(QLabel, "StatValue").setText(f"{session_stats['lines']}줄")
                    
                    # 1분마다 자동 저장
                    save_timer += 0.05
                    if save_timer >= 60:
                        save_stats(persistent_stats)
                        save_timer = 0

                    QApplication.processEvents()

            await asyncio.sleep(0.05)
    finally:
        save_stats(persistent_stats) # 종료 시 최종 저장
        if last_hwnd:
            print("\n[🧹] 멜론 창 상태 원복 중...")
            apply_transparency(last_hwnd, False)
        cv2.destroyAllWindows()

if __name__ == "__main__":
    asyncio.run(main())
