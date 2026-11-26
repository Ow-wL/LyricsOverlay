r"""asset/icon/*.svg에서 asset/icon.ico(16~256px)와 사이드바 로고 asset/brand_mark.png를 만듭니다.

- 32px 이상: asset/icon/icon.svg (가사 줄 세 개 + 음표)
- 16·20·24px: asset/icon/icon_small.svg (줄 두 개로 간소화, 작은 크기에서 뭉개지지 않게)
크기마다 벡터에서 바로 그리므로 작업 표시줄·트레이의 작은 아이콘도 또렷합니다. (PNG 항목 ICO는 Windows Vista 이상 지원)

실행: venv\Scripts\python.exe tools\make_icon.py [--preview 미리보기.png]
"""

import os
import struct
import sys

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]
SMALL_MAX = 24  # 이 크기까지는 간소화 버전을 씁니다
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_LARGE = os.path.join(ROOT, "asset", "icon", "icon.svg")
SVG_SMALL = os.path.join(ROOT, "asset", "icon", "icon_small.svg")
OUT = os.path.join(ROOT, "asset", "icon.ico")
BRAND_MARK = os.path.join(ROOT, "asset", "brand_mark.png")
BRAND_MARK_SIZE = 256  # 사이드바에서 38px(고배율 화면은 그 배수)로 줄여 그립니다


def render(renderer: QSvgRenderer, size: int, supersample: int = 1) -> QImage:
    """SVG를 size px 정사각형으로 그립니다. supersample>1이면 크게 그려서 부드럽게 줄입니다."""
    big = size * supersample
    img = QImage(big, big, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    renderer.render(p, QRectF(0, 0, big, big))
    p.end()
    if supersample > 1:
        img = img.scaled(size, size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    return img


def png_bytes(img: QImage) -> bytes:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(data)


def main() -> int:
    QApplication(sys.argv)
    large = QSvgRenderer(SVG_LARGE)
    small = QSvgRenderer(SVG_SMALL)
    if not large.isValid() or not small.isValid():
        print(f"SVG를 읽지 못했습니다: {SVG_LARGE}, {SVG_SMALL}")
        return 1

    images = {}
    for s in SIZES:
        if s <= SMALL_MAX:
            images[s] = render(small, s, supersample=1)  # 16px 격자에 맞춘 좌표라 그대로 그립니다
        else:
            images[s] = render(large, s, supersample=4)

    header = struct.pack("<HHH", 0, 1, len(SIZES))
    offset = 6 + 16 * len(SIZES)
    entries = b""
    blobs = []
    for size in SIZES:
        data = png_bytes(images[size])
        dim = 0 if size >= 256 else size  # ICO 형식에서 0은 256을 뜻함
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        blobs.append(data)
    with open(OUT, "wb") as f:
        f.write(header + entries + b"".join(blobs))
    print(f"{OUT} 생성: {', '.join(map(str, SIZES))}px")

    render(large, BRAND_MARK_SIZE, supersample=4).save(BRAND_MARK)
    print(f"{BRAND_MARK} 생성: {BRAND_MARK_SIZE}px")

    if "--preview" in sys.argv:
        out = sys.argv[sys.argv.index("--preview") + 1]
        pad = 24
        total_w = sum(s for s in SIZES) + pad * (len(SIZES) + 1)
        sheet = QImage(total_w, 256 + pad * 2, QImage.Format_ARGB32_Premultiplied)
        sheet.fill(QColor("#202020"))  # 다크 작업 표시줄 색
        p = QPainter(sheet)
        x = pad
        for s in SIZES:
            p.drawImage(x, pad + (256 - s) // 2, images[s])
            x += s + pad
        p.end()
        sheet.save(out)
        print(f"미리보기 저장: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
