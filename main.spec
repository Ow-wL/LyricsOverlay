# -*- mode: python ; coding: utf-8 -*-
# 빌드는 build.ps1을 쓰세요 (exe와 함께 SHA-256 체크섬 파일을 만듭니다).
# 직접 빌드: venv\Scripts\python.exe -m PyInstaller main.spec --noconfirm
#
# 실행 중 코드가 읽는 파일은 모두 여기 datas에 있어야 합니다.
#   asset/icon.ico  — 창·작업 표시줄·트레이 아이콘
#   asset/brand_mark.png — 사이드바 상단 로고 마크 (없으면 'LO' 모노그램으로 대체)
#   asset/Font      — 앱 글꼴 (Pretendard, 하위 폴더의 나눔스퀘어 네오·Wanted Sans)
#   THIRD_PARTY_NOTICES.txt, LICENSE — 오픈소스 고지 (tools/make_notices.py가 생성, 정보 페이지에서 열기)
#
# 앱이 쓰지 않는 Qt·OpenCV 구성요소는 아래 _EXCLUDE로 뺍니다. 특히 Qt Virtual Keyboard는 오픈소스 배포 시
# GPLv3이고, OpenCV의 FFmpeg 모듈(동영상 입출력)은 쓰지 않습니다. 빼고 나서는 build.ps1의 자체 점검(--smoke-test)이
# 창·글꼴·아이콘이 정상인지 확인합니다.


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('asset/icon.ico', 'asset'),
        ('asset/brand_mark.png', 'asset'),
        ('asset/Font', 'asset/Font'),
        ('THIRD_PARTY_NOTICES.txt', '.'),
        ('LICENSE', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
    optimize=0,
)
_EXCLUDE = (
    'qt6virtualkeyboard', 'qtvirtualkeyboardplugin',          # GPLv3 모듈 (쓰지 않음)
    'opencv_videoio_ffmpeg',                                   # FFmpeg (쓰지 않음)
    'qt6quick', 'qt6qml', 'qt6pdf', 'qpdf.dll',                # 가상 키보드가 끌고 온 QML·Quick·PDF (쓰지 않음)
)


def _keep(entry) -> bool:
    name = entry[0].replace(chr(92), '/').lower()
    return not any(x in name for x in _EXCLUDE)


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='LyricsOverlay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['asset/icon.ico'],
)
