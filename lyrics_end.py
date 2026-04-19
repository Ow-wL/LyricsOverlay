import cv2
import numpy as np
import pygetwindow as gw
import win32gui
import win32ui
import win32con
import ctypes
import asyncio
import time
import keyboard
from winsdk.windows.media.ocr import OcrEngine
from winsdk.windows.graphics.imaging import SoftwareBitmap, BitmapDecoder
from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
from lyric_matcher import LyricMatcher


# 1. 전역 변수
engine = OcrEngine.try_create_from_user_profile_languages()
is_ghost_mode = False 
log_history = []

def add_log(message):
    """최근 로그 5개만 유지하는 함수"""
    global log_history
    timestamp = time.strftime("%H:%M:%S")
    log_history.append(f"[{timestamp}] {message}")
    if len(log_history) > 5:  # 너무 많으면 지움
        log_history.pop(0)

def toggle_mode():
    global is_ghost_mode
    is_ghost_mode = not is_ghost_mode
    mode_name = "반투명 + 클릭통과" if is_ghost_mode else "불투명 + 클릭가능"
    print(f"\n[🔔] 모드 전환: {mode_name}")

keyboard.add_hotkey('F10', toggle_mode)

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
            # 게임 모드: 클릭 통과 + 항상 위 강제
            new_style = style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 1, win32con.LWA_ALPHA)
            # 고스트 모드일 때는 확실하게 위로 올립니다.
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
        else:
            # 조작 모드: 클릭 가능하게 복구
            new_style = (style | win32con.WS_EX_LAYERED) & ~win32con.WS_EX_TRANSPARENT
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)
            
            # [핵심] 여기서 HWND_NOTOPMOST를 쓰지 않고, 멜론의 자체 설정을 존중하도록
            # 창의 스타일만 바꾸고 위치(Z-order)는 건드리지 않습니다.
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
    # 1. 새 보정 엔진 초기화 (LyricMatcher)
    matcher = LyricMatcher() 
    last_applied_mode = None # 이전에 적용된 모드를 저장
    global is_ghost_mode
    
    print("=" * 50)
    print("🎤 OBS 호환 가사 대시보드 실행 중 (보정 엔진 활성화)")
    print("⌨️  단축키: [F10] 모드 전환 | [Q] 종료")
    print("=" * 50)
    
    # 검색 대상 제외 리스트
    exclude = ["Visual Studio Code", "Whale", "Gemini", "OBS", "Overlay", "Discord", "파일 탐색기", "메모장"]
    
    while True:
        target_win = None
        for w in gw.getAllWindows():
            # 멜론 창 찾기 로직
            if ("Melon" in w.title or " - " in w.title) and not any(ex in w.title for ex in exclude):
                if w.width > 200:
                    target_win = w
                    break
        
        if target_win:
            hwnd = target_win._hWnd

            # [수정] 모드가 바뀌었을 때만 스타일을 적용합니다.
            if is_ghost_mode != last_applied_mode:
                apply_transparency(hwnd, is_ghost_mode)
                last_applied_mode = is_ghost_mode
                add_log(f"창 스타일 변경 완료: {'고스트' if is_ghost_mode else '일반'}")

            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
            
            # 투명도 및 클릭 통과 설정 적용
            apply_transparency(hwnd, is_ghost_mode)
            
            full_img = capture_covered_window(hwnd)
            if full_img is not None:
                # 가사 영역 정밀 추출 및 3배 확대
                roi = full_img[216:216+46, 28:28+251]
                scaled = cv2.resize(roi, None, fx=5, fy=5, interpolation=cv2.INTER_LANCZOS4)
                
                # 윈도우 네이티브 OCR 실행
                lines = await windows_native_ocr_split(scaled)
                
                # 가사 보정 및 로그 수집
                fixed_lines = []
                for line in lines:
                    fixed_text, status = matcher.get_best_match(line, target_win.title)
                    if status: # 새로운 로그가 발생했다면 history에 추가
                        add_log(status)
                    fixed_lines.append(fixed_text)

               # 1. 화면 지우기
                print("\033[H\033[J") 
                
                # 2. 상태 및 가사 출력
                mode_status = "👻 게임 모드" if is_ghost_mode else "🖱️  조작 모드"
                print(f"상태: {mode_status} | 대상: {target_win.title}")
                print("-" * 40)
                
                curr = fixed_lines[0] if len(fixed_lines) > 0 else "..."
                nxt = fixed_lines[1] if len(fixed_lines) > 1 else "..."
                
                print(f"🔥 현재: {curr}")
                print(f"💤 다음: {nxt}")
                print("-" * 40)

                # 3. [핵심] 하단 로그 출력 영역
                print("[ 시스템 로그 ]")
                for log in log_history:
                    print(f" > {log}")

                # 디버그용 프리뷰 창
                cv2.imshow("OCR Preview (5x)", scaled)
        
        # 'q' 키를 누르면 루프 종료
        if cv2.waitKey(200) & 0xFF == ord('q'): 
            break
            
    cv2.destroyAllWindows()

if __name__ == "__main__":
    asyncio.run(main())