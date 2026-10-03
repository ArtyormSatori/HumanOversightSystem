# TECHNICAL DESIGN — ADR-1944: proactive Claude usage-threshold pause. A loopback poller writes one reading, `hos-cron` gates every cycle on it, and the dashboard path can never touch the decision

**Status:** DRAFT-1 + **Architect round 1: APPROVED WITH CHANGES (2026-10-03).** The architect applied its changes directly; each is marked "Architect round 1". The rulings are in §9 and the AD changes are in ADR-1944 Amendment 1. No further design round is needed unless `technical-design` disputes a change. Original status text: Waiting on `architect` review (iteration 1 of a 5-round cap). This document is the implementation contract for ADR-1944. **S1 (poller) and S2 (`hos-cron` gate) are fully specified and codeable. Nothing in them is TBD.** Where this design adds to an AD or tightens it, the change is listed in §9 as a TD-O question with a binding interim choice, so the coder never waits on the answer. This document contains no application code.
**Date:** 2026-10-02
**Author:** technical-design
**Baseline:** local `HEAD` = `03aebf13d` (the three #1944 design commits on top of `9f6a4f05f`). `origin/main` = `ba1e67b97`. `git diff HEAD origin/main` touches only `contract/dimensions/**`, `packs/*/dimensions.yaml`, `tests/automation/test_dimension_registry_data.py` and the two #1944 docs. **Every file this design cites is byte-identical at both commits**, so every line number below holds on `origin/main` (TD-VF-1).
**Consumes:** `docs/v0.7.0/ADR-1944-proactive-usage-pause.md` (binding), `docs/v0.7.0/REQUIREMENTS-1944-proactive-usage-pause.md` (incl. Amendment 1), the verbatim 2026-10-02 loopback `/usage` capture (embedded in §1.9; provenance there), #1944 body, #1446 comments 05:17:05Z / 05:25:22Z / 07:47:00Z, the PR #1450 thread, `bin/hos-cron`, `bin/hos-suspend`, `bootstrap/{query_issues,create_issue,edit_issue,post_comment}.sh`, `bootstrap/hos_install.sh`, `scripts/framework/{protected_surfaces,framework_consumer_files,consumer_agents}.txt`, `contract/sandbox-policy.template.json`, `docs/SANDBOX-POLICY.md`, `docs/CRON-SETUP.md`, `docs/LABELS.md`, `scripts/automation/lib/cycle_log.py`, `tests/framework/test_agent_invocation_migration.py`, `tests/automation/test_hos_cron.py`, and the live faberix node_exporter (read-only: `--version`, `--help`, unit file, textfile directory listing).
**Consumers:** `architect` (review), then the coder via **four** slice PRs (S1 → S2, S1 → S3 → S4), plus `unit-test`, `system-test`, `security-reviewer` (§3.7, §3.9, TD-VF-9), and `infra-reviewer` (§5, §6).
**Scope note:** This document says what the code must do: file paths, function signatures, grammars, file formats, orderings, exit codes, and test names. It contains no implementation.

---

## Rulings taken as given, not re-litigated

Requirements Amendment 1 and ADR-1944 bind. In particular: standalone `*/5` poller (FR-50); SSH loopback with the personal-login credential (FR-3); `>=` (FR-19); 90/90 defaults (FR-18); fail-closed default (FR-21); overwrite-in-place status files (FR-31); the #1450 reactive breaker is obsolete and untouched (FR-40); raw values only in the export (FR-43); every file on the decision path lives under `bin/` (AD-2); a stateless gate, never the `hos-suspend` marker (AD-7); no Haiku fallback in v1 (AD-4). ADR §5 items are carried forward **unresolved** in §11.

---

## 0. Verification findings — every ADR premise re-derived

### TD-VF-1 (process) — the line numbers hold on `origin/main`.

*Architect round 1:* the branch concern is moot. All four #1944 docs are now on `interactive-1944-proactive-usage-pause-design`, and ESC-T3 is closed. The architect re-checked the anchors that its rulings rely on (`:864-870`, `:1839-1841`, `:247`, `:349`, the T4.1/T4.2 ledgers) on that branch, and they match. The 4 commits only on `origin/main` (the #1943 W5b merge) touch no file this design cites, so every anchor below holds on `origin/main`.

ADR anchors re-derived against `bin/hos-cron` (2245 lines):

| Anchor | ADR cites | Actual |
|---|---|---|
| `hos-suspend` marker check | `:258-286` | `:258-286` ✓ (`_SUSPEND_FILE` `:263`) |
| Overlap lock acquired | — | `:304-332` (EXIT trap `:332`) |
| `_audit()` | — | `:362-365` |
| Wakeup consume (`rm -f`) | — | `:808` (before the gate — TD-VF-12) |
| `_REPO_SLUG` | — | `:820-821` |
| GitHub auth / identity guard | — | `:831-853` |
| Git credentials block | `:855-868` | `:855-868` ✓ (closing `fi` `:868`, blank `:869`) |
| Claude subscription auth | `:870` | `:870` ✓ (header comment), source `:883-886` |
| Optional model auth probe | `:895-904` | `:894-904` ✓ (the `"$CLAUDE_BIN" --print` call is `:899`) |
| Halt check | — | `:906-933` |
| Worktree hygiene invocation | — | `:1258` (after the gate) |
| `_TIMEOUT_BIN` (private copy) | — | `:1839-1841` (Architect round 1: re-verified) |
| Session launch `--print` | `:1849` | `:1849` ✓ |
| #1446 breaker block (commented out) | `:2090-2155` | `:2090-2155` ✓ |
| #1446 live auto-close half | `:2181-2202` | `:2181-2202` ✓ |
| AF-3 first-page dedup sites | `:2066, :2134, :2164, :2188` | **`:954`, `:2063`, `:2136` (commented), `:2167`, `:2191`** — the shape is as ADR describes, the coordinates are off by 2–3, and there is a fifth site at `:954` (agent-availability) that the ADR did not list. Relevant to ESC-4 only. |
| T4.1 | `test_agent_invocation_migration.py:98-132` | `:98-132` ✓ |

### TD-VF-2 (HIGH) — `bootstrap/query_issues.sh --list` is not a complete reader. AD-8's first suggested dedup option is the AF-3 bug with a higher ceiling.

`query_issues.sh` `--list` (`:258-272`) issues **one** `gh api "repos/…/issues?per_page=100&…"` call. It has no `--paginate` and no page loop, and it does not refuse truncated output. Only the edge modes (`:319-355`) paginate and refuse truncation. With more than 100 open `needs-human` issues it silently drops the overflow, which is exactly AF-3's fail-open dedup. AD-8 offers "`bootstrap/query_issues.sh --list`, **or** the equivalent `gh api --paginate`". **BINDING:** S2 uses `gh api --paginate` (§4.4). `query_issues.sh` is not used for dedup. Making `--list` complete is the natural fix for ESC-4 as well, but it changes output for every existing caller, so it stays out of #1944 (§10 ESC-T2).

### TD-VF-3 (HIGH) — the issue wrappers do not ship to consumers, but `bin/hos-cron` does. The gate therefore uses raw `gh`, not the wrappers.

`hos_install.sh:1882-1894` ships only `get_app_token.sh`, `hos_repo_sync.sh`, `validate_setup.sh`, `apps.env.template` and `sync_apps_env.sh` from `bootstrap/`. `framework_consumer_files.txt:24-36` adds only `create_branch.sh`, `lib/branch_ownership.sh` and `lib/sandbox_paths.sh`. **`create_issue.sh`, `edit_issue.sh`, `post_comment.sh` and `query_issues.sh` are not on any consumer.** If `bin/hos-cron` called them, issue filing would fail on every consumer, with only a log line, and FR-37 would be silently dead there. There are three further reasons:
- Each wrapper mints its own token and resolves the repo slug from `git remote get-url origin`. That bypasses `_REPO_SLUG` (`:820`, which honours `HOS_REPO_SLUG`), so the dedup query and the filing could target different repos.
- `create_issue.sh` revokes its token with a `curl` that has no `--max-time` (`:84`).
- CLAUDE.md's wrapper rule exists for sandboxed **agent** sessions, so that commands are allowlistable. `hos-cron` runs unsandboxed with an already-minted `GH_TOKEN`, and **every** existing `hos-cron` issue path (`:954-968`, `:2062-2081`, `:2164-2178`, `:2190-2202`) uses raw `gh`.

**BINDING:** the gate uses raw `gh` with `--body-file` (never `--body "$(…)"`) under `_REPO_SLUG`, bounded by `timeout`. This departs from the orchestrator's stated preference, not from any AD (AD-8 itself names `gh api --paginate`). It is listed for confirmation as TD-O-2.

### TD-VF-4 (HIGH) — the ADR handled T4.1 but missed T4.2. A bounded SSH read in bash is a fourth private `_TIMEOUT_BIN` copy and fails the existing suite.

`test_agent_invocation_migration.py:135-200` (T4.2) asserts that the set of files in `scripts/`, `bootstrap/`, `bin/` with a code line matching `_TIMEOUT_BIN\s*=` is **exactly** `{validate_agents.sh, validate_scripts.sh, bin/hos-cron}`. AD-6 binds `<timeout_bin> --kill-after=5 …` in `bin/hos-usage-poll`. Naming the variable anything else would pass the test by exploiting a blind spot, the same thing AD-5 forbids for T4.1. ~~**BINDING:** the poller names the variable `_TIMEOUT_BIN`, and S1 adds `"bin/hos-usage-poll"` to `_T4_2_EXPECTED_TIMEOUT_BIN_COPIES` … `…_is_exactly_four`.~~ **Architect round 1 (TD-O-1 OVERRIDDEN):** the bounded SSH read moves into Python (`usage_pause.py read-usage`, §3.1/§3.6 P8). No `_TIMEOUT_BIN` exists anywhere in the poller, and **the T4.2 ledger and test name do not change**. The finding stands: it is the reason for the override.

### TD-VF-5 (HIGH) — S2 breaks nearly every existing `test_hos_cron.py` test unless the shared fixture writes a fresh reading.

`CronEnv` (`test_hos_cron.py:86-500`) builds a fake HOME with no `~/.ssh/hos_loopback`, no `usage-pause.conf` and no reading file. After S2, every test that drives the launcher past `:868`, which is most of the 4,600-line suite, would pause with `poller_not_installed`. A second problem: the `gh` stub's generic `*"labels=needs-human"*)` case (`:238`) answers `0`, and `jq` cannot iterate that, so a new dedup query would fall into it and read as a failed query. **BINDING** S2 harness changes are in §4.6: a default fresh under-threshold reading written by `CronEnv.run()`, and a dedicated `gh` stub case placed before `:214`.

*Architect round 1, a third problem:* `test_hos_cron.py:1768-1839` copies `bin/hos-cron` and `bin/lib/git-credentials.sh` into a temporary `repo/bin/` and runs that copy. Without `bin/lib/usage_pause.py` next to it, the gate reaches `check_error` and pauses. §4.6 item 4 covers this.

### TD-VF-6 (MEDIUM) — `_audit` with one space-joined string records **one** field, not several.

`cycle_log._parse_args` (`scripts/automation/lib/cycle_log.py:69-83`) splits each argv element on the first `=`. So `_audit cycle-usage-pause "role=worker reason=x"` records `{"role": "worker reason=x"}`. The ADR's example (AD-8) uses that single-string form. The existing timeout breaker (`:2054`) has the same latent defect. That one is out of scope, and I did not file it. **BINDING:** every new `_audit` call passes one `key=value` per argv element (§1.6).

### TD-VF-7 (MEDIUM) — a title-prefix match can cross projects that share a repo.

`"[PAUSED] … paused on hos"` is a prefix of `"[PAUSED] … paused on hos-dev"`. `projects.conf` permits two projects that point at one repo. **BINDING:** dedup and auto-close match the **exact title** (`.title == $t`), not `startswith`. The ADR's "stable prefix" becomes the stable full title (§1.7). This is clarifying and stricter.

### TD-VF-8 (MEDIUM) — AC-25 cannot be shown from the real success output, which has no cost footer.

The D-1 capture (§1.9) has no `Total cost:` / `Usage:` lines. Those appear only in the **failure** (empty-session) shape. ADR §3 maps AC-25 to "`$0.0000` on real read". That is not observable. The substitute verification is in §3.13 and §7, and it is flagged as TD-O-4.

### TD-VF-9 (HIGH, pre-existing, not introduced by #1944) — `denyWrite` covers only each session's **own** clone's `bin/`. AF-2's "sandbox `denyWrite`" protection does not hold across clones.

`contract/sandbox-policy.template.json`: `allowWrite` includes `__HOS_ROOT__/Human`, `__HOS_ROOT__/Worker` and `__HOS_ROOT__/Overseer`, while `denyWrite` is only `__PROJECT_ROOT__/bin` (and `docs/SANDBOX-POLICY.md:274` defines `__PROJECT_ROOT__` as "this role's own clone"). A sandboxed **Overseer** or **Human** session can therefore write `Worker/bin/*` with Bash (`cp`, `sed -i`). The `permissions.deny` entry `Edit(__HOS_ROOT__/Worker/**)` stops only the Edit tool. ADR-1944's crontab line runs `…/Worker/bin/hos-usage-poll`, the same exposure `…/Worker/bin/hos-cron` already has. The **data** on the decision path (`~/.hos`, `~/.config/hos/usage-pause.conf`) is outside every `allowWrite`, so AF-1 holds. AF-2's protected-surface half (CODEOWNERS → HUMAN_REQUIRED) also holds. Only the OS-level half is narrower than stated. Escalated as ESC-T1 (security-reviewer, then the human). It does not block #1944 and widens nothing #1944 adds.

### TD-VF-10 (verified) — node_exporter 1.10.2 on faberix: the AD-10 fallback (i) **is available**. Symlink-follow is still unverified and needs root.

Read-only checks this session (`hostname` = `faberix.kumajyo.com`):
- `prometheus-node-exporter --version` reports `1.10.2 (… 1.10.2-1ubuntu0.26.04.1~esm1)`.
- `--help` shows `--collector.textfile.directory=/var/lib/prometheus/node-exporter … supports glob matching. (repeatable)`. **Fallback (i) is therefore supported.**
- The unit runs as `User=prometheus` with `ExecStart=/usr/bin/prometheus-node-exporter $ARGS`, and has no `ProtectSystem`/`ProtectHome`/`ReadOnlyPaths`, so `/var/lib/hos-usage` is reachable.
- `/etc/default/prometheus-node-exporter` has `ARGS=""`.
- `/var/lib/prometheus/node-exporter/` is `root:root 0755` and holds `apt.prom`, `nvme.prom`, `smartmon.prom`.

Symlink following needs a root-created symlink to test. The procedure is in §5.1 and gates S3 coding.

### TD-VF-11 (verified) — every parser regex in §3.2 was run against the verbatim capture and produced the expected values.

I ran a scratch check against the capture (1091 bytes, 20 lines, sha256 `c8d52b0ace496176dded36c78b13b587a2c378cd9d2f6a5acbfdf63266196683`):
- `session=6`, `weekly_all=48`, models `[all models→excluded, Fable=3]`
- 24h: `2049/181`, behaviors `61/36/34`, top list `technical-design 6, architect 3, pm-agent 2, coder 1`, more `0`
- 7d: `13242/1442`, behaviors `48/28/10`, top list of 8 items, `+2 more`
- subscription marker present

Line 8 also contains U+2014 (em dash). The fixture must be byte-exact (§1.9).

### TD-VF-12 (LOW) — a paused cycle still consumes the wakeup file.

`:808` `rm -f`s the wakeup signal before the gate. On a paused cycle it is lost. This is benign: since #1196 every cron fire runs the cycle anyway. Not changed.

### TD-VF-13 (LOW) — T4.1 will deliberately match the poller.

To keep AD-5.3 deterministic rather than "either way", the poller's `--help` text names the command literally (`claude -p /usage`). T4.1 therefore matches the file, and S1 adds it to `_T4_1_EXPECTED_EXEMPTIONS` (§3.11). *Architect round 1: retargeted.* The literal now lives only in `bin/lib/usage_pause.py`, in the first line of its module docstring, and that file is the one T4.1 exemption. `bin/hos-usage-poll` must not contain `claude -p`.

### Verification gaps I could not close

- Symlink-follow in the textfile collector (needs root; §5.1).
- Alertmanager receivers on monitrix (ADR §0.4).
- Which stream `claude -p /usage` writes to over SSH. The capture does not say. The design parses **stdout only**. If the text arrives on stderr, every read fails loudly as `unparseable`, and `--check` item 6 / AC-16 catch it before S2 merges.
- Whether `claude` at `claude_bin` needs `node` on the forced command's PATH. The native installer does not, an npm install would. `--check` item 6 catches it.

---

## 1. Canonical names, grammars and formats (binding — nothing below may re-spell these)

### 1.1 Paths

`$STATE` = `${HOS_STATE_DIR:-$HOME/.hos}`. `HOS_STATE_DIR` is pre-existing (`hos-cron:247`). `HOS_USAGE_PAUSE_CONF` and `HOS_USAGE_PROM_PATH` are **test-only overrides**. They are named only in the module docstring and in the tests, never in the runbook (static test S1-ST7).

| Path | Writer | Readers | Notes |
|---|---|---|---|
| `$STATE/usage-pause/` | poller, `hos-cron` | — | mode 0700, created by whichever runs first |
| `$STATE/usage-pause/reading.status` | poller only | `hos-cron` gate, `--check`, `write-prom` | §1.3 |
| `$STATE/usage-pause/reading.status.tmp` | poller | — | transient, fixed name |
| `$STATE/usage-pause/<role>-<project>.status` | `hos-cron` gate (`check` / `record`) only | gate | §1.4; `<project>` sanitized `tr -c 'A-Za-z0-9._-' '-'` exactly as `hos-cron:349`. *Architect round 1:* `tr` works **per byte**, so Python must sanitize the UTF-8 **bytes** (each byte outside the set becomes one `-`), not the `str`. Otherwise a non-ASCII project name gives bash and Python different file names, and the check-error flag is never found. Test: `test_project_sanitize_matches_tr_bytewise`. |
| `$STATE/usage-pause/<role>-<project>.status.tmp` | gate | — | transient |
| `$STATE/usage-pause/check-error-<role>-<project>.flag` | `hos-cron` bash (on `check_error`) | `check` | empty file, §4.3 G2 |
| `$STATE/usage-pause/issue-body-<role>-<project>.md` | `issue-body` / bash | `gh` | overwritten per use |
| `$STATE/usage-pause/poll.stdout.tmp`, `poll.stderr.tmp` | poller | `poll-record` | deleted at the end of each poll |
| `$STATE/usage-pause/poll.last.log` | the crontab `>` redirect | human | FR-34 |
| `$STATE/locks/usage-poll.lock/` | poller | poller | mkdir lock, 600 s ceiling |
| `$STATE/locks/usage-pause-issue-<project>.lock/` | gate | gate | mkdir lock, 600 s ceiling |
| `$HOME/.config/hos/usage-pause.conf` | human | poller, gate | literal `$HOME`, **never** `HOS_CONFIG_DIR` (VF-4 trap) |
| `$HOME/.ssh/hos_loopback{,.pub}` | human | poller (`-i`), `--check` | |
| `/var/lib/hos-usage/hos_claude_usage.prom` | poller (S3) | node_exporter (via symlink) | §5 |
| `/var/lib/hos-usage/.hos_claude_usage.prom.tmp` | poller (S3) | — | not `*.prom` and outside the collector dir |

**Directory bound (AC-13):** after any number of polls and cycles, `$STATE/usage-pause/` contains only: `reading.status`; one `<role>-<project>.status` per role/project that has run; at most one `issue-body-<role>-<project>.md` per role/project; at most one `check-error-…flag` per role/project; and `poll.last.log`. No `*.tmp` survives a completed run.

### 1.2 Enums and reason tokens

**Read-failure reasons (AD-4, closed, stable).** These are values of `reason=` in the reading file and of the `reason` label on `hos_claude_usage_read_failure`:
`ssh_failed`, `timeout`, `empty_session`, `missing_session`, `missing_weekly`, `unparseable`, `claude_not_executable`, `crashed`.

*Architect round 1:* the list has **eight** reasons. `no_timeout_binary` is removed: the read is bounded in Python (TD-O-1), so that failure cannot occur. A reason that can never be emitted is dead enum surface.

`lock_stale_reclaimed` is **not** a failure reason. AD-4 lists it as "diagnostic only; the read still runs", so it is recorded in a separate key, `diagnostics=lock_stale_reclaimed`, and can appear on a success record (TD-O-11, clarifying).

**Consumer unusable-status reasons (AD-7 step 2):** `status_missing`, `poller_not_installed`, `status_truncated`, `schema_unknown`, `status_unreadable`, `status_stale`, `status_future`.

**Decision reason tokens** (`reason=` in §1.4 and in the verdict line). Charset `[a-z0-9_:+.-]`, maximum 80 characters:

| Token | Decision |
|---|---|
| `under_threshold` | run |
| `threshold_session` / `threshold_weekly` / `threshold_both` | pause |
| `read_failed:<read-failure reason>` | pause (closed) |
| `<unusable reason>` (e.g. `status_stale`) | pause (closed) |
| `failopen:read_failed:<r>` / `failopen:<unusable reason>` | run (open) |
| `settings_invalid:<key>` | pause, any fail mode |
| `check_error` | pause, any fail mode (bash only, §4.3) |

`<key>` is one of the eight AD-9 keys, a sanitized unknown key (`[a-z0-9_]`, ≤ 40 characters), `line_<n>` for a malformed line, or `file_unreadable`. An unknown `reason=` read from the reading file maps to `read_failed:unknown`.

### 1.3 Reading file — `reading.status` (poller-written)

The grammar is shared by both status files:
- UTF-8, LF line endings, every line `key=value`, keys `^[a-z0-9_]+$`.
- Values carry no characters `< 0x20` or `0x7f`. Leading and trailing whitespace is stripped.
- Length caps: `detail` and `summary` ≤ 200, any `*_resets` and any `*_name` ≤ 100, every other value ≤ 200.
- **Line 1 is exactly `schema=1`. The last line is exactly `end=1`, followed by `\n`.** Each key appears at most once. Absent keys are **omitted**, never written empty or `0` (AD-3, FR-44).

Key order, exactly as follows; any key not present is simply skipped:

```
schema=1
kind=reading
run_at=<UTC ISO-8601, YYYY-MM-DDTHH:MM:SSZ>
run_epoch=<int>
outcome=success|failure|crashed
reason=<read-failure reason>                 # outcome≠success only
detail=<sanitized, ≤200>                     # outcome≠success only
diagnostics=lock_stale_reclaimed             # only when it happened
remote_exit=<int>                            # only when ssh ran
parsed_via=grep                              # outcome=success only
subscription_marker=present|absent           # only when ssh ran and produced stdout
session_pct=<int>                            # success only
session_resets=<raw text>                    # success, when the resets text matched
weekly_all_pct=<int>                         # success only
weekly_all_resets=<raw text>
weekly_model_<slug>_name=<label-sanitized model name>   # per model line, in source order
weekly_model_<slug>_pct=<int>
weekly_model_<slug>_resets=<raw text>
requests_24h=<int>  sessions_24h=<int>       # then, in this order, for w=24h then w=7d:
subagent_heavy_pct_<w>  long_context_pct_<w>  long_session_pct_<w>
top_subagents_<w>=<name>=<pct>,<name>=<pct>,…   # source order
top_subagents_more_<w>=<int>                 # 0 = parsed and no "+K more"
consecutive_failures=<int>
last_success_epoch=<int>                     # absent = never succeeded
settings_status=defaults|file|invalid:<key>
machine_decision=run|pause                   # informational only; consumers recompute
machine_decision_reason=<decision reason token>
end=1
```

(One key per line in the real file. The two-per-line rows above are for brevity only.)

**Per-model and breakdown values are written only on `outcome=success`.** On failure the poller writes no percentages of any kind. That is the AC-4 guarantee: "no artifact anywhere records 0%".

**Carry-over rules.** "Previous" means the existing `reading.status`, but only if `read_status()` returns `ok` (§3.5).
- `consecutive_failures`: success → `0`; failure or crash → previous value + 1, or `1` when the previous file is not `ok` or lacks the key.
- `last_success_epoch`: success → `run_epoch`; failure → the previous value, if present, else omitted.

**Bash crash fallback (§3.6 step P11):** a minimal file with only `schema`, `kind`, `run_at`, `run_epoch`, `outcome=crashed`, `reason=crashed`, `detail`, `end`. Consumers treat a missing `consecutive_failures` as `>= failopen_issue_after` (§3.5 table row R14).

### 1.4 Per-role/project status file — `<role>-<project>.status` (gate-written)

Same framing as §1.3. Keys in this order, absent keys omitted:

```
schema=1
kind=cycle
role=worker|overseer
project=<sanitized project>
checked_at=<ISO>  checked_epoch=<int>
decision=run|pause
reason=<decision reason token>
summary=<printable ASCII, ≤160, e.g. "session 92% >= 90%">
fail_mode=closed|open                        # the in-force value (default when settings invalid)
settings_status=defaults|file|invalid:<key>
settings_invalid_value=<sanitized, ≤60>      # only when invalid and a value exists
session_threshold=<int>  weekly_threshold=<int>   # in-force values
reading_state=ok|missing|truncated|schema_unknown|unreadable
reading_outcome=success|failure|crashed      # when reading_state=ok
reading_reason=<…>                           # when outcome≠success
reading_run_at=<ISO>  reading_age_seconds=<int>
session_pct=<int>  weekly_all_pct=<int>      # copied, only when the reading is usable and success
consecutive_failures=<int>                   # copied when present
degraded=0|1
paused_since=<ISO>                           # decision=pause only; episode start
pause_issue=<int>                            # decision=pause and the issue is known
pause_close_pending=1                        # §4.5
degraded_since=<ISO>                         # degraded=1 only
degraded_issue=<int>
degraded_close_pending=1
end=1
```

### 1.5 Write discipline (both files, every writer)

1. Render the full content in memory.
2. Open `<file>.tmp` (same directory) with `O_WRONLY|O_CREAT|O_TRUNC` and mode `0600`. Write, flush, `fsync`, close.
3. `os.replace(<file>.tmp, <file>)`, then best-effort `fsync` on the directory.

A crash leaves at most one fixed-name `.tmp`, which the next write truncates. The bash crash fallback follows the same steps: `printf … > <file>.tmp`, then `mv -f <file>.tmp <file>`. **No writer ever appends.**

### 1.6 Audit events (transition-only; no decision may read one)

| Event | Emitted by | When | argv (one `key=value` per element — TD-VF-6) |
|---|---|---|---|
| `cycle-usage-pause` | gate | `transition=enter` | `role=$ROLE` `project=$PROJECT` `reason=<tok>` `session_pct=<n|->` `weekly_pct=<n|->` `reading_age=<n|->` |
| `cycle-usage-resume` | gate | `transition=exit` | `role=$ROLE` `project=$PROJECT` `paused_since=<iso>` |
| `cycle-usage-degraded` | gate | `degraded_transition=enter` | `role=$ROLE` `project=$PROJECT` `reason=<tok>` |

There are no other events. The poller emits none. There is no event per paused cycle and none on `check_error`, because a crashed helper cannot track transitions (§4.3).

### 1.7 Issue titles, label, bodies

Defined once in `bin/hos-cron`, next to `:221`/`:225`, in the existing style:

```
_USAGE_PAUSE_TITLE="[PAUSED] Claude usage threshold — autonomous cron paused on ${PROJECT}"
_USAGE_DEGRADED_TITLE="[DEGRADED] Claude usage check failing — fail-open, cron NOT paused on ${PROJECT}"
```

(The `—` is U+2014.) These are **full titles**, matched with `==` (TD-VF-7). Both titles are role-agnostic (Q15). The label is `needs-human` only. `needs-ai` is never added (AD-8). This is confirmed against `docs/LABELS.md:30`, and S2 adds `bin/hos-cron` (usage pause) to that row's writer list.

Bodies are rendered by `usage_pause.py issue-body` (§4.2), except the `check_error` body, which bash writes (§4.4). Required content:
- **Paused:** a first line marker `<!-- hos-usage-pause v1 kind=paused project=<p> -->`. Then: the cause (window(s) `>=` threshold with values, **or** the failure / unusable reason and `detail`, **or** the invalid settings key and its rejected value); the reading's `run_at` and age; fail mode; `settings_status`; the role and time of the first paused cycle; "nothing to do — auto-resumes on the first fresh reading below both thresholds, and this issue then closes itself"; "if the check is misfiring: run `bin/hos-usage-poll --check`; last resort `fail_mode=open` in `~/.config/hos/usage-pause.conf`"; "interactive sessions are not paused". This satisfies FR-39 and AC-3.
- **Degraded:** marker `kind=degraded`. Then: the underlying reason, `consecutive_failures`, the reading age (or "no reading file"), that cron is **not** paused because `fail_mode=open`, and that credits billing is unwatched until this closes.
- **Resolved comment** (`--kind paused-resolved|degraded-resolved`): the resuming reading's `run_at`, `session X% < T%`, `weekly Y% < T%`, and "auto-closing".

### 1.8 Settings file — `$HOME/.config/hos/usage-pause.conf` (AD-9; parsed, never sourced)

- **Missing (ENOENT only):** all defaults, `settings_status=defaults`.
- **Any other open/read error, a directory, size > 64 KiB, or invalid UTF-8:** `invalid:file_unreadable`.
- **Line rules:** CRLF is tolerated (strip one trailing `\r`). After stripping surrounding whitespace, an empty line or one starting with `#` is ignored. Every other line must match `^([a-z_]+)=(.*)$`, with the value right-stripped. There are no inline comments, no quotes and no expansion, so `90 # note` is simply an invalid integer. A non-matching line gives `invalid:line_<n>` (1-based).
- **Unknown key:** `invalid:<key>`. **Duplicate key:** `invalid:<key>`.
- **Integers:** `^(0|[1-9][0-9]*)$`, ASCII only (leading zeros rejected; `+`, `-` and Unicode digits rejected).

| Key | Default | Valid |
|---|---|---|
| `session_threshold` | 90 | 1–100 |
| `weekly_threshold` | 90 | 1–100 |
| `fail_mode` | `closed` | exactly `closed` \| `open` |
| `poll_interval_seconds` | 300 | multiple of 60, 60–3600 |
| `staleness_seconds` | 900 | `> poll_interval_seconds + read_timeout_seconds` **and ≤ 7200** (*Architect round 1, TD-O-5:* the draft's `≤ 3600` left no valid value when `poll_interval_seconds=3600`. With 7200 the range is never empty, because interval + timeout ≤ 3600 + 3570 = 7170.) |
| `read_timeout_seconds` | 60 | 5 to `poll_interval_seconds − 30` |
| `failopen_issue_after` | 3 | 1–100 |
| `claude_bin` | unset → resolved | `^/[A-Za-z0-9._+/-]{1,254}$`, no `/../` or `/./` segment, does not end in `/` (charset is TD-O-5: the value is interpolated into a remote command and an `authorized_keys` line) |

- **Cross-field checks** run after the per-key checks, using the in-file values or the defaults: `read_timeout_seconds` first, then `staleness_seconds`. The failing key is named.
- **Report the first violation only, in file-line order.** Cross-field violations are reported after all per-line violations.
- **Under invalid settings:** the decision is pause with `settings_invalid:<key>` (§3.5 R1). The poller keeps polling with **default** `read_timeout_seconds` and **default-resolution** `claude_bin` (AD-9).

### 1.9 The D-1 capture (verbatim; the fixture must be byte-identical)

Provenance: captured over SSH loopback on faberix on 2026-10-02 and relayed by the coordinator. It was originally held at `/tmp/claude-1000/-home-scott-Code-HumanOversightSystem-Worker/8ad4dbe9-649f-453c-ab5d-ab82e06b9102/scratchpad/usage-sample.txt`. That is ephemeral session scratch, which is why it is reproduced here. The file is 1091 bytes and 20 lines, with a trailing LF and no CR. sha256 is `c8d52b0ace496176dded36c78b13b587a2c378cd9d2f6a5acbfdf63266196683`. `·` is **U+00B7** (lines 3, 4, 5, 10, 16). `—` on line 8 is **U+2014**. Line 2, 6, 9 and 15 are empty. Lines 11–14 and 17–20 start with two spaces.

```
You are currently using your subscription to power your Claude Code usage

Current session: 6% used · resets Oct 3, 2:40am (UTC)
Current week (all models): 48% used · resets Oct 3, 12am (UTC)
Current week (Fable): 3% used · resets Oct 3, 12am (UTC)

What's contributing to your limits usage?
Approximate, based on local sessions on this machine — does not include other devices or claude.ai. Behaviors are independent characteristics, not a breakdown.

Last 24h · 2049 requests · 181 sessions
  61% of your usage came from subagent-heavy sessions
  36% of your usage was at >150k context
  34% of your usage came from sessions active for 8+ hours
  Top subagents: technical-design 6%, architect 3%, pm-agent 2%, coder 1%

Last 7d · 13242 requests · 1442 sessions
  48% of your usage came from subagent-heavy sessions
  28% of your usage was at >150k context
  10% of your usage came from sessions active for 8+ hours
  Top subagents: coder 14%, technical-design 3%, architect 2%, code-reviewer 2%, unit-test 1%, general-purpose 1%, oversight-evaluator 1%, risk-assessor 1%, +2 more
```

**Empty-session fixture** (PR #1450 2026-08-17T07:48:32Z, Test 1). Five lines, each ending in LF, internal runs of spaces exactly as shown (12, 2, 1, 4 and 17 spaces after the colons, respectively):

```
Total cost:            $0.0000
Total duration (API):  0s
Total duration (wall): 1s
Total code changes:    0 lines added, 0 lines removed
Usage:                 0 input, 0 output, 0 cache read, 0 cache write
```

---

## 2. Component map

| # | Path | New/changed | Purpose | Slice | Protected? |
|---|---|---|---|---|---|
| A | `bin/lib/usage_pause.py` | new | parser, settings, status I/O, decision, CLI (S1); `check`/`record`/`issue-body` (S2); `render_prom`/`write-prom` (S3). Python 3, **stdlib only**, 3.9-compatible syntax (macOS `/usr/bin/python3`): `from __future__ import annotations`, no `match` | S1, S2, S3 | yes (`bin/**`) |
| B | `bin/hos-usage-poll` | new, `+x` | cron entry point: poll, `--check`, `--print-setup`, `--help` | S1, S3 | yes |
| C | `bin/hos-cron` | changed | §4 gate block + two title constants + one header paragraph | S2 | yes |
| D | `scripts/framework/framework_consumer_files.txt` | changed | add `bin/hos-usage-poll`, `bin/lib/usage_pause.py` under the existing `bin/` heading | S1 | yes |
| E | `bootstrap/hos_install.sh` | changed | post-install summary prints one §2a pointer line inside the existing cron-suggestion block (`:2515-2533`); provisions nothing (FR-47) | S1 | yes |
| F | `tests/framework/test_agent_invocation_migration.py` | changed | T4.1 exemption (`bin/lib/usage_pause.py`) + T4.1b. *Architect round 1:* the T4.2 ledger is **unchanged** (TD-O-1). | S1 | no |
| G | `tests/automation/fixtures/usage/` | new | fixtures + `README.md` provenance | S1 (S3 adds golden `.prom`) | no |
| H | `tests/automation/test_usage_pause_{parse,settings,status,decision}.py` | new | units | S1 | no |
| I | `tests/automation/test_hos_usage_poll.py` | new | poller integration (stub ssh/claude/crontab) | S1, S3 | no |
| J | `tests/framework/test_usage_pause_static.py` | new | static guards | S1, S2, S4 | no |
| K | `tests/framework/test_consumer_framework_files.py` | changed | assert D's two entries | S1 | no |
| L | `docs/CRON-SETUP.md` | changed | new §2a; §7 troubleshooting rows; S3 adds §2a.7 | S1, S2, S3 | no |
| M | `docs/MACHINE-ACCOUNTS-SETUP.md` | changed | one-line pointer to CRON-SETUP §2a | S1 | no |
| N | `SCRIPTS-INDEX.md` | regenerated | via `scripts/framework/regen_all.sh` (B is a top-level `bin/` script) | S1 | no |
| O | `tests/automation/test_usage_pause_check_cli.py` | new | `check`/`record`/`issue-body` | S2 | no |
| P | `tests/automation/test_hos_cron.py` | changed | §4.6 harness + `TestUsagePauseGate` | S2 | no |
| Q | `docs/LABELS.md` | changed | `needs-human` writer row | S2 | no |
| R | `tests/automation/test_usage_pause_prom.py` | new | render/golden | S3 | no |
| S | `contrib/monitoring/{README.md, prometheus/hos-claude-usage.rules.yml, grafana/provisioning/hos.yaml, grafana/dashboards/hos-claude-usage.json}` | new | monitrix artifacts; never shipped | S4 | no |
| T | `tests/framework/test_contrib_monitoring.py` | new | structure, PromQL and metric-name checks | S4 | no |

Not touched by any slice: `bin/hos-suspend`, the `#1446` breaker block and auto-close half (`:2090-2155`, `:2181-2202`), the header paragraph `:91-96`, `TestUsageLimitBreaker` (stays `@skip`), and every other dedup site (ESC-4).

---

## 3. S1 — poller, parser, settings, reading file, runbook

### 3.1 `bin/lib/usage_pause.py` — module API

These are pure functions. **No function on the decision path raises.** Every failure is a value. Only the CLI wrappers do I/O, apart from `load_settings`, `read_status` and `write_status_atomic`, which are named I/O helpers.

```text
SCHEMA_VERSION: int = 1
READ_FAILURE_REASONS: frozenset[str]          # §1.2, exactly eight (Architect round 1)
REMOTE_CMD_TEMPLATE: str = "env -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN {claude_bin} -p /usage"
    # Architect round 1: the single source of the remote command. read_usage, --check
    # item 2 and --print-setup all format it. One code line, trailing comment
    # "# ADR-1944 AD-5: the only /usage call site (T4.1b)".
SSH_OPTIONS: tuple[str, ...]                  # the AD-6 -o list, verbatim and in AD-6 order
KILL_GRACE_SECONDS: int = 5                   # AD-6's --kill-after=5, now in Python

read_usage(*, claude_bin: str, key_path: Path, timeout_s: int,
           stdout_path: Path, stderr_path: Path) -> ReadOutcome   # Architect round 1; never raises
    argv = ["ssh", "-n", "-i", str(key_path), *SSH_OPTIONS, "127.0.0.1",
            REMOTE_CMD_TEMPLATE.format(claude_bin=claude_bin)]   # list argv; no local shell
    Popen(argv, stdin=DEVNULL, stdout=<stdout_path fh>, stderr=<stderr_path fh>,
          start_new_session=True, env=<os.environ minus the three credential vars>)
    wait(timeout=timeout_s). On TimeoutExpired: os.killpg(pid, SIGTERM), wait(KILL_GRACE_SECONDS);
    if still alive: os.killpg(pid, SIGKILL), wait(). ProcessLookupError is ignored.
    ReadOutcome(kind: "exited"|"timeout"|"spawn_failed", rc: int|None, detail: str|None)
    spawn_failed = OSError from Popen (e.g. ssh not on PATH).
UNUSABLE_REASONS: frozenset[str]              # §1.2, exactly seven
DEFAULTS: Mapping[str, int|str|None]          # §1.8
INPUT_CAP_BYTES: int = 65536
STALE_FUTURE_TOLERANCE_SECONDS: int = 120

decode_usage_bytes(raw: bytes) -> str
    raw[:INPUT_CAP_BYTES] → utf-8 errors="replace" → strip OSC (\x1b\][^\x07\x1b]*(\x07|\x1b\\))
    and CSI (\x1b\[[0-9;?]*[ -/]*[@-~]) escapes → delete '\r'. Locale-independent.

parse_usage(text: str) -> ParseResult              # never raises; §3.2–3.3
classify_transport(outcome: ReadOutcome) -> str | None   # §3.3 (Architect round 1: takes ReadOutcome, not rc)
load_settings(path: Path) -> SettingsResult        # never raises; §1.8
read_status(path: Path) -> StatusRead              # never raises; §3.5
evaluate(status: StatusRead, settings: SettingsResult, now: float, *,
         poller_artifacts_present: bool) -> Decision      # pure; §3.5
build_reading(parse: ParseResult | None, *, transport_reason: str | None, detail: str | None,
              remote_exit: int | None, diagnostics: str | None, previous: StatusRead,
              settings: SettingsResult, now: float) -> list[tuple[str, str]]   # §1.3 order
render_status(fields: list[tuple[str, str]]) -> str     # adds schema/end framing, sanitizes, orders
write_status_atomic(path: Path, text: str) -> None      # raises OSError only; §1.5
main(argv: list[str]) -> int                            # CLI; §3.6, §4.2, §5
```

Data types (frozen dataclasses):
- `ParseResult(ok: bool, reason: str|None, session_pct: int|None, session_resets: str|None, weekly_all_pct: int|None, weekly_all_resets: str|None, models: tuple[ModelWeekly, ...], windows: Mapping[str, WindowBreakdown], subscription_marker: str)`
  - `ok` ⇔ `reason is None`
  - `models` and `windows` are populated **only** when `ok`
- `ModelWeekly(name: str, slug: str, pct: int, resets: str|None)`
- `WindowBreakdown(window: str, requests: int|None, sessions: int|None, subagent_heavy_pct: int|None, long_context_pct: int|None, long_session_pct: int|None, top_subagents: tuple[tuple[str,int], ...]|None, top_subagents_more: int|None)`
- `SettingsResult(values: Mapping[str, int|str|None], status: str, invalid_key: str|None, invalid_value: str|None)`
  - `values` always holds a complete set: the file values when valid, the defaults when invalid
  - `status ∈ {"defaults", "file", "invalid:<key>"}`
- `StatusRead(state: str, fields: Mapping[str, str])`
  - `state ∈ {ok, missing, truncated, schema_unknown, unreadable}`
- `Decision(decision: str, reason: str, summary: str, degraded: bool, session_pct: int|None, weekly_pct: int|None, reading_age: int|None)`

### 3.2 Parser regexes (pinned against §1.9, TD-VF-11)

All are Python `re`. Use `[0-9]`, never `\d`, and `re.ASCII` wherever a digit class appears. `·` is written `·`. "Last match wins" means: take the **final** `finditer` match over the whole text, as `tail -1` does.

| Field | Pattern | Rule |
|---|---|---|
| `session_pct` | `Current session: ([0-9]+)% used` | last match; `int()` |
| `session_resets` | `Current session: [0-9]+% used · resets (.*)` | last match; strip; cap 100 |
| `weekly_all_pct` | `Current week \(all models\): ([0-9]+)% used` | last match |
| `weekly_all_resets` | `Current week \(all models\): [0-9]+% used · resets (.*)` | last match |
| per-model | `Current week \(([^)]+)\): ([0-9]+)% used(?: · resets (.*))?` | every match whose group 1 ≠ `all models`; slug = lowercase, `[^a-z0-9]+`→`_`, strip `_`, cap 32; empty slug → skip; duplicate slug → last wins; `name` = group 1 label-sanitized (§5.2) |
| subscription marker | `^You are currently using your subscription to power your Claude Code usage\s*$` (`re.M`) | `present`/`absent`, informational only |
| any `% used` | `[0-9]+% used` | used only by the empty-shape test |
| empty markers | `Total cost:` (substring) or `Usage:\s+0 input` | |

The percentages are uncapped integers. `150` is accepted as-is. `48.5%` does not match, so the read **fails** (AD-4, no clamping, no decimals).

**Breakdown (each field independent; only when `ok`).** Process line by line.
- **Header:** `^\s*Last (24h|7d) · ([0-9]+) requests · ([0-9]+) sessions\s*$`. It opens a block for window `w`.
- **Block extent:** a block runs to the next header, the next empty line, or end of text, whichever comes first. Lines outside any block are ignored.
- **Behavior lines** (inside a block only):
  - `^\s*([0-9]+)% of your usage came from subagent-heavy sessions\s*$` → `subagent_heavy_pct_<w>`
  - `^\s*([0-9]+)% of your usage was at >150k context\s*$` → `long_context_pct_<w>`
  - `^\s*([0-9]+)% of your usage came from sessions active for 8\+ hours\s*$` → `long_session_pct_<w>`
- **Top line:** `^\s*Top subagents: (.+?)\s*$`. Split group 1 on `", "`.
  - The **last** item may match `^\+([0-9]+) more$`, which gives `more = K`. If it does not, `more = 0`.
  - Every other item must match `^(\S(?:.*\S)?) ([0-9]+)%$`. The name is label-sanitized. A duplicate sanitized name makes the line invalid.
  - **If any item fails, the whole top line is invalid:** `top_subagents_<w>` and `top_subagents_more_<w>` are both absent.
- **Ambiguity → absent.** A window header seen twice makes every field of that window absent. A behavior or top line seen twice in one block makes that field absent.
- **Isolation.** Each of the 2 × 6 breakdown extractions runs inside its own `try/except Exception`. An exception leaves that one field absent and **can never change `ok`/`reason`** (FR-17, AC-18).

### 3.3 Read classification

`parse_usage` sets `ok`/`reason` from **content** only, in this order:
1. Session **and** weekly-all matched → `ok=True`.
2. No `[0-9]+% used` anywhere, and (`Total cost:` present or `Usage:\s+0 input` matches) → `empty_session`. This shape never yields a number.
3. Session matched only → `missing_weekly`.
4. Weekly-all matched only → `missing_session`.
5. Otherwise → `unparseable`. This covers the empty string.

~~`classify_transport(rc)` returns `timeout` for 124 and 137 … `ssh_failed` for 255, 125, 126 and 127 …~~ **Architect round 1:** `classify_transport(outcome: ReadOutcome)` returns:
- `timeout` for `kind=timeout`. This is observed directly and no longer inferred from an exit code, so a remote exit of 124 is no longer misread as a timeout;
- `ssh_failed` for `kind=spawn_failed`, and for `kind=exited` with `rc == 255`;
- `None` otherwise.

A remote `127` (claude missing on the far side) is now a content failure (`unparseable`, with `detail` carrying stderr), not `ssh_failed`. The local P6 check is the primary `claude_not_executable` path.

`poll-record` combines the two (§3.6):
- A **pre-ssh refusal** (`--transport-reason`) wins.
- Otherwise, `classify_transport` not `None` wins. Stdout is not parsed then: a killed or failed transport is a failure even if partial text parsed.
- Otherwise the content classification decides, including when `rc` is a non-zero remote exit other than the codes above. `remote_exit` is recorded either way. AD-4 binds "not the exit code". The FR-11 tension is TD-O-3.
- `detail` on failure is the first 200 sanitized characters of stderr, or of stdout for content failures, prefixed `stderr:`/`stdout:`.

### 3.4 Settings

As specified in §1.8. `load_settings` accepts a `Path`. CLI callers resolve it as `os.environ.get("HOS_USAGE_PAUSE_CONF")` or `Path(os.environ["HOME"]) / ".config/hos/usage-pause.conf"`. It is **never** derived from `HOS_CONFIG_DIR` (static test S1-ST3 greps the module for `HOS_CONFIG_DIR`). `claude_bin` resolution, when unset or under invalid settings, is `shutil.which("claude")` against the process `PATH`, which the poller has pinned.

### 3.5 `read_status` and `evaluate` (the decision table)

**`read_status(path)`** never raises:
- `ENOENT` → `missing`.
- Any other `OSError`, size > 65536, or invalid UTF-8 → `unreadable`.
- Empty file, or last line (after a final `\n`) ≠ `end=1` → `truncated`.
- First line not of the form `schema=<digits>` → `unreadable`. `schema` ≠ `1` → `schema_unknown`.
- Any line that does not match `^[a-z0-9_]+=[^\x00-\x1f\x7f]*$`, any duplicate key, or `end`/`schema` appearing anywhere other than the last/first line → `unreadable`.
- Otherwise → `ok`, with `fields` holding everything except `schema`/`end`.

**`evaluate(status, settings, now, *, poller_artifacts_present)`** — the first matching row wins. "Closed" and "open" refer to `settings.values["fail_mode"]`, and `N` is `failopen_issue_after`.

| # | Condition | decision | reason | degraded |
|---|---|---|---|---|
| R1 | `settings.status` starts `invalid:` | pause | `settings_invalid:<key>` | 0 |
| R2 | `status.state == missing` and `not poller_artifacts_present` | U | `poller_not_installed` | — |
| R3 | `status.state == missing` | U | `status_missing` | — |
| R4 | `truncated` / `schema_unknown` / `unreadable` | U | `status_truncated` / `schema_unknown` / `status_unreadable` | — |
| R5 | `kind ≠ reading`, `run_epoch` not `^[0-9]+$`, or `outcome ∉ {success, failure, crashed}` | U | `status_unreadable` | — |
| R6 | `now − run_epoch < −120` | U | `status_future` | — |
| R7 | `now − run_epoch > staleness_seconds` (strict; exactly `staleness_seconds` is fresh) | U | `status_stale` | — |
| R8 | `outcome=success` and (`session_pct` or `weekly_all_pct` missing or not `^[0-9]+$`) | U | `status_unreadable` | — |
| R9 | success, `s >= ST` and `w >= WT` | pause | `threshold_both` | 0 |
| R10 | success, `s >= ST` | pause | `threshold_session` | 0 |
| R11 | success, `w >= WT` | pause | `threshold_weekly` | 0 |
| R12 | success otherwise | run | `under_threshold` | 0 |
| R13 | `outcome ∈ {failure, crashed}` | F | `read_failed:<reason or unknown>` | — |
| R14 | resolve **U** / **F** under closed | pause | the U/F reason | 0 |
| R15 | resolve **U** under open | run | `failopen:<U reason>` | **1** (AD-8 b) |
| R16 | resolve **F** under open | run | `failopen:<F reason>` | 1 iff `consecutive_failures` absent / non-integer / `>= N`, else 0 |

Notes on the table:
- `poller_artifacts_present` is computed by the CLI as `conf file exists or $HOME/.ssh/hos_loopback exists`. It uses `exists` only and never opens the key (AD-7.2: `poller_not_installed` is used when the reading **and** the conf **and** the key are all absent).
- Per-model values never enter this table (AS-1).
- Breakdown fields never enter this table (FR-17).
- `summary` is printable ASCII ≤ 160. Examples: `session 92% >= 90%`; `weekly 90% >= 90%`; `session 92% >= 90% and weekly 95% >= 90%`; `session 6% < 90%, weekly 48% < 90%`; `reading failed: timeout`; `reading stale: age 1260s > 900s`; `settings invalid: session_threshold='8O'`; `fail-open: reading failed: empty_session (3 consecutive)`.

### 3.6 `bin/hos-usage-poll` — CLI and poll procedure

```
hos-usage-poll                 # one poll (crontab)
hos-usage-poll --check         # preflight; read-only (§3.8)
hos-usage-poll --print-setup   # prints setup artifacts; never mutates (§3.9)
hos-usage-poll --help          # first description line, verbatim (Architect round 1):
                               #   "Reads Claude subscription usage (/usage) over SSH loopback (ADR-1944); the read itself is bin/lib/usage_pause.py read-usage."
                               # The bash file must NOT contain the literal `claude -p`. The literal now
                               # lives only in usage_pause.py: its module docstring's first line names
                               # `claude -p /usage`, so T4.1 matches that one file deterministically (TD-VF-13, retargeted).
```

**Exit codes:**
- poll: `0` = a reading was written, or the lock was held. `1` = no reading could be written (the crash path was attempted). `64` = usage error.
- `--check`: `0` = all PASS/SKIP/INFO, `1` = any FAIL, `64` = usage error.
- `--print-setup`: `0`, or `1` if a required input (the `.pub` file) is missing. In that case it still prints everything else, with a `MISSING:` line.

**Poll procedure (`set -uo pipefail`, no `-e`; every step explicit).**
- **P1. Pin the environment** exactly as `hos-cron:123-126`: the HOME fallback and `export PATH="$HOME/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"`. No nvm. `unset CLAUDE_CODE_OAUTH_TOKEN ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN`. The poller never sources, reads or names `claude-auth.env` (AC-15).
- **P2.** `_BIN_DIR` = the absolute directory of `$0`. `_LIB="$_BIN_DIR/lib/usage_pause.py"`. `_STATE="${HOS_STATE_DIR:-$HOME/.hos}"`. Run `mkdir -p "$_STATE/usage-pause" "$_STATE/locks"` and `chmod 700 "$_STATE/usage-pause"`.
- **P3. Lock.** `mkdir "$_STATE/locks/usage-poll.lock"`.
  - If it exists and its mtime age is < 600 s (the `_stat_mtime` idiom from `hos-cron:305`), print `[hos-usage-poll] <iso> another poll holds the lock — exiting` and exit 0 without writing.
  - If its age is ≥ 600 s, reclaim it (`rm -rf` + `mkdir`) and set `_DIAG=lock_stale_reclaimed`.
  - Install `trap _on_exit EXIT` (P11).
- **P4. Parameters.** Run `python3 "$_LIB" poll-params`. It prints exactly three lines, `read_timeout_seconds=<int>`, `claude_bin=<abs path or empty>` and `settings_status=<…>`. Read them with `while IFS='=' read -r k v` plus a `case`. **Never `eval`/`source`.**
  - Any other output, or `rc≠0` → `_TRANSPORT_REASON=crashed`, `detail="poll-params failed"`, then go to P9.
- ~~**P5. Timeout binary.**~~ **Architect round 1: P5 is deleted.** The bound is `read_usage`'s `wait(timeout)` plus a process-group SIGTERM/SIGKILL (§3.1). It is always available, so FR-7 holds with no coreutils dependency on macOS. The poller assigns no `_TIMEOUT_BIN` and calls no `timeout`/`gtimeout`.
- **P6. claude.** An empty `claude_bin`, or one that is not `-x` → `_TRANSPORT_REASON=claude_not_executable`, go to P9. The path is local, and the same path is used remotely: same host, same user.
- **P7. Key.** `$HOME/.ssh/hos_loopback` not a readable regular file → `_TRANSPORT_REASON=ssh_failed`, `detail="loopback key missing"`, go to P9.
- **P8. The read (Architect round 1, TD-O-1: done in Python, not as a bash `timeout … ssh` pipeline).**
  ```
  _READ_LINE="$(python3 "$_LIB" read-usage --timeout "$_READ_TIMEOUT" --claude-bin "$_CLAUDE_BIN" \
      --key "$HOME/.ssh/hos_loopback" \
      --stdout "$_STATE/usage-pause/poll.stdout.tmp" --stderr "$_STATE/usage-pause/poll.stderr.tmp")"
  ```
  - `read-usage` calls `read_usage()` (§3.1). It prints **exactly one** line matching `^read=(exited|timeout|spawn_failed) rc=([0-9]+|-)$` and exits 0.
  - Any other output, or a non-zero exit, → `_TRANSPORT_REASON=crashed`, `detail="read-usage failed"`, then P9.
  - The ssh argv is the AD-6 argv with no `timeout` prefix: `ssh -n -i <key> <SSH_OPTIONS> 127.0.0.1 <REMOTE_CMD_TEMPLATE formatted>`. It is a Python list, with no local shell and no `eval`.
  - `REMOTE_CMD_TEMPLATE` is a **single code line in `usage_pause.py`**, byte-for-byte as in §3.1, carrying the trailing comment `# ADR-1944 AD-5: the only /usage call site (T4.1b)`.
  - There is exactly one `Popen`/`subprocess` call that runs `ssh` in the module, and **no `ssh` invocation in `bin/hos-usage-poll`**.
- **P9. Record.** Run `python3 "$_LIB" poll-record --read <exited|timeout|spawn_failed> --rc <n|-> --stdout <path> --stderr <path> [--transport-reason <r>] [--detail <text>] [--diagnostics "$_DIAG"]`. The `--read`/`--rc` and stdout/stderr arguments are omitted when P8 did not run.
  - `poll-record` reads ≤ 64 KiB of each stream, classifies (§3.3), builds the reading with carry-over (§1.3), evaluates `machine_decision` with `now = run_epoch` (never stale), and writes `reading.status` atomically.
  - It prints one summary line, `[hos-usage-poll] <iso> outcome=<o> [reason=<r>] [session=<n> weekly=<n>] decision=<d> (<reason>)`, and exits 0 on a successful write and 1 otherwise.
  - On exit 0, set `_WROTE=1`.
- **P10. (S3)** If `_WROTE=1`: `python3 "$_LIB" write-prom || echo "[hos-usage-poll] <iso> WARN: prom export failed (ignored; never affects the pause)"`. This runs strictly **after** P9 (AD-10).
- **P11. `_on_exit` (EXIT trap).**
  - `rm -f` both `poll.*.tmp` files and `rm -rf` the lock.
  - If `_WROTE≠1`, try `python3 "$_LIB" poll-record --transport-reason crashed --detail "exit=<code> at <step>"`.
  - If that also fails, write the §1.3 minimal crash file **in bash**, using §1.5's tmp+`mv` (no Python), so a broken module still leaves `outcome=crashed`.
  - Never re-raise.

**No step reads `$STATE/suspend/`, a `hos-halt` issue, `projects.conf`, or any project state** (FR-24, AC-12, AC-27; static test S1-ST2). There are no network calls apart from the loopback `ssh`, and no audit events (FR-34).

### 3.7 SSH, credential hygiene, time bound — summary of what is binding

- The argv in P8 is the AD-6 argv verbatim, minus the `timeout` prefix. The bound moved into `read_usage` (Architect round 1; ADR Amendment 1 A1-2).
- The worst-case run is about 75 s plus local I/O: 60 s, then SIGTERM to the process group, then 5 s grace, then SIGKILL.
- `-n` and `RequestTTY=no` mean no stdin and no pty (FR-5).
- `StrictHostKeyChecking=yes` means a changed host key yields `ssh_failed`.
- The **remote** `env -u` strips the three variables even if the remote shell's startup files set them (AC-15).
- With a forced command in `authorized_keys`, the client command is ignored. The design works identically with or without it (§5 Q12 stays the human's call).

### 3.8 `--check` (FR-48, AC-22) — read-only, idempotent, writes no state

`--check` takes no lock and writes nothing under `$STATE` or `/var/lib/hos-usage`. Its one real read goes to `mktemp -d` under `${TMPDIR:-/tmp}`, which is removed on exit.

Output is one line per item, `PASS|FAIL|SKIP|INFO  <n>  <text>[ — <remedy>]`, then `RESULT: PASS` or `RESULT: FAIL (<k> failed)`.

1. `~/.ssh/hos_loopback` exists and its mode is exactly `0600` (via `python3 "$_LIB" stat-mode <path>`; no GNU/BSD `stat` divergence).
2. `~/.ssh/hos_loopback.pub` exists. Some line of `~/.ssh/authorized_keys` contains its base64 blob (field 2), and that line's option list contains the exact token `from="127.0.0.1,::1"`.
   - INFO reports whether `restrict` and `command=` are present.
   - If `command=` is present, its value must equal `env -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN <resolved claude_bin> -p /usage` exactly. Otherwise FAIL `forced command mismatch — regenerate with --print-setup`.
3. `ssh-keygen -F 127.0.0.1 -f ~/.ssh/known_hosts` exits 0.
4. `python3 "$_LIB" check-settings` prints `settings_status=…` and exits 0 for `defaults`/`file`. Invalid → FAIL naming the key and value.
5. `crontab -l` has **exactly one** non-comment line containing `hos-usage-poll`.
   - Its schedule must be `*/N * * * *` with `N*60 == poll_interval_seconds` (or `0 * * * *` when the interval is 3600).
   - Its redirect must not contain `>>` (FR-34).
   - The path must equal this script's absolute path. `crontab` absent or `crontab -l` failing → FAIL.
6. One real loopback read, P6–P8 (`read-usage`) into the temp dir, then `python3 "$_LIB" classify --read <k> --rc <rc> --stdout <f> --stderr <f>` (Architect round 1). That prints `SUCCESS session=<n> weekly=<n>` or `FAILED reason=<r> detail=<…>`. PASS iff `SUCCESS`. This also reports INFO `stderr non-empty (<k> bytes)`.
7. (S3) Export. If `/var/lib/hos-usage` does not exist → SKIP `export not configured`. Otherwise:
   - the directory is writable by the current user, **and**
   - **exactly one** of these holds: (a) `/var/lib/prometheus/node-exporter/hos_claude_usage.prom` is a symlink resolving (`realpath`) to `/var/lib/hos-usage/hos_claude_usage.prom`; (b) `/etc/default/prometheus-node-exporter`'s `ARGS` contains `--collector.textfile.directory=/var/lib/hos-usage` (fallback (i)).
   - Both → FAIL `duplicate export path (node_exporter would read the file twice)`. Neither → FAIL `symlink missing — re-run the §2a.7 root step (a release upgrade may have purged node_exporter)`.
   - INFO reports `systemctl is-active prometheus-node-exporter` when `systemctl` exists.

*Architect round 1:* item 2's expected `command=` value, and every forced-command line `--print-setup` prints (§3.9 block 3), are obtained from `python3 "$_LIB" remote-cmd --claude-bin <path>`. That subcommand prints `REMOTE_CMD_TEMPLATE` formatted. `bin/hos-usage-poll` never spells `-p /usage` itself, so T4.1b's single call site stays `usage_pause.py`, and the forced command cannot drift from what the poller actually sends.

### 3.9 `--print-setup` — prints, never mutates

It prints these blocks, in this order, with headings:
1. `mkdir -p ~/.hos/usage-pause && chmod 700 ~/.hos/usage-pause`.
2. `ssh-keygen -t ed25519 -N '' -C hos-loopback -f ~/.ssh/hos_loopback`.
3. **Recommended (Q12, §11 item 5)** `authorized_keys` line, then the **ruled minimum** line, each fully expanded with the resolved `claude_bin` and the `.pub` content:
   ```
   restrict,from="127.0.0.1,::1",command="env -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN <claude_bin> -p /usage" <type> <blob> hos-loopback
   from="127.0.0.1,::1" <type> <blob> hos-loopback
   ```
4. Seeding `known_hosts` from the host key **on disk**, which needs no network trust: `printf '127.0.0.1 %s\n' "$(cut -d' ' -f1,2 /etc/ssh/ssh_host_ed25519_key.pub)" >> ~/.ssh/known_hosts`.
5. The crontab line: `*/N * * * *  <abs path to hos-usage-poll> > <abs $HOME>/.hos/usage-pause/poll.last.log 2>&1`, or `0 * * * *` for 3600.
6. (S3) The two root commands from §5.1.
7. `bin/hos-usage-poll --check`.

### 3.10 Shipping

S1 adds `bin/hos-usage-poll` and `bin/lib/usage_pause.py` to `framework_consumer_files.txt` (AD-2). The existing copy loop (`hos_install.sh:1904-1916`) `chmod +x`'s both. `contrib/` is never listed (S4 static test). ESC-1's consumer behaviour is unchanged by this design and is still open (§11 item 10).

### 3.11 T4.1, T4.1b, T4.2 (in `tests/framework/test_agent_invocation_migration.py`)

*Architect round 1 (TD-O-1): this subsection is rewritten. The call site is `bin/lib/usage_pause.py`.*
- **T4.1:** add `"bin/lib/usage_pause.py",  # EXEMPT (permanent, ADR-1944 AD-5): non-agent /usage read over SSH loopback; argv pinned by T4.1b.` to `_T4_1_EXPECTED_EXEMPTIONS`, and add a line to the exemption comment block naming ADR-1944 AD-5. The match is guaranteed by the module docstring's first line, which names `claude -p /usage` literally (TD-VF-13, retargeted). `bin/hos-usage-poll` must **not** match T4.1.
- **`test_T4_1b_usage_read_has_one_call_site`:** over code lines (`_code_lines`) of `scripts/`, `bootstrap/`, `bin/`, the regex `(?:-p|--print)\s+["']?/usage\b` matches **only** in `bin/lib/usage_pause.py`.
- **`test_T4_1b_remote_command_is_exact`:** `bin/lib/usage_pause.py` has exactly one code line matching `^REMOTE_CMD_TEMPLATE\s*=`. Stripped of its trailing comment, it equals `REMOTE_CMD_TEMPLATE = "env -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN {claude_bin} -p /usage"`. Neither `bin/lib/usage_pause.py` nor `bin/hos-usage-poll` has a code line matching `--model|--json-schema|--agent`.
- **T4.2: no change.** Neither file assigns `_TIMEOUT_BIN`. `test_T4_2_private_timeout_bin_copy_ledger_is_exactly_three` stays as it is and passes unmodified. That is the point of the override.

### 3.12 Runbook — `docs/CRON-SETUP.md` §2a "Usage-pause poller (SSH loopback)" (inserted after §2, before §3)

Outline (S1 writes all of it except 2a.7, which S3 adds):
- **2a.1 What it is.** One `*/5` poller per host. It reads `/usage` under your personal login over SSH loopback, never `claude-auth.env`. Every worker/overseer cycle pauses when session or weekly usage is `>=` 90%, or when the reading is missing, stale or failed (fail-closed). It resumes automatically. Interactive sessions are never paused.
- **2a.2 Key.** `mkdir -p ~/.hos/usage-pause`, then `ssh-keygen -t ed25519 -N '' -C hos-loopback -f ~/.ssh/hos_loopback`.
- **2a.3 authorized_keys.** Run `bin/hos-usage-poll --print-setup` and append **one** of the two printed lines (recommended: the `restrict,…,command=` form, which limits the key to the one read-only command; the ruled minimum is `from=` only). Note: if `claude` moves, regenerate the line; `--check` item 2 detects it.
- **2a.4 known_hosts.** The printed on-disk seeding command. Do not use `ssh-keyscan` and do not accept-new.
- **2a.5 Settings (optional).** `~/.config/hos/usage-pause.conf`. Include the §1.8 table verbatim, plus: "missing = ruled defaults; any invalid value, unknown key or duplicate key pauses every cycle until fixed, regardless of `fail_mode`".
- **2a.6 Crontab.** The printed line. Use `>` and **not** `>>`. One entry per host. Then `bin/hos-usage-poll --check` must print `RESULT: PASS`.
- **2a.7 (S3) Dashboard export on faberix.** The root step (§5.1), the symlink verification, the fallback, and the ESM-purge note.
- **2a.8 Reading the state.** `cat ~/.hos/usage-pause/reading.status`; `cat ~/.hos/usage-pause/<role>-<project>.status`; the `[PAUSED]`/`[DEGRADED]` issues; `[PAUSED-USAGE]`/`[DEGRADED-USAGE]` lines in `/tmp/hos-<role>-<project>.log`.
- **2a.9 Order of operations.** Do the poller setup (2a.2–2a.6, `--check` green) **before** upgrading to a release that contains the S2 gate. Otherwise every cycle pauses with `poller_not_installed` until it is done (AD-12; ESC-1 for consumers).
- **§7 rows (S2):**
  - `[PAUSED-USAGE] … reason=poller_not_installed|status_missing|status_stale` → run `--check`, then `crontab -l`, then `cat poll.last.log`.
  - `reason=settings_invalid:<key>` → fix the conf.
  - `reason=check_error` → run `python3 bin/lib/usage_pause.py check --role <r> --project <p>` by hand and read the traceback.

`MACHINE-ACCOUNTS-SETUP.md` gets one line: "Claude usage-pause poller (SSH loopback): see `docs/CRON-SETUP.md` §2a." `hos_install.sh` prints `"       d. Claude usage-pause poller (required before cycles run): see docs/CRON-SETUP.md §2a"` inside the existing `$ROLE_WORKER || $ROLE_OVERSEER` cron block (`:2515-2533`).

### 3.13 S1 exit criteria (all required before S2 merges)

1. The PR suite is green, including T4.1/T4.1b/T4.2 (AC-26).
2. **AC-16 recorded.** On faberix, with the crontab line installed, at least one **cron-fired** poll produced `outcome=success`. The record is a #1944 comment (posted by the human or the orchestrating session) with: `crontab -l | grep hos-usage-poll`; `reading.status` showing a `run_at` on a `*/5` boundary within 90 s; `poll.last.log`; and `bin/hos-usage-poll --check` output with `RESULT: PASS`.
3. **AC-25 substitute (TD-O-4)**, recorded in the same comment: (a) the AC-21 stub test passes; (b) a hand check that `--check` item 2 shows the forced command, if adopted, so the key cannot carry a prompt; (c) two reads 10 s apart with no other Claude activity on the host report identical `session_pct`.

---

## 4. S2 — the `bin/hos-cron` cycle-start gate and visibility

### 4.1 Exact insertion point

A new section is inserted **between line 868** (the `fi` closing the deterministic git-credentials block) **and line 870** (`# ── Claude Code subscription auth (#728) …`), replacing the blank line 869 with: one blank line, the block, one blank line.
- The block starts with the unique anchor line `# ── Usage-threshold pause (#1944, ADR-1944 AD-7/AD-8) ─────` and ends with the unique anchor line `# ── end usage-threshold pause (#1944) ──`.
- **Each anchor string appears exactly once in the file, with no quoting of either anchor anywhere** (test anchors match the first occurrence).
- The two title constants (§1.7) go immediately after `:225`.
- One header paragraph goes after the `:112-114` crontab example (not inside `:91-96`). It describes the gate in five lines or fewer and points to CRON-SETUP §2a.

**What runs before the gate:**
- suspend check `:258-286`; overlap lock `:304-332`; cycle id; deps check; jitter; env validation; wakeup; preflight; GitHub auth; identity guard; git credentials.
- None of these invokes Claude.

**What runs after the gate:**
- `claude-auth.env` `:877-892`; the model probe `:899`; halt check `:906`; agent availability; milestone; actionable-work gate `:1003`; git sync and hygiene `:1248-1258`; baseline `:1482`; session `:1849`.
- So a paused cycle starts no Claude process of any kind (FR-26), and it also skips the sync and the baseline.

### 4.2 Python side (S2 additions to `usage_pause.py`)

**`check --role R --project P`.** Steps:
1. `load_settings`.
2. `read_status(reading.status)`.
3. Compute `poller_artifacts_present`.
4. `evaluate(…, now=time.time())`.
5. Read the previous per-role file with `read_status` (state `ok` and `kind=cycle`; anything else is "previous unknown"). Also note whether the previous file was **corrupt**, meaning present but not `ok`.
6. Note whether `check-error-<role>-<project>.flag` exists. If it does, the previous decision is treated as `pause` with no `pause_issue`, and the flag is deleted **after** step 8.
7. Compute transitions and memory (§4.5).
8. Write the new per-role file (§1.4, §1.5).
9. Print the verdict line and exit 0.

Any exception, or a failed write in step 8, → nothing on stdout, a one-line traceback summary on stderr, exit **70**.

**Verdict line.** Exactly one line on stdout. The bash side matches it with this **exact** ERE:

```
^USAGE_PAUSE v=1 decision=(run|pause) reason=([a-z0-9_:+.-]{1,80}) transition=(none|enter|exit) degraded=(0|1) degraded_transition=(none|enter|exit) file_pause_issue=(0|1) close_pause_issues=(0|1) file_degraded_issue=(0|1) close_degraded_issues=(0|1) session_pct=([0-9]+|-) weekly_pct=([0-9]+|-) reading_age=(-?[0-9]+|-) paused_since=([0-9TZ:-]+|-) summary=([ -~]{0,200})$
```

`BASH_REMATCH[1..14]` map in order. The `summary` is printable ASCII, so it is safe to echo.

**`record --role R --project P (--pause-issue N | --degraded-issue N | --clear-pause-close | --clear-degraded-close)`.**
- Reads the per-role file. It must be `ok` and `kind=cycle`, else exit 1.
- Applies the one change, rewrites atomically, exits 0.
- `--clear-pause-close` removes `pause_close_pending` and `pause_issue`. `--clear-degraded-close` removes `degraded_close_pending` and `degraded_issue`.

**`issue-body --kind (paused|degraded|paused-resolved|degraded-resolved) --role R --project P --out PATH`** renders §1.7 from the per-role file, the reading file and the settings, writes `PATH` atomically, and exits 0, or exits 1 if the per-role file is not `ok`.

### 4.3 The bash block — contract (steps G1–G6)

- **G1.** `_UP_BOUND=()`. If `timeout` exists: `_UP_BOUND=(timeout --kill-after=5 60)`. Else if `gtimeout` exists: `_UP_BOUND=(gtimeout --kill-after=5 60)` (*Architect round 1:* `--kill-after` added, to match AD-6's discipline). This is **not** a `_TIMEOUT_BIN=` assignment, so the T4.2 ledger for `bin/hos-cron` is unchanged (`bin/hos-cron` is already in it in any case). Then `mkdir -p "$_HOS_DIR/usage-pause"` (failure ignored).
  - **Architect round 1, binding:** every expansion of the array is written `${_UP_BOUND[@]+"${_UP_BOUND[@]}"}`, never a bare `"${_UP_BOUND[@]}"`. In bash before 4.4 (which includes macOS `/bin/bash` 3.2 when Homebrew bash is not first on PATH), the bare form on an empty array under `set -u` (`hos-cron:116`) is a fatal "unbound variable". That would abort hos-cron at the gate on every macOS host without coreutils. Static test `S2-ST5 test_up_bound_expansions_are_set_u_safe`. The expansions in §4.4 follow the same rule.
- **G2. Ask.** Run `_UP_LINE="$(${_UP_BOUND[@]+"${_UP_BOUND[@]}"} python3 "$_HOS_CRON_DIR/lib/usage_pause.py" check --role "$ROLE" --project "$PROJECT")"`, recording `rc`, inside an `if` so `set -e` cannot fire. Python's stderr is inherited and goes to the cron log; the draft's `2>&2` was a no-op and is dropped. Then match `_UP_LINE` against the §4.2 ERE.
  - **Architect round 1, binding:** the `[[ =~ ]]` match runs inside a helper function that declares `local LC_ALL=C` first. Bracket ranges (`[a-z]`, `[ -~]`) are then byte ranges, whatever the cron locale. A locale-induced mismatch could only fail safe (`check_error`), but a spurious `check_error` pause is a loud false positive, and this costs one line.
  - **If `rc≠0` or there is no match:** set `decision=pause reason=check_error transition=none degraded=0 file_pause_issue=1` (all other actions 0) and `summary="usage-pause check helper failed (rc=<rc>)"`, and `touch "$_HOS_DIR/usage-pause/check-error-${ROLE}-${_project_safe}.flag"`. **The pause stands regardless of `fail_mode`** (AD-7.5). A missing or broken `bin/lib/usage_pause.py` lands here.
- **G3. Log.**
  - Pause: `echo "$LOG_PREFIX [PAUSED-USAGE] <summary> (reason=<reason>)"`.
  - Run with `degraded=1`: `echo "$LOG_PREFIX [DEGRADED-USAGE] fail-open: <summary> — cycle continues"`.
  - Run with `degraded=0`: no line (the common case stays quiet).
- **G4. Audit** (§1.6), only on the transitions the verdict reports. `check_error` emits none.
- **G5. Visibility.** `_usage_pause_visibility || true` (§4.4). Its failures never change the decision. **The decision was fixed in G2, before any GitHub call** (FR-37, AC-14).
- **G6. Act.** On pause: `exit 0`. The EXIT trap at `:332` frees the overlap lock. There is no `_LAST_RUN_FILE` write, no wakeup, and no audit sync, the same as every other early exit. On run: fall through to line 870.

The block contains **no** reference to `suspend`, `hos-suspend`, `.prom`, `node_exporter`, `ssh` or `/usage`. It contains no `rm` of anything except its own lock directory, and it reads no file under `last-claude-output/` (FR-25, FR-28, AC-11, AC-24, AC-27; static tests S2-ST1/ST2).

### 4.4 `_usage_pause_visibility` — issue filing, dedup, auto-close

This function is defined inside the block (all `_up_*` names) and only runs on paths the verdict asks for. On a normal run cycle with nothing pending it makes **zero** GitHub calls. On paused cycles after the issue is recorded it also makes zero calls.

1. If `_REPO_SLUG` is empty, or `command -v gh` fails: log `WARN: usage-pause issue actions skipped (no repo slug / gh)` and return 0. The pause still applies.
2. **Complete dedup query** `_up_find <title>`. *Architect round 1:* the draft piped into a standalone `jq`. `bin/hos-cron` never depends on standalone `jq`; every existing query uses `gh --jq`, and consumers are not required to have `jq`. On a host without `jq`, the dedup query would fail on every cycle, so no pause issue would ever be filed. That would be fail-closed, but FR-37 would be silently dead. Replaced with:
   ```
   _up_raw="$(${_UP_BOUND[@]+"${_UP_BOUND[@]}"} gh api --paginate "repos/${_REPO_SLUG}/issues?state=open&labels=needs-human&per_page=100" \
     --jq '.[] | select(.pull_request == null) | "\(.number)\t\(.title)"')"
   ```
   - Success requires `gh` to exit 0 **and** every non-empty output line to match `^[0-9]+<TAB>`. Otherwise it is a query failure: log `WARN: usage-pause dedup query failed — no filing this cycle (fail-closed)` and do not file.
   - The **exact-title comparison is done in bash** (`[[ "${line#*$'\t'}" == "$title" ]]`, inside the `local LC_ALL=C` helper). It is not done in jq, because the title contains operator-supplied `${PROJECT}` and must never be interpolated into a jq program.
   - `--paginate` follows every page and errors if any page fails, so a result is never truncated (TD-VF-2). `gh` applies `--jq` per page. The match is exact-title (TD-VF-7).
3. **Issue lock.** `mkdir "$_HOS_DIR/locks/usage-pause-issue-${_project_safe}.lock"`. If it exists and is < 600 s old: log `usage-pause issue lock held — skipping this cycle` and skip the filing **and** close actions. If it is ≥ 600 s old, reclaim it. Release it at the end of the function (`rm -rf`), on every path.
4. **File pause** (`file_pause_issue=1`):
   - Run `_up_find "$_USAGE_PAUSE_TITLE"`.
   - If it returns at least one number: `record --pause-issue <lowest>` and log `usage-pause issue already open (#N)`.
   - If it returns none: render the body. For a normal verdict use `issue-body --kind paused`. For `check_error`, bash writes the body with `printf` to the same fixed path; it names the rc, says every cycle on `<project>` is paused regardless of `fail_mode`, and gives the hand-run command.
   - Then `${_UP_BOUND[@]+"${_UP_BOUND[@]}"} gh issue create --repo "$_REPO_SLUG" --title "$_USAGE_PAUSE_TITLE" --label needs-human --body-file <path>`. Parse the number from the URL (`/issues/([0-9]+)$`). On success, `record --pause-issue N`, skipped for `check_error`, and log `filed usage-pause issue #N`. On failure log a WARN; the next paused cycle retries.
5. **Close pause** (`close_pause_issues=1`):
   - `_up_find` the title. Render `issue-body --kind paused-resolved`.
   - For each number: `gh issue comment N --repo … --body-file <path>`, **then** `gh issue close N --repo …`, each bounded.
   - If the query succeeded and every comment/close succeeded: `record --clear-pause-close`. Otherwise leave it pending; the next cycle retries.
6. **File degraded** (`file_degraded_issue=1`): as in 4, with `_USAGE_DEGRADED_TITLE`, `--kind degraded` and `--degraded-issue`.
7. **Close degraded** (`close_degraded_issues=1`): as in 5, with `--kind degraded-resolved` and `--clear-degraded-close`.

### 4.5 Transitions and episode memory (computed in `check`, step 7)

"Prev" means the previous per-role file when it is `ok`. When the check-error flag is present, prev is `decision=pause` with no issue fields. Otherwise prev is "unknown".

| Item | Rule |
|---|---|
| `transition` | `enter` if new=pause and prev ≠ pause (unknown counts as run, AD-8); `exit` if new=run and prev=pause; else `none` |
| `paused_since` | `enter` → `checked_at`; pause→pause → carried |
| `pause_issue` | pause→pause → carried; `enter` → absent |
| `pause_close_pending` | set to 1 on `exit`; carried while new=run until `--clear-pause-close`; **also** set to 1 when the previous per-role file was **corrupt** (present but not `ok`) and new=run, so an episode whose memory was destroyed still gets its issue closed (TD-O-9); cleared (dropped) if new=pause |
| `pause_issue` on `exit` | carried into the run-state file, so the close can name it in the log |
| `file_pause_issue` | new=pause and no `pause_issue` |
| `close_pause_issues` | new=run and `pause_close_pending=1` |
| `degraded` | from `evaluate` |
| `degraded_transition` | `enter` if degraded=1 and prev degraded ≠ 1; `exit` if degraded=0 and prev degraded=1; else `none` |
| `degraded_since`, `degraded_issue` | carried while degraded=1 |
| `degraded_close_pending` | set to 1 when (prev `degraded_issue` set, or prev degraded=1, or prev corrupt) **and** this cycle's reading is usable with `outcome=success`; carried until `--clear-degraded-close`. A degraded issue therefore closes only on a fresh success (AD-8), not when `fail_mode` is flipped back to closed. |
| `file_degraded_issue` | degraded=1 and no `degraded_issue` |
| `close_degraded_issues` | `degraded_close_pending=1` |

**Cross-role behaviour.** Worker and overseer keep separate memory but share one title.
- The first role to pause files the issue under the issue lock. The other role's next paused cycle finds it through `_up_find` and records it, so there is one issue per project per episode (Q15, AC-14).
- Whichever role resumes first closes it. The other role's close sweep finds nothing and clears its pending flag.
- If a human closes the issue mid-episode, a role that still remembers `pause_issue` does not re-file (AD-8).

### 4.6 Test-harness changes in `tests/automation/test_hos_cron.py` (required by TD-VF-5)

1. **`CronEnv.write_usage_reading(**overrides)`.** Writes `self.state/"usage-pause"/"reading.status"` in §1.3 format.
   - Defaults: `outcome=success`, `session_pct=6`, `weekly_all_pct=48`, `consecutive_failures=0`, `run_epoch=int(time.time())`, `settings_status=defaults`.
   - `overrides` may set any key, set `None` to omit a key, or pass `raw=<str>` to write arbitrary bytes.
   - Also `CronEnv.write_usage_conf(text)` → `self.home/".config/hos/usage-pause.conf"`, and `CronEnv.usage_status(role, project)` → parsed dict.
2. **`CronEnv.run()`.** Unless the test has called `write_usage_reading`/`set_usage_reading_managed()`, `run()` writes the default reading **fresh before every invocation**, so every pre-existing test sees "run" exactly as before.
3. **`gh` stub.** A new case is inserted **before** `:214`:
   ```
   *"--paginate"*"labels=needs-human&per_page=100"*)
     [[ -n "${HOS_TEST_USAGE_PAUSE_QUERY_FAIL:-}" ]] && exit 1
     printf '%b' "${HOS_TEST_USAGE_PAUSE_ISSUES:-}" ;;   # Architect round 1: pre-rendered "N\tTitle\n" lines (the stub cannot run --jq)
   ```
   No existing launcher query uses `--paginate` (grep-verified). *Architect round 1:* `HOS_TEST_USAGE_PAUSE_ISSUES` holds the post-`--jq` lines. Paging itself is `gh`'s job; the harness instead asserts the recorded argv carries `--paginate` and `per_page=100`. Also add `HOS_TEST_GH_ISSUE_CREATE_FAIL` to the existing `issue create` branch (`exit 1` before printing the URL) and record `issue comment` with `--body-file`.

4. **Copied-launcher tests (Architect round 1).** Every test that copies `bin/hos-cron` elsewhere and runs the copy also copies `bin/lib/usage_pause.py` into the copy's `bin/lib/`, and writes a fresh reading under that test's `HOS_STATE_DIR`. Known sites are `test_hos_cron.py:1768-1839` (`REAL_GIT_CREDS_LIB` pattern); the coder greps `shutil.copy(HOS_CRON` across `tests/` for the full set. Without this, those tests hit `check_error` and pause. The fix belongs in the harness, never in the gate.

### 4.7 Docs in S2

- `docs/LABELS.md:30`: add the writer "`bin/hos-cron` usage-threshold pause (#1944): files and auto-closes `[PAUSED]`/`[DEGRADED]` issues".
- `docs/CRON-SETUP.md` §7: the rows from §3.12.

---

## 5. S3 — the `.prom` export on faberix

### 5.1 Precondition — the symlink-follow verification. A human runs it on faberix and records the output in the S3 PR **before** S3 is coded.

```
sudo install -d -o scott -g scott -m 0755 /var/lib/hos-usage
printf '# HELP hos_symlink_probe probe\n# TYPE hos_symlink_probe gauge\nhos_symlink_probe 1\n' > /var/lib/hos-usage/hos_symlink_probe.prom
sudo ln -sfn /var/lib/hos-usage/hos_symlink_probe.prom /var/lib/prometheus/node-exporter/hos_symlink_probe.prom
curl -s localhost:9100/metrics | grep -E '^hos_symlink_probe |^node_textfile_scrape_error |node_textfile_mtime_seconds\{file=.*hos_symlink_probe'
# rename-through-symlink check (what the poller actually does):
printf '# HELP hos_symlink_probe probe\n# TYPE hos_symlink_probe gauge\nhos_symlink_probe 2\n' > /var/lib/hos-usage/.probe.tmp
mv -f /var/lib/hos-usage/.probe.tmp /var/lib/hos-usage/hos_symlink_probe.prom
curl -s localhost:9100/metrics | grep -E '^hos_symlink_probe '
# cleanup
sudo rm /var/lib/prometheus/node-exporter/hos_symlink_probe.prom
rm /var/lib/hos-usage/hos_symlink_probe.prom
```

**PASS** requires all of: `hos_symlink_probe 1`, then `hos_symlink_probe 2` after the rename; `node_textfile_scrape_error 0`; and an `mtime` series for the probe. Then perform the real step:

```
sudo ln -sfn /var/lib/hos-usage/hos_claude_usage.prom /var/lib/prometheus/node-exporter/hos_claude_usage.prom
```

**FAIL → fallback (i)**, which is available per TD-VF-10. Set `ARGS="--collector.textfile.directory=/var/lib/prometheus/node-exporter --collector.textfile.directory=/var/lib/hos-usage"` in `/etc/default/prometheus-node-exporter`, run `sudo systemctl restart prometheus-node-exporter`, and do **not** create the symlink. Both directories must be listed, because setting the flag replaces the compiled-in default. A symlink **plus** the second directory would read the file twice, which `--check` item 7 rejects. If fallback (i) also fails → escalate (AD-10 ii). **Never** write in place into the root-owned directory. S1/S2 are unaffected either way.

### 5.2 `render_prom(status, settings, decision) -> str` and `write-prom`

- **`write-prom` CLI.** `read_status(reading.status)` (it must be `ok`, else exit 1 with no write) → `load_settings` → `evaluate(…, now=run_epoch, poller_artifacts_present=True)` → `render_prom`.
  - Target: `HOS_USAGE_PROM_PATH` (test-only) or `/var/lib/hos-usage/hos_claude_usage.prom`. If the parent directory does not exist → exit 0 with the stdout line `prom export not configured`.
  - Write `<dir>/.hos_claude_usage.prom.tmp`, `fsync`, `chmod 0644`, `os.replace` → target.
  - **It never touches `reading.status` and nothing on the decision path reads its output.**
- **Format.** Prometheus text 0.0.4, LF, final newline.
  - Families appear in the order of the table below. Each **present** family is preceded by `# HELP` and `# TYPE <name> gauge`. A family with no samples is omitted entirely, HELP and TYPE included.
  - **No sample timestamps** (the textfile collector rejects them).
  - Values are decimal integers.
  - Labels are sorted by name. Label values are sanitized to `[A-Za-z0-9_.:-]` (anything else → `_`) and capped at 64. Two items that sanitize to the same value keep the first and drop the rest.

| Metric | Labels | Present when | HELP text |
|---|---|---|---|
| `hos_claude_usage_session_percent` | — | success | Current-session usage % reported by `claude -p /usage` (raw; may exceed 100) |
| `hos_claude_usage_weekly_all_models_percent` | — | success | Current-week all-models usage % (raw) |
| `hos_claude_usage_weekly_model_percent` | `model` | success, per model line | Current-week usage % for one model (gauge only; never pauses) |
| `hos_claude_usage_window_requests` | `window` (`24h`\|`7d`) | header parsed | Requests in the rolling window, as reported (local sessions on this machine) |
| `hos_claude_usage_window_sessions` | `window` | header parsed | Sessions in the rolling window, as reported |
| `hos_claude_usage_subagent_heavy_percent` | `window` | line parsed | % of usage from subagent-heavy sessions (independent characteristic, overlaps others) |
| `hos_claude_usage_long_context_percent` | `window` | line parsed | % of usage at >150k context (independent characteristic) |
| `hos_claude_usage_long_session_percent` | `window` | line parsed | % of usage from sessions active 8+ hours (independent characteristic) |
| `hos_claude_usage_top_subagent_percent` | `subagent`, `window` | name in that window's top list | % of usage attributed to a top-N subagent (truncated list) |
| `hos_claude_usage_top_subagents_more` | `window` | top line parsed (`0` = known none) | Count of subagents omitted from the top list ("+K more") |
| `hos_claude_usage_threshold_percent` | `window` (`session`\|`weekly`) | settings valid (TD-O-6) | Configured pause threshold % |
| `hos_claude_usage_settings_valid` | — | always | 1 if usage-pause.conf is valid or absent (TD-O-6) |
| `hos_claude_usage_pause_condition` | — | always | 1 iff the AD-7 rule says pause for this reading with current settings (machine-level) |
| `hos_claude_usage_read_ok` | — | always | 1 if the last poll was a successful read |
| `hos_claude_usage_read_failure` | `reason` | failure only (value 1) | Reason the last poll failed |
| `hos_claude_usage_poll_timestamp_seconds` | — | always | Unix time of the last poll (`run_epoch`) |
| `hos_claude_usage_last_success_timestamp_seconds` | — | always | Unix time of the last successful read; 0 = none on record |
| `hos_claude_usage_fail_mode_closed` | — | always | 1 if fail_mode=closed (default) |

The module exports `METRIC_NAMES: tuple[str, ...]` (this table, in order). The S4 tests import it to check that every name the rules and the dashboard reference exists.

### 5.3 Poller and `--check` changes in S3

- Step P10 (§3.6).
- `--check` item 7 (§3.8).
- `--print-setup` block 6.
- CRON-SETUP §2a.7, which also carries the ESM-purge note and the verification queries (§6.4).

---

## 6. S4 — `contrib/monitoring/` (never shipped; human-applied on monitrix)

### 6.1 `contrib/monitoring/prometheus/hos-claude-usage.rules.yml` (full content contract)

```yaml
groups:
  - name: hos-claude-usage
    rules:
      - alert: HosClaudeUsageMetricsAbsent
        expr: absent(hos_claude_usage_poll_timestamp_seconds{instance="faberix"})
        for: 15m
        labels: {severity: warning}
        annotations:
          summary: "HOS usage metrics absent from faberix"
          description: "node_exporter purged/stopped, symlink broken, or S3 never applied. Reinstall prometheus-node-exporter if a release upgrade removed it, then run bin/hos-usage-poll --check on faberix."
      - alert: HosClaudeUsagePollStale
        expr: time() - hos_claude_usage_poll_timestamp_seconds > 900
        for: 5m
        labels: {severity: warning}
        annotations:
          summary: "HOS usage poller has not written for >15m on {{ $labels.instance }}"
          description: "The .prom file is frozen: the poller is dead (crontab, lock, or host). Every HOS cron cycle is paused under fail_mode=closed."
      - alert: HosClaudeUsageReadFailing
        expr: hos_claude_usage_read_ok == 0
        for: 15m
        labels: {severity: warning}
        annotations:
          summary: "HOS /usage reads failing on {{ $labels.instance }}"
          description: "See hos_claude_usage_read_failure{reason}. Run bin/hos-usage-poll --check."
      - alert: HosClaudeUsageTextfileError
        expr: node_textfile_scrape_error{instance="faberix"} > 0
        for: 15m
        labels: {severity: warning}
        annotations:
          summary: "node_exporter textfile collector error on faberix"
      - alert: HosClaudeUsagePauseCondition
        expr: hos_claude_usage_pause_condition == 1
        for: 0m
        labels: {severity: info}
        annotations:
          summary: "HOS autonomous cron pause condition is active (machine-level)"
      - alert: HosClaudeUsageWeeklyTimeToThreshold
        expr: predict_linear(hos_claude_usage_weekly_all_models_percent[6h], 86400) >= on(instance) hos_claude_usage_threshold_percent{window="weekly"}
        for: 30m
        labels: {severity: warning}
        annotations:
          summary: "Weekly Claude usage projected to reach the pause threshold within 24h"
```

The `900` is the default `staleness_seconds`. The README says to edit it if the conf changes. None of these rules affects the pause (AD-11).

### 6.2 `contrib/monitoring/grafana/provisioning/hos.yaml`

```yaml
apiVersion: 1
providers:
  - name: hos
    orgId: 1
    folder: HOS
    type: file
    disableDeletion: true
    allowUiUpdates: false
    updateIntervalSeconds: 60
    options:
      path: /var/lib/grafana/dashboards/hos
      foldersFromFilesStructure: false
```

### 6.3 `contrib/monitoring/grafana/dashboards/hos-claude-usage.json` — specification

**Top level:**
- classic dashboard JSON model; `uid: "hos-claude-usage"`; `title: "HOS — Claude usage (proactive pause)"`; `tags: ["hos"]`
- `editable: false`; `schemaVersion: 39` (Grafana 13.2.3 migrates it forward on load); `refresh: "1m"`; `time: {from: "now-7d", to: "now"}`
- **no `__inputs`, no `__requires`, no `${DS_` string anywhere**

**Templating:**
- `datasource`: `type: "datasource"`, `query: "prometheus"`, `refresh: 1`, no hard-coded current.
- `instance`: `type: "textbox"`, `query: "faberix"`, `current: {text: "faberix", value: "faberix"}`.

**Every** panel and target uses `"datasource": {"type": "prometheus", "uid": "${datasource}"}`.

**Annotation** (`annotations.list`, besides Grafana's built-in):
- `name: "pause condition (machine)"`, `datasource: ${datasource}`, `enable: true`, `iconColor: "red"`
- `expr: hos_claude_usage_pause_condition{instance="$instance"} == 1`, `step: "60s"`, `titleFormat: "pause condition (machine)"`, `useValueForTime: false`

The name must not say "cycles paused" (AD-10/AD-11).

| # | Title | Type / options | Targets (exact `expr`, `legendFormat`) | Description |
|---|---|---|---|---|
| 1 | `Usage sawtooth vs pause threshold` | timeseries; unit `percent`; `min: 0`, no `max` (values may exceed 100); `spanNulls: false` (gaps = failed reads); stacking `none`; overrides make the threshold series dashed | A `hos_claude_usage_session_percent{instance="$instance"}` → `session %`; B `hos_claude_usage_weekly_all_models_percent{instance="$instance"}` → `weekly (all models) %`; C `hos_claude_usage_threshold_percent{instance="$instance",window="session"}` → `session threshold`; D `hos_claude_usage_threshold_percent{instance="$instance",window="weekly"}` → `weekly threshold`; E `hos_claude_usage_weekly_model_percent{instance="$instance"}` → `weekly {{model}} % (gauge only)` | "Raw values from claude -p /usage. Threshold lines follow the configured value. Red regions = pause condition (machine-level), not per-role cycle state." |
| 2 | `Early warning (predict_linear)` | timeseries; unit `percent`; stacking `none` | A `predict_linear(hos_claude_usage_session_percent{instance="$instance"}[1h], 3600)` → `session % projected +1h`; B `predict_linear(hos_claude_usage_weekly_all_models_percent{instance="$instance"}[6h], 86400)` → `weekly % projected +24h`; C, D as panel 1 | "Forecasts computed at query time (nothing derived is exported). Unreliable just after a window reset." |
| 3a | `Subagent attribution — top-N, 24h` | timeseries; stacking `normal`; unit `percent`; override for target B: unit `none`, right axis, stacking `none`, line style dashed | A `hos_claude_usage_top_subagent_percent{instance="$instance",window="24h"}` → `{{subagent}}`; B `hos_claude_usage_top_subagents_more{instance="$instance",window="24h"}` → `+K more (count)` | **Exactly:** "Top-N only and truncated (`+K more`, also plotted). A subagent leaving the list appears as a gap, not zero. Not a complete breakdown." |
| 3b | `Subagent attribution — top-N, 7d` | as 3a | same exprs with `window="7d"` | same text |
| 4 | `Behaviors (independent, overlapping)` | timeseries; **stacking `none`** on the panel and in every override; `fillOpacity: 0`; unit `percent`; placed at the same `gridPos.y` as panel 1, alongside it | A `hos_claude_usage_long_context_percent{instance="$instance"}` → `{{window}} >150k context %`; B `hos_claude_usage_long_session_percent{instance="$instance"}` → `{{window}} 8h+ sessions %`; C `hos_claude_usage_subagent_heavy_percent{instance="$instance"}` → `{{window}} subagent-heavy %` | **Exactly:** "Independent characteristics, not a breakdown; values overlap. Never sum or stack these." |
| 5 | `Check health` | stat row, four stats | `hos_claude_usage_read_ok{instance="$instance"}`; `time() - hos_claude_usage_poll_timestamp_seconds{instance="$instance"}` (unit `s`); `time() - hos_claude_usage_last_success_timestamp_seconds{instance="$instance"}` (unit `s`; huge = no success on record); `hos_claude_usage_read_failure{instance="$instance"}` → `{{reason}}` | "Health of the check itself. Last-success 0 means none on record." |

There are no `rate(`, `increase(`, `delta(` or `deriv(` calls. Only `predict_linear` and `time() -` appear, and both are query-time.

### 6.4 `contrib/monitoring/README.md` (outline)

1. **Purpose and boundary.** This is the dashboard path only. It never affects the pause. It is not shipped to consumers.
2. **Prerequisites.** S3 is applied on faberix and `bin/hos-usage-poll --check` item 7 passes.
3. **Prometheus on monitrix (human):**
   - copy the rules file to `/etc/prometheus/rules/`
   - uncomment `rule_files:` in `/etc/prometheus/prometheus.yml` with `- /etc/prometheus/rules/*.yml`
   - `promtool check rules /etc/prometheus/rules/hos-claude-usage.rules.yml`
   - `promtool check config /etc/prometheus/prometheus.yml`
   - `sudo systemctl reload prometheus`
   - check `/rules` and `/alerts`
   - scrape config: no change (job `linux_servers`, AD-11.1)
4. **Grafana on monitrix (human):**
   - `sudo install -d /var/lib/grafana/dashboards/hos`
   - copy the JSON there, and `hos.yaml` to `/etc/grafana/provisioning/dashboards/`
   - `sudo systemctl restart grafana-server`
   - confirm the dashboard is in folder HOS, and that `journalctl -u grafana-server` shows no `provisioning` errors (this is the AC-20 record)
5. **Verification queries:**
   - `hos_claude_usage_poll_timestamp_seconds{instance="faberix"}` (present and advancing about every 5 minutes)
   - `hos_claude_usage_read_ok` = 1
   - `node_textfile_mtime_seconds{file=~".*hos_claude_usage.prom"}`
   - rules loaded; dashboard renders
6. **Alert routing.** Alerts go to the existing Alertmanager at `localhost:9093`. Receivers are unverified (ADR §0.4).
7. **ESM purge.** The ADR's exact sentence: "A release upgrade can purge the ESM `prometheus-node-exporter` build (it did on 2026-10-01). `HosClaudeUsageMetricsAbsent` and the absence of `hos_*` series on monitrix are how you notice. Reinstall, then re-run `bin/hos-usage-poll --check`."
8. **Host-specific values** (`faberix`, the monitrix paths) appear only here and in variable defaults.

---

## 7. Test plan

Every test listed runs in the PR suite (`not slow and not integration`) unless marked. Fixtures live in `tests/automation/fixtures/usage/`. `README.md` there records each file's provenance and, for derived fixtures, the exact single-line edit made to `d1-loopback-2026-10-02.txt`.

| Fixture | Content |
|---|---|
| `d1-loopback-2026-10-02.txt` | §1.9 verbatim; sha256 asserted by `test_d1_fixture_is_verbatim` |
| `empty-session-pr1450-test1.txt` | §1.9 empty-session block verbatim |
| `ac1-real-shape-no-breakdown.txt` | D-1 lines 1–5 shape with AC-1 values: `Current session: 4% used · resets Aug 17, 7:20am (UTC)`, `Current week (all models): 29% used · resets Aug 22, 12am (UTC)`, `Current week (Fable): 6% used · resets Aug 22, 12am (UTC)` (values from #1446 05:17:05Z; line shape from D-1) |
| `session-only.txt` / `weekly-only.txt` | D-1 with line 4 / line 3 deleted |
| `garbled.txt` | D-1 with every `% used` replaced by `pct used` and lines 7–20 removed |
| `decimal-percent.txt` | D-1 with `6%` → `6.5%` on line 3 |
| `over-100.txt` | D-1 with `48%` → `112%` on line 4 |
| `breakdown-one-garbled.txt` | D-1 with line 12 changed to `36 percent of your usage was at >150k context` |
| `top-list-bad-item.txt` | D-1 with `architect 3%` → `architect three%` on line 14 |
| `no-weekly-model.txt` | D-1 with line 5 deleted |
| `ansi-crlf.txt` | D-1 with CSI color codes around the percentages and CRLF endings |
| `expected-d1.prom` (S3) | golden `render_prom` output for D-1 with default settings |

### 7.1 S1 tests

**`test_usage_pause_parse.py`**
- `test_d1_fixture_is_verbatim` — sha256 and byte length.
- `test_d1_success_values` — 6, 48, resets text, `parsed_via=grep`, marker present (AC-1 shape on real data).
- `test_d1_model_fable` (FR-16).
- `test_d1_breakdown_24h` / `test_d1_breakdown_7d` — every value in TD-VF-11 (AC-18, FR-17).
- `test_d1_top_more_counts` — 24h → 0, 7d → 2.
- `test_ac1_real_shape_success_no_breakdown` — AC-1; AC-18 first half: windows empty.
- `test_empty_session_is_failed_empty_session` (AC-4, FR-12).
- `test_empty_session_yields_no_number` — every numeric field None (AC-4).
- `test_session_only_missing_weekly`, `test_weekly_only_missing_session` (AC-5).
- `test_garbled_unparseable`, `test_empty_string_unparseable`.
- `test_decimal_percent_fails` (AD-4 no decimals).
- `test_over_100_accepted_unclamped`.
- `test_last_match_wins`.
- `test_ansi_crlf_stripped`.
- `test_unicode_digits_rejected`.
- `test_invalid_utf8_replaced_not_raised`.
- `test_input_capped_at_64k`.
- `test_marker_absent_still_success`.
- `test_breakdown_line_garbled_isolated` — only that field absent; ok=True (AC-18).
- `test_breakdown_exception_isolated` — monkeypatch one sub-extractor to raise (AC-18).
- `test_duplicate_window_header_absent`.
- `test_top_list_bad_item_whole_line_absent`.
- `test_no_weekly_model_line_absent`.
- `test_label_sanitization`.
- `test_window_length_never_parsed` — no `2h`/`5h` literal in the module; reset text is free-form (FR-20).
- `test_classify_transport` — *(Architect round 1)* `read=timeout` → timeout; `read=spawn_failed` and `exited rc=255` → ssh_failed; `exited` with rc 0/1/2/124/127 → None (AC-6, AC-7).
- `test_read_usage_timeout_kills_process_group` — *(Architect round 1)* calls `read_usage(timeout_s=1)` directly against a stub `ssh` that forks a sleeping grandchild. Within ~1 s + grace it returns `kind=timeout`, and neither process survives (FR-7, AC-7, fast).
- `test_read_usage_spawn_failed` — `ssh` absent from PATH → `kind=spawn_failed`, no raise.
- `test_read_usage_env_strips_credentials` — the child env lacks the three variables even when the caller's env has them (FR-4).
- `test_project_sanitize_matches_tr_bytewise` — for ASCII and non-ASCII names, the Python sanitizer equals `printf '%s' X | tr -c 'A-Za-z0-9._-' '-'` (§1.1).

**`test_usage_pause_settings.py`**
- `test_missing_file_defaults` (FR-18, FR-29).
- `test_each_key_valid_bounds` — parametrized, both edges.
- `test_each_key_invalid` — parametrized: 0, 101, `8O`, `090`, `+90`, `90 # c`, empty, Unicode digit, `fail_mode=Closed`, interval 90, interval 3660, staleness 360 (≤ 300+60), staleness 7201 (Architect round 1), timeout 4, timeout 271, relative `claude_bin`, `claude_bin` with a space or `/../` → `invalid:<key>` (Q11, FR-30).
- `test_unknown_key_invalid` — `sesion_threshold`.
- `test_duplicate_key_invalid`.
- `test_malformed_line_invalid_line_n`.
- `test_unreadable_file`, `test_directory_path`, `test_non_utf8_file` → `file_unreadable`.
- `test_first_violation_reported`.
- `test_never_raises` — fuzz 200 random byte strings.
- `test_conf_path_never_from_hos_config_dir` — `HOS_CONFIG_DIR` set to a dir holding a conf → ignored (VF-4, FR-27).

**`test_usage_pause_status.py`**
- `test_render_read_roundtrip`.
- `test_missing`.
- `test_truncated_no_end`, `test_truncated_empty`.
- `test_schema_2_unknown`.
- `test_garbled_line_unreadable`, `test_duplicate_key_unreadable`, `test_oversize_unreadable`.
- `test_values_sanitized_control_chars`.
- `test_atomic_write_no_tmp_left`.
- `test_failure_reading_has_no_pct_keys` (AC-4).
- `test_carryover_consecutive_and_last_success` (FR-32, AC-30 poller half).
- `test_bash_crash_file_parses` — the §1.3 minimal file is `ok`.

**`test_usage_pause_decision.py`** — table-driven over §3.5 R1–R16:
- `test_boundary_session_90_pauses`, `test_boundary_weekly_90_pauses`, `test_89_89_runs` (AC-2, AC-28; the AC-28 negative guard is `test_exact_90_is_reached`).
- `test_weekly_only_reason_names_weekly` (AC-3).
- `test_both_over`.
- `test_threshold_80` (AC-23 unit).
- `test_model_100_never_pauses` (AS-1).
- `test_stale_boundary_900_fresh_901_stale`, `test_future_boundary_120_ok_121_future` (FR-36, AC-8).
- `test_missing_vs_poller_not_installed` (AF-4).
- `test_each_unusable_reason_distinct` (AC-8).
- `test_failure_closed_pauses`, `test_failure_open_runs` (FR-21, FR-22, AC-9).
- `test_failopen_degraded_at_n_not_n_minus_1` (AC-30).
- `test_failopen_unusable_degraded` (AD-8 b).
- `test_failopen_missing_counter_is_degraded`.
- `test_invalid_settings_pause_even_open` (Q11).
- `test_success_missing_pct_is_unreadable`.
- `test_summary_ascii_and_bounded`.

**`test_hos_usage_poll.py`** — runs the real `bin/hos-usage-poll` with a temp `HOME`, `HOS_STATE_DIR`, and stubs in `$HOME/.local/bin`:
- `ssh` stub: records argv, then `exec bash -c "$last_arg"` with the inherited env, or exits per `HOS_TEST_SSH_EXIT`.
- `claude` stub: records argv and env, prints a fixture file.
- `crontab` stub.

Tests:
- `test_poll_success_writes_reading` (AC-1, FR-31, FR-33).
- `test_poll_claude_argv_exactly_dash_p_usage` (AC-21, FR-9, FR-14).
- `test_poll_ssh_argv_matches_ad6`.
- `test_poll_strips_credentials` — caller exports all three variables; the claude stub sees none; the poller's own env too (AC-15, FR-4).
- `test_poll_ssh_255_ssh_failed`, `test_poll_key_missing_ssh_failed` (AC-6).
- ~~`test_poll_no_timeout_binary_refused`~~ *(Architect round 1: removed with `no_timeout_binary`.)* Replaced by `test_poll_needs_no_timeout_binary`: with PATH lacking `timeout`/`gtimeout`, the poll still succeeds (FR-7 via `read_usage`).
- `test_poll_claude_not_executable`.
- `test_poll_timeout` — **slow**: read_timeout 5, stub sleeps 60 (AC-7).
- `test_poll_remote_124_is_not_timeout` — *(Architect round 1)* stub ssh exits 124 promptly with the D-1 text → success with `remote_exit=124`. A remote exit code is no longer read as a timeout.
- `test_poll_nonzero_remote_exit_content_decides` (AD-4 / TD-O-3).
- `test_poll_failure_overwrites_success` (FR-32, AC-13).
- `test_poll_three_runs_dir_bounded` — mixed outcomes, directory listing equals the §1.1 set, files below 8 KiB (AC-13, FR-34).
- `test_poll_runs_and_writes_while_project_suspended` — a suspend marker is present (AC-12, AC-27, FR-24).
- `test_poll_lock_held_exits_without_write`.
- `test_poll_stale_lock_reclaimed_diagnostic`.
- `test_poll_lib_missing_bash_crash_file` (AD-3 crash-still-writes).
- `test_poll_invalid_settings_still_polls_records_status` (AD-9).
- `test_poll_emits_no_audit` — no file appears under the repo's `audit/` (FR-34, AC-13).
- `test_check_all_pass` (FR-48).
- `test_check_idempotent_writes_nothing` — the state tree hash is unchanged after two runs; outputs identical (AC-22).
- `test_check_missing_key_fails_nonzero` (AC-22).
- `test_check_key_mode_0644_fails`.
- `test_check_crontab_append_fails`, `test_check_crontab_interval_mismatch_fails` (FR-8, FR-34).
- `test_check_forced_command_mismatch_fails`.
- `test_check_read_failure_fails` (FR-48).
- `test_print_setup_never_mutates`.
- `test_print_setup_crontab_matches_interval` (FR-8).

**`tests/framework/test_usage_pause_static.py`**
- `S1-ST1 test_no_claude_auth_env_or_token_assignment` — code lines of the poller and module: no `claude-auth.env`, no `CLAUDE_CODE_OAUTH_TOKEN=`, no `source`/`.` of `~/.config/hos` (AC-15).
- `S1-ST2 test_poller_and_lib_never_reference_suspend_or_halt` — no `suspend`, `hos-halt`, `projects.conf` (FR-24, AC-27).
- `S1-ST3 test_lib_never_uses_hos_config_dir`.
- `S1-ST4 test_lib_stdlib_only` — the AST imports are a subset of `{__future__, argparse, dataclasses, datetime, os, pathlib, re, shutil, signal, stat, subprocess, sys, time, typing}`. *Architect round 1:* `signal` and `subprocess` added for `read_usage`.
- `S1-ST5 test_sandbox_allowwrite_excludes_decision_inputs` — with `__HOME__`→`/h`, no `allowWrite` entry is a path-prefix of `/h/.hos/usage-pause/reading.status`, `/h/.config/hos/usage-pause.conf` or `/var/lib/hos-usage/x` (AF-1).
- `S1-ST6 test_consumer_files_list_both`.
- `S1-ST7 test_test_only_overrides_absent_from_runbook` — `HOS_USAGE_PAUSE_CONF`/`HOS_USAGE_PROM_PATH` do not appear in `docs/CRON-SETUP.md`.
- `S1-ST8 test_poller_has_one_ssh_invocation` — *(Architect round 1)* `bin/hos-usage-poll` has **no** `ssh` invocation, `usage_pause.py` has exactly one `subprocess`/`Popen` call site, and neither file assigns `_TIMEOUT_BIN` or invokes `timeout`/`gtimeout`.
- `S1-ST9 test_staleness_range_nonempty_for_every_interval` — *(Architect round 1)* for every valid `poll_interval_seconds` there is a valid `(read_timeout_seconds, staleness_seconds)` pair.

**`test_agent_invocation_migration.py`:** T4.1 (updated), `test_T4_1b_usage_read_has_one_call_site`, `test_T4_1b_remote_command_is_exact`, T4.2 (updated) (AD-5, AC-26).

**`test_consumer_framework_files.py`:** `test_usage_pause_files_shipped`.

### 7.2 S2 tests

**`test_usage_pause_check_cli.py`**
- `test_verdict_line_matches_bash_ere` — the ERE is copied from `bin/hos-cron` at test time via anchor extraction, so the two cannot drift.
- `test_check_writes_status_before_printing`.
- `test_transition_table` — every §4.5 row.
- `test_check_error_flag_treated_as_prev_pause`.
- `test_corrupt_prev_sets_close_pending` (TD-O-9).
- `test_record_each_flag`.
- `test_issue_body_paused_names_window_values_threshold` (FR-39, AC-3).
- `test_issue_body_failure_names_reason` (FR-39).
- `test_issue_body_settings_invalid_names_key_and_value` (Q11).
- `test_issue_body_degraded`.
- `test_check_crash_exit_70_no_stdout`.
- `test_check_status_write_failure_is_exit_70`.

**`test_hos_cron.py::TestUsagePauseGate`** — real launcher, §4.6 harness:
- `test_under_threshold_runs_claude` (AC-1 consumer side).
- `test_session_90_pauses_before_claude` — exit 0, `[PAUSED-USAGE]`, claude stub never ran (AC-2, AC-28, FR-26).
- `test_89_89_runs` (AC-2, AC-28).
- `test_weekly_90_pauses_issue_names_weekly` (AC-3).
- `test_empty_session_reading_pauses_closed` (AC-4).
- `test_failopen_failure_runs_and_records` (AC-9).
- `test_unusable_reasons_distinct` — parametrized: stale / missing / poller_not_installed / truncated / garbled / schema / future (AC-8).
- `test_auto_resume_next_cycle_closes_issue` — paused at 92, then reading 40/30, then claude ran, issue comment+close recorded, `cycle-usage-resume` audited (AC-10, FR-23, FR-38).
- `test_human_suspend_marker_untouched` — marker present plus an under-threshold reading → `[SUSPENDED]`, no `[PAUSED-USAGE]`, marker byte-identical, no per-role status written (AC-11, FR-25).
- `test_five_paused_cycles_one_issue` (AC-14).
- `test_dedup_query_failure_no_issue_still_paused` (AC-14).
- `test_issue_create_failure_still_paused_then_retries` (FR-37).
- `test_dedup_query_paginates` — the recorded gh argv contains `--paginate`, `per_page=100` and a `--jq` filter, and no `jq` process is spawned (TD-VF-2; Architect round 1).
- `test_exact_title_not_prefix` — an open issue titled `…paused on hos-dev` does not dedup `hos` (TD-VF-7).
- `test_threshold_80_applies_without_new_poll_all_projects` — conf changed after the reading was written; `hos` and a second registered project both pause (AC-23, FR-27).
- `test_transcript_wording_never_pauses` — `HOS_TEST_CLAUDE_STDOUT="Claude usage limit reached"` across two cycles plus an under-threshold reading → both run (AC-24, FR-28).
- `test_running_cycle_not_killed` — the claude stub overwrites the reading to 95% mid-session; the cycle completes and exits normally; the next cycle pauses (AC-29, AS-2).
- `test_failopen_n_failures_one_degraded_issue`, `test_failopen_n_minus_1_no_issue`, `test_success_resets_and_closes_degraded` (AC-30, AS-3).
- `test_failopen_dead_poller_degraded_issue` (AD-8 b).
- `test_gate_precedes_claude_auth_env` — `claude-auth.env` removed plus an over-threshold reading → exit 0 paused (not 78) (FR-26).
- `test_gate_precedes_halt_check` — `HOS_TEST_HALT_QUERY_FAIL` plus pause → no halt log line.
- `test_check_error_pauses_even_failopen` — the module is made unimportable by pointing `HOS_STATE_DIR` at a file path, or by a monkeypatched copy of `bin/` in a temp dir (AD-7.5).
- `test_check_error_issue_closes_after_recovery`.
- `test_invalid_settings_pause_even_failopen_issue_names_key` (Q11).
- `test_paused_cycle_one_log_line_no_audit_after_first` (AD-7, FR-34).
- `test_transition_audit_events_separate_fields` (TD-VF-6, Q17).
- `test_worker_then_overseer_one_issue` (Q15).
- `test_issue_lock_contention_skips_filing`.
- `test_no_repo_slug_still_pauses`.
- `test_both_roles_gated` — overseer is parametrized through the pause and run cases.

**`test_usage_pause_static.py` (S2 additions)**
- `S2-ST1 test_gate_anchors_unique_and_block_clean` — anchors once each; the block has no `suspend`, `hos-suspend`, `.prom`, `node_exporter`, `ssh`, `/usage`, `last-claude-output` (FR-25, FR-28, AC-11, AC-27).
- `S2-ST2 test_gate_between_git_creds_and_claude_auth` — the block's line range is after the `hos_configure_git_credentials` block and before `# ── Claude Code subscription auth`.
- `S2-ST3 test_reactive_breaker_code_unchanged` — sha256 of `bin/hos-cron` lines from `# ── DISABLED 2026-09-01 (operator request)` up to `# ── Post-cycle bookkeeping`, and of the `# #1446: symmetry with the timeout-breaker auto-close above` paragraph through its closing `fi`, equal the values recorded from the S2 base commit. `TestUsageLimitBreaker` is still decorated `@pytest.mark.skip` (AC-17, FR-40).
- `S2-ST4 test_check_invoked_once` — exactly one `usage_pause.py" check` in `bin/hos-cron`.
- `S2-ST5 test_up_bound_expansions_are_set_u_safe` — *(Architect round 1)* inside the gate block, every `_UP_BOUND` expansion is `${_UP_BOUND[@]+"${_UP_BOUND[@]}"}`. There is no standalone `jq` invocation, and the ERE match sits in a function with `local LC_ALL=C`.
- `test_gate_runs_on_bash_without_timeout` (in `TestUsagePauseGate`) — PATH with no `timeout`/`gtimeout` plus an under-threshold reading → the cycle runs, with no `unbound variable` error.

### 7.3 S3 tests

**`test_usage_pause_prom.py`**
- `test_d1_golden` — `expected-d1.prom` (FR-41, FR-42).
- `test_failure_render_absent_values` — no session/weekly/model/breakdown families; `read_ok 0`; `read_failure{reason="empty_session"} 1` (AC-4, AC-9, FR-44).
- `test_no_breakdown_absent_not_zero` (AC-18).
- `test_never_succeeded_last_success_zero`.
- `test_gauge_only_no_counters_rates` — every `# TYPE` is `gauge`; no name ends in `_total|_rate|_delta|_increase` (AC-19, FR-43).
- `test_no_sample_timestamps`.
- `test_label_values_sanitized_and_deduped`.
- `test_pause_condition_matches_evaluate`.
- `test_invalid_settings_threshold_absent_settings_valid_0` (TD-O-6).
- `test_metric_names_constant_matches_table`.

**`test_hos_usage_poll.py` (S3 additions)**
- `test_prom_written_after_reading`.
- `test_prom_unwritable_reading_and_decision_identical` — `HOS_USAGE_PROM_PATH` in a read-only dir. `reading.status`, with `run_at`/`run_epoch` masked, is byte-identical to the writable run, and the `check` verdict is identical (AD-10 isolation, FR-45).
- `test_prom_dir_absent_not_configured`.
- `test_prom_atomic_no_tmp_left` (FR-45).
- `test_two_polls_one_prom_file` (AC-13).
- `test_check_item7_symlink_pass`, `test_check_item7_fallback_args_pass`, `test_check_item7_both_fail`, `test_check_item7_neither_fail`.
- `test_check_item7_skip_when_unconfigured`.

There is no listening socket: no module or poller code line contains `socket`, `http.server`, `listen` or `bind` (AC-19 static, in `test_usage_pause_static.py` as `S3-ST1`).

### 7.4 S4 tests — `tests/framework/test_contrib_monitoring.py`

- `test_rules_yaml_structure` — pyyaml load; one group; exactly the six alert names; every `for` and `expr` as in §6.1.
- `test_rules_metric_names_exist` — every `hos_claude_usage_*` token is in `METRIC_NAMES`.
- `test_rules_promtool` — **integration**: runs `promtool check rules` when on PATH, else `pytest.skip("promtool not installed")` (TD-O-7).
- `test_provider_yaml`.
- `test_dashboard_json_parses_and_fixed_uid`.
- `test_dashboard_no_inputs_no_ds_placeholders`.
- `test_datasource_variable_prometheus`.
- `test_instance_variable_default_faberix`.
- `test_required_panels_and_exact_exprs` — panels 1, 2, 3a, 3b and 4 per §6.3 (AC-20, FR-46).
- `test_threshold_lines_from_threshold_gauge` (AC-20).
- `test_predict_linear_panel` (AC-20).
- `test_pause_annotation_from_pause_condition_named_machine` (AC-20).
- `test_subagent_panel_stacked_with_truncation_text`.
- `test_behaviors_panel_unstacked_with_independence_text` (AF-6).
- `test_dashboard_metric_names_exist`.
- `test_no_rate_increase_delta` (FR-43).
- `test_contrib_never_shipped` — no `framework_consumer_files.txt` entry starts with `contrib/`, and `hos_install.sh` has no `contrib` token.
- `test_host_values_only_in_readme_and_defaults` — `faberix` appears only in the README, rules `absent`/textfile selectors, and the `instance` default.

**AC-20 "loads through Grafana provisioning without errors"** is a recorded human step on monitrix (§6.4 step 4), attached to the S4 PR.

---

## 8. Traceability — every requirement and acceptance criterion

| Req / AC | TD section | Test(s) |
|---|---|---|
| FR-1 | §3, §4 (S1+S2 fully specified), §3.13 | whole S1/S2 suites; AC-16 record |
| FR-2 | §3.6 P8, §3.2 | `test_poll_claude_argv_exactly_dash_p_usage` |
| FR-3 | §3.6 P7–P8, §3.9, §3.12 | `test_poll_ssh_argv_matches_ad6`, `test_check_all_pass` |
| FR-4 | §3.6 P1/P8, §3.7 | `test_poll_strips_credentials`, S1-ST1 |
| FR-5 | §3.6 P8 (`-n`, `RequestTTY=no`) | `test_poll_ssh_argv_matches_ad6` |
| FR-6 | §3.6 P1, §3.4 | `test_poll_success_writes_reading` (minimal incoming PATH) |
| FR-7 | §3.1 `read_usage`, §3.6 P8 (Architect round 1) | `test_read_usage_timeout_kills_process_group`, `test_poll_needs_no_timeout_binary`, `test_poll_timeout` |
| FR-8 | §1.8, §3.8 item 5, §3.9 | `test_print_setup_crontab_matches_interval`, `test_check_crontab_interval_mismatch_fails` |
| FR-9 | §3.6 P8, §3.11 | `test_poll_claude_argv_exactly_dash_p_usage`, T4.1b |
| FR-10 | §3.2 | `test_usage_pause_parse.py` (all) |
| FR-11 | §3.3 | `test_session_only_missing_weekly`, `test_weekly_only_missing_session` |
| FR-12 | §3.3 step 2, §1.3 | `test_empty_session_is_failed_empty_session`, `test_empty_session_yields_no_number` |
| FR-13 | §3.3 | `test_poll_nonzero_remote_exit_content_decides` (TD-O-3) |
| FR-14 | §3.3 (no fallback path) | `test_poll_claude_argv_exactly_dash_p_usage` |
| FR-15 | §1.3 `parsed_via` | `test_d1_success_values` |
| FR-16 | §3.2 per-model, §3.5 note | `test_d1_model_fable`, `test_model_100_never_pauses` |
| FR-17 | §3.2 breakdown | `test_d1_breakdown_*`, `test_breakdown_*_isolated` |
| FR-18 | §1.8 | `test_missing_file_defaults` |
| FR-19 | §3.5 R9–R11 | `test_boundary_*`, `test_exact_90_is_reached` |
| FR-20 | §3.2 (no window length) | `test_window_length_never_parsed` |
| FR-21 | §3.5 R14 | `test_failure_closed_pauses`, `test_empty_session_reading_pauses_closed` |
| FR-22 | §3.5 R15–R16, §4.4 step 6 | `test_failure_open_runs`, `test_failopen_*` |
| FR-23 | §4.5 `exit` | `test_auto_resume_next_cycle_closes_issue` |
| FR-24 | §3.6 (no suspend read) | `test_poll_runs_and_writes_while_project_suspended`, S1-ST2 |
| FR-25 | §4.3 (no suspend write) | `test_human_suspend_marker_untouched`, S2-ST1 |
| FR-26 | §4.1 | `test_gate_precedes_claude_auth_env`, `test_session_90_pauses_before_claude`, S2-ST2 |
| FR-27 | §1.1, §1.8 | `test_threshold_80_applies_without_new_poll_all_projects`, `test_conf_path_never_from_hos_config_dir` |
| FR-28 | §4.3 | `test_transcript_wording_never_pauses`, S2-ST1 |
| FR-29 | §1.8 | `test_usage_pause_settings.py` |
| FR-30 | §1.8, §3.5 R1 | `test_each_key_invalid`, `test_invalid_settings_pause_even_failopen_issue_names_key` |
| FR-31 | §1.3–1.5 | `test_render_read_roundtrip`, `test_atomic_write_no_tmp_left` |
| FR-32 | §1.3, §3.6 P11 | `test_poll_failure_overwrites_success`, `test_poll_lib_missing_bash_crash_file` |
| FR-33 | §1.3, §1.4 | `test_poll_success_writes_reading`, `test_check_writes_status_before_printing` |
| FR-34 | §1.1 bound, §1.6, §3.9 | `test_poll_three_runs_dir_bounded`, `test_poll_emits_no_audit`, `test_check_crontab_append_fails` |
| FR-35 | §1.4 (snapshot only) | `test_render_read_roundtrip` |
| FR-36 | §3.5 R2–R8 | `test_stale_boundary_*`, `test_unusable_reasons_distinct` |
| FR-37 | §4.4 steps 2–4 | `test_five_paused_cycles_one_issue`, `test_dedup_query_failure_no_issue_still_paused`, `test_issue_create_failure_still_paused_then_retries` |
| FR-38 | §4.4 step 5 | `test_auto_resume_next_cycle_closes_issue` |
| FR-39 | §1.7 | `test_issue_body_*` |
| FR-40 | §2 "not touched" | S2-ST3 |
| FR-41 | §5 | `test_d1_golden`, §5.1 record |
| FR-42 | §5.2 (machine-level pause; §11 item 8) | `test_d1_golden`, `test_pause_condition_matches_evaluate` |
| FR-43 | §5.2, §6.3 | `test_gauge_only_no_counters_rates`, `test_no_rate_increase_delta` |
| FR-44 | §1.3, §5.2 | `test_failure_render_absent_values`, `test_no_breakdown_absent_not_zero` |
| FR-45 | §5.1–5.2 | `test_prom_atomic_no_tmp_left`, `test_prom_unwritable_reading_and_decision_identical` |
| FR-46 | §6.3 | `test_required_panels_and_exact_exprs` |
| FR-47 | §3.12, §2 E | `test_print_setup_never_mutates` (install provisions nothing: static S1-ST6 plus review) |
| FR-48 | §3.8 | `test_check_*` |
| FR-49 | §2 "Protected?" column | CODEOWNERS (`bin/**`) |
| FR-50 | §3.6, §3.9 | `test_poll_*`, `test_print_setup_crontab_matches_interval` |
| AC-1 | §3.2, §5.2 | `test_ac1_real_shape_success_no_breakdown`, `test_poll_success_writes_reading`, `test_under_threshold_runs_claude`, `test_d1_golden` |
| AC-2 | §3.5 | `test_boundary_session_90_pauses`, `test_89_89_runs` (unit + gate) |
| AC-3 | §3.5, §1.7 | `test_weekly_only_reason_names_weekly`, `test_weekly_90_pauses_issue_names_weekly` |
| AC-4 | §3.3, §1.3, §5.2 | `test_empty_session_*`, `test_failure_reading_has_no_pct_keys`, `test_failure_render_absent_values`, `test_empty_session_reading_pauses_closed` |
| AC-5 | §3.3 | `test_session_only_missing_weekly`, `test_weekly_only_missing_session` |
| AC-6 | §3.3, §3.6 P7 | `test_poll_ssh_255_ssh_failed`, `test_poll_key_missing_ssh_failed` |
| AC-7 | §3.1, §3.6 P8 | `test_poll_timeout` (slow), `test_read_usage_timeout_kills_process_group` (fast) |
| AC-8 | §3.5 | `test_each_unusable_reason_distinct`, `test_unusable_reasons_distinct` |
| AC-9 | §3.5 R16 | `test_failopen_failure_runs_and_records`, `test_failure_render_absent_values` |
| AC-10 | §4.5 | `test_auto_resume_next_cycle_closes_issue` |
| AC-11 | §4.1, §4.3 | `test_human_suspend_marker_untouched` |
| AC-12 | §3.6 | `test_poll_runs_and_writes_while_project_suspended` |
| AC-13 | §1.1, §1.5 | `test_poll_three_runs_dir_bounded`, `test_two_polls_one_prom_file` |
| AC-14 | §4.4 | `test_five_paused_cycles_one_issue`, `test_dedup_query_failure_no_issue_still_paused` |
| AC-15 | §3.6 P1/P8 | `test_poll_strips_credentials`, S1-ST1 |
| AC-16 | §3.13 item 2 | manual record (S1 exit criterion) |
| AC-17 | §2 | S2-ST3 |
| AC-18 | §3.2 | `test_ac1_real_shape_success_no_breakdown`, `test_d1_breakdown_*`, `test_no_breakdown_absent_not_zero` |
| AC-19 | §5.2 | `test_gauge_only_no_counters_rates`, S3-ST1 |
| AC-20 | §6.3–6.4 | `test_required_panels_and_exact_exprs` etc. plus the monitrix record |
| AC-21 | §3.3, §3.6 P8 | `test_poll_claude_argv_exactly_dash_p_usage` |
| AC-22 | §3.8 | `test_check_idempotent_writes_nothing`, `test_check_missing_key_fails_nonzero` |
| AC-23 | §4.2 (recompute) | `test_threshold_80`, `test_threshold_80_applies_without_new_poll_all_projects` |
| AC-24 | §4.3 | `test_transcript_wording_never_pauses` |
| AC-25 | §3.13 item 3 (TD-O-4) | AC-21 test plus manual record |
| AC-26 | §3.11 | full PR suite incl. T4.1/T4.1b/T4.2 |
| AC-27 | §3.6, §4.3 | `test_poll_runs_and_writes_while_project_suspended`, S1-ST2, S2-ST1, T4.1b |
| AC-28 | §3.5 | `test_exact_90_is_reached`, `test_boundary_*`, `test_session_90_pauses_before_claude` |
| AC-29 | §4.3 (cycle start only) | `test_running_cycle_not_killed`, S2-ST4 |
| AC-30 | §1.3 carry-over, §3.5 R16 | `test_failopen_degraded_at_n_not_n_minus_1`, `test_failopen_n_*`, `test_success_resets_and_closes_degraded` |
| AS-1 / AS-2 / AS-3 | §3.5 / §4.3 / §3.5 R15–R16 | `test_model_100_never_pauses` / `test_running_cycle_not_killed` / `test_failopen_*` |
| D-1 / D-2 / D-3 | §1.9 / §3.3 (no fallback) / TD-VF-10, §5.1 | `test_d1_fixture_is_verbatim` / AC-21 test / §5.1 record |

---

## 9. Questions for the architect (TD-O). Each has a binding interim, so none blocks coding.

- **TD-O-1 (TD-VF-4).** The T4.2 ledger gains `bin/hos-usage-poll` as a fourth private `_TIMEOUT_BIN` copy, with a permanent ADR-1944 AD-6 exemption. The alternative is to move the bounded exec into Python (`subprocess.run(timeout=…)` + `killpg`), which removes `no_timeout_binary` and the AD-6 argv's `timeout` prefix. *Interim: the ledger entry; AD-6 as written.*
- **TD-O-2 (TD-VF-3).** Raw `gh` in the gate instead of the bootstrap wrappers, because the wrappers do not ship to consumers, the `--list` read is incomplete, and the slug is resolved independently of `_REPO_SLUG`. This deviates from the orchestrator's preference, not from any AD. *Interim: raw `gh`, `--body-file`, bounded.*
- **TD-O-3.** FR-11 lists "non-zero exit" as a FAILED read, while AD-4 binds "not the exit code". *Interim (AD-4 literal):* transport codes (124/137/255/125–127) fail; any other remote exit is recorded and content decides. If the architect prefers FR-11 literally, `classify_transport` gains "any non-zero → `unparseable`", and that is a one-row change.
- **TD-O-4 (TD-VF-8).** AC-25 as worded ("reports `$0.0000`") is unobservable on the real success shape. *Interim:* the §3.13 item 3 substitute. pm-agent may need to reword AC-25.
- **TD-O-5.** These are stricter than AD-9: an upper bound `staleness_seconds ≤ 3600` (a typo like `staleness_seconds=90000` would otherwise be a near-disable), and a `claude_bin` charset limit (the value is interpolated into a remote command and an `authorized_keys` line). *Interim: both bind.*
- **TD-O-6.** AD-10 says `threshold_percent` is emitted "always (configured value)", but under invalid settings no configured value exists. *Interim:* omit `threshold_percent` when settings are invalid, and add the health gauge `hos_claude_usage_settings_valid` (always). `pause_condition` is 1 in that state.
- **TD-O-7.** AD-12 S4 asks for "a `promtool` lint test in CI". CI has no `promtool`, and adding it means editing `.github/workflows/**`, which is protected and would turn S4 from a normal merge into HUMAN_REQUIRED. *Interim:* structural tests in CI, an `integration`-marked promtool test, and the human's `promtool check` on monitrix as the record.
- **TD-O-8 (TD-VF-7).** Exact-title dedup replaces prefix dedup. Clarifying; confirm.
- **TD-O-9.** These are additions to AD-8, so that a lost close is retried and a destroyed episode memory still closes its issue: the `pause_close_pending`/`degraded_close_pending` retry memory, the close sweep when the previous per-role file is **corrupt**, and the `check-error` flag that makes a `check_error` episode's issue closable. *Interim: all bind.*
- **TD-O-10 (TD-VF-6).** Audit events use separate argv fields. Clarifying.
- **TD-O-11.** `lock_stale_reclaimed` moves from the failure-reason enum to a `diagnostics` key, because AD-4 itself says the read still runs. Clarifying.

**No AD was found unimplementable.** The two internal tensions are TD-O-3 (FR-11 vs AD-4) and TD-O-6 (AD-10's "always" vs invalid settings). TD-VF-4 is a test collision the ADR did not foresee, not a contradiction.

### 9.1 Architect round 1 rulings (binding; AD changes recorded in ADR-1944 Amendment 1)

- **TD-O-1: OVERRIDE. Bound the read in Python.**
  - A permanent T4.2 entry would put a non-AI read into a ledger whose purpose is AD-16.6's AI-review timeout copies. That widens a governance ledger for an unrelated concern.
  - The Python version is no more complex: one `Popen` with `start_new_session=True`, `wait(timeout)`, then `killpg` TERM→KILL.
  - It is strictly better on three counts. Timeout is *observed*, not inferred from exit code 124/137, which a remote process could also return. The macOS coreutils dependency and the `no_timeout_binary` failure mode disappear. The call site and the remote-command template move into one protected file.
  - Applied in §1.2, §2 F, §3.1, §3.3, §3.6 P5/P8/P9, §3.7, §3.8, §3.11, §7 and §8. ADR A1-1/A1-2.
- **TD-O-2: ACCEPT raw `gh`** with `--body-file`, `_REPO_SLUG`, and the bound.
  - The wrappers do not ship to consumers (`framework_consumer_files.txt:20-22` has no `bootstrap/*issue*`). They resolve the slug independently of `HOS_REPO_SLUG`. Every existing `hos-cron` issue path is raw `gh`.
  - CLAUDE.md's wrapper rule governs sandboxed agent sessions, not the unsandboxed launcher.
  - Round-1 correction: the draft's standalone `jq` is replaced by `gh --jq` with the title compared in bash (§4.4 step 2). Standalone `jq` is not a `hos-cron` dependency.
- **TD-O-3: ACCEPT AD-4 (content decides; transport failures fail); FR-11's "non-zero exit" item is overridden.**
  - FR-11 names the reference parser's condition as its source, and that condition is content-only (`[[ -n "$session_pct" && -n "$weekly_all_pct" ]]`). FR-13 forbids deciding from the exit code.
  - A non-zero remote exit with both `% used` lines present is real data. Rejecting it would produce a pause mislabelled `unparseable`.
  - `remote_exit` is still recorded.
  - Requirements amendment needed: **pm-agent** rewords FR-11's failure list from "non-zero exit" to "transport failure (ssh failure, timeout)". The architect does not edit REQUIREMENTS. This narrows a requirement, so it is also listed for human confirmation (§11 item 12). ADR A1-3.
- **TD-O-4: ACCEPT** the §3.13 item-3 substitute. AC-25 as worded cannot be observed on the real success shape. **pm-agent** rewords AC-25 to "a primary-path read makes no model call (stub-verified, AC-21) and the key can only run `/usage` when the forced command is adopted". §11 item 13.
- **TD-O-5: ACCEPT, with one correction.**
  - The `claude_bin` charset limit binds.
  - The `staleness_seconds` upper bound is **7200**, not 3600. With `poll_interval_seconds=3600` the draft's bound left no valid staleness value, which would have turned a legal interval into a guaranteed `settings_invalid` pause. Test S1-ST9 is added.
  - ADR A1-4.
- **TD-O-6: ACCEPT.** Omit `threshold_percent` when settings are invalid. Add `hos_claude_usage_settings_valid`, always emitted. `pause_condition=1`. This is honest, because no threshold is in force in that state. ADR A1-5.
- **TD-O-7: ACCEPT.** Structural tests in CI. `promtool` runs as an `integration`-marked test that is skipped when absent. The monitrix `promtool check` output is the recorded evidence. S4 does not touch `.github/workflows/**`. ADR A1-6.
- **TD-O-8: ACCEPT** exact-title match. It is strictly stricter than a prefix match and closes a real cross-project collision (`hos` vs `hos-dev`).
- **TD-O-9: ACCEPT.** The close-pending memory, the corrupt-previous-file close sweep, and the check-error flag are additive retries. They cannot unpause anything, and they cost at most one extra paginated query per affected cycle.
- **TD-O-10: ACCEPT** (one `key=value` per argv element; matches `cycle_log._parse_args`).
- **TD-O-11: ACCEPT** (`lock_stale_reclaimed` → `diagnostics`, as AD-4 itself says "the read still runs").

**Further round-1 changes, not raised by the TD:**
- §4.3 G1/G2 and §4.4: use the `set -u`-safe array expansion. Without it, bash 3.2 aborts on a host with no `timeout`.
- §4.3 G1: `--kill-after=5`.
- §4.3 G2: the ERE match runs under `local LC_ALL=C`.
- §1.1: the project-name sanitizer works on bytes.
- §4.6 item 4: copied-launcher tests also copy the lib.
- §3.8: `remote-cmd` is the single source for the forced-command text.

**Regex spot-check (architect, independent of TD-VF-11).** The architect extracted §1.9 from this file and got 1091 bytes, 20 LF, sha256 `c8d52b0a…6196683`, a match. It then ran every §3.2 pattern with `re.ASCII`:
- session 6 / `Oct 3, 2:40am (UTC)`; weekly 48 / `Oct 3, 12am (UTC)`;
- models `[all models (excluded), Fable 3]`; marker present;
- 24h: 2049/181, 61/36/34, 4 items, more 0; 7d: 13242/1442, 48/28/10, 8 items, more 2;
- empty-session: no `% used`, `Total cost:` present, `Usage:\s+0 input` matches;
- the §4.2 verdict ERE yields 14 groups and accepts a `failopen:read_failed:empty_session` reason.

All results are as the TD states.

---

## 10. Escalations

- **ESC-T1 (security-reviewer → human; pre-existing).** TD-VF-9: the sandbox `denyWrite` covers only `__PROJECT_ROOT__/bin`, while `allowWrite` covers all three clones. A sandboxed Overseer or Human session can rewrite `Worker/bin/hos-cron` today, and `Worker/bin/hos-usage-poll` once it exists. Recommendation: add `__HOS_ROOT__/{Human,Worker,Overseer}/bin` to `denyWrite`. This is a `contract/**` change (protected). It does not block #1944. Not filed; I am design-only.
  - *Architect round 1:* recorded as a **finding outside #1944's scope**. It is a pre-existing gap in shipped sandbox policy. #1944 neither widens it nor depends on closing it: the decision-path *data* stays outside every `allowWrite` (AF-1 holds), and the code is CODEOWNERS-gated (AF-2's governance half holds). AF-2's OS-level half is narrower than the ADR stated, and ADR Amendment 1 A1-7 corrects that statement. The fix is a `contract/**` (protected) change and needs security-reviewer review plus human approval. Carried to §11 item 14.
- **ESC-T2 (orchestrating session).** ESC-4 should also cover `query_issues.sh --list` being single-page (TD-VF-2) and the fifth first-page site at `bin/hos-cron:954`. Not filed. *Architect round 1:* there are more sites than that. `bin/hos-cron:1430` (`per_page=30`), `:1682`, `:1760` and `:1801` (`per_page=20`) also dedup or close from a single page. The follow-up issue must enumerate every `gh api …issues?…per_page=` site in `bin/hos-cron`, not the ADR's list. Making `query_issues.sh --list` paginate changes output for every caller, so it is a **human-owned scoping call** (§11 item 15).
- **ESC-T3: CLOSED (Architect round 1).** All four docs are on `interactive-1944-proactive-usage-pause-design`.
- **ESC-T4 (orchestrating session, minor).** The existing timeout-breaker `_audit` at `bin/hos-cron:2054` records a single collapsed field (TD-VF-6). Out of scope. Not filed. *Architect round 1:* this stands. It is cosmetic, because no decision reads that record, but it is a shipped defect in a protected file and goes in the same follow-up as ESC-T2. Human-owned filing (§11 item 16).

---

## 11. Human confirmation required (carried forward from ADR-1944 §5, unchanged and unresolved)

1. **AS-1:** only session and all-models weekly trigger a pause. Per-model weekly values are gauges only.
2. **AS-2:** gate at cycle start only. A running cycle finishes, bounded by `HOS_CRON_MAX_SECONDS`. No mid-cycle kill.
3. **AS-3:** fail-open files one deduped `[DEGRADED]` issue after **N=3** consecutive failed polls (architect's proposed default). **Plus the DERIVED extension:** under fail-open, also file it immediately when the reading file is missing or stale (dead poller), AD-8 (b).
4. **Q11 (recommended rule):** missing conf → ruled defaults. Unreadable conf, invalid value, unknown key, or duplicate key → **pause regardless of `fail_mode`**, with a `needs-human` issue naming the key. No per-key fallback to defaults. Thresholds limited to 1-100.
5. **Q12 (recommended, security-reviewer to concur):** the `authorized_keys` entry should carry `restrict,from="127.0.0.1,::1",command="env -u … <abs claude> -p /usage"`, not `from=` alone. That limits the passphrase-less key to one read-only command. The design works either way.
6. **Q5 reconciliation:** one machine **reading** file (poller) plus one fixed-path **per-role/project status** file (each cycle check), both overwritten in full. Confirm this meets the per-role/project ruling.
7. **Q15:** one pause issue per **project repo** per episode (role-agnostic title), not one machine-wide issue.
8. **FR-42 / FR-44 interpretations:** "paused state" is exported as a machine-level `pause_condition` gauge (per-role/project state stays in status files). `last_success_timestamp_seconds=0` means "none on record".
9. **Grafana:** file provisioning (`allowUiUpdates: false`) rather than UI import.
10. **ESC-1:** consumer-upgrade behavior (option a or b).
11. **Human actions (not confirmations), when each slice lands:**
    - generate the loopback key, add the `authorized_keys` line, seed `known_hosts`, add the poller crontab line, run `--check` (S1);
    - the `/var/lib/hos-usage` + symlink root step on faberix (S3);
    - the rules, `rule_files`, and Grafana provisioning on monitrix (S4).

**Added by architect round 1 (items 1–11 above are unchanged):**

12. **FR-11 narrowed (TD-O-3, ADR A1-3).** A non-zero *remote* exit with both `% used` lines present counts as a SUCCESSFUL read, and `remote_exit` is recorded. Only transport failures (ssh failure or spawn failure, timeout) and content failures are FAILED reads. pm-agent amends the FR-11 text. The human confirms, because this narrows a ruled failure list in the less-pausing direction.
13. **AC-25 reworded (TD-O-4).** pm-agent rewords it. The real success output has no cost footer, so "reports `$0.0000`" cannot be observed.
14. **ESC-T1, cross-clone `bin/` write exposure (finding outside #1944's scope).** `denyWrite` covers only each role's own `bin/`, so a sandboxed Overseer or Human session can rewrite `Worker/bin/*`, including `hos-cron` today and `hos-usage-poll` once it ships. Recommended fix: add `__HOS_ROOT__/{Human,Worker,Overseer}/bin` to `denyWrite` in `contract/sandbox-policy.template.json`. That is protected surface and needs security-reviewer review plus human approval. It does not block #1944. The human decides whether and when to file it.
15. **ESC-T2, widening the AF-3 dedup follow-up.** This covers every single-page `issues?…per_page=` dedup or close site in `bin/hos-cron` (`:954`, `:1430`, `:1682`, `:1760`, `:1801`, `:2063`, `:2167`, `:2191`, plus the commented `:2136`) and `query_issues.sh --list`'s single-page read. Making `--list` complete changes behaviour for every caller, so the human decides the scope. It does not block #1944, which binds its own complete query.
16. **ESC-T4, collapsed audit call at `bin/hos-cron:2054`.** The timeout-breaker `_audit` passes one space-joined string, so `cycle_log` records a single field. It is cosmetic (no decision reads it). Fix it in the ESC-T2 follow-up or on its own; the human decides. Out of scope for #1944.

---

## 12. Startup-gap analysis and affected sign-offs

**"Should this have been settled in the initial technical design, before any code was written against it?"** This *is* the initial technical design, and nothing for #1944 has been built (ADR §6), so **no prior sign-off is orphaned**.
- **TD-VF-2, TD-VF-3, TD-VF-4 and TD-VF-5** correct ADR-level premises before any code exists. They are caught in time; no sign-off is affected.
- **TD-VF-9** is a gap in *shipped* sandbox policy, not in #1944. The sign-offs on `contract/sandbox-policy.template.json` (#1183/#1185 era) stand for what they reviewed, which was each clone's own `bin/`. The cross-clone case is new information routed via ESC-T1. It does not invalidate them, because they never claimed cross-clone coverage.
- **TD-VF-6** affects shipped code (`:2054`). That code's sign-off stands, because the defect is cosmetic: the audit record is never read by a decision. Routed as ESC-T4.
- The #1450 breaker's sign-offs stand untouched (FR-40, S2-ST3).
- *Architect round 1:* ADR Amendment 1 (A1-1 to A1-7) revises AD-4, AD-5, AD-6, AD-9, AD-10, AD-12 and the AF-2 statement. These are the reactive revisions the startup-gap test covers, so the question is asked again. Each revision corrects a premise *before any code exists*: no design other than this TD, and no code, was approved against the superseded text. **Affected sign-offs: none orphaned.** The only artifact built against the superseded ADR is this TD, and round 1 updates it in place. No `startup-artifact-gap` issue is warranted, because the initial review is still in progress.

---

## Human Review Required

**RISK: HIGH.** This contract gates every autonomous cycle on every host running `hos-cron`, and S2 changes a shipped launcher. If it is wrong, it either stops all autonomous work (fail-closed) or lets credits billing run unwatched (fail-open). The design closes both routes with named tests:
- Every decision-path failure resolves to a *named* pause, including the helper itself crashing (`check_error`, which ignores `fail_mode`).
- Fail-open can never be silent (R15/R16, `[DEGRADED]`, dead-poller case).
- A failed read can never record 0% anywhere (§1.3, §5.2).

Three hazards the upstream documents missed are closed here:
- AD-8's suggested reader is not complete (TD-VF-2).
- The suggested wrappers would have made issue filing dead on every consumer (TD-VF-3).
- An unmodified test harness would have made the S2 PR red across the suite, inviting a "make the tests pass" weakening of the gate (TD-VF-5).

**CONFIDENCE: HIGH** on §0 (every anchor re-derived; regexes executed against the verbatim capture; node_exporter flags read live) and on §1–§4 (S1/S2). **MEDIUM-HIGH** on §5 (depends on the §5.1 root-only verification, with a verified-available fallback) and on §6 (Grafana 13's acceptance of a schemaVersion-39 classic model is expected but only the monitrix step proves it).

**BLAST RADIUS:**
- `bin/hos-cron` cycle start (both roles, every project, every consumer on upgrade);
- new `bin/hos-usage-poll` and `bin/lib/usage_pause.py`;
- `framework_consumer_files.txt`, `hos_install.sh` post-install text;
- `test_agent_invocation_migration.py` T4.1/T4.2 ledgers;
- the shared `CronEnv` fixture used by the entire `test_hos_cron.py` suite;
- the user crontab, `~/.ssh/authorized_keys`, `~/.hos/usage-pause/`, `~/.config/hos/usage-pause.conf`;
- `/var/lib/hos-usage` plus one symlink in node_exporter's textfile directory;
- monitrix Prometheus rules and Grafana provisioning.

**Change classification: STRUCTURAL** (inherits the ADR's classification): a new gate on every autonomous cycle, a new credential-bearing host path, and new host-infra artifacts. ESC-1 (§11 item 10) must clear the product-boundary checkpoint before S2 ships to consumers. S1 and S2 on faberix wait only on architect review of this document and the §11 human items.
