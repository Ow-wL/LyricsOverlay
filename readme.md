# LyricsOverlay

가사 오버레이 프로젝트입니다. 실행 중인 음악의 가사를 실시간으로 인식하여 화면에 표시합니다.

## 파일 구성

- **lyrics_main.py** - 프로그램의 메인 실행 파일 (OCR, 가사 매칭, UI 업데이트 통합)
- **lyrics_overlay.py** - 가사를 화면에 표시하는 투명 오버레이 UI 구현
- **lyrics_searcher.py** - 멜론 등에서 노래 제목으로 가사를 검색하고 가져오는 모듈
- **lyric_matcher.py** - OCR로 인식된 텍스트와 검색된 가사를 비교하여 최적의 구절을 찾는 모듈
- **install.txt** - 프로그램 실행에 필요한 라이브러리 설치 안내
- **readme.md** - 프로젝트 설명 및 파일 구성 안내
- **🛠️ 도구 및 테스트 파일/get_roi.py** - OCR 인식을 위한 화면 영역(ROI) 설정 도구
- **🛠️ 도구 및 테스트 파일/lyrics_window3.py** - 가사 표시 창 관련 테스트 또는 대체 UI 구현 파일
