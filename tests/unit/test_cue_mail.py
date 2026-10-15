import importlib.util
import io
import json
import os
import smtplib
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/cue_mail.py"
SPEC = importlib.util.spec_from_file_location("cue_mail", SCRIPT)
cue_mail = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cue_mail)
PASSWORD = "abcdefghijklmnop"


class CueMailTests(unittest.TestCase):
    def test_utf8_message_and_attachment_preserve_content_and_thread(self):
        with tempfile.TemporaryDirectory() as directory:
            attachment = Path(directory) / "results.zip"
            attachment.write_bytes(b"saved experiment")
            message = cue_mail.build_message(
                "Legal evaluation", "راجع النتائج العربية", [attachment], "<bot-reply>"
            )
        self.assertEqual(message["From"], cue_mail.GMAIL_ADDRESS)
        self.assertEqual(message["To"], cue_mail.BOT_ADDRESS)
        self.assertEqual(message["Reply-To"], cue_mail.GMAIL_ADDRESS)
        self.assertEqual(message["In-Reply-To"], "<bot-reply>")
        self.assertEqual(message["References"], "<bot-reply>")
        self.assertEqual(
            message.get_body().get_content().strip(), "راجع النتائج العربية"
        )
        attached = list(message.iter_attachments())
        self.assertEqual(attached[0].get_filename(), "results.zip")
        self.assertEqual(attached[0].get_payload(decode=True), b"saved experiment")

    def test_send_authenticates_over_tls_before_sending_to_only_the_bot(self):
        message = cue_mail.build_message("Status", "Please report status.", [])
        with patch.object(cue_mail.smtplib, "SMTP") as smtp:
            connection = smtp.return_value.__enter__.return_value
            connection.send_message.return_value = {}
            cue_mail.send_message(message, PASSWORD)
        smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=30)
        self.assertEqual(
            [call[0] for call in connection.method_calls],
            ["ehlo", "starttls", "ehlo", "login", "send_message"],
        )
        connection.login.assert_called_once_with(cue_mail.GMAIL_ADDRESS, PASSWORD)
        connection.send_message.assert_called_once_with(
            message, from_addr=cue_mail.GMAIL_ADDRESS, to_addrs=[cue_mail.BOT_ADDRESS]
        )

    def test_failed_authentication_does_not_send(self):
        message = cue_mail.build_message("Status", "Please report status.", [])
        with patch.object(cue_mail.smtplib, "SMTP") as smtp:
            connection = smtp.return_value.__enter__.return_value
            connection.login.side_effect = smtplib.SMTPAuthenticationError(
                535, b"Denied"
            )
            with self.assertRaises(smtplib.SMTPAuthenticationError):
                cue_mail.send_message(message, PASSWORD)
            connection.send_message.assert_not_called()

    def test_replies_are_read_only_and_filter_exact_sender_and_uid(self):
        reply = EmailMessage()
        reply["From"] = cue_mail.BOT_ADDRESS
        reply["Subject"] = "Experiment finished"
        reply["In-Reply-To"] = "<our-query>"
        reply.set_content("<p>Saved results</p>", subtype="html")
        reply.add_attachment(
            b"{}", maintype="application", subtype="json", filename="metrics.json"
        )
        other = EmailMessage()
        other["From"] = f"unrelated-{cue_mail.BOT_ADDRESS}"
        other.set_content("Different sender")

        def command(name, *args):
            if name == "search":
                self.assertEqual(args, (None, "FROM", f'"{cue_mail.BOT_ADDRESS}"'))
                return "OK", [b"1 2 3"]
            self.assertEqual(args[1], "(BODY.PEEK[])")
            message = other if args[0] == "3" else reply
            return "OK", [(b"message", message.as_bytes()), b")"]

        with patch.object(cue_mail.imaplib, "IMAP4_SSL") as imap:
            connection = imap.return_value.__enter__.return_value
            connection.select.return_value = "OK", [b"3"]
            connection.uid.side_effect = command
            result = cue_mail.read_replies(PASSWORD, limit=1, after_uid=1)
        connection.select.assert_called_once_with("INBOX", readonly=True)
        connection.login.assert_called_once_with(cue_mail.GMAIL_ADDRESS, PASSWORD)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["uid"], 2)
        self.assertEqual(result[0]["body"], "Saved results")
        self.assertEqual(result[0]["in_reply_to"], "<our-query>")
        self.assertEqual(result[0]["attachments"], ["metrics.json"])

    def test_empty_inbox_returns_no_replies(self):
        with patch.object(cue_mail.imaplib, "IMAP4_SSL") as imap:
            connection = imap.return_value.__enter__.return_value
            connection.select.return_value = "OK", [b"0"]
            connection.uid.return_value = "OK", [b""]
            self.assertEqual(cue_mail.read_replies(PASSWORD, limit=5), [])
            self.assertEqual(connection.uid.call_count, 1)

    def test_oldest_first_preserves_unprocessed_replies_in_a_backlog(self):
        reply = EmailMessage()
        reply["From"] = cue_mail.BOT_ADDRESS
        reply.set_content("Status")

        def command(name, *args):
            if name == "search":
                return "OK", [b"10 11 12"]
            return "OK", [(b"message", reply.as_bytes()), b")"]

        with patch.object(cue_mail.imaplib, "IMAP4_SSL") as imap:
            connection = imap.return_value.__enter__.return_value
            connection.select.return_value = "OK", [b"3"]
            connection.uid.side_effect = command
            result = cue_mail.read_replies(PASSWORD, limit=1, oldest_first=True)
        self.assertEqual(result[0]["uid"], 10)

    def test_setup_keeps_password_private_and_environment_takes_precedence(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / ".env.cue-mail"
            with patch.object(cue_mail, "PASSWORD_FILE", config):
                with patch.object(
                    cue_mail.getpass, "getpass", return_value="abcd efgh ijkl mnop"
                ):
                    with redirect_stdout(output):
                        cue_mail.setup_password()
                self.assertEqual(config.stat().st_mode & 0o777, 0o600)
                with patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(cue_mail.load_password(), PASSWORD)
                with patch.dict(
                    os.environ, {cue_mail.PASSWORD_NAME: "ponmlkjihgfedcba"}
                ):
                    self.assertEqual(cue_mail.load_password(), "ponmlkjihgfedcba")
        self.assertNotIn(PASSWORD, output.getvalue())

    def test_dry_run_never_loads_credentials_or_connects(self):
        output = io.StringIO()
        with patch.object(cue_mail, "load_password") as password:
            with patch.object(cue_mail.smtplib, "SMTP") as smtp:
                with patch.object(cue_mail, "append_history") as history:
                    with redirect_stdout(output):
                        cue_mail.main(
                            ["send", "--text", "Please report status.", "--dry-run"]
                        )
                    history.assert_not_called()
        password.assert_not_called()
        smtp.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"], "preview")

    def test_missing_credentials_fail_before_a_connection(self):
        error_output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(cue_mail, "PASSWORD_FILE", Path(directory) / "missing"):
                with patch.dict(os.environ, {}, clear=True):
                    with patch.object(cue_mail.smtplib, "SMTP") as smtp:
                        with (
                            redirect_stderr(error_output),
                            self.assertRaises(SystemExit) as error,
                        ):
                            cue_mail.main(
                                [
                                    "send",
                                    "--text",
                                    "Please report status.",
                                ]
                            )
                        smtp.assert_not_called()
        self.assertEqual(error.exception.code, 1)
        self.assertIn("Gmail is not configured", error_output.getvalue())

    def test_successful_query_is_recorded_without_credentials(self):
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "private/history.jsonl"
            with patch.object(cue_mail, "HISTORY_FILE", history):
                with patch.object(cue_mail, "load_password", return_value=PASSWORD):
                    with patch.object(cue_mail, "send_message") as send:
                        with redirect_stdout(output):
                            cue_mail.main(
                                [
                                    "send",
                                    "--text",
                                    "Please report status.",
                                ]
                            )
                    records = cue_mail.load_history()
            self.assertEqual(history.stat().st_mode & 0o777, 0o600)
            self.assertEqual(history.parent.stat().st_mode & 0o777, 0o700)
            self.assertNotIn(PASSWORD, history.read_text(encoding="utf-8"))
        send.assert_called_once()
        self.assertEqual(
            [record["status"] for record in records], ["attempting", "smtp_accepted"]
        )
        self.assertEqual(records[1]["body"], "Please report status.")
        self.assertEqual(records[1]["authorization"], "standing_user_authorization")
        self.assertEqual(
            records[1]["message_id"], json.loads(output.getvalue())["message_id"]
        )

    def test_failed_send_preserves_an_unconfirmed_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            history = Path(directory) / "history.jsonl"
            with patch.object(cue_mail, "HISTORY_FILE", history):
                with patch.object(cue_mail, "load_password", return_value=PASSWORD):
                    with patch.object(
                        cue_mail, "send_message", side_effect=TimeoutError
                    ):
                        with (
                            redirect_stderr(io.StringIO()),
                            self.assertRaises(SystemExit),
                        ):
                            cue_mail.main(
                                [
                                    "send",
                                    "--text",
                                    "Please report status.",
                                ]
                            )
                records = cue_mail.load_history()
        self.assertEqual(records[-1]["status"], "unconfirmed")
        self.assertEqual(records[-1]["error_type"], "TimeoutError")
        self.assertNotIn("smtp_accepted", [record["status"] for record in records])

    def test_repeated_reply_reads_do_not_duplicate_memory(self):
        reply = {"uid": 12, "message_id": "<reply-12>", "body": "Evaluation finished."}
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(
                cue_mail, "HISTORY_FILE", Path(directory) / "history.jsonl"
            ):
                cue_mail.remember_replies([reply])
                cue_mail.remember_replies([reply])
                records = cue_mail.load_history()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["direction"], "incoming")
        self.assertEqual(records[0]["body"], reply["body"])

    def test_local_memory_can_be_read_without_authentication(self):
        output = io.StringIO()
        with patch.object(
            cue_mail, "load_history", return_value=[{"uid": 1}, {"uid": 2}]
        ):
            with patch.object(cue_mail, "load_password") as password:
                with redirect_stdout(output):
                    cue_mail.main(["history", "--limit", "1"])
        password.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), [{"uid": 2}])


if __name__ == "__main__":
    unittest.main()
