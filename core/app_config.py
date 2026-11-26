import os
import shutil
import tempfile
import time
from typing import Callable

from PySide6.QtCore import QSettings, QStandardPaths  # type: ignore

# 데이터 폴더에 저장되는 파일들
DATA_FILES = ["lyrics_stats.json", "overlay_settings.json", "overlay_styles.json"]


class AppConfig:
    """앱 전체의 글로벌 설정 (예: 데이터 저장 경로)을 관리합니다."""

    def __init__(self):
        self.settings = QSettings("Ow-wL", "LyricsOverlay")
        self._listeners: list[Callable[[str], None]] = []
        self._data_dir = self.settings.value("data_dir", None)
        first_run = not self._data_dir

        # 테스트·휴대용 실행: 환경 변수로 데이터 폴더를 지정하면 저장된 경로 대신 씁니다 (설정에는 기록 안 함).
        override = os.environ.get("LYRICSOVERLAY_DATA_DIR")
        if override:
            os.makedirs(override, exist_ok=True)
            self._data_dir = os.path.abspath(override)
            return

        if not self._data_dir:
            # 기본 경로: 문서/LyricsOverlay
            docs_path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
            self._data_dir = os.path.join(docs_path, "LyricsOverlay")
            self.settings.setValue("data_dir", self._data_dir)

        if not os.path.exists(self._data_dir):
            try:
                os.makedirs(self._data_dir)
            except Exception as e:
                print(f"[⚠️] 기본 데이터 폴더 생성 실패: {e}")
                # 실패 시 현재 폴더로 fallback
                self._data_dir = os.getcwd()
                self.settings.setValue("data_dir", self._data_dir)

        # 예전 버전은 실행 폴더에 데이터를 저장했습니다. 처음 실행할 때 한 번만 옮겨 옵니다.
        # (매번 하면 아무 폴더에서 실행해도 그 폴더의 JSON을 가져오게 됩니다.)
        if first_run:
            self._migrate_existing_files()

    @property
    def data_dir(self) -> str:
        return self._data_dir

    @property
    def record_history(self) -> bool:
        """감상 기록을 파일에 남길지. 데이터 폴더를 바꿔도 유지되도록 앱 설정(레지스트리)에 둡니다."""
        if not hasattr(self, "_record_history"):  # 메인 루프가 자주 읽으므로 메모리에 둡니다
            value = self.settings.value("record_history", True)
            self._record_history = value not in (False, "false", "0", 0)
        return self._record_history

    @record_history.setter
    def record_history(self, on: bool) -> None:
        self._record_history = bool(on)
        self.settings.setValue("record_history", bool(on))

    def add_listener(self, fn: Callable[[str], None]) -> None:
        """데이터 경로가 바뀌면 새 경로로 fn(new_dir)을 호출합니다.

        각 관리자(오버레이 설정, 통계, 창 복구 기록)는 여기서 자기 파일 경로를 바꾸고
        메모리의 최신 상태를 새 경로에 저장합니다.
        """
        self._listeners.append(fn)

    @staticmethod
    def existing_data_files(directory: str) -> list[str]:
        """directory에 이미 있는 데이터 파일 이름 목록."""
        return [f for f in DATA_FILES if os.path.exists(os.path.join(directory, f))]

    @staticmethod
    def is_writable(directory: str) -> bool:
        try:
            with tempfile.TemporaryFile(dir=directory):
                pass
            return True
        except Exception:
            return False

    def set_data_dir(self, new_dir: str, overwrite_existing: bool = False) -> bool:
        """데이터 경로를 바꾸고, 지금 쓰는 데이터를 새 경로에 저장합니다.

        새 경로에 같은 이름의 파일이 있으면 overwrite_existing=True일 때만 진행하며,
        그 파일은 덮어쓰기 전에 `.bak-<시각>`으로 백업합니다.
        기존 경로의 파일은 지우지 않고 그대로 둡니다.
        """
        if not new_dir or not os.path.isdir(new_dir):
            return False
        new_dir = os.path.abspath(new_dir)
        if os.path.normcase(new_dir) == os.path.normcase(os.path.abspath(self._data_dir)):
            return True
        if not self.is_writable(new_dir):
            return False

        existing = self.existing_data_files(new_dir)
        if existing and not overwrite_existing:
            return False
        stamp = time.strftime("%Y%m%d-%H%M%S")
        for name in existing:
            path = os.path.join(new_dir, name)
            try:
                shutil.copy2(path, f"{path}.bak-{stamp}")
            except Exception as e:
                print(f"[⚠️] 기존 파일 백업 실패 ({name}): {e}")
                return False

        self._data_dir = new_dir
        self.settings.setValue("data_dir", new_dir)
        for fn in self._listeners:
            try:
                fn(new_dir)
            except Exception as e:
                print(f"[⚠️] 데이터 경로 변경 반영 실패: {e}")
        return True

    @property
    def auto_update_check(self) -> bool:
        """새 버전을 자동으로 확인할지 (기본 켬)."""
        if not hasattr(self, "_auto_update_check"):
            value = self.settings.value("auto_update_check", True)
            self._auto_update_check = value not in (False, "false", "0", 0)
        return self._auto_update_check

    @auto_update_check.setter
    def auto_update_check(self, on: bool) -> None:
        self._auto_update_check = bool(on)
        self.settings.setValue("auto_update_check", bool(on))

    @property
    def ui_font(self) -> str:
        """앱 화면 글꼴 (gui.typography.UI_FONTS의 키). 가사 오버레이 글꼴과는 따로입니다."""
        return str(self.settings.value("ui_font", "pretendard") or "pretendard")

    @ui_font.setter
    def ui_font(self, key: str) -> None:
        self.settings.setValue("ui_font", key or "pretendard")

    @property
    def skipped_version(self) -> str:
        """'이 버전 건너뛰기'를 누른 버전. 자동 확인에서는 이 버전을 다시 알리지 않습니다."""
        return str(self.settings.value("skipped_version", "") or "")

    @skipped_version.setter
    def skipped_version(self, version: str) -> None:
        self.settings.setValue("skipped_version", version or "")

    def set_data_dir_on_next_start(self, new_dir: str) -> None:
        """새 경로의 기존 데이터를 쓰도록, 다음 실행부터 경로를 바꿉니다.

        지금 실행 중에는 기존 경로에 계속 저장해 새 경로의 파일을 덮어쓰지 않습니다.
        """
        self.settings.setValue("data_dir", os.path.abspath(new_dir))

    def _migrate_existing_files(self):
        """현재 디렉토리에 레거시 파일이 있다면 새 경로로 복사합니다."""
        cwd = os.getcwd()
        if cwd == self._data_dir:
            return

        for file_name in DATA_FILES:
            old_path = os.path.join(cwd, file_name)
            new_path = os.path.join(self._data_dir, file_name)
            if os.path.exists(old_path) and not os.path.exists(new_path):
                try:
                    shutil.copy2(old_path, new_path)
                    print(f"[🔄] 레거시 파일 마이그레이션: {file_name}")
                except Exception:
                    pass
