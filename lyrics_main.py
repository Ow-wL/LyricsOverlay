import sys
import cv2
import numpy as np
import pygetwindow as gw # type: ignore
import asyncio
import win32gui, win32ui, win32con
import time
import keyboard # type: ignore
import ctypes
from PySide6.QtWidgets import QApplication # type: ignore
import threading

# 윈도우 SDK 및 모듈 임포트
from winsdk.windows.media.ocr import OcrEngine # type: ignore
from winsdk.windows.graphics.imaging import BitmapDecoder # type: ignore
from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter # type: ignore

# 우리가 만든 모듈들
from lyrics_overlay import LyricsOverlay
from lyrics_matcher import LyricMatcher

# 전역 변수 설정
log_history = []
is_ghost_mode = True
is_running = True # 프로그램 실행 상태 플래그 추가
engine = OcrEngine.try_create_from_user_profile_languages()

def add_log(message):
    """최근 로그 5개만 유지하는 함수"""
    global log_history
    timestamp = time.strftime("%H:%M:%S")
    log_history.append(f"[{timestamp}] {message}")
    if len(log_history) > 5:
        log_history.pop(0)

def toggle_mode():
    global is_ghost_mode
    is_ghost_mode = not is_ghost_mode
    mode_name = "반투명 + 클릭통과" if is_ghost_mode else "불투명 + 클릭가능"
    # 터미널에 즉시 출력 및 로그 추가
    print(f"\n[🔔] 모드 전환: {mode_name}")
    add_log(f"모드 전환: {mode_name}")

def exit_program():
    """프로그램 종료 플래그를 설정하는 함수"""
    global is_running
    is_running = False
    print("\n[🔔] 프로그램 종료 요청됨.")

keyboard.add_hotkey('F10', toggle_mode)
keyboard.add_hotkey('shift+q', exit_program) # 'shift+q' 키로 프로그램 종료 기능 추가

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
    overlay = LyricsOverlay()
    matcher = LyricMatcher() 

    # overlay.setGeometry(460, 800, 666, 160)
    overlay.show()
    overlay.raise_()
    
    last_applied_mode = None 
    global is_ghost_mode
    
    print("=" * 50)
    print("🎤 가사 대시보드 및 오버레이 실행 중")
    print("⌨️  단축키: [F10] 모드 전환 | [Q] 종료")
    print("=" * 50)
    
    exclude = ["Visual Studio Code", "Whale", "Gemini", "OBS", "Overlay", "Discord", "파일 탐색기", "메모장", "PowerPoint"]
    
    while is_running: # is_running 플래그를 사용하여 루프 제어
        app.processEvents()

        target_win = None
        for w in gw.getAllWindows():
            if ("Melon" in w.title or " - " in w.title) and not any(ex in w.title for ex in exclude):
                if w.width > 200:
                    target_win = w
                    break
        
        if target_win:
            hwnd = target_win._hWnd

            # 모드 변경 시 창 스타일 적용
            if is_ghost_mode != last_applied_mode:
                apply_transparency(hwnd, is_ghost_mode)
                overlay.set_ghost_mode(is_ghost_mode) # 오버레이 모드도 함께 변경
                last_applied_mode = is_ghost_mode
                add_log(f"창 스타일 변경 완료: {'고스트' if is_ghost_mode else '일반'}")

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
                
                print(f"🔥 현재: {curr}")
                print(f"💤 다음: {nxt}")
                print("-" * 40)
                print("[ 시스템 로그 ]")
                for log in log_history:
                    print(f" > {log}")

                # --- 오버레이 업데이트 영역 ---
                overlay.update_lyrics(curr, nxt)
                QApplication.processEvents()

                # 디버그용 프리뷰
                # cv2.imshow("OCR Preview (5x)", scaled)
        
        # cv2.waitKey(1) & 0xFF == ord('q') 대신 keyboard 모듈 사용
        # if cv2.waitKey(1) & 0xFF == ord('q'): 
        #     break

        await asyncio.sleep(0.05)
            
    cv2.destroyAllWindows()

def start_keyboard_listener():
    """키보드 이벤트를 감지하는 리스너를 시작합니다."""
    keyboard.wait() # 이 함수는 블로킹되므로 별도의 스레드에서 실행해야 합니다.

if __name__ == "__main__":
    # 키보드 리스너를 별도의 스레드에서 시작
    keyboard_thread = threading.Thread(target=start_keyboard_listener, daemon=True)
    keyboard_thread.start()
    
    asyncio.run(main())