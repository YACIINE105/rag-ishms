# Cue coordination memory

Last updated: 2026-10-16 (Africa/Cairo).

Current local status: Qwen base generation, BGE reranking and the existing Docker
stack are running. Full-PDF Qalam extraction, 310 actual retrieved-context
answers and real 50-user/SSE measurements are complete. The original Super
endpoint passed the revised controls and is actively finishing the consistent
five-way regrade in configurations-super-candidate-v2/; two configurations are
complete. The throttled VL attempt is preserved separately. See the latest entries and
`docs/final-project-report.md` for current counts and known answer/judge errors.
The report, figures, PDF and evidence export are the current local deliverables.
Cue's artifacts are already reviewed through UID 221; Kaggle is reported stopped.
Do not launch new training or replace the selected base with a pilot adapter.

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

## Final-project evaluation authorized — 2026-10-15

The user authorized completing the remaining quality evaluation, five measured
configuration comparisons, 50-user load/TTFT test and final-project evidence.
Use `G:\Downloads\1576751803.pdf` and the existing Qalam parser. They prefer
progress updates only when requested; keep detailed progress in local artifacts.
No new training or Cue/Kaggle task is needed. Preserve existing projects/indexes.

The supplied file at `/mnt/g/Downloads/1576751803.pdf` is byte-identical to the
existing corpus: SHA-256
`2d6419fb262dab712f7bf5f6e31834bea74fbcf03b78ae081dd35d156915eebf`.
Independently reran `scripts/build_legal_corpus.py` on the user-specified path;
output is `eval/reports/final-project/corpus/articles.json`: 1,149 articles,
2,297 nonempty Arabic/English text fields, the known 1021/1022 alignment issue,
and no new validation error. Longest field is 525 Qwen tokens. This is actual
Qalam extraction, not a claim that every article has been legally reviewed.

OpenRouter's current key has only 44 of 50 daily free-model requests remaining,
so it cannot support the requested evaluation/load workload. The project's
existing NVIDIA key in ignored `src/.env` independently passed an authenticated
probe of **the same** Nemotron VL 1B v2 embedding model (2,048 dimensions).
A separate large NVIDIA Nemotron judge also returned valid structured JSON.
Plan: use a private local evaluation profile with that existing direct endpoint,
keeping production Docker credentials/settings/index identities untouched.
Record the exact endpoint/model distinction in the final evidence. No paid API,
new account, external deployment or replacement model weights were requested.

Next: freeze source-reviewed bilingual cases, validate the independent judge,
extend the existing evaluator for full bilingual corpus/batched seeding and
resumable evidence, execute five comparisons plus the full metric suite, then
run the isolated HTTP load test and create the final report/screenshots. These
experiments are authorized but **not yet executed** at this checkpoint.

## Frozen Civil Code evaluation in progress — 2026-10-15

Created `eval/civil_code_full.json` and its checksum manifest before generation:
62 cases (25 answerable plus six unanswerable per language), covering 25 distinct
articles. Historical acceptance references are retained, their oracle contexts
removed, and ten source-reviewed questions add Articles 226/374/558/802/1148.
Rendered bilingual PDF pages 28/50/74/113/170 were inspected locally. This is
assistant review, not independent human legal review. Dataset SHA-256:
`18bcdaee5525639b721be2a2a6d473da33b1d8bfe5e68b55317cc7c9306a72b0`.

The independent NVIDIA Nemotron 120B judge correctly distinguished all 12
correct/incorrect Arabic/English sanity examples. A real RAGAS probe produced
all four metrics; NVIDIA embeddings require `input_type` for both single and
batched RAGAS calls, now supplied in the evaluation adapter. These are actual
executed checks, not agreement with legal experts.

Evaluation now seeds all 2,297 language chunks in batches, uses semantic refusal
checks for the new benchmark, retains raw answers before judging and checkpoints
completed scores. Generation remains sequential; up to three remote grading
workers overlap. Restored the citation header in Qalam's production chunk text
so numbered provisions remain identifiable inside the prompt, matching the
existing evaluator representation. Existing stored chunks are not rewritten.
Expanded stage histogram buckets to measure queuing beyond ten seconds.

Latest executed suite: **226 tests and 12 subtests passed**. The first complete
62-case configuration has saved all answers (one in an earlier completed row,
61 in the raw-answer map), with 39 fully scored before the judge returned HTTP
429. No aggregate comparison is complete yet. Resumed from saved answers with
HTTP-level request spacing of 2.1 seconds, retaining earlier scores and RAGAS
cache. The interruption/rate-limit evidence stays in the experiment log.

Outputs: `eval/reports/final-project/`; current checkpoints are under
`configurations/`, and MLflow uses `reports/mlflow.db`. A focused isolated API
load-test runner and delivered-SSE latency/token-throughput probe are prepared,
but **load testing and the final report are still unexecuted** at this checkpoint.
Production Docker settings and indexes remain untouched; no Cue/Kaggle action.

### Status request / resumed scoring — 2026-10-15 15:49 Cairo

The user asked whether everything is done. Answered that engineering evidence is
still in progress; no completed comparison/load/report was claimed. Latest full
suite remains 226 tests plus 12 subtests passing. Local commits `9e2882e` preserve
Qalam citation headings and `36abf57` adds the frozen/resumable evaluation.

Scoring resumed with request pacing; the first comparison reached 60/62 graded
cases. Its raw answers were not regenerated. `scripts/run_experiments.py` remains
active; after all five comparisons finish, the one-off local finalization runner
(`/tmp/finish_rag_evidence.sh`, log `eval/reports/final-project/finalization.log`)
is waiting to execute the isolated full-PDF API ingestion, SSE probes, 50-user
Locust test and report generation. Check process and output state before starting
anything again. Do not launch duplicate evaluation or load processes.

Reviewed all 62 baseline answers against frozen references. Recorded specific
model errors and judge disagreements in
`eval/reports/final-project/assistant-answer-review.json`, without changing any
automated score. Clear findings include the Arabic Article 94 missing meeting-end
condition, Article 147 omitted void-agreement clause, a generic category passed as
a personal name, and Arabic Article 226 output truncation. The judge also
fabricated interpretations of some Arabic text (notably court-address refusal
and Article 374). Its simple 12-item calibration therefore does not establish
reliable legal correctness. All final accuracy conclusions must retain this caveat
and source/answer review; no legal expert review exists.

Tried the existing NVIDIA account for an alternative Kimi and Mistral judge;
both returned 404 indicating those listed models are unavailable to this account.
No new key/account, paid endpoint, or generator change was made. Existing
Nemotron scores are preserved as provisional automated diagnostics.

The report generator `scripts/report_final_project.py` requires all five complete
62-case reports and actual load/streaming artifacts. It cannot produce a completed
report from partial scores. Playwright rendering and Matplotlib imports were
independently checked; final screenshots/PDF exports and final review/commits
remain pending. Production Docker services/settings/indexes are unchanged.

### First comparison complete — 2026-10-15 15:50 Cairo

Verified `configurations/article-rerank.json`: all 62 cases scored. Automated
faithfulness 0.9491, reference accuracy 58/62 (0.9355), article hit rate 1.0,
p95 RAG latency 28.72 seconds; the existing engineering gate passes. These remain
provisional LLM-judge scores because the independently recorded Arabic
misreadings and model errors have not disappeared. Do not equate 58/62 with
legally correct answers.

The second configuration is actively building its disposable full-corpus index
(850/2,297 chunks at the status check), so a missing checkpoint does not mean its
process has not started. Four comparisons remain incomplete. The finalization
runner is still waiting; no load/streaming results or final report exist yet.
User asked only for the remaining list; no new scope or duplicate run was added.

### Finish the remaining tasks authorized — 2026-10-15

The user explicitly said to do the four remaining tasks now. Continue the
existing live comparisons, then complete load/SSE measurements, result review,
report/figures/screenshots and professional local commits. Keep updates quiet
unless requested. Do not stop at another status list or launch duplicate runs.
The same experiment process and finalization runner are still active; inspect
saved progress and recover routine provider/tool errors autonomously.

Prepared report rendering with actual Markdown tables and portable PNG/PDF
figures; separate measurement dependencies are pinned in
`loadtest/requirements.txt`. Load evidence will record observed peak users,
actual failures and one-second GPU samples. These additions are prepared code,
not claims that the load run already occurred. Human legal review remains
outside what an automated agent can truthfully complete.

### Provider availability and actual API/load execution — 2026-10-15

The Super judge resumed but hit HTTP 429 again even below 40 observed responses
per minute. Saved baseline scoring remains complete (62); no-rerank has all 62
answers and 34 completed scores. Paused scoring to complete independent work.
Request handling now respects Retry-After/minimum 60-second cooldown, limits
judge HTTP concurrency to two and retries only transient failures from saved
checkpoints. Regression tests cover cooldown and wrapped-error classification;
commit `579a1a8`. No duplicate scoring process should be launched without checking.
Alternative NVIDIA Kimi/Mistral were 404; Ultra passed a tiny probe and four
English calibration calls, then 503; DeepSeek and GLM probes timed out. These
alternatives are not accepted judges and no existing score was replaced/mixed.

Grafana's running container had empty WSL bind directories after restart: only
its folder existed and the dashboard API returned 404. Recreated **Grafana only**
with the existing named volume and Compose mounts; dashboard now returns 200
with all 13 panels. No orphan container/volume was deleted. Published the real
completed baseline evaluation through the existing node-exporter textfile path;
quality metrics are present. They remain provisional automated scores.

Started the isolated real API load workflow. The first setup exposed an existing
bug: upload returns numeric asset IDs, whereas processing looked up only stored
filenames. Fixed the project-scoped AssetModel lookup to accept returned IDs
while keeping stored filenames and rejecting out-of-range IDs. Thirty targeted
checks passed, and the actual second API run processed the supplied PDF into
2,297 Qalam chunks successfully. Commit `e13a19a`. Full suite after this fix:
**233 tests, 12 subtests, 86.48% source coverage**, exceeding the 70% requirement.
First failed setup artifacts are retained in `load-setup-attempt1/`.

The second run indexed all 2,297 chunks and completed six delivered-SSE/tokenizer
probes. The 50-user Locust run is active/draining under
`eval/reports/final-project/load/`; wait for its metadata and stop before any
new GPU-quality run. Initial failures/long health latency reveal threadpool
starvation: run_serialized waits for its RLock *inside* a worker thread. A focused
async wait gate outside the pool is being considered/tested next; retain the
original load results and compare separately, without claiming the 6-GiB,
one-generation-sequence setup meets a 50-user latency target.

Added a capture-only evaluation phase (currently being verified) so real RAG
answers/contexts/retrieval hits/latencies can finish across all five frozen
configurations when the external judge is unavailable. It writes separate
`.capture.json` artifacts with status `awaiting_judge`; it must not claim scored
accuracy or a passed gate. Normal resume reuses exact saved answers. The final
report must distinguish complete scores from captured-but-unscored work.

### Continued after host restart — 2026-10-15

The first 50-user run is preserved under `load-baseline/`: observed peak 50,
66 answer requests / 49 failures in the final console (periodic CSV omits one
trailing request), and four failed health probes. Six SSE probes completed.
This failed capacity target is evidence, not a pass. Queued synchronous model
locks exhausted the API worker pool; commit `e6c42a7` awaits the per-provider
async gate before entering a worker and raises the general SQL command budget
to 30 seconds for bulk chunk deletion. Targeted regression checks passed.
The readiness check retains its separate bounded deadline.

The PGVector setup successfully processed/indexed all 2,297 Qalam chunks, but
its second SSE probe failed when vLLM raised `CUDA error: unknown error` at
2026-10-15 13:57:56 UTC. It was not an embedding/indexing failure or a completed
Locust run. That attempt remains in `load-setup-attempt3/`. The host subsequently
restarted; both managed GPU services started automatically. No driver/reset or
manual service interruption was performed during this continuation.

Resumed measurements reuse only the already indexed disposable PGVector project
900102, checking its saved/current index info first. No corpus upload or remote
re-embedding is repeated. Independent keys remain temporary. Measurement tools
now live at `~/.cache/rag-final-tools` so a `/tmp` cleanup cannot remove them;
Chromium and package caches stay on G:. Inspect active processes before starting
another load or GPU-quality run. No new Cue/Kaggle work is authorized/needed.

### Measured PGVector capacity and verification — 2026-10-15

The measurement-only retry completed: 50 observed users, 58 answer requests,
50 failures (180-second p95/p99 client timeout), and four health requests with
one failure. Locust exit 1 is retained. Final authoritative counts come from
`load/load-final.json` after draining; periodic CSV/HTML may lag. Six SSE probes
all completed: first delivered text 21.435, 16.485, 33.569, 18.553, 17.634,
20.111 seconds. Buffered guardrails make these end-to-end delivery times, not
engine TTFT. This hardware/profile does not meet a 50-user capacity target.
The original Qdrant run and later seeded PGVector run are not a controlled causal
comparison of the async gate; backend, boot/runtime and workload also differ.

Added configurable index batches (default 50), scoped PGVector batch replacement,
and verified the actual SQL against project 900102: reinserting the same saved
chunk/vector twice leaves exactly 2,297 rows. No other collection was touched.
The full suite initially exposed missing new settings in test fixtures; corrected
those fixtures and exercised single-record pagination/pacing. Final executed
suite: **236 passed, 86.55% source coverage**. Commits `a6d3bcb`, `e3967bd`.
Capture/scoring separation is committed as `3acb758`; raw generation can finish
without inventing quality scores while the independent judge is throttled.

The capture runner is now building the 250-character full-corpus configuration
(4,215 chunks). Offline judging resumed the existing no-rerank checkpoint from
34 completed scores; it reached 35 and encountered another judge 429. No raw
answers were regenerated. Both processes are active; inspect them before starting
anything else. Five scored comparisons, final report exports and the shareable
archive remain incomplete at this checkpoint. Grafana dashboard API returns 200
with 13 panels and all five Prometheus scrape targets are up after this restart.

Rebuilt only the existing Docker FastAPI image after confirming zero queued or
running production jobs. The fixed code is now in the running image; nginx health
200, missing-key 401 and authenticated blank-query 422 all include request IDs.
Production model/embedding settings and indexes are preserved. No orphan Mongo
container, user volume or GPU service was removed. Evidence is saved in
`docker-rebuild.log` and `docker-verification.json`.

Reference-rubric responses now share a checksum-bound cache with the existing
RAGAS cache, so successful rubric calls are reused if later metrics fail. Model,
endpoint, exact prompt/input, temperature and options form its key. Targeted
26-test evaluation suite passed, including identical-input reuse and changed-input
cache separation; commit `3338395`. Restarted only the offline scoring process to
load this fix; raw RAG answers and completed grades were retained. A tiny direct
Super judge probe still returned 429 / Too Many Requests without Retry-After.
No alternative judge was silently substituted.

### Captures and malformed judge output — 2026-10-15

The 250-character configuration completed all 62 real answers/contexts with no
empty answers or missing contexts; article hit rate 1.0 and observed p95 27.308s.
A focused seven-case assistant review is saved as `assistant-250-review.json`.
It found a real Arabic Article 44 numerical failure: answer 20 although both
retrieved language passages say twenty-one. Incorrect English Article 1 article
attributions/extra fallback, Article 94 omissions and the person-name failure
remain. Targeted no-rerank review covers 11 Arabic cases. These are diagnostic
reviews, not a new legal accuracy label set; no machine score was changed.

The no-rerank judge reached 54/62, then returned unterminated JSON. This is an
external structured-output failure, separate from HTTP 429. Its traceback is
preserved in `scoring-invalid-output.log`. Added strict rubric schema validation,
rejection of length-terminated output, one 4,096-token retry after a reported
2,048-token length termination, and bounded retries of invalid judge output.
Bad response diagnostics are saved in the existing ignored judge cache. The
27-test evaluation suite passes, including truncated-output recovery, cooldown,
exact cache reuse and changed-input separation. Resumed only offline scoring
from saved answers/grades; it reached 55/62 at the latest check. No generation
was repeated and no judge/prompt was replaced.

The 500-character configuration is generating after indexing 2,694 chunks.
The final top-three article configuration, full score comparison and final
report/archive are still pending. Actual Locust and Grafana screenshots were
rendered and visually inspected; the latter is the production dashboard, not
an isolated-load scrape. Its ten per-language baseline quality series are live
in node_exporter and Prometheus. No Kaggle/Cue work was opened.

Latest full suite after structured-output handling: **237 passed, 86.55% source coverage** (see unit-tests.log).

### Sequential judge scheduling / second full score — 2026-10-15

Reduced only the judge request schedule to one HTTP request in flight and one
case-grading worker (same model, prompts, temperature, frozen answers and cache).
This reduces overlapping prototype pressure; it is not evidence of a legal-quality
improvement. The 27 targeted evaluation tests pass; commit `b6f867d`.
No-rerank then completed all 62 scores: faithfulness 0.9461, reference accuracy
56/62 (0.9032), context precision 0.8936, recall 1.0, observed p95 28.000s.
Arabic reference accuracy 26/31, English 30/31; abstention 8/12. Its engineering
gate passes, while the independently recorded model/judge defects remain.

All 62 500-character answers are captured with no empty answers or missing
contexts; hit rate 1.0, p95 36.618s. Targeted review of seven cases preserves the
same Arabic 94/147 omissions, unsupported Article 44 explanation, person-name
failure and truncated Article 226. It does not establish aggregate legal accuracy.
The final article-k3 run is generating; the offline worker has started scoring
250-character outputs from the existing capture, with no generation repeated.

### All five raw comparisons and report export — 2026-10-15

All five configurations completed 62 real answers each: **310 captures**. A fresh
coverage/hash audit confirms the exact frozen IDs, no empty answers, no missing
contexts, the same prompt (`rag-4d3aa56930b0`) and encoder fingerprint. Five capture
runs are saved in MLflow alongside the earlier scored/failed attempts (13 total
runs at the audit). Source PDF bytes/hash, 1,149 articles, 2,297 language chunks and
the frozen dataset hash were checked again. The GPU capture process has exited.

Article-k3 observed p95 is 33.956s and article hit rate 1.0. A seven-case review
finds better completeness for Arabic Articles 147 and 226, but Article 44 starts
with twenty-one then incorrectly gives 18 twice; the generic-category-as-name
failure persists. See assistant-k3-review.json. These are targeted observations,
not a new legal accuracy average or an authorized default/prompt change.

Scoring remains at two complete reports plus two graded 250-character cases;
500-character/k3 grading has not started. Sequential requests did not eliminate
429. Removed nested OpenAI SDK retries so the checkpoint runner owns bounded
recovery instead of multiplying SDK/Instructor/runner retry counts (`238c793`).
27 targeted checks pass; latest full suite is **237 passed / 86.55% coverage**.
The offline worker is exhausting its existing bounded attempts; do not restart
it indefinitely or replace missing grades with fabricated metrics.

The Markdown/HTML report, four PNG/PDF figures and landscape report PDF have been
exported with pending grades explicitly n/a. The PDF source/table pages, Locust
and Grafana screenshots were rendered and visually inspected. A post-rebuild
nginx/API smoke produced nonempty cited English and Arabic answers on existing
project 900001; this is a connectivity/citation check, not another legal benchmark.
The shareable archive, final snapshot/commits and pending-grade handoff are being
finished. No new Cue/Kaggle work, training, deployment target or paid API was used.

### Finalization resumed after host restart — 2026-10-16

Read the latest mail history again; UID 221 is already reviewed and no new Cue
work is needed. The laptop/WSL had restarted before this turn. Both managed GPU
services became healthy automatically; Docker Desktop then restored the existing
containers. Direct API and nginx readiness both returned 200 with all dependencies
ready. `post-restart-verification.json` records this actual check. No volume was
reset and no training/generation sweep was repeated.

The offline scorer had stopped at 3/62 graded 250-character cases, after an invalid
reference-rubric schema. Invalid schema responses now receive the same saved raw
diagnostics as invalid/truncated JSON and are never cached as scores. A meaningful
mocked recovery test verifies rejection of a quoted boolean, saved diagnostics,
and exact-input reuse of the later valid rubric. Full suite: **238 passed**, 12
subtests, **86.55% source coverage**; Ruff and formatting pass. Offline scoring
resumed only from saved answers; the first resumed request again encountered
NVIDIA HTTP 429. A bounded availability check of the existing account's current
model catalogue is being made; any alternative would require calibration and
separate complete scoring, never mixing judges in one comparison.

The recovery probe found Nemotron 3.5 Super VL available, but **11/28** frozen
bilingual control judgments were wrong. In particular, it accepted wrong Arabic
ages, incomplete Article 147 answers, invented court/person facts and wrong
prescription rules. Some returned claims substituted the expected answer for the
actual supplied answer. The full inputs/outputs are retained in
`super35-judge-calibration.json`; this judge was rejected without scoring any
comparison case. DeepSeek V4.1 Flash with its documented `thinking=false` option
timed out after 45 seconds. No alternative scores were mixed in. The original
Super grader progressed to 4/62 for the 250-character configuration, but its
bounded retry sequence continues to encounter HTTP 429.

### Corrected bilingual rubric and consistent regrading — 2026-10-16

The judge failure investigation found an implementation issue: the rubric's
JSON-serialized user message used escaped Unicode for Arabic, and its instructions
could confuse candidate claims with reference claims. The revised
`candidate-unicode-v2` rubric sends readable Arabic, uses a distinct
`candidate_answer` field, prohibits substituting reference numbers/claims, and
explicitly rejects missing required conditions. With this revision the available
Super VL judge passed **28/28** controls, including the previously failed ages,
Article 147 omission and invented personal/court facts. This does not establish
legal expert agreement or guarantee real-case grading quality.

Started a fully separate regrading of all 310 existing captures in
`configurations-unicode-v2/`, using the same Super VL judge/options across every
configuration. Original generation, retrieval and production settings are unchanged.
The legacy scores/failures remain under `configurations/` and are not mixed into
this comparison. A versioned judge-profile manifest rejects mismatched or legacy
scoring directories. Tests cover this rejection and preservation of literal Arabic
in the request payload.

The original Super worker exhausted its bounded retries with HTTP 429, retaining
4/62 250-character grades. The revised scorer was checkpointed once to enable two
HTTP slots/three grading workers while retaining 2.1-second request spacing; its
completed grades/cache were reused. The KeyboardInterrupt in that scoring log is
this intentional offline-worker scheduling restart, not a new GPU/model failure.
No RAG answers, training or load test were rerun. Final comparison/report/archive
will use the consistent revised scores once all five finish.

The revised grading/profile checks pass in the full suite: **240 tests**, 12
subtests and **86.55% source coverage**. The consistent regrade has completed five
article-rerank cases. Its first transient provider HTTP 500 is being handled by
the existing bounded checkpoint retry; this is not a changed model answer or a
training failure. Final packaging waits for the actual result of that recovery.

The two-slot Super VL attempt encountered repeated transient 500s. Its saved
checkpoint/cache were retained and the offline scorer was returned to one HTTP
slot/one grading worker, still at 2.1-second spacing. It then resumed real grading
without repeating captured generation. A second intentional offline-worker
KeyboardInterrupt appears in the log for this scheduling adjustment. The HTTP
error diagnostic option stores request/response bodies only inside the ignored
cache and excludes authorization headers; its mocked check confirms the API key
is absent. Thirty targeted evaluation checks pass. Final recorded full suite
remains 240 tests / 86.55% source coverage.

Fresh post-restart English/Arabic requests through nginx/project 900001 each
returned 200, a nonempty answer and one source (~12.5s each). These consume only
two production embedding requests and are separate from the frozen benchmark.
English gives the source's fallback order; Arabic adds a redundant circular final
fallback sentence. This is a connectivity/citation smoke with a retained semantic
caveat, not an accuracy claim. See post-restart-answer-smoke.json. All five current
Prometheus targets are up and ten recorded per-language baseline series are live.

Intermittent provider 500s continued even with serial requests. The offline
runner's recovery budget now resets only when the checkpoint gained completed
cases, instead of exhausting four retries over an entire long configuration.
It still stops on four consecutive failures without progress, a non-transient
error, or an exhausted recovery deadline. Two meaningful tests exercise continued
progress past four total interruptions and bounded stalled retries, including
client cleanup. All 32 targeted evaluation tests pass. The scorer was checkpointed
once to load this recovery fix and enable private HTTP-error diagnostics; its
completed 16 cases and exact cached work were retained. No model answers changed.

Full suite after the recovery change: **242 passed**, 12 subtests, **86.55% source
coverage**. Inspection of the revised judge's real Article 44 Arabic verdict found
that it still omits the unsupported definition of legal interdiction from its
claim list and gives full faithfulness. This is retained in
`revised-judge-review.json`; the earlier assistant review already identified the
model defect. Calibration passed but is not exhaustive legal validation. The report
will explicitly preserve this current-judge limitation, without inventing corrected
aggregate accuracy or changing the frozen answers/prompts to improve scores.

The handoff now includes copies of the earlier independently checked training,
controlled-inference and acceptance audit reports under prior-model-study/, with
a README identifying their historical startup/remaining-work statements. The
report distinguishes Cue's acceptance judgments (base 34/52, SFT 18/52, M/A 16/52)
from locally reproduced counts, and from the new actual-retrieval benchmark. It
also keeps the English-context/cross-language limitation and the five training
mask-label conflicts. No adapter weights, private mail or model downloads are
added to the evidence bundle. MLflow's final scored runs will log judge/rubric
identity and per-language metrics alongside the existing global metrics.

### First complete consistent regrade — 2026-10-16

`configurations-unicode-v2/article-rerank.json` now contains all 62 completed
scores from the candidate-unicode-v2/Super VL profile. The no-rerank configuration
has started using exact saved captures/cache. The prior-model source review's
Arabic Article 44/94/147/226 defects remain; the revised judge still gives false
positive reference judgments for several of them. These are recorded in
revised-judge-review.json and the report; aggregate correctness is an automated
estimate, not legal acceptance. The complete current article-rerank report has
been published to the existing Prometheus textfile collector; this supersedes the
legacy dashboard pilot scores only, without changing production model/indexes.

Current offline command (still running, do not duplicate):
`.venv/bin/python scripts/score_captured.py --env-file .env.evaluation-super35 --reports eval/reports/final-project/configurations-unicode-v2 --wait-seconds 14400`
Its log is `eval/reports/final-project/scoring-unicode-v2.log`. It never calls the
RAG generator. Original captures and legacy grades remain in configurations/.
All 310 original generated answers/contexts are complete and immutable.

After all five new scored JSONs exist: run run_experiments.py with the frozen
civil_code_full.json dataset, actual results/corpus/articles.json, --reports
pointing to configurations-unicode-v2, --env-file .env.evaluation-super35,
--full-metrics --resume, to log the five completed scores in MLflow without new
inference. Then render report_final_project.py with --configurations pointing to
that new directory (strict mode, no --allow-incomplete). Refresh capture/hash
coverage audit, MLflow run export and current plan-review status; render the actual
PDF/Locust/Grafana evidence with export_final_evidence.py --render using the tools
environment ~/.cache/rag-final-tools and browser cache on G:. Private Grafana
credentials are passed via dotenv/subprocess environment, never printed.

Finish by visually checking report/table pages and figures; commit the report,
figures, setup/evaluation/plan/runbook docs and memory professionally. Export a
credential-scanned evidence ZIP under /mnt/g/Downloads/ with Oct16 date. The private
scan candidate file currently exists at /tmp/rag-final-export-secrets.json (600);
recreate from ignored profiles if needed, never display it. All ZIP CRCs and each
manifest payload SHA must verify; save whole-archive SHA sidecar. Record archive
path/hash in memory in a final follow-up commit. Leave the unrelated untracked
rag-ishms-current.md user transcript alone; exclude it, all mail, profiles, caches
and model weights from the archive. Keep Docker and the managed model services
running. No new training/Cue/Kaggle/deployment/push is authorized or needed.

The completed revised article-rerank metrics are faithfulness 0.98143, automated
reference match 61/62 (0.98387), relevancy 0.71463, precision 0.95511, recall 1.0,
article hit 1.0 and observed p95 28.719s. Arabic automated reference match 30/31,
English 31/31. These high numbers are known to miss substantive defects; they must
not be presented as legally correct-answer percentages. The gate passes only its
automated threshold. Exact machine scores and the source-review disagreements
are both retained.

### Recovery after interruption / provider cooldown — 2026-10-16

The prior user turn was interrupted; read memory/mail history again before
continuing. UID 221 is still the latest incoming artifact and already reviewed.
The independent offline process had continued and completed all 62 no-rerank
scores, then stopped at 5/62 for 250-character scoring after four consecutive
HTTP 429 failures without progress. No scorer was running at the new inspection.
Original captures remain complete; no generation is needed.

At 03:29 UTC a fresh same-account/same-judge availability probe returned 200 in
0.6s (`judge-current-availability.json`). Resumed only offline scoring using the
same versioned profile/checkpoints/cache, reducing request spacing from 2.1s to
5s while retaining one HTTP slot/one grading worker. This is an operational
schedule change, not a new scoring rubric or model. New log:
`eval/reports/final-project/scoring-after-cooldown.log`. The prior log/failed
attempts are preserved. Wait for actual grading progress before claiming service
recovery; the tiny probe alone does not establish a completed evaluation.

### Real-request fallback check — 2026-10-16T03:56:21.451151+00:00

The VL scorer was checkpointed with 11/62 third-configuration grades after
continued 429s. A replay of a real 4,096-token-budget RAGAS request against the
previously used nvidia/nemotron-3-super-120b-a12b returned 200 in 4.791 seconds
(super-legacy-real-request-probe.json). This is stronger availability evidence
than a tiny prompt, but is not a quality result. A separate 28-control calibration
is running with the unchanged candidate-unicode-v2 rubric, using ignored
.env.evaluation-super-candidate; outputs are super-candidate-judge-calibration.*.
Existing VL calibration/scores are preserved. No fallback scores may be mixed
with VL scores; switching requires its own profile and all five comparisons.
Exact original-model RAGAS cache entries may be reused only through the existing
input/model/options hash, while revised custom-rubric requests have different
cache keys. No generation, indexing or training is repeated.

### Calibrated original-Super recovery — 2026-10-16T03:58:55.972212+00:00

The separate original-Super calibration passed all 28 controls with the unchanged
candidate-unicode-v2 rubric. Started only offline scoring into
configurations-super-candidate-v2/ using .env.evaluation-super-candidate. Log:
scoring-super-candidate-v2.log. Initial progress is steady without VL throttling.
The existing judge-cache permits hash-verified original-model RAGAS stage reuse;
custom-rubric keys change with the revised instructions. All five configurations
must complete with this profile before claiming a five-way result. Preserve both
legacy and VL directories; do not duplicate this active worker. Final report and
export code now read the selected judge identity/directory explicitly. The current
committed report remains the earlier incomplete VL snapshot until refreshed.

### Typed-schema recovery and resumed scoring — 2026-10-16T04:08:34.508198+00:00

The original-Super fallback reached 41/62 steadily, then deterministic malformed
JSON omitted every claim's supported boolean on the Arabic interest-percentage
negative. No invalid output was scored. Added one format-only 4,096-token retry
after the primary 2,048-token response fails typed validation; a second invalid
response still raises. Quoted booleans are never cast. The format retry has an
explicit cache-key version; primary grading rules/model are unchanged. The real
failing case recovered, all 28 controls passed again, 33 focused evaluation tests
passed, and the full suite passed 243 tests/12 subtests at 86.55% source coverage.

Resumed the same original-Super score directory with 2.1-second pacing, two HTTP
slots and three grading workers to overlap remote waits. Source answers are never
regenerated. This schedule is distinct from the throttled VL recovery profile.
Active command: score_captured.py --env-file .env.evaluation-super-candidate
--reports eval/reports/final-project/configurations-super-candidate-v2
--wait-seconds 14400. Its append-only scoring-super-candidate-v2.log retains the
earlier malformed-response attempt and deliberate checkpoint interruption.
Do not launch a duplicate. Both the incomplete VL results and original legacy
results remain preserved and must not be merged into the final comparison.

### Consistent grading progress — 2026-10-16T04:42:00.131157+00:00

The original-Super/candidate-unicode-v2 run has completed article-rerank,
article-no-rerank and 250-rerank (62 cases each). Current reference-rubric means
are 0.93548, 0.88710 and 0.77419 respectively; the 250-character Arabic subgroup
is 0.70968. These are automated diagnostics, not legal accuracy. The 500-character
run is active; article-k3 follows. Do not run the ordinary experiment runner until
all five new score JSONs exist, as missing files would trigger fresh inference.
Published the new completed article-rerank baseline to the existing node_exporter
textfile collector; published-evaluation.json pins its source. final-judge-review.json
records that the new reference rubric rejects Arabic Article 44/226 but still
misses the Article 94/147 omissions. RAGAS faithfulness alone still misses an
unsupported Article 44 definition. No source-review scores overwrite machine
scores. Final report/archive must select configurations-super-candidate-v2/,
refresh all five MLflow runs, audits, figures and PDF/screenshots, then export
and verify the credential-scanned ZIP. The current committed report remains the
earlier incomplete snapshot; the final ZIP has not yet been created.

### Final-configuration throttling / user progress tracker — 2026-10-16T05:00:42.122019+00:00

Four original-Super configurations are fully graded. 500-rerank has faithfulness
0.92498, reference-rubric mean 0.91935, context precision 0.95819 and recall 1.0.
The final article-k3 reached 14/62, then NVIDIA 429s recurred. Checkpointed its
worker and allowed cooldown; resuming the same profile/cache with one HTTP slot,
one grading worker and five-second spacing. HTTP error diagnostics are enabled
only in the private cache; they remain excluded from export. No judge/model,
rubric, token budgets, generated answers or existing completed grades change.

The user requested a TODO list and progress bar inside Codex. Show it inline in
commentary and update with actual counts (currently 262/310 = 84.5% evaluation),
not an invented overall-completion percentage. Their request steers this active
work; it does not cancel it. Remaining checklist: finish k3; final MLflow/audit;
final report/charts/PDF/screenshots; verified ZIP and professional closeout commits.
The current report draft now selects the recovered original-Super profile and
contains four full score sets, with k3 marked incomplete. It will need a final
strict regeneration after all five finish. No final ZIP exists yet.

### Original-budget availability control — 2026-10-16T05:17:47.283101+00:00

The final configuration reached 20/62 (268/310 total). Continued 429s led to a
bounded diagnostic after checkpointing and at least 60 seconds of cooldown.
Replaying the most recent actual failed 4,096-token RAGAS request succeeded in
1.74 seconds with stop termination and complete JSON (271 characters). The
smaller-budget probes were therefore not executed. This does not establish a
quota cause; there is no basis for changing token budgets or grading semantics.
No new RAGAS budget option/code or test was added. Keep all 4,096-token RAGAS
settings and the existing two-budget validated custom-rubric retry unchanged.
The reply is diagnostic only, not injected into cache or used as a metric score.
super-active-budget-diagnostic.json records it; the raw reply stays in the private
judge cache. Resume the same final directory and lower-pressure 5s/1-slot/1-worker
schedule. All four completed reports and 20 saved k3 grades remain valid.

### Recovery now recognizes validated cached stages — 2026-10-16T05:26:10.812600+00:00

Observed seven successful DiskCache stage entries added after a completed-case
checkpoint while the final case count stayed unchanged. The old retry guard
recognized only whole-case progress, so it could abort useful partial work after
four provider failures. score_captured.py now reads the actual Cache table in
read-only SQLite, closes the connection, and resets the stalled-failure count
when new persisted stage results or whole cases appear. Diagnostic file writes
do not count as progress. Four failures with neither kind of progress and the
wall deadline remain bounded. No prompt, model, budget or quality criterion changes.

Regression tests use real DiskCache writes to prove more than four failures can
recover with stage progress, and diagnostic-only changes still stop after four.
34 focused tests pass; full suite: 244 tests/12 subtests, coverage 86.55%. The
existing worker was checkpointed at 23/62 final cases to load this recovery fix.
Resume the same directory/model using the existing 5s/one-HTTP/one-worker profile
after cooldown; do not duplicate it. Keep the user's inline Codex checklist and
actual graded-case progress bar updated. Final reporting must use 244 as the
latest executed test count, while retaining historical counts in earlier notes.

### Readiness and final-audit preparation — 2026-10-16T05:51:26.056789+00:00

Repeated local read-only readiness/access checks at 2026-10-16T05:40:18.677590+00:00:
nginx, generator, reranker, Prometheus and Grafana returned 200; missing-key
and authenticated blank-query requests returned 401/422. Three deployed source
files (NLPController, data routes and metrics) exactly match this checkout.
final-readiness.json records the actual running image and request IDs. No new
generation, upload/index, load run or Docker rebuild was performed.

Four current original-Super configurations are complete; final k3 is 32/62
(280/310 total). The sole scorer continues using the 5s/one-slot/one-worker
profile, retaining successful stage progress despite 429s. No duplicate grader
was launched. A one-off /tmp/rag-finalize-tracking.py is prepared and syntax
checked, NOT executed: after all five score JSONs exist and the scorer exits, it
checks exact captured-output identity, typed/finite values and reproduced means,
then records five --resume MLflow runs without inference. It tags the current
release 2026-10-16-super-candidate-v2 and retains historical runs. Reports, final
figures/PDF/screenshots, current docs, audited ZIP and closeout commits still
follow. /tmp/rag-final-export-secrets.json is private; never print/export it.

### All scoring and final report checks complete — 2026-10-16T06:48:27.677952+00:00

The sole offline scorer exited 0. All five original-Super/candidate-unicode-v2
reports now contain 62 grades (310 total). No generation was repeated. Executed
/tmp/rag-finalize-tracking.py: exact answers/contexts/latencies match their original
captures, frozen dataset/PDF hashes match, typed values are finite, and every
overall/per-language average, p95 and gate reproduces. capture-audit.json is complete.

Five new finished MLflow runs are tagged 2026-10-16-super-candidate-v2; all have
62 grades and actual source hashes. Eighteen earlier runs remain. The previous
VL release snapshot is preserved as mlflow-release-unicode-v2.json; current
mlflow-release.json selects only the final original-Super runs. No legacy/VL
grades are merged. k3 finished at faithfulness 0.96917/reference 0.90323. The
article/rerank baseline has the highest automated reference mean, 58/62; the
250-character variant fails its Arabic gate (22/31). These are machine diagnostics
with recorded false positives, not legal accuracy. Existing retrieval defaults
and selected untuned Qwen base remain.

Generated the strict complete report, 310 unique fully graded CSV rows and all
four PNG/PDF figure pairs. The final PDF has 11 landscape pages. Visually inspected
its first page/table (all five 62/62 rows, no clipped table), the full accuracy
figure and actual Grafana-quality/Locust screenshots. Replaced the earlier PDF
page screenshots with pages from this final PDF. report-export-audit.json records
the checks and hashes. Full tests remain 244 passed/12 subtests, coverage 86.55%;
report script lint/format and git whitespace checks pass. No extra suite/load run.

Next: commit the completed report/docs, create the credential-scanned evidence
ZIP on G: with that source commit, verify every payload/whole-archive hash, record
the receipt and commit memory. Keep local GPU/Docker services running. No Cue
query, remote deployment or new training is required. Preserve the untracked
user transcript rag-ishms-current.md; never stage/export it.

### Final verified handoff — 2026-10-16T06:49:49.954636+00:00

Requested engineering work is complete. Source/report commit: 4d94dbb20c6d3d3a8d926dfb23dada34ebf9d47b.
Final archive: /mnt/g/Downloads/RAG_ISHMS_Final_Project_Evidence_2026-10-16.zip
Size: 8,622,336 bytes; SHA-256: cbb9c30e7c52e426310931a1b70f9c66ce1a494ca11836002dbb23f50ef59db3.
Adjacent .zip.sha256 matches. The exporter scanned configured credentials, passed
ZIP integrity and verified every one of 215 payload SHA-256 hashes. Additional
archive checks confirm unique paths, five complete current reports/310 grades,
the selected final MLflow release plus prior snapshot, and no .env files, private
caches, mail, model weights or user transcript. evidence-export-receipt.json
records these checks outside the ZIP (avoiding a self-referential archive hash).

Direct Windows-friendly report copy: /mnt/g/Downloads/RAG_ISHMS_Final_Project_Report_2026-10-16.pdf
It matches the audited 11-page PDF in the archive. The manifest pins the source
commit above; this subsequent memory receipt is intentionally outside that bundle.
Final tests: 244 passed, 12 subtests, coverage 86.55%; commit hooks passed lint,
format, whitespace, conflict and private-key checks. All 310 raw answers are
unchanged and all five scoring reports complete. No remaining engineering action
is queued. The user's inline Codex checklist can be marked complete.

Keep the current Docker and local Qwen/BGE GPU services running. Preserve existing
user projects/data and the untracked conversation transcript. No remote deployment,
push, training or new Cue request was performed. Cue/Kaggle remains closed per the
previous reported shutdown. Known model numerical/omission errors, unreliable
automated legal grading, 50/58 failed load requests and the 50-user capacity limit
remain explicit. Legal expert approval/larger independent labels and optional
external Langfuse/alerts/CI/registry setup are outside this completed local work.
