import cv2
import numpy as np
import pygetwindow as gw
import win32gui
import win32con
import asyncio
import time
from mss import mss
from winsdk.windows.media.ocr import OcrEngine
from winsdk.windows.graphics.imaging import SoftwareBitmap, BitmapDecoder
from winsdk.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

# 1. OCR 엔진 초기화
engine = OcrEngine.try_create_from_user_profile_languages()

async def windows_native_ocr_split(image):
    """이미지를 읽어 줄 단위(Lines)로 리스트를 반환"""
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
    
    # 인식된 라인들을 리스트에 담아 반환
    extracted_lines = [line.text for line in result.lines]
    return extracted_lines

def capture_raw_area():
    exclude = ["Visual Studio Code", "Whale", "Gemini"]
    target_win = None
    for w in gw.getAllWindows():
        if ("Melon" in w.title or " - " in w.title) and not any(ex in w.title for ex in exclude):
            if w.width > 200:
                target_win = w
                break

    if not target_win: return None, "멜론 창 없음"

    hwnd = target_win._hWnd
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_SHOWNOACTIVATE)
        time.sleep(0.3)

    with mss() as sct:
        # 사용자가 지정한 정밀 좌표 (2줄이 다 포함된 영역)
        monitor = {
            'top': target_win.top + 216, 
            'left': target_win.left + 28, 
            'width': 251, 
            'height': 46
        }
        sct_img = sct.grab(monitor)
        img = np.array(sct_img)
        # 전처리 없이 원본 BGR 이미지 그대로 사용 (알파 채널만 제거)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR), target_win.title

async def main():
    print("🎬 전처리 없는 원본 OCR 테스트 시작...")
    
    while True:
        raw_img, title = capture_raw_area()
        
        if raw_img is not None:
            lines = await windows_native_ocr_split(raw_img)
            
            # 터미널 화면 정리
            print("\033[H\033[J") 
            print(f"🎵 곡 제목: {title}")
            print("-" * 30)

            # 라인별로 나누어 출력
            current_lyric = lines[0] if len(lines) > 0 else "..."
            next_lyric = lines[1] if len(lines) > 1 else "..."

            print(f"🔥 현재 가사: {current_lyric}")
            print(f"💤 다음 가사: {next_lyric}")
            print("-" * 30)
            
            # 원본 확인용 창
            cv2.imshow("Raw Capture View", raw_img)
        
        if cv2.waitKey(300) & 0xFF == ord('q'): 
            break
            
    cv2.destroyAllWindows()

if __name__ == "__main__":
    asyncio.run(main())