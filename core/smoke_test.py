"""빌드 확인용 자체 점검: `LyricsOverlay.exe --smoke-test 결과.txt`

빌드한 exe 안에 꼭 필요한 Qt 모듈·플러그인·글꼴·아이콘이 들어 있는지, 창을 실제로 만들 수 있는지 확인합니다.
- 임시 폴더를 데이터 폴더로 쓰고, 실제 설정(레지스트리)·감상 기록·멜론에는 손대지 않습니다.
- 중복 실행 확인을 거치지 않으므로 이미 실행 중인 앱과 함께 돌릴 수 있습니다.
- 결과를 파일에 적고, 모두 통과하면 종료 코드 0, 아니면 1.
"""

import os
import sys
import tempfile
import time


class _TempConfig:
    """실제 설정을 건드리지 않는 임시 설정."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.record_history = True
        self.auto_update_check = False
        self.skipped_version = ""
        self.ui_font = "pretendard"
        self.melon_lyrics = True
        self.melon_covers = True

    def add_listener(self, fn) -> None:
        pass

    def set_data_dir(self, new_dir, overwrite_existing=False):
        return True


def run(argv: list[str]) -> int:
    report = argv[argv.index("--smoke-test") + 1] if len(argv) > argv.index("--smoke-test") + 1 else ""
    lines, ok = [], True

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        ok = ok and bool(cond)
        lines.append(f"{'OK  ' if cond else 'FAIL'} {name}{(' — ' + detail) if detail else ''}")

    try:
        from PySide6.QtGui import QFontDatabase, QGuiApplication  # type: ignore
        from PySide6.QtWidgets import QApplication  # type: ignore

        app = QApplication(sys.argv[:1])
        check("Qt 플랫폼 플러그인", QGuiApplication.platformName() == "windows", QGuiApplication.platformName())

        from gui import typography
        from gui.main_window import MainWindow

        data_dir = tempfile.mkdtemp(prefix="lyricsoverlay-smoke-")
        window = MainWindow(stats={"play_history": [], "total_lines": 0, "total_play_time_sec": 0},
                            app_config=_TempConfig(data_dir))
        window.move(-3000, -3000)  # 화면 밖에서 만들어 깜빡이지 않게
        window.show()
        end = time.monotonic() + 1.5
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.02)
        check("메인 창 생성", window.isVisible())
        for key, _label, _family in typography.UI_FONTS:  # 선택형 글꼴도 exe에 들어 있는지 확인
            typography.ensure_loaded(key)
        families = set(QFontDatabase.families())
        for key, label, family in typography.UI_FONTS:
            check(f"글꼴 {label}", family in families, family)
        check("앱 아이콘", not window.windowIcon().isNull())
        check("사이드바 로고 이미지", window.brand_mark._image is not None)
        notices = None
        try:
            from core.utils import resource_path
            notices = resource_path("THIRD_PARTY_NOTICES.txt")
        except Exception:
            pass
        check("오픈소스 고지 파일", bool(notices) and os.path.exists(notices), notices or "")
        if window.tray is not None:
            window.tray.hide()
        window.hide()
        app.processEvents()
    except Exception as e:  # 어떤 이유로든 실패하면 기록
        import traceback

        check("예외 없이 실행", False, f"{e}\n{traceback.format_exc()}")

    text = "\n".join(lines) + f"\n결과: {'통과' if ok else '실패'}\n"
    if report:
        with open(report, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        print(text)
    return 0 if ok else 1
