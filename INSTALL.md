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
