"""화면 동작: 감상 기록 → 멜론 링크, 정보 페이지 업데이트 버튼, 업데이트 창."""

import unittest

from tests import _qt  # noqa: F401
from PySide6.QtWidgets import QApplication  # type: ignore

app = QApplication.instance() or QApplication([])

from core.updater import ReleaseInfo  # noqa: E402
from gui.pages.info_page import InfoPage  # noqa: E402
from gui.pages.music_list_page import MusicListPage  # noqa: E402
from gui.update_dialog import UpdateDialog, _NotesView  # noqa: E402


class HistoryLinkTest(unittest.TestCase):
    def test_double_click_target(self):
        page = MusicListPage()
        page.set_history([
            {"title": "봄날", "artist": "방탄소년단", "timestamp": "2026-11-26 10:00:00", "song_id": "30244931"},
            {"title": "밤편지", "artist": "아이유", "timestamp": "2026-11-26 09:00:00"},
        ])
        header, first, second = (page.music_list.item(i) for i in range(3))
        self.assertIsNone(page.entry_url(header))
        self.assertTrue(page.entry_url(first).endswith("songId=30244931"))
        self.assertIn("search", page.entry_url(second))


class InfoPageTest(unittest.TestCase):
    def test_install_button_follows_update_state(self):
        page = InfoPage()
        hits = []
        page.install_requested.connect(lambda: hits.append(1))
        self.assertTrue(page.install_btn.isHidden())
        page.show_install(True)
        self.assertFalse(page.install_btn.isHidden())
        page.install_btn.click()
        self.assertEqual(hits, [1])
        page.hide_install()
        self.assertTrue(page.install_btn.isHidden())


class UpdateDialogTest(unittest.TestCase):
    def test_notes_render_markdown_without_html(self):
        info = ReleaseInfo("9.9.9", "https://github.com/Ow-wL/LyricsOverlay/releases",
                           "**굵게** <b>태그</b>", exe_size=1024 * 1024)
        dlg = UpdateDialog(info)
        text = dlg.findChild(_NotesView).toPlainText()
        self.assertIn("굵게", text)
        self.assertNotIn("**", text)
        self.assertIn("<b>", text)  # HTML은 해석하지 않고 글자 그대로
        dlg.done(0)


if __name__ == "__main__":
    unittest.main()
