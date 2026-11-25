"""앱 버전 (정보 페이지 등에서 표시). 릴리즈할 때 이 값만 올리면 됩니다."""

APP_VERSION = "1.2.2"

# 작업 표시줄이 이 앱을 구분하는 ID (AppUserModelID).
# Windows는 이 ID별로 작업 표시줄 아이콘을 기억해 두는데, 예전 ID(owwl.lyricsoverlay.app.1.0)에는
# 아이콘 없던 옛 빌드 때의 빈 아이콘이 남아 새 빌드도 기본 아이콘으로 보였습니다.
# 그래서 ID를 새로 정했습니다. 앞으로 같은 문제가 생기면 끝의 숫자를 올리면 됩니다.
APP_USER_MODEL_ID = "OwwL.LyricsOverlay.App.2"
