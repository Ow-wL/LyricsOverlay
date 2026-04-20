```
LyricsOverlay/
│
├── main.py              # [실행 파일] 전체 로직을 총괄 (OCR + 매칭 + UI 연결)
├── overlay_ui.py        # [UI] PySide6 기반의 투명 오버레이 창 설정
├── lyrics_searcher.py   # [크롤링] 멜론에서 정답 가사집을 가져오는 역할
├── lyric_matcher.py     # [보정] OCR 오타를 정답 가사집과 대조해 수정하는 역할
└── (requirements.txt)   # 필요한 라이브러리 목록 (필선택)
```