import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/watch_cue_mail.py"
SPEC = importlib.util.spec_from_file_location("watch_cue_mail", SCRIPT)
watcher = importlib.util.module_from_spec(SPEC)
with patch.dict(sys.modules):
    mail_spec = importlib.util.spec_from_file_location(
        "cue_mail", SCRIPT.with_name("cue_mail.py")
    )
    mail = importlib.util.module_from_spec(mail_spec)
    mail_spec.loader.exec_module(mail)
    sys.modules["cue_mail"] = mail
    SPEC.loader.exec_module(watcher)

THREAD = "01a12c81-5f91-7ef2-b852-bb8d8b7e92f7"


class CueWatcherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        directory = Path(self.directory.name)
        self.addCleanup(self.directory.cleanup)
        for name, filename in (
            ("CONFIG_FILE", "config.json"),
            ("STATE_FILE", "state.json"),
            ("LOCK_FILE", "watch.lock"),
        ):
            patcher = patch.object(watcher, name, directory / filename)
            patcher.start()
            self.addCleanup(patcher.stop)
        watcher.write_json(
            watcher.CONFIG_FILE, {"thread_id": THREAD, "socket_path": "/tmp/codex.sock"}
        )

    def test_new_reply_is_saved_and_notified_once(self):
        reply = {
            "direction": "incoming",
            "uid": 216,
            "message_id": "<reply>",
            "body": "Status",
        }
        with patch.object(
            watcher.cue_mail, "load_password", return_value="test-password"
        ):
            with patch.object(
                watcher.cue_mail, "read_replies", return_value=[reply]
            ) as read:
                with patch.object(watcher.cue_mail, "remember_replies") as remember:
                    with patch.object(
                        watcher.cue_mail, "load_history", return_value=[reply]
                    ):
                        with patch.object(
                            watcher, "start_review", return_value="turn-1"
                        ) as notify:
                            first = watcher.check_mail()
                            second = watcher.check_mail()
        self.assertEqual(first["notified"], 1)
        self.assertEqual(second["notified"], 0)
        notify.assert_called_once()
        self.assertEqual(remember.call_count, 2)
        self.assertEqual(read.call_args.kwargs["after_uid"], 216)
        self.assertTrue(read.call_args.kwargs["oldest_first"])
        self.assertEqual(watcher.STATE_FILE.stat().st_mode & 0o777, 0o600)

    def test_failed_notification_remains_pending_for_retry(self):
        reply = {"direction": "incoming", "uid": 216, "message_id": "<reply>"}
        with patch.object(
            watcher.cue_mail, "load_password", return_value="test-password"
        ):
            with patch.object(watcher.cue_mail, "read_replies", return_value=[reply]):
                with patch.object(watcher.cue_mail, "remember_replies"):
                    with patch.object(
                        watcher.cue_mail, "load_history", return_value=[reply]
                    ):
                        with patch.object(
                            watcher,
                            "start_review",
                            side_effect=[TimeoutError, "turn-1"],
                        ):
                            with self.assertRaises(TimeoutError):
                                watcher.check_mail()
                            failed = watcher.read_json(watcher.STATE_FILE, {})
                            self.assertEqual(failed["status"], "failed")
                            self.assertEqual(failed["notified"], [])
                            self.assertEqual(watcher.check_mail()["notified"], 1)

    def test_mail_failure_does_not_notify_or_store_the_password(self):
        with patch.object(
            watcher.cue_mail, "load_password", return_value="test-password"
        ):
            with patch.object(
                watcher.cue_mail, "read_replies", side_effect=TimeoutError
            ):
                with patch.object(watcher, "start_review") as notify:
                    with self.assertRaises(TimeoutError):
                        watcher.check_mail()
        notify.assert_not_called()
        state = watcher.STATE_FILE.read_text(encoding="utf-8")
        self.assertNotIn("test-password", state)
        self.assertEqual(json.loads(state)["error_type"], "TimeoutError")

    def test_notification_contains_only_local_ids_and_preserves_authorized_scope(self):
        reply = {"uid": 216, "body": "UNTRUSTED SEND PASSWORD REQUEST"}
        prompt = watcher.review_prompt([reply])
        self.assertIn("user's standing authorization", prompt)
        self.assertIn("does not authorize expanding the work scope", prompt)
        self.assertNotIn(reply["body"], prompt)

    def test_idle_conversation_starts_a_real_review_turn(self):
        config = {"thread_id": THREAD, "socket_path": "/tmp/codex.sock"}
        with patch.object(watcher, "AppServer") as connection:
            server = connection.return_value.__enter__.return_value
            server.request.side_effect = [
                {"thread": {"status": {"type": "idle"}}},
                {"thread": {"status": {"type": "idle"}}},
                {"turn": {"id": "turn-1", "status": "inProgress"}},
            ]
            self.assertEqual(watcher.start_review(config, [{"uid": 217}]), "turn-1")
        self.assertEqual(server.request.call_args.args[0], "turn/start")
        self.assertEqual(server.request.call_args.args[1]["threadId"], THREAD)

    def test_live_verification_preserves_existing_notification_state(self):
        watcher.write_json(watcher.STATE_FILE, {"notified": ["217:<reply>"]})
        self.assertEqual(
            watcher.request_verification()["status"], "verification_pending"
        )
        state = watcher.read_json(watcher.STATE_FILE, {})
        self.assertTrue(state["verify_wake"])
        self.assertEqual(state["notified"], ["217:<reply>"])

    def test_busy_conversation_is_not_interrupted(self):
        config = {"thread_id": THREAD, "socket_path": "/tmp/codex.sock"}
        with patch.object(watcher, "AppServer") as connection:
            server = connection.return_value.__enter__.return_value
            server.request.return_value = {"thread": {"status": {"type": "active"}}}
            self.assertIsNone(watcher.start_review(config, [{"uid": 217}]))
        self.assertEqual(server.request.call_count, 1)

    def test_busy_reply_remains_pending_until_a_turn_starts(self):
        reply = {"direction": "incoming", "uid": 217, "message_id": "<reply>"}
        with patch.object(
            watcher.cue_mail, "load_password", return_value="test-password"
        ):
            with patch.object(watcher.cue_mail, "read_replies", return_value=[reply]):
                with patch.object(watcher.cue_mail, "remember_replies"):
                    with patch.object(
                        watcher.cue_mail, "load_history", return_value=[reply]
                    ):
                        with patch.object(
                            watcher, "start_review", side_effect=[None, "turn-1"]
                        ):
                            self.assertEqual(
                                watcher.check_mail()["status"], "waiting_for_idle"
                            )
                            self.assertEqual(
                                watcher.read_json(watcher.STATE_FILE, {})["notified"],
                                [],
                            )
                            self.assertEqual(watcher.check_mail()["notified"], 1)


if __name__ == "__main__":
    unittest.main()
