"""
text_processor.py
OpenCV 기반 텍스트 추출 + 배경 제거 + 색상 치환 프로세서.

파이프라인:
  numpy BGRA
     │
     ▼
  그레이스케일 변환
     │
     ▼
  적응형 임계값(Adaptive Threshold) → 텍스트 마스크 생성
     │
     ├─ 형태학 연산(dilate) → 마스크 정교화
     │
     ▼
  마스크 기반 BGRA 알파 합성
     ├─ 텍스트 픽셀    → 사용자 지정 텍스트 색상 + alpha=255
     └─ 비텍스트 픽셀  → 배경 색상 + 사용자 지정 배경 투명도
     │
     ▼
  numpy RGBA → QImage

설정 가능 파라미터 (ProcessorSettings):
  - text_color       : 텍스트 색상 (R,G,B)
  - text_alpha       : 텍스트 불투명도 0–255
  - bg_color         : 배경 색상 (R,G,B)
  - bg_alpha         : 배경 불투명도 0–255
  - threshold_mode   : 'adaptive' | 'otsu'
  - threshold_offset : 적응형 임계값 오프셋 (-50 ~ +50)
  - morph_size       : 형태학 커널 크기 1–7 (글자 두께 보정)
  - invert           : True이면 밝은 배경에 어두운 글씨 (기본 False = 어두운 배경에 밝은 글씨)
"""

from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np
import cv2
from PyQt6.QtGui import QImage


@dataclass
class ProcessorSettings:
    # 텍스트
    text_color:  tuple[int, int, int] = (255, 255, 255)  # RGB
    text_alpha:  int = 255

    # 배경
    bg_color:    tuple[int, int, int] = (0, 0, 0)        # RGB
    bg_alpha:    int = 80                                 # 반투명 배경

    # 임계값
    threshold_mode:   str = "adaptive"   # 'adaptive' | 'otsu'
    threshold_offset: int = -10          # 적응형 offset (음수 = 더 엄격)
    block_size:       int = 15           # 적응형 블록 크기 (홀수)

    # 후처리
    morph_size:  int = 1     # 팽창 커널 크기 (0 = 사용 안 함)
    invert:      bool = False # True: 밝은 배경/어두운 글씨


class TextProcessor:
    """
    캡처된 BGRA numpy 배열에서 텍스트만 추출해 RGBA QImage로 반환한다.
    인스턴스를 유지하면서 settings 를 교체하면 실시간으로 적용된다.
    """

    def __init__(self, settings: ProcessorSettings | None = None) -> None:
        self.settings = settings or ProcessorSettings()

    # ── 퍼블릭 ──────────────────────────────────────────────────────────
    def process(self, bgra: np.ndarray) -> QImage:
        """
        BGRA uint8 배열 → 텍스트만 남긴 RGBA QImage 반환.
        배경은 bg_alpha 로 반투명하게 처리.
        """
        s = self.settings
        h, w = bgra.shape[:2]

        # 1) 그레이스케일
        gray = cv2.cvtColor(bgra, cv2.COLOR_BGRA2GRAY)

        # 2) 텍스트 마스크 생성
        mask = self._build_mask(gray, s)

        # 3) RGBA 출력 버퍼
        out = np.zeros((h, w, 4), dtype=np.uint8)

        # 4) 배경 픽셀 채우기
        bg_r, bg_g, bg_b = s.bg_color
        out[:, :, 0] = bg_r
        out[:, :, 1] = bg_g
        out[:, :, 2] = bg_b
        out[:, :, 3] = s.bg_alpha

        # 5) 텍스트 픽셀 덮어쓰기
        tx_r, tx_g, tx_b = s.text_color
        out[mask > 0, 0] = tx_r
        out[mask > 0, 1] = tx_g
        out[mask > 0, 2] = tx_b
        out[mask > 0, 3] = s.text_alpha

        # 6) QImage 생성 (copy로 numpy 버퍼 수명에서 독립)
        img = QImage(out.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        return img.copy()

    # ── 내부 ────────────────────────────────────────────────────────────
    @staticmethod
    def _build_mask(gray: np.ndarray, s: ProcessorSettings) -> np.ndarray:
        """
        그레이스케일 이미지에서 텍스트 픽셀 마스크(255=텍스트, 0=배경)를 반환.
        """
        # 노이즈 제거 (경량 블러)
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        if s.threshold_mode == "otsu":
            _, mask = cv2.threshold(blurred, 0, 255,
                                    cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        else:
            # 적응형: 블록 크기는 반드시 홀수 & >= 3
            block = max(3, s.block_size | 1)   # 비트OR 1 → 홀수 보장
            c_val = -s.threshold_offset        # OpenCV C 파라미터는 부호 반대
            mask = cv2.adaptiveThreshold(
                blurred, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                block, c_val
            )

        # invert: 밝은 배경에 어두운 글씨
        if s.invert:
            mask = cv2.bitwise_not(mask)

        # 형태학: 팽창으로 글자 경계 보강
        if s.morph_size > 0:
            kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (s.morph_size * 2 + 1, s.morph_size * 2 + 1)
            )
            mask = cv2.dilate(mask, kernel, iterations=1)

        return mask
