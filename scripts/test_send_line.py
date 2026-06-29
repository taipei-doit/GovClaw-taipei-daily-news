"""scripts/send_line.py 的單元測試（不觸網）。

於 scripts/ 目錄執行：  cd scripts && python -m unittest -v
"""
import io
import json
import os
import tempfile
import unittest
import urllib.error
from datetime import datetime as _RealDateTime, timezone as _tz
from pathlib import Path
from unittest import mock

import send_line


class SafeYouTubeURLTests(unittest.TestCase):
    def test_valid_https(self):
        u = "https://www.youtube.com/watch?v=abc"
        self.assertEqual(send_line.safe_youtube_url(u), u)

    def test_short_host(self):
        u = "https://youtu.be/abc"
        self.assertEqual(send_line.safe_youtube_url(u), u)

    def test_http_rejected(self):
        self.assertEqual(send_line.safe_youtube_url("http://www.youtube.com/x", "FB"), "FB")

    def test_evil_host_rejected(self):
        self.assertEqual(send_line.safe_youtube_url("https://youtube.com.evil.com/x", "FB"), "FB")

    def test_userinfo_rejected(self):
        self.assertEqual(send_line.safe_youtube_url("https://youtu.be@evil.com/x", "FB"), "FB")

    def test_subdomain_not_allowed(self):
        self.assertEqual(send_line.safe_youtube_url("https://music.youtube.com/x", "FB"), "FB")

    def test_protocol_relative_rejected(self):
        self.assertEqual(send_line.safe_youtube_url("//youtu.be/x", "FB"), "FB")

    def test_javascript_rejected(self):
        self.assertEqual(send_line.safe_youtube_url("javascript:alert(1)", "FB"), "FB")

    def test_data_rejected(self):
        self.assertEqual(send_line.safe_youtube_url("data:text/html,<script>", "FB"), "FB")

    def test_empty_fallback(self):
        self.assertEqual(send_line.safe_youtube_url("  \n", "FB"), "FB")

    def test_uppercase_scheme_accepted(self):
        u = "HTTPS://youtu.be/x"
        self.assertEqual(send_line.safe_youtube_url(u, "FB"), u)

    def test_open_redirect_rejected(self):
        for u in (
            "https://www.youtube.com/redirect?q=https://evil.com",
            "https://www.youtube.com/redirect%2f?q=https://evil.com",
            "https://www.youtube.com/REDIRECT?q=x",
            "https://www.youtube.com/redirect/foo",
            "https://www.youtube.com/attribution_link?u=/evil",
        ):
            self.assertEqual(send_line.safe_youtube_url(u, "FB"), "FB", u)

    def test_legit_path_not_overblocked(self):
        u = "https://www.youtube.com/redirect-guide"
        self.assertEqual(send_line.safe_youtube_url(u, "FB"), u)


class LoadNewsTitlesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.json_path = Path(self.tmp.name) / "selected_articles.json"
        p = mock.patch.object(send_line, "INPUT_JSON", self.json_path)
        p.start()
        self.addCleanup(p.stop)

    def _write(self, obj):
        self.json_path.write_text(json.dumps(obj), encoding="utf-8")

    def test_missing_fails_closed(self):
        with self.assertRaises(SystemExit):
            send_line.load_news_titles()

    def test_invalid_json_fails_closed(self):
        self.json_path.write_text("{bad", encoding="utf-8")
        with self.assertRaises(SystemExit):
            send_line.load_news_titles()

    def test_invalid_utf8_fails_closed(self):
        self.json_path.write_bytes(b"\xff\xfe\x00bad")
        with self.assertRaises(SystemExit):
            send_line.load_news_titles()

    def test_selected_not_list_fails_closed(self):
        self._write({"selected": "nope"})
        with self.assertRaises(SystemExit):
            send_line.load_news_titles()

    def test_empty_fails_closed(self):
        self._write({"selected": []})
        with self.assertRaises(SystemExit):
            send_line.load_news_titles()

    def test_no_valid_titles_fails_closed(self):
        self._write({"selected": [{"title": "  "}, {"x": 1}, "y"]})
        with self.assertRaises(SystemExit):
            send_line.load_news_titles()

    def test_valid(self):
        self._write({"selected": [{"title": " A "}, {"title": "B"}]})
        self.assertEqual(send_line.load_news_titles(), ["A", "B"])

    def test_caps_count(self):
        self._write({"selected": [{"title": f"t{i}"} for i in range(20)]})
        self.assertEqual(len(send_line.load_news_titles()), send_line.MAX_ITEMS)

    def test_caps_title_length(self):
        self._write({"selected": [{"title": "x" * 500}]})
        self.assertEqual(len(send_line.load_news_titles()[0]), send_line.MAX_TITLE_LEN)


class BuildMessageTests(unittest.TestCase):
    def test_alt_text_truncated(self):
        titles = ["長標題" * 50 for _ in range(5)]
        msgs = send_line.build_flex_message(titles, "2026-06-29", "https://youtu.be/x")
        self.assertLessEqual(len(msgs[0]["altText"]), send_line.MAX_ALT_TEXT_LEN)

    def test_youtube_url_in_button(self):
        msgs = send_line.build_flex_message(["A"], "2026-06-29", "https://youtu.be/x")
        uris = [b["action"]["uri"] for b in msgs[0]["contents"]["footer"]["contents"]]
        self.assertIn("https://youtu.be/x", uris)


class BroadcastTests(unittest.TestCase):
    def _msg(self):
        return [{"type": "text", "text": "x"}]

    def test_http_error_no_body_leak(self):
        body = b'{"message":"super-secret-internal-detail"}'
        err = urllib.error.HTTPError("https://api.line.me/x", 400, "Bad Request", {}, io.BytesIO(body))
        with mock.patch("send_line.urllib.request.urlopen", side_effect=err):
            with self.assertRaises(RuntimeError) as ctx:
                send_line.broadcast_message(self._msg(), "tok")
        self.assertIn("400", str(ctx.exception))
        self.assertNotIn("super-secret-internal-detail", str(ctx.exception))

    def test_urlerror_reraised(self):
        with mock.patch("send_line.urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            with self.assertRaises(RuntimeError):
                send_line.broadcast_message(self._msg(), "tok")

    def test_timeout_passed(self):
        cm = mock.MagicMock()
        cm.__enter__.return_value.status = 200
        with mock.patch("send_line.urllib.request.urlopen", return_value=cm) as up:
            send_line.broadcast_message(self._msg(), "tok", timeout=7)
        _, kwargs = up.call_args
        self.assertEqual(kwargs.get("timeout"), 7)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state = Path(self.tmp.name) / "memory" / "heartbeat-state.json"

    def test_creates_and_preserves(self):
        self.state.parent.mkdir(parents=True)
        self.state.write_text(json.dumps({"keep": 1}), encoding="utf-8")
        send_line.update_heartbeat(self.state, "2026-06-29")
        data = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(data["5pm_pipeline_date"], "2026-06-29")
        self.assertEqual(data["keep"], 1)
        self.assertIn("lastChecks", data)

    def test_uses_atomic_replace(self):
        self.state.parent.mkdir(parents=True)
        with mock.patch("send_line.os.replace", wraps=os.replace) as rep:
            send_line.update_heartbeat(self.state, "2026-06-29")
        rep.assert_called_once()

    def test_recovers_from_corrupt(self):
        self.state.parent.mkdir(parents=True)
        self.state.write_bytes(b"\xff\xfe\x00bad")
        send_line.update_heartbeat(self.state, "2026-06-29")
        self.assertEqual(json.loads(self.state.read_text(encoding="utf-8"))["5pm_pipeline_date"], "2026-06-29")


class MainFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.json_path = base / "selected_articles.json"
        self.state = base / "memory" / "state.json"
        self.yt = base / "yt.txt"
        for attr, val in [("INPUT_JSON", self.json_path), ("STATE_FILE", self.state), ("YOUTUBE_URL_FILE", self.yt)]:
            p = mock.patch.object(send_line, attr, val)
            p.start()
            self.addCleanup(p.stop)
        os.environ.pop("DRY_RUN", None)

    def _valid(self):
        self.json_path.write_text(json.dumps({"selected": [{"title": "A"}]}), encoding="utf-8")

    def test_dry_run_no_broadcast_no_state(self):
        self._valid()
        with mock.patch.object(send_line, "broadcast_message", side_effect=AssertionError("不該被呼叫")):
            self.assertEqual(send_line.main(["--dry-run"]), 0)
        self.assertFalse(self.state.exists())

    def test_fail_closed_missing_data(self):
        with self.assertRaises(SystemExit):
            send_line.main([])

    def test_success_writes_state_after_send(self):
        self._valid()
        with mock.patch.object(send_line, "broadcast_message") as bm, \
             mock.patch.object(send_line, "get_line_token", return_value="tok"):
            self.assertEqual(send_line.main([]), 0)
        bm.assert_called_once()
        self.assertTrue(self.state.exists())

    def test_failed_send_no_state(self):
        self._valid()
        with mock.patch.object(send_line, "broadcast_message", side_effect=RuntimeError("boom")), \
             mock.patch.object(send_line, "get_line_token", return_value="tok"):
            with self.assertRaises(RuntimeError):
                send_line.main([])
        self.assertFalse(self.state.exists())

    def test_heartbeat_failure_returns_2(self):
        self._valid()
        with mock.patch.object(send_line, "broadcast_message"), \
             mock.patch.object(send_line, "get_line_token", return_value="tok"), \
             mock.patch.object(send_line, "update_heartbeat", side_effect=OSError("disk")):
            self.assertEqual(send_line.main([]), 2)


class TodayStrTests(unittest.TestCase):
    def test_format(self):
        self.assertRegex(send_line.today_str(), r"^\d{4}-\d{2}-\d{2}$")

    def test_honors_taipei_tz(self):
        fixed = _RealDateTime(2026, 6, 28, 16, 30, tzinfo=_tz.utc)  # = 台北 06-29 00:30

        class _FakeDT:
            @staticmethod
            def now(tz=None):
                return fixed.astimezone(tz) if tz is not None else fixed

        with mock.patch.object(send_line, "datetime", _FakeDT):
            self.assertEqual(send_line.today_str(), "2026-06-29")


class TokenTests(unittest.TestCase):
    def test_missing_raises(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                send_line.get_line_token()

    def test_blank_raises(self):
        with mock.patch.dict(os.environ, {"LINE_CHANNEL_ACCESS_TOKEN": "  \n"}):
            with self.assertRaises(SystemExit):
                send_line.get_line_token()

    def test_strips(self):
        with mock.patch.dict(os.environ, {"LINE_CHANNEL_ACCESS_TOKEN": "  abc\n"}):
            self.assertEqual(send_line.get_line_token(), "abc")


class TruthyTests(unittest.TestCase):
    def test_truthy(self):
        for v in ["1", "true", "TRUE", "Yes", "on"]:
            self.assertTrue(send_line._truthy(v), v)

    def test_falsy(self):
        for v in ["", "0", "no", "off", "x", None]:
            self.assertFalse(send_line._truthy(v), repr(v))


if __name__ == "__main__":
    unittest.main(verbosity=2)
