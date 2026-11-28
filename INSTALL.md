# 🛠️ 설치 방법 (Installation)

이 문서는 **LyricsOverlay** 프로그램의 설치 및 실행 환경 구성 방법을 안내합니다.

## 시스템 요구사항
- 운영체제: Windows 10 이상 (Windows 기본 OCR 기능 사용)
- Python 버전: Python 3.10 이상 권장

## 1. 소스 코드 다운로드

git을 사용하여 저장소를 클론하거나, [Download ZIP] 버튼을 눌러 소스코드를 다운로드합니다.

```bash
# 저장소 클론
git clone https://github.com/Ow-wL/LyricsOverlay
cd LyricsOverlay
```

## 2. 필수 라이브러리 설치

Python 패키지 매니저(pip)를 통해 프로그램 실행에 필요한 필수 라이브러리들을 설치합니다. 가급적 가상환경(venv)을 설정하고 설치하는 것을 권장합니다.

```bash
# 필수 라이브러리 설치
pip install -r requirements.txt
```

## 3. 프로그램 실행

설치가 완료되면 아래 명령어로 메인 프로그램을 실행할 수 있습니다.

```bash
python main.py
```
> **참고**: `main.py`는 애플리케이션의 메인 진입점 파일입니다. 실행 시 대시보드 화면이 열리며, 백그라운드에서 오버레이 엔진이 작동을 시작합니다.

## 4. exe 파일로 만들기

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\build.ps1
```

- 결과물: `dist\LyricsOverlay.exe`와 체크섬 파일 `dist\LyricsOverlay.exe.sha256.txt`
- 빌드 설정은 `main.spec`에 있습니다. 아이콘(`asset/icon.ico`)과 글꼴(`asset/Font`)이 exe에 함께 들어갑니다.
- 코드 서명 인증서가 있으면 `$env:LYRICSOVERLAY_SIGN_THUMBPRINT`에 인증서 지문을 넣고 빌드하면 서명까지 합니다.
- 아이콘을 바꿨다면 `venv\Scripts\python.exe tools\make_icon.py`로 여러 크기가 든 아이콘을 다시 만드세요.

받은 exe가 바뀌지 않았는지 확인하려면, 체크섬 파일의 값과 아래 결과를 비교하세요.

```powershell
Get-FileHash .\LyricsOverlay.exe -Algorithm SHA256
```

## 5. 새 버전 배포하기 (업데이트 알림이 뜨게 하려면)

앱은 GitHub의 **최신 릴리스**(Latest)를 보고 새 버전을 알려 주고, exe로 실행 중이면 그 자리에서 업데이트합니다.

**자동 (권장)**

1. `core/version.py`의 `APP_VERSION`을 올려 `main`에 머지합니다. (예: `1.4.0`)
2. 그 커밋에 같은 숫자의 태그를 만들어 올립니다.

   ```powershell
   git tag 1.4.0
   ```
   ```powershell
   git push origin 1.4.0
   ```
3. GitHub Actions의 `release` 워크플로(`.github/workflows/release.yml`)가 테스트 → exe 빌드와 자체 점검 → 사용 가이드 생성을 하고, 파일을 첨부한 릴리스 **초안**을 만듭니다. 태그와 `APP_VERSION`이 다르면 멈춥니다.
4. 초안에서 exe를 받아 직접 실행해 확인합니다. 변경 내용(`docs/release_notes_template.md`의 첫 줄 자리)을 적고 **게시**합니다. 초안인 동안에는 업데이트 알림이 뜨지 않습니다.

빌드 관련 파일(`build.ps1`, `main.spec`, `requirements*.txt` 등)을 고친 PR에서는 같은 워크플로가 릴리스 없이 빌드만 해 봅니다.

**수동**

1. `core/version.py`의 `APP_VERSION`을 올립니다. (예: `1.2.0`)
2. `.\build.ps1`로 빌드합니다.
3. GitHub에서 새 릴리스를 만듭니다.
   - 태그: 버전 숫자 그대로 (예: `1.2.0`, 앞에 `v`를 붙여도 됨). 지금 앱 버전보다 커야 알림이 뜹니다.
   - 첨부 파일: `dist\LyricsOverlay.exe` (이름을 바꾸지 마세요), `dist\LyricsOverlay.exe.sha256.txt`
   - '사전 릴리스(pre-release)'로 표시하면 알림이 뜨지 않습니다.
4. 릴리스 설명에 적은 내용이 앱의 '변경 내용'에서 보입니다.

앱은 GitHub가 계산한 파일의 SHA-256 값과 받은 파일을 비교한 뒤에만 교체합니다.
