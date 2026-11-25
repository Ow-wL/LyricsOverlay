"""사용 가이드 HTML/PDF 빌드.

프로젝트 루트에서 실행:
    venv\\Scripts\\python.exe docs\\guide\\build_guide.py

- docs/guide/guide_template.html 의 {{VERSION}}, {{IMG:파일명}} 을 채워
  이미지가 들어간 단일 HTML을 만듭니다 (버전은 core/version.py).
- 설치된 Edge 또는 Chrome의 헤드리스 인쇄로 같은 내용을 A4 PDF로 만듭니다.
- 결과물: dist/LyricsOverlay_Guide_v<버전>.html / .pdf
"""

import base64
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUIDE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from core.version import APP_VERSION  # noqa: E402

BROWSERS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def build_html(out_path: Path) -> None:
    html = (GUIDE_DIR / "guide_template.html").read_text(encoding="utf-8")
    html = html.replace("{{VERSION}}", APP_VERSION)

    def embed(m: re.Match) -> str:
        data = (GUIDE_DIR / "images" / m.group(1)).read_bytes()
        return "data:image/png;base64," + base64.b64encode(data).decode()

    html = re.sub(r"\{\{IMG:([^}]+)\}\}", embed, html)
    if "{{" in html:
        raise SystemExit("채워지지 않은 자리표시자가 남아 있습니다.")
    out_path.write_text(html, encoding="utf-8")


def build_pdf(html_path: Path, pdf_path: Path) -> bool:
    browser = next((b for b in BROWSERS if os.path.exists(b)), None)
    if browser is None:
        print("[!] Edge/Chrome을 찾지 못해 PDF는 만들지 않았습니다.")
        return False
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                "--virtual-time-budget=8000",
                f"--user-data-dir={profile}",
                f"--print-to-pdf={pdf_path}",
                html_path.as_uri(),
            ],
            check=True,
            timeout=120,
        )
    return pdf_path.exists()


def main() -> None:
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    html_path = dist / f"LyricsOverlay_Guide_v{APP_VERSION}.html"
    pdf_path = dist / f"LyricsOverlay_Guide_v{APP_VERSION}.pdf"

    build_html(html_path)
    print(f"HTML: {html_path} ({html_path.stat().st_size // 1024} KB)")
    if build_pdf(html_path, pdf_path):
        print(f"PDF:  {pdf_path} ({pdf_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
