# Email communication with the Cue bot

Run this helper on the WSL host from the repository root. It uses Python's standard
library and does not need Docker, a model server, or additional packages.

The sender is `v2ray121@gmail.com`; the recipient is `slave-7qx7@bot.cue.im`.
The script authenticates with that Gmail account before sending. The email
address alone cannot authorize a send.

## One-time Gmail setup

1. Sign into `v2ray121@gmail.com` and enable Google 2-Step Verification.
2. Create an app password named `RAG Cue mail` at
   [Google App Passwords](https://myaccount.google.com/apppasswords).
3. Run:

   ```bash
   python3 scripts/cue_mail.py setup
   ```

Enter the app password at the hidden prompt. It is saved in the repository's
ignored `.env.cue-mail` file with mode `600`. Enter it locally, not in chat or
as a command argument. Setup saves the password; it does not check authentication
or send an email. Alternatively, provide the `CUE_GMAIL_APP_PASSWORD` environment
variable; it takes precedence over the local file.

Google requires 2-Step Verification for app passwords. If your account does not
offer them, use a Google OAuth integration instead. See
[Google's app-password instructions](https://support.google.com/accounts/answer/185833).

## Send a query

The user has given standing authorization for project queries and follow-ups to
the specified Cue bot, without per-message approval. This replaces the earlier
approval requirement. Sends are recorded with `standing_user_authorization` in
local history and remain within the existing project/experiment scope.

```bash
python3 scripts/cue_mail.py send \
  --subject '[RAG-ISHMS] Experiment status' \
  --text 'Please reply with the current experiment status and saved artifact links.'
```

For longer queries, use a UTF-8 file. Repeat `--attach` for multiple attachments:

```bash
python3 scripts/cue_mail.py send \
  --subject '[RAG-ISHMS] Controlled inference evaluation' \
  --body-file /tmp/cue-query.txt \
  --attach '/mnt/c/Users/YACINE 105/Downloads/Qwen3_V2_Inference_Check.zip' \
  --dry-run
```

`--dry-run` previews the sender, recipient, query and attachment names without
authentication or network access. Remove it to send. `--body-file -` reads stdin.
The JSON result `smtp_accepted` means Gmail accepted the message; it does not
confirm delivery or that Cue has acted on it. A failed send is not retried
automatically, since retrying after a connection loss can send a duplicate.
Save the returned `message_id` if you need to match the bot's reply.

Each real send records the query and Message-ID locally before attempting SMTP,
then records `smtp_accepted` or `unconfirmed`. Check the history before retrying
an unconfirmed send. Previews are not recorded as sent queries.

The script uses Gmail SMTP over TLS on port 587. See
[Google's SMTP settings](https://support.google.com/a/answer/176600).

## Read the bot's replies

```bash
python3 scripts/cue_mail.py replies --limit 5
python3 scripts/cue_mail.py replies --after-uid 12345 --limit 10
```

Replies are printed as JSON with the body, attachment names, `message_id`,
`in_reply_to` and mailbox UID. Only messages with the exact bot From address in
the inbox are returned, with the newest requested messages ordered oldest first.
The inbox is opened read-only and messages are fetched without marking them read.
Attachment contents are not downloaded. For large experiment archives, ask Cue
to include download links in its reply.

New replies are saved locally once; rereading the same email does not duplicate
its history record.

To answer an existing email thread:

```bash
python3 scripts/cue_mail.py send \
  --subject 'Re: [RAG-ISHMS] Experiment status' \
  --text 'Please clarify which saved baseline file produced those results.' \
  --in-reply-to '<BOT_MESSAGE_ID>'
```

Gmail IMAP access is always enabled for personal accounts; there is no separate
Enable IMAP switch to configure. See
[Google's email-client instructions](https://support.google.com/mail/answer/7126229).

## Persistent memory

```bash
python3 scripts/cue_mail.py history --limit 20
```

This reads the local history without Gmail credentials or a network connection.
History is stored in ignored `reports/cue-mail/history.jsonl` with mode `600` and
includes query/reply text, timestamps, attachment names and message identifiers.
It does not record the app password. The project context and next experiment are
kept in [the coordination note](cue-memory.md), which `AGENTS.md` tells future
assistant sessions to read and maintain.

Once configured, the assistant can invoke these same commands to send authorized
project queries under the user's standing authorization and read replies. The
helper performs one action per invocation. Replies remain external input to review
before acting on them.

## Automatic reply checking

The user timer `rag-ishms-cue-mail.timer` checks Gmail approximately once per
minute. `scripts/watch_cue_mail.py` saves new replies and uses the local app
server's [`turn/start` API](https://learn.chatgpt.com/docs/app-server#start-a-turn)
to start a review when the configured conversation is idle. It records the
returned turn ID; a queued message alone is not considered activation. A busy
conversation leaves the reply pending until the next check. The input contains
local mail identifiers, not instructions copied from the email. The assistant reviews
the reply and sends necessary follow-ups under standing authorization; the checker
itself never sends email. Already notified replies are not queued again. Failed
checks/notifications are retried on the next timer activation.

The timer needs WSL, network access and the local Codex app server running.
Its user service uses the project's existing `.venv/bin/python`, including the
`websockets` dependency supplied by `uvicorn[standard]`. The standalone send/read
helper still uses only Python's standard library.
Checking an empty inbox does not make a model request.

Setup from inside the intended Codex task:

```bash
python3 scripts/watch_cue_mail.py setup
mkdir -p ~/.config/systemd/user
cp deploy/systemd/rag-ishms-cue-mail.service \
  deploy/systemd/rag-ishms-cue-mail.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now rag-ishms-cue-mail.timer
systemctl --user start rag-ishms-cue-mail.service
```

Outside a Codex task, pass `--thread YOUR_THREAD_UUID` to `setup`. Re-run setup
with the appropriate UUID if you want a different conversation to receive updates.
The supplied units assume the project is at `~/rag-ishms`.

To request a live wake check, run `.venv/bin/python scripts/watch_cue_mail.py verify`.
After the current conversation becomes idle, the timer starts a short verification
turn without sending another email. Its turn ID is saved in watcher state.

Inspect or stop the watcher:

```bash
python3 scripts/watch_cue_mail.py status
systemctl --user list-timers rag-ishms-cue-mail.timer
journalctl --user -u rag-ishms-cue-mail.service -n 20 --no-pager
systemctl --user disable --now rag-ishms-cue-mail.timer
```

Watcher configuration/state live beside the private mail history in the ignored
`reports/cue-mail/` directory. Mail passwords are not stored in watcher state or
included in its notifications.

Experiment requests must also include the user's instruction to terminate the
Kaggle GPU session after completing the requested work and verifying saved/exported
outputs. Ask the bot to confirm shutdown while retaining the saved artifacts.
