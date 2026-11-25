"""새 버전 확인과 업데이트 안전장치 (네트워크·프로세스 실행 없이)."""

import os
import tempfile
import unittest
from unittest import mock

from tests import _qt  # noqa: F401
import core.update_install as ui
import core.updater as up

REPO = "Ow-wL/LyricsOverlay"
DIGEST = "sha256:" + "ab" * 32


def release(tag="1.9.0", assets=None, **extra):
    data = {
        "tag_name": tag, "draft": False, "prerelease": False, "body": "notes",
        "html_url": f"https://github.com/{REPO}/releases/tag/{tag}",
        "assets": assets if assets is not None else [exe_asset(tag)],
    }
    data.update(extra)
    return data


def exe_asset(tag, **extra):
    a = {"name": "LyricsOverlay.exe", "state": "uploaded", "size": 1000, "digest": DIGEST,
         "browser_download_url": f"https://github.com/{REPO}/releases/download/{tag}/LyricsOverlay.exe"}
    a.update(extra)
    return a


class VersionTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(up.parse_version("1.2.0"), (1, 2, 0))
        self.assertEqual(up.parse_version("v1.10"), (1, 10, 0))
        self.assertIsNone(up.parse_version("1.2.0-beta"))
        self.assertIsNone(up.parse_version(None))

    def test_compare_numerically(self):
        self.assertTrue(up.is_newer("1.10.0", "1.9.0"))
        self.assertFalse(up.is_newer("1.2.0", "1.2.0"))
        self.assertFalse(up.is_newer("abc", "1.0.0"))


class FetchLatestTest(unittest.TestCase):
    def fetch(self, data):
        with mock.patch.object(up, "_get_json", return_value=data):
            return up.fetch_latest()

    def test_valid_release_can_auto_update(self):
        info = self.fetch(release())
        self.assertEqual(info.version, "1.9.0")
        self.assertTrue(info.can_auto_update)
        self.assertEqual(info.exe_sha256, "ab" * 32)

    def test_prerelease_and_draft_ignored(self):
        self.assertIsNone(self.fetch(release(prerelease=True)))
        self.assertIsNone(self.fetch(release(draft=True)))

    def test_missing_digest_means_manual_only(self):
        info = self.fetch(release(assets=[exe_asset("1.9.0", digest=None)]))
        self.assertFalse(info.can_auto_update)

    def test_duplicate_exe_assets_rejected(self):
        info = self.fetch(release(assets=[exe_asset("1.9.0"), exe_asset("1.9.0")]))
        self.assertFalse(info.can_auto_update)

    def test_foreign_or_other_tag_url_rejected(self):
        evil = exe_asset("1.9.0", browser_download_url="https://evil.example.com/LyricsOverlay.exe")
        self.assertFalse(self.fetch(release(assets=[evil])).can_auto_update)
        other_tag = exe_asset("1.0.0")
        self.assertFalse(self.fetch(release(assets=[other_tag])).can_auto_update)

    def test_html_url_outside_repo_replaced(self):
        info = self.fetch(release(html_url="https://evil.example.com/"))
        self.assertEqual(info.html_url, up.RELEASES_PAGE)


class CheckerTest(unittest.TestCase):
    def test_manual_check_reports_available(self):
        info = up.ReleaseInfo("99.0.0", up.RELEASES_PAGE, "")
        with mock.patch.object(up, "fetch_latest", return_value=info):
            c = up.UpdateChecker()
            c.check_now()
            c._future.result(timeout=5)
            kind, payload, manual = c.poll(auto_enabled=True)
            c.shutdown()
        self.assertEqual((kind, manual), ("available", True))

    def test_invalid_release_distinguished(self):
        with mock.patch.object(up, "fetch_latest", return_value=None):
            c = up.UpdateChecker()
            c.check_now()
            c._future.result(timeout=5)
            kind, _, _ = c.poll(auto_enabled=True)
            c.shutdown()
        self.assertEqual(kind, "invalid")


class InstallSafetyTest(unittest.TestCase):
    def test_redirect_to_unknown_host_refused_before_request(self):
        with mock.patch("requests.Session.get") as get:
            with self.assertRaises(ui.UpdateError):
                ui._open_following_redirects("https://evil.example.com/x.exe")
            get.assert_not_called()
        with self.assertRaises(ui.UpdateError):
            ui._open_following_redirects("http://github.com/x.exe")  # https만 허용

    def test_download_requires_digest(self):
        info = up.ReleaseInfo("9.9.9", up.RELEASES_PAGE, "", exe_url="https://github.com/x", exe_size=10)
        with self.assertRaises(ui.UpdateError):
            ui.download(info, lambda d, t: None, lambda: False)

    def test_apply_mode_refuses_other_target(self):
        with mock.patch("subprocess.Popen") as popen:
            code = ui.run_apply_mode(["x", "--apply-update", r"C:\Windows\System32\notepad.exe",
                                      "--wait-pids", "1"])
        self.assertEqual(code, 2)
        popen.assert_not_called()

    def test_cleanup_only_touches_own_folder_files(self):
        with tempfile.TemporaryDirectory() as d:
            exe = os.path.join(d, "LyricsOverlay.exe")
            keep = os.path.join(d, "다른파일.exe")
            leftovers = [os.path.join(d, "LyricsOverlay.update-abc.exe"), exe + ".previous"]
            for p in [exe, keep, *leftovers]:
                open(p, "w").close()
            with mock.patch.object(ui, "current_exe", return_value=exe), \
                    mock.patch.object(ui, "is_frozen", return_value=True):
                ui.cleanup_after_update([])
            self.assertTrue(os.path.exists(exe))
            self.assertTrue(os.path.exists(keep))
            for p in leftovers:
                self.assertFalse(os.path.exists(p))


if __name__ == "__main__":
    unittest.main()
