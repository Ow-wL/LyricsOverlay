"""
capture_engine.py
Low-latency screen-region capture using `mss`.
Runs on a dedicated QThread so the GUI stays responsive.

Future extension point: swap _capture_frame() body for a CUDA/DXGI path.
"""

from __future__ import annotations
import time
import numpy as np
import mss
import mss.tools
from PyQt6.QtCore import QThread, pyqtSignal, QRect
from PyQt6.QtGui import QImage


class CaptureEngine(QThread):
    """
    Worker thread that captures a fixed screen region at ~target_fps.

    Signals
    -------
    frame_ready(QImage)
        Emitted every time a new frame is captured.
    error_occurred(str)
        Emitted when capture fails.
    """

    frame_ready = pyqtSignal(QImage)
    error_occurred = pyqtSignal(str)

    def __init__(self, region: QRect, target_fps: int = 30) -> None:
        super().__init__()
        self._region = region
        self._target_fps = target_fps
        self._running = False

        # mss monitor dict  (top-left origin, width/height)
        self._monitor: dict = self._rect_to_monitor(region)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def update_region(self, region: QRect) -> None:
        """Thread-safe region update."""
        self._region = region
        self._monitor = self._rect_to_monitor(region)

    def stop(self) -> None:
        self._running = False
        self.wait()

    # ------------------------------------------------------------------ #
    #  QThread entry                                                       #
    # ------------------------------------------------------------------ #

    def run(self) -> None:
        self._running = True
        frame_duration = 1.0 / self._target_fps

        # Each thread gets its own mss instance (not thread-safe to share)
        with mss.mss() as sct:
            while self._running:
                t0 = time.perf_counter()
                try:
                    frame = self._capture_frame(sct)
                    if frame is not None:
                        self.frame_ready.emit(frame)
                except Exception as exc:
                    self.error_occurred.emit(str(exc))

                # Adaptive sleep: subtract elapsed time so we stay on cadence
                elapsed = time.perf_counter() - t0
                sleep_for = frame_duration - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)

    # ------------------------------------------------------------------ #
    #  Internals                                                           #
    # ------------------------------------------------------------------ #

    def _capture_frame(self, sct: mss.mss) -> QImage | None:
        """
        Capture one frame using mss and return it as a QImage (ARGB32).

        Extension point: replace this method body with a CUDA or DXGI
        Desktop-Duplication path without changing the rest of the pipeline.
        """
        raw = sct.grab(self._monitor)
        if raw is None:
            return None

        # mss returns BGRA; convert to RGBA for Qt
        arr: np.ndarray = np.frombuffer(raw.bgra, dtype=np.uint8).reshape(
            raw.height, raw.width, 4
        )
        # BGRA → RGBA
        arr = arr[:, :, [2, 1, 0, 3]].copy()

        img = QImage(
            arr.data,
            raw.width,
            raw.height,
            raw.width * 4,
            QImage.Format.Format_RGBA8888,
        )
        return img.copy()   # detach from numpy buffer lifetime

    @staticmethod
    def _rect_to_monitor(rect: QRect) -> dict:
        return {
            "top": rect.top(),
            "left": rect.left(),
            "width": rect.width(),
            "height": rect.height(),
        }
