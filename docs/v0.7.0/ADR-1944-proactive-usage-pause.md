# ADR-1944: Proactive Claude usage-threshold pause. A standalone loopback poller writes one machine reading, `hos-cron` gates every worker/overseer cycle on it without touching `hos-suspend`, and Prometheus/Grafana get the raw values by a side path that can never affect the decision

**Status:** ACCEPTED FOR DESIGN. Binds `technical-design`. The proactive percentage check is the **core** of this ADR (AD-1 to AD-9). Nothing below defers it, softens it, or puts it behind a flag. Items that need the human are listed in §5 ("Human confirmation required") and §4 (escalations). **None of them blocks the proactive check from being designed or built.** Each one changes a default, a label, or an operator procedure. None changes whether the check exists.
**Date:** 2026-10-02
**Author:** architect
**Inputs:** `docs/v0.7.0/REQUIREMENTS-1944-proactive-usage-pause.md` (pm-agent, including Amendment 1). Its rulings are not reopened here. Also: #1944 body; #1446 comments 2026-08-17T05:17:05Z / 05:25:22Z / 07:47:00Z; PR #1450 thread; `bin/hos-cron`, `bin/hos-suspend`, `docs/CRON-SETUP.md`, `docs/SANDBOX-POLICY.md`, `contract/sandbox-policy.template.json`, `scripts/framework/machine-accounts.env`, `scripts/framework/protected_surfaces.txt`, `scripts/framework/framework_consumer_files.txt`, `bootstrap/hos_install.sh`, `tests/framework/test_agent_invocation_migration.py` (T4.1), `docs/v0.7.0/ADR-1643-deterministic-agent-invocation.md` AD-16, `bootstrap/create_issue.sh`, `bootstrap/escalate_to_human.sh`, `/home/scott/.local/bin/sync_human_clone.sh` (readable; `write_status()` at `:120-133`). Also two inputs the coordinator relayed on 2026-10-02: **a verbatim `/usage` capture taken over the loopback (D-1, now resolved)** and the **verified faberix/monitrix host facts** (§0.3).
**Consumers:** `technical-design` (next), then `unit-test`, `system-test`, `security-reviewer` (AD-6), `infra-reviewer` (AD-10/AD-11).
**Explicitly does NOT re-litigate:** the standalone 5-minute poller (FR-50), SSH loopback with personal-login credential (FR-3), `>=` (FR-19), 90/90 defaults (FR-18), fail-closed default (FR-21), overwrite-in-place status file (FR-31), the #1450 reactive breaker being obsolete and untouched (FR-40), and raw-values-only export (FR-43).

---

## 0. Verification findings

Line numbers refer to the working tree on `interactive-1944-proactive-usage-pause-design` (HEAD `b750e258e`).

### 0.1 Confirming pm-agent

- **VF-3 CONFIRMED.** The `hos-suspend` marker is `{suspended_at, reason?, until?}` at `~/.hos/suspend/<project>`. It has no owner field and no role field. `bin/hos-cron:258-286` checks it before the lock and `exit 0`s.
- **VF-4 CONFIRMED, and sharpened.** `bin/hos-cron` never reads `machine-accounts.env`. It reads exactly two things under literal `$HOME/.config/hos/`: `projects.conf` (`:172`) and `claude-auth.env` (`:877`). **Trap for the TD:** `HOS_CONFIG_DIR` (`:181`) is *per-project* (`<project>_config_dir`, e.g. `$HOME/Code/HOS/.config/hos`). It is **not** the machine-level directory. A setting resolved through `HOS_CONFIG_DIR` would be per-project and would violate FR-27.
- **VF-6 CONFIRMED.** T4.1 (`test_agent_invocation_migration.py:98-132`) is a literal regex `claude -p|claude --print` over non-comment lines in `scripts/`, `bootstrap/`, `bin/`.
- **VF-7 CONFIRMED.** `write_status()` writes key=value lines with `>` and installs an `ERR` trap.
- **VF-8 CONFIRMED.** One more defect in it, see AF-3.

### 0.2 My own findings (these change the design)

**AF-1 (HIGH): the status file must not live where `sync_human_clone.sh` puts its file.** That script writes to `/tmp/hos-human-sync-<project>.status`. `contract/sandbox-policy.template.json:167-176` puts `/tmp` in the sandboxed sessions' `allowWrite`. `~/.hos/`, `~/.config/hos/`, `~/.ssh/` and `/var/lib/` are not in it, and `~/.ssh/**` is in `permissions.deny`. If the pause input sat in `/tmp`, a worker or overseer session running with `bypassPermissions` could write `session_pct=0` and unpause itself. **We mirror the pattern but not the location.** Every file on the decision path lives outside every sandboxed role's `allowWrite` (AD-3).

**AF-2 (HIGH): all code on the decision path must sit on protected surface.** `bin/**` is protected (`protected_surfaces.txt`, CODEOWNERS → HUMAN_REQUIRED). It is also OS-level `denyWrite` for sandboxed sessions (`SANDBOX-POLICY.md` §`denyWrite`). `scripts/automation/lib/` is neither. If the parser or decision logic lived there, the worker could weaken its own brake through an ordinary LOW-tier PR that the overseer may auto-merge. The poller, the parser/decision library, and the cycle check therefore all live under `bin/` (AD-2).

**AF-3 (MEDIUM, pre-existing defect, out of scope to fix): the #1435/#1446 dedup query is first-page only.** `bin/hos-cron:2066` (and `:2134`, `:2164`, `:2188`) dedups with `issues?state=open&labels=needs-human&per_page=20` and then filters by title prefix. pm-agent's VF-5 in ADR-1604 counted **56** open `needs-human` issues. Once more than 20 exist, an already-open breaker issue can fall off page 1, the filter returns 0, and **a duplicate is filed.** This "dedup" fails open. FR-37 says to *reuse #1450's pattern*. We reuse its *shape* (stable prefix, fail-closed on error, auto-close), and AD-8 binds a complete query. The existing sites are not changed by #1944. That needs its own issue (ESC-4).

**AF-4 (HIGH): `bin/hos-cron` ships to every consumer, so a fail-closed check would stop every consumer on upgrade.** `framework_consumer_files.txt` ships `bin/hos-cron`, and `hos_install.sh:1904-1916` copies it. A consumer host that upgrades without a poller has no status file. Under the ruled fail-closed default, every worker and overseer cycle on that host then pauses. That is correct by the ruling, and it is loud (AD-8 files an issue naming `poller_not_installed`). It is also a deployment-topology and operational-burden change for every consumer, which puts it under the product-boundary checkpoint (ESC-1). It does **not** change what ships on this host.

**AF-5 (LOW): T4.1's regex cannot see a variable-path invocation.** `bin/hos-cron:899` and `:1849` run `"$CLAUDE_BIN" --print`, and T4.1 does not match either. A `/usage` call written as `"$claude_bin" -p /usage` would also pass T4.1 silently. AD-5 does not lean on that blind spot. It records the exemption explicitly.

**AF-6 (from the D-1 sample): the requirements' "subagent-breakdown %" is not a breakdown.** The real section says: *"Behaviors are independent characteristics, not a breakdown."* The three behavior lines (subagent-heavy, >150k context, 8+ hours) overlap. Summing or stacking them would invent a number. Only the "Top subagents" list is attribution, and it is **truncated** (`+2 more`). AD-4, AD-10 and AD-11 carry this through.

### 0.3 Verified host facts (coordinator, 2026-10-02; treated as ground truth)

- **D-1 RESOLVED.** Verbatim loopback capture (2026-10-02) has: line 1 `You are currently using your subscription to power your Claude Code usage`; `Current session: 6% used · resets Oct 3, 2:40am (UTC)`; `Current week (all models): 48% used · resets Oct 3, 12am (UTC)`; `Current week (Fable): 3% used · …` (the `·` is U+00B7). There is a breakdown section with two windows, `Last 24h · 2049 requests · 181 sessions` and `Last 7d · 13242 requests · 1442 sessions`. Each window has three behavior lines and a `Top subagents: name N%, …, +K more` line. The `usage-parse.sh` grep regexes match lines 3-5 exactly.
- **D-3 RESOLVED.** `prometheus-node-exporter` 1.10.2 (`1.10.2-1ubuntu0.26.04.1~esm1`) is **reinstalled** on faberix. monitrix reports `up{instance="faberix"}=1` and `node_scrape_collector_success{collector="textfile"}=1`. The textfile directory is `/var/lib/prometheus/node-exporter/`, `root:root 0755`, holding root-written `apt.prom`, `nvme.prom`, `smartmon.prom`. `/etc/default/prometheus-node-exporter` has `ARGS=""`. **Fragility:** this is an ESM build. The 10-01 release upgrade marked the previous ESM build "Foreign" and it was purged. A future release upgrade can remove it again (handled in AD-10/AD-11).
- **monitrix:** Prometheus job `linux_servers` (`scrape_interval: 15s`) already targets `192.168.1.12:9100` with labels `instance="faberix", role=server, os=ubuntu`. `rule_files` is commented out. Alertmanager is configured at `localhost:9093`. Grafana is 13.2.3, and its provisioning directories hold only `sample.yaml` (dashboards are managed in the UI today).

### 0.4 Verification gaps

- Whether node_exporter 1.10.2's textfile collector follows a **symlink** in its directory. AD-10 depends on this, and the TD must verify it on faberix before S3 is coded (AD-10 gives a fallback).
- Which Alertmanager receivers exist on monitrix. AD-11's alerts route wherever the existing config sends them.
- AC-16 (a successful read under **real cron**, not an interactive SSH) has not been recorded for the shipped poller. It is an S1 exit criterion.

---

## 1. Context: what this is after §0

Three processes share one fact: *how much quota is left*.
- A machine-level **poller** learns that fact, using a credential nothing else may touch.
- Each project's **worker and overseer** cycles act on it.
- **monitrix** displays it.

The design draws one line, and the August failure is what drew it. **The pause decision depends only on: the reading file, the settings file, and the clock.** It does not depend on Prometheus, Grafana, the audit trail, GitHub, a transcript, or the `hos-suspend` marker. Each of those can fail, and none of those failures can turn "can't confirm under threshold" into "run". Under the default, every failure mode on the decision path resolves to **pause, with a named reason**.

---

## 2. Decisions (BINDING on `technical-design`)

### AD-1: The proactive check is the core deliverable. It ships enabled, with no off switch. (BINDING; FR-1, FR-26, FR-50.)

- There is no `enabled=` setting, no env var, and no flag that bypasses the cycle-start check. The ruled operator lever is `fail_mode=open` (FR-21). Even in that mode, every failure is still recorded and surfaced (AD-8).
- The work is done only when **S1 and S2 are both merged** (AD-12). S3/S4 (dashboards) without S2 do not satisfy #1944.
- **If any blocker prevents a real `/usage` read in production** (for example, a CLI change that breaks the loopback read), the build **stops and escalates `needs-human`, naming the blocker** (FR-1). It does not ship a reactive or partial substitute. The #1450 block at `bin/hos-cron:2090-2155` and its live auto-close half at `:2181-2202` are not touched (FR-40, AC-17).

### AD-2: Component placement. Every file on the decision path lives under `bin/` (protected surface, sandbox `denyWrite`). (BINDING; AF-2, FR-49, FR-50.)

| Component | Path | Role |
|---|---|---|
| Poller entry point | `bin/hos-usage-poll` (bash) | Cron-invoked. Pins PATH, takes the lock, runs the bounded SSH read, calls the library, writes the reading file, then (best-effort) the `.prom`. `--check` = preflight (AD-6). `--print-setup` = prints the exact `authorized_keys` line, crontab line, and root commands (never mutates). |
| Parser / settings / decision library | `bin/lib/usage_pause.py` (Python 3, **stdlib only**) | Pure functions: `parse_usage(text)`, `load_settings(path)`, `evaluate(reading, settings, now)`, `read_status(path)`, `render_status(...)`, `render_prom(...)`. Also a small CLI used by both callers. |
| Cycle-start check | inline block in `bin/hos-cron` (AD-7) | Calls `usage_pause.py check …`, then does the bash side effects (audit, issue, log) in the existing hos-cron style. |

- **Python, not `grep -P`.** The `usage-parse.sh` *regexes and success condition* are reused unchanged in meaning (FR-10). They are ported to Python `re` because BSD `grep` (macOS, which `hos-cron` supports, `:118-131`) has no `-P`, and because the decision logic must be unit-testable without a shell harness. This is reuse of the verified asset (the patterns), not re-derivation.
- `bin/hos-usage-poll` and `bin/lib/usage_pause.py` are added to `scripts/framework/framework_consumer_files.txt` (they ship with `hos-cron`, which depends on them). See AF-4 / ESC-1 for consumer impact.
- **Version skew.** The poller runs from one clone and `hos-cron` from each project's clone. The reading file carries `schema=1`. A consumer that sees an unknown schema treats the file as unreadable (fail mode, reason `schema_unknown`).

*Rejected:* `scripts/automation/lib/` (not protected, so the worker could edit its own brake, AF-2). `bootstrap/` (protected, but it is the machine-setup bundle and is not copied wholesale by the installer. The poller is a cron entry point, and those live in `bin/` next to `hos-cron`/`hos-trim-logs`).

### AD-3: Status files. One machine-level **reading file** written by the poller, plus one fixed-path **per-role/project status file** written by each cycle check. Both are overwritten in full and never grow. (BINDING; FR-31-FR-36, FR-27, Q5, AF-1.)

**Reconciling Q5.** The 08-17 ruling's "one fixed-path status file per project/role" was written when the read was assumed to run inside each role's cycle. With one poller (FR-50) and a machine-wide quota (FR-27), the *reading* is a single fact. Writing N copies of it would add a failure mode (copies disagree after a partial run) and would couple the poller to `projects.conf`. The design keeps both rulings literally:

1. **Reading file (machine):** `${HOS_STATE_DIR:-$HOME/.hos}/usage-pause/reading.status`. One file, written by every poll, covering successes, failures and crashes.
2. **Per-role/project status file:** `${HOS_STATE_DIR:-$HOME/.hos}/usage-pause/<role>-<project>.status`. One file per role/project, rewritten in full by **every cycle check**. It holds that cycle's view: the reading it consumed (copied values, reading age), the **pause decision and reason** (FR-33), and episode memory (`paused_since`, open issue number). This is the "fixed path per role/project, overwritten every run" of the ruling, and it is what AD-8 uses for transition detection.

The intent ("fixed path, overwritten, never grows, consumers read only the current snapshot") holds for both. This reconciliation is listed for confirmation in §5 because Q5 asked for any ruling refinement to go back to the human.

**Format** (both files): `key=value` lines, as in `write_status()`. Every value is a single line, sanitized (CR/LF/control characters stripped, length-capped). The first line is `schema=1` and the last line is the sentinel `end=1`.

**Write discipline.** This uses `write_status()` semantics (full overwrite at a fixed path; failure states written; an `ERR`/`EXIT` trap writes `outcome=crashed`), made atomic. Content goes to a fixed sibling temp name (`<file>.tmp`, same directory), then `rename(2)`. A crash leaves at most one fixed-name temp file, so nothing grows. The sentinel is defence in depth: a reader that finds no `end=1` treats the file as truncated (FR-36, AC-8).

**Reading file keys (minimum):**
- `schema`, `run_at` (UTC ISO-8601), `run_epoch`
- `outcome` = `success|failure|crashed`, `reason` (closed enum, AD-4), `detail` (≤200 chars, sanitized, failure only)
- `session_pct`, `weekly_all_pct`, `weekly_model_<slug>_pct` (one per model line), `parsed_via=grep`
- `session_resets`, `weekly_all_resets`, `weekly_model_<slug>_resets` (raw text, **status file only**; Q13 ruling: no year in the source, so no metric)
- `subscription_marker=present|absent` (informational, AD-4)
- breakdown fields per window (AD-4)
- `consecutive_failures` (carried from the previous file; an unreadable previous file restarts it at 1 on a failure), `last_success_epoch` (carried)
- `machine_decision=pause|run` + `machine_decision_reason`, evaluated with the settings at poll time. **Informational only:** the consumer recomputes (AD-7).
- `settings_status=defaults|file|invalid:<key>`
- `end=1`

**Absent means absent.** A value the poll did not obtain is **omitted** from the file, never written as `0` or empty-as-zero (FR-12, FR-44, AC-4). A failed read writes no `session_pct`/`weekly_all_pct` at all.

**Location** is outside every sandboxed role's `allowWrite` and `allowRead` (AF-1). The TD adds a static test asserting that neither `~/.hos` nor `~/.config/hos/usage-pause.conf` appears in `contract/sandbox-policy.template.json` `allowWrite`.

### AD-4: Parser and read classification, pinned to the D-1 sample. No model fallback ships in v1. (BINDING; FR-10-FR-17, FR-9, FR-14, FR-15, D-1, D-2, Q18.)

**Success criterion (FR-11, FR-13).** A read is SUCCESSFUL **only if** it yields an integer `session_pct` from the `Current session: N% used` line **and** an integer `weekly_all_pct` from the `Current week (all models): N% used` line. These are the reference regexes, last match wins, as in `tail -1`. Nothing else decides success: not the exit code, not stderr, not the line-1 subscription marker.

- *The marker is recorded, not required.* `subscription_marker` is captured for diagnosis. It is **not** part of the success criterion, because it is product copy that can change wording and its absence says nothing the % lines do not. The silent-empty shape already fails because it has no % lines. Requiring the marker would add a second way to fail on a harmless copy edit without catching anything new.
- **No clamping.** Percentages are `[0-9]+`, and values above 100 are accepted as-is (credits overflow, per D-1's note). A non-integer format (e.g. `48.5%`) does not match, so the read FAILS. That is loud and safe. The TD must not "helpfully" accept decimals without a captured sample showing them.
- **Decoding.** Input is read as bytes, decoded UTF-8 with `errors="replace"`, and ANSI escapes are stripped. Behavior must not depend on cron's locale (the `·` is U+00B7). Input is capped at 64 KiB.

**Failure reasons** (closed enum, stable for gauges and AC-8 distinctness):
- `ssh_failed`: ssh exit 255, key missing, `from=` rejected, connection refused
- `timeout`: outer bound hit
- `empty_session`: the FR-12 shape (contains `Total cost:` and/or `Usage: 0 input`, and no `% used` line). This shape **never** yields any numeric value anywhere.
- `missing_session` / `missing_weekly`: one of the two lines is absent (AC-5)
- `unparseable`: neither line, and not the empty shape
- `claude_not_executable`
- `no_timeout_binary`: neither `timeout` nor `gtimeout` exists. The read is **refused**, not run unbounded (FR-7).
- `lock_stale_reclaimed` (diagnostic only; the read still runs)
- `crashed`

**Per-model weekly (FR-16, AS-1).** Matches `Current week \(([^)]+)\): N% used`, excluding `all models`. The model name is slugified to `[a-z0-9_]`. These values are **gauges only and never feed the decision** (AS-1, pending confirmation).

**Breakdown (FR-17, AF-6).** Parsed per window `w ∈ {24h, 7d}` from the header `Last (24h|7d) · N requests · M sessions`:
- `requests_<w>`, `sessions_<w>`
- `subagent_heavy_pct_<w>` (`… came from subagent-heavy sessions`)
- `long_context_pct_<w>` (`… was at >150k context`)
- `long_session_pct_<w>` (`… sessions active for 8+ hours`)
- `top_subagents_<w>`: an ordered list of `name=pct` pairs, plus `top_subagents_more_<w>`, the `+K more` integer. When the line parsed and has no `+K more`, this is `0`, which is a *known* zero. It is absent when the line did not parse.

Every breakdown field is parsed **independently**. A miss, a format change, or an exception in any breakdown parse leaves that field absent and **cannot** change `outcome` (FR-17, AC-18). Breakdown fields **never** feed the decision.

**Fixture.** The TD pins every regex against the verbatim 2026-10-02 capture, committed as a test fixture (with the coordinator's path as provenance). The TD also adds the FR-12 empty-session text (PR #1450 07:48:32Z, Test 1) and the AC-1 real-shape values as fixtures. Regexes pinned to a paraphrase are not acceptable.

**Haiku fallback: not shipped in v1.** There is no code path for it, so a grep miss is a FAILED read (FR-14). AC-21 is met by a stub `claude` asserting it was invoked exactly once, with `/usage` and no model or prompt arguments. `parsed_via` is always `grep` in v1, and the field stays in the schema (FR-15) so a future verified fallback is distinguishable. *Rejected:* shipping it disabled. An unverified path in the tree is the "structurally correct, never run" class this repo has been bitten by (ADR-1604 AF-1). It would also be a bare-model call, which ADR-1643 AD-3/AD-16 do not admit (Q18 is moot until D-2, and any future fallback goes through `invoke_agent.sh` with a shipped agent).

### AD-5: The `/usage` call site is an on-the-record exemption from ADR-1643 AD-16. It is not routed through `invoke_agent.sh`. (BINDING; Q8, VF-6, AF-5, FR-9.)

`/usage` invokes no model, has no agent, has no verdict, and must run under a credential `invoke_agent.sh` must never use (the personal login, reached by SSH). `invoke_agent.sh` exists to give *agent* invocations a deterministic envelope (ADR-1643 AD-16: "nothing else invokes `claude --agent` directly"). Routing a non-agent, non-model read through it would either fail its preconditions (no agent file) or force a bare-model escape hatch into the primitive, which AD-16 forbids. This mirrors the `setup_clis.sh` exemption: the call must not depend on the thing it is not.

How the exemption is recorded, so it cannot be silently widened:
1. `bin/hos-usage-poll` is the **only** file in `bin/`, `scripts/`, `bootstrap/` whose code invokes `claude` with `/usage`. Its remote command is exactly `env -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN <claude_bin> -p /usage`. There are no other arguments, no `--model`, and no stdin prompt.
2. **New test T4.1b** (`tests/framework/test_agent_invocation_migration.py`) asserts (1). It checks that this is the sole `/usage` call site and that the poller's claude argv is exactly that, so any added argument (a model, a prompt) fails the build.
3. If the invocation is written so that T4.1's literal regex matches (e.g. a literal `claude -p /usage` in the forced-command template the poller prints), then `bin/hos-usage-poll` is added to `_T4_1_EXPECTED_EXEMPTIONS` as `# EXEMPT (permanent, ADR-1944 AD-5): non-agent /usage read`. Either way, a comment in T4.1's exemption block names this ADR so the next reader sees the site. **The design must not depend on AF-5's regex blind spot to pass.**
4. A one-line comment at the call site cites this AD.

*Rejected:* routing through `invoke_agent.sh` (reasons above). A blanket "non-model calls are exempt" rule (unbounded, and it invites the next site to self-classify).

### AD-6: The SSH read: options, time bound, credential hygiene, and the forced-command recommendation. (BINDING except the `authorized_keys` options, which are a §5 recommendation; FR-3-FR-7, FR-47, FR-48, Q2, Q9, Q12, Q14.)

**Invocation** (from `bin/hos-usage-poll`, no shell `eval`, argv array):

```
<timeout_bin> --kill-after=5 <read_timeout_seconds> \
  ssh -n -i ~/.ssh/hos_loopback \
      -o BatchMode=yes -o IdentitiesOnly=yes -o RequestTTY=no \
      -o ConnectTimeout=10 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 \
      -o StrictHostKeyChecking=yes -o LogLevel=ERROR \
      127.0.0.1 '<remote command from AD-5.1>'
```

- **`-n` and `RequestTTY=no`.** No stdin and no pty, explicitly. FR-5 says pty never mattered, so we request none and get no warning noise. This is not a pty workaround.
- **`StrictHostKeyChecking=yes`.** The runbook seeds `known_hosts` for `127.0.0.1` once. A changed host key is a FAILED read (`ssh_failed`), never an auto-accept.
- **`IdentitiesOnly=yes`.** Cron has no agent socket, and this stops an unrelated agent key from being offered.
- **Time bound (Q9).** `read_timeout_seconds` defaults to **60** and is configurable (AD-9). It must be `< poll_interval_seconds`. A timeout is a FAILED read (`timeout`, AC-7). Outer `--kill-after` guarantees termination. The poller's whole run is therefore bounded by about 75s plus local I/O, well inside the 300s interval.
- **Credential hygiene (FR-4, AC-15).** The poller never sources `claude-auth.env`. A static test greps `bin/hos-usage-poll` and `bin/lib/usage_pause.py` for `claude-auth.env`, `CLAUDE_CODE_OAUTH_TOKEN=` assignments, and `source`/`.` of any `~/.config/hos` file. The poller `unset`s the three variables in its own process. sshd does not forward them anyway (`SendEnv` is not used). The remote `env -u …` covers anything the remote shell's startup files set.
- **PATH / claude path (FR-6).** The poller pins `PATH` exactly as `hos-cron:118-131` does. `claude_bin` is an absolute path (setting, AD-9). When it is unset, `--check`/`--print-setup` resolve it with the pinned PATH and print it. At poll time an unset value resolves the same way, and failure is `claude_not_executable`. The value is baked into the printed `authorized_keys` line, so the forced command never relies on sshd's PATH.
- **Overlap.** The poller takes a non-blocking mkdir lock at `~/.hos/locks/usage-poll.lock`, with a 10-minute age ceiling (the `hos-cron` pattern). If the lock is held, it exits without writing. The other run writes.
- **Not gated by `hos-suspend` (FR-24, AC-12, AC-27).** The poller reads no suspend marker, no halt issue, and no project state. The TD adds a static test for this.

**`authorized_keys` entry, Q12 (recommendation; security-reviewer + human, §5).** The ruled minimum is `from="127.0.0.1,::1"`. **I recommend adding a forced command and `restrict`:**

```
restrict,from="127.0.0.1,::1",command="env -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN /home/scott/.local/bin/claude -p /usage" ssh-ed25519 AAAA… hos-loopback
```

- **Why.** As ruled, the key is a passphrase-less, cron-readable credential that grants **an arbitrary shell as scott** to anything able to reach loopback with it. With the forced command it grants exactly one read-only, zero-cost command. `restrict` (OpenSSH ≥ 7.2) adds no-pty, no port, agent or X11 forwarding, and no `~/.ssh/rc`. This is least privilege with no functional cost, since the poller only ever wants that one command. The forced command ignores the client's command (it goes to `SSH_ORIGINAL_COMMAND`), so the poller's explicit remote command (AD-5.1) works identically with or without the restriction. **The design is correct under both, and the human chooses.**
- **Cost of the recommendation.** If the claude install path moves, the `authorized_keys` line must be regenerated (`--print-setup`). `--check` detects the mismatch, because the read fails with `claude_not_executable` or `unparseable`.

**Runbook (Q14, FR-47).** A new `docs/CRON-SETUP.md` **§2a "Usage-pause poller (SSH loopback)"**, directly after §2 (the #728 auth runbook, VF-5). It covers:
- keypair generation (`ssh-keygen -t ed25519 -N '' -f ~/.ssh/hos_loopback`)
- the `authorized_keys` line, printed by `--print-setup`
- seeding `known_hosts`
- the settings file (AD-9)
- the crontab line (below)
- `bin/hos-usage-poll --check`

`MACHINE-ACCOUNTS-SETUP.md` gets a one-line pointer. `hos_install.sh` does **not** provision any of this (FR-47). In its post-install summary it **prints** the §2a pointer, the same way it already prints crontab suggestions (`hos_install.sh:2526-2533`).

**Crontab line (FR-50, FR-34).** The human adds it (sandboxed sessions are denied `crontab`, `sandbox-policy.template.json`):

```
*/5 * * * *  /home/scott/Code/HumanOversightSystem/Worker/bin/hos-usage-poll > /home/scott/.hos/usage-pause/poll.last.log 2>&1
```

- **`>`, not `>>`.** This is a fixed-path last-run log, overwritten every run (FR-34). The existing `hos-cron` lines' `>>` logs are pre-existing and out of scope.
- **One entry per host,** regardless of how many projects run there.
- `--print-setup` emits this line, with `*/N` derived from `poll_interval_seconds` (must be a whole number of minutes, AD-9).

**Preflight `--check` (FR-48, AC-22).** Read-only, idempotent, and writes **no** state: no reading file, no `.prom`. Runs from a terminal or the runbook. It checks, reporting each line as PASS/FAIL, and exits non-zero on any FAIL:
1. the key exists with mode 0600
2. `authorized_keys` carries a line for its public key with `from="127.0.0.1,::1"` (and reports whether `restrict`/`command=` are present)
3. `known_hosts` has `127.0.0.1`
4. the settings file is valid (or absent, meaning defaults)
5. exactly one crontab line invokes `hos-usage-poll`, at an interval matching `poll_interval_seconds`
6. **one real loopback read classifies as SUCCESSFUL** (FR-48; the read itself, not an assumption)
7. (S3) the `.prom` path is writable and the symlink resolves (AD-10)

A failure in production is still just a FAILED read, so the fail mode applies and it is never silent.

### AD-7: The cycle-start check in `bin/hos-cron`. It is a stateless gate re-evaluated every cycle. It never writes, reads-to-clear, or removes a `hos-suspend` marker. (BINDING; FR-19, FR-21, FR-23-FR-26, FR-28, FR-36, Q16, AS-2.)

**Pause = this cycle exits 0 before any Claude session starts.** There is no pause marker. Every cycle re-derives the decision from the reading file, the settings, and the clock. Therefore:
- **Auto-resume (FR-23, AC-10)** is structural. The first cycle that sees a fresh successful reading with both windows `<` threshold runs. Nothing needs clearing.
- **FR-25 / AC-11 hold by construction.** The existing `hos-suspend` check (`:258-286`) still runs first, before the lock. A human or timeout-breaker marker still stops the cycle before this gate is reached, and this mechanism contains no code path that writes, edits, or deletes anything under `~/.hos/suspend/`. A static test asserts that the new block and `usage_pause.py` never reference `suspend/` or invoke `hos-suspend`.

*Rejected: reusing the `hos-suspend` marker* (Q16). It is project-keyed and role-blind and has no owner field (VF-3). Auto-clearing it would wipe human suspensions unless an owner field were added. That is a schema change to a shipped human control, made to solve a problem a stateless gate does not have. It would also make `hos-suspend --list` the place a usage pause shows up, rather than the issue queue the ruling chose.

**Placement in the cycle-start sequence.** Immediately **after** the deterministic git-credentials block (`:855-868`) and **before** the Claude subscription-auth block (`:870`):
- **after GitHub auth**, because AD-8's issue filing/closing needs `GH_TOKEN` and `_REPO_SLUG`;
- **before** `claude-auth.env` is sourced, before the optional model auth probe (`:895-904`, a model call), and before every later stage (halt check, milestone resolution, actionable-work gate, git sync, the worker baseline test run, the session). It is therefore before **any** Claude session in the cycle (FR-26), and it also skips the expensive sync/baseline on paused cycles;
- the same block serves **both roles**. There is no role branch before this point.

**Decision rule (evaluated by `usage_pause.py check --role R --project P`; the bash block acts only on its single-line verdict):**
1. **Load settings (AD-9).** If invalid, the verdict is **pause**, reason `settings_invalid:<key>`, **regardless of `fail_mode`** (Q11).
2. **Read the reading file.** The following are **unusable**, each with its own reason (AC-8):
   - missing: `status_missing`. If the conf file is also missing and `~/.ssh/hos_loopback` is absent, the more specific `poller_not_installed` is used (AF-4).
   - no `end=1`: `status_truncated`
   - unknown schema: `schema_unknown`
   - unparseable: `status_unreadable`
   - `run_epoch` older than `staleness_seconds`: `status_stale`
   - `run_epoch` more than 120s in the future: `status_future`
3. If the file is usable and `outcome=success`: **pause** iff `session_pct >= session_threshold` **or** `weekly_all_pct >= weekly_threshold` (FR-19, AC-2, AC-3, AC-28). The reason names the window(s), the value(s), and the threshold(s) (FR-39). Otherwise **run**.
4. If unusable, or `outcome≠success`: under `fail_mode=closed`, **pause** with the reason (`read_failed:<reason>` or the step-2 reason). Under `fail_mode=open`, **run**, recorded (AD-8 degraded path).
5. If the check helper itself crashes, prints nothing, or prints an unparseable verdict: **pause**, reason `check_error`, regardless of `fail_mode`. The fail mode cannot be trusted when the code that reads it has failed.

**The consumer recomputes from raw values and current settings.** It never trusts the reading file's `machine_decision`. A threshold change therefore applies at the next cycle with no new poll (AC-23), and a garbled decision field cannot unpause anything.

**FR-28 / AC-24.** No input to this decision comes from any session transcript, `last-claude-output`, or log. The test drives a transcript containing threshold wording with an under-threshold reading and asserts **run**.

**AS-2 (pending, §5).** The gate runs at cycle start only. A cycle already running finishes, bounded by `HOS_CRON_MAX_SECONDS`. There is no mid-cycle kill (AC-29).

**Per-role/project status file (AD-3.2)** is rewritten by every check, before the bash block acts.

**Paused-cycle output.** One log line per paused cycle on stdout (the existing cron log), e.g. `[PAUSED-USAGE] session 92% >= 90%`. **No** audit event per paused cycle (AD-8).

### AD-8: Visibility. One audit event per transition, and one deduped `needs-human` issue per **project repo** per episode, auto-closed on resume. The query is complete, and both dedup and filing fail closed. (BINDING; FR-34, FR-37-FR-39, FR-22, AS-3, Q15, Q17, AF-3.)

**Transitions** are detected by comparing the new decision with the previous per-role/project status file (AD-3.2). If the previous file is unreadable, it counts as "run", so a fresh pause still files (dedup protects against repeats).

**Audit (Q17: yes, transitions only).** `_audit cycle-usage-pause "role=… reason=… session_pct=… weekly_pct=… reading_age=…"` on run→pause, and `_audit cycle-usage-resume "role=… paused_since=…"` on pause→run. There are no per-poll events and the poller emits no audit (FR-34, AC-13). **No decision reads an audit event** (the ADR-1604 AD-4 rule, for the same reason as its AF-2 lost-write finding).

**Pause issue (FR-37/38/39).**
- Title prefix, role-agnostic and project-scoped, distinct from both breakers: `[PAUSED] Claude usage threshold — autonomous cron paused on ${PROJECT}`. Worker and overseer of the same project therefore dedup against **one** issue.
- Label: `needs-human`. The TD confirms against `docs/LABELS.md`. `needs-ai` is **not** added, because no agent can act on it while paused, unlike the breakers' issues.
- Body: window(s) `>=` threshold with values, or the failure/stale reason and detail; the reading's `run_at`; the settings in force; and how to resume (nothing to do, it auto-resumes; or set `fail_mode=open` if the check itself is misfiring).
- **Filed** on a paused cycle when the per-role/project status file has no `issue_number` for the current episode. It is attempted on later paused cycles until it succeeds, which gives at most one issue per episode even if a human closes it mid-episode (the issue number is remembered).
- **Dedup must be complete (AF-3).** Either query by title across *all* open `needs-human` issues using a paginating reader that refuses truncated results (`bootstrap/query_issues.sh --list`, or the equivalent `gh api --paginate`), or use the search API scoped to the title prefix. A query error or a truncation means **no filing this cycle** (fail-closed, AC-14).
- **Cross-role race.** A mkdir lock at `~/.hos/locks/usage-pause-issue-${PROJECT}.lock` (non-blocking; on contention, skip this cycle) wraps query and create.
- **A filing failure never prevents the pause** (FR-37, AC-14). The pause is decided and applied before any GitHub call.
- **Auto-close (FR-38, AC-10):** on the pause→run transition, close every open issue with the prefix (same complete query), with a comment giving the resuming reading.

**Q15 recommendation: one issue per project repo.** Each repo's queue should explain why *its* cron went quiet. On this host that means one issue in each of the HOS and CPS repos per episode. A single machine-scoped issue would have to live in one repo, leaving the other repo's silence unexplained. Pending confirmation (§5).

**Degraded path (`fail_mode=open`; FR-22, AS-3).** A separate prefix: `[DEGRADED] Claude usage check failing — fail-open, cron NOT paused on ${PROJECT}`. It is filed with the same dedup and lock discipline when either:
- (a) the reading is `outcome≠success` with `consecutive_failures >= failopen_issue_after` (default **3**, i.e. 15 minutes at a 5-minute poll, matching the staleness window); AC-30: N-1 failures file nothing, and one success resets the count via the poller; or
- (b) **[DERIVED, §5]** the reading file is unusable (missing, stale, truncated, unknown schema) on a fail-open cycle.

(b) closes a hole AS-3 does not name. With fail-open plus a **dead poller**, there are no "failed polls" to count, the check is silently absent, and credits billing runs unwatched. That is exactly the #1362/#1369 class this feature exists to prevent. The issue auto-closes on the first fresh success. A degraded state also emits one `cycle-usage-degraded` audit event on entry.

### AD-9: Settings: `$HOME/.config/hos/usage-pause.conf`, key=value, **parsed, never sourced**. Missing file means the ruled defaults. Any invalid value means pause, loudly. (BINDING; recommendation on Q11 pending, §5; FR-8, FR-18, FR-21, FR-27, FR-29, FR-30, FR-36, AC-23.)

**Location (Q3).** `$HOME/.config/hos/usage-pause.conf`, the machine-level directory `hos-cron` already reads (`projects.conf`, `claude-auth.env`). It is resolved from **literal `$HOME`**, never `HOS_CONFIG_DIR` (VF-4 trap). One file per host user means every project's worker and overseer, and the poller, read the same values (FR-27).

*Rejected:*
- `scripts/framework/machine-accounts.env`: committed per repo, never read by `hos-cron`, so it is per-project in practice (VF-4).
- `projects.conf` keys: that file's grammar is `<project>_<key>`, which is per-project by design.
- env vars: a crontab line could set them per project and silently diverge projects (FR-27). `HOS_STATE_DIR` and a `HOS_USAGE_PAUSE_CONF` path override exist **for tests only**. They are documented as such and are not mentioned in the runbook.

**Grammar.** `key=value`, `#` comments, no quoting, no expansion. It is read with a line parser, never `source`d (sourcing executes code from a file the poller reads on every run).

| Key | Default | Valid |
|---|---|---|
| `session_threshold` | `90` | integer 1-100 |
| `weekly_threshold` | `90` | integer 1-100 |
| `fail_mode` | `closed` | `closed` \| `open` |
| `poll_interval_seconds` | `300` | integer multiple of 60, 60-3600 |
| `staleness_seconds` | `900` | integer `> poll_interval_seconds + read_timeout_seconds` |
| `read_timeout_seconds` | `60` | integer 5 to `poll_interval_seconds − 30` |
| `failopen_issue_after` | `3` | integer 1-100 |
| `claude_bin` | (unset → resolved) | absolute path |

Thresholds above 100 are invalid, not "effectively off". A typo must never become a silent disable.

**Invalid-settings rule (Q11, recommended):**
- **Missing file:** all defaults. This is not a loosening, because the defaults *are* the ruled values at full strength. Recorded as `settings_status=defaults`.
- **Present but unreadable, or any invalid value, unknown key, or duplicate key:** the cycle check **pauses regardless of `fail_mode`**, with reason `settings_invalid:<key>`, a pause issue naming the key and the rejected value, and a stderr line. **Unknown keys are invalid** because `sesion_threshold=80` would otherwise be ignored and leave the check looser than the operator intended.
- **Partial-default fallback is rejected** (an invalid `session_threshold=8O` falling back to 90 would be *looser* than the 80 the operator meant).
- **The poller keeps polling under invalid settings,** using defaults for its own `read_timeout_seconds`/`claude_bin` and recording `settings_status=invalid:<key>`. The reading stays fresh, so fixing the file resumes work at the next cycle.

### AD-10: Prometheus export on faberix: a best-effort side path through a scott-owned file, symlinked into the root-owned textfile directory. It can never affect the pause. (BINDING; FR-41-FR-45, Q4, D-3.)

**Isolation (binding).** The poller writes the reading file **first**. Only then does it render and write the `.prom`, inside an error-swallowing step whose failure is logged to `poll.last.log` and nothing else. **No code on the decision path reads the `.prom`, node_exporter, or Prometheus.** A test makes the `.prom` path unwritable and asserts that the reading file and the decision are byte-identical to the writable case.

**Write path (least privilege).** The textfile directory is `root:root 0755` and holds root-written files. `rename(2)` into it needs directory write permission, which scott must not get: that would let scott replace `apt.prom`/`smartmon.prom`. **One-time root step** (human, documented in the §2a runbook; sudo is denied to sessions):

```
sudo install -d -o scott -g scott -m 0755 /var/lib/hos-usage
sudo ln -sfn /var/lib/hos-usage/hos_claude_usage.prom /var/lib/prometheus/node-exporter/hos_claude_usage.prom
```

- The poller writes `/var/lib/hos-usage/.hos_claude_usage.prom.tmp`, then `rename`s it to `/var/lib/hos-usage/hos_claude_usage.prom`. The rename is atomic in a directory scott owns. The symlink always resolves to a complete file, so Prometheus never scrapes a half-written file (FR-45). The temp name lacks the `.prom` suffix and sits outside the collector directory, so it is never scraped.
- **Outside `$HOME` on purpose.** Ubuntu home directories are 0750, and node_exporter (user `prometheus`) cannot traverse them.
- What scott gains is exactly one metrics file's content. It is also outside every sandboxed role's `allowWrite`.
- **Precondition the TD must verify on faberix before coding S3:** node_exporter 1.10.2's textfile collector follows a symlinked `*.prom` entry. Check by hand with a symlinked test file and `curl -s localhost:9100/metrics | grep`. **Fallback if it does not:**
  - (i) if 1.10.2 accepts a repeated `--collector.textfile.directory`, add `/var/lib/hos-usage` via `ARGS` in `/etc/default/prometheus-node-exporter` (human, root);
  - otherwise (ii) escalate. **Do not** fall back to in-place writes into a pre-created file in the root directory. A torn read there can turn `92` into `9`, a silently wrong value.
  - Either way, S1/S2 (the pause) are unaffected.
- *Rejected:*
  - making the textfile directory group-writable (exposes the root-written files);
  - in-place writes to a pre-created file (torn reads, above);
  - a root-run copier timer (more privileged machinery than one symlink);
  - a new listening exporter (FR-41: no new service or port).

**Metrics** (all `gauge`, each with `# HELP`/`# TYPE`). Raw current values only: no deltas, rates, cumulative transforms or forecasts (FR-43, AC-19). Absent when not obtained, never 0 (FR-44).

| Metric | Labels | Present when |
|---|---|---|
| `hos_claude_usage_session_percent` | — | successful read |
| `hos_claude_usage_weekly_all_models_percent` | — | successful read |
| `hos_claude_usage_weekly_model_percent` | `model` | per model line present |
| `hos_claude_usage_window_requests` / `_window_sessions` | `window`=`24h`\|`7d` | header parsed |
| `hos_claude_usage_subagent_heavy_percent` | `window` | line parsed |
| `hos_claude_usage_long_context_percent` (>150k) | `window` | line parsed |
| `hos_claude_usage_long_session_percent` (8h+) | `window` | line parsed |
| `hos_claude_usage_top_subagent_percent` | `window`, `subagent` | name in that window's top list |
| `hos_claude_usage_top_subagents_more` | `window` | Top line parsed (`0` = known none) |
| `hos_claude_usage_threshold_percent` | `window`=`session`\|`weekly` | always (configured value) |
| `hos_claude_usage_pause_condition` | — | always: 1 iff AD-7's rule, applied to this reading with current settings, says pause |
| `hos_claude_usage_read_ok` | — | always (1/0) |
| `hos_claude_usage_read_failure` | `reason` (AD-4 enum) | value 1, on failure only |
| `hos_claude_usage_poll_timestamp_seconds` | — | always |
| `hos_claude_usage_last_success_timestamp_seconds` | — | always; **0 = no success on record** |
| `hos_claude_usage_fail_mode_closed` | — | always (1/0) |

Binding notes:
- **`last_success_timestamp_seconds = 0`** is the one deliberate zero. FR-44 forbids 0 for unknown *usage values*, because 0% reads as "all clear". For a timestamp, 0 (1970) reads as *maximally stale*, which is the safe direction. It is also how "always emitted" health gauges (FR-44) can exist on a fresh host. This interpretation is flagged in §5.
- **`pause_condition` is machine-level.** FR-42 asks for "paused state". Per-role/project paused state is **not exported**. Exporting it would need one writable `.prom` per role/project (more root symlinks) or would make `hos-cron` write to a file shared with the poller. The machine condition is the same fact all consumers act on (FR-27). The difference is consumer-side staleness, and when the poller dies the `.prom` freezes and AD-11's staleness alert fires. Per-role/project state stays in AD-3.2's status files. Flagged in §5 as a partial reading of FR-42.
- **Label hygiene.** `subagent` and `model` values are sanitized to `[A-Za-z0-9_.:-]` with a length cap. Cardinality is bounded by the CLI's top list.
- **Truncated top list (AF-6).** A subagent that drops out of a window's top list becomes an **absent** series, not 0. The dashboard says so (AD-11).

### AD-11: monitrix configuration: scrape unchanged, a small alert-rules file, a file-provisioned dashboard. All human-applied. Artifacts live in `contrib/monitoring/` and are never shipped to consumers. (BINDING; FR-41, FR-46, AC-20; human scope addition 2026-10-02.)

**(1) Prometheus scrape config: no change (a decision, not an omission).** Job `linux_servers` already scrapes `192.168.1.12:9100` every 15s with `instance="faberix"`. Textfile-collector metrics come out of the same `/metrics` endpoint, so `hos_claude_usage_*` series arrive with the existing labels automatically. A 15s scrape of a file that changes every 5 minutes adds no information loss. A separate job would duplicate the target and add a second `up` series to reason about.

**(2) Prometheus alert rules: ship `contrib/monitoring/prometheus/hos-claude-usage.rules.yml` (recommended).** The pause itself needs none of this. These alerts exist because the *dashboard's* failure modes are otherwise invisible, especially the ESM purge recurring on a release upgrade (§0.3).

| Alert | Expression (TD finalizes) | for | Purpose |
|---|---|---|---|
| `HosClaudeUsageMetricsAbsent` | `absent(hos_claude_usage_poll_timestamp_seconds{instance="faberix"})` | 15m | node_exporter removed or purged, symlink broken, or S3 never applied |
| `HosClaudeUsagePollStale` | `time() - hos_claude_usage_poll_timestamp_seconds > 900` | 5m | poller dead while the exporter is alive (the `.prom` freezes) |
| `HosClaudeUsageReadFailing` | `hos_claude_usage_read_ok == 0` | 15m | the check is broken |
| `HosClaudeUsageTextfileError` | `node_textfile_scrape_error{instance="faberix"} > 0` | 15m | collector cannot read a file |
| `HosClaudeUsagePauseCondition` (info) | `hos_claude_usage_pause_condition == 1` | 0m | visibility |
| `HosClaudeUsageWeeklyTimeToThreshold` (warning, optional) | `predict_linear(hos_claude_usage_weekly_all_models_percent[6h], 86400) >= on(instance) hos_claude_usage_threshold_percent{window="weekly"}` | 30m | early warning (forecast at query time, FR-43) |

To enable it, a human on monitrix:
1. copies the file to `/etc/prometheus/rules/`;
2. uncomments `rule_files:` in `/etc/prometheus/prometheus.yml` with `- /etc/prometheus/rules/*.yml`;
3. runs `promtool check rules …` and `promtool check config /etc/prometheus/prometheus.yml`;
4. reloads with `sudo systemctl reload prometheus` (SIGHUP);
5. verifies at `/rules` and `/alerts` in the Prometheus UI.

Alerts route through the existing Alertmanager at `localhost:9093`. Which receivers fire is a §0.4 gap, recorded in the README.

**(3) Grafana: file provisioning (recommended) over UI import.** AC-20 requires the JSON to "load through Grafana provisioning without errors". Provisioning also makes the repo the source of truth, so a UI edit cannot silently drift the threshold line or the annotation query.
- Ship `contrib/monitoring/grafana/provisioning/hos.yaml`, a dashboards provider: `folder: HOS`, `allowUiUpdates: false`, `path: /var/lib/grafana/dashboards/hos`.
- Ship `contrib/monitoring/grafana/dashboards/hos-claude-usage.json` with a fixed `uid`, no `__inputs`, and a **`datasource`-type template variable** (`query: prometheus`). That form works under both provisioning and UI import (`${DS_…}` `__inputs` work only for UI import).
- An `instance` variable defaults to `faberix`.
- Human steps: copy the provider yaml to `/etc/grafana/provisioning/dashboards/`, copy the JSON to the provider path, `sudo systemctl restart grafana-server`, then confirm the dashboard appears under folder HOS with no provisioning errors in the Grafana log.
- *Rejected:* UI import (matches today's practice, but fails AC-20 as written and drifts).

**Panels (FR-46).** Every derived view is PromQL:
1. **Sawtooth.** Session % and weekly-all %, with the threshold line from `hos_claude_usage_threshold_percent` (it follows config, AC-20). Pause annotations come from `hos_claude_usage_pause_condition == 1`, **labelled "pause condition (machine)"**. They are not labelled "cycles paused", because AD-10 explains the difference.
2. **Early warning.** `predict_linear(...[1h], 3600)` for session and `[6h], 86400` for weekly, against the threshold.
3. **Subagent attribution.** `hos_claude_usage_top_subagent_percent` by `subagent`, one panel per window. Stacking is allowed, with a panel description: *"Top-N only and truncated (`+K more`, also plotted). A subagent leaving the list appears as a gap, not zero. Not a complete breakdown."*
4. **Behaviors.** Long-context % and 8h+-session % (plus subagent-heavy %) per window, **unstacked lines, never summed**. Panel description: *"Independent characteristics, not a breakdown; values overlap"* (AF-6). Shown alongside the sawtooth.

**(4) Artifact location: `contrib/monitoring/`** (new, with a `README.md` runbook). The repo has no existing convention for host-infra artifacts; I searched for existing `contrib/`, `ops/`, `monitoring/`, `dashboards/` dirs and found none outside the venv. `contrib/` is not listed in `framework_consumer_files.txt` and is not copied by `hos_install.sh`. A test asserts that no `contrib/` path ever appears in that list. Host-specific values (monitrix IP, `instance="faberix"`) live only in the README and in variable defaults, never in code. The README's verification steps on monitrix:
- query `hos_claude_usage_poll_timestamp_seconds{instance="faberix"}` (present, advancing every ~5 minutes);
- query `hos_claude_usage_read_ok` = 1;
- query `node_textfile_mtime_seconds{file=~".*hos_claude_usage.prom"}`;
- check the rules are loaded;
- check the dashboard renders.

The README also states: **"A release upgrade can purge the ESM `prometheus-node-exporter` build (it did on 2026-10-01). `HosClaudeUsageMetricsAbsent` and the absence of `hos_*` series on monitrix are how you notice. Reinstall, then re-run `bin/hos-usage-poll --check`."** The `--check` symlink/writability line (AD-6 item 7) also catches it from faberix.

### AD-12: Build slicing and risk tiers. (BINDING.)

| Slice | Contents | Tier | Merge |
|---|---|---|---|
| **S1: Poller + parser + reading file + settings + runbook** | `bin/hos-usage-poll` (poll, `--check`, `--print-setup`); `bin/lib/usage_pause.py` (parse, settings, evaluate, status I/O); D-1 + empty-session + AC-1 fixtures; T4.1b + T4.1 comment; static credential/suspend tests; `framework_consumer_files.txt`; CRON-SETUP §2a; MACHINE-ACCOUNTS pointer. **Exit criterion:** AC-16 recorded, meaning a real cron-fired poll on faberix produced `outcome=success`. | **HIGH** (credential-adjacent; feeds every pause decision) | HUMAN_REQUIRED (`bin/**`) |
| **S2: `hos-cron` cycle-start gate + visibility** | AD-7 block; per-role/project status file; AD-8 audit, pause issue, degraded issue, complete dedup, lock, auto-close. | **HIGH** (gates every autonomous cycle on every host; protected) | HUMAN_REQUIRED (`bin/**`, FR-49) |
| **S3: `.prom` export on faberix** | `render_prom` + the isolated write in the poller; `--check` item 7; root-step runbook; symlink verification (AD-10 precondition). | MEDIUM | HUMAN_REQUIRED (`bin/**`) |
| **S4: monitrix artifacts** | `contrib/monitoring/` rules, provider yaml, dashboard JSON, README; `promtool` lint test and dashboard JSON schema/panel test in CI; human applies on monitrix. | LOW-MEDIUM | normal (`contrib/` is not protected), with an infra-reviewer pass |

**Ordering.**
- S1 → S2 (S2 consumes S1's file contract).
- S1 → S3 → S4 (S4 needs metric names).
- **Deploy S1 (crontab installed, `--check` green) before S2 merges.** Otherwise the first post-merge cycle on faberix pauses with `poller_not_installed`. That is correct fail-closed behavior, but avoidable noise.
- **#1944 is satisfied by S1+S2.** S3/S4 deliver the dashboard scope.
- **If S2 is blocked for any reason, the issue stays open and escalates (AD-1). S3/S4 landing never closes it.**
- Each slice's PR states its dependencies on both sides.

---

## 3. Traceability (every ruled requirement)

| Req | Satisfied by | Note |
|---|---|---|
| FR-1 | AD-1, AD-12 | no off switch; S1+S2 required; blocker → escalate |
| FR-2 | AD-4, AD-6 | `claude -p /usage` text only |
| FR-3 | AD-6 | key, `from=`, no `claude-auth.env` |
| FR-4 | AD-5.1, AD-6 | `env -u` + static test (AC-15) |
| FR-5 | AD-6 | `-n`, `RequestTTY=no`; no pty workaround |
| FR-6 | AD-6 | pinned PATH + absolute `claude_bin` |
| FR-7 | AD-6, AD-4 | `timeout --kill-after`; no timeout binary → refuse |
| FR-8 | AD-9, AD-6 | `poll_interval_seconds` → crontab `*/N` via `--print-setup`; `--check` detects drift |
| FR-9 | AD-4, AD-5 | no model call; AC-25 via `$0.0000` on real read |
| FR-10 | AD-2, AD-4 | reference regexes ported to Python (interpretation flagged §5) |
| FR-11-FR-13 | AD-4 | content-decided; `empty_session` reason |
| FR-14 | AD-4 | fallback not shipped; AC-21 stub |
| FR-15 | AD-3, AD-4 | `parsed_via=grep` |
| FR-16 | AD-4, AD-10 | gauges only (AS-1) |
| FR-17 | AD-4, AD-10, AD-11 | pinned to D-1 sample; independent; never decides |
| FR-18, FR-19 | AD-7, AD-9 | 90/90, `>=` |
| FR-20 | AD-4 | window length never parsed or assumed |
| FR-21 | AD-7, AD-9 | default closed |
| FR-22 | AD-8 | degraded issue (+ DERIVED stale case, §5) |
| FR-23 | AD-7 | stateless gate; first fresh under-threshold read runs |
| FR-24 | AD-6 | poller never reads suspend/halt (static test) |
| FR-25 | AD-7 | no marker write/clear (static test); AC-11 |
| FR-26 | AD-7 | placed before `claude-auth.env`, probe, and every session |
| FR-27 | AD-3, AD-9 | one reading, one machine conf from literal `$HOME` |
| FR-28 | AD-7 | inputs exclude transcripts; AC-24 |
| FR-29, FR-30 | AD-9 | location decided; invalid → pause (Q11 pending) |
| FR-31-FR-33 | AD-3 | reading file + per-role/project status (Q5 confirm) |
| FR-34, FR-35 | AD-3, AD-6, AD-8 | `>` cron log; transition-only audit; no history |
| FR-36 | AD-7 | staleness 900 > 300+60; distinct reasons |
| FR-37-FR-39 | AD-8 | complete dedup (AF-3); per-project issue (Q15 confirm) |
| FR-40 | AD-1 | #1450 code untouched (AC-17) |
| FR-41 | AD-10 | existing node_exporter; no new port |
| FR-42 | AD-10 | **partial:** paused state exported machine-level only (§5) |
| FR-43 | AD-10, AD-11 | raw only; forecasts in PromQL |
| FR-44 | AD-3, AD-10 | absent not 0; `last_success=0` interpretation (§5) |
| FR-45 | AD-10 | rename in owned dir + symlink; **depends on symlink verification** (fallback/escalation in AD-10) |
| FR-46 | AD-11 | four panels, provisioning |
| FR-47, FR-48 | AD-6 | CRON-SETUP §2a; `--check` |
| FR-49 | AD-12 | HUMAN_REQUIRED stated |
| FR-50 | AD-2, AD-6 | standalone `*/5` crontab poller |
| AS-1 / AS-2 / AS-3 | AD-4 / AD-7 / AD-8 | carried as assumptions (§5) |
| D-1 | AD-4 | **resolved** (2026-10-02 capture) |
| D-2 | AD-4 | not shipped; remains open, not a v1 dependency |
| D-3 | §0.3, AD-10 | **resolved** (node_exporter reinstalled) |
| AC-1-AC-30 | AD-4 (1,4,5,18,21,25), AD-6 (6,7,15,16,22,27), AD-7 (2,3,8,10,11,23,24,28,29), AD-8 (9,10,14,30), AD-3 (12,13), AD-10/11 (19,20), AD-1 (17), AD-5 (26) | AC-16 is an S1 exit criterion |

**Unsatisfied ruled requirements: none.** **Partially satisfied, flagged:** FR-42 ("paused state" exported only at machine level). **Conditional:** FR-45 depends on a symlink precondition with a defined fallback. This never affects the pause.

---

## 4. Escalations

### Bound here, not escalated
- Placement under `bin/` (AF-2).
- Stateless gate, not `hos-suspend` reuse (Q16).
- The `/usage` exemption mechanics (Q8).
- Python port of the reference regexes.
- Haiku not shipped.
- Complete dedup (AF-3).
- Scrape config unchanged.

### ESC-1: Consumers get the fail-closed gate on upgrade (product boundary: pm-agent + human). AF-4.
`bin/hos-cron` ships to consumers. After upgrading, a consumer host with no poller pauses every cycle (`poller_not_installed`, with an issue) until it does the §2a setup or sets `fail_mode=open`. Consumers on API-key billing have no subscription `/usage` at all, and for them only `fail_mode=open` plus a permanent `[DEGRADED]` issue is available. **This ADR does not add an off switch (FR-1).** The human decides between:
- (a) ship as designed, with a release note and an upgrade-checklist step; or
- (b) a consumer-only escape hatch.

(b) would need a new human ruling, because it is the "flag" FR-1 forbids, applied to installs other than this host. **This does not block S1/S2 on faberix.** It must be decided before the next release that ships S2 to consumers.

### ESC-2: monitrix and faberix root steps are human actions.
- faberix: the `/var/lib/hos-usage` + symlink step.
- monitrix: rules + `rule_files`, Grafana provider + JSON.

Sessions are denied `sudo` and do not reach monitrix. These are documented, not automated, and they gate only S3/S4 verification.

### ESC-3: The fail-open dead-poller case (AD-8 (b)) is DERIVED. Confirm, §5.

### ESC-4: AF-3 (the existing breakers' first-page dedup) needs its own issue.
I am design-only this session and have not filed it. The orchestrating session should file it. #1944 does not depend on the fix, because AD-8 binds its own complete query.

---

## 5. Human confirmation required

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

*Removed as done:* the node_exporter reinstall (verified 2026-10-02, §0.3) and the D-1 `/usage` sample capture (2026-10-02, §0.3).

---

## 6. Startup-gap analysis and affected sign-offs

Nothing for #1944 has been designed or built before this ADR, so **no prior sign-off is orphaned.** The #1450 breaker code and its sign-offs stand untouched (FR-40). AF-3's defect affects shipped breaker code, but #1944 does not change it, so ESC-4 carries it separately. One requirements correction for the TD: the requirements' "subagent-breakdown %" (FR-17/FR-42) is, per the D-1 sample, the **subagent-heavy behavior %**, an overlapping characteristic. Attribution comes only from the truncated Top-subagents list (AF-6). Build against AD-4/AD-10's names, not the requirements' wording.

---

## Human Review Required

**RISK: HIGH.** The gate sits in front of every autonomous cycle on every host that runs `hos-cron`. Under the fail-closed default, a defect stops all autonomous work. Under fail-open, a defect lets credits billing continue unwatched. The design handles both. Every decision-path failure resolves to a *named* pause (AD-7). Fail-open can never be silent, even with a dead poller (AD-8 (b)). The only inputs to the decision are three things a sandboxed session cannot write (AF-1, AF-2).
**CONFIDENCE: HIGH** on §0 (re-derived from the tree), AD-1 to AD-9, and AD-12. **MEDIUM-HIGH** on AD-10, which depends on the symlink precondition (fallback defined), and on AD-11's alert routing (receivers unknown).
**BLAST RADIUS:** `bin/hos-cron` cycle start (both roles, every project, every consumer on upgrade); new `bin/hos-usage-poll` + `bin/lib/usage_pause.py`; user crontab; `~/.ssh/authorized_keys`; `~/.hos/usage-pause/`; `~/.config/hos/usage-pause.conf`; `/var/lib/hos-usage` + one symlink in node_exporter's textfile directory; monitrix Prometheus rules and Grafana provisioning.
**Change classification: STRUCTURAL.** A new gate on every autonomous cycle, a new credential-bearing host path, and new host-infra artifacts. ESC-1 must clear the product-boundary checkpoint before S2 ships to consumers. S1/S2 on faberix may proceed on `technical-design` completion.

---

## Amendment 1 (2026-10-03, architect, TD review round 1)

These revisions come out of reviewing `TECHNICAL-DESIGN-1944-proactive-usage-pause.md`, DRAFT-1 (§9.1 there). They are appended; the text above is not rewritten. Where they conflict, this amendment governs. Startup-gap check: every item corrects a premise before any code exists, and the only artifact built against the superseded text is the TD, which was updated in the same round. **No sign-off is orphaned.**

- **A1-1 (AD-5, call site).** The sole `/usage` call site is **`bin/lib/usage_pause.py`**, not `bin/hos-usage-poll`.
  - It holds the remote command as one constant, `REMOTE_CMD_TEMPLATE`, and that constant is also the source of the `--check`/`--print-setup` forced-command text.
  - The T4.1 exemption is `bin/lib/usage_pause.py`, matched deterministically through its docstring.
  - T4.1b pins the template line and the sole call site.
  - AD-5.1's exact remote command is unchanged.
- **A1-2 (AD-6, time bound; AD-4 enum).** The `<timeout_bin> --kill-after=5 <t>` prefix is replaced by an in-process bound in Python: `Popen(start_new_session=True)`, `wait(read_timeout_seconds)`, then process-group SIGTERM, a 5 s grace, then SIGKILL.
  - The ssh argv and options are otherwise exactly as AD-6.
  - `no_timeout_binary` is removed from the failure enum, which now has eight reasons.
  - Timeout is observed directly, not inferred from exit code 124/137.
  - **Why:** a bash `_TIMEOUT_BIN` would be a permanent fourth entry in ADR-1643 AD-16.6's T4.2 ledger, which exists for AI-review timeout copies. The Python form is no more complex, removes the macOS coreutils dependency, and cannot mistake a remote exit code for a timeout.
  - FR-7 still holds: the read is always bounded.
- **A1-3 (AD-4, success criterion vs FR-11).** AD-4 stands: content decides. A transport failure (ssh exit 255, spawn failure, timeout) is a FAILED read whatever the content. Any other remote exit code is recorded as `remote_exit` and does not by itself fail the read.
  - This **overrides FR-11's literal "non-zero exit" item**. FR-11's own cited source (the reference parser's content-only condition) and FR-13 both support the override.
  - **Requirements amendment required:** pm-agent rewords FR-11. The human confirms, because the change narrows a failure list in the less-pausing direction.
  - pm-agent also rewords AC-25, which cannot be observed on the real success shape (TD §3.13 item 3 is the substitute).
- **A1-4 (AD-9, bounds).** `staleness_seconds` must be `> poll_interval_seconds + read_timeout_seconds` **and `≤ 7200`**. The upper bound stops a typo from becoming a near-disable, and 7200 keeps the range non-empty at the maximum interval. `claude_bin` must match `^/[A-Za-z0-9._+/-]{1,254}$` with no `/./` or `/../` segment, because it is interpolated into a remote command and an `authorized_keys` line.
- **A1-5 (AD-10, metrics).** `hos_claude_usage_threshold_percent` is emitted **only when settings are valid**. A new always-present gauge, `hos_claude_usage_settings_valid` (1/0), is added. Under invalid settings, `pause_condition` is 1.
- **A1-6 (AD-12, S4).** "A `promtool` lint test in CI" becomes: structural YAML/JSON and metric-name tests in CI, plus an `integration`-marked `promtool check rules` test that is skipped when `promtool` is absent. The human's `promtool check` output on monitrix is the recorded evidence. S4 does not touch `.github/workflows/**`.
- **A1-7 (AF-2, statement correction).** The OS-level half of AF-2 is narrower than stated. `denyWrite` covers only each role's **own** clone's `bin/`, while `allowWrite` covers all three clones, so a sandboxed Overseer or Human session can write `Worker/bin/*`. AF-2's governance half (CODEOWNERS → HUMAN_REQUIRED) and AF-1 (decision *data* outside every `allowWrite`) are unaffected.
  - This is a **pre-existing gap outside #1944's scope** (TD ESC-T1). #1944 neither widens it nor depends on closing it.
  - The fix (adding the three clones' `bin/` to `denyWrite`) is protected `contract/**` surface and needs security-reviewer review plus human approval.

**Confirmed without change** (clarifications the TD made under AD-3/AD-4/AD-8, now binding):
- exact-title dedup and auto-close, not prefix (AD-8);
- the complete query through `gh api --paginate … --jq` under `_REPO_SLUG`, using raw `gh` rather than the bootstrap wrappers, which do not ship to consumers (AD-8);
- one `key=value` per `_audit` argv element (AD-8);
- `lock_stale_reclaimed` as a `diagnostics` key, not a failure reason (AD-4);
- close-pending retry memory, the corrupt-previous-file close sweep, and the check-error flag (AD-8).

**Human confirmation added to §5:**
- 12: FR-11 narrowing (A1-3);
- 13: AC-25 rewording;
- 14: the A1-7 cross-clone `denyWrite` gap, a finding outside #1944's scope;
- 15: widening ESC-4 to every single-page dedup site in `bin/hos-cron` (`:954`, `:1430`, `:1682`, `:1760`, `:1801`, `:2063`, `:2167`, `:2191`) and `query_issues.sh --list`;
- 16: the collapsed `_audit` call at `bin/hos-cron:2054`.

Items 1–11 of §5 are unchanged and unresolved.
