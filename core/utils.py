import sys
import os

def resource_path(relative_path: str) -> str:
    """
    PyInstaller에 의해 패키징되었을 때와 일반 실행 시의 경로를 모두 지원하는 함수입니다.
    패키징된 경우 임시 폴더(sys._MEIPASS)의 경로를 반환하고, 일반 실행 시 원본 경로를 반환합니다.
    """
    try:
        # PyInstaller는 런타임에 임시 폴더를 생성하고 경로를 _MEIPASS에 저장합니다.
        base_path = sys._MEIPASS
    except AttributeError:
        # 일반 실행 환경
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)
