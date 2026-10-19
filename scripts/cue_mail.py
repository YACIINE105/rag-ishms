"""Send project queries to Cue through Gmail and read the bot's replies."""

import argparse
import getpass
import imaplib
import json
import mimetypes
import os
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate, getaddresses, make_msgid
from html.parser import HTMLParser
from pathlib import Path

GMAIL_ADDRESS = "v2ray121@gmail.com"
BOT_ADDRESS = "slave-7qx7@bot.cue.im"
PASSWORD_NAME = "CUE_GMAIL_APP_PASSWORD"
PASSWORD_FILE = Path(__file__).resolve().parents[1] / ".env.cue-mail"
HISTORY_FILE = Path(__file__).resolve().parents[1] / "reports/cue-mail/history.jsonl"


def load_history():
    if not HISTORY_FILE.exists():
        return []
    return [
        json.loads(line)
        for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def append_history(event):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    HISTORY_FILE.parent.chmod(0o700)
    record = {"recorded_at": datetime.now(timezone.utc).isoformat(), **event}
    descriptor = os.open(HISTORY_FILE, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as history:
        os.fchmod(history.fileno(), 0o600)
        history.write(json.dumps(record, ensure_ascii=False) + "\n")


def record_outcome(event):
    try:
        append_history(event)
    except OSError:
        print(
            "Mail action finished, but its outcome could not be saved to history.",
            file=sys.stderr,
        )


def remember_replies(replies):
    seen = {
        (event["uid"], event["message_id"])
        for event in load_history()
        if event.get("direction") == "incoming"
    }
    for reply in replies:
        key = (reply["uid"], reply["message_id"])
        if key not in seen:
            append_history({"direction": "incoming", "from": BOT_ADDRESS, **reply})
            seen.add(key)


def normalize_password(value):
    password = "".join(value.split())
    if len(password) != 16 or not password.isascii() or not password.isalnum():
        raise ValueError(
            "Use the 16-character Gmail app password, not your login password."
        )
    return password


def load_password():
    password = os.environ.get(PASSWORD_NAME)
    if not password and PASSWORD_FILE.exists():
        for line in PASSWORD_FILE.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == PASSWORD_NAME:
                password = value.strip()
                break
    if not password:
        raise ValueError(
            "Gmail is not configured. Run: python3 scripts/cue_mail.py setup"
        )
    return normalize_password(password)


def setup_password():
    password = normalize_password(
        getpass.getpass(f"Gmail app password for {GMAIL_ADDRESS}: ")
    )
    descriptor = os.open(PASSWORD_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as config:
        os.fchmod(config.fileno(), 0o600)
        config.write(f"{PASSWORD_NAME}={password}\n")
    print(f"Saved private Gmail configuration to {PASSWORD_FILE}. No email was sent.")


def build_message(subject, text, attachments, in_reply_to=None):
    if not subject.strip() or not text.strip():
        raise ValueError("The subject and query must not be blank.")
    message = EmailMessage()
    message["From"] = GMAIL_ADDRESS
    message["To"] = BOT_ADDRESS
    message["Reply-To"] = GMAIL_ADDRESS
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False)
    message["Message-ID"] = make_msgid(domain="gmail.com")
    if in_reply_to:
        message["In-Reply-To"] = in_reply_to
        message["References"] = in_reply_to
    message.set_content(text)
    for path in attachments:
        content_type, encoding = mimetypes.guess_type(path.name)
        if not content_type or encoding:
            content_type = "application/octet-stream"
        maintype, subtype = content_type.split("/", 1)
        message.add_attachment(
            path.read_bytes(), maintype=maintype, subtype=subtype, filename=path.name
        )
    return message


def send_message(message, password):
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as connection:
        connection.ehlo()
        connection.starttls(context=ssl.create_default_context())
        connection.ehlo()
        connection.login(GMAIL_ADDRESS, password)
        refused = connection.send_message(
            message, from_addr=GMAIL_ADDRESS, to_addrs=[BOT_ADDRESS]
        )
        if refused:
            raise ValueError(
                "Gmail refused the Cue recipient. No successful send was confirmed."
            )


class PlainTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in {"br", "p", "div", "li"}:
            self.parts.append("\n")


def reply_body(message):
    part = message.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    text = part.get_content()
    if part.get_content_type() == "text/html":
        parser = PlainTextParser()
        parser.feed(text)
        text = "".join(parser.parts)
    return text.strip()


def read_replies(password, limit, after_uid=0, oldest_first=False):
    replies = []
    with imaplib.IMAP4_SSL(
        "imap.gmail.com", 993, ssl_context=ssl.create_default_context(), timeout=30
    ) as connection:
        connection.login(GMAIL_ADDRESS, password)
        status, _ = connection.select("INBOX", readonly=True)
        if status != "OK":
            raise ValueError("Gmail inbox could not be opened.")
        status, data = connection.uid("search", None, "FROM", f'"{BOT_ADDRESS}"')
        if status != "OK":
            raise ValueError("Gmail could not search for Cue replies.")
        identifiers = sorted(
            int(uid) for uid in data[0].split() if int(uid) > after_uid
        )
        ordered = identifiers if oldest_first else reversed(identifiers)
        for identifier in ordered:
            status, fetched = connection.uid("fetch", str(identifier), "(BODY.PEEK[])")
            if status != "OK":
                raise ValueError(f"Gmail could not read Cue reply UID {identifier}.")
            payload = next(
                (item[1] for item in fetched if isinstance(item, tuple)), None
            )
            if payload is None:
                raise ValueError(
                    f"Gmail returned no content for Cue reply UID {identifier}."
                )
            message = BytesParser(policy=policy.default).parsebytes(payload)
            addresses = getaddresses(message.get_all("From", []))
            if len(addresses) != 1 or addresses[0][1].lower() != BOT_ADDRESS:
                continue
            replies.append(
                {
                    "uid": identifier,
                    "message_id": str(message.get("Message-ID", "")),
                    "in_reply_to": str(message.get("In-Reply-To", "")),
                    "date": str(message.get("Date", "")),
                    "subject": str(message.get("Subject", "")),
                    "body": reply_body(message),
                    "attachments": [
                        part.get_filename() for part in message.iter_attachments()
                    ],
                }
            )
            if len(replies) == limit:
                break
    return replies if oldest_first else list(reversed(replies))


def positive_integer(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Use a positive integer.")
    return number


def nonnegative_integer(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError("UID must not be negative.")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="Save a Gmail app password using a hidden prompt")
    send = commands.add_parser("send", help="Send one query to the configured Cue bot")
    send.add_argument("--subject", default="[RAG-ISHMS] Query")
    body = send.add_mutually_exclusive_group(required=True)
    body.add_argument("--text", help="Query text")
    body.add_argument("--body-file", help="UTF-8 query file, or - to read stdin")
    send.add_argument("--attach", type=Path, action="append", default=[])
    send.add_argument(
        "--in-reply-to", help="Message-ID of the bot email being answered"
    )
    send.add_argument(
        "--dry-run", action="store_true", help="Preview without signing in or sending"
    )
    replies = commands.add_parser(
        "replies", help="Read Cue replies without marking them read"
    )
    replies.add_argument("--limit", type=positive_integer, default=5)
    replies.add_argument("--after-uid", type=nonnegative_integer, default=0)
    history = commands.add_parser(
        "history", help="Read local mail memory without connecting"
    )
    history.add_argument("--limit", type=positive_integer, default=20)
    args = parser.parse_args(argv)
    try:
        if args.command == "setup":
            setup_password()
        elif args.command == "send":
            if args.body_file == "-":
                text = sys.stdin.read()
            elif args.body_file:
                text = Path(args.body_file).read_text(encoding="utf-8")
            else:
                text = args.text
            message = build_message(args.subject, text, args.attach, args.in_reply_to)
            if args.dry_run:
                result = {
                    "status": "preview",
                    "from": GMAIL_ADDRESS,
                    "to": BOT_ADDRESS,
                    "subject": args.subject,
                    "body": text,
                    "attachments": [path.name for path in args.attach],
                }
            else:
                password = load_password()
                event = {
                    "direction": "outgoing",
                    "from": GMAIL_ADDRESS,
                    "to": BOT_ADDRESS,
                    "message_id": str(message["Message-ID"]),
                    "in_reply_to": args.in_reply_to,
                    "subject": args.subject,
                    "body": text,
                    "attachments": [str(path) for path in args.attach],
                    "authorization": "standing_user_authorization",
                }
                append_history({**event, "status": "attempting"})
                try:
                    send_message(message, password)
                except (OSError, ValueError, smtplib.SMTPException) as error:
                    record_outcome(
                        {
                            **event,
                            "status": "unconfirmed",
                            "error_type": type(error).__name__,
                        }
                    )
                    raise
                record_outcome({**event, "status": "smtp_accepted"})
                result = {
                    "status": "smtp_accepted",
                    "to": BOT_ADDRESS,
                    "message_id": str(message["Message-ID"]),
                }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "replies":
            result = read_replies(load_password(), args.limit, args.after_uid)
            remember_replies(result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(
                json.dumps(load_history()[-args.limit :], ensure_ascii=False, indent=2)
            )
    except smtplib.SMTPAuthenticationError:
        parser.exit(
            1, "Gmail authentication failed. Check the account's app password.\n"
        )
    except smtplib.SMTPRecipientsRefused:
        parser.exit(
            1, "Gmail refused the Cue recipient. Check the bot's email address.\n"
        )
    except (OSError, ValueError, smtplib.SMTPException, imaplib.IMAP4.error) as error:
        parser.exit(1, f"Cue mail failed: {error}\n")


if __name__ == "__main__":
    main()
