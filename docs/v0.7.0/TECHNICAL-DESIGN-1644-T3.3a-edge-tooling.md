# TECHNICAL DESIGN — #1644 slice T3.3a: edge tooling (canonical scripts for sub-issue links and `blocked_by` dependency edges; the #1352 pull-forward)

**Status:** DRAFT-1 + architect round-1 and round-2 edits. **Architect round 1 of 5: APPROVED_WITH_EDITS;
round 2 of 5 (independent re-review after commit adoption): APPROVED_WITH_EDITS** (see the final sections). Cleared for `coder` handoff with the edits applied. The V-LIVE authorization (§9) is
not a handoff blocker.
**Date:** 2026-10-01
**Author:** technical-design
**Baseline:** `origin/main` = `HEAD` = **`109985cb06520efd86368ae12a7f2cdf82dfcaae`** (the merge of PR
#1918, T3.0a). Every file:line below is that commit's blob. Live GitHub probes were run at
2026-10-01T05:07–05:12Z. They were **read-only** (GET only) against `thurlow-research/HumanOversightSystem`
(§0.2). Write-endpoint contracts come from GitHub's published OpenAPI description, which was itself
fetched with a read-only GET (§0.3).
**Binding inputs:**
- `docs/v0.7.0/ADR-1644-stage-per-cycle.md`: **AD-C14** (`:638-672`, especially the "Tooling" bullet,
  `:664-670`), §5's T3.3a row (`:901`, "Depends on: nothing"), §8 (`:1004`, the remainder of #1352 is a
  non-goal), and §0 "Verification gaps" (`:165-178`). This is the controlling document. Nothing here
  re-litigates it.
- Issue **#1352** (the source requirement, read live with `query_issues.sh --issue 1352 --full`). Its
  open question ("broader relationship types?") is answered by AD-C14: sub-issues **plus** `blocked_by`
  dependencies, and **nothing else** (no issue types, no "duplicate of", no "related to", no
  sub-issue reprioritization).
- `docs/v0.7.0/TECHNICAL-DESIGN-1644-T3.0a-no-idle-selection.md` (the preceding slice). It supplies the
  sibling-script pattern of `escalate_to_human.sh` (§4 there) and the selector's native-edge exclusions,
  which these edges feed (§2 there).

**Scope (the ADR's, and nothing more):**
- add, remove and list a **sub-issue link**;
- add, remove and list a **`blocked_by` edge**;
- callers pass issue **numbers**, and the script resolves each to GitHub's internal `id`;
- `--app`-scoped, with the `--body-file` family convention (no inline free text), and **no hand-rolled
  `gh api` at any call site**.

**Explicitly out of scope:**
- the paid edge-satisfaction check, cycle walk, dangling-edge handling, and the edge ⊇ tracking-block
  check (**T3.3**);
- the tracking block itself and its format (ADR-1604 AD-8/AD-10; T3.7a/T3.8);
- decomposition-time acyclicity validation (AD-C14 "before any write"; T3.7a/T3.8);
- re-parenting (`replace_parent`), sub-issue reprioritization (`PATCH …/sub_issues/priority`), issue
  types, and every other relationship kind: the rest of #1352, v0.7.4 (ADR §8);
- Python (`scripts/automation/lib/github.py`) readers for these endpoints (§11 OQ-4);
- wiring into `bin/hos-cron`, `worker-cron-prompt.md`, or any executor (T3.7a is the first caller).

This document says *what the code must do*. It contains no application code.

---

## 0. Verification, re-derived against `109985cb` and live GitHub

### 0.1 Search for existing helpers (CLAUDE.md "Search first", required)

I searched `scripts/` (recursively), `bootstrap/`, `bin/` and `scripts/automation/lib/`.

| Looked for | Found | Consequence |
|---|---|---|
| Any reader or writer of `sub_issue`, `sub_issues`, `parent_issue`, `/parent`, `dependencies`, `blocked_by` | **Only** `scripts/framework/select_work_candidates.py`'s T3.0a predicate, which reads the two **summary counters** from the list record (`_dependency_counts`, `_sub_issue_total`). There are no endpoint calls anywhere. | Confirms #1352's "no hits", updated for T3.0a. Nothing to reuse, and nothing to conflict with. The selector's T-ZC4 static test forbids `/dependencies`, `/sub_issues` and `parent_issue` in the selector itself, so **nothing in this slice may be added there**. |
| An issue-edit write wrapper | `bootstrap/edit_issue.sh` (labels, milestone, title, state, assignees, body; exit 1 on every failure; `--remove-label` failures **warn and exit 0**, `:200-207`) | Pattern source (mint, revoke, slug resolution). **Not extended for writes** (§2). |
| A read wrapper | `bootstrap/query_issues.sh` (seven read modes; exactly-one-mode guard `:109-117`; each mode fetches **page 1 only**, `per_page=100`, with no further pages) | **Extended** with four read modes (§4). |
| The newest sibling write primitive | `bootstrap/escalate_to_human.sh` (exit codes 0/1/2/4/5/6; validation before mint; one mint; EXIT-trap revoke; `jq`-built JSON through `--input -`; best-effort audit) | **The pattern this slice copies** for the write script (§3). |
| A Python GitHub layer | `scripts/automation/lib/github.py::_run_gh` (`gh api --include`, status-line parse, retry on 5xx/429/403-RL) | Its status-line parse is the precedent for §3.5's HTTP classification. Nothing is added to it (OQ-4). |
| A PATH-level `gh` double for a bootstrap script | `tests/automation/test_edit_issue.py` (bash `GH_STUB`), `tests/automation/test_query_issues.py`, `tests/automation/test_escalate_to_human.py` (Python `GH_STUB` that logs `METHOD PATH` and captures stdin) | Test harness pattern for §8. |
| An open issue for the repeated-flag overwrite defect | None found in the 100 most recent issues (`query_issues.sh --search`). The defect is recorded only in operator memory. | **TD-E7.** Not fixed here. The new flags reject repeats instead (§3.2, §4.2). Reported in §11 OQ-5. |

### 0.2 Live probes (read-only GET; nothing was written)

The probes used `gh api` with the session's ambient `GH_TOKEN`, against `thurlow-research/HumanOversightSystem`.

| # | Request | Result | Status |
|---|---|---|---|
| **P1** | `GET repos/…/issues/1644/sub_issues?per_page=100` | `200`, `[]`. `X-Accepted-Github-Permissions: issues=read`. `X-Github-Api-Version-Selected: 2022-11-28`. | **Confirmed**: endpoint live, empty list for a non-parent |
| **P2** | `GET repos/…/issues/1644/dependencies/blocked_by?per_page=100` | `200`, `[]`. `issues=read`. | **Confirmed**: the dependencies API is enabled on this repo |
| **P3** | `GET repos/…/issues/1644/dependencies/blocking?per_page=100` | `200`, `[]`. | **Confirmed** |
| **P4** | `GET repos/…/issues/1644/parent` (not a child) and `GET repos/…/issues/999999/parent` (no such issue) | **Both `404`.** The messages differ: `"No parent issue found"` vs `"Not Found"`. | **Confirmed. The status alone is ambiguous** (TD-E2) |
| **P5** | `GET …/issues/999999/sub_issues` and `GET …/issues/999999/dependencies/blocked_by` | `404 "Not Found"` | **Confirmed** |
| **P6** | `GET …/issues/1349/sub_issues` | One record: #1351, `id = 5144957276`, `node_id = "I_kwDOS4BZNs8AAAABMqnRXA"`, `parent_issue_url = …/issues/1349`. The record carries both summaries and `repository_url`. | **Confirmed.** #1352's own hand-rolled 2026-08-13 call was `POST …/issues/1349/sub_issues -F sub_issue_id=5144957276`. **That is #1351's `.id`.** This is historical write evidence that the API takes `.id`, not `number` and not `node_id` (TD-E5) |
| **P7** | `GET …/issues/1351` (a child) and `GET …/issues/1349` (a parent, not a child) | The child record **has** the key `parent_issue_url` = `…/repos/thurlow-research/HumanOversightSystem/issues/1349`. On the non-child, **the key is absent** (`has("parent_issue_url") == false`), not `null`. | **Confirmed** (TD-E3) |
| **P8** | `GET …/issues/1351/parent` | `200`: the full issue record of #1349 (`number`, `id`, `state`, `repository_url`, …). That record's own `parent_issue_url` is `null`. | **Confirmed** |
| **P9** | List endpoint `GET …/issues?state=closed&labels=documentation,process-gap,priority:high&per_page=100` | Three records. #1351 **carries** `parent_issue_url`. #1400 and #1359 do **not** carry the key. | **Confirmed. This closes ADR §0 gap 1** (§0.5) |
| **P10** | A full scan of `GET …/issues?state=all&per_page=100&page=1..25`, issues only | **Zero dependency edges in the repo** (every `total_blocked_by` and `total_blocking` is 0). Sub-issue links: **#1349 → #1351** (closed), and **#1358 → #1350, #1356, #1357**. #1358 is open, with `sub_issues_summary.total = 3`. | **Confirmed** (TD-E4) |
| **P11** | `GET …/issues/1358/events?per_page=100` and `GET …/issues/1356/events?per_page=100` | On the parent: three `sub_issue_added` events, `actor = scottthurlow-claude[bot]`. The payload carries `sub_issue.number` and `sub_issue.repository.full_name`. On the child: `parent_issue_added`, with the same actor. | **Confirmed for adds.** Removal and dependency event names are **unconfirmed**, because no instance exists (§0.5, V-LIVE) |
| **P12** | gh CLI behaviour: `gh api --include …/issues/1644/parent` | Exit **1**. **stdout** carries `HTTP/2.0 404 Not Found`, then the headers, a blank line, and the JSON body. **stderr** carries `gh: No parent issue found (HTTP 404)`. | **Confirmed.** The status line is reliably on stdout, even on error. That is the basis of §3.5 |

### 0.3 Write-endpoint contracts (documented; **not** live-confirmable read-only)

The source is `github/rest-api-description`, `descriptions/api.github.com/api.github.com.json`, fetched
2026-10-01 by a read-only GET. These shapes are **documented, not observed**. The design is built so
that its **correctness does not depend on them** (§3.4 read-back), and §9 binds a live verification.

| Operation | Method and path | Body | Documented responses |
|---|---|---|---|
| Add sub-issue | `POST /repos/{o}/{r}/issues/{PARENT}/sub_issues` | `{"sub_issue_id": <child .id>}` (int, required). Optional `replace_parent` (bool), which is **never sent** (§3.3). The sub-issue "must belong to the same repository owner as the parent". | 201, 403, 404, 410, 422 |
| Remove sub-issue | `DELETE /repos/{o}/{r}/issues/{PARENT}/sub_issue` (**singular**) | `{"sub_issue_id": <child .id>}` (int, required): **a DELETE with a body** | 200, 400, 403, 404 |
| Add `blocked_by` | `POST /repos/{o}/{r}/issues/{BLOCKED}/dependencies/blocked_by` | `{"issue_id": <blocker .id>}` (int, required): "The id of the issue that blocks the current issue" | 201, 301, 403, 404, 410, 422 |
| Remove `blocked_by` | `DELETE /repos/{o}/{r}/issues/{BLOCKED}/dependencies/blocked_by/{issue_id}` | none. The blocker's **internal id is in the path**. | 200, 301, 400, 401, 403, 404, 410 |
| Get parent | `GET /repos/{o}/{r}/issues/{CHILD}/parent` | — | 200, 301, 404, 410 |
| List sub-issues / blocked_by / blocking | `GET …/sub_issues`, `GET …/dependencies/blocked_by`, `GET …/dependencies/blocking` | — | 200 (array of issue), 301, 404, 410 |

**Answer to "does the dependencies API also take an internal id?" Yes, both directions.** POST takes the
blocker's `.id` in the body (`issue_id`). DELETE takes it **in the path**. The issue being blocked is
addressed by **number** in the path, as the sub-issue parent is.

**Unconfirmed (U-n). Each is bound to V-LIVE (§9), and none affects correctness:**
- **U1.** The status of a duplicate `POST …/sub_issues` (same child, same parent), and of a POST for a
  child that already has a different parent without `replace_parent` (expected `422`).
- **U2.** The status of `DELETE …/sub_issue` for a non-child (`400` or `404`?).
- **U3.** The status of a duplicate `POST …/blocked_by`, and of `DELETE …/blocked_by/{id}` for an absent
  edge.
- **U4.** The status of a self-reference (`issue_id` = own id; `sub_issue_id` = parent's own id).
- **U5.** Whether GitHub rejects a dependency **cycle** (A blocked_by B while B is blocked_by A), and the
  hierarchy limits (depth and children per parent).
- **U6.** That the App installation's `issues: write` permission covers these writes (the GETs advertise
  `issues=read`).
- **U7.** The event names and actor fields for `sub_issue_removed`/`parent_issue_removed` and for
  dependency add/remove (ADR §0 gap 2).
- **U8.** That `gh api --method DELETE --input -` sends the body on DELETE. `gh api`'s `--input` is
  documented as method-agnostic, but this was not observed.

### 0.4 Findings that shape this design

- **TD-E1 (HIGH, interface).** **The four writes have four different shapes.** Sub-issue writes go on
  the **parent's** path and carry the **child's** id in the body (the DELETE path is the singular
  `sub_issue`, with a body). Dependency writes go on the **blocked** issue's path and carry the
  **blocker's** id, in the body for POST and in the path for DELETE. Every one needs a number→id
  resolution first. That is exactly the "multi-step, runtime-valued logic" CLAUDE.md says belongs in
  one committed script, and it is why no caller may ever hand-roll it.
- **TD-E2 (MEDIUM, correctness).** **`GET …/parent` returns 404 both for "no parent" and for "no such
  issue"** (P4). Telling them apart by the message text would be brittle. **The design never uses
  `/parent` to decide existence.** It reads `parent_issue_url` from the issue record (P7). It calls
  `/parent` only for display, after the record has proved that a parent exists (§4.3).
- **TD-E3 (MEDIUM, parsing).** On a non-child, `parent_issue_url` is **absent** from the issue and list
  records, and it is `null` inside `/parent`'s own record (P7, P8). Both scripts treat **absent and
  `null` identically** as "no parent". Any other non-string value is "undeterminable" (§3.4).
- **TD-E4 (INFO, blast radius).** The live graph has **0 dependency edges** and **4 sub-issue links**
  (P10). Every write this slice enables is therefore new state. T3.3a does not change any existing
  edge's meaning. #1358 (open, 3 children) is already reported as `untracked-parent` by T3.0a when it
  appears in a `needs-ai` candidate list. T3.3a does not touch that.
- **TD-E5 (HIGH, confirmed).** `.id` (not `number`, not `node_id`) is the value the sub-issue API
  accepts. #1352's successful 2026-08-13 write used `5144957276`, which P6 shows is #1351's `.id`. For
  the dependencies API, `.id` is **documented** (§0.3) and live-unconfirmed (V-LIVE).
- **TD-E6 (MEDIUM, existing gap; not fixed here).** The existing `query_issues.sh` modes `--list`,
  `--search`, `--comments`, `--comments-json` and `--assignable-users` fetch **page 1 only** and print
  it, so they **silently truncate at 100**. An edge list read for T3.3's ⊇ check must never be
  truncated silently, so **the new modes paginate and fail closed** (§4.4). The old modes are left
  alone, and §11 OQ-5 reports the gap.
- **TD-E7 (MEDIUM, existing gap; not fixed here).** In `edit_issue.sh` (`:77-84`), `query_issues.sh`
  (`:86-98`) and `create_issue.sh`, **a repeated flag silently keeps only its last value**
  (`VAR="$2"`). An edge tool with that behaviour would mutate a different edge from the one the caller
  believes it named. **Every flag this slice adds rejects a second occurrence** (exit 2 or exit 1, per
  script). Existing flags are unchanged, and §11 OQ-5 reports the gap.

### 0.5 The ADR §0 gaps, as they touch T3.3a

| ADR §0 gap | Touches T3.3a? | Disposition |
|---|---|---|
| How a child resolves its parent, and whether `parent_issue_url` is on the list record | **Yes.** `--add-parent`/`--remove-parent` idempotency and `--parent-of` need it. | **Closed.** `parent_issue_url` is on the **single-issue record (P7) and the list record (P9)** of a child, and absent on a non-child. `GET …/{child}/parent` returns the full parent record (P8). A cross-repo parent is recognisable from the URL's `/repos/<owner>/<repo>/` segment. **This also unblocks AD-C16/T3.8a's question.** |
| Timeline event types, and actors, for edge add/remove | **Partly.** T3.3a does not read events. AD-C14's asymmetry stays the safety basis. | **Partly closed** (P11): `sub_issue_added` on the parent and `parent_issue_added` on the child both appear on `/events` with an `actor`. **Removal and all dependency events remain unconfirmed** (U7). V-LIVE (§9) is bound to record them for T3.3. |
| Whether a reaction moves `updated_at` | No | — |
| A5 on plan-stage `Write` | No | T3.7a. |
| No behaviour was run under `bin/hos-cron` | No | T3.3a is not wired into the launcher. |

---

## 1. Files (≤15; this is one code PR)

This TD lands first in its own PR, as T3.0a's did (#1916 then #1918). The code PR is:

| # | Path | Change | Surface |
|---|---|---|---|
| 1 | `bootstrap/edit_issue_edges.sh` | **New.** The edge write primitive (§3). | **protected** (`bootstrap/**`) |
| 2 | `bootstrap/query_issues.sh` | **Modify.** Four new read modes (§4). Header usage block updated. | **protected** |
| 3 | `bootstrap/edit_issue.sh` | **Modify.** One redirect arm in the argument parser, plus two header lines (§5). No behaviour change for any existing flag. | **protected** |
| 4 | `tests/automation/test_edit_issue_edges.py` | **New.** T-EW1 to T-EW24 (§8.1). | — |
| 5 | `tests/automation/test_query_issues_edges.py` | **New.** T-EQ1 to T-EQ11 (§8.2). This is a separate file so that the existing `test_query_issues.py` stub stays untouched. | — |
| 6 | `tests/automation/test_edit_issue.py` | **Modify.** One test, T-ER1 (§8.3). | — |
| 7 | `CLAUDE.md` | **Modify.** One row in "Canonical entry points by task", and one sentence extending the reads prose (§7). | **protected** |
| 8 | `SCRIPTS-INDEX.md` | **Regenerate** with `scripts/framework/gen_scripts_index.sh` (via `scripts/framework/regen_all.sh`). No hand edits. | — |

That is eight files. Before the PR:
- `scripts/framework/regen_all.sh --check` must be clean.
- CODEOWNERS already covers `/bootstrap/` (`.github/CODEOWNERS:22`), so no CODEOWNERS change is
  expected. If `--check` disagrees, regenerate; never hand-edit.
- Run the gates **scoped to the changed files**, never unscoped:
  `scripts/oversight/run_gates.sh <files>` and `scripts/oversight/run_validators.sh <files>`.
- `shell_logic_check.py` will score the new script's decision density. A HIGH floor there is expected
  and is not a defect.

**Not touched:**
- `scripts/framework/select_work_candidates.py`: T3.0a's static T-ZC4 forbids these endpoints there.
  The selector keeps reading only the free summaries.
- `scripts/automation/lib/github.py`: OQ-4.
- `bootstrap/worker-cron-prompt.md`: no autonomous caller exists until T3.7a, and the removal flags
  should not be advertised to the autonomous worker before T3.3 (§6.3).
- `.claude/agents/worker.md` (`:126`, `:128`) and `.claude/agents/overseer.md` (`:723`): their GitHub-ops
  tables would gain rows. That is an agent-definition edit, which the top-level session must author
  (#1347), never `coder`. **Deferred to T3.7a** (OQ-5(c)).
- `scripts/framework/framework_consumer_files.txt`: the new script ships exactly as its siblings
  `edit_issue.sh`, `query_issues.sh`, `post_comment.sh` and `escalate_to_human.sh` do. **None of them
  is listed.** This is the pre-existing family-wide gap the architect recorded at T3.0a OQ-3(c). It is
  not T3.3a's to fix.
- `contract/dimensions/postures/review-read-only-gh-read.*`: unchanged, but **affected**. See §4.6.

---

## 2. Interface decision: writes in a new sibling, reads in `query_issues.sh`

AD-C14 allows either form ("extends `edit_issue.sh` / `query_issues.sh` or is a sibling of them").
#1352 preferred extending `edit_issue.sh` for writes. **This design extends `query_issues.sh` for reads,
and puts writes in a new sibling, `bootstrap/edit_issue_edges.sh`.**

### 2.1 Why the writes are a sibling

1. **The exit contract.** `edit_issue.sh` exits **1 for every failure**, usage errors included
   (`err`, `:59`). On `--remove-label` failure it **warns and exits 0** (`:204-205`). An edge write
   needs callers to tell four outcomes apart:
   - "the requested state holds" (0);
   - "transient, retry unchanged" (1);
   - "refused, fix the input" (2);
   - "the live graph contradicts you, do not retry" (6).

   T3.7a's reconcile re-runs (AD-C3.1) depend on exactly that split. Grafting a second exit contract
   onto one script, selected by which flags were passed, would make every caller's `$?` reading
   mode-dependent. Changing `edit_issue.sh`'s existing contract would break its 28 tests and every
   prose caller. **D41 item 1 (honest degradation)** rules out inheriting "warn and exit 0" for an edge
   removal.
2. **One operation per invocation.** Every edge write needs pre-reads (number→id, idempotency) and a
   read-back (§3.4). `edit_issue.sh` already issues up to four independent writes per call (PATCH,
   labels POST, label DELETEs, assignees POST) with no partial-state report. Adding edge writes to
   that sequence would create an unreportable partial state: "labels applied, edge not". The sibling
   does **exactly one edge mutation per invocation**, so its exit code describes exactly one edge.
3. **D41 item 3 (one invocation site) is satisfied, not strained.** D41 means one site *per operation*.
   After this slice:
   - each of the four edge mutations has exactly one invocation site, the sibling;
   - each of the four edge reads has exactly one site, `query_issues.sh`;
   - no `gh api` for these endpoints exists anywhere else.

   `edit_issue.sh`'s redirect arm (§5) points #1352's spelling (`--parent`) at the sibling, so a caller
   who reaches for the old script is told where the operation lives instead of getting a generic
   usage error.
4. **The allowlist cost is one rule.** The autonomous roles run `--permission-mode bypassPermissions`
   (`bin/hos-cron:1849`), so there is no cost there. Interactive sessions get one prompt that has
   "Always allow", for a literal-path command (CLAUDE.md "What breaks allowlisting": nothing here is
   runtime-composed).

### 2.2 Why the reads go in `query_issues.sh`, and why the writes must not

- CLAUDE.md already names `query_issues.sh` as the single read surface ("Reads … go through
  `bootstrap/query_issues.sh` … never hand-rolled `gh api` reads").
- **`query_issues.sh` is granted to read-only reviewer sessions** by the
  `review-read-only-gh-read` posture (`contract/dimensions/postures/review-read-only-gh-read.settings.json:11`:
  `Bash(bootstrap/query_issues.sh *)`). Putting edge **writes** there would silently hand every
  read-only reviewer a path that can **unblock work** (§6). This is the decisive reason the write/read
  split follows the script boundary. T-EQ11 pins `query_issues.sh` as write-free.

### 2.3 Repeated flags: a single value, a single occurrence, and a hard error

- Every new flag takes **exactly one issue number**. Commas, `#`, `/`, URLs and leading zeros are
  rejected (`^[1-9][0-9]*$`).
- A flag given twice is a **usage error**, never last-wins (TD-E7). This applies to every flag of
  `edit_issue_edges.sh`, including `--number` and `--app`, and to the four new `query_issues.sh` modes.
- **Multiple edges mean multiple invocations.** That is deliberate. The cost is one Bash call per
  edge. The benefit is that each call's exit code and stdout line name one edge. A caller that loops
  (T3.7a's executor) does so inside committed code, which is allowed.

---

## 3. `bootstrap/edit_issue_edges.sh`, the write primitive

### 3.1 Purpose and boundary

The script makes **one** native edge between two issues **in this repository** exist or not exist, and it
**verifies** the result. It does not decide whether an edge *should* exist. That is the tracking block's
job (AD-C14 "authority"), and it belongs to T3.7a/T3.8.

**What it must not do:**
- re-parent: it never sends `replace_parent`, so a child with a different parent is a conflict (§3.4);
- reorder sub-issues;
- validate acyclicity (AD-C14 puts that at decomposition time and in T3.3's pre-check walk);
- read or write a tracking block;
- touch labels, `stage:*`, milestones or comments;
- operate on a pull request;
- accept a reference to another repository.

### 3.2 CLI (exact)

```
bash bootstrap/edit_issue_edges.sh --number <N> --app <worker|overseer|human> \
  ( --add-parent <P> | --remove-parent <P> | --add-blocked-by <B> | --remove-blocked-by <B> )
```

| Flag | Required | Meaning / rule |
|---|---|---|
| `--number <N>` | yes | **The subject issue.** For the parent flags it is the **child**. For the blocked-by flags it is the **blocked** issue. `^[1-9][0-9]*$`. |
| `--app` | yes | `worker`, `overseer` or `human`, the same set as every sibling. (The unauthenticated-`--app` residual is #1819's, open and `needs-human`. This script neither widens nor narrows it.) |
| `--add-parent <P>` | one op | Make N a sub-issue of P. |
| `--remove-parent <P>` | one op | Detach N from P. **P must be named.** The script never removes "whatever parent N has". |
| `--add-blocked-by <B>` | one op | Record that N is blocked by B. |
| `--remove-blocked-by <B>` | one op | Remove the edge "N is blocked by B". |
| `--body`, `--body-file` | — | **Rejected**, exit 2: `--body/--body-file are not applicable — this script takes no free text`. The family's `--body-file` convention is honoured vacuously: there is no free-text input, and every JSON body is `jq`-built and piped through `--input -`. |
| anything else | — | Usage error, exit 2. |

**Validation runs before any mint. Every failure exits 2, with zero `gh` calls:**
- a flag missing its value;
- **any flag given twice** (`usage: <flag> given more than once`);
- zero, or more than one, operation flag (`usage: exactly one of --add-parent, --remove-parent, --add-blocked-by, --remove-blocked-by is required`);
- a value not matching `^[1-9][0-9]*$`. If the value contains `/` or `#`, the token is
  `qualified-reference-unsupported` and the message says that only this repository's issue numbers are
  accepted (the cross-repo answer, §3.6);
- `N == <other>`, which gives token `self-reference`;
- a bad or missing `--app`.

**Why the parent flags are subject-centric (`--number <child> --add-parent <P>`)** rather than
`--number <parent> --add-sub-issue <C>`:
- GitHub allows **one** parent per child. So the child is the side where a conflict ("already has a
  different parent") is decidable from one record (P7).
- It matches #1352's `--parent <N>` reading ("make this issue a sub-issue of N").
- One direction per edge kind keeps the flag set to four.

Reads cover both directions (§4).

### 3.3 Environment and pattern (copied from `escalate_to_human.sh`)

- `set -euo pipefail`. `SCRIPT_DIR`, `err` and `warn` are as in the siblings. **Every exit-2 path goes
  through a `refuse` helper** (the `escalate_to_human.sh:62-66` precedent), never `err`, because the
  siblings' `err` exits 1. *(Architect round 2, edit B2.)*
- The repo slug comes from `git -C "$SCRIPT_DIR/.." remote get-url origin`, with the siblings' `sed`.
  A failure exits 1, as in the siblings.
- **One mint:** `bash "$SCRIPT_DIR/get_app_token.sh" --app <role>` into a `mktemp` file, which is
  sourced and then deleted at once (#549).
  - A mint failure exits 1 with token `mint-failed`.
  - Revocation goes in an **EXIT trap** that runs on every post-mint exit, guarded by a `MINTED` flag.
    `curl` gets `--connect-timeout 10 --max-time 30`. A revoke failure only warns.
  - `HOS_BOT_LOGIN` is **not required**: there is no authorship check. It is recorded in the audit event
    as the actor, or as `"unknown"` when it is empty.
- **Every GitHub call is one `gh api --include --method <M> <path>` invocation, through one helper**
  (§3.5). Never `--paginate`, never `-f`/`-F`/`--field`/`--raw-field`, never `--jq`, never
  `gh issue …`. Bodies are `jq -nc --argjson …` piped to `--input -`.
- **`replace_parent` never appears in the script** (T-EW21).
- Tools: `gh`, `git`, `jq`, `curl`.

### 3.4 Ordered procedure: resolve, decide, write once, read back, audit

**Reads (R). Nothing has been written yet.** Each read is classified by §3.5. "Transient" means exit 1.

- **R1. `GET repos/<slug>/issues/<N>`.**
  - `not-found` (404/410): exit 2, `issue-not-found issue=#N`.
  - `rejected` (403 that is not a rate limit, other 4xx): exit 2, `read-rejected issue=#N http=<s>`.
  - The body is not a JSON object, or `.id` is not a positive integer JSON number: exit 1,
    `read-malformed issue=#N`.
  - `.number != N`, or `.repository_url` (lower-cased) does not end with `/repos/<slug lower-cased>`:
    exit 2, `issue-moved issue=#N`. This covers a transferred issue whose redirect `gh` followed.
  - `has("pull_request")`: exit 2, `target-is-pull-request issue=#N`.
  - Capture `ID_N` and `PARENT_URL_N` (`.parent_issue_url`; absent and `null` both become empty;
    TD-E3). Any other type is recorded as `undeterminable`.
- **R2. `GET repos/<slug>/issues/<M>`** for the other endpoint (P or B). The checks are identical, with
  `issue=#M`. Capture `ID_M`. R2 runs only if R1 passed.
- **R3. The blocked-by flags only.** Page through
  `GET repos/<slug>/issues/<N>/dependencies/blocked_by?per_page=100&page=<p>` for `p = 1..10`. Stop at
  the first page with fewer than 100 items. Collect every element's `.id`.
  - A non-array body exits 1, `read-malformed`.
  - `not-found` (404/410) here exits **6**, `edges-undeterminable issue=#N http=<s>`. N existed at R1, so
    a 404 here is far more likely to be permanent (the dependencies feature unavailable on this host or
    repo, e.g. an older GHES consumer) than a deletion race. Exit 1 would invite unbounded identical
    retries. A genuine race lands on 6 harmlessly. *(Architect round 1, edit A1.)*
  - **Ten full pages without a short page:** exit **6**, `edges-undeterminable issue=#N`. A page bound is
    permanent, not transient. This is the `escalate_to_human.sh` R3 lesson (T3.0a architect correction).

**Decision.**

| Op | Live state (from R1/R3) | Action | Outcome / exit |
|---|---|---|---|
| `--add-parent P` | `PARENT_URL_N` empty | **W** = `POST issues/<P>/sub_issues` with `{"sub_issue_id": ID_N}` | → V |
| | parses to (this slug, P) | none | `already-present`, **exit 0** |
| | parses to any other (slug, number), cross-repo included | none | **exit 6**, `has-other-parent current=<ref>` |
| | unparseable / undeterminable | none | **exit 6**, `parent-undeterminable` |
| `--remove-parent P` | empty | none | `already-absent`, **exit 0** |
| | (this slug, P) | **W** = `DELETE issues/<P>/sub_issue` with `{"sub_issue_id": ID_N}` | → V |
| | any other parent | none | **exit 6**, `parent-mismatch current=<ref>`. **It never removes a link it was not told about.** |
| | unparseable / undeterminable | none | **exit 6**, `parent-undeterminable` |
| `--add-blocked-by B` | `ID_M ∈ ids` | none | `already-present`, **exit 0** |
| | `ID_M ∉ ids` | **W** = `POST issues/<N>/dependencies/blocked_by` with `{"issue_id": ID_M}` | → V |
| `--remove-blocked-by B` | `ID_M ∉ ids` | none | `already-absent`, **exit 0** |
| | `ID_M ∈ ids` | **W** = `DELETE issues/<N>/dependencies/blocked_by/<ID_M>`, no body | → V |

**Parsing `parent_issue_url`.** It must match `/repos/([^/]+)/([^/]+)/issues/([1-9][0-9]*)$`. The match is
host-agnostic, so a GHES `/api/v3` prefix still parses. The owner and repo are compared to the slug
case-insensitively. `<ref>` is `#<n>` when the repo is this one, and `<owner>/<repo>#<n>` otherwise.

**Membership in R3** is decided by **`.id` equality only**, never by number. Ids are unique across
repositories, so a cross-repo blocker with the same number can never be mistaken for B.

**State is not a refusal criterion.** A closed N, P or B is accepted. An edge to a closed blocker is
legitimate, and T3.0a already treats it as `blocker-closed-unverified` (exclusion) until T3.3 (T-EW24).

**W: exactly one mutation request.** Its HTTP class (§3.5) is recorded as `W_CLASS` and `W_STATUS`.
**No retry inside the script.** That matches the siblings, and `github.py` uses `retries=0` for
non-idempotent writes.

**V: read-back, always performed after W, whatever W's status was.** "Never assume the write took" is
the `edit_issue.sh` precedent. V performs the R1 read of N (parent flags) or the R3 walk (blocked-by
flags) again. V's result decides the exit. W's status only selects the failure token. **Rows are
evaluated top to bottom and the first matching row wins** (rows 3 to 6 overlap: an `--add-parent` whose
W was rejected *and* whose V shows a different parent is row 3, exit 6, per T-EW20). *(Architect round 1,
edit A2.)*

| V result | Exit | Token / outcome |
|---|---|---|
| V read failed: **any** non-`ok` class (transient, `not-found`, `rejected`), a malformed body, the page bound, or (parent flags) a `parent_issue_url` that is neither absent/`null` nor a parseable URL *(round 2, edit B1)* | **4** | `unverified verify-read-failed http=<W_STATUS>` |
| The requested state holds | **0** | `added` / `removed`. This covers both W 2xx and a W failure where the state landed anyway (a lost response, or a concurrent identical write). |
| `--add-parent` and V shows a **different** parent | **6** | `has-other-parent current=<ref>` (a race with another actor) |
| The state does not hold, and `W_CLASS` ∈ {`rejected`, `not-found`} | **2** | `write-rejected http=<W_STATUS> message=<sanitized>` |
| The state does not hold, and `W_CLASS` = `transient` | **4** | `write-failed http=<W_STATUS or none>` |
| The state does not hold, and `W_CLASS` = `ok` (2xx) | **4** | `unverified http=<W_STATUS>` (possible read-after-write lag) |

`<sanitized>` is GitHub's `.message` from W's body: characters outside printable ASCII `0x20–0x7E` are
removed, and the result is capped at 200 characters. An absent message gives `-`. **No title or other
issue content is ever printed** (the R-1 rule of TD-1540).

**Why read-back makes the unconfirmed write statuses (U1 to U4) irrelevant to correctness.** The exit
code reports the **observed** final state. Whatever status GitHub returns for a duplicate, an absent
edge or a self-reference, the script either observes the requested state (0) or reports the HTTP class
honestly (2 or 4). V-LIVE only refines which **token** a given rejection produces.

**Audit (best-effort).** It runs only on paths where **W was attempted**: exit 0 with `added`/`removed`,
exit 2 `write-rejected`, exit 4, and exit 6 after W. No event is written for no-ops or pre-write exits,
because nothing happened.

### 3.5 HTTP classification (one helper, `gh_req`)

`gh_req <METHOD> <path> [<json>]` runs `gh api --include --method <METHOD> <path>`, adding `--input -`
fed with `<json>` when it is given. It captures stdout **without tripping `errexit`** (`… || true`).
P12 shows that `gh` exits 1 on any non-2xx status. It splits headers from body at the first blank line,
CRLF-aware (the `github.py:_run_gh` precedent), and parses the status from the first line,
`HTTP/<v> <code>`.

| Condition | Class | Pre-write read → | Write → (then V) |
|---|---|---|---|
| No status line (network, DNS, `gh` crash) | `transient` | exit 1 `read-failed` | V decides |
| `2xx` | `ok` | continue | V decides |
| `401` | `transient` (token race) | exit 1 | V decides |
| `403` with a `retry-after` header, or `x-ratelimit-remaining: 0` | `transient` (primary/secondary rate limit; the docs warn of secondary limits on these writes) | exit 1 | V decides |
| `429`, `5xx` | `transient` | exit 1 | V decides |
| `404`, `410` | `not-found` | exit 2 `issue-not-found` (R1/R2); exit 6 `edges-undeterminable` (R3; edit A1) | V decides |
| Any other `3xx`/`4xx` (`400`, `403` that is not a rate limit, `422`, `301` on a write) | `rejected` | exit 2 `read-rejected` | V decides |

Header names are matched case-insensitively.

### 3.6 Idempotency and error semantics: the cases the slice brief names

| Case | Behaviour | Exit |
|---|---|---|
| Add a link that already exists | R1 or R3 sees it, so there is no write | 0 `already-present` |
| Remove a link that is absent | R1 or R3 sees it absent, so there is no write | 0 `already-absent` |
| Child already has a **different** parent (GitHub allows one) | No write, and `replace_parent` is never sent. Re-parenting is two explicit invocations: remove from the old parent, then add to the new one. Each is audited. That is deliberate, because a removal can unblock the old parent (§6.1). | 6 `has-other-parent` |
| Remove-parent naming the wrong parent | No write | 6 `parent-mismatch` |
| **Cross-repo reference** | **Inexpressible at the interface.** Values are bare numbers, resolved against `origin`'s slug, and qualified forms are refused pre-mint. A pre-existing cross-repo parent (made in the UI) is reported as a conflict (6). A pre-existing cross-repo **blocker** cannot be named, so this tool cannot remove it. `--blockers-of` shows it qualified (§4.3), and T3.3 owns "unresolvable reference ⇒ fail-closed" (AD-C14). | 2 / 6 |
| **Self-reference** | Refused pre-mint, so GitHub's behaviour (U4) is never exercised | 2 `self-reference` |
| Either endpoint is a PR | Refused after R1/R2, before any write | 2 `target-is-pull-request` |
| Either endpoint does not exist | Refused at R1/R2 | 2 `issue-not-found` |
| A transferred or moved issue | Refused at R1/R2 | 2 `issue-moved` |
| A dependency cycle (A ← B ← A) | **Not checked here.** GitHub may or may not reject it (U5). If it does, the result is exit 2 `write-rejected`. If it does not, the edge lands, both issues stay excluded (fail-safe, over-exclusion), and T3.3's walk escalates. Acyclicity is decomposition-time and T3.3's (AD-C14). | 0 or 2 |
| Hierarchy limits (depth, children per parent) | GitHub rejects (U5), so the result is exit 2 `write-rejected http=422 message=…` | 2 |
| Two concurrent identical invocations | Both may write. One gets 2xx, the other likely `422`. V shows the state holds for both, so **both exit 0**. | 0 |

### 3.7 Exit codes and output

| Exit | Meaning | Writes made | Caller's correct response |
|---|---|---|---|
| 0 | The requested edge state holds and was observed (`added`, `removed`, `already-present`, `already-absent`) | 0 or 1 | Done. |
| 1 | Transient: mint, slug, or a pre-write read failed or was malformed | **none** | Retry later, unchanged. |
| 2 | Refused: usage, self-reference, qualified reference, not found, a PR, moved, `read-rejected`, or **`write-rejected`** (GitHub refused the write and V confirms it did not land) | none landed | Fix the input. Do not retry unchanged. |
| 4 | `write-failed` / `unverified`: a write was attempted and the requested state was **not** observed, or could not be read back | maybe | **Retry the identical command.** Pre-read idempotency makes a landed write a no-op on the re-run. |
| 6 | Conflict or undeterminable: `has-other-parent`, `parent-mismatch`, `parent-undeterminable`, `edges-undeterminable` (page bound, or R3 404/410 per edit A1). The live graph contradicts the request, or cannot be read completely. | none (or one that lost a race) | **Do not retry.** A human, or the tracking-block reconcile (T3.7a), must decide. |

**Exit codes 3 and 5 are deliberately unused.** 3 is avoided so that no reader confuses this script with
the selector's DEGRADED. There is no 5 because a single-write operation has no partial state.
`escalate_to_human.sh`'s 5 ("record landed, label did not") has no analogue here. Its 4 maps directly:
"retry the identical command".

**stdout** gets exactly one line, and only on exit 0:
- `edge kind=sub-issue op=<add|remove> parent=#<P> child=#<N> outcome=<added|removed|already-present|already-absent>`
- `edge kind=blocked-by op=<add|remove> issue=#<N> blocked_by=#<B> outcome=<…>`

**stderr** gets one line on every non-zero exit:
`edit_issue_edges: <token> kind=<sub-issue|blocked-by> op=<add|remove> issue=#<N> other=#<M> [<k=v> …]`.
It carries numbers and fixed tokens only. The `warn` helper's revoke and audit warnings may add lines.
Pre-mint usage refusals, where `issue`/`other` may not be valid numbers, use the form
`edit_issue_edges: usage: <message>` (or `edit_issue_edges: <token>: <message>` for `self-reference` and
`qualified-reference-unsupported`) and never echo the rejected value verbatim beyond printable ASCII.
*(Edit B2.)*

### 3.8 Audit event

The event goes through `scripts/oversight/lib/audit_log.sh::audit_write_event '<json>' "$SCRIPT_DIR/.."`,
in **exactly** `escalate_to_human.sh::audit_event`'s best-effort shape:
- a missing library or an undefined function is skipped with a warn;
- a failure warns;
- **the exit code never changes** because of the audit.

The JSON is built with `jq -nc --arg/--argjson`:

```
{"event":"issue-edge-changed",
 "kind":"sub-issue|blocked-by", "op":"add|remove",
 "issue":<N>, "other":<M>,
 "outcome":"added|removed|write-rejected|write-failed|unverified|has-other-parent",
 "http_status":<int or null>, "app":"<role>", "actor":"<HOS_BOT_LOGIN or unknown>",
 "timestamp":"<UTC ISO-8601 Z>"}
```

No decision reads this event (ADR-1643 AD-8, ADR-1644 AD-C19). It exists for **removal provenance**
(§6.2). It does not replace GitHub's own `*_added`/`*_removed` events, which carry the actor (P11).

### 3.9 Request budget per invocation (`gh` calls; mint and revoke are not counted)

| Path | Calls | Sequence |
|---|---|---|
| Any pre-mint refusal | **0** (and no mint) | — |
| `--add-parent` / `--remove-parent`, a write happens | **4** | GET N, GET P, POST or DELETE, GET N |
| `--add-parent` / `--remove-parent`, a no-op or a conflict | **2** | GET N, GET P |
| `--add-blocked-by` / `--remove-blocked-by`, a write happens, ≤100 blockers | **5** | GET N, GET B, GET deps p1, POST or DELETE, GET deps p1 |
| Same, a no-op | **3** | GET N, GET B, GET deps p1 |
| Each additional full page of blockers | +1 per walk | — |

The sequences are binding (T-EW22).

---

## 4. `bootstrap/query_issues.sh`: four read modes

### 4.1 New modes

| Mode | Lists | Endpoint(s) |
|---|---|---|
| `--parent-of <N>` | N's parent: **0 or 1 line** | `GET issues/<N>`; then **only if** `parent_issue_url` is a non-empty string, `GET issues/<N>/parent` |
| `--sub-issues-of <N>` | N's children, in API order (GitHub's sub-issue priority order; **not re-sorted**) | `GET issues/<N>/sub_issues?per_page=100&page=<p>` |
| `--blockers-of <N>` | issues **that block N** (N is blocked by them) | `GET issues/<N>/dependencies/blocked_by?per_page=100&page=<p>` |
| `--dependents-of <N>` | issues **that N blocks** | `GET issues/<N>/dependencies/blocking?per_page=100&page=<p>` |

**Naming.** #1352 proposed `--sub-issues <N>`. This design uses an `-of` family because the obvious
`--blocked-by <N>` is ambiguous: "what N is blocked by" or "what is blocked by N"? T-EQ6 pins the
direction to the endpoint, so a future rename cannot silently invert it.

**Why include `--dependents-of`?** AD-C14 asks to "list a `blocked_by` edge", and the tracking block
records "both sides of every edge". The blocking side is the only way to check the other end of an edge,
and it costs one endpoint.

### 4.2 Argument rules

- Each new mode takes exactly one value, `^[1-9][0-9]*$`. Commas are rejected (the edge modes are not
  `--issue`-style lists).
- Each new mode joins the exactly-one-mode count (`:109-117`). The error message keeps its
  `exactly one of …` prefix (asserted by the existing `test_no_mode_rejected`/`test_two_modes_rejected`)
  and lists the four new flags.
- **A new mode flag given twice is a usage error.** Existing flags keep their behaviour (TD-E7).
- `--milestone`, `--milestone-less`, `--label`, `--state` and `--full` are **rejected** with any new
  mode: `<flag> is not supported with edge modes — an edge list is always complete and unfiltered`. A
  filtered edge list could be misread as a complete one. Today `--issue` silently ignores the list
  filters. The new modes refuse them instead.
- **Every rule in this subsection, including the `^[1-9][0-9]*$` value check, runs before the mint**
  (with the existing validation block, `:103-130`), so a usage error never mints (T-EQ8). This differs
  deliberately from `--comments`, which validates its number after the mint. *(Architect round 2,
  edit B3.)*
- Exit codes follow the script's **existing contract**: 0 on success (possibly with empty output), and
  1 on any usage or read failure (`err`/`fail`). `query_issues.sh`'s contract is not changed.

### 4.3 Output format

There is one line per related issue, in **exactly** the `--list` format whenever the related issue is
in this repository:

```
#<n> milestone=<title|NONE> state=<state> labels=<a,b> <title>
```

- **Cross-repo entries** render their reference as `<owner>/<repo>#<n>` in place of `#<n>`. The rest of
  the line is unchanged. The repo is derived from `.repository_url` by stripping everything up to
  `/repos/`. When `.repository_url` is missing, the reference is `unknown-repo#<n>`.
  - Rationale: a parser anchored on `^#\d+ ` (the `--list` convention) will **not** match a cross-repo
    line. That **fails visibly** instead of misattributing an edge to a same-numbered issue here.
- "In this repository" means the owner/repo derived from `.repository_url` equals `REPO_SLUG`
  **case-insensitively**, the same comparison §3.4 uses. *(Architect round 1, edit A3.)*
- The filter is a **new, separate variable** (e.g. `EDGE_LINE_FILTER`): the existing filter with the
  reference term replaced. **`ISSUE_LINE_FILTER` itself stays textually unchanged** and is not
  parametrised or refactored, because `--issue`, `--list` and `--search` share it and §4.5 freezes their
  output. *(Edit A3.)* It is applied with
  `jq -r --arg slug "$REPO_SLUG"` (the `--search` mode's piping precedent, `:213`), because `gh api --jq`
  has no `--arg`. For a same-repo record, the line is **byte-identical** to `--list`'s (T-EQ4).
- **No PR filter.** `--list` drops `pull_request` records. An edge mode must never hide an edge.
  GitHub does not permit PR edges, so in practice there is nothing to drop.
- `--parent-of` on a non-child prints **nothing** and exits 0, the same "empty is a valid answer" rule
  as an empty `--list`. "Non-child" means `parent_issue_url` is absent or `null` **only** (TD-E3). Any
  other non-string value, or an empty string, is undeterminable: exit 1, no stdout, never an empty
  "no parent" answer. *(Edit B3.)* The `/parent` record is rendered through the same edge filter, so a
  cross-repo parent is qualified (T-EQ3).

### 4.4 Pagination: complete, or fail

- The list modes fetch `page=1..10` with explicit `?per_page=100&page=<p>`, stopping at the first page
  with fewer than 100 items. They never use `--paginate`.
- **Output is buffered and printed only after the walk completes.**
- If 10 full pages are fetched without a short page, the mode prints **nothing** to stdout. It exits 1
  with `edge list for #<N> exceeds 1000 entries — refusing to print a truncated list`. A partial edge
  list is never printed (TD-E6, D41 item 1).
- A failure on any page exits 1 with no stdout. A page body that is not a JSON array counts as a
  failure. *(Edit B3.)*

### 4.5 `--issue` output: unchanged, byte for byte

The `--issue` summary line **does not gain** parent or blocker fields.
- **Callers.** A repo-wide grep finds **no programmatic parser** of `--issue` output. `run_release_panel.sh`
  uses `--comments-json` (`:237`). `select_work_candidates.py` does not call `query_issues.sh` at all, and
  T3.0a's T-ZC4 keeps it that way. The consumers are agents and humans reading text
  (`worker.md:126`, `overseer.md:723`, CLAUDE.md, the operator-memory habit of "confirm the `labels=`
  field"), plus `test_query_issues.py`'s exact-line assertions.
- **Why not add fields anyway.** The title is the line's free-text tail, so new fields would have to go
  between `labels=` and the title. That changes every existing line for every reader, to save one call
  that the new modes already provide. It is not worth the churn.
- T-EQ10 pins the format with a record that **does** carry `parent_issue_url` and non-zero summaries.

### 4.6 The read-only posture consequence (stated, not changed)

`review-read-only-gh-read` grants `Bash(bootstrap/query_issues.sh *)` to read-only reviewer sessions,
so they **gain the four edge reads automatically**. That is intended: they are reads of the same
issue data `--issue` already exposes. The posture's safety rests on `query_issues.sh` never writing.
**T-EQ11 makes that a test.** No `gh` invocation in `query_issues.sh` may carry `--method`, `-X`, or
`--input`. The script's only non-GET HTTP request is the token-revoke `curl -X DELETE …/installation/token`
in `revoke_token` (`:149`). That request is exempted by name, and it is the only exemption.

---

## 5. `bootstrap/edit_issue.sh`: a redirect arm only

- **The parser gains one case arm**, placed before the catch-all `*)` (`:86`):
  `--parent|--remove-parent|--add-parent|--add-blocked-by|--remove-blocked-by|--sub-issue|--sub-issues`.
  It calls `err` with:
  `sub-issue links and blocked_by edges are edited with bootstrap/edit_issue_edges.sh --number <N> --app <role> (--add-parent|--remove-parent|--add-blocked-by|--remove-blocked-by) <M> — see its header`.
  That is exit 1, `edit_issue.sh`'s existing usage code, and it fires **before any mint**.
- **The header** gains two lines after the usage block, pointing at the sibling and at
  `query_issues.sh`'s four edge modes.
- **The "at least one edit flag" guard is untouched.** Edge flags never reach it: they error in the
  parser, which runs first. No existing flag, exit code or output changes.

---

## 6. The AD-C14 safety asymmetry, applied to this tooling

### 6.1 Which operations can unblock work (under the T3.0a selector as merged)

| Operation | Effect on selection | Direction |
|---|---|---|
| `--add-blocked-by` | N becomes `blocked-by-open-issue` or `blocker-closed-unverified`, so it is **excluded** | fail-safe |
| `--add-parent P` | **P** becomes `untracked-parent`, so it is **excluded**. N's selectability is unchanged. | fail-safe |
| `--remove-blocked-by` | If it was N's last blocker, **N becomes selectable** | **unblocks** |
| `--remove-parent P` | If N was P's last child, **P becomes selectable**. N is unchanged. | **unblocks (the parent)** |

**Forward note on the second row (architect round 1, edit A4).** "Fail-safe" holds under the T3.0a
selector as merged. Once T3.8a lands (AD-C16), a native sub-issue link becomes limb (a) of the S2
derivation admission path for a worker-authored child. It is necessary but not sufficient, because limbs
(b) to (d) also require a worker-authored, unedited tracking block listing the child and a parent
authorized now. `--add-parent` therefore never admits work on its own. T3.8a's TD and its adversarial
panel must still re-assess this tool as part of that trust boundary, and **this table's "fail-safe"
classification of `--add-parent` must not be cited there as settled**.

The fourth row is easy to miss. Detaching a child can promote its **parent** to leaf work. The same
holds for re-parenting (§3.6), which is why it is two audited steps and never a silent
`replace_parent`.

**A caller consequence worth stating.** Linking a child under an in-flight issue excludes that issue
from selection (`untracked-parent`) until T3.2 gives it `stage:tracking`. For example, a child linked
under #1644 would exclude #1644 itself. T3.7a must sequence its first `--add-parent` with that in mind.

### 6.2 Does removal need a guard in this slice? **No. The guard is T3.3's.**

- **The only correct guard is "live edges ⊇ tracking-block edges"** (AD-C5 step 4, AD-C14). It needs the
  tracking block, which is T3.7a/T3.8's format and T3.3's check. A guard here would be a **second
  implementation** of T3.3's check, ahead of its data, which is the D41 drift pattern. It could only
  check something weaker.
- **What T3.3a does instead** (provenance and narrowness, not prevention):
  1. **Removal must name the exact edge.** There is no "remove all", no "remove whatever parent", and
     no wildcard. A mismatch is a conflict (6), not a best-effort removal.
  2. **Every attempted removal is audited** (§3.8), and GitHub records the actor natively (P11; U7 for
     the removal event name).
  3. **No new capability is created.** Any session under `bypassPermissions` can already issue the raw
     DELETE, and a human can remove an edge in the UI. The script makes the operation canonical and
     auditable. It does not make it possible.
  4. **No advertisement to the autonomous worker before T3.3**: no `worker-cron-prompt.md` or
     `worker.md` text in this slice. The CLAUDE.md row carries the caution in §7.
- **The residual window** runs from T3.3a's merge to T3.3's. During it, a removal by any actor unblocks
  work with no ⊇ check. P10 shows **zero dependency edges exist today**, and the four sub-issue links
  are on closed or `untracked-parent` issues. The window therefore guards almost nothing now. §11 OQ-2
  asks the architect to accept it.

---

## 7. Docs and registration

- **`CLAUDE.md`** is a protected surface (`CLAUDE.md` is listed in `scripts/framework/protected_surfaces.txt`).
  - **"Canonical entry points by task" gains one row:**
    `Adding or removing one sub-issue link or blocked_by dependency edge (numbers in, internal ids resolved, idempotent, read-back verified; removal can unblock work — until T3.3's edge check lands, remove an edge only on a human's instruction) | bootstrap/edit_issue_edges.sh`
  - **The reads sentence in item 5** (`:301-306`) gains the four modes inside its existing parenthesised
    mode list: `| --parent-of <n> | --sub-issues-of <n> | --blockers-of <n> | --dependents-of <n>`.
    One clause follows: `edge modes paginate and refuse to print a truncated list`.
  - **The `edit_issue.sh` sentence** (`:292-301`) is **not** changed. Its enumerated scope (labels,
    milestone, title, state, assignees, body) stays true.
- **`SCRIPTS-INDEX.md`** is regenerated via `scripts/framework/regen_all.sh`. The new script's header
  line 2 must be a one-line description, because the generator reads it:
  `# bootstrap/edit_issue_edges.sh — canonical write path for sub-issue links and blocked_by dependency edges (#1352 slice, #1644 T3.3a, ADR-1644 AD-C14)`.
- **CODEOWNERS** is covered by `/bootstrap/` (`.github/CODEOWNERS:22`). There is no change, and
  `regen_all.sh --check` confirms it.
- **Protected surfaces touched:** `bootstrap/edit_issue_edges.sh`, `bootstrap/query_issues.sh`,
  `bootstrap/edit_issue.sh` (all `bootstrap/**`), and `CLAUDE.md`. The PR therefore passes the
  CODEOWNERS human gate.
- **Consumer manifest:** not listed, the same as its siblings (§1, "Not touched").
- **`.claude/agents/worker.md` and `overseer.md` GitHub-ops tables:** deferred (OQ-5(c)).

---

## 8. Test plan

The test IDs are binding.

### 8.1 `tests/automation/test_edit_issue_edges.py`

**Harness.** It copies `test_escalate_to_human.py`'s approach:
- the script is copied to `tmp/bootstrap/`, beside a stub `get_app_token.sh` (it exports `GH_TOKEN` and
  `HOS_BOT_LOGIN`, and logs `MINT`);
- `git` and `curl` are PATH stubs. `curl` logs `CURL` so that revocation is observable;
- an audit-lib stub appends its JSON to `AUDIT_FILE`;
- `gh` is a **Python stub** that:
  1. requires `--include`. Without it, the stub exits 97, so a missing `--include` fails the test;
  2. logs `METHOD PATH` per call in order, and logs stdin bodies;
  3. serves a **mutable graph** from a JSON state file: issues (`number`, `id`, `repository_url`,
     `pull_request?`, `parent_issue_url?`) and `blocked_by` lists. POST and DELETE **mutate the state
     file**, so V observes real effects;
  4. prints `HTTP/2.0 <code> <text>\r\n<headers>\r\n\r\n<body>` and exits 1 on non-2xx, like real `gh`
     (P12);
  5. takes injected faults per `METHOD PATH`: a status code, extra headers (`retry-after`), "no response"
     (empty stdout, exit 1), "status N but apply the mutation anyway" (lost response), "2xx but do not
     apply" (lag), and a malformed body.

Test ids use values deliberately different from the numbers (N=10 ⇒ `id`=5000000010, and so on), so a
number/id mix-up fails.

| ID | Asserts |
|---|---|
| **T-EW1** | Each missing required flag (`--number`, `--app`, the op) exits 2 with **no `MINT` and no `gh` call**. |
| **T-EW2** | Zero op flags, or two different op flags, exit 2 with the `exactly one of` message. No mint. |
| **T-EW3** *(TD-E7 guard)* | The same op flag twice (`--add-blocked-by 5 --add-blocked-by 6`), `--number` twice, or `--app` twice each exits 2 with `given more than once`. No mint, no `gh`. |
| **T-EW4** | Values `0`, `-1`, `05`, `1,2`, `abc` exit 2 (usage). Values `#5`, `o/r#5`, `https://github.com/o/r/issues/5` exit 2 with `qualified-reference-unsupported`. No mint. |
| **T-EW5** | Self-reference for each of the four ops exits 2 with `self-reference`. No mint. |
| **T-EW6** | `--body x` and `--body-file f` exit 2 with the not-applicable message. A bad `--app` exits 2. |
| **T-EW7** *(add-parent, happy)* | The call log is exactly `[GET issues/10, GET issues/20, POST issues/20/sub_issues, GET issues/10]`. The POST stdin parses to **exactly** `{"sub_issue_id": 5000000010}` (an int; not 10, and not a string). stdout is `edge kind=sub-issue op=add parent=#20 child=#10 outcome=added`. Exit 0. The audit outcome is `added`. |
| **T-EW8** | Add-parent when it is already the parent: **2 calls**, zero writes, exit 0, `already-present`, no audit event. |
| **T-EW9** | Add-parent when N has parent #30 (same repo): exit 6, `has-other-parent current=#30`, zero writes. When N has parent `other/repo#7`: exit 6, `current=other/repo#7`. When N's `parent_issue_url` is `null`, it is treated as absent and the write proceeds. When it is the integer `5`: exit 6, `parent-undeterminable`. |
| **T-EW10** *(remove-parent, happy)* | `[GET issues/10, GET issues/20, DELETE issues/20/sub_issue, GET issues/10]`. The DELETE stdin is exactly `{"sub_issue_id": 5000000010}`. The path is **singular** `sub_issue`. Exit 0, `removed`. |
| **T-EW11** | Remove-parent when there is no parent: exit 0, `already-absent`, 2 calls. When the parent is #30 but #20 was named: exit 6, `parent-mismatch`, zero writes. |
| **T-EW12** *(add-blocked-by, happy)* | `[GET issues/10, GET issues/20, GET issues/10/dependencies/blocked_by?per_page=100&page=1, POST issues/10/dependencies/blocked_by, GET …blocked_by?per_page=100&page=1]`. The stdin is exactly `{"issue_id": 5000000020}`. Exit 0, stdout `… issue=#10 blocked_by=#20 outcome=added`. |
| **T-EW13** | Add-blocked-by when already present: 3 calls, exit 0, `already-present`. **Membership is by id.** A blocker in `other/repo` with **number 20** and a different id does **not** count as present, so the write proceeds. |
| **T-EW14** *(remove-blocked-by)* | Happy path: the DELETE path ends `/dependencies/blocked_by/5000000020` (the **id**, not `/20`), with **no `--input`**. Exit 0, `removed`. When absent: 3 calls, exit 0, `already-absent`. |
| **T-EW15** *(pagination)* | A full page 1 of 100 other blockers, with B on page 2 of 3 entries, is found. The walk requests `page=1` then `page=2` and stops. **Ten full pages without B** exit 6 with `edges-undeterminable` and zero writes. |
| **T-EW16** *(resolution failures)* | R1 404: exit 2 `issue-not-found issue=#10`, **no R2 call**. R2 404: exit 2 `issue=#20`. R1 500: exit 1. R1 403 with no rate-limit header: exit 2 `read-rejected`. R1 403 with `retry-after`: exit 1. R1 with no response: exit 1. R1 body with no integer `id` (missing, or the string `"5"`): exit 1 `read-malformed`. A PR on either side: exit 2 `target-is-pull-request`. `.number` mismatch, or a foreign `repository_url`: exit 2 `issue-moved`. R3 404 after R1/R2 pass (blocked-by flags): exit 6 `edges-undeterminable http=404` (edit A1). Every case makes **zero writes**. |
| **T-EW17** *(write rejected)* | POST 422 with message `"bad\u0007thing"`, state unchanged: exit 2 `write-rejected http=422 message=badthing`. The control character is stripped. The audit outcome is `write-rejected`. |
| **T-EW18** *(lost response)* | POST 502, but the stub applies the mutation: V sees it, so **exit 0 `added`**. Same for 422 with the mutation already applied by a "concurrent" writer. |
| **T-EW19** *(write failed / unverified)* | POST 502, not applied: exit 4 `write-failed http=502`. POST 403 with `retry-after`, not applied: exit 4. No response, not applied: exit 4 `http=none`. POST 201 but not applied (lag): exit 4 `unverified http=201`. POST 201, then V's GET 500: exit 4 `unverified verify-read-failed`. POST 201, then V's GET 404, and (add-parent) V's `parent_issue_url` is the integer `5`: each exit 4 `unverified verify-read-failed` (edit B1). |
| **T-EW20** *(race on add-parent)* | POST 422, and V shows parent #30: exit 6, `has-other-parent current=#30`. |
| **T-EW21** *(static)* | The script text has no `--paginate`, `-f `, `-F `, `--field`, `--raw-field`, `--jq`, `gh issue`, `replace_parent` or `body=@`. Every `gh api` invocation line carries `--include`. |
| **T-EW22** *(request budget)* | Parametrized over §3.9's rows: the count of `gh` calls equals the table, and the **sequence** equals the table. Pre-mint refusals show 0 `gh` calls and no `MINT`. |
| **T-EW23** *(audit and revoke)* | The audit event has exactly §3.8's keys, and is emitted iff W was attempted. With the audit lib absent, the exit is unchanged and a warn is printed. **`CURL … DELETE` (revoke) appears on every post-mint exit path:** 0, 1 (R1 500), 2 (R1 404), 4, 6. |
| **T-EW24** | A closed B, a closed N, or a closed P is **not** refused. The write proceeds and exits 0. |

### 8.2 `tests/automation/test_query_issues_edges.py`

**Harness.** It is `test_query_issues.py`'s harness, duplicated (no import across test modules). Its
bash `gh` stub is extended to serve `issues/<n>`, `issues/<n>/parent`, `…/sub_issues?…`,
`…/dependencies/blocked_by?…` and `…/dependencies/blocking?…` from env JSON, logging every call.

| ID | Asserts |
|---|---|
| **T-EQ1** | `--parent-of 1351` with a child fixture: exactly 2 calls (`issues/1351`, `issues/1351/parent`), and one line `#1349 milestone=… state=closed labels=… <title>`. |
| **T-EQ2** | `--parent-of` on a record **without** `parent_issue_url`, and on one with `null`: exactly **1** call, empty stdout, exit 0. `/parent` is never called (TD-E2). With `parent_issue_url` = the integer `5` or `""`: 1 call, exit 1, empty stdout (edit B3). |
| **T-EQ3** | `--parent-of` with a cross-repo parent: the line starts `other-owner/other-repo#7 milestone=`. |
| **T-EQ4** | `--sub-issues-of 1358` gives three lines in fixture order (no sort). For each same-repo record, the line is **byte-identical** to the line `--list` prints for the same record (the test runs both modes on one fixture). No PR filtering: a record carrying `pull_request` is still printed. |
| **T-EQ5** | Pagination: 100 + 3 records give 103 lines, with calls `page=1`, `page=2` and explicit `per_page=100`. Ten full pages give exit 1, **empty stdout**, and stderr containing `refusing to print a truncated list`. A page-2 body that is a JSON object, not an array: exit 1, empty stdout (edit B3). |
| **T-EQ6** *(direction pin)* | `--blockers-of 10` requests `…/issues/10/dependencies/blocked_by?…`. `--dependents-of 10` requests `…/issues/10/dependencies/blocking?…`. |
| **T-EQ7** | A cross-repo entry inside `--blockers-of` renders as `o/r#5 …`. A record missing `repository_url` renders as `unknown-repo#5 …`. |
| **T-EQ8** *(usage)* | `--sub-issues-of 1,2` → exit 1. The same mode twice → exit 1 `given more than once`. Combined with `--list`, `--issue`, or another edge mode → exit 1 `exactly one of`. Combined with `--milestone`, `--milestone-less`, `--label`, `--state` or `--full` → exit 1 `not supported with edge modes`. None of these mints. |
| **T-EQ9** | A 404 or 500 on any edge endpoint → exit 1, no stdout, and revoke called. |
| **T-EQ10** *(format freeze)* | `--issue 1351`, against a record that **has** `parent_issue_url` and non-zero `issue_dependencies_summary`/`sub_issues_summary`, prints exactly `#1351 milestone=<t> state=closed labels=<l> <title>`: no new fields. |
| **T-EQ11** *(read-only invariant)* | With `#`-comment lines removed and continuation lines joined: (a) every logical line containing `gh api` contains none of `--method`, `-X`, `--input`; (b) the only line containing `-X` is the `revoke_token` `curl … installation/token` line. A behavioural limb also applies: across T-EQ1 to T-EQ9 the `gh` stub's log contains **no** non-GET method. The docstring cites the `review-read-only-gh-read` posture (§4.6). |

All existing `test_query_issues.py` tests stay green **unchanged**.

### 8.3 `tests/automation/test_edit_issue.py`

- **T-ER1.** For each of `--parent 5`, `--remove-parent`, `--add-blocked-by 5` (each alongside
  `--number 42 --app worker`): exit non-zero, stderr contains `bootstrap/edit_issue_edges.sh`, and **no**
  `GET_APP_TOKEN_CALLED_WITH`.
- All 28 existing tests stay green unchanged.

### 8.4 Traceability

| Clause | Tests |
|---|---|
| AD-C14: add, remove and list a sub-issue link | T-EW7, T-EW8, T-EW10, T-EW11; T-EQ1 to T-EQ4 |
| AD-C14: add, remove and list a `blocked_by` edge | T-EW12 to T-EW15; T-EQ5, T-EQ6, T-EQ7 |
| AD-C14: `--app`-scoped | T-EW6, T-EW1; the existing `--app` tests in both read suites |
| AD-C14: `--body-file` convention (no inline free text) | T-EW6, T-EW21 |
| AD-C14: never a hand-rolled `gh api` at a call site | One invocation site per operation (§2.1(3)); T-EW21; T-ER1 (the old spelling is redirected, not reimplemented) |
| #1352: numbers in, internal id resolved | T-EW7, T-EW10, T-EW12, T-EW14 (number ≠ id fixtures) |
| AD-C14 asymmetry: removal names the exact edge and is audited | T-EW11, T-EW14, T-EW23 |
| D41 honest degradation | T-EW17 to T-EW20 (observed-state exits), T-EQ5 (no truncated list), T-EW15 |
| TD-E7: no last-wins on new flags | T-EW3, T-EQ8 |
| Read-only posture stays read-only | T-EQ11 |
| `--issue` callers unaffected | T-EQ10; the existing `test_query_issues.py` suite |

---

## 9. V-LIVE: the write-side verification that cannot be done read-only

This slice is **correct without it** (§3.4). V-LIVE refines the error **tokens** and closes ADR §0 gap 2
for T3.3. It requires **GitHub writes**, so it is **human-authorized** (OQ-3). It is never run by the
autonomous worker on its own initiative.

1. Create three scratch issues, X, Y and Z, through `bootstrap/create_issue.sh`, with no `needs-ai`
   label. They are never selectable.
2. Run, recording each exit code, stdout/stderr, and the underlying HTTP status from a `GH_DEBUG=api`
   run or the audit event:
   - `--number Y --add-parent X`, twice (expect `added`, then `already-present`);
   - `--number Y --add-parent Z` (expect exit 6);
   - `--number Y --remove-parent X`, twice;
   - `--number Y --add-blocked-by X`, twice;
   - `--number X --add-blocked-by Y` (**U5**: does GitHub accept a 2-cycle?);
   - `--number Y --remove-blocked-by X`, twice.
3. Read `GET …/issues/{X,Y}/events` and record the **event names and actors** for every add and remove
   (U7).
4. Close X, Y and Z as `not_planned`.
5. Record the results as a TD edit to §0.3 (U1 to U8 → confirmed or refuted), and notify the architect.
   **If any token changes, it is a `clarifying` design change** to §3.4/§3.5. The read-back design means
   no exit **code** changes.

**Architect binding (round 1, edit A5).**
- **App:** run under `--app worker`, because U6 (the permission T3.7a will actually use) is the
  point. The human-proxy App does not close U6.
- **Timing:** V-LIVE is **not** a T3.3a merge blocker. It is an **entry criterion for whichever of T3.3
  or T3.7a enters coding first**. T3.3 consumes U7, and T3.7a is the first autonomous caller of the
  write paths (U6, U8).
- **U4 stays unexercised by design.** Self-reference is refused pre-mint, so V-LIVE cannot observe it,
  and it does not need to.
- **Authorization:** the run writes to the live repository, so it waits on the human (Human Review
  Required, round 1 section).

---

## 10. Affected tests and sign-offs (the startup-gap analysis)

**Should this have been settled in the initial technical design?** No. T3.3a is a new slice that the
human pulled forward on 2026-09-30 (ESC-5). No prior TD defined edge tooling, and no code has been
written against an edge contract. I do **not** recommend a `startup-artifact-gap` issue.

**Tests whose expectation changes: none.**
- `test_query_issues.py`'s two `exactly one of` tests keep passing, because the message keeps its
  prefix.
- `test_edit_issue.py`'s catch-all usage behaviour is unchanged for every existing flag.

**Sign-offs:**
- **These stand:** every T3.0a sign-off (selector, `escalate_to_human.sh`). T3.3a does not touch the
  selector, and T-ZC4's forbidden-endpoint list stays satisfied.
- **No already-approved code is orphaned.** `edit_issue.sh` gains one additive parser arm, and
  `query_issues.sh` gains four additive modes. `security-reviewer` should review §6 (unblocking
  direction) and §4.6 (posture consequence) explicitly.

---

## 11. Open questions / escalations

**OQ-1 (architect): confirm the interface split.**
- Writes go in the new sibling `bootstrap/edit_issue_edges.sh`. Reads go in `query_issues.sh`.
  `edit_issue.sh` gets only a redirect arm.
- This departs from #1352's preference (`edit_issue.sh --parent`), for the reasons in §2.1:
  - the exit contract;
  - one mutation per call;
  - D41 honest degradation, which "warn and exit 0" on removal would violate;
  - the read-only posture, which rules out writes in `query_issues.sh` (§2.2).
- Also confirm the deliberate renames from #1352: `--sub-issues` becomes `--sub-issues-of`, and
  `--remove-parent` takes the parent number.

**OQ-2 (architect): accept the pre-T3.3 removal window (§6.2).**
- T3.3a ships removal with provenance and narrowness, but **no** ⊇ guard. The ⊇ guard is T3.3's.
- Between the two merges, any actor's removal can unblock work, exactly as a UI removal can today.
  Zero dependency edges exist now (P10).
- The alternative is to ship add/list only in T3.3a and removal in T3.3. That contradicts AD-C14's
  "add, remove and list", so I do not recommend it. Please rule.

**OQ-3 (human, via architect): authorize V-LIVE (§9).**
- It creates three scratch issues and writes edges.
- Under which App: `human` or `worker`? `worker` exercises the permission (U6) that T3.7a will actually
  use.
- It is needed for the U1 to U8 tokens and for ADR §0 gap 2. It is **not** a merge blocker for T3.3a. I
  recommend it be a **T3.3 entry criterion**, because T3.3 consumes the event names.

**OQ-4 (architect): the Python-side readers for T3.3.**
- T3.3's paid satisfaction check and pre-check are executor code. They will read these same endpoints
  either by shelling out to `query_issues.sh` or by adding `github.py` readers.
- The second option creates a second invocation site for the same GETs. Please rule in T3.3's TD
  which one it is. If `github.py`, the endpoint paths should be pinned by a shared test so that the
  bash and Python sides cannot drift (the D41 concern).
- T3.3a adds nothing to `github.py`.

**OQ-5 (orchestrator / triage, not architect): pre-existing gaps found, not fixed, and not filed (per my
instructions).**
- **(a)** TD-E7: the repeated-flag last-wins defect in `edit_issue.sh`, `query_issues.sh` and
  `create_issue.sh`. I found no open issue for it.
- **(b)** TD-E6: the existing `query_issues.sh` list modes silently truncate at 100.
- **(c)** The `worker.md` (`:126-128`) and `overseer.md` (`:723`) GitHub-ops tables need the new rows.
  That is an agent-definition edit by the top-level session (#1347). I recommend it be done **with
  T3.7a**, the first autonomous caller, and **not** before T3.3 for the removal flags (§6.2(4)).
- **(d)** The consumer-manifest gap for the whole `bootstrap/` write family stands as recorded at T3.0a
  OQ-3(c).

No product question arose, so there is no `pm-agent` escalation.

**Process note.** I was instructed to write only this file. The CORE loop's temp-state file
(`.claudetmp/design/technical-design-T3.3a-<ts>.md`) was therefore **not** written. Iteration count:
round 1, draft 1, with no architect file present for T3.3a.

---

## Human Review Required

**RISK: MEDIUM.**
- The slice adds a protected-surface write primitive whose **removal** operations can **unblock work**
  under the T3.0a selector (§6.1), and it extends the read surface granted to read-only reviewers (§4.6).
- The failure direction is bounded:
  - additions are fail-safe;
  - removals must name the exact edge, never wildcard, and are audited;
  - every exit reports the **observed** final state, never an assumed one (§3.4).
- The unblocking window before T3.3 is real, but it covers an empty dependency graph today (P10,
  OQ-2).

**CONFIDENCE:**
- **HIGH** on the read-side shapes (P1 to P11, probed live).
- **HIGH** on `.id` for sub-issues (P6 plus #1352's historical write, TD-E5).
- **HIGH** on gh's `--include` status behaviour (P12).
- **MEDIUM** on the write-side statuses and event names (U1 to U8, documented but not observed). The
  design is built so that those affect only the tokens, not correctness. V-LIVE closes them.

**BLAST RADIUS:**
- `bootstrap/edit_issue_edges.sh` (new);
- `bootstrap/query_issues.sh` (four additive modes; every existing mode unchanged);
- `bootstrap/edit_issue.sh` (one parser arm);
- `CLAUDE.md` (one row, one clause);
- `SCRIPTS-INDEX.md` (generated).
- No selector, launcher, executor or agent-definition change.

**Change classification: `additive`.** It adds new primitives inside ADR-1644 AD-C14's approved
structure. It adds no new decision authority, state carrier or trust input. The structural decisions
(native edges as the enforcement mirror, and the asymmetry) are ADR-1644's and are already human-ruled.
No structural escalation is required before writing. The PR passes the CODEOWNERS human gate as a
protected surface.

**Architect review is required before `coder` handoff** (iteration 1 of 5).

---

## Architect review — round 1 (2026-10-01)

**Verdict: APPROVED_WITH_EDITS.** Edits A1 to A5 are applied in place, and nothing else in the design
changes. Binding authority: ADR-1644 AD-C14 (Tooling bullet), the §5 T3.3a row, §8, and Erratum 1.
Erratum 1 does not touch T3.3a. Its E5 (a write-primitive key is not a record format) is consistent
with this design, which writes no record.

**Fidelity.** Every AD-C14 Tooling requirement is met and traced (§8.4): add, remove and list for both
edge kinds; `--app` scoping; the `--body-file` convention (vacuous, because there is no free text); and
no hand-rolled `gh api`. §5's "depends on nothing" holds, because nothing here reads T3.1 or T3.2
artifacts. §8 holds: `replace_parent`, reprioritization, issue types and other relationship kinds are
excluded, and T-EW21 pins the first. `--parent-of` and `--dependents-of` are **not** scope creep. AD-C14
says "list", and an edge has two ends. Verified independently: `parent_issue_url`, the endpoint-free
selector (T-ZC4), CODEOWNERS `/bootstrap/`, and the consumer-manifest omission for the whole family.

**Verified by my own grep: `--issue` has no programmatic parser.** I searched `bin/`, `bootstrap/`,
`scripts/**` (`.sh`/`.py`), `.claude/agents/` and `worker-cron-prompt.md` for `query_issues`.
- Code callers: only `run_release_panel.sh:237` (`--comments-json`) and `test_agent_invoke_cli.py`
  (`--list-milestones`).
- `--issue` appears only in prose usage tables (`worker.md:126`, `overseer.md:723`) and in the
  `edit_issue.sh:43` comment.
- §4.5's claim stands. Edit A3 closes the one real risk: a coder "refactoring" the shared
  `ISSUE_LINE_FILTER`.

**Edits made:**
- **A1, R3 404 → exit 6** (§3.4 R3, §3.5, §3.7, T-EW16). A 404 on the dependencies list after R1 passed
  is a permanent condition in practice (the feature is absent on the host). Exit 1 would license
  unbounded identical retries.
- **A2, first-match ordering of the V table** (§3.4). Rows 3 and 4 to 6 overlap. T-EW20 already assumed
  row 3 wins, so this makes it explicit.
- **A3, same-repo test and filter isolation** (§4.3). The comparison is case-insensitive.
  `ISSUE_LINE_FILTER` stays textually unchanged, and the edge filter is a separate variable.
- **A4, AD-C16 forward note** (§6.1). `--add-parent` is fail-safe only until T3.8a. After that it is
  one necessary-not-sufficient admission limb, and T3.8a must re-assess it.
- **A5, V-LIVE binding** (§9). The App is `worker`. V-LIVE is an entry criterion for T3.3 or T3.7a,
  whichever enters coding first. U4 is unexercised by design.

**Soundness (beyond the edits):**
- **Exit scheme 0/1/2/4/6.** It is sound, and its central property holds: **exit 0 is emitted only on
  an observed final state.** That is why U1 to U8 affect tokens and never safety. A gh that drops the
  DELETE body (U8) degrades to exit 2 `write-rejected`, never to a false "removed".
- **Idempotency.** It is idempotent by pre-read, with `.id` equality for membership. The read-back
  closes lost-response and concurrent-writer races (T-EW18).
- **Residual and accepted.** A `--remove-parent P` whose V shows a third parent Q (a concurrent
  re-parent) exits 0 `removed`. The requested state ("P is not N's parent") is observed, so this is
  correct, and the audit records it.
- **Cross-repo and self references.** Refusing them pre-mint is correct. Making cross-repo inexpressible
  at the interface is stronger than validating it. The two sides that cannot be removed (a pre-existing
  cross-repo blocker) are correctly left to T3.3's "unresolvable ⇒ fail-closed".
- **Repeated flag = hard error.** It is correct for an edge tool, because last-wins would mutate an edge
  the caller did not name. The exit codes stay with each script's existing contract (2 here, 1 in
  `query_issues.sh`). Leaving the existing last-wins flags alone is the right scope boundary (OQ-5(a)).

**File plan.** 8 files, within the ≤15 limit. The protected surfaces are correctly identified against
`scripts/framework/protected_surfaces.txt`: `bootstrap/edit_issue_edges.sh`, `bootstrap/query_issues.sh`
and `bootstrap/edit_issue.sh` (`bootstrap/**`), plus `CLAUDE.md`. The tests and `SCRIPTS-INDEX.md` are
not protected. The PR is HUMAN_REQUIRED.

**Rulings (final unless noted):**
- **OQ-1: APPROVED.**
  - A write sibling plus reads in `query_issues.sh` is the "sibling of them" form AD-C14 names
    explicitly.
  - D41 is satisfied: there is one invocation site per operation.
  - §2.2 is decisive on its own. Edge writes inside a script granted to read-only reviewer postures
    would be a privilege escalation. **They must never be added to `query_issues.sh` in any later
    slice.** T-EQ11 is the enforcement, and it must not be weakened.
  - The renames are accepted. `--sub-issues-of` and the `-of` family remove a direction ambiguity.
    `--remove-parent <P>` naming the exact edge is required by the asymmetry, not optional.
  - The `edit_issue.sh` redirect arm is accepted as a minimal, pre-mint, additive change.
- **OQ-2: ACCEPTED, with one binding sequencing constraint.**
  - Removal without a ⊇ guard is acceptable in T3.3a. A guard here would be a second, weaker copy of
    T3.3's check (D41 drift). The capability already exists through the UI and raw API. The tool adds
    exact-edge naming and provenance, and today's graph has zero dependency edges.
  - **Binding: no autonomous caller (executor code, `worker-cron-prompt.md`, `worker.md`, or any
    cron-invoked path) may invoke `--remove-parent` or `--remove-blocked-by` until T3.3 has merged.**
    T3.7a's TD must state its compliance. If T3.7a needs removal before T3.3, that is an escalation to
    me, not a design choice.
  - This needs no human ruling. The asymmetry is already human-ruled (ESC-3, ESC-5), and the window
    adds no capability.
- **OQ-3: ACCEPTED as bound in A5.** V-LIVE is not a T3.3a merge blocker. The read-back design makes
  correctness independent of the write statuses. V-LIVE is an entry criterion for T3.3 or T3.7a,
  whichever is first, and runs under `--app worker`. **The authorization to write to the live repo is
  the human's** (see below).
- **OQ-4: RULED for T3.3's TD. Use `github.py` readers. Do not shell out to `query_issues.sh`.**
  - `query_issues.sh` prints a human-oriented text line. It has no `.id` and no `state_reason`, and its
    title is a free-text tail. T3.3's satisfaction check needs `state_reason`, `.id` and
    `repository_url`.
  - Each shell-out mints and revokes a token, which is unbudgeted request traffic against the S2
    ceiling AD-C14 counts.
  - The D41 drift concern is real. **T3.3 must add a static test pinning the four list/parent endpoint
    path templates in `github.py` to the ones in `query_issues.sh` and `edit_issue_edges.sh`**, so the
    two layers cannot drift.
  - T3.3's TD must also reconcile T3.0a's T-ZC4 (the selector's forbidden-endpoint list) with wherever
    the paid check lives.
- **OQ-5:** it is not mine, and it is noted for triage. (c) agrees with OQ-2's constraint: the
  `worker.md`/`overseer.md` rows for the **removal** flags must not land before T3.3.

**Binding on the caller (T3.7a), recorded here so it is not lost.** Exits 1 and 4 mean "retry". The
caller must bound those retries: persistent exit 1 or 4 on the same edge beyond AD-C5's grace period
(2 × the cron interval) escalates through `escalate_to_human.sh`. This script must not loop internally.

**Required changes from `technical-design`: none.** A1 to A5 are applied. `coder` implements the TD as
edited.

**Startup-gap analysis.** None of A1 to A5 should have been settled in the initial ADR review. They are
detail-level corrections inside a slice nobody has built. No sign-off is affected, and no
`startup-artifact-gap` is warranted.

### Human Review Required (round 1)

1. **Authorize V-LIVE (§9).** It creates three scratch issues and writes and removes sub-issue and
   dependency edges in `thurlow-research/HumanOversightSystem` under the **worker** App. It is
   non-selectable (no `needs-ai`), and the issues are closed `not_planned` afterwards. It must be run by
   the human, or on the human's explicit per-instance authorization, never by the autonomous worker on
   its own initiative. It blocks the start of coding on T3.3 or T3.7a, not this slice's merge.
2. **The code PR is a protected surface** (`bootstrap/**`, `CLAUDE.md`), so it passes the CODEOWNERS
   human gate as usual.

---

## Architect review — round 2 (2026-10-01, independent re-review)

**Verdict: APPROVED_WITH_EDITS.** The adopting cycle does not inherit round 1's status, so this is a
fresh read of the committed text against ADR-1644 AD-C14, §5 (T3.3a row), §8 and Erratum 1, and against
`bootstrap/query_issues.sh` and `bootstrap/edit_issue.sh` at `109985cb`.

**Round-1 edits verified in the text, not just listed:** A1 (§3.4 R3, §3.5 `404`/`410` row, §3.7 exit 6,
T-EW16), A2 (§3.4 first-match note above the V table), A3 (§4.3 case-insensitive comparison and the
separate `EDGE_LINE_FILTER`), A4 (§6.1 forward note), A5 (§9 binding). OQ-1 to OQ-4 are consistent
with §1 "Not touched", §6.2(4), §7's CLAUDE.md caution, and §9. OQ-3's original "T3.3 entry criterion"
recommendation is superseded by the A5 ruling ("T3.3 or T3.7a, whichever enters coding first").

**Edits made (round 2):**
- **B1, V-failure classification** (§3.4 V table, T-EW19). The first row named only transient,
  malformed and page-bound failures. A V read returning `404`/`rejected`, or a V record whose
  `parent_issue_url` is undeterminable, matched no row cleanly and could have fallen into the
  "state does not hold" rows or, for `--remove-parent`, been misread as "absent → removed". Now every
  non-`ok` V read and every undeterminable V parent is exit 4 `verify-read-failed`. This preserves the
  round-1 soundness property: exit 0 only on an observed state.
- **B2, exit-2 helper and pre-mint stderr form** (§3.3, §3.7). "`err` as in the siblings" exits 1, which
  contradicts the exit-2 usage contract. The script must use a `refuse` helper (the
  `escalate_to_human.sh` precedent). Pre-mint usage lines get a defined form, because `issue=#N` cannot
  be populated for an invalid value.
- **B3, `query_issues.sh` edge-mode validation timing and undeterminable reads** (§4.2, §4.3, §4.4,
  T-EQ2, T-EQ5). T-EQ8 asserts "none of these mints", but the TD did not say the value check runs
  before the mint, and the closest existing precedent (`--comments`) validates after it. `--parent-of`
  on a non-string `parent_issue_url` would have printed an empty "no parent" answer. That is a silent
  wrong answer, so it is now exit 1. Non-array pages are a failure.

**Checked and sound without change:**
- **Exit codes** 0/1/2/4/6 are each reachable, mutually exclusive, and mapped to one caller action
  (§3.7). `query_issues.sh` keeps 0/1.
- **Read-back contract.** V always runs after W. W's status selects only the token. B1 closes the one
  unmapped V outcome.
- **`--issue` byte-identity.** `ISSUE_LINE_FILTER` (`query_issues.sh:174`) and `ISSUE_FULL_FILTER`
  (`:175`) stay textually frozen (A3). T-EQ10 pins the line against a record that carries the new
  fields, and the existing `test_query_issues.py` suite runs unchanged.
- **Test plan.** Every AD-C14 clause traces to at least one test (§8.4), and the number≠id fixtures make
  a number/id mix-up fail. T-EQ11 is the enforcement behind the OQ-1 ruling, and it must not be
  weakened.
- **File list.** 8 files, within ≤15. The protected surfaces are correctly identified, and the PR is
  HUMAN_REQUIRED via CODEOWNERS.
- **V-LIVE scope.** It is correctly a gate on T3.3/T3.7a entry and not on T3.3a's merge (§9, header).
  **Durability note (non-blocking):** the binding lives only in this TD. Whoever opens the T3.3 or
  T3.7a TD must cite §9 as an entry criterion. The orchestrator should carry it into those slices'
  briefs, because ADR-1644 §5 does not list it.

**Startup-gap analysis.** B1 to B3 are detail-level corrections in an unbuilt slice. No sign-off is
affected. No `startup-artifact-gap` is warranted.

**Required changes from `technical-design`: none.** `coder` implements the TD as edited. The human
items from round 1 (V-LIVE authorization; CODEOWNERS gate) are unchanged.
