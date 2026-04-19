import cv2
import numpy as np
import pygetwindow as gw
from mss import mss
import time

def select_melon_roi():
    print("🔍 멜론 창을 찾는 중...")
    exclude = ["Visual Studio Code", "Whale", "Chrome", "Edge", "Gemini", "ocr_test"]
    target_win = None
    
    for w in gw.getAllWindows():
        if w.title and ("Melon" in w.title or " - " in w.title):
            if not any(ex in w.title for ex in exclude):
                target_win = w
                break

    if not target_win:
        print("❌ 멜론 창을 찾을 수 없습니다.")
        return

    # 창을 활성화하여 맨 앞으로 가져옴
    try:
        target_win.activate()
        time.sleep(0.5)
    except:
        pass

    with mss() as sct:
        # 멜론 창 위치 및 크기 정보
        monitor = {
            "top": target_win.top,
            "left": target_win.left,
            "width": target_win.width,
            "height": target_win.height
        }
        
        # 캡처
        sct_img = sct.grab(monitor)
        img = np.array(sct_img)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        
        # 실제 캡처된 이미지의 가로/세로 크기 (픽셀 단위)
        h, w, _ = img.shape

    print(f"\n🎯 찾은 창: {target_win.title}")
    print(f"📏 실제 픽셀 크기: {w}x{h}")
    print("\n💡 [사용법]")
    print("1. 창이 뜨면 가사 부분만 마우스로 드래그하세요.")
    print("2. 선택 후 Enter 또는 Space를 누르세요.")

    # 윈도우 생성 및 크기 고정
    win_name = "Select Lyrics Area"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    # 캡처된 이미지의 실제 픽셀 크기에 맞춰 윈도우 크기 조절
    cv2.resizeWindow(win_name, w, h)
    
    # ROI 선택
    roi = cv2.selectROI(win_name, img, fromCenter=False, showCrosshair=True)
    
    x, y, rw, rh = roi

    if rw > 0 and rh > 0:
        print("\n--- ✅ 좌표 획득 완료! ---")
        print(f"X: {x}")
        print(f"Y: {y}")
        print(f"W: {rw}")
        print(f"H: {rh}")
        print("--------------------------")
        print(f"\n[복사용] monitor = {{'top': target_win.top + {y}, 'left': target_win.left + {x}, 'width': {rw}, 'height': {rh}}}")
    else:
        print("\n❌ 영역이 선택되지 않았습니다.")
    
    cv2.destroyAllWindows()

if __name__ == "__main__":
    select_melon_roi()