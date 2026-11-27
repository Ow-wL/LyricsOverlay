"""앨범 커버 그리기: 저장된 커버가 있으면 그 이미지를, 없으면 곡마다 다른 색의 대체 타일을 그립니다."""

import hashlib
import os
from collections import OrderedDict

from PySide6.QtCore import QRectF, Qt  # type: ignore
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap  # type: ignore

from core import covers
from gui import typography

# 대체 타일 색 (커버가 아직 없을 때). 앨범 아트 느낌의 차분한 두 색 그라데이션
_PALETTE = [
    ("#F7B267", "#F25C54"), ("#3A6073", "#16222A"), ("#8E7DFF", "#2E6BD8"), ("#43C6AC", "#191654"),
    ("#E0C3FC", "#8EC5FC"), ("#FDC830", "#F37335"), ("#5F2C82", "#49A09D"), ("#0F2027", "#2C5364"),
    ("#EECDA3", "#EF629F"), ("#4B79A1", "#283E51"),
]

# 그린 커버 캐시. 곡을 많이 들어도 메모리가 계속 늘지 않게 가장 오래 안 쓴 것부터 버립니다(LRU).
# 목록용 작은 커버(44~112px)는 개당 수십 KB라 넉넉히, 흐린 배경(240px)은 지금 곡 것만 있으면 되므로 몇 개만.
_CACHE_MAX = 300
_BLUR_MAX = 3
_cache: "OrderedDict[tuple, QPixmap]" = OrderedDict()
_blur_cache: "OrderedDict[tuple, QPixmap]" = OrderedDict()


def _get(cache: OrderedDict, key):
    pm = cache.get(key)
    if pm is not None:
        cache.move_to_end(key)
    return pm


def _put(cache: OrderedDict, key, pm: QPixmap, limit: int) -> None:
    cache[key] = pm
    cache.move_to_end(key)
    while len(cache) > limit:
        cache.popitem(last=False)


def _load(path: str, px: int) -> QPixmap | None:
    try:
        key = (path, px, os.path.getmtime(path))
    except OSError:
        return None
    pm = _get(_cache, key)
    if pm is None:
        src = QPixmap(path)
        if src.isNull():
            return None
        pm = src.scaled(px, px, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        _put(_cache, key, pm, _CACHE_MAX)
    return pm


def cover_path(title: str, artist: str, song_id=None) -> str | None:
    return covers.path_for(title, artist, song_id)


def paint_art(painter: QPainter, rect: QRectF, title: str, artist: str = "", song_id=None,
              radius: float = 6, circle: bool = False) -> None:
    """rect 안에 커버(또는 대체 타일)를 그립니다."""
    rect = QRectF(rect)
    clip = QPainterPath()
    if circle:
        clip.addEllipse(rect)
    else:
        clip.addRoundedRect(rect, radius, radius)
    painter.save()
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.setClipPath(clip)
    dpr = painter.device().devicePixelRatioF() if painter.device() else 1.0
    path = cover_path(title, artist, song_id)
    pm = _load(path, int(max(rect.width(), rect.height()) * dpr)) if path else None
    if pm is not None:
        pm.setDevicePixelRatio(dpr)
        painter.drawPixmap(rect.topLeft(), pm)
    else:
        paint_placeholder(painter, rect, title or artist)
    painter.restore()


def paint_placeholder(painter: QPainter, rect: QRectF, seed: str) -> None:
    h = int(hashlib.md5((seed or "").encode("utf-8")).hexdigest()[:6], 16)
    c1, c2 = _PALETTE[h % len(_PALETTE)]
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0, QColor(c1))
    grad.setColorAt(1, QColor(c2))
    painter.fillRect(rect, grad)
    letter = (seed or "♪").strip()[:1].upper() or "♪"
    f = QFont(typography.family())
    f.setPixelSize(max(10, int(rect.height() * 0.42)))
    f.setWeight(QFont.Bold)
    painter.setFont(f)
    painter.setPen(QColor(255, 255, 255, 215))
    painter.drawText(rect, Qt.AlignCenter, letter)


def blurred_backdrop(title: str, artist: str, song_id=None) -> QPixmap | None:
    """지금 재생 카드 배경용: 커버를 아주 작게 줄였다가 키워 흐린 색면을 만듭니다(효과 없이 가볍게)."""
    path = cover_path(title, artist, song_id)
    if not path:
        return None
    key = ("blur", path)
    try:
        key = key + (os.path.getmtime(path),)
    except OSError:
        return None
    pm = _get(_blur_cache, key)
    if pm is None:
        src = QPixmap(path)
        if src.isNull():
            return None
        tiny = src.scaled(6, 6, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        pm = tiny.scaled(240, 240, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        _put(_blur_cache, key, pm, _BLUR_MAX)
    return pm
