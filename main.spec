# -*- mode: python ; coding: utf-8 -*-
# 빌드는 build.ps1을 쓰세요 (exe와 함께 SHA-256 체크섬 파일을 만듭니다).
# 직접 빌드: venv\Scripts\python.exe -m PyInstaller main.spec --noconfirm
#
# 실행 중 코드가 읽는 파일은 모두 여기 datas에 있어야 합니다.
#   asset/icon.ico  — 창·작업 표시줄·트레이 아이콘
#   asset/Font      — Pretendard 글꼴


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('asset/icon.ico', 'asset'),
        ('asset/Font', 'asset/Font'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
    optimize=0,
)
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
