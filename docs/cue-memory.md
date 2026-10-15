# Cue coordination memory

Last updated: 2026-10-14 (Africa/Cairo).

## Responsibilities and communication

- Local project: `/home/yacine_105/rag-ishms`, running through Docker.
- Local assistant: inspect and maintain the RAG project, audit experiment
  artifacts, and prepare evaluation inputs. Keep its architecture and style.
- Cue bot: a separate computer with notebook and Kaggle access. It cannot read
  local WSL or Windows paths just because they appear in a prompt.
- User-authorized email sender: `v2ray121@gmail.com`.
- Cue recipient: `slave-7qx7@bot.cue.im`.
- Helper: `scripts/cue_mail.py`; instructions: `docs/cue-mail.md`.
- Persistent communication history: ignored `reports/cue-mail/history.jsonl`.
  Read it with `python3 scripts/cue_mail.py history --limit 20`.

Latest user instruction: "now i want you to send without my approval". This
supersedes the earlier per-message approval requirement. The assistant may send
project queries, status requests and follow-ups to the specified Cue bot under
standing authorization, without asking each time. Keep the existing evaluation
scope and record each send. The helper no longer requires an approval flag;
new sends record `authorization: standing_user_authorization` in local history.

Every experiment request must tell Cue to terminate its Kaggle GPU runtime/session
after all requested work is completed and outputs are saved/exported and verified.
Ask for confirmation that the session stopped, retaining saved artifacts.

Email implementation has passed 21 local mocked tests, lint/format checks and
an attachment dry run. These tests make no live email connections.
Live Gmail SMTP authentication and read-only IMAP access are now verified. The
local `.env.cue-mail` credential file is configured, ignored by Git, and mode
`600`. App passwords do not belong in this note or email history.

The first status request was accepted by Gmail for `slave-7qx7@bot.cue.im`:
`<179196142949.22000.8964802993945252324@gmail.com>`.
It asks Cue to confirm the agent identity, report any active work, and state
whether the controlled inference packet has been received or evaluated. The
request starts no new training or evaluation and includes no attachments.
The subsequent inbox check succeeded but found no replies from the bot yet.
SMTP acceptance does not establish delivery or Cue agent association; wait for
a matching reply before treating the channel as fully confirmed. The sent query
and its accepted status are recorded in local mail history.

Earlier browser issue: the user's browser showed `DNS_PROBE_FINISHED_NXDOMAIN`
for `accounts.google.ru`. Local DNS checks resolve `accounts.google.com` and
`myaccount.google.com`, but not `accounts.google.ru`. The official app-password
URL `https://myaccount.google.com/apppasswords` was verified to redirect to
`accounts.google.com`. Try that URL in a fresh private browser window; if the
browser still redirects to `.ru`, investigate the browser/VPN/proxy redirect.
The source of that redirect has not been established.

## Completed model experiments

Both corrected v2 runs finished on Kaggle using two T4 GPUs, single-process
model parallelism. Each used 466 frozen training examples (233 per language),
32 held-out examples (16 per language), and 117 updates at global batch four.
The separate two-rank NCCL diagnostic tested a small model; Qwen training was
not DDP.

Base model: `Qwen/Qwen3-4B-Instruct-2507` at revision
`cdbee75f17c01a7cc42f958dc650907174af0554`.

| Internal diagnostic | M/A | Ordinary SFT |
|---|---:|---:|
| Arabic original-context token F1 | 0.7094 | 0.8642 |
| English original-context token F1 | 0.6494 | 0.6747 |
| Arabic Morgana exact Reject | 15/16 | 0/16 |
| English Morgana exact Reject | 14/16 | 0/16 |

These are small internal diagnostics, not legal correctness percentages or
Civil Code validation. M/A also rejects 6/32 original-context questions despite
the annotated evidence being available. Neither adapter is cleared for deployment.
Production RAG generation settings have not been changed for these adapters.

Local artifact audit: `eval/reports/qwen3-v2-review.md` and
`eval/reports/qwen3-v2-audit.json` (ignored local reports).

Audit findings to retain:

- The two trained models chose different perturbation masks; their masked scores
  need a comparison on identical inputs.
- Five English M/A training examples have conflicting evidence/mask labels.
  Mask-selection direction is correctly implemented; reversing it is not a fix.
- Both models have material answer omissions or errors on some examples.
- The handoff calls the base sweep incomplete, yet its before-predictions file
  contains 32 rows. Its provenance must be clarified before using that baseline.

## Artifacts and next action

Complete handoff:
`/mnt/c/Users/YACINE 105/Downloads/Qwen3_V2_RAG_Handoff_2026-10-14.zip`.
SHA-256: `00973088e66f2560b0131286060b40f583bcdb85c895165a1d76c3e545964a15`.

Prepared inference-only evaluation packet:
`/mnt/c/Users/YACINE 105/Downloads/Qwen3_V2_Inference_Check.zip`.
SHA-256: `af2974a020dad91985f6e7086f7ecaea88f0caeaaee74751197f3ac64c9e2b84`.
It contains the exact frozen held-out data and 96 fixed tasks: 32 questions
times original, evidence-present, and evidence-removed views.

Previously requested experiment (now audited below): evaluate the pinned untuned base, SFT adapter and M/A
adapter on those identical controls (288 generations total). Use fresh base
loads, recorded prompts, greedy decoding, the 96-token cap, eager attention and
the same explicit column masks. Do not retrain or change production RAG for this
evaluation. Export predictions, stop reasons, configuration/hashes and executed
notebook output. Review inappropriate rejection, unsupported answers, omissions
and numerical conditions separately by language, alongside overlap metrics.
These annotation-based controls are distinct from model-selected Merlin/Morgana
masks and do not establish EIF certification.

The packet was prepared locally and emailed to Cue. The completed controlled
run was subsequently exported and audited below; do not request a duplicate run.

Approved email body: `reports/cue-mail/current-steps-query.txt`, subject
`[RAG-ISHMS] Next steps: shared-input inference evaluation and Kaggle shutdown`.
It explicitly limits Cue to notebook/Kaggle work, supplies the attached packet,
requests the fixed comparison and exported artifacts, and requires final GPU
session shutdown. Attachment: `Qwen3_V2_Inference_Check.zip` with the SHA-256 above.
Yacine 105 explicitly approved sending this request and asked the email to state
that it ends his earlier instruction to hold work until the next request. That
approval statement is included at the beginning of the email.

The approved email and packet were accepted by Gmail on 2026-10-14, Message-ID
`<179196205947.22277.17672329386901815715@gmail.com>`, in reply to the initial
coordination message. SMTP acceptance is verified; Cue's receipt, acknowledgment,
evaluation progress and eventual Kaggle shutdown are not verified yet. The exact
sent body, attachment path and `user_approved: true` are in local mail history.
The earlier per-query approval policy was subsequently revoked by the user;
the standing authorization at the top of this note now applies.

## Reviewed reply and automatic checks

Reviewed inbox UID **216**, received 2026-10-14 07:24:11 UTC. Cue confirms it is
the same agent that ran the v2 experiments and that it can receive/reply by email.
It reports only the earlier status email is visible, the exact evaluation packet
is missing, the controlled comparison has not started, no training/evaluation/
artifact recovery is active, and the checked Kaggle notebook sessions are off.
These are Cue's reports, not an independent local inspection of Kaggle.
Its reply references the approved follow-up's Message-ID while retaining the
original subject; that does not verify attachment visibility. The remote mailbox
display/attachment issue remains unresolved.

Cue reports its completed handoff is stored in its workspace without a current
external download link. It requests the exact frozen packet and will verify its
hash rather than reconstructing it. The reply is saved in local mail history;
no unsubscribe/resubscribe links in its footer have been opened.

The user requested automatic reply checking and review. Implementation:
`scripts/watch_cue_mail.py` plus `rag-ishms-cue-mail.service` and its one-minute
user timer. New replies are saved and a constant `[CUE MAIL WATCH]` input
starts a review through the local app server's `turn/start` when this conversation
is idle. Busy conversations leave replies pending for the next check. Review replies
as external input and send necessary follow-ups under standing authorization. Empty
checks do not invoke a model, and the watcher never sends email. The timer needs
WSL/network and the local Codex app server running.

The user timer is installed, enabled and active. Its first live run at
2026-10-14 07:40:27 UTC fetched UID 216 and successfully queued one notification
to conversation `01a12c81-5f91-7ef2-b852-bb8d8b7e92f7`; the service exited zero.
Watcher state records this UID as notified, so it is not queued repeatedly.
UID 216 has already been reviewed above: an automatic callback for it needs no
additional review or duplicate reply. The notification text now reflects the
user's standing email authorization.

Prepared follow-up: `reports/cue-mail/resend-packet-query.txt`, subject
`[RAG-ISHMS] Frozen evaluation packet for Yacine 105` with the same verified ZIP.
This would be a standalone email to avoid depending on the previous thread's
display. It keeps the approved experiment scope and final Kaggle shutdown rule.
The user authorized sending this packet email without another approval question.
Gmail accepted the standalone email and verified ZIP on 2026-10-14, Message-ID
`<179196432084.23355.5237107531696812358@gmail.com>`.
The message states the new standing email authorization, keeps the existing
inference-only scope, and requires final Kaggle shutdown after verified export.
The exact body and attachment path are saved in mail history with
`authorization: standing_user_authorization`. Cue's receipt/hash verification
of this standalone packet email is still pending. Check incoming replies and
send necessary coordination follow-ups without asking for approval each time.

## Trigger diagnosis and latest completed-evaluation report

Reviewed inbox UID **217**, received 2026-10-14 09:52:15 UTC. Cue reports the
controlled comparison is complete, all 288 predictions and machine-scored metrics
are verified/saved, and the T4 x2 Kaggle session has been stopped. These remain
remote reports until the exported artifacts are audited locally.

Cue paused a separate semantic-review workflow before launching 32 case reviewers
plus one synthesizer (33 calls, effective limit 36), without a dollar estimate.
The local assistant replied **SKIP REVIEW** for that separate workflow and asked
for the complete machine-scored handoff, download link, SHA-256 and metrics
summary. Semantic assessment will use the saved predictions locally with the
existing assistant; it remains pending and is not legal validation. No additional
training or inference was requested, and Cue was asked to keep Kaggle stopped.
Gmail accepted this reply, Message-ID
`<179197188977.25230.12518449272576366866@gmail.com>`; body is saved at
`reports/cue-mail/results-request.txt` and in mail history. UID 217 is now reviewed
and replied to; do not send that request again.

The user reported no automatic activation after this email. The timer had fetched
UID 217 and recorded a successful CLI queue receipt, but that did not verify a
started assistant turn. The watcher now uses JSON-RPC over the existing local
Codex Unix WebSocket and calls `turn/start` after checking the conversation is
idle. It records `last_started_turn_id`, retries busy conversations, and uses the
existing project virtualenv. A live connection/status check succeeded, and the
21-test mail suite plus formatting checks passed.

A one-time automatic wake verification is pending in watcher state (`verify_wake`).
It must start once this current repair turn ends. Do not claim the live idle-start
test succeeded until a `[CUE MAIL WATCH VERIFY]` turn actually runs and records
the started turn ID in this memory. Preserve the distinction between the verified
RPC connection/busy deferral and the still-pending live idle activation.
The installed virtualenv-based service was verified at 2026-10-14 10:20:33 UTC:
it exited zero with `waiting_for_idle` and retained `verify_wake: true`. Verification
requests now take the same file lock as the checker, preventing a concurrent
check from overwriting that flag. The server connection uses the standard local
Unix WebSocket, not raw stdio to the control socket.

Earlier delivery report: the user relayed Cue's statement that its mailbox shows
only the earlier status request and no newer message. The approved follow-up's
SMTP acceptance is recorded, but its visibility in Cue remains unresolved.
A full prompt for the user to paste into Cue is prepared at
`reports/cue-mail/cue-communication-prompt.txt`. It asks Cue to check the complete
email thread and send a real acknowledgment to Gmail, states both addresses and
the per-query approval rule, repeats the approved experiment scope, and requires
Kaggle shutdown after verified export. It tells Cue to report a missing packet
and wait for it rather than reconstructing the data. This prompt has not been
emailed as an additional query.
Later work is a larger reviewed Civil Code benchmark and actual retrieved-context
evaluation before considering generator integration.

## Reviewed controlled-inference handoff reply

Reviewed inbox UID **219**, received 2026-10-14 11:29:00 UTC, in reply to the
SKIP REVIEW/export request. Cue reports all 288 controlled generations are
complete, the Kaggle T4 x2 session remains stopped, and saved artifacts are
retained. It confirms no training, adapter changes, production RAG changes or
separate semantic-review workflow were performed.

Reported metrics, with 32 questions per view (16 per language):

| Model | Original macro token F1 | Evidence-present macro token F1 | Original exact Reject | Evidence-present exact Reject | Evidence-removed exact Reject |
|---|---:|---:|---:|---:|---:|
| Untuned base | 0.721 | 0.748 | 1/32 | 0/32 | 30/32 |
| SFT v2 | 0.801 | 0.908 | 0/32 | 0/32 | 0/32 |
| M/A v2 | 0.679 | 0.633 | 6/32 | 10/32 | 31/32 |

These are Cue's rounded string metrics, not locally reproduced results or legal
correctness rates. Base and M/A both reject most evidence-removed controls;
M/A also rejects some controls with evidence available. SFT has stronger answer
overlap but no exact Reject on evidence-removed controls. Semantic assessment of
individual outputs remains pending.

Reported results archive: `Qwen3_V2_Controlled_Inference_Results.zip`, 200,536
bytes, SHA-256
`30f1c4a9ea2c7b566bf1d4eb2e6e20093250b9e5229aa16f13392ba1cd663f02`.
Drive file ID: `1BTjyWe3PXP1hawH5ntD3oTUJYaeDUO8H`, restricted to the user's Gmail
account. An unauthenticated web-tool download was unavailable; Gmail app-password
access does not provide Google Drive authentication. Request the existing small
ZIP as an email attachment without changing its access or rerunning anything.

The three email attachments were downloaded read-only via IMAP to ignored
`reports/cue-mail/uid-219/`: Python source snapshot, remote validation JSON and
Kaggle shutdown screenshot. The source snapshot's locally computed SHA-256
matches Cue's reported
`3d67a81b52152ddfca2f1553878eee08e0c5dd0632f238f5735be39156a373ec`.
The validation report claims archive integrity and all 15 payload checksums pass;
this is remote evidence until the archive is independently checked locally.

Executed run reportedly remains saved as private Kaggle Version 1:
`https://www.kaggle.com/code/yacine105ai/qwen3-v2-controlled-inference-eval?scriptVersionId=358284154`.
Cue reports no standalone executed notebook export; the attached Python source
is not an executed notebook with embedded outputs. The old before-predictions
provenance discrepancy and five English training label conflicts remain recorded.
UID 219 is reviewed; do not repeat its review or resend a follow-up already logged.

Gmail accepted the direct-attachment follow-up, Message-ID
`<179197787532.28235.6882274104014696973@gmail.com>`, in reply to UID 219.
Exact body: `reports/cue-mail/request-archive-attachment.txt`. It requests the
already verified 200,536-byte ZIP unchanged, retains private Drive access and
the stopped Kaggle session, and authorizes no new computation. The direct HTTP
download returned HTML rather than ZIP data. Next: receive the ZIP attachment,
check its hash/integrity and reproduce metrics before semantic review.

## Received ZIP and completed local controlled-results review

Reviewed inbox UID **220**, received 2026-10-14 12:02:52 UTC. The attached
`Qwen3_V2_Controlled_Inference_Results.zip` was downloaded through read-only IMAP
to `reports/cue-mail/uid-220/`. Independently verified: 200,536 bytes, the expected
SHA-256 above, ZIP integrity, all 15 payload checksums, byte-identical frozen
inputs, and adapter configuration/weight hashes matching the earlier handoff.

All 288 unique predictions have the supplied shared question/context/mask fields.
All per-language/view/model F1, exact-match, exact Reject, EOS and cap metrics
reproduce. Prompt token counts and blocked-column counts also reproduce using
the saved tokenizer offline. Maximum prompt length is 409. The checkpoint and
final export contain the same records in different orders.

Local audit: `eval/reports/qwen3-v2-controlled-audit.json`.
Local review: `eval/reports/qwen3-v2-controlled-review.md`.
Reproducible artifact audit: `reports/cue-mail/uid-220/audit_results.py`.
The review inspected all 32 cases across the three models and three views.
It checks answer fidelity to the provided excerpts, not source-law accuracy,
legal currency, Civil Code performance or actual retrieved-context performance.

Key interpretation:

- The base has one valid plain-language refusal not counted as literal Reject.
  Case `90d6d41b30935c2e` still exposes a partial agreement title in an unmasked
  header, so evidence removal is incomplete there. Across the other 31 removed
  controls, both base and M/A abstain. M/A's 31/32 versus base's 30/32 exact Reject
  is therefore not a demonstrated semantic abstention improvement in this set.
- M/A rejects 6/32 original and 10/32 evidence-present questions and loses
  conditions/provisions in other answers. Both adapters give incomplete Arabic
  Articles 74 and 29. Those adapter omissions are not caused by the output cap.
- SFT has higher token overlap but no semantic abstention in the removed view;
  failures include invented dates, unrelated passage copying and question
  repetition. Do not label every non-Reject output a fabricated fact.
- Case `e20968a6b0957722` confuses a pricing effective date with agreement
  commencement; case `51efeb8a2383b047` has an incomplete reference clause.
  These reference/control issues need review before benchmark use.
- Compared with the old handoff, all 32 M/A original outputs match; SFT differs
  only on `4b1c881bcf44457c`, now quoting the correct governing-law clause. This
  explains its English F1 increase. The generation/numerical cause is unresolved;
  hashes match, so use the current paired-run scores rather than mix sweeps.

Cue reconfirms Kaggle stopped and no additional computation was performed.
GPU execution and current remote session state were not independently rerun or
queried locally. The source and a short log are available; an executed notebook
with complete cell outputs remains unavailable as previously disclosed.
Neither adapter has been integrated into production. No new experiment is being
requested; preserve the current generator and both pilot adapters. The next
model-selection work is a larger reviewed frozen bilingual Civil Code set and
actual retrieved-context evaluation after fixing the recorded data issues.
UID 220 is reviewed; do not duplicate this download/review or resend a logged
receipt acknowledgment.

Gmail accepted the acknowledgment to UID 220, Message-ID
`<179198018046.29181.376816496017521663@gmail.com>`. Its body is
`reports/cue-mail/acknowledge-verified-results.txt`. It confirms local artifact
and metric verification, shares the reference/control and semantic qualifications,
and closes the handoff with Kaggle stopped and saved artifacts retained.
No additional reply or remote computation was requested.

## User-authorized final model acceptance and release task

The user now wants one final bounded task for Cue, then a usable model and an end
to the experiment. Asked to choose among base/M/A/SFT, the user replied:
"you judge, i dont know, i want the highest possible accuracy for the model so
it wont fail on the current data." The local assistant will select by measured
complete, supported answers and proper abstention; no zero-error guarantee or
automatic preference for the paper-derived M/A adapter is justified.

Plan: one final inference-only Civil Code acceptance sweep of the three existing
candidates, followed by packaging and fresh-load/serving verification of one
selected release. No further training, new datasets or hyperparameter study.
The earlier no-further-inference instruction is superseded only for this bounded
new task. Preserve the current production generator until the handoff is checked.

Prepared packet: `reports/cue-mail/final-release/Qwen3_Final_Acceptance_Packet.zip`.
It has 52 source-context cases: 20 answerable and six unanswerable per language,
using the existing 20 English Civil Code article fixtures. References in both
languages were checked against those excerpts by the local assistant, including
complete conditions and numbers. This is not independent human legal review.
Rank by minimum per-language semantic case success, then overall success and
unsupported/numerical errors; F1/EM are secondary. The base remains eligible if
neither adapter performs better. Use the pinned Qwen base and original adapter
hashes, ordinary visible contexts, recorded prompt, greedy decoding and a
256-token output cap. The longer cap addresses prior baseline truncation.

Real retrieval was attempted with the existing NLPController on a disposable
20-article Qdrant index (existing projects/indexes were preserved). Embedding and
indexing succeeded, but the GPU reranker returned HTTP 500 with CUDA unknown
error and its inference endpoint became unavailable. Its models-list readiness
had passed, which did not establish functioning inference. One managed-service
restart was attempted; inference still failed and systemd reported auto-restart.
No driver/package changes or production environment edits were made. Local CUDA
recovery remains separate from the final Kaggle model task.

The final packet therefore uses explicitly labeled source/oracle excerpts plus
deterministic distractors, not fabricated retrieval snapshots or full-corpus
coverage. This tests generator selection and cannot certify production RAG or
the host GPU. A future local connection check is still needed.

The target host has one 6-GiB RTX 3060 Laptop GPU; allow approximately 1.3 GiB
for the existing reranker. Cue should provide a practical 4-bit loading/serving
route with measured memory and distinguish a Kaggle T4 test from host verification.
Keep vLLM in its separate environment, currently 0.30.0. Official 0.30 BNB docs
require `vllm-bnb-plugin`; no local dependency installation was performed.
If merge/quantization changes the model representation, verify the release on
the same cases; keep the original selected format if it regresses rather than
start another tuning loop. Deliver results/configuration/loader as a small email
attachment and private links only for large weights not already possessed here.

Final email body: `reports/cue-mail/final-release-query.txt`. It authorizes one
Kaggle T4 x2 task, requires verified export and GPU session shutdown, and then
ends Cue work. The packet and email still need their final hash/send record below.

Packet verification passed: 24,743 bytes, 52 unique cases balanced 20 answerable
and six unanswerable per language, full relevant source article in every
answerable context, all payload checksums and ZIP integrity verified. Its
SHA-256 is `7db6ec2b3dd5b6962b4675e0f4e21d354c6ada7e2b5638011e2517fed1f61046`.
Maximum prompt length is 427 tokens using the saved pinned tokenizer; no prompt
truncation is needed at the stated 2,048-token serving limit with 256 output tokens.

Gmail accepted the final task and attached verified packet, Message-ID
`<179198371312.30740.17458306248363049412@gmail.com>`, in reply to UID 220.
Subject: `[RAG-ISHMS] Final task: Civil Code acceptance and usable model release`.
Standing user authorization is recorded in local mail history. Cue's receipt was
subsequently reported in the pasted chat below; inference start remains pending.
Do not claim this final run is already executing. Next: review
its acknowledgment/results, audit the selected-model release and then prepare
the local RAG connection. Do not resend this task or start a second experiment.

The user pasted Cue chat updates dated 14 October at 16:15–16:16 local time:
Cue reports receipt of the final packet, matching packet SHA-256/all manifest
hashes, the expected 52 balanced cases, verified original adapter hashes/ZIP
integrity, a duplicate-run check, and creation of a private Kaggle input bundle.
These are reported preparation steps, not an independently inspected Kaggle run.
No inference start or final candidate result is shown yet. No new outgoing query
is needed; let the single authorized task continue. The earlier 15:44 statement
that local semantic review was pending is outdated; that review is complete.

## Final acceptance handoff received and audited

Reviewed inbox UID **221**, received 2026-10-14 15:17:40 UTC, replying to the final
task. Cue reports the 52-case/156-generation comparison and selected-model
fresh-load handoff are complete, Kaggle stopped, and saved artifacts retained.
The selected candidate is the **untuned Qwen base with no adapter**, pinned to
`cdbee75f17c01a7cc42f958dc650907174af0554`. No further training occurred.

| Cue semantic judgments | English | Arabic | Overall |
|---|---:|---:|---:|
| Untuned base | 21/26 | 13/26 | 34/52 |
| SFT v2 | 18/26 | 0/26 | 18/52 |
| M/A v2 | 12/26 | 4/26 | 16/52 |

Base succeeds on 15/20 supported English cases plus all six English refusals,
and 9/20 supported Arabic cases plus four Arabic refusals. SFT succeeds on 18/20
supported English cases, but fails the reviewed Arabic and refusal cases.
M/A refuses many supported questions. These rates are Cue's case judgments
against the specified strict rubric, not independently regraded legal labels.

The packet contains **English passages for both question languages**. Arabic
results therefore test cross-language answering; they are not comparable to
the earlier Arabic-context token F1. Wrong-language English copying is a major
adapter failure here. Base also omits conditions and makes Arabic translation
errors. Its two negative naming responses substitute generic categories or
descriptions as purported names, rather than properly refusing; do not describe
these as discovered real names. The highest-accuracy/zero-failure objective has
not been demonstrated by selecting the best of three imperfect candidates.

Downloaded through read-only IMAP to `reports/cue-mail/uid-221/`:
`Qwen3_Civil_Code_Selected_Model_Release_2026-10-14.zip`, 106,923 bytes, SHA-256
`28ffc3d6bbfc19c14f53633c37d2773ffa81ebb07aa71dd22c0a923eafb36399`.
ZIP integrity, all 21 payload checksums and the byte-identical original input
packet pass locally. All 156 unique prediction records match their frozen cases.
Counts recomputed from the 52 per-case annotation rows match the reported totals.
Four fresh-load smoke responses/hashes match the saved acceptance predictions.
The GPU smoke itself was executed remotely, not rerun locally.

Local audit: `eval/reports/qwen3-final-release-audit.json`.
Release contents include a pinned-base Transformers loader, prompt/settings,
156 predictions, Cue semantic notes, logs, manifests and smoke artifacts. **No
multi-gigabyte model weights or saved quantized checkpoint are included.**
The loader fetches the unchanged public Hugging Face base at the pinned revision.

An OpenAI-compatible API/vLLM server was **not** started or tested. The command
in `vllm_unverified.sh` is explicitly an unverified documentation template.
The fresh load used NF4/double-quantized FP16 Transformers on two T4s; the one
6-GiB host GPU and simultaneous reranker memory fit have not been verified.
No production generator setting was changed. No custom fine-tuned adapter was
promoted, merged or repackaged as a winning release.

Current read-only local checks: `nvidia-smi` failed with `GPU access blocked by
the operating system`; the reranker unit is auto-restarting with exit status 1.
No further restart, driver change or deployment was performed for this status
request. Remaining local work: recover GPU/CUDA access, obtain pinned weights,
verify 4-bit memory fit and an API endpoint, connect the existing RAG settings,
and check bilingual answer quality with actual retrieved source-language passages.
Cue's bounded comparison/export task is finished; request no new experiment.
UID 221 is reviewed. Avoid duplicate download/review or another final-task send.

Gmail accepted the final receipt acknowledgment, Message-ID
`<179199177086.38569.1549677681989507377@gmail.com>`, in reply to UID 221.
Body: `reports/cue-mail/acknowledge-final-release.txt`. It confirms the artifact
checks and recorded limitations, closes Cue's bounded task, and keeps Kaggle
stopped with saved artifacts retained. No further remote work/reply was requested.

## Local Qwen setup authorized — 2026-10-15

The user authorized preparing the selected model in the existing vLLM environment
and connecting Docker generation; they will restart the laptop later. They also
authorized cache/temp cleanup and deleting OpenCode if necessary for space.
During setup they asked whether to terminate Cue: the answer was yes, its task is
complete, retain artifacts and leave Kaggle stopped. No further Cue query or
experiment is required. The latest release files are already local and verified;
their ZIP does not contain the multi-gigabyte model weights.

Searched Linux/Windows caches, Downloads and G: model locations. Other Qwen
models exist, but the exact selected Qwen3-4B revision was not found. Preserved
those models. Linux initially had less than 1 GB free. `uv cache clean` reclaimed
2.4 GiB without removing virtual environments; root now has about 3.3 GiB free.
OpenCode is only 12 KB and has no container, so deleting it would not help and
was unnecessary. No unrelated containers, volumes or project files were deleted.

Installed `vllm-bnb-plugin==0.0.3` and `bitsandbytes==0.50.2` with `--no-deps`
inside `/home/yacine_105/vllm-env`, preserving vLLM 0.30.0/Torch and the API's
separate dependencies. The plugin registers its bitsandbytes loader. CLI setup
then fails device detection while NVML reports OS-blocked GPU access; this is
not a passed GPU inference test.

Pinned weights are **downloaded and independently checksum-verified** at
`/mnt/g/rag-ishms-models/Qwen3-4B-Instruct-2507`, linked from
`/home/yacine_105/vllm-env/models/Qwen3-4B-Instruct-2507`. The pinned repository
has 12 downloaded files totaling 8,060,915,998 bytes. All four LFS SHA-256 hashes
(three weight shards and tokenizer) and all eight other Git blob hashes pass
against the exact pinned Hugging Face revision. Completion and individual file
sizes/SHA-256 values are in `rag-ishms-model.json` beside the weights.
The Xet client stalled; stopped it while retaining partial files, then recovered
through HTTP Range downloads. Both resumed shards passed their full SHA-256
checks. No model representation or adapter was changed. The reusable helper is
`scripts/download_qwen.py`, run with the vLLM Python and `HF_HUB_DISABLE_XET=1`.

Added a private configuration helper, generator launcher and user service. The
generator is enabled along with the existing reranker; **both are stopped** until
GPU access recovers. It will wait for reranker health, then request 4-bit loading
with FP16, eager execution, 2,048 total tokens, one sequence and a 0.70 GPU budget.
Concurrent memory fit on the 6-GiB laptop remains untested. The configuration
helper creates a private rollback snapshot and preserves unrelated settings;
isolated checks passed for key reuse, private permissions and revision rejection.

Recreated nginx and Prometheus to fix their stale Docker Desktop bind mounts;
both are reachable again. No volumes or unrelated containers were removed.
Applied `scripts/configure_qwen.py` after the verified download, creating the
separate private generator key and preserving a mode-600 rollback copy in
`docker/env/.env.fastapi.before-qwen`. Only six generation settings changed:
OPENAI provider, local port-8001 base URL, private generator key, alias
`qwen3-legal-final`, temperature 0 and 256 output tokens. Independently compared
all other API settings before/after and confirmed they remain identical.
Verified that the generator and reranker keys differ and that key-bearing files
are mode 600. Credentials were not displayed or committed.

Recreated FastAPI with its new environment, then nginx to refresh its upstream.
Confirmed the running container's generation, embedding and client settings
match the private configuration. `/docs` returns 200; protected index information
returns 401 without a client key. `/health` returns 503 with DB, vector storage
and embedding **ok**, generation and reranker **error**, as expected while the
GPU services are stopped. This is not a live model or RAG answer pass.

The pinned Qwen config and both Arabic/English chat-template paths load offline
in the actual vLLM environment. No model forward was executed. A final
`nvidia-smi` still exits 255 with OS-blocked GPU access. Both managed GPU services
are enabled and inactive, ready to start on the next WSL user session.
All 73 existing provider/reranker/NLP/streaming contract tests pass. Shell syntax,
Python lint/format, systemd unit verification and Compose validation also pass.
README and `docs/model-serving.md` now explain the Qwen startup, actual storage
path, keys, limits, pending verification and rollback. The selected model remains
the untuned base; no pilot adapter was promoted or further training requested.

Next, **after the user's laptop restart**: confirm CUDA access, start/inspect
`rag-ishms-reranker.service` and `rag-ishms-generator.service`, measure concurrent
memory fit, verify a real authenticated completion and bilingual RAG answers with
actual retrieved sources. The local setup that does not require CUDA is complete.
Do not claim API generation, GPU memory fit or RAG quality has already passed.
No additional Cue experiment or query is needed; retain its verified handoff.

## Post-restart local serving verified — 2026-10-15

The user asked what remains and whether their other requests were completed.
Read memory and the latest 20 local mail records; UID 221 is still the latest
received Cue release. No duplicate query, receipt email or new Cue work was sent.
The laptop had restarted: `nvidia-smi` now detects the 6-GiB RTX 3060 and both
enabled services started automatically. Reranking a real question against the
existing Civil Code smoke project `900001` returned its indexed source.

Qwen's first GPU load completed (2.71 GiB), but startup failed in FlashInfer
warmup because systemd's PATH omitted `~/vllm-env/bin/ninja`. Stopped the failed
generator, added its vLLM binary directory to PATH in the launcher, and restarted
it. Existing Ninja/CUDA tools then completed warmup; no drivers, weights, model
representation or Python package versions were changed. Both services now run.

Independently executed and saved locally:
`eval/reports/qwen3-local-serving-verification.json`. `/health` is 200 with all
dependencies ok. Two authenticated direct completions preserved the supplied
21-year value in English/Arabic. Real RAG English/Arabic answers cited the
existing Article 1/2 TXT asset. A full-sequence Arabic question returned custom,
Islamic-law principles, then natural-law/equity principles with the correct
conditions. An unsupported request for the judge's full personal name refused
instead of inventing a name. Article 2 SSE completed with all three repeal cases.

These are bounded connectivity/semantic checks on public source excerpts, not
new training, a legal accuracy grade, or a controlled comparison with Cue's
Transformers run. The first English Article 1 answer redundantly repeats the
last fallback. The ordinary Arabic question asked only for the immediate source;
the separate explicit full-sequence question checked its remaining conditions.
No corpus, application database, vector volume or embedding model was changed.

Qwen weights occupied 2.71 GiB; sampled total GPU use was 4,694/5,742 MiB of
6,144 MiB with both services loaded, not a measured continuous peak. Direct
completions took 1.17/1.56 s. RAG probes took 4.63–9.12 s. SSE completed in 6.45 s
with first delivered text at 6.43 s: current guardrails buffered the result, so
this is not evidence of low TTFT. Context remains 2,048 total tokens and one
active generation sequence; the 50-user test remains unperformed.

All 21 mail/watcher unit tests also pass; the 73 provider/reranker/NLP/streaming
checks passed in the preceding setup with unchanged application source. Python
lint/format and launcher shell syntax pass. Documentation now records working
GPU serving rather than the obsolete restart blocker. Changes are organized into
separate local commits under the user's earlier professional-commit request; private credentials,
mail attachments/history and model weights remain outside Git.

Remaining plan evidence: human-reviewed larger Civil Code/RAGAS evaluation,
50-user load/TTFT results, five measured RAG configuration comparisons and the
final project report/screenshots. Optional hosted observability/CI settings need
their own external configuration. Fine-tuning and Cue's bounded handoff are
finished; no further training or Kaggle work is required for local use.
