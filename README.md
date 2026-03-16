# Lyrics Overlay MVP

A Windows desktop application that captures a region from any music player
(Melon, YouTube Music, Spotify, etc.) and displays it as a semi-transparent,
always-on-top overlay suitable for use during full-screen gaming.

---

## File Structure

```
lyrics_overlay/
├── main.py               # Entry point
├── control_panel.py      # Main UI window
├── window_enumerator.py  # Win32 window listing
├── region_selector.py    # Drag-to-select overlay
├── capture_engine.py     # QThread capture loop (mss)
├── overlay_window.py     # Floating display window
└── requirements.txt
```

---

## How the Capture Loop Works

```
CaptureEngine (QThread)
│
│  run()
│  ┌─────────────────────────────────────────────┐
│  │  target_interval = 1 / target_fps (e.g. 33ms)
│  │                                             │
│  │  while running:                             │
│  │      t0 = perf_counter()                   │
│  │      raw  = mss.grab(monitor_dict)         │  ← ~2–5 ms on modern GPU
│  │      arr  = numpy BGRA→RGBA convert        │  ← ~1 ms
│  │      img  = QImage(arr)                    │
│  │      emit frame_ready(img)                 │  ← Qt signal, thread-safe
│  │                                             │
│  │      elapsed = perf_counter() - t0         │
│  │      sleep(max(0, interval - elapsed))     │  ← adaptive sleep
│  └─────────────────────────────────────────────┘
│
│  frame_ready  ──(Qt queued connection)──►  OverlayWindow.update_frame()
                                               │
                                               └─ QPixmap.fromImage()
                                               └─ self.update() → paintEvent
                                               └─ QPainter.drawPixmap()
```

**Key design decisions:**

| Decision | Rationale |
|---|---|
| `mss` for capture | Uses Windows GDI BitBlt under the hood; ~2–5 ms/frame, no D3D overhead |
| Dedicated `QThread` | Capture never blocks the Qt event loop / GUI |
| `QImage.copy()` | Detaches from the numpy buffer so the buffer can be freed each frame |
| Adaptive sleep | `sleep(interval - elapsed)` rather than fixed sleep prevents drift |
| `paintEvent` via `update()` | Qt coalesces rapid `update()` calls; no redundant repaints |
| `WS_EX_TRANSPARENT` | Win32 extended style that makes the HWND invisible to hit-testing |

---

## Installation

```bash
# Python 3.10+  (Windows only)
pip install -r requirements.txt
python main.py
```

---

## Usage

1. **Select Window** – choose your music player from the dropdown.
2. **Draw Region** – click "Draw Region…" and drag a rectangle over the
   lyrics area in the music player.
3. **Start Overlay** – the captured region appears as a floating window.
   Drag it anywhere on screen.
4. **Click-through** – enable the checkbox so the overlay doesn't intercept
   game mouse/keyboard input.

---

## Extension Points

### CUDA GPU Acceleration
Replace `CaptureEngine._capture_frame()`:
```python
# capture via mss → numpy array
# upload to GPU:  gpu_arr = cv2.cuda_GpuMat(); gpu_arr.upload(arr)
# run CUDA ops:   processed = cv2.cuda.resize(gpu_arr, ...)
# download:       result = processed.download()
# wrap in QImage as before
```

### Firebase Authentication
Add an `AuthManager` class before `ControlPanel` is constructed in `main.py`:
```python
auth = AuthManager(api_key="...")
if not auth.login_dialog():
    sys.exit(0)
panel = ControlPanel(auth=auth)
```
The class-based OOP structure means no existing module needs to change.
