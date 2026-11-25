r"""asset/icon.ico를 여러 크기(16~256px)가 든 아이콘으로 다시 만듭니다.

원래 아이콘에는 256px 한 장만 있어 작업 표시줄·탐색기의 작은 크기에서 Windows가 줄여 그렸습니다.
크기마다 미리 부드럽게 줄인 PNG를 넣어 두면 작은 아이콘도 또렷합니다. (PNG 항목 ICO는 Windows Vista 이상 지원)

실행: venv\Scripts\python.exe tools\make_icon.py
"""

import os
import struct
import sys

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "asset", "icon.ico")


def png_bytes(img: QImage) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(data)


def main() -> int:
    QApplication(sys.argv)
    src = QImage(SRC)
    if src.isNull():
        print(f"원본 아이콘을 읽지 못했습니다: {SRC}")
        return 1
    src = src.convertToFormat(QImage.Format_ARGB32)
    images = [png_bytes(src.scaled(s, s, Qt.KeepAspectRatio, Qt.SmoothTransformation)) for s in SIZES]

    header = struct.pack("<HHH", 0, 1, len(SIZES))
    offset = 6 + 16 * len(SIZES)
    entries = b""
    for size, data in zip(SIZES, images):
        dim = 0 if size >= 256 else size  # ICO 형식에서 0은 256을 뜻함
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    with open(SRC, "wb") as f:
        f.write(header + entries + b"".join(images))
    print(f"{SRC} 생성: {', '.join(map(str, SIZES))}px")
    return 0


if __name__ == "__main__":
    sys.exit(main())
