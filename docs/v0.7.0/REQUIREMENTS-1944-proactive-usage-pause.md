# REQUIREMENTS-1944 — Proactive Claude usage-threshold pause for worker/overseer cron: read real `/usage` percentages over SSH loopback, pause before the hard limit, fail closed, resume automatically

**Status:** DRAFT for architect. This is the **second attempt** at a requirement ruled on 2026-08-17.
The first attempt (#1446 → PR #1450) followed a hedge in #1446's body ("Recommended v1 scope:
reactive tier only"). It shipped only the reactive backstop and left out the proactive check the
human actually asked for. **The proactive percentage check is the core, non-optional requirement of
this issue (FR-1).** Nothing here defers, softens, or re-scopes a ruled item. Every requirement
traces to a source in §7. Requirements this pass *derived* (implied by a ruling but not stated in
it) are marked **[DERIVED]** and listed for human confirmation in §8.
**Date:** 2026-10-02
**Author:** pm-agent
**Source issues:** #1944 (open, `priority:critical`, v0.6.1. Its body is authoritative, and its
2026-10-02 "Design decisions ruled today" section governs wherever it conflicts with older material);
#1446 (closed; comments 2026-08-17T05:17:05Z, 05:25:22Z, 07:47:00Z); PR #1450 (merged; comments
2026-08-17T07:46:46Z through 2026-08-18T04:20:43Z, including ScottThurlow's 08:08:39Z rejection);
human directive, interactive session 2026-10-02 (Prometheus and Grafana scope).
**Target:** pm-agent (this document) → `architect` → `technical-design` → implementation, run through
human-driven interactive worker sessions (#1944 "Process note"), with the overseer reviewing the PR(s).
**Consumers:** `architect` (next), then `technical-design`, `unit-test`, `system-test`.
**Scope note:** This document covers WHAT and WHY only. Where it gives a concrete value, that value is
a ruled default and must be configurable. It is not an implementation instruction. Mechanism, file
layout, and placement belong to `architect` (§6).

---

## 0. Verification findings: where the rulings meet the repo

All checks were made against the working tree on branch `interactive-1944-proactive-usage-pause-design`
(HEAD `9f6a4f05f`). Line numbers refer to that commit.

**Verification gaps.** (a) This session runs in a PID-namespaced sandbox, so it could not see a
running `node_exporter` or its textfile-collector directory. Q4 remains fully open. (b) Nothing was
run against the live cron, SSH loopback, or `claude`. (c) No real `/usage` sample showing the
local-sessions breakdown section exists in any source (D-1).

**VF-1: CONFLICTS WITH THE ISSUE'S PREMISE. The reactive backstop #1944 says to "keep as-is" is
currently disabled.** `bin/hos-cron:2090-2155`. The #1446 usage-limit breaker block has been
**commented out since 2026-09-01 at operator request**. The in-file reason is false positives: it
greps the session's *own* transcript, trips on the first match, and needs a manual
`hos-suspend --clear`, so *"documenting the breaker can trip the breaker."* Only its auto-close
half (`:2181-2202`) is still live. **Consequence:** right now no usage protection of any kind is
active on this host. Once this issue ships, the proactive check will be the only live protection,
not a check with a backstop behind it. This document does not resolve the conflict. FR-40 keeps
the block byte-for-byte unchanged, and whether to re-enable it is escalated to the human (§8, C-1).

**VF-2: The 09-01 false-positive lesson applies directly.** Any pause signal taken from free text
that an agent session might also print will trip on that text. The proactive check must read only
its own `/usage` invocation's output (FR-28).

**VF-3: `hos-suspend` is per-project, role-blind, date-granular, and has no owner field.**
`bin/hos-suspend:122-137` writes `{suspended_at, reason?, until?}` to `~/.hos/suspend/<project>`.
`--until` takes only `YYYY-MM-DD`. `bin/hos-cron:263-283` checks the marker **before** any role work
and exits 0. Two consequences. (i) If the proactive pause reuses this marker and the poll runs
inside `hos-cron` after this check, the poll never runs while paused and auto-resume is impossible
(a deadlock; FR-24). (ii) The marker has no field recording *who* set it, so an automatic resume
that clears it could also wipe a human's or the timeout breaker's suspension (FR-25).

**VF-4: The suggested settings location is a repo-committed, per-repo file, and `hos-cron` does not
read it.** #1944 suggests `scripts/framework/machine-accounts.env` "e.g.". That file is committed
in each consumer repo, and `bin/hos-cron` never sources it. The machine-level config directory
`bin/hos-cron` actually reads is `~/.config/hos/` (`projects.conf` at `:172`, `claude-auth.env` at
`:877`). #1944 asks for the location to be confirmed, not assumed (Q3). This finding is input to
that question, not a ruling on it.

**VF-5: The `#728` auth runbook is `docs/CRON-SETUP.md` §2, not `docs/MACHINE-ACCOUNTS-SETUP.md`.**
The `claude setup-token` / `claude-auth.env` steps are at `docs/CRON-SETUP.md:47-67`.
`MACHINE-ACCOUNTS-SETUP.md` covers GitHub App identity. #1944 Q2 says "likely" the latter. That is
input to Q2.

**VF-6: A literal `claude -p "/usage"` in `bin/`, `scripts/`, or `bootstrap/` fails an existing
enforced test.** `tests/framework/test_agent_invocation_migration.py:98-132` (T4.1, ADR-1643 AD-16)
asserts that the only raw `claude -p` / `claude --print` call sites are three named exemptions.
`/usage` is not an agent invocation and makes no model call. The ruled mechanism and the AD-16
single-invocation-site rule need reconciling (Q8). The Haiku fallback *is* a model invocation and
falls squarely under AD-16.

**VF-7: `write_status()` is plain truncate-and-write plus an ERR trap.**
`/home/scott/.local/bin/sync_human_clone.sh:120-133` writes `last_run`, `outcome`, `head`, and
`detail` with `>`, and installs `trap 'write_status crashed …' ERR` so an unexpected exit still
leaves a record. That is the pattern to mirror (FR-31). A truncating write is not atomic, so a
reader can catch a half-written file. FR-36 requires such a file to be treated as unreadable.

**VF-8: The issue-filing pattern to reuse.** The live timeout breaker (`bin/hos-cron:2056-2080`) and
the disabled usage breaker (`:2132-2154`) share one pattern. Each files one `needs-human,needs-ai`
issue under a stable title prefix (`_USAGE_LIMIT_BREAKER_TITLE_PREFIX`, `:225`). Dedup is
fail-closed: if the dedup query errors, no issue is filed. The issue is auto-closed on recovery.
Note: per this repo's tooling notes, `bootstrap/create_issue.sh` and `edit_issue.sh` keep only the
last of repeated `--label` flags. That is an implementation hazard if the pattern moves to those
scripts.

---

## 1. Context

Usage credits are enabled on this account. When a hard plan limit is reached, Anthropic does not
refuse. It keeps serving and bills real dollars (PR #1450, 2026-08-17T08:16:12Z). A breaker that
waits for a refusal may therefore **never fire** while spend runs past the included quota. Only a
proactive percentage check catches this, and only a proactive check keeps headroom for interactive
work, which was always the goal (PR #1450, 07:46:46Z).

The work stalled for seven weeks because `claude -p "/usage"` under the cron credential
(`CLAUDE_CODE_OAUTH_TOKEN` from `claude-auth.env`) returns a silent empty session. **That question is
closed** (#1944 "What's new today"). Running `claude -p "/usage"` over SSH loopback to self, without
sourcing `claude-auth.env`, uses the existing on-disk personal-login credential and returns real data.
This held under real unattended cron, even when SSH could not allocate a pty. The deciding variable
is the credential, never TTY or pty. The read costs $0 and makes no model call.

---

## 2. Functional requirements

### A. The proactive read (core)

- **FR-1: The proactive percentage check is mandatory and is the primary deliverable.** A delivery
  that ships only reactive or hard-limit detection, or that ships the proactive check disabled by
  default or behind a flag left off, does **not** satisfy this issue. If an unforeseen blocker
  prevents the proactive read, the build stops and escalates to `needs-human`, naming the blocker.
  It must not ship a lesser version (PR #1450, 07:46:46Z: *"Do not silently fall back to
  reactive-only again"*).
- **FR-2:** Usage is read by running `claude -p "/usage"` and parsing the plain-text output. No other
  data source is used for the threshold decision. The direct `GET /api/oauth/usage` endpoint is
  explicitly non-viable (#1446, 05:17:05Z).
- **FR-3:** The read runs over SSH loopback to the same user on the same host, using a dedicated
  keypair (`~/.ssh/hos_loopback`, no passphrase). Its `authorized_keys` entry is restricted with
  `from="127.0.0.1,::1"`. The remote command runs **without** sourcing `claude-auth.env`, so the
  existing personal-login credential is used.
- **FR-4:** The read path must not extract, copy, duplicate, re-store, or pass on any credential
  (#1359 least-privilege; #1944: *"does not extract, duplicate, or store a second copy of
  anything"*). `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` must not
  be set in the environment of the `claude` process doing the read, even if the caller has them
  exported.
- **FR-5:** The read must not depend on a TTY or pty. It must succeed when SSH reports
  `Pseudo-terminal will not be allocated` (#1944 table, last row). The design must not add pty
  workarounds. They have been tested and do not matter.
- **FR-6:** The read must not depend on cron's minimal `PATH`. An earlier ad hoc crontab attempt
  failed with `claude: command not found` (#1446, 05:17:05Z).
- **FR-7:** The read must have a time bound. A timeout counts as a failed read (FR-21). The timeout
  value is open (Q9).
- **FR-8:** Poll interval is configurable, default **5 minutes** (#1944 10-02).
- **FR-9:** The primary read path makes no model call and adds no token cost.

### B. Parsing and classification

- **FR-10:** Parsing reuses `usage-parse.sh` (#1446, 05:17:05Z), with grep-based parsing as the
  primary path. The reference script is a verified starting point, not reviewed production code. It
  must still go through normal review.
- **FR-11: A read counts as SUCCESSFUL only if it yields a numeric current-session percentage and a
  numeric all-models current-week percentage.** Every other result is a **FAILED read**: missing
  either value, non-numeric, SSH failure, non-zero exit, timeout, or garbled output. This is the
  reference parser's own success condition (`[[ -n "$session_pct" && -n "$weekly_all_pct" ]]`).
- **FR-12: The silent-empty-session shape is a FAILED read and must never be read as 0% usage.**
  That shape is `Total cost: $0.0000 … Usage: 0 input, 0 output, 0 cache read, 0 cache write` with
  no `% used` lines (PR #1450, 07:48:32Z, Test 1). This is the #1362 / #1369 "silently reports clean"
  failure class. Reading it as 0% would turn a broken check into "all clear", the worst possible
  outcome under credits billing.
- **FR-13:** Success is decided from the parsed content, never from the process exit code. The
  empty-session shape came back with no error text.
- **FR-14: The Haiku fallback must not be trusted until it has been verified end to end outside the
  #1370 nested-`claude` sandbox restriction.** It has never run successfully (#1446, 05:17:05Z;
  #1944 Reference). Until a verification record exists (AC-21), a grep miss is a FAILED read, and the
  fallback must not feed the threshold decision. Once verified, its output remains distinguishable
  (FR-15). Note: the fallback is a model call that spends the quota it measures and falls under
  AD-16 (VF-6, Q8, Q18).
- **FR-15:** Every successful reading records how it was parsed (`parsed_via`: grep or fallback).
- **FR-16:** Per-model weekly values (e.g. `Current week (Fable)`) are captured when present and
  recorded as absent when not present. Whether they also feed the pause decision is open (Q6).
- **FR-17: Local-session breakdown fields** ("Approximate, based on local sessions on this
  machine": subagent-breakdown %, >150k-context %, 8h+-session %) are parsed when present (human
  directive, interactive session 2026-10-02). **These fields never affect the pause decision.** A
  missing, unparseable, or format-changed breakdown field must not turn a successful read into a
  failed one. A missing field is recorded as **absent, never 0** (FR-44). Their parser cannot be
  specified until D-1 is met.

### C. The pause decision

- **FR-18:** Thresholds are configurable. Defaults are **90% for the current-session window and 90%
  for the weekly window**. These defaults **supersede** the 85%/90% in the 2026-08-17 final ruling
  (PR #1450 08:05:21Z and ScottThurlow 08:08:39Z). They also supersede the 90%/95% in the 07:46:46Z
  and 07:47:00Z correction comments (#1944 10-02).
- **FR-19:** Pause when **either** window's reading is **at or above** its threshold (ScottThurlow
  08:08:39Z: *"If we exceed either threshold, we pause"*; 07:46:46Z: *"Suspend at 90%"*).
  "At or above" is a clarifying precision on the "at 90%" wording.
- **FR-20:** "Session window" means whatever window `/usage` reports as `Current session`. Its
  length (variously called 2h or 5h in the sources) must not be hard-coded or assumed.
- **FR-21:** Fail mode is configurable, default **fail-closed**. Under fail-closed, each of the
  following is treated exactly as "confirmed over threshold": a FAILED read (FR-11/12), or a missing,
  stale, or unreadable status file at the consumer (FR-36). (#1944 10-02 affirms 08-17: *"can't
  confirm under threshold" treated the same as "confirmed over threshold."*) If the default
  misfires, the operator response is to flip the setting, not change the default.
- **FR-22 [DERIVED]:** Under fail-open, a failed read does not cause a pause. It is still recorded as
  a failure in the status file and in the health gauges, so a broken check is never invisible
  (#1446 05:25:22Z: *"the check is broken" is distinguishable*).
- **FR-23: Auto-resume.** When a later successful read shows both windows below threshold, cron work
  resumes with no human action (08:05:21Z; #1944). ScottThurlow's 08:08:39Z wording, *"pause until
  the offending window resets"*, is **recorded alongside and has the same effect**. Usage within a
  window only rises, so a reading drops below threshold only when the offending window resets. The
  rule for implementation is the read-driven one: resume on the first successful under-threshold
  read. The two wordings only differ when the operator changes a threshold mid-window. In that case
  the read-driven rule applies the new threshold at the next read. This is a clarifying
  reconciliation, recorded in §8.
- **FR-24 [DERIVED]: The pause must not stop the poll.** The poll keeps running and writing status
  while cron work is paused. Otherwise FR-23 can never happen (VF-3 deadlock).
- **FR-25 [DERIVED]: Auto-resume lifts only the pause this mechanism set.** It must never clear a
  human `hos-suspend`, a timeout-breaker suspension, or a reactive-breaker suspension. This
  preserves existing `hos-suspend` behavior (VF-3).
- **FR-26:** The check gates **every worker and overseer cron cycle before any Claude session starts**
  in that cycle (#1944 title and Goal: pause *before* the hard limit).
- **FR-27:** The settings and the quota reading are machine-level, so every HOS project's worker and
  overseer on the host follows the same thresholds and the same reading (#1944 10-02: *"the
  underlying subscription quota is shared across whatever projects run on this box"*).
- **FR-28:** Pause state comes only from the dedicated `/usage` read. It is never inferred from a
  worker or overseer session transcript (VF-1/VF-2, `bin/hos-cron:2093-2100`).

### D. Settings

- **FR-29:** Thresholds (both windows), fail mode, poll interval, and staleness window are
  configurable in the existing machine-wide settings surface, never hard-coded. The location is
  confirmed by the architect (Q3; see VF-4). The location is **machine-level**. This supersedes
  08:08:39Z's "project config" (#1944 10-02).
- **FR-30 [DERIVED]:** Missing, unreadable, or out-of-range settings must never quietly disable the
  check or quietly loosen it. What happens instead is open (Q11).

### E. Status file

- **FR-31:** One fixed-path status file **per role/project** (as ruled in #1446 05:25:22Z and #1944
  10-02; see Q5 on how this fits with poll location). It is overwritten **in full** on every run,
  mirroring `sync_human_clone.sh` `write_status()` (#1276, VF-7), including the crash-still-writes
  behavior.
- **FR-32:** A run that cannot produce a usable reading still overwrites the status file with that
  failure state and a reason. So "the check is broken" (failure record), "the check hasn't run since
  boot" (no file), and "the check is healthy" (success record) are all distinguishable.
- **FR-33:** The status file contains at least: the run timestamp, outcome (success or failure plus
  a reason), session %, all-models weekly %, per-model weekly % if present, `parsed_via`, and the
  resulting pause decision with its reason (over which threshold, or failure, or stale). The reset
  text `/usage` reports may be included as-is (open: Q13).
- **FR-34:** Nothing in this feature appends to a growing file, rotates files, or keeps per-poll
  history. That includes a new crontab `>>` redirect for a poller and per-poll records in
  `audit/log/` (#1446 05:25:22Z; ScottThurlow 08:08:39Z *"we don't have ever growing log files"*).
  Whether a single audit event on pause or resume is allowed is left to the architect. Per-poll
  events are not allowed.
- **FR-35:** Consumers read only the current snapshot. There is no history to tail.
- **FR-36: Consumer contract.** A worker or overseer cycle reads the status file. If its timestamp
  is within the **staleness window**, the cycle applies the threshold and fail-mode settings to that
  reading. If the file is stale, missing, truncated, or unparseable, the cycle applies the fail mode.
  The staleness window is configurable and must be **wider than the poll interval**. Default
  **15 minutes**, the issue's worked example, which allows two missed 5-minute polls (#1944 10-02).

### F. Visibility

- **FR-37:** A proactive pause files a `needs-human` issue, reusing #1450's pattern (VF-8): a stable
  title prefix distinct from the reactive and timeout breakers, fail-closed dedup, and at most one
  open issue per pause episode, never one per poll. A failed issue filing does not prevent the
  pause.
- **FR-38:** On auto-resume, the open proactive-pause issue is auto-closed with a comment. #1450's
  pattern includes auto-close on recovery (#1944 Reference; `bin/hos-cron:2181-2202`).
- **FR-39:** The issue says why the pause happened: which window crossed which threshold at what
  reading, or that the check failed or went stale (with the failure reason) under fail-closed.

### G. Reactive backstop

- **FR-40:** #1450's reactive breaker code in `bin/hos-cron` is left **unchanged**, including its
  current commented-out state (`:2090-2155`) and its live auto-close half (`:2181-2202`). This issue
  adds the proactive check alongside it and does not replace it (08:08:39Z: *"If hard limit hit,
  pause too"*; #1944). Re-enabling the breaker is **out of scope** for this build and escalated to
  the human (C-1).

### H. Prometheus export (human directive, interactive session 2026-10-02)

- **FR-41:** Each poll also writes a Prometheus textfile-collector `.prom` file into the host's
  **existing** `node_exporter` textfile-collector directory. No new listening service, port, or
  exposure surface (#1944 10-02 Dashboarding). The mechanism and directory need confirming (Q4).
- **FR-42:** Gauges for raw current values: current-session %; all-models weekly %; per-model
  weekly % (one series per model present, e.g. Fable); subagent-breakdown %; >150k-context %;
  8h+-session %. Check-health gauges: last-successful-read timestamp, parse status, paused state.
- **FR-43:** **Raw current values only.** No deltas, rates, cumulative transforms, or forecasts are
  computed in the exporter or the status file. Those belong in PromQL/Grafana at query time.
- **FR-44:** A value the poll did not obtain is an **absent series, never 0**. This covers any
  breakdown field, any per-model weekly value, and session/weekly on a failed read. Health gauges are
  always emitted. Writing 0 for an unknown value would repeat the FR-12 "silently clean" failure on
  the dashboard.
- **FR-45:** The `.prom` file is replaced in full on every run (FR-34), and Prometheus must never
  scrape a half-written file (mechanism: Q4).

### I. Grafana dashboard (human directive, interactive session 2026-10-02)

- **FR-46:** Deliverable: a provisionable Grafana dashboard JSON with:
  (1) session % and weekly % sawtooth over time, with the threshold line at the configured value
  (90% default) and pause events annotated (from the paused-state gauge);
  (2) a `predict_linear`-based early-warning panel;
  (3) subagent attribution over time;
  (4) >150k-context % and 8h+-session % over time, for comparison against the sawtooth.
  All derived views are computed in PromQL (FR-43).

### J. Host setup

- **FR-47:** The SSH-loopback setup (keypair plus the restricted `authorized_keys` entry) is a
  documented one-time host-local manual step, like `#728`'s `claude setup-token`. It is **not**
  provisioned by `hos_install.sh` (#1944 Q2; runbook location Q14 / VF-5).
- **FR-48:** An idempotent preflight check confirms the key exists and a loopback `/usage` read
  actually returns a SUCCESSFUL read (FR-11), rather than assuming setup was done. If the check
  fails, it says so plainly. The failure surfaces as a failed read, so fail mode applies, and is
  never silent.

### K. Governance

- **FR-49:** Changes to `bin/hos-cron` (and anything else under `bin/**`) are protected surface and
  need human merge approval (CODEOWNERS). This is expected and not a blocker (#1944 Process note).

---

## 3. Dependencies

- **D-1: A real captured `/usage` sample containing the local-sessions breakdown section** is
  needed before the parser for subagent / >150k-context / 8h+-session can be specified. None of the
  sources captured it, and `usage-parse.sh` parses only the session and weekly lines. This does
  **not** block the threshold decision (FR-17). The sample should also show whether percentages
  can exceed 100 once credits are in use, so the parser does not clamp or reject them.
- **D-2: Haiku fallback end-to-end verification** outside the #1370 constraint (FR-14 / AC-21).
- **D-3: Confirmation of the textfile-collector mechanism and directory** on this host (Q4).
  Needed for FR-41. The sandbox could not observe it (verification gap a).

---

## 4. Acceptance criteria

The `/usage` cases use captured fixtures or a stubbed SSH/`claude` boundary unless stated otherwise.
Every criterion applies to both the worker and overseer roles.

- **AC-1:** A real-shape fixture (session 4%, weekly-all 29%, Fable 6%; #1446 05:17:05Z) gives a
  SUCCESSFUL read, no pause, a success status record with `parsed_via=grep`, and the matching gauges.
- **AC-2 (boundary):** session 90%, weekly 10% → pause. session 89%, weekly 89% → no pause.
- **AC-3:** session 10%, weekly 90% → pause. The issue names the weekly window.
- **AC-4 (negative, #1362/#1369 class):** The silent-empty-session fixture (exact text from PR
  #1450 07:48:32Z, Test 1) → FAILED read, with a reason that identifies the empty shape. Under
  fail-closed → pause. The session/weekly gauges are **absent**, and **no artifact anywhere records
  0%**.
- **AC-5 (negative):** Output with a session line but no weekly line, or the reverse → FAILED read.
- **AC-6 (negative):** Missing key, refused connection, or rejected `from=` (SSH failure) →
  FAILED read → fail mode.
- **AC-7 (negative):** A `claude` stub that hangs → FAILED read within the configured bound. The
  poll does not hang the cycle.
- **AC-8 (negative, consumer side):** Status file older than the staleness window → fail mode.
  Missing file → fail mode. Truncated or garbled file → fail mode. Each case produces its own
  distinct reason.
- **AC-9:** Fail-open setting plus empty-session fixture → no pause. The status file records the
  failure, and the parse-status health gauge shows the failure.
- **AC-10 (auto-resume):** Paused at session 92%. The next read shows 40%/30% → the next cycle runs
  with no human action, and the proactive-pause issue is auto-closed.
- **AC-11 (negative):** A human `hos-suspend` marker (or a timeout-breaker one) exists. An
  under-threshold read does **not** remove it, and the cycle stays suspended.
- **AC-12 (no deadlock):** While paused, the poll keeps running and keeps overwriting the status
  file. A pause can always end through FR-23.
- **AC-13:** After N ≥ 3 runs mixing success and failure, exactly one status file and one `.prom`
  file exist for the scope, each with bounded size. A failure run overwrites a previous success
  record. No new files or appended lines appear anywhere, including `audit/log/` per poll.
- **AC-14:** Five consecutive over-threshold polls → exactly one open proactive-pause issue. If the
  dedup query fails → no issue is filed, and the pause is still applied.
- **AC-15 (negative, credential):** With `CLAUDE_CODE_OAUTH_TOKEN` exported in the caller's
  environment, the `claude` process doing the read does not have it. A static check confirms the
  read path never sources `claude-auth.env`.
- **AC-16:** On a host with the loopback set up, a real unattended cron-context read without a pty
  gives a SUCCESSFUL read (a manual, recorded run is acceptable).
- **AC-17:** `bin/hos-cron`'s reactive-breaker block (`:2090-2155`) and its auto-close block
  (`:2181-2202`) are byte-identical before and after the change.
- **AC-18:** A fixture with no breakdown section → a SUCCESSFUL read with an unchanged decision, and
  the breakdown gauges are absent (not 0). After D-1, a fixture with the breakdown section → those
  gauges are present with the raw values.
- **AC-19:** The `.prom` output has only raw-value and health gauges, with no
  delta/rate/forecast/cumulative series. The change adds no listening socket.
- **AC-20:** The dashboard JSON loads through Grafana provisioning without errors and contains the
  four panels in FR-46. Its threshold line follows the configured value. Its early-warning panel
  uses `predict_linear`. Its pause annotations come from the paused-state gauge.
- **AC-21 (Haiku):** Until a verification record exists, a grep-miss fixture → FAILED read, and a
  stub confirms **no model call** was made. The verification record is a documented run outside the
  #1370 sandbox against real failed-grep input, showing the fallback's actual output. It is
  required before the fallback can feed the decision.
- **AC-22:** The preflight check run twice changes nothing on the second run. With the key removed,
  it reports the missing key plainly and exits non-zero.
- **AC-23:** Changing the session threshold to 80 in the machine-level settings → pause at 80% with
  no code change, and every project on the host picks it up.
- **AC-24 (negative, VF-2):** A worker transcript containing "usage limit reached" or any threshold
  wording, while `/usage` reads under threshold → no proactive pause.
- **AC-25:** A primary-path read reports `$0.0000` / `0 input, 0 output`, meaning no model call.
- **AC-26:** The existing suite (`scripts/framework/run_tests_inner_loop.sh`) passes, including
  T4.1 once Q8 is resolved.

---

## 5. Explicit non-goals

- Re-enabling, rewriting, or re-scoping #1450's reactive breaker (C-1 is for the human).
- Pausing interactive or human-proxy sessions. The purpose is to leave headroom *for* them.
- A cron-specific `/usage`-capable token, or any re-storing of the personal credential (rejected
  under #1359).
- Revisiting whether `/usage` works under `CLAUDE_CODE_OAUTH_TOKEN`, or TTY/pty theories. Closed.
- Building a historical usage log. Prometheus TSDB provides history (#1944 10-02).
- Provisioning SSH loopback through `hos_install.sh`.

---

## 6. Open questions for the architect

From #1944 (carried over unchanged):
- **Q1: Where does the poll run?** Inside `bin/hos-cron`, or as a standalone timer or script? It must
  satisfy FR-24 (the poll survives a pause) and FR-34 (no new appending log).
- **Q2: SSH-loopback setup runbook plus the idempotent preflight check (FR-47/48).**
- **Q3: Exact settings location** (FR-29). VF-4 is input: `machine-accounts.env` is a repo file that
  `hos-cron` does not read, while `~/.config/hos/` is the machine-level directory `hos-cron` does
  read.
- **Q4: The textfile-collector mechanism and directory on this host**, and how the `.prom` write is
  made atomic for scraping (FR-45).

**NEW from this pass:**
- **Q5 (NEW):** How the ruled per-role/project status file (FR-31) fits a machine-level quota and
  settings. If Q1 picks a single machine-level poller, how is "one fixed path per role/project"
  satisfied without per-consumer history or N redundant polls? The ruling is not reopened here. The
  architect must show how the chosen design complies with it, or bring a conflict back to the human.
- **Q6 (NEW):** Do per-model weekly windows (e.g. Fable) feed the pause decision, or only the
  all-models weekly? The sources say only "weekly window". **Escalate to the human.** The PM will not
  infer this.
- **Q7 (NEW):** What happens to a Claude session already **running** when a poll crosses threshold?
  Is it left to finish, or interrupted? The sources only rule on gating before a cycle (FR-26).
  **Escalate to the human.**
- **Q8 (NEW):** How the `claude -p "/usage"` call site fits with ADR-1643 AD-16 / T4.1 (VF-6). Is it
  a named exemption, routed through `invoke_agent.sh`, or something else? The same question applies
  to the Haiku fallback.
- **Q9 (NEW):** The default time bound for the `/usage` read (FR-7), and whether it is configurable.
- **Q10 (NEW):** Under fail-open, should a persistent check failure still file a `needs-human`
  issue? The sources rule on visibility for a *pause* only. **Escalate to the human.**
- **Q11 (NEW):** What happens with invalid settings (FR-30), e.g. a threshold above 100 or below 0,
  a non-numeric value, a staleness window ≤ the poll interval, or an unknown fail mode. Fail closed
  plus loud error is the conservative reading. **Escalate to the human** for the rule.
- **Q12 (NEW, security):** Should the loopback `authorized_keys` entry also carry `command=` and
  `no-*` restrictions so the key can only run the `/usage` read? Not ruled. Route to
  `security-reviewer`. A change to the ruled setup goes back to the human.
- **Q13 (NEW):** Should reset times (the `/usage` reset text) go into the status file and/or appear
  as gauges? The text has no year (`Aug 17, 7:20am (UTC)`).
- **Q14 (NEW):** Runbook location. #728's auth runbook is `CRON-SETUP.md` §2, not
  `MACHINE-ACCOUNTS-SETUP.md` (VF-5).
- **Q15 (NEW):** One machine-wide trip with FR-37 applied per project files one issue per project
  repo. Is that the intended visibility, or should there be a single machine-scoped issue?
- **Q16 (NEW):** Should the pause reuse the `hos-suspend` marker? If so, how are FR-24 and FR-25
  satisfied given that it is project-keyed and role-blind and has no owner field (VF-3)?
- **Q17 (NEW):** Is a single audit event per pause/resume transition wanted? Per-poll events are
  ruled out (FR-34).
- **Q18 (NEW):** If the Haiku fallback is ever verified, which credential and quota does it run
  under, given that it spends the quota it measures?

---

## 7. Traceability

| Req | Source |
|---|---|
| FR-1 | PR #1450 bot correction 2026-08-17T07:46:46Z; ScottThurlow 08:08:39Z; #1446 07:47:00Z; #1944 History |
| FR-2 | ScottThurlow 08:08:39Z; #1944 History; #1446 05:17:05Z (`/api/oauth/usage` non-viable) |
| FR-3 | #1944 "What's new today (2026-10-02)" |
| FR-4 | #1944 "What's new" + History (#1359 rejection) |
| FR-5 | #1944 empirical table, last row |
| FR-6 | #1446 05:17:05Z (`command not found`); #1944 Q1 |
| FR-7 | #1944 History restating 08-17 ("no reading, error, timeout") |
| FR-8 | #1944 10-02 "Poll interval" |
| FR-9 | #1944 "Confirmed separately: `/usage` costs nothing" |
| FR-10, FR-11 | #1944 Reference; #1446 05:17:05Z (`usage-parse.sh` `parse_grep`) |
| FR-12, FR-13 | PR #1450 07:48:32Z Test 1; #1944 History; #1944 Related (#1362/#1369) |
| FR-14 | #1944 Reference; #1446 05:17:05Z |
| FR-15 | #1446 05:17:05Z (`parsed_via`); #1446 05:25:22Z (status contents) |
| FR-16 | #1446 05:17:05Z (Fable optional, null when absent) |
| FR-17 | Human directive, interactive session 2026-10-02 |
| FR-18 | #1944 10-02 "Thresholds" (supersedes PR #1450 08:05:21Z, ScottThurlow 08:08:39Z, 07:46:46Z, #1446 07:47:00Z) |
| FR-19 | ScottThurlow 08:08:39Z ("either"); PR #1450 07:46:46Z ("at 90%") |
| FR-20 | #1944 ("2h"); ScottThurlow 08:08:39Z ("2 hour"); human directive 2026-10-02 ("2h/5h") |
| FR-21 | #1944 10-02 "Fail-open/fail-closed" + "consumption contract"; PR #1450 08:05:21Z; overseer 08:37:00Z |
| FR-22 | [DERIVED] #1446 05:25:22Z |
| FR-23 | PR #1450 08:05:21Z; #1944 History; ScottThurlow 08:08:39Z ("until the offending window resets", recorded as equivalent) |
| FR-24, FR-25 | [DERIVED] FR-23 + VF-3 (`bin/hos-suspend`, `bin/hos-cron:263-283`) |
| FR-26 | #1944 title + Goal |
| FR-27 | #1944 10-02 "Thresholds" (shared-quota rationale) |
| FR-28 | `bin/hos-cron:2090-2107` (operator disable 2026-09-01) |
| FR-29 | #1944 10-02 "Thresholds" (machine-level; supersedes 08:08:39Z "project config"); #1944 Q3 |
| FR-30 | [DERIVED] FR-21 intent + #1362/#1369 class |
| FR-31, FR-32 | #1446 05:25:22Z; #1944 10-02 "Status file"; `sync_human_clone.sh:120-133` |
| FR-33 | #1446 05:25:22Z (percentages, `parsed_via`, timestamp, breaker state) |
| FR-34, FR-35 | #1446 05:25:22Z; ScottThurlow 08:08:39Z; #1944 10-02 |
| FR-36 | #1944 10-02 "consumption contract" + "Poll interval" |
| FR-37, FR-39 | #1944 10-02 "Visibility on trip"; `bin/hos-cron:2056-2080, 2132-2154` |
| FR-38 | #1944 Reference ("auto-close on recovery"); `bin/hos-cron:2181-2202` |
| FR-40 | ScottThurlow 08:08:39Z; PR #1450 07:46:46Z; #1944 10-02 + Reference; VF-1 |
| FR-41 | #1944 10-02 "Dashboarding"; human directive 2026-10-02 |
| FR-42, FR-43, FR-44 | Human directive, interactive session 2026-10-02 |
| FR-45 | #1944 10-02 "Dashboarding" + FR-34 |
| FR-46 | Human directive, interactive session 2026-10-02 |
| FR-47 | #1944 Q2 |
| FR-48 | #1944 Q2 ("idempotent check … rather than assuming") |
| FR-49 | #1944 Process note; overseer PR #1450 08:37:00Z |
| D-1 | Human directive 2026-10-02 (NOTE on breakdown format) |
| D-2 | #1944 Reference; #1446 05:17:05Z |
| D-3 | #1944 10-02 "Dashboarding" + Q4 |

---

## 8. Source conflicts and supersessions (how each was recorded)

- **S-1, thresholds:** 90/95 (PR #1450 07:46:46Z, #1446 07:47:00Z) → 85/90 (08:05:21Z, ScottThurlow
  08:08:39Z) → **90/90 (#1944 10-02, authoritative)**. Recorded in FR-18.
- **S-2, settings scope:** "project config" (08:08:39Z) → **machine-level (#1944 10-02)**. FR-29.
- **S-3, resume wording:** "pause until the offending window resets" (08:08:39Z) and "auto-resume on
  a subsequent under-threshold read" (08:05:21Z, #1944). Same effect, both recorded. The read-driven
  rule is the operative one (FR-23). Clarifying.
- **S-4, the credential question:** "did not work" (ScottThurlow 2026-08-18T04:20:43Z) and the
  retracted success report (07:57:29Z) → **closed by #1944 10-02 SSH loopback**. Not reopened.
- **C-1, CONFLICT, escalated:** #1944 says "keep #1450's reactive breaker as-is" as a hard-limit
  backstop, but at HEAD that breaker is **disabled** (operator, 2026-09-01; VF-1). FR-40 keeps it
  unchanged, so no ruling is overridden. **The human must decide** whether a scoped re-enable is
  wanted as a separate issue. Until then, the proactive check (with fail-closed) is the only live
  protection.
- **C-2, settings location:** #1944's suggested `machine-accounts.env` is not machine-level in
  practice (VF-4). Recorded as input to Q3, not resolved.
- **C-3, runbook location:** #1944 "likely `MACHINE-ACCOUNTS-SETUP.md`" vs the #728 runbook actually
  being `CRON-SETUP.md` (VF-5). Input to Q14.
- **C-4, governance:** The ruled raw `claude -p "/usage"` vs the AD-16 / T4.1 single-invocation-site
  rule (VF-6). Q8.
- **C-5, scoping tension:** status file per role/project (ruled) vs machine-level quota and settings
  (ruled). Not a contradiction, but the design has to satisfy both. Q5.

---

## Escalation flag (CORE self-flag)

RISK: HIGH. The feature gates every autonomous cycle on the host, changes `bin/hos-cron`
(protected), and under fail-closed a defect stops all autonomous work. Under a fail-open defect,
credits billing continues silently.
CONFIDENCE: 80%. High confidence in the ruled items and in VF-1/VF-3/VF-6, all grep-verified.
Lower confidence in the breakdown-section format (D-1) and in the host's exporter setup (Q4). Neither
could be observed from this session.

Classification: **additive** for FR-1 to FR-21, FR-23, FR-26 to FR-29, and FR-31 to FR-49. These
write down behavior already ruled in the cited sources. **Structural / needs human confirmation:**
FR-22, FR-24, FR-25, and FR-30 ([DERIVED]), plus the escalated questions Q6, Q7, Q10, Q11, and C-1.

## Human Review Required

1. **C-1:** The reactive backstop is disabled at HEAD. Confirm that the proactive check alone is
   acceptable for now, and say whether you want a separate scoped re-enable issue.
2. **[DERIVED] FR-22, FR-24, FR-25, FR-30:** Confirm these. They follow from the rulings but are not
   stated in them.
3. **Q6, Q7, Q10, Q11:** Product rulings needed. Per-model weekly thresholds, in-flight session
   behavior, fail-open visibility, and invalid-settings behavior.
4. **D-1:** Provide a real `/usage` capture that includes the "Approximate, based on local sessions
   on this machine" breakdown section.
