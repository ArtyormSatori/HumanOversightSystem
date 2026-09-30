# TECHNICAL DESIGN — #1644 slice T3.0a: no-idle selection, issue side (native-blocker and parent exclusion in the selector's free phase, `bootstrap/escalate_to_human.sh`, and the ESC-8 tests)

**Status:** DRAFT-1 + architect edits. **APPROVED_WITH_EDITS by `architect`, round 1 of 5
(2026-09-30).** The architect's binding corrections are applied in place and are listed in §10. OQ-1..3
are ruled there and in ADR-1644 Erratum 1. Cleared for `coder` handoff.
**Date:** 2026-09-30
**Author:** technical-design
**Baseline:** `origin/main` = `HEAD` = **`5b041f2742daf3fb96720129f5b5cca7367fe25b`** (the merge of PR
#1911, ADR-1644). Every file:line below is that commit's blob. Live GitHub probes were run at
2026-09-30T16:2xZ, read-only, through `scripts/automation/lib/github.py::_run_gh` (§0.2).
**Binding inputs:**
- `docs/v0.7.0/ADR-1644-stage-per-cycle.md`: §0, AD-C4, AD-C6, AD-C10, AD-C14, and §5's T3.0a row plus
  "Why T3.0a is the first slice". This is the controlling document, and nothing here re-litigates it.
- `docs/v0.7.0/REQUIREMENTS-1644-AMENDMENT-1-stage-per-cycle.md`: REQ-C5, REQ-C11, REQ-C12, REQ-C16,
  REQ-C18, ESC-3, ESC-8.
- `docs/v0.7.0/TECHNICAL-DESIGN-1540-S1-S2-intake-trust-gate.md`, revision 8, and ADR-1540 AMENDMENT-1..4.
  T3.0a extends the gate those documents built. Its exit, budget and report contract (§2.2, §2.3, §5
  there) is inherited unchanged except where §3 below names a delta.

**Scope, which is the ADR's and nothing more:**
- AD-C4's native-blocker exclusions: `blocked-by-open-issue`, `blocker-closed-unverified`, and
  unevaluated/DEGRADED on a missing or malformed summary;
- AD-C4's `untracked-parent` exclusion;
- `bootstrap/escalate_to_human.sh` (AD-C6 H5), record-first;
- the ESC-8 tests T-NS1 to T-NS4 against the selector;
- the mocked-`gh` zero-added-request proof.

**Explicitly out of scope:**
- stage labels and stage parsing (`stage-malformed`, `tracking-parent`), and in-flight ordering (T3.2);
- the `contract/stages/` registry (T3.1);
- the executor and the pre-check (T3.2, T3.7a/b);
- the PR classifier and H4 (T3.0b, gated on ARCH-ESC-1);
- round records, caps and epochs (T3.4);
- the paid edge-satisfaction check (T3.3);
- question issues (T3.7a);
- the S2 derivation path (T3.8a).

This document says *what the code must do*. It contains no application code.

---

## 0. Verification, re-derived against `5b041f27` and live GitHub

### 0.1 Search for existing helpers (CLAUDE.md "Search first", required)

I searched `scripts/` (recursively), `bootstrap/`, `bin/` and `scripts/automation/lib/`.

| Looked for | Found | Consequence |
|---|---|---|
| Any reader or writer of `issue_dependencies`, `sub_issues`, `blocked_by`, `parent_issue` | **Nothing** outside `.venv` (grep exit 1) | Confirms ADR VF-C2. The selector's parse is new code. There is no helper to reuse and none to conflict with. |
| A pure predicate home for list-record parsing | `select_work_candidates.py::_label_names`, `_rank`, `_apply_free_filters` | The new predicate lives beside them (§2.1). There is no new module. |
| A "post a question, then apply `needs-human`" helper | **None.** Near misses follow. | `escalate_to_human.sh` is new, as ADR §5 states. It **composes** the pieces below and does not re-implement them. |
| ↳ comment write | `bootstrap/post_comment.sh` (mint, `gh issue comment --body-file`, revoke); `github.py::post_comment` (read-back verify, ambient token) | Pattern source for mint/revoke and the `@/` guard (§4.3). |
| ↳ label write + verify | `bootstrap/edit_issue.sh` (POST `/labels`, then GET and print the resulting labels) | Pattern source for label-add and verify (§4.4 step W3/W4). |
| ↳ record format / idempotency key (architect addition) | `scripts/automation/lib/envelope.py` (`---hos-envelope`), `scripts/automation/lib/correlation.py` (cid); marker precedent `scripts/oversight/release_panel_logic.py:58` (`<!-- hos-release-panel-verdict v1 -->`) | **Not reused, deliberately.** AD-C7's envelope rule governs *round and stage records*, not this write primitive. `correlation.py`'s cid keys a claim/branch, not a question's content. `envelope.py`'s `DEFAULT_ACK_PATTERNS` treats `---hos-envelope` as evidence that a prior *answer* exists, so an envelope in an escalation *question* could read as answered. The §4.5 HTML-comment marker follows the `release_panel_logic.py` precedent. It is this script's idempotency key only. It is **not** the AD-C10 escalation-record format. That format is T3.6's to define inside the body the caller passes (ADR-1644 Erratum 1, E5). |
| ↳ author-safe comment read | `bootstrap/query_issues.sh --comments-json` | **Not reusable.** It fetches page 1 only (`?per_page=100`, `:229`) and omits `id`, `updated_at` and `html_url`. Idempotency needs all four (§4.5). Reads are done in-script under the same token (§4.4). |
| ↳ `@/` literal guard | `bootstrap/lib/comment_format_check.sh::hos_cfc_check_at_path_literal` | Sourced and reused (§4.3). |
| ↳ audit write | `scripts/oversight/lib/audit_log.sh::audit_write_event`. Best-effort precedent: `bootstrap/submit_pr.sh::_hos_audit_stale_base_merge` (`:79-95`) | Reused with the identical best-effort shape (§4.7). |
| ↳ existing `needs-human` escalations | `merge_authority.py` (`labels_to_add=["needs-human"]`, PR paths, `:579-672`); `bin/hos-cron:1732-1739` (baseline-repair cap) | **Finding TD-F4 (§0.3).** Neither is record-first. Neither is migrated here. |
| A PATH-level `gh` double | `tests/automation/test_edit_issue.py` (`GH_STUB`, `GET_APP_TOKEN_STUB`, copy-script-into-tmp harness); `tests/automation/test_hos_cron.py::CronEnv` | Test harness pattern for §7.3 and T-ZC2. |

### 0.2 Live probes (read-only)

These were run against `thurlow-research/HumanOversightSystem`, through `github._run_gh`, with the
selector's **exact** endpoint shape.

- **P1: `issues?state=open&labels=needs-ai&per_page=100&page=1`.** Of 100 records, **100** carry
  `issue_dependencies_summary` with keys `{blocked_by, blocking, total_blocked_by, total_blocking}`, and
  **100** carry `sub_issues_summary` with keys `{completed, percent_completed, total}`. Every value was
  zero. There are no edges and no parents.
- **P2: `issues?state=all&per_page=100&page=1`.** There are 82 issue records and 18 PR records. All 82
  issues carry both summaries. **All 18 PR records carry both keys with value `None`.**
- **P3: `issues/1643` and `issues/1644`.** Both carry `needs-ai` and no `needs-human`. Both summaries are
  all zero. `parent_issue_url` is **absent** as a key. This is the ADR's H5 shape, a prose-only human
  wait, and it is still live today.
- **P4: comments with reactions on #1644, #1643, #1540, #1539, #1604, #1880, #1912 and #1915.** None was
  found. The ADR §0 gap "does a reaction move `updated_at`" is **not closed**. §4.5 states which way the
  answer fails.

**AF-C1 is confirmed on the selector's own endpoint. The zero-cost claim holds** (§3.1). No escalation is
needed on cost.

### 0.3 Findings that shape this design

- **TD-F1 (HIGH, design).** **P2 means the native check must run after D1.** PR records have `None`
  summaries. If they were evaluated before D1, every PR in the list would become "unreadable" and force
  `complete=no`, turning DEGRADED into the steady state. §2.3 fixes the order as D1, then D2, then D2b.
- **TD-F2 (HIGH, test impact).** The existing selector fixtures have **no summary keys at all**. The
  affected fixtures are:
  - `tests/framework/test_select_work_candidates.py::_issue` (`:45-55`) and the raw literals at
    `:206-216`;
  - `tests/automation/test_hos_cron.py::_candidates_json` (`:54-76`).

  Under AD-C4's "missing ⇒ unevaluated" rule, every existing test that expects a candidate would go
  DEGRADED. The fixtures must gain zeroed summaries (§6.2). **That is a fixture correction, not a change
  to any test's expectation.** §8 lists every test whose *expectation* does change.
- **TD-F3 (MEDIUM, correctness independent of an unverified semantic).** AF-C1's caveat 1 is that
  `blocked_by` counts **open** blockers only. No edge exists to probe (P1, P2), so that reading is
  **unverified**. The exclusion predicate is designed so that **safety does not depend on it** (§2.2 R4):
  given `0 ≤ blocked_by ≤ total_blocked_by`, the record is excluded **iff `total_blocked_by > 0`**,
  whichever count GitHub uses. Only the *reason token* depends on the open/closed split. The satisfaction
  semantics that do depend on it belong to T3.3.
- **TD-F4 (MEDIUM, for AD-C10 "one code path"; not fixed here).** `bin/hos-cron:1732-1739` escalates
  **label-first**, and both writes are `|| true`: `gh issue edit --add-label needs-human`, then
  `gh issue comment --body …`. *(Architect addition.)* `.claude/agents/worker.md:291-295` (the
  baseline-repair "cannot determine which side is wrong" step) is a third label-first site: it relabels
  with `edit_issue.sh --add-label needs-human`, then posts the evidence. `merge_authority.py`'s `labels_to_add` paths are PR-side and write no
  question record. Both predate AD-C10. Migrating them onto `escalate_to_human.sh` is T3.6's job (AD-C10
  makes escalation one code path), and §9 OQ-3 asks the architect to record that.

### 0.4 The ADR §0 gaps, as they touch T3.0a

| ADR §0 gap | Touches T3.0a? | Disposition |
|---|---|---|
| How a child resolves its parent, and whether `parent_issue_url` is on the list record | **No.** `untracked-parent` reads the **parent's own** `sub_issues_summary` (P1). | Probed anyway (P3): the key is **absent** on a non-child. No child exists to probe. Still open, for AD-C16/T3.8a. |
| Timeline events and actors for edge add/remove | **No.** T3.0a never unblocks anything. Every new rule only **excludes** (AD-C14 asymmetry). | Left to T3.3. |
| Whether a reaction moves `updated_at` | **Yes.** `escalate_to_human.sh`'s idempotency uses "unedited". | Not closed (P4). §4.5 makes both answers safe: the worst case is a **duplicate question comment**, never a lost escalation. |
| A5 on plan-stage `Write` | No | T3.7a. |
| No behavior was run under `bin/hos-cron` | Partly | T-HC1 (§7.4) drives the real launcher against a stubbed `gh`. |

---

## 1. Files (≤15; this is one PR)

| # | Path | Change | Surface |
|---|---|---|---|
| 1 | `scripts/framework/select_work_candidates.py` | **Modify.** Add D2b (§2), the report deltas (§3), and a docstring update (§2.6). | protected |
| 2 | `tests/framework/test_select_work_candidates.py` | **Modify.** Fixture correction (TD-F2) and two renamed or extended tests (§8). | — |
| 3 | `tests/framework/test_select_work_candidates_native.py` | **New.** T-NB*, T-EX*, T-ZC1/3/4, T-NS1 to T-NS4 (§7.1, §7.2). | — |
| 4 | `tests/framework/test_select_work_candidates_ghshim.py` | **New.** T-ZC2, the PATH-level fake `gh` request count (§7.2). | — |
| 5 | `tests/automation/test_hos_cron.py` | **Modify.** Fixture correction in `_candidates_json`, and T-HC1 (§7.4). | — |
| 6 | `bootstrap/escalate_to_human.sh` | **New** (§4). | protected |
| 7 | `tests/automation/test_escalate_to_human.py` | **New.** T-ESC* (§7.3). | — |
| 8 | `bootstrap/worker-cron-prompt.md` | **Modify.** One paragraph: human waits go through the script (§5). | protected |
| 9 | `docs/LABELS.md` | **Modify.** Add a `needs-human` writer and the native-exclusion note (§5). | — |
| 10 | `CLAUDE.md` | **Modify.** One row in "Canonical entry points by task" (§5). | protected |
| 11 | `SCRIPTS-INDEX.md` | **Regenerate** with `scripts/framework/gen_scripts_index.sh`. No hand edits. | — |

That is eleven files. `scripts/framework/regen_all.sh --check` must be clean before the PR. CODEOWNERS
already covers `bootstrap/**` and `scripts/framework/**` by glob, so no regeneration is expected. If
`--check` disagrees, regenerate; never hand-edit.

**Not touched:**
- `scripts/framework/requester_trust.py`: trust is unchanged; nothing in T3.0a is a trust decision.
- `bin/hos-cron`: exit-code handling is unchanged (§3.4).
- `scripts/framework/framework_consumer_files.txt`: the new script ships exactly as its siblings
  `post_comment.sh` and `edit_issue.sh` do today, and neither is listed. §9 OQ-3(c).
- `.claude/agents/worker.md`: see §5, last bullet.

---

## 2. Selector: D2b, the native free filter

### 2.1 Placement

All of it goes in `scripts/framework/select_work_candidates.py`, beside `_label_names` and `_rank`. The
predicate is **pure**: no network, no filesystem, no clock. It reads **exactly two keys** of a list record,
`issue_dependencies_summary` and `sub_issues_summary`, and nothing else (T-NB13 pins this the same way
`test_ranking_reads_only_the_list_payload` pins `_rank`).

### 2.2 Data shapes and the predicate

**New module constants** (not flags, per AD-13 of TD-1540):

```
NATIVE_EXCLUSION_REASONS = (            # precedence order; the literals are ADR-binding (AD-C4)
    "blocked-by-open-issue",
    "blocker-closed-unverified",
    "untracked-parent",
)
UNEVALUATED_EDGE_SUMMARY = "edge-summary-unreadable"   # the unevaluated sub-reason token (§3.2)
_EXCLUDED_LIST_BOUND = 20                               # same bound as the ALL-CANDIDATES-GATED issue list
```

**New types:**

```
@dataclass(frozen=True)
class _NativeVerdict:
    outcome: str   # exactly one of: "clear" | "excluded" | "unreadable"
    reason: str    # outcome=="excluded"   -> one NATIVE_EXCLUSION_REASONS literal
                   # outcome=="unreadable" -> "dependencies" | "sub-issues" | "both"
                   # outcome=="clear"      -> ""

@dataclass
class _FreeFilterResult:
    kept: list        # records surviving D1, D2 and D2b, in input order: these are ranked and walked
    unreadable: list  # [(number:int, limb:str)] in input order: unevaluated, never walked
    excluded: list    # [(number:int, reason:str)] in input order: dropped, reported
```

**New functions (signatures are binding):**

```
def _nonneg_int(container: Any, key: str) -> Optional[int]
    # The value iff `container` is a dict, `key` is present, and the value is an int that is NOT a
    # bool and is >= 0. Otherwise None.

def _dependency_counts(record: dict) -> Optional[tuple[int, int]]
    # (blocked_by, total_blocked_by) from record["issue_dependencies_summary"], or None when:
    #   the key is absent; or its value is not a dict (this includes None); or either field fails
    #   _nonneg_int; or blocked_by > total_blocked_by (internally inconsistent => unreadable).
    # `blocking` and `total_blocking` are NOT read and NOT validated: they do not bear on whether
    # THIS record may run.

def _sub_issue_total(record: dict) -> Optional[int]
    # record["sub_issues_summary"]["total"] via _nonneg_int, or None under the same rules.
    # `completed` and `percent_completed` are NOT read.

def _native_verdict(record: dict) -> _NativeVerdict
```

**`_native_verdict` rules, evaluated in this order. The order is part of the contract.**

- **R1.** If `deps` is readable and `blocked_by > 0`, the result is `excluded / blocked-by-open-issue`.
- **R2.** If `deps` is readable and `total_blocked_by > blocked_by`, the result is
  `excluded / blocker-closed-unverified`.
- **R3.** If `subs` is readable and `total > 0`, the result is `excluded / untracked-parent`.
- **R4.** If `deps` is unreadable or `subs` is unreadable, the result is `unreadable`, with the limb set
  to `dependencies`, `sub-issues` or `both`.
- **R5.** Otherwise the result is `clear`.

Consequences, each of which a test pins:
- **An exclusion wins over an unreadable limb (R1 to R3 before R4).** Excluding is always safe (the
  AD-C14 asymmetry). A record that is certainly a parent and has an unreadable dependency summary is
  therefore reported as `untracked-parent`, not as unevaluated. This keeps DEGRADED for records whose
  **selectability** is genuinely unknown (T-NB9).
- **Safety does not depend on the open/closed reading (TD-F3).** R4 guarantees
  `0 ≤ blocked_by ≤ total_blocked_by` for any readable `deps`. So R1 ∨ R2 ⇔ `total_blocked_by > 0`. A
  property test over the grid `0 ≤ b ≤ t ≤ 3` asserts "excluded iff `t > 0`" (T-NB10).
- **A parent is excluded whether its children are open or closed.** `total` counts both. Per AD-C4,
  "an epic with children is not leaf work". §9 OQ-2 asks the architect to confirm the closed-children
  case.
- **Stage labels are inert in T3.0a.** A `stage:*` label changes nothing: no parse, no
  `stage-malformed`, no `tracking-parent`. A `stage:tracking` parent is reported as `untracked-parent`
  until T3.2 splits that reason. That is harmless because both reasons exclude, and nobody can apply
  `stage:*` before T3.1 provisions the labels. The graph-contradiction case (AD-C4: code stage while
  blocked) is reported under `blocked-by-open-issue` **by construction** (T-NB7).
- **The predicate never reads `labels`, `user`, `title` or `body`.** It is not a trust input and cannot
  become one.

### 2.3 Where D2b runs (the algorithm order, extended)

`_apply_free_filters(raw_records: list) -> _FreeFilterResult`. This changes the return type, and the one
caller (`main`) is updated. For each raw record, in order:

1. **D0.** A non-dict record is skipped, as today.
2. **D1.** A `pull_request` record is skipped, as today. **This must precede D2b** (TD-F1).
3. **D2.** A record carrying any `EXCLUDED_LABELS` label is skipped silently, as today. `needs-human`
   wins over everything, including an unreadable summary (T-NB12). The single-literal rule
   (`test_excluded_labels_is_defined_in_exactly_one_place`) is untouched.
4. **D2b.** `v = _native_verdict(record)`:
   - `excluded`: append `(number, v.reason)` to `excluded`, and the record goes no further;
   - `unreadable`: append `(number, v.reason)` to `unreadable`, and the record goes no further;
   - `clear`: append the record to `kept`.

The rest of the pipeline is **unchanged**: D3 `requester_verdict`, D4, D-rank, D5 walk, E emit. They
operate on `kept` only.
- The walk key stays `(rank, -number)` and the emit key stays `(rank, number)`. **In-flight ordering is
  T3.2's.** See §9 OQ-1 for its effect on T-NS2.
- Neither `excluded` nor `unreadable` ever enters `walk_order`. Neither can consume a `max_candidates`
  slot or an events request. **This is what makes ESC-8's exception structural** (AD-C6).

The module docstring's algorithm block (`:23-29`) gains one line, placed between D2 and D3:
`D2b drop native-blocked / parent records; set aside unreadable-summary records (free)`.

### 2.4 Counting identities (the invariants, extended)

- `scanned = len(kept) + len(unreadable)`. **Excluded records are not scanned**, exactly as D2's
  `needs-human` records are not scanned today.
- `unevaluated = sufficient + cost_ceiling + query_failed + edge_summary_unreadable`.
- `scanned == evaluated + unevaluated`, and `evaluated == eligible + gated`. Both existing identities in
  `TestSummaryInvariants` hold **unchanged** (T-EX4).

### 2.5 Step C's REFUSED path

When the request ceiling refuses a list page (`ceiling_refused_at_list`, `:716-739`), D2b still runs over
the fetched records, because it is free. Then:
- `unevaluated_cost_ceiling = len(kept)`, **not** `scanned`;
- `edge_summary_unreadable = len(unreadable)`;
- excluded records are reported (§3.2).

This preserves `scanned == evaluated + unevaluated` without double-counting (T-EX5).

### 2.6 Docstring (the consumer-facing statement)

Add one paragraph after the FR29(b) block:

> Native GitHub issue dependencies and sub-issues gate selection (ADR-1644 AD-C4). An issue with any
> blocking dependency (`blocked by`), open or closed, is not selected. An issue that has sub-issues is not
> selected. Neither costs a request, because both are read from the list record. If the host does not
> return these summaries, selection reports DEGRADED (exit 3) rather than assume "not blocked". On
> such a host (for example, a GitHub Enterprise Server version without issue dependencies), this
> happens **on every run**, and no new issue work is selected until the host returns them. An issue
> that has sub-issues stays unselected even after all of them close. To make it selectable, close it or
> remove its sub-issue links.

*(Architect edit, OQ-2 ruling: the two added sentences are this consumer-facing module's statement of
both fail-closed consequences. There is no CHANGELOG in this repo. The docstring is the shipped surface.)*

---

## 3. Report and exit contract: the only deltas

The S2 contract (TD-1540 §2.2 and §5) otherwise stands byte-for-byte. The following **do not change**:
- stdout format (`#N [priority] title`, title sanitized);
- the summary line's keys and their order;
- the exit-code rules;
- the ALL-CANDIDATES-GATED block;
- every existing token.

### 3.1 Zero added requests

D2b reads only fields already present in Step C's list payload (P1). The request count of a run is still
exactly the following, **identically**:

  list pages fetched  +  events pages fetched in D5  +  collaborator pages (tiers only)

Because excluded and unreadable records never enter D5, T3.0a can only **lower** a run's request count,
never raise it (T-ZC3). §7.2 gives the proof tests.

### 3.2 New stderr lines (all under the existing `select_work_candidates: ` prefix)

1. **The UNEVALUATED line** (`:597-604`) gains one trailing token, always printed when the line is:
   `unevaluated:edge-summary-unreadable=<n>`. The line's trigger condition becomes
   `unevaluated > 0 or list_truncated`, as today, where `unevaluated` now includes `n`.
2. **One line per unreadable record,** in input order, capped at `_EXCLUDED_LIST_BOUND`:
   `WARN unevaluated:edge-summary-unreadable issue=#<N> limb=<dependencies|sub-issues|both>`. If the cap
   binds, one more line follows:
   `WARN unevaluated:edge-summary-unreadable (+<k> more)`.
3. **When `unreadable` is non-empty and `kept` is empty** (every scanned record unreadable), one line:
   `WARN edge-summary-unreadable-on-every-record n=<scanned> — the GitHub host may not return issue dependency / sub-issue summaries on the list endpoint; selection cannot determine blocked-ness (DEGRADED, not "no work")`.
4. **When `excluded` is non-empty,** two lines:
   - `EXCLUDED <m> in-milestone issues are not actionable (not counted in scanned): blocked-by-open-issue=<a> blocker-closed-unverified=<b> untracked-parent=<c>`.
     All three tokens are always printed, and they are sorted in `NATIVE_EXCLUSION_REASONS` order.
   - `EXCLUDED issues: #<N>(<reason>) …` in input order, capped at 20, with `(+<k> more)` appended.
5. **One line per `blocker-closed-unverified` record,** capped at 20:
   `WARN blocker-closed-unverified issue=#<N> — a closed blocker does not unblock until the T3.3 satisfaction check exists; a CODEOWNER may remove the dependency edge if the blocker is satisfied`.

**Emission order in `_report_and_exit`:**
1. the walk WARN lines (existing);
2. UNEVALUATED (1);
3. the query-failed WARNs (existing);
4. (2), then (3);
5. the cost-ceiling lines (existing);
6. AUTHORIZED (existing);
7. the truncation, tier and collaborator WARNs (existing);
8. (4), then (5);
9. ALL-CANDIDATES-GATED (existing);
10. the summary line (existing, last).

Every new line carries only issue numbers and fixed tokens. **No title or other record content reaches
stderr** (the R-1 injection rule of TD-1540).

### 3.3 `_report_and_exit` signature delta

Two parameters are added after `ceiling_refused_at_list`, each defaulting to empty, so the two existing
call sites change only by passing them. *(Architect correction: DRAFT-1 said "three keyword-only". There
are two, and the existing signature has no `*` marker, so do not add one.)*

```
    edge_summary_unreadable: list = ()   # [(number, limb)]
    excluded: list = ()                   # [(number, reason)]
```

`complete` gains no new clause. Unreadable records enter it through `unevaluated`, which the existing
`unevaluated == 0` clause already reads. Excluded records are **determinations** and never affect
`complete`.

### 3.4 Exit-code interplay (the 0/2/3 contract, restated with D2b)

| Situation | stdout | `complete` | Exit | `bin/hos-cron` reading (`:1158-1162`, unchanged) |
|---|---|---|---|---|
| Some `kept` records admitted, no unreadable | candidates | per existing rules | 0 | candidates usable |
| Some admitted, ≥1 unreadable | candidates | **no** | **0** | usable. The unreadable record is a named quarantine hole, the same precedent as AM-31 `query-failed` (T-NB5). |
| None admitted, ≥1 unreadable | empty | **no** | **3** | "WORK SELECTION INCOMPLETE", DEGRADED. **Never "no work"** (T-NB4). |
| Every in-milestone record native-excluded (or D2-excluded) | empty | yes | 0 | "no actionable work", and the cycle skips. This is correct, because nothing is actionable. The EXCLUDED line says why (T-EX3). |
| All `kept` gated, none unreadable | empty | yes | 0 | ALL-CANDIDATES-GATED fires, as today. Excluded records are **not** counted as gated (T-EX2). |
| Any config, list-fetch or argv failure | empty | — | 2 | Unchanged. **D2b adds no exit-2 path**: an unreadable summary is "unknown", not "misconfigured". |

**ALL-CANDIDATES-GATED is untouched.** Its text says "held for human authorization", which is untrue of
a blocked or parent record, so native exclusions never feed it.

---

## 4. `bootstrap/escalate_to_human.sh`, the H5 write path

### 4.1 Purpose and boundary

AD-C6's H5 row gives this script one job: turn a human wait into **H1** (`needs-human` on the issue),
after first recording the question so that the label never exists without its reason. AD-C10 makes
escalation one code path. **This script is that path's write primitive.** T3.6 will call it with a
composed escalation body. It does not decide *whether* to escalate, and it does not compose the question.

**What it must not do:**
- remove the pending-actor label (`needs-ai`), because resume semantics are T3.4/T3.6's;
- touch `stage:*`;
- file a question issue (T3.7a);
- write to a PR (H4 is T3.0b);
- read or write any clone-local state other than the audit record.

### 4.2 CLI (exact)

```
bash bootstrap/escalate_to_human.sh --number <N> --body-file <path> --reason <token> --app <worker|overseer|human>
```

| Flag | Required | Rule |
|---|---|---|
| `--number` | yes | `^[1-9][0-9]*$` |
| `--body-file` | yes | The file exists. Its content is not empty after stripping whitespace. It passes `hos_cfc_check_at_path_literal` (the #1155 `@/` guard). It does **not** contain the substring `<!-- hos-escalation` (a body may not carry a marker; §4.5). Its size plus the marker (§4.5) is ≤ **65,000 bytes**. That is conservatively below GitHub's 65,536-character comment limit, because bytes ≥ characters. |
| `--reason` | yes | `^[a-z][a-z0-9-]{1,63}$`. This is a machine token naming the trigger. It is recorded in the marker and in the audit event (AD-C10 "names its trigger"). T3.0a does not enumerate the allowed values; T3.6 may. |
| `--app` | yes | `worker`, `overseer` or `human`, the same set as the sibling scripts. |
| `--body` | — | **Rejected**, with the siblings' exact message pattern (`--body is not supported — write the body to a file and pass --body-file <path>…`). |
| anything else | — | A usage error. |

All validation happens **before** any token is minted. A validation failure exits 2 (§4.6).

### 4.3 Environment and pattern

- `set -euo pipefail`. `SCRIPT_DIR` resolves as in the siblings. The `err`/`warn` helpers are identical.
- `source "$SCRIPT_DIR/lib/comment_format_check.sh"`, for the `@/` guard.
- The repo slug is resolved from `git -C "$SCRIPT_DIR/.." remote get-url origin`, as in the siblings.
- **One token mint per run:** `bash "$SCRIPT_DIR/get_app_token.sh" --app <role>` into a `mktemp` file;
  source it; delete the file at once (#549). A mint failure exits 1.
  - `HOS_BOT_LOGIN`, exported by `get_app_token.sh`, is **required**. If it is empty, exit 1 before any
    write. Idempotency cannot verify authorship without it.
  - Revocation goes in an **EXIT trap**, so every exit path after the mint revokes the token (T-ESC20).
    Revoke failure only warns, as in the siblings.
- **Every GitHub call is a single `gh api` invocation.**
  - Reads use explicit `?per_page=100&page=<p>`. **Never `--paginate`, and never `-f`/`-F`**, following
    the selector's §1.4 rule.
  - Writes pipe a `jq -n`-built JSON object through `--input -`. **Never `-f body=@path`**, which is the
    #1155 trap (T-ESC21 checks this statically).
- Tools used: `gh`, `git`, `jq`, `curl`, and `sha256sum` (falling back to `shasum -a 256`; if neither
  exists, exit 2 before the mint).

### 4.4 Ordered procedure: record first, then label, then audit

**Reads (R). Nothing has been written yet; a failure here exits 1.**

- **R1.** `GET repos/<slug>/issues/<N>`.
  - A 404 or unparseable response exits 1.
  - If `pull_request` is present, exit 2 with `target-is-pull-request`.
  - If `state != "open"`, exit 2 with `target-not-open`.
  - If the labels include `release-request`, exit 2 with `target-is-release-request`. NG3b owns
    `needs-human` on those issues, and the human's *removal* of it there is an authorization signal
    (`docs/LABELS.md` row `needs-human`). This script must never be able to re-apply it.
  - Record `had_label` (whether `needs-human` is present now).
- **R2.** Compute the key (§4.5). Page through `GET repos/<slug>/issues/<N>/comments?per_page=100&page=p`
  for `p = 1..30`, stopping at the first page with fewer than 100 items. Find **own marker comments**
  (§4.5).
  - A read failure on any page exits 1.
  - If 30 full pages are reached without a short page, the search is **inconclusive**. Proceed as "not
    found", and emit `WARN comment-page-bound-reached; a duplicate question comment is possible`. That
    fails toward recording, never toward silence.
- **R3.** Only when an own marker comment `C` was found **and** `had_label` is false: page through
  `GET repos/<slug>/issues/<N>/events?per_page=100&page=p` for `p = 1..10`.
  - If any event has `event == "unlabeled"`, `label.name == "needs-human"` and `created_at ≥ C.created_at`,
    the escalation was **superseded**. Someone cleared the label after this question was recorded.
  - A read failure exits 1 (transient). The script cannot tell a partial write from a human's clearance,
    and re-applying over a human's act is the worse error.
  - *(Architect correction.)* **The page bound reached (10 full pages without a short page) is not
    transient.** A retry would hit the same bound forever. It is treated as **superseded**: exit **6**,
    stderr token `supersede-undeterminable`, audit `outcome:"supersede-undeterminable"`, zero POSTs. It
    fails toward *not* re-applying the label. The caller's remedy is the same as for `superseded`: a
    *new* body gives a new key, which is a new, legitimate escalation (T-ESC23).

**Decision.**

| Found own `C`? | `had_label` | Superseded (R3) | Action | Outcome |
|---|---|---|---|---|
| no | any | — | W1 to W5 | `escalated` |
| yes | true | — | W5 only | `already-escalated` |
| yes | false | no | W3 to W5 (repair) | `label-repaired` |
| yes | false | yes | W5 only, exit 6 | `superseded` |

**Writes (W). Each step halts before the next on failure. This is SPEC-378 halt-on-failure (AD-C7).**

- **W1: record.** `POST repos/<slug>/issues/<N>/comments` with `{"body": <body-file bytes> + "\n\n" + <marker line> + "\n"}`,
  built with `jq -n --rawfile`. Capture `id` and `html_url`. On failure, exit **4**. The POST may have
  landed, and a re-run is safe (§4.5).
- **W2: confirm.** `GET repos/<slug>/issues/comments/<id>`. The comment must have
  `user.login` equal to `HOS_BOT_LOGIN` (case-insensitive) and `user.type == "Bot"`, and its body must
  contain the exact marker line. If any check fails, exit **4**. **The label is never applied on an
  unconfirmed record.**
- **W3: label.** `POST repos/<slug>/issues/<N>/labels` with `{"labels":["needs-human"]}`. This is the
  add endpoint. It never replaces labels, so it does not clobber concurrent edits, following
  `edit_issue.sh`. On failure, exit **5**.
- **W4: verify.** `GET repos/<slug>/issues/<N>`. `needs-human` must be in `labels[].name`. If it is not,
  exit **5**.
- **W5: audit.** Best-effort (§4.7). A failure here never changes the exit code.

On the `escalated` path, W1 runs even if `had_label` is already true. A new question is a new record,
and W3 is then a no-op add.

### 4.5 Idempotency: the marker and the key

- **Key.** The first 16 hex characters of
  `sha256("hos-escalation-v1" NUL <N> NUL <reason> NUL <body-file bytes>)`.
  - The same issue, reason and body always give the same key.
  - A changed question gives a new key, and so a new record. That is intended: it is a new escalation.
- **The marker line**, appended as the comment's last line and invisible when rendered:
  `<!-- hos-escalation v=1 reason=<reason> key=<key> -->`.
  - Matching grammar: `^<!-- hos-escalation v=1 reason=([a-z][a-z0-9-]{1,63}) key=([0-9a-f]{16}) -->$`,
    applied to a whole line.
- **Own marker comment:** a comment whose body has a line matching the grammar **with this run's exact
  key**, and all three of the following:
  1. `user.login` equals `HOS_BOT_LOGIN` (case-insensitive);
  2. `user.type == "Bot"`;
  3. `updated_at == created_at`.
- **Why each condition:**
  - (1) and (2): any user can paste a marker line into a comment. Without the author test, a forged
    marker would **suppress** a real escalation (T-ESC11).
  - (3): an edited comment may no longer say what was escalated, so the script re-records rather than
    trust it (T-ESC12).
  - If reactions do move `updated_at` (the open §0 gap), a reacted-to escalation comment fails (3). The
    only cost is **one duplicate question comment** on a re-run. Neither answer to the gap can suppress
    an escalation or re-apply a label over a human's act.
- **Bodies may not carry a marker** (§4.2). Otherwise a caller re-posting an old escalation's text would
  make the new comment match the old key.
- **Concurrency.** Two concurrent runs with the same key can both miss each other's comment in R2 and
  both post. The result is a duplicate comment, which is harmless. There is no lock, and none is needed,
  because W3 is idempotent.

### 4.6 Exit codes and output

| Exit | Meaning | Writes made | Caller's correct response |
|---|---|---|---|
| 0 | `needs-human` is on the issue **and** a confirmed own record exists (`escalated`, `already-escalated`, `label-repaired`) | as the table in §4.4 | Done. |
| 1 | Transient: token mint, identity, or any pre-write read (R1 to R3) failed. An inconclusive R2 proceeds as "not found" (§4.4). An inconclusive R3 is exit 6 (architect correction). | **none** | Retry later, unchanged. |
| 2 | Refused: usage, body, or target precondition (not open, a PR, a `release-request`, oversized, carries a marker, no sha256 tool) | **none** | Fix the input. Do not retry unchanged. |
| 4 | `record-failed`: W1 or W2 failed. The label was **not** applied. A comment may exist. | maybe a comment | Retry the identical command. Idempotency finds a landed comment. |
| 5 | `partial`: the record is confirmed, but `needs-human` was not applied or not verified | the comment | **Retry the identical command.** It takes the `label-repaired` path. Until then the issue is still selectable, which is the §4.8 residual. |
| 6 | `superseded`: an own record exists, and `needs-human` was removed after it. Also `supersede-undeterminable`: the R3 event page bound was reached (architect correction, §4.4 R3) | none | Do not retry. If still blocked, escalate again with a *new* body. |

Code 3 is deliberately unused, so that no reader confuses this script's codes with the selector's
DEGRADED.

**stdout** gets exactly one line, and only on exit 0:
`escalated issue=#<N> outcome=<escalated|already-escalated|label-repaired> reason=<r> key=<k> comment=<html_url>`.

**stderr** gets one `escalate_to_human: <outcome-or-refusal-token> issue=#<N> …` line on every non-zero
exit. On exit 5 a second line follows, verbatim:
`escalate_to_human: REPAIR — re-run the identical command; the question is recorded at <html_url> but needs-human is NOT applied, so the issue is still selectable`.

### 4.7 Audit event

The event is written through `scripts/oversight/lib/audit_log.sh::audit_write_event '<json>' "$SCRIPT_DIR/.."`,
using the exact best-effort shape of `submit_pr.sh::_hos_audit_stale_base_merge`:
- if the library is missing, skip;
- if `audit_write_event` is undefined, skip;
- the write is followed by `|| true`;
- a skipped or failed write prints `warn "audit event not written"` to stderr and **never** changes the
  exit code.

No decision reads this event (ADR-1643 AD-8, ADR-1644 AD-C19).

It is emitted on exits **0, 4, 5 and 6**. It is not emitted on 1 or 2, when nothing happened. The JSON
is built with `jq -nc --arg/--argjson`, never `printf`-interpolated:

```
{"event":"escalated-to-human",
 "issue":<N>, "reason":"<r>", "key":"<k>",
 "outcome":"escalated|already-escalated|label-repaired|record-failed|partial|superseded|supersede-undeterminable",
 "comment_id":<id or null>, "app":"<role>", "actor":"<HOS_BOT_LOGIN>",
 "label_present_before":<bool>, "timestamp":"<UTC ISO-8601 Z>"}
```

### 4.8 Stated residuals

- **An exit-5 window.** The question is recorded and the label is missing, so the issue stays selectable
  until a re-run. This is the direction AD-C7's ordering accepts, because the record precedes the label.
  The exit-5 stderr and audit event make it loud. The alternative ordering (label first) is the TD-F4
  defect.
- **A duplicate question comment** is possible under concurrency, the page bound, or the reactions gap
  (§4.5). It is cosmetic only.
- **The selector cannot see prose.** H5 becomes H1 only when a caller runs this script. T-NS4b (§7.1)
  pins that limit so that nobody reads T-NS4a as covering prose-only waits.

---

## 5. Prose and docs deltas (minimal)

- **`bootstrap/worker-cron-prompt.md`.** One paragraph goes in the section where the worker reports a
  wait on a human answer. It says that such a wait **must** be recorded with
  `bash bootstrap/escalate_to_human.sh --number <N> --body-file <path> --reason awaiting-human-answer --app worker`,
  so that the selector stops choosing the issue, and that a prose-only wait leaves it selectable.
  - Write the label name in backticks only. `test_excluded_labels_is_defined_in_exactly_one_place`
    forbids a quoted `"needs-human"`/`'needs-human'` literal in this file.
  - Do **not** touch "Pick the first non-blocked candidate" (`:96`). Retiring it is T3.9 (AD-C20).
- **`docs/LABELS.md`.**
  - The `needs-human` row's Writers column gains
    `bootstrap/escalate_to_human.sh (record-first: question comment, then label; ADR-1644 AD-C6 H5)`.
  - Its "Work-selection exclusion" text gains one sentence: native blockers and sub-issue parents are
    also excluded, free, from the list record (ADR-1644 AD-C4), and that exclusion is not
    label-carried.
- **`CLAUDE.md`, "Canonical entry points by task".** One row:
  `Recording a human wait (question comment, then needs-human, idempotent) | bootstrap/escalate_to_human.sh`.
- **`.claude/agents/worker.md` is NOT in this PR.** A matching instruction there is an agent-definition
  edit. Per CLAUDE.md (#1347), it must be authored directly by the top-level session, never by `coder`.
  *(Architect ruling OQ-3(b): **deferred to T3.6**, with the `worker.md:291-295` label-first migration.
  It is not a companion edit to this PR. See ADR-1644 Erratum 1, E4.)*

---

## 6. Test fixtures

### 6.1 The canonical zero summaries

Both helpers below gain these two keys by default:

```
"issue_dependencies_summary": {"blocked_by": 0, "blocking": 0, "total_blocked_by": 0, "total_blocking": 0},
"sub_issues_summary": {"total": 0, "completed": 0, "percent_completed": 0},
```

### 6.2 Fixture corrections (TD-F2): expectations unchanged

- `tests/framework/test_select_work_candidates.py::_issue` gains keyword overrides
  `deps: Optional[dict] = <zero>` and `subs: Optional[dict] = <zero>`. A sentinel `_OMIT` drops the key
  entirely.
- The two raw literals in `test_missing_or_null_labels_does_not_crash` (`:206-216`) gain the zero
  summaries.
  - That test is about labels. Its expectation `[5, 10, 20]` is unchanged.
- PR literals (`:232-239`, `:368-374`, `:520-526`) are **not** changed. D1 drops them before D2b (TD-F1),
  and leaving them summary-less is itself a regression check on that order.
- `tests/automation/test_hos_cron.py::_candidates_json` gains the zero summaries, plus an optional 4th
  tuple element that overrides `issue_dependencies_summary` (used by T-HC1).

---

## 7. Test plan

The test IDs are binding. Each maps to an ADR clause in §7.5.

### 7.1 Native exclusion and the ESC-8 tests: `tests/framework/test_select_work_candidates_native.py`

All tests use the existing `gate_repo`, `stub` and `run_gate` fixtures, imported or duplicated.

| ID | Fixture | Asserts |
|---|---|---|
| **T-NB1** | #10 `blocked_by=1,total=1`, #11 clear | stdout `[11]`. `EXCLUDED … blocked-by-open-issue=1`. `EXCLUDED issues: #10(blocked-by-open-issue)`. Exit 0, `complete=yes`, `scanned=1`. |
| **T-NB2** | #20 `blocked_by=0,total=1`, #21 clear | stdout `[21]`. The reason is `blocker-closed-unverified`. The WARN line for #20 is present verbatim. |
| **T-NB3** | Parametrized over each malformation, applied to the dependency summary and, separately, the sub-issue summary: key absent, `None`, a list, a string, a missing field, a `bool` field, a negative field, a float field, `blocked_by > total_blocked_by` | The record is **not emitted**. It is counted in `unevaluated:edge-summary-unreadable`. `WARN … issue=#N limb=<limb>` names the right limb. `complete=no`. |
| **T-NB4** | Only one record, with its dependency summary absent | stdout empty. **Exit 3.** `unevaluated=1`, `unevaluated:edge-summary-unreadable=1`, `complete=no`. |
| **T-NB5** | #30 critical, unreadable; #31 low, clear | stdout `[31]`. **Exit 0.** `complete=no`. #30 is named on its WARN line (the quarantine-hole precedent). |
| **T-NB6** | #40 `sub_issues total=2`; #41 `total=1, completed=1`; #42 clear | stdout `[42]`. #40 and #41 are both `untracked-parent`. |
| **T-NB7** | #50 labeled `stage:code` + `blocked_by=1`; #51 labeled `stage:tracking`, `total=0` | #50 is reported only as `blocked-by-open-issue`. No `stage-malformed` token appears anywhere. #51 is **emitted**: stage labels are inert in T3.0a (§2.2). *(Architect note: the #51 limb pins T3.0a's scope boundary. It is **not** an ADR property. T3.2 inverts it, because `stage:tracking` then means excluded with `tracking-parent` (AD-C4). The test docstring must say so.)* |
| **T-NB8** | Spy on `_rank`, like the existing limb (c): #60 critical and blocked, #61 critical and a parent, #62 critical and unreadable, #63 critical and clear | `_rank` is called for **63 only**. |
| **T-NB9** | #70: dependency summary absent, `sub_issues total=1` | `untracked-parent`, **not** unevaluated. `complete=yes`. Exclusion wins over unreadable (R3 before R4). |
| **T-NB10** | Property: for every `0 ≤ b ≤ t ≤ 3`, call `_native_verdict` directly | `outcome == "excluded"` iff `t > 0`. The reason is `blocked-by-open-issue` iff `b > 0`. |
| **T-NB11** | A PR record with both summaries `None`, plus a clear issue | The PR is not counted in `unevaluated` and there is no WARN for it. `complete=yes`. |
| **T-NB12** | #80 `needs-human` + dependency summary absent | Not emitted, not unevaluated, not in EXCLUDED. D2 wins. `complete=yes`. |
| **T-NB13** | A hostile dict in which every key except the two summaries raises on access, passed to `_native_verdict` | It returns without touching `labels`, `user`, `title` or `body`. |
| **T-EX1** | Any T-NB1 run | stdout lines match `^#\d+ \[(critical\|high\|medium\|low)\] ` exactly. The summary line has exactly the S2 keys in the S2 order. |
| **T-EX2** | #90 worker-bot-authored, gated (events `[]`); #91 blocked | `ALL-CANDIDATES-GATED 1 of 1`, and its reasons show `no-codeowner-actor=1` only. #91 is in EXCLUDED, not gated. |
| **T-EX3** | Every record blocked or a parent | stdout empty, exit 0, `complete=yes`, `scanned=0`, and no ALL-CANDIDATES-GATED line. |
| **T-EX4** | A mix of eligible, gated, query-failed, unreadable, excluded, and sufficiency-stopped records | `scanned == evaluated + unevaluated`, `evaluated == eligible + gated`, and `unevaluated == sufficient + cost-ceiling + query-failed + edge-summary-unreadable`. |
| **T-EX5** | `--max-api-requests 1` with a full list page 1 (so page 2 is REFUSED), containing 2 unreadable and 1 excluded record | `unevaluated:cost-ceiling == len(kept)`, `edge-summary-unreadable == 2`, the identities hold, and there is no double count. |
| **T-EX6** | 25 unreadable records | Exactly 20 per-record WARNs, then `(+5 more)`. The "every record" WARN is present. Exit 3. |
| **T-NS1** | ADR text: A (`priority:critical`, `stage:architecture`, `needs-human`), B (`critical`, `stage:code`, `blocked_by=1`), C (`low`, no stage) | stdout is exactly `[C]`. B is reported as `blocked-by-open-issue`. |
| **T-NS2** | ADR text: D (`low`, `stage:design`, actionable), E (`critical`, no stage) | stdout `[D, E]`. **`pytest.mark.xfail(strict=True, raises=AssertionError, reason="in-flight ordering is T3.2's gate (ADR-1644 Erratum 1, E1)")`.** *(Architect ruling OQ-1.)* `raises=AssertionError` makes a fixture or harness error **fail** the test instead of counting as the expected failure, so the xfail cannot pass vacuously. **Do not write T-NS2-pre.** A test that asserts the order the ADR rules wrong (`[E, D]`) is a characterization of a known defect. It is not needed once `raises=` closes the vacuity hole. |
| **T-NS3a** | Six in-flight human-blocked records, all `priority:critical` and **trusted-author**: three `needs-human`, three `blocked_by=1`. One new record, `low` and clear. `--max-candidates 5`. | The new record **is** emitted, and `unevaluated:sufficient=0`. This fails if exclusion ever moves after the sufficiency cut. |
| **T-NS3b** | The same, with the six **worker-bot-authored** (untrusted) | The new record is emitted, and **zero** `/events` calls are made for the six. This fails if exclusion ever moves after D5's paid walk. |
| **T-NS4a** | Replay of 2026-09-30, post-T3.0a encoding: #1643-shape (`critical`, `bug`, `process-gap`, **`needs-human`** as `escalate_to_human.sh` would leave it); #1644-shape (`high`, `enhancement`, `process-gap`, **`blocked_by=1`**, for a native blocker on a question issue); eligible #1700 (`high`), #1701 (`medium`), #1702 (`low`) | stdout `[1700, 1701, 1702]`, and the first emitted line is `#1700`. |
| **T-NS4b** (negative control) | The same five records with **no** carrier on #1643/#1644 (their live P3 state) | stdout begins with `#1643`. The docstring states that this pins the H5 limit: the selector cannot see prose waits, which is why `escalate_to_human.sh` exists. |

The fixture shapes of #1643/#1644 are **shapes only**: priority and labels as probed in P3, plus the ADR's
description of 2026-09-30. They make no claim about those issues' state beyond that.

### 7.2 Zero added requests: the mocked-`gh` proof (REQ-C11 AC, ADR §5 gate)

| ID | Mechanism | Asserts |
|---|---|---|
| **T-ZC1** (in-process, golden + differential) | Fixture F0: records #1 to #3 with a trusted author, #4 untrusted with events `[labeled by ScottThurlow]` (authorized), #5 untrusted with events `[]` (gated). All summaries are zero. Run once normally. Then monkeypatch `swc._native_verdict` to `lambda r: _NativeVerdict("clear", "")`, which **simulates pre-T3.0a behavior**, and run again. | (a) **Golden:** `stub.calls == [list p1, events #5 p1, events #4 p1]` in walk order (rank ties, number DESC), `len == 3`, and the summary shows `api_requests=3`. (b) **Differential:** the two runs' `stub.calls` lists are **identical**, element for element. |
| **T-ZC2** (subprocess, PATH-level fake `gh`) | Write an executable `gh` (a Python script) into `tmp/bin`. It appends its full argv as one JSON line to `tmp/gh-calls.jsonl` and serves F0 by endpoint regex. It **exits 97 on any endpoint outside the three S2 families** (list `…/issues?state=open&milestone=…`, `…/issues/<n>/events?…`, `…/collaborators?…`). Run `python3 -c "import sys; from pathlib import Path; import scripts.framework.select_work_candidates as s; s._REPO_ROOT = Path(sys.argv[1]); sys.exit(s.main(sys.argv[2:]))" <gate_repo> --repo owner/repo --milestone 5` with `cwd=REPO_ROOT` and `PATH=tmp/bin:$PATH`. | Exit 0. There are exactly **3** lines in `gh-calls.jsonl`, equal to the stderr `api_requests=3`. Every argv is `["api", <endpoint>]`: no `--paginate`, no `-f`/`-F`, no `graphql`. No endpoint contains `/dependencies`, `/sub_issues`, `/parent`, `/timeline`, or a bare single-issue GET. **This catches any new request path, including one that bypasses `_run_gh`.** |
| **T-ZC3** (exclusion only removes requests) | F0 plus `blocked_by=1` on #5 and `sub_issues total=1` on #4 | `stub.calls == [list p1]`, `api_requests=1`. That is F0's calls minus exactly the two events fetches. |
| **T-ZC4** (static) | Parse `select_work_candidates.py` with `ast` | No string constant contains `/dependencies`, `/sub_issues`, `/timeline`, `parent_issue` or `graphql`. `subprocess` is referenced only inside `_run_gh`. `_native_verdict`, `_dependency_counts` and `_sub_issue_total` contain no `Call` to `_run_gh`, `_fetch_pages` or `subprocess.*`. *(Architect addition.)* The module imports none of `urllib.request`, `http.client`, `http`, `requests`, `socket` or `scripts.automation.lib.github`. `urllib.parse` stays allowed, because `main` uses it. This closes the in-process HTTP path that T-ZC2's PATH shim cannot see. |

### 7.3 `escalate_to_human.sh`: `tests/automation/test_escalate_to_human.py`

The harness copies `test_edit_issue.py`'s:
- the script is copied to `tmp/bootstrap/`, beside a stub `get_app_token.sh` that exports `GH_TOKEN` and
  `HOS_BOT_LOGIN='hos-worker-hos[bot]'`, plus a copied `lib/comment_format_check.sh`;
- `gh`, `git` and `curl` are PATH stubs;
- a stub `tmp/scripts/oversight/lib/audit_log.sh` defines `audit_write_event` to append its JSON to a
  capture file;
- the `gh` stub serves issue, comments, events and comment-by-id from env-provided JSON, logs
  `METHOD PATH` in order, and captures stdin bodies.

| ID | Asserts |
|---|---|
| **T-ESC1** | Each missing required flag exits 2 with no `gh` call and no mint. |
| **T-ESC2** | `--body` is rejected with the sibling message, exit 2. |
| **T-ESC3** | A bad `--app`, a bad `--number`, and a bad `--reason` (`Bad`, `x`, 65 characters, `a_b`) each exit 2. |
| **T-ESC4** | The body file is missing, empty or whitespace-only, starts with `@/`, contains `<!-- hos-escalation`, or exceeds 65,000 bytes with the marker. Each exits 2, with no mint. |
| **T-ESC5** | The target is a PR, closed, or carries `release-request`. Each exits 2, with **no POST of any kind**. |
| **T-ESC6** (happy path, **ordering**) | The call log is exactly GET issue, GET comments p1, POST comment, GET comment/<id>, POST labels, GET issue. The **POST comment index is less than the POST labels index.** The comment body ends with the marker line for the expected key. Exit 0. stdout `outcome=escalated`. |
| **T-ESC7** | The key is deterministic. The same inputs give the same key across runs. A one-byte body change, a different `--reason`, or a different `--number` changes it. The expected key is computed in the test with `hashlib`. |
| **T-ESC8** (idempotent full) | The comments contain an own marker comment with this key, and the issue has `needs-human`. **Zero POSTs.** Exit 0, `already-escalated`. |
| **T-ESC9** (partial repair) | An own marker comment, `needs-human` absent, and events show no later `unlabeled`. The only POST is POST labels. Exit 0, `label-repaired`. |
| **T-ESC10** (superseded) | An own marker comment, `needs-human` absent, and an `unlabeled needs-human` event after `C.created_at`. **Zero POSTs.** Exit 6. |
| **T-ESC11** (forged marker) | A marker comment with the correct key authored by `someone` (User), and separately by `hos-overseer-hos[bot]` under `--app worker`. The script **posts** the record. Exit 0, `escalated`. |
| **T-ESC12** (edited marker) | An own marker comment with `updated_at != created_at`. The script posts. Exit 0. |
| **T-ESC13** | The marker comment is on page 2, after a full page 1. It is found, and there are no POSTs. |
| **T-ESC14** | POST comment fails. Exit 4. **POST labels never called.** Audit `record-failed`. |
| **T-ESC15** | The read-back comes back with the wrong author, or without the marker. Exit 4. POST labels never called. |
| **T-ESC16** | POST labels fails. Exit 5. stderr carries the verbatim REPAIR line with the comment URL. Audit `partial`. |
| **T-ESC17** | The verify GET does not show `needs-human`. Exit 5. |
| **T-ESC18** | A pre-write read fails: token mint, empty `HOS_BOT_LOGIN`, R1, R2 or R3. Exit 1, zero POSTs, no audit event. |
| **T-ESC19** | Audit: the event JSON has exactly the §4.7 keys, the right `outcome` on exits 0/4/5/6, and nothing on 1/2. With the audit lib absent, exit 0 is unchanged and the warn is printed. |
| **T-ESC20** | The token is revoked (curl DELETE captured) on **every** post-mint exit path: 0, 1, 4, 5, 6. |
| **T-ESC21** (static) | The script text contains no `--paginate`, no `-f `/`-F `/`--field`/`--raw-field`, no `body=@`, no `gh issue edit`, and no `gh issue comment`. Every write uses `--input -`. |
| **T-ESC22** | The label is already present on a fresh key. The record **is** posted, the label add is a no-op, exit 0 `escalated`, and the audit shows `label_present_before:true`. |
| **T-ESC23** *(architect addition)* | An own marker comment, `needs-human` absent, and events serve 10 full pages with no qualifying `unlabeled`. Exit **6**, stderr `supersede-undeterminable`, **zero POSTs**, and audit `outcome:"supersede-undeterminable"`. |

### 7.4 Launcher integration: `tests/automation/test_hos_cron.py`

- **T-HC1.** `CronEnv` with `HOS_TEST_ISSUE_CANDIDATES_JSON = _candidates_json((10, "blocked", ["needs-ai","priority:critical"], {"blocked_by":1,"total_blocked_by":1,...}), (11, "free", ["needs-ai"]))`.
  - The worker prompt's candidate block contains `#11`, and does **not** contain `#10`.
  - The launcher's stderr passthrough contains `EXCLUDED issues: #10(blocked-by-open-issue)`.
  - This is the one test that runs the real `bin/hos-cron` path (ADR §0's "no behavior was run under
    `bin/hos-cron`").

### 7.5 Traceability: every AD-C4 and AD-C6 clause in scope maps to a test

| Clause | Tests |
|---|---|
| AD-C4: these run in D1/D2, before D-rank and before any paid D5 request | T-NB8, T-NS3a, T-NS3b, T-ZC3 |
| AD-C4: request budget, exit contract and stderr contract unchanged; only new tokens | T-EX1, T-EX2, T-EX4, T-EX5, T-ZC1, T-ZC2, and the existing S2 suite green after the TD-F2 correction |
| AD-C4: `blocked_by > 0` gives `blocked-by-open-issue` | T-NB1, T-NB10 |
| AD-C4: `total_blocked_by > blocked_by` gives `blocker-closed-unverified` (until T3.3) | T-NB2, T-NB10 |
| AD-C4: summary missing or malformed gives unevaluated, `complete=no`, DEGRADED when nothing else is emitted, and is never "not blocked" | T-NB3, T-NB4, T-NB5, T-EX6, T-NB11 (PR not misread) |
| AD-C4: `sub_issues_summary.total > 0` gives `untracked-parent` | T-NB6, T-NB9 |
| AD-C4: graph contradiction reported under the blocker reason | T-NB7, T-NS1 |
| AD-C4: every exclusion runs before ranking | T-NB8 |
| AD-C4: label-actor verification is NOT done here (zero cost) | T-ZC1, T-ZC2, T-NS3b |
| §5 T3.0a gate: zero added requests, proven by a mocked-`gh` request count | **T-ZC1** (golden + differential), **T-ZC2** (PATH shim), T-ZC3, T-ZC4 |
| REQ-C11 AC: "request count of a run with no dependency edges unchanged" | T-ZC1(b) |
| REQ-C16 AC: a code-issue whose blocker is unsatisfied is never emitted | T-NB1, T-NB2, T-HC1 |
| AD-C6 property: a human-blocked item is never a candidate; exclusion precedes the sufficiency cut | T-NS1, T-NS3a, T-NS3b, T-NS4a |
| AD-C6 H1 (`needs-human`) | the existing `test_needs_human_is_excluded`, T-NS1, T-NB12 |
| AD-C6 H2 (`blocked_by > 0`) | T-NB1, T-NS1, T-NS4a |
| AD-C6 H5 (`escalate_to_human.sh`, record-first) | T-ESC6 (ordering), T-ESC14 to T-ESC17 (halt-on-failure), T-ESC8 to T-ESC10 (idempotency and supersede), T-NS4a/T-NS4b |
| AD-C6 T-NS1, T-NS3, T-NS4 (T3.0a's gate after Erratum 1, E1) | T-NS1, T-NS3a/b, T-NS4a/b |
| AD-C6 T-NS2 (T3.2's gate after Erratum 1, E1) | T-NS2, shipped here as strict xfail with `raises=AssertionError` |
| AD-C10: one code path, names its trigger, record-first | T-ESC3 (`--reason`), T-ESC6, T-ESC19 |
| AD-C7 write order (record, confirm, label, audit; halt before label) | T-ESC6, T-ESC14, T-ESC15 |

---

## 8. Affected existing tests and sign-offs (the startup-gap analysis)

**Should this have been settled in the initial technical design?**
- **No, for the exclusions.** Native edges became the carrier only with the human's 2026-09-30 ESC-3/ESC-5
  rulings and ADR-1644 AF-C1, which came after TD-1540 revision 8.
- **Partly, for fixture realism.** TD-1540's fixtures model a list record that the live API does not
  return (P1: the summaries are always present). That is a test-fidelity gap, not a contract gap, and TD-F2
  corrects it without changing any expectation. I do **not** recommend a `startup-artifact-gap` issue for
  it.

**Tests whose expectation changes. These are named, not "re-run the suite and call it green":**

1. `test_select_work_candidates.py::TestSummaryInvariants::test_unevaluated_partition_sums_to_its_three_named_reasons`.
   Rename it to `…_four_named_reasons` and add `unevaluated:edge-summary-unreadable` to the sum. Its
   fixture is unchanged, and the new term is 0 there.
2. *(Architect addition, a strengthening, not a change of expectation.)*
   `test_unevaluated_tokens_never_appear_in_the_gated_reasons_breakdown` adds
   `unevaluated:edge-summary-unreadable` to its forbidden-token tuple. Its docstring already says "the
   four unevaluated:* tokens", and with this token there are five.
3. **No other existing test's expectation changes.**
   - `test_missing_or_null_labels_does_not_crash` and every `_issue`/`_candidates_json` consumer change
     their **fixtures only** (TD-F2).
   - The three PR-literal tests are unchanged by design.

**Sign-offs:**
- **These stand:** every S2 sign-off and panel run on trust (`requester_trust.py` is untouched), the
  budget, the exit-code rules, AM-31 quarantine, AM-32's caller contract, and the ALL-CANDIDATES-GATED
  block. D2b adds no request, no exit path and no trust input.
- **These re-open for this PR's own review, not retroactively:** S2's "algorithm order is part of the
  contract" (§2.3 of TD-1540). D2b inserts a step. It is exclusion-only, but it is a change to a
  protected selection surface, so `security-reviewer` and `code-reviewer` review the D1→D2→D2b order and
  TD-F1 explicitly. **No already-approved code is orphaned.**

---

## 9. Open questions for the architect

**OQ-1: T-NS2 cannot pass inside T3.0a as scoped. Please rule.**
- **The conflict.** ADR §5 places "ESC-8 tests T-NS1 to T-NS4 against the selector" in T3.0a, and "AD-C4's
  stage parse and in-flight ordering" in T3.2. T-NS2 asserts `[D, E]`: low in-flight beats critical new.
  That **requires** in-flight ordering. In-flight ordering requires the stage parse ("exactly one *known*
  stage label"). The known-stage set is AD-C1's registry data, which is T3.1's.
- **The other three pass on exclusion alone.** T-NS1, T-NS3 and T-NS4 need no ordering change.
- **My proposed resolution, which this draft binds unless you rule otherwise:** ship T-NS2 in T3.0a as
  `xfail(strict=True)` naming T3.2, with the T-NS2-pre companion. Strict xfail turns into a hard
  **failure** the moment T3.2 makes it pass, which forces T3.2 to remove the marker. The test therefore
  exists from the first release and cannot silently stay dormant.
- **The alternative:** move in-flight ordering into T3.0a with a hard-coded stage set. That creates a
  second vocabulary source ahead of AD-C1's registry, which AD-C1 ("one loader") and §5 ("no labels, no
  registry") both forbid. I do not recommend it.
- **Question:** accept the strict-xfail reading of "T-NS1 to T-NS4 in T3.0a", or re-scope?

**OQ-2: two fail-closed consequences to confirm, not re-decide.**
- **(a) Hosts without the summaries go DEGRADED permanently.** A consumer whose GitHub host or API version
  does not return `issue_dependencies_summary`/`sub_issues_summary` on the list endpoint (for example, an
  older GHES) will have **every** record unreadable. That means exit 3 every cycle: the worker never
  selects new issue work there.
  - This is AD-C4's binding "never not blocked". The design makes it loud (§3.2 line 3) and adds no
    knob.
  - Please confirm it is accepted, and whether a release-note line is wanted.
- **(b) `untracked-parent` counts closed children.** `sub_issues_summary.total` includes completed
  children, so a parent stays excluded after all its sub-issues close. I read AD-C4's "an epic with
  children is not leaf work" as intending that. Please confirm.

**OQ-3: `escalate_to_human.sh` boundaries I bound strictly.**
- **(a) Target restrictions.** The script refuses PRs, closed issues and `release-request` issues. It does
  **not** remove the pending-actor label. T3.0b and T3.6 may widen it, each with a design edit here.
- **(b) The `worker.md` companion edit** (§5) is needed for H5 to fire from the interactive and model
  paths as well. It must be authored by the top-level session (#1347), outside this PR.
- **(c) Shipping.** The script ships with the same (non-)listing as its siblings. There is no new
  consumer-shipping obligation.
- **(d) TD-F4.** Please record that T3.6 migrates `bin/hos-cron:1732-1739`'s label-first escalation, and
  `merge_authority.py`'s question-less `needs-human` writes where they apply to issues, onto this script,
  so that AD-C10's "one code path" becomes true.

No product question arose, so there is no `pm-agent` escalation. PM-2's acceptance-criterion wording is
unaffected, because T3.0a does no actor verification.

---

## 10. Architect rulings and binding corrections (round 1, 2026-09-30)

**Verdict: APPROVED_WITH_EDITS.** The edits are applied in place above and marked *(Architect …)*. The
ADR-level rulings are in ADR-1644 **Erratum 1**.

**Rulings on the open questions:**
- **OQ-1: re-scoped by ADR erratum (E1).** T-NS2 is a **T3.2 gate test**. T3.0a ships it as
  `xfail(strict=True, raises=AssertionError)`. The ADR's §5 T3.0a row was wrong to list T-NS2: in-flight
  ordering is T3.2's content, and the TD's reasoning is correct. T-NS2-pre is **dropped** (see §7.1). The
  alternative, a hard-coded stage set in T3.0a, is **rejected** for the reason the TD gives: it would be a
  second vocabulary source, which AD-C1 forbids.
- **OQ-2(a): confirmed.** DEGRADED on every cycle on a host without the summaries is AD-C4's binding
  fail-closed outcome. It stays loud (§3.2 line 3), it gets no knob, and it is stated in the shipped
  docstring (§2.6 edit).
- **OQ-2(b): confirmed.** `total` includes closed children, and the parent stays excluded. That is the
  safe direction: an epic whose children are done has no leaf work left. The human remedy before T3.2 is
  to close the parent or unlink its children. The remedy is stated in the docstring (§2.6 edit).
- **OQ-3(a): confirmed as bound.** The script refuses PRs, closed issues and `release-request` issues, and
  it never removes `needs-ai`.
  - The `release-request` refusal is **required**, not merely prudent. `needs-human` removal on those
    issues is an NG3b authorization signal (`docs/LABELS.md` row `needs-human`).
  - Widening the target set needs a TD edit **and** an architect ruling.
- **OQ-3(b): deferred to T3.6 (E4).** The `worker.md` instruction is **not** a T3.0a companion edit. The
  2026-09-30 H5 case was autonomous, and this PR's `worker-cron-prompt.md` paragraph covers the autonomous
  path. `worker.md` also carries its own label-first site (TD-F4, `:291-295`). Both belong in T3.6, which
  makes escalation one code path.
- **OQ-3(c): confirmed.** Consumer shipping matches the siblings. The bootstrap write scripts are not in
  `framework_consumer_files.txt`, and neither is `worker-cron-prompt.md`, while the selector **is**
  listed. That is a pre-existing gap across the whole family, not T3.0a's to fix. It is reported to the
  orchestrator.
- **OQ-3(d): recorded (E4).** T3.6 migrates `bin/hos-cron:1732-1739` and `worker.md:291-295` onto this
  script. T3.6's TD must list **every** issue-side `needs-human` writer and say, for each one, whether it
  migrates or why it does not. Two stay out, by name:
  - `merge_authority.py::route_embargo` is an embargo, not a question;
  - NG3b R4 step 0b is a `release-request` issue, which this script refuses.

**Review findings on the unasked checks:**
- **Scope: holds.**
  - No label is created, no `contract/stages/` file is touched, and there is no executor.
  - `needs-human` already exists, and `stage:*` is inert.
  - The three prose edits are one paragraph or one row each, and each points at the new script.
- **Reason strings and precedence: match AD-C4 and AD-C6.**
  - `blocked-by-open-issue`, `blocker-closed-unverified` and `untracked-parent` are the ADR's literals.
    `edge-summary-unreadable` is a permitted new `unevaluated:` sub-token ("only new reason tokens").
  - "Exclusion wins over unreadable" (R1 to R3 before R4) is **accepted**, because the ADR's "missing ⇒
    unevaluated" rule is per-summary.
    - A record whose *readable* summary already proves it unselectable is a determination, not an
      unknown.
    - It is never "not blocked", so AD-C4's invariant holds.
  - D2 (`needs-human`) preceding D2b is correct.
    - H1 is silent today.
    - Reporting H1 records under EXCLUDED would change an existing contract for no gain.
  - Placing D2b after D1 is **required** by live evidence (TD-F1, P2), not by preference.
- **The zero-added-request proof: sound, with one gap closed by edit.**
  - The anchor is T-ZC1(a), the golden absolute count. T-ZC1(b)'s differential only proves that an
    all-clear D2b is request-neutral, which is weak on its own and acceptable as a supplement.
  - T-ZC2's PATH shim catches any new `gh` path. It could not see an in-process HTTP client. T-ZC4 now
    forbids one (edit).
  - T-ZC3 proves monotonic decrease.
  - I verified the three-call golden against the code. The walk key is `(rank, -number)`, so #5 is walked
    before #4. `gate_repo` has no tier, so there is no collaborator page. Every `_run_gh` argv is exactly
    `["gh","api",endpoint]` (`select_work_candidates.py:219`).
- **Exit 2/3 contract (#1540 S2 AD-3): preserved.** Checked against `_report_and_exit:586-660` and
  `bin/hos-cron:1158-1162`.
  - `complete` gains no clause. Unreadable records reach it only through `unevaluated`.
  - Exit 3 remains exactly `complete=no ∧ ¬eligible`.
  - D2b adds no exit-2 path.
  - "All excluded" gives `complete=yes` and exit 0, which is a true statement: nothing is actionable.
  - Exit 0 with `complete=no` (T-NB5) is the AM-31 quarantine precedent, and hos-cron already treats rc 0
    as usable.
  - The invariant tests' `k=v` field parser tolerates every new token. Each has a single `=`, and the
    `issue=` tokens are filtered.
- **One correctness defect, fixed by edit.** In DRAFT-1, R3's page-bound case exited 1, which is
  "transient, retry unchanged". That is a permanent condition, so the caller would retry forever. It is now
  exit 6, `supersede-undeterminable`, and fails toward not re-applying (T-ESC23).

---

## Human Review Required

**RISK: MEDIUM.** This changes the protected work selector that every worker cycle runs, and it adds a
protected-surface write script. The failure direction is bounded. Every new selector rule only
**removes** records from consideration or marks them unknown. No path makes a previously excluded or
gated record selectable, and no new request, trust input or exit-2 path is added. The worst selector
failure is therefore **over-exclusion or a DEGRADED stall** (OQ-2(a)), never unreviewed work being
selected. The script's worst failures are a duplicate comment, or an exit-5 window in which a recorded
question lacks its label. Both are loud.

**CONFIDENCE: HIGH** on the zero-cost claim and the placement after D1, both re-probed live on the
selector's exact endpoint (P1, P2). **HIGH** on the exit-code interplay, which is derived from the
unchanged `_report_and_exit` and `bin/hos-cron:1158-1162`. **MEDIUM** on the `blocked_by` open/closed
semantics. They are unprobeable without an edge, but the predicate is built so that safety does not
depend on them (TD-F3, T-NB10). **MEDIUM** on the reactions/`updated_at` gap, which is designed to fail
toward a duplicate comment.

**BLAST RADIUS:**
- `select_work_candidates.py` (every worker cycle, both call sites);
- `bootstrap/escalate_to_human.sh` (new);
- `worker-cron-prompt.md`, `docs/LABELS.md`, `CLAUDE.md` (one paragraph or row each);
- fixture helpers in two test modules.

**Change classification: `additive`.** It adds exclusion rules and a new write primitive inside the ADR's
already-approved structure. There is no new decision authority, no new state carrier beyond `needs-human`
(which already exists), and no trust-boundary change. The structural decision is ADR-1644's, which is
already human-ruled. No structural escalation to a human is required before writing. The PR itself
passes the CODEOWNERS human gate as protected surface.

**Architect review is required before `coder` handoff** (iteration 1 of 5).
