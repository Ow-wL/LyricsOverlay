# 사용 가이드 원본

릴리즈에 첨부하는 사용 가이드(HTML · PDF)의 원본입니다.

| 파일 | 내용 |
|---|---|
| `guide_template.html` | 가이드 본문. `{{VERSION}}`, `{{IMG:파일명}}` 자리표시자를 빌드할 때 채웁니다. |
| `images/` | 가이드에 들어가는 스크린샷 (예시 데이터로 만든 화면) |
| `build_guide.py` | HTML과 PDF를 `dist/`에 만듭니다. |
| `make_screenshots.py` | UI를 바꾼 뒤 스크린샷을 다시 만듭니다. |

## 빌드

프로젝트 루트에서 실행합니다.

```powershell
venv\Scripts\python.exe docs\guide\build_guide.py
```

- 버전은 `core/version.py`의 `APP_VERSION`을 씁니다.
- 결과: `dist/LyricsOverlay_Guide_v<버전>.html`, `dist/LyricsOverlay_Guide_v<버전>.pdf`
- PDF는 설치된 Edge 또는 Chrome의 헤드리스 인쇄로 만듭니다.

## 스크린샷 다시 만들기

UI를 바꿨다면 먼저 스크린샷을 갱신한 뒤 빌드합니다.

```powershell
venv\Scripts\python.exe docs\guide\make_screenshots.py
```

- 임시 폴더의 예시 데이터만 사용하며, 실제 감상 기록이나 설정 파일은 건드리지 않습니다.
- `docs/guide/images/`와 README용 `asset/screenshots/`를 함께 갱신합니다.
- 화면에 표시되는 가사 문장은 화면 예시용으로 지어낸 문장입니다.
