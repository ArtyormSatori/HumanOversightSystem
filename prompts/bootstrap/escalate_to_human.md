# Prompt Artifact — escalate_to_human.sh

| Field | Value |
|---|---|
| **Generated file** | `bootstrap/escalate_to_human.sh` |
| **Description** | #1644 T3.0a record-first needs-human escalation write primitive |
| **Date** | 2026-09-30 |
| **Model** | claude-opus-5-5 |
| **Risk level** | HIGH (coder/TD declared MEDIUM; risk-assessor raised on deterministic floors) |
| **Human review status** | ⬜ Pending |

---

## Prompt

Dispatched by the autonomous worker to the `coder` subagent (exact text):

```
You are implementing the ESCALATION-SCRIPT half of #1644 slice T3.0a in the HOS repo at /home/scott/Code/HumanOversightSystem/Worker (branch `worker-1644-t3-0a-no-idle-selection-260930181001-4069397`, already checked out — do NOT create or switch branches, do NOT commit, do NOT push, do NOT file issues, post comments, or touch labels; never run the new script against real GitHub).

Binding design: `docs/v0.7.0/TECHNICAL-DESIGN-1644-T3.0a-no-idle-selection.md` (architect-approved). Read it in full, especially §4 (CLI, environment, ordered R1–R3 / W1–W5 procedure, decision table, idempotency marker + key, exit codes 0/1/2/4/5/6 — 3 unused, exact stdout/stderr lines, audit event JSON keys), §5 (prose deltas), §7.3 (tests T-ESC1..T-ESC23), and the architect corrections in §10 (R3 page-bound → exit 6 `supersede-undeterminable`). Controlling ADR: `docs/v0.7.0/ADR-1644-stage-per-cycle.md` (AD-C6 H5, AD-C7, AD-C10, Erratum 1).

YOUR FILES (only these):
1. `bootstrap/escalate_to_human.sh` (new, executable). Follow sibling conventions exactly: read `bootstrap/post_comment.sh` and `bootstrap/edit_issue.sh` first (SCRIPT_DIR, err/warn, repo-slug resolution, token mint into mktemp + source + delete, revoke via curl, `--body` rejection message). Source `bootstrap/lib/comment_format_check.sh` for `hos_cfc_check_at_path_literal`. Audit via `scripts/oversight/lib/audit_log.sh::audit_write_event` with the exact best-effort shape of `bootstrap/submit_pr.sh::_hos_audit_stale_base_merge`. Revoke in an EXIT trap. Reads: single `gh api` with explicit `?per_page=100&page=<p>`, never `--paginate`, never `-f/-F/--field/--raw-field`; writes: `jq -n --rawfile ... | gh api --method POST ... --input -`. No `gh issue edit`, no `gh issue comment`, no `body=@`. All validation before minting. Header comment block documenting usage, like siblings.
2. `tests/automation/test_escalate_to_human.py` (new) — T-ESC1..T-ESC23, harness modeled on `tests/automation/test_edit_issue.py` (copy script into tmp/bootstrap, stub get_app_token.sh exporting GH_TOKEN and HOS_BOT_LOGIN='hos-worker-hos[bot]', copied lib/comment_format_check.sh, PATH stubs for gh/git/curl, stub tmp/scripts/oversight/lib/audit_log.sh capturing audit JSON, gh stub logging METHOD PATH and capturing stdin bodies). Compute expected key with hashlib per §4.5.
3. `bootstrap/worker-cron-prompt.md` — one paragraph per §5 (label name in backticks only; never a quoted "needs-human"/'needs-human' literal — see `test_excluded_labels_is_defined_in_exactly_one_place`; do NOT touch "Pick the first non-blocked candidate").
4. `docs/LABELS.md` — `needs-human` row Writers gain the script; Work-selection exclusion text gains the one sentence per §5.
5. `CLAUDE.md` — one row in "Canonical entry points by task": `Recording a human wait (question comment, then needs-human, idempotent) | bootstrap/escalate_to_human.sh`.

Do NOT touch `.claude/agents/worker.md` (deferred to T3.6), the selector or its tests (another coder owns them), SCRIPTS-INDEX.md, or framework_consumer_files.txt.

Verify: `scripts/oversight/.venv/bin/python -m pytest tests/automation/test_escalate_to_human.py tests/automation/test_edit_issue.py -q` plus any test that greps worker-cron-prompt.md / LABELS.md / CLAUDE.md (grep tests/ for those filenames and run the matching modules). Run `shellcheck bootstrap/escalate_to_human.sh` if available.

Return: files changed, test results (counts), any deviation from the TD and why, and your self-flag (RISK/CONFIDENCE/BLAST RADIUS per AGENTS.md). If the TD is ambiguous or wrong anywhere, say so explicitly.
```

## Constraints Specified

- Binding spec: `docs/v0.7.0/TECHNICAL-DESIGN-1644-T3.0a-no-idle-selection.md` §4, §5, §7.3, §10.
- Record-first ordering: comment, confirm, label, verify, audit; halt before the label on any record failure.
- Must refuse PRs, closed issues and `release-request` issues; must never remove `needs-ai`.
- Must NOT: use `--paginate`, `-f`/`-F`, `body=@`, `gh issue edit` or `gh issue comment`; run against real GitHub; touch `.claude/agents/worker.md`.

## Refinement History

Refinements after review, if any, are recorded in the sign-off register and commit history of this PR.

## Human Review Notes

<!-- After human review, record findings here. -->

---

## Reproducibility Check

To verify this prompt still produces equivalent output in a new session:
1. Open a fresh Claude Code session
2. Paste the prompt above verbatim
3. Compare key logic paths against `bootstrap/escalate_to_human.sh`
4. Note any drift in a new version artifact (`escalate_to_human.v1.md`)
