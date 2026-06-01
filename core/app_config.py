import os
import shutil
from PySide6.QtCore import QSettings, QStandardPaths  # type: ignore

class AppConfig:
    """앱 전체의 글로벌 설정 (예: 데이터 저장 경로)을 관리합니다."""

    def __init__(self):
        self.settings = QSettings("Ow-wL", "LyricsOverlay")
        self._data_dir = self.settings.value("data_dir", None)

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
                
        # 최초 실행 시 현재 폴더에 기존 파일이 있다면 복사 (마이그레이션 편의성)
        self._migrate_existing_files()

    @property
    def data_dir(self) -> str:
        return self._data_dir

    def set_data_dir(self, new_dir: str) -> bool:
        """데이터 경로를 변경하고 기존 파일들을 새 경로로 이동시킵니다."""
        if not new_dir or not os.path.exists(new_dir):
            return False

        old_dir = self._data_dir
        if old_dir == new_dir:
            return True

        files_to_move = ["lyrics_stats.json", "overlay_settings.json", "overlay_styles.json"]
        
        for file_name in files_to_move:
            old_path = os.path.join(old_dir, file_name)
            new_path = os.path.join(new_dir, file_name)
            if os.path.exists(old_path) and not os.path.exists(new_path):
                try:
                    shutil.copy2(old_path, new_path)
                except Exception as e:
                    print(f"[⚠️] 파일 복사 실패 ({file_name}): {e}")
        
        self._data_dir = new_dir
        self.settings.setValue("data_dir", new_dir)
        return True
        
    def _migrate_existing_files(self):
        """현재 디렉토리에 레거시 파일이 있다면 새 경로로 복사합니다."""
        cwd = os.getcwd()
        if cwd == self._data_dir:
            return
            
        files_to_move = ["lyrics_stats.json", "overlay_settings.json", "overlay_styles.json"]
        for file_name in files_to_move:
            old_path = os.path.join(cwd, file_name)
            new_path = os.path.join(self._data_dir, file_name)
            if os.path.exists(old_path) and not os.path.exists(new_path):
                try:
                    shutil.copy2(old_path, new_path)
                    print(f"[🔄] 레거시 파일 마이그레이션: {file_name}")
                except Exception:
                    pass
