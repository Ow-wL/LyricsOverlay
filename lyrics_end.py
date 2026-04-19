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
    """OBS 충돌 방지를 위해 스타일 설정을 매번 확인하고 강제 적용"""
    try:
        # 현재 확장 스타일 가져오기
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        
        if ghost:
            # 반투명(LAYERED)과 클릭 통과(TRANSPARENT)를 명시적으로 추가
            new_style = style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
            if style != new_style:
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
            
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 1, win32con.LWA_ALPHA)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0, 
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
        else:
            # 클릭 가능하게 복구하되, 투명도 조절을 위해 LAYERED는 유지하는 것이 안전함
            new_style = (style | win32con.WS_EX_LAYERED) & ~win32con.WS_EX_TRANSPARENT
            if style != new_style:
                win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE, new_style)
            
            # 255(불투명) 적용 전 레이어드 스타일이 확실히 있는지 재확인
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_ALPHA)
            win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0, 
                                  win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
    except Exception as e:
        # 에러가 나도 프로그램이 종료되지 않고 다음 루프로 넘어가게 함
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
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
            
            # 투명도 및 클릭 통과 설정 적용
            apply_transparency(hwnd, is_ghost_mode)
            
            full_img = capture_covered_window(hwnd)
            if full_img is not None:
                # 가사 영역 정밀 추출 및 3배 확대
                roi = full_img[216:216+46, 28:28+251]
                sscaled = cv2.resize(roi, None, fx=5, fy=5, interpolation=cv2.INTER_LANCZOS4)
                
                # 윈도우 네이티브 OCR 실행
                lines = await windows_native_ocr_split(scaled)
                
                # --- [오늘의 핵심: 실시간 가사 보정 로직] ---
                # OCR 결과(lines)와 현재 곡 제목(target_win.title)을 대조하여 정답지로 보정
                fixed_lines = [matcher.get_best_match(line, target_win.title) for line in lines]

                # 터미널 출력 및 화면 청소
                print("\033[H\033[J") 
                mode_status = "👻 게임 모드 (클릭 통과)" if is_ghost_mode else "🖱️  조작 모드 (클릭 가능)"
                print(f"상태: {mode_status}\n대상: {target_win.title}\n" + "-"*30)
                
                # 보정된 가사 출력
                curr = fixed_lines[0] if len(fixed_lines) > 0 else "..."
                nxt = fixed_lines[1] if len(fixed_lines) > 1 else "..."
                
                print(f"🔥 현재(보정됨): {curr}")
                print(f"💤 다음(보정됨): {nxt}\n" + "-"*30)

                # 디버그용 프리뷰 창
                cv2.imshow("OCR Preview (5x)", scaled)
        
        # 'q' 키를 누르면 루프 종료
        if cv2.waitKey(200) & 0xFF == ord('q'): 
            break
            
    cv2.destroyAllWindows()

if __name__ == "__main__":
    asyncio.run(main())