"""
capture_engine.py
mss 기반 저지연 화면 캡처 + TextProcessor 실시간 적용.
QThread에서 동작해 GUI가 블로킹되지 않는다.
"""

from __future__ import annotations
import time
import numpy as np
import mss
from PyQt6.QtCore import QThread, pyqtSignal, QRect
from PyQt6.QtGui import QImage

from text_processor import TextProcessor, ProcessorSettings


class CaptureEngine(QThread):
    """
    지정 스크린 영역을 target_fps 로 캡처하고,
    TextProcessor 를 거쳐 QImage 를 frame_ready 시그널로 내보낸다.
    """

    frame_ready    = pyqtSignal(QImage)
    error_occurred = pyqtSignal(str)

    def __init__(
        self,
        region: QRect,
        target_fps: int = 30,
        settings: ProcessorSettings | None = None,
    ) -> None:
        super().__init__()
        self._region    = region
        self._target_fps = target_fps
        self._running   = False
        self._monitor   = self._rect_to_monitor(region)
        self._processor = TextProcessor(settings or ProcessorSettings())

    # ── 공개 API ────────────────────────────────────────────────────────
    def update_region(self, region: QRect) -> None:
        self._region  = region
        self._monitor = self._rect_to_monitor(region)

    def update_settings(self, settings: ProcessorSettings) -> None:
        """실시간 설정 변경 (스레드 안전: 단순 객체 교체)."""
        self._processor.settings = settings

    def stop(self) -> None:
        self._running = False
        self.wait()

    # ── QThread 진입점 ──────────────────────────────────────────────────
    def run(self) -> None:
        self._running = True
        frame_dur = 1.0 / self._target_fps

        with mss.mss() as sct:
            while self._running:
                t0 = time.perf_counter()
                try:
                    qimg = self._capture_and_process(sct)
                    if qimg is not None:
                        self.frame_ready.emit(qimg)
                except Exception as exc:
                    self.error_occurred.emit(str(exc))

                elapsed = time.perf_counter() - t0
                sleep_for = frame_dur - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)

    # ── 내부 ────────────────────────────────────────────────────────────
    def _capture_and_process(self, sct) -> QImage | None:
        raw = sct.grab(self._monitor)
        if raw is None:
            return None

        # mss → numpy BGRA
        bgra: np.ndarray = np.frombuffer(raw.bgra, dtype=np.uint8).reshape(
            raw.height, raw.width, 4
        ).copy()   # writeable copy 필요 (OpenCV 연산)

        # TextProcessor 적용 → RGBA QImage
        return self._processor.process(bgra)

    @staticmethod
    def _rect_to_monitor(rect: QRect) -> dict:
        return {
            "top":    rect.top(),
            "left":   rect.left(),
            "width":  rect.width(),
            "height": rect.height(),
        }
