r"""THIRD_PARTY_NOTICES.txt를 만듭니다 (배포 exe에 함께 넣는 오픈소스 고지).

빌드 환경(venv)에 실제로 설치된 패키지의 버전과 라이선스 파일을 그대로 모읍니다.
패키지를 올리거나 번들 구성을 바꾸면 build.ps1이 이 스크립트를 다시 실행합니다.

실행: venv\Scripts\python.exe tools\make_notices.py
"""

import importlib.metadata as md
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "THIRD_PARTY_NOTICES.txt")
LIC = os.path.join(ROOT, "licenses")

# (배포 이름, 화면 이름, 라이선스, 비고)
PACKAGES = [
    ("PySide6_Essentials", "Qt for Python (PySide6) + Qt 6", "LGPL-3.0", "아래 'Qt·PySide6 (LGPL-3.0)' 절 참고"),
    ("shiboken6", "Shiboken6", "LGPL-3.0", ""),
    ("opencv-python", "OpenCV (opencv-python)", "Apache-2.0 (+ 제3자 구성요소)", "FFmpeg 모듈은 번들에서 제외"),
    ("numpy", "NumPy", "BSD-3-Clause (+ OpenBLAS 등)", ""),
    ("requests", "Requests", "Apache-2.0", "NOTICE 포함"),
    ("urllib3", "urllib3", "MIT", ""),
    ("idna", "idna", "BSD-3-Clause", ""),
    ("charset-normalizer", "charset-normalizer", "MIT", ""),
    ("certifi", "certifi", "MPL-2.0", "소스: https://github.com/certifi/python-certifi"),
    ("beautifulsoup4", "Beautiful Soup", "MIT", ""),
    ("soupsieve", "Soup Sieve", "MIT", ""),
    ("rapidfuzz", "RapidFuzz", "MIT", ""),
    ("keyboard", "keyboard", "MIT", ""),
    ("winsdk", "Python/WinRT (winsdk)", "MIT", ""),
    ("pywin32", "pywin32", "PSF-2.0 등 (구성별)", ""),
    ("pyinstaller", "PyInstaller (부트로더)", "GPL-2.0-or-later + 부트로더 예외", "예외 조항에 따라 앱 라이선스에 영향 없음"),
]

LICENSE_HINTS = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")


def dist_license_files(dist_name: str) -> list[tuple[str, str]]:
    dist = md.distribution(dist_name)
    out = []
    for f in dist.files or []:
        name = os.path.basename(str(f)).upper()
        if not any(name.startswith(h) for h in LICENSE_HINTS):
            continue
        p = str(f)
        if "/" in p and not p.split("/")[0].endswith((".dist-info",)) and dist_name not in ("pywin32", "opencv-python"):
            continue  # 패키지 안쪽의 하위 모듈 라이선스(예: numpy/random)는 dist-info 쪽 전문에 포함됨
        if p.endswith((".py", ".pyi", ".pyc")) or "licensemanagement" in p or "license_plate" in p:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except Exception:
            continue
        if "LicenseRef-Qt-Commercial" in p:
            continue  # 상용 라이선스 안내 파일 — 우리는 LGPL로 사용
        out.append((p, text))
    return out


def read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def section(title: str, body: str) -> str:
    bar = "=" * 78
    return f"\n{bar}\n{title}\n{bar}\n\n{body.rstrip()}\n"


def main() -> int:
    parts = []
    parts.append(
        "Lyrics Overlay — 오픈소스 고지 (THIRD PARTY NOTICES)\n\n"
        "이 프로그램(LyricsOverlay.exe)에는 아래 오픈소스 소프트웨어와 글꼴이 포함돼 있습니다.\n"
        "각 구성요소는 해당 라이선스를 따르며, 라이선스 전문은 이 파일 아래쪽에 있습니다.\n"
        "Lyrics Overlay 자체의 라이선스는 MIT입니다 (LICENSE 파일, https://github.com/Ow-wL/LyricsOverlay).\n"
    )
    rows = []
    for dist_name, label, lic, note in PACKAGES:
        try:
            ver = md.version(dist_name)
        except md.PackageNotFoundError:
            continue
        rows.append(f"- {label} {ver} — {lic}" + (f" ({note})" if note else ""))
    rows += [
        f"- Python {sys.version.split()[0]} 런타임 — PSF-2.0 (+ OpenSSL 1.1, libffi, bzip2 등, 아래 Python 절)",
        "- OpenSSL 3 (Qt TLS 백엔드용 libcrypto-3/libssl-3) — Apache-2.0",
        "- Microsoft Visual C++ 런타임 (VCRUNTIME140 등) — Microsoft 재배포 허용 조건에 따라 포함",
        "- 글꼴 Pretendard — SIL OFL 1.1",
        "- 글꼴 Wanted Sans — SIL OFL 1.1",
        "- 글꼴 나눔스퀘어 네오 — SIL OFL 1.1 (NAVER, Reserved Font Name 포함)",
    ]
    parts.append("포함된 구성요소\n\n" + "\n".join(rows) + "\n")

    parts.append(section(
        "Qt·PySide6 (LGPL-3.0) — 소스 코드와 교체 방법",
        "Qt 6와 Qt for Python(PySide6, Shiboken6)은 GNU LGPL 3.0으로 사용합니다. 수정하지 않았습니다.\n"
        "- Qt 소스: https://download.qt.io/official_releases/qt/\n"
        "- PySide6·Shiboken6 소스: https://download.qt.io/official_releases/QtForPython/ ,"
        " https://code.qt.io/cgit/pyside/pyside-setup.git/\n"
        "- 라이브러리 교체(재결합): Lyrics Overlay의 전체 소스와 빌드 스크립트(build.ps1, main.spec)가\n"
        "  https://github.com/Ow-wL/LyricsOverlay 에 공개돼 있습니다. 수정한 Qt/PySide6를 설치한 환경에서\n"
        "  같은 스크립트로 다시 빌드하면 수정한 라이브러리로 동작하는 실행 파일을 만들 수 있습니다.\n"
        "- 위 소스를 받기 어려우면 GitHub 이슈로 요청해 주세요. 사용한 버전의 소스를 제공합니다.\n"
        "- 앱에서 쓰지 않는 GPL 전용 Qt 모듈(Qt Virtual Keyboard 등)은 번들에서 제외했습니다.\n\n"
        "LGPL-3.0 전문은 아래에, 이 라이선스가 참조하는 GPL-3.0 전문은 그 다음에 있습니다."))

    seen: set[int] = set()  # 같은 전문이 두 곳(패키지 폴더와 dist-info)에 있으면 한 번만
    for dist_name, label, _lic, _note in PACKAGES:
        try:
            files = dist_license_files(dist_name)
            ver = md.version(dist_name)
        except md.PackageNotFoundError:
            continue
        for path, text in files:
            key = hash(text.strip())
            if key in seen:
                continue
            seen.add(key)
            parts.append(section(f"{label} {ver} — {path}", text))

    import sysconfig  # noqa: F401
    py_license = os.path.join(sys.base_prefix, "LICENSE.txt")
    if os.path.exists(py_license):
        parts.append(section(f"Python {sys.version.split()[0]} (LICENSE.txt, 포함 구성요소 라이선스 포함)", read(py_license)))

    for name in ("LGPL-3.0.txt", "GPL-3.0.txt", "MPL-2.0.txt"):
        parts.append(section(f"라이선스 전문: {name[:-4]}", read(os.path.join(LIC, name))))

    fonts = [
        ("글꼴 Pretendard", os.path.join(ROOT, "asset", "Font", "OFL-Pretendard.txt")),
        ("글꼴 Wanted Sans", os.path.join(ROOT, "asset", "Font", "WantedSans", "OFL-WantedSans.txt")),
        ("글꼴 나눔스퀘어 네오", os.path.join(ROOT, "asset", "Font", "NanumSquareNeo", "LICENSE-NanumSquareNeo.txt")),
    ]
    for title, path in fonts:
        if os.path.exists(path):
            parts.append(section(title, read(path)))

    # 줄바꿈은 운영체제 기본값(Windows CRLF)으로: 저장소 체크아웃과 같아서 빌드 후 '변경됨'으로 뜨지 않음
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"{OUT} 생성 ({os.path.getsize(OUT) // 1024}KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
