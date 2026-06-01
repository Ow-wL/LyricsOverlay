import cv2
import asyncio

from winsdk.windows.media.ocr import OcrEngine  # type: ignore
from winsdk.windows.graphics.imaging import BitmapDecoder  # type: ignore
from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter  # type: ignore

# 전역 OCR 엔진 인스턴스
_engine: OcrEngine = OcrEngine.try_create_from_user_profile_languages()


async def windows_native_ocr_split(image) -> list[str]:
    """이미지에서 Windows 기본 OCR로 텍스트 줄 목록을 추출합니다."""
    try:
        is_success, buffer = cv2.imencode(".bmp", image)
        if not is_success:
            return []
        stream = InMemoryRandomAccessStream()
        writer = DataWriter(stream)
        writer.write_bytes(buffer.tobytes())
        await writer.store_async()
        await writer.flush_async()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        software_bitmap = await decoder.get_software_bitmap_async()
        result = await _engine.recognize_async(software_bitmap)
        return [line.text for line in result.lines]
    except Exception:
        return []
