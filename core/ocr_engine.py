import cv2

from winsdk.windows.globalization import Language  # type: ignore
from winsdk.windows.media.ocr import OcrEngine  # type: ignore
from winsdk.windows.graphics.imaging import BitmapDecoder  # type: ignore
from winsdk.windows.storage.streams import InMemoryRandomAccessStream, DataWriter  # type: ignore


def _create_engine():
    """한국어 OCR을 우선 사용하고, 없으면 사용자 프로필 언어로 만듭니다.

    Returns (engine | None, 상태 메시지)
    """
    try:
        ko = Language("ko")
        if OcrEngine.is_language_supported(ko):
            engine = OcrEngine.try_create_from_language(ko)
            if engine is not None:
                return engine, "한국어 OCR 사용 중"
        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is not None:
            tag = engine.recognizer_language.language_tag
            return engine, f"한국어 OCR이 없어 '{tag}' OCR을 사용 중 (한국어 가사 인식이 부정확할 수 있음)"
    except Exception as e:
        return None, f"OCR 엔진을 만들 수 없습니다: {e}"
    return None, "사용할 수 있는 OCR 언어가 없습니다"


_engine, OCR_STATUS = _create_engine()
OCR_KOREAN = _engine is not None and OCR_STATUS.startswith("한국어")
OCR_HELP = (
    "Windows 설정 → 시간 및 언어 → 언어 및 지역에서 '한국어'를 추가하고, "
    "언어 옵션에서 '광학 문자 인식(OCR)'을 설치한 뒤 프로그램을 다시 시작하세요."
)


def ocr_available() -> bool:
    return _engine is not None


async def windows_native_ocr_split(image) -> list[str]:
    """이미지에서 Windows 기본 OCR로 텍스트 줄 목록을 추출합니다."""
    if _engine is None:
        return []
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
