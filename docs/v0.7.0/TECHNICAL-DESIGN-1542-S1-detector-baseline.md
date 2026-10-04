# TECHNICAL DESIGN — #1542 slice 1: the allowlistability detector, the coverage check, and the closed debt baseline

**Status:** **DRAFT — iteration 2 of 5 (CORE cap). REQUESTING ARCHITECT RE-REVIEW of RC-1…RC-10.**
Iteration 1 was **APPROVED WITH REQUIRED CHANGES** (architect, 2026-10-03; full review preserved
verbatim at the end of this document). TD-O1…TD-O7 are **ruled** (§16.1; ADR-1542 Amendment 2,
AM2-1…AM2-7). This iteration applies RC-1…RC-10 and nothing else. Not to be handed to `coder` until the
architect clears iteration 2. Two items remain for the human (§16.2, **ESC-S1-1**, **ESC-S1-2**, in the
architect's sharpened form); neither blocks building slice 1.
**Date:** 2026-10-03 (iteration 1) · revised 2026-10-03 (iteration 2)
**Iteration:** 2 of 5

**Iteration-2 change log** (each RC → the sections it changed; no other section was edited):

| RC | Change | Sections |
|---|---|---|
| RC-1 | E1/E2/C3 replaced by one base-scan admission rule **C1′**; `count_growth[]` dropped; new doc absent at base must be clean | §6.4 (table, TD-D8 paragraph, release-branch note), §8.2 `detect`, §8.5 `closure` payload, §13.2 `T-BL-05/06/10`, §13.3 `T-CLI-09`/`T-CLI-20`, §5 N8 |
| RC-2 | C0 requires module absent at **both** merge-base and `origin/main`; otherwise exit 1 `"stale base: merge origin/main"` | §6.4 C0/C0s, §8.3, §13.2 `T-BL-15`, §13.3 `T-CLI-19`, §15 item 9 |
| RC-3 | `EXCLUDED_NAMES` is a literal frozen constant generated once under 3.12; collision test `T-FN-06` | §4.4, §5 (empirical paragraph), §8.6, §13.1 |
| RC-4 | HOS-only `scripts/framework/hos_required_contexts.txt`; `setup_branch_protection.sh`'s shipped list is not enlarged; PR 2 = 5 files | §9.3, §10, §13.4 `T-RP-05`/`T-RP-09`, §14 PR 2, §15 item 8, §6.7, §16.2 |
| RC-5 | Owners/dispositions: call-a-function descriptive refs → debt; G13 + `get_app_token` sourcing + release-request listing + stale out-of-scope refs → `ADR-1542 slice 1b`; `git remote get-url origin` → slice 2; `ADR-1542 FR-7` owner retired; pattern admits `slice 1b` | §1, §6.1, §6.3, §6.5, §11 (routing column), §12.2, §12.3, §13.2 `T-BL-12`, §13.4 `T-RP-06` |
| RC-6 | `removed_since_base[]` and `l1_changed_since_base` in `detect`; stderr signal for the N8 signature | §6.4 (new X3 reporting rows), §8.5, §13.3 `T-CLI-21` |
| RC-7 | Any `--output`/`--output=` in a `git` segment fires `SB-RAWGIT` | §4.2, §4.3, §13.1 `T-R-RAWGIT-P8` |
| RC-8 | New non-claim N9 (repo-function-index coupling) + its stderr cause line | §5, §8.5 |
| RC-9 | AV-4: 14 public functions; `get_branch_protection` exists; §11 findings list re-routed (TD-VF-2/3 standalone bugs; G13 per AM2-5) | §0.2, §11 |
| RC-10 | Header; §16.1 TD-Os marked ruled; §16.2 replaced with the sharpened ESC-S1-1/2 | header, §16, Human Review Required (iteration-2 addendum) |
**Author:** `technical-design`
**Binding input:** `docs/v0.7.0/ADR-1542-sandbox-script-coverage.md` (ACCEPTED FOR DESIGN, amended
2026-09-15 — G11 superseded by `ADR-1540-AMENDMENT-1` AM-11; that amendment does not touch slice 1).
**Also binding:** ADR-1357 AD-1/AD-2 (the CLI contract, inherited verbatim by ADR-1542 AD-1);
`TECHNICAL-DESIGN-1357-merge-authority-primitives.md` §3.2–§3.4.0 (envelope shape, exit-code table,
the "no policy-source selector on argv" rule — ARCH-1); the human rulings on #1542 of 2026-09-10
(layered CLI), 2026-09-11 (acceptance bar is **zero** prompts), 2026-09-15 (start the design chain).
**Scope:** ADR-1542 §4 build slice **1 of 9** only — *"Detector + inventory baseline"*: AD-11's
document scanner (including the call-a-function rule), AD-10's coverage check, both wired into CI as
required-capable checks with an enumerated, closed debt baseline; and FR-9.1's re-audit of the
"already covered" table. **Slices 2–9 are not designed here.** Where this document mentions them, it
is only to say which slice owns a baseline entry.
**Slice gate (ADR §4):** *"Detector red on today's four documents with every failing site enumerated;
check green; no new baseline entries permitted after merge."* §15 makes each clause checkable.
**Does not depend on:** ESC-1, ESC-2 or ESC-3. Where ESC-3 touches this slice, §6.7 gives a mechanism
that is correct under every option the ADR lists, and §16.2 surfaces the one residual choice.

> This document specifies **contracts, not code**. Every "must" below is a requirement on the
> implementation. Where the ADR is explicit this document restates it in implementable terms and adds
> nothing; where the ADR left a choice to `technical-design`, the choice is made here and labelled
> **TD-D<n>** with its reason.

---

## 0. Verification — the ADR's premises, re-derived on current HEAD

The ADR was verified at `511e2a2f` (2026-09-12). This document was written against `5ee0412ba`
(`origin/main`, 2026-10-03) — **191 commits later**, seven of which edit the four documents this
slice scans (`git log 511e2a2f..HEAD -- <the four docs>`: #1594, #1615, #1805, #1657 Part 2, #1540 S2,
#1644 T3.0a). Every premise slice 1 binds on was re-checked. **Note on method:** this clone is
**shallow** (`git rev-parse --is-shallow-repository` → `true`, boundary `823cea53`, 2026-09-11), so
`git blame` attributes every pre-boundary line to the boundary commit. That is good enough to say
"before or after the ADR" (the boundary predates `511e2a2f`) and no more. §6.6 makes the tool account
for this rather than mis-report it.

### 0.1 The four scanned documents — real paths (HOLDS)

| Role | Agent file | Cron prompt |
|---|---|---|
| worker | `.claude/agents/worker.md` (984 lines) | `bootstrap/worker-cron-prompt.md` (171 lines) |
| overseer | `.claude/agents/overseer.md` (850 lines) | `bootstrap/overseer-cron-prompt.md` (66 lines) |

`bin/hos-cron:1889` selects `PROMPT_FILE="$REPO_ROOT/bootstrap/${ROLE}-cron-prompt.md"`, substitutes
only `@@TARGET_RELEASE@@` and `@@MILESTONE_NUMBER@@` (`:1895-1897`), and appends a generated
"Pre-computed cycle context" block (`_build_context`, `:1905` ff.). The generated block is **not** a
file and is out of slice 1's scan (§5, non-claim N6).

### 0.2 ADR premises — status on HEAD

| ADR finding | Status | What is true now |
|---|---|---|
| **AV-1** (15 raw `gh api` sites; 6 "no wrapper" annotations) | **COUNT HOLDS, COMPOSITION CHANGED** | Still 15 textual `gh api` hits (worker.md 4, overseer.md 4, worker-cron 3, overseer-cron 4), but overseer.md's four are now `:711` (a permissive "fall back to `gh api`") plus `:812/:816/:817`, which are **prohibition examples** ("Never use …"). worker-cron `:101`'s `$(cat …next_candidates.jq)` is **gone** (#1540 S2); `:102` is now a prohibition. "No wrapper" annotations are **4**, not 6: `overseer.md:713, :748, :753`, `worker.md:327`. Consequence for this design: a bare count of `gh api` text is not a debt count — prohibitions must be classifiable (§6.3). |
| **AV-3** (#1542 builds no PR-write wrappers; ADR-1357's `overseer_merge.sh`/`overseer_escalate.sh` own them) | **PARTLY SUPERSEDED** | Neither ADR-1357 mutation wrapper exists yet. **`bootstrap/pr_review.sh`** (#1657, `ADR-1357-AMENDMENT-1`) now owns submit-verdict and request-reviewer. Merge (`overseer.md:447, :753` — raw `PUT …/merge`) and dismiss (`:449` — raw `PUT …/dismissals`) remain raw. Ownership unchanged (#1357); slice 1 records them as #1357-owned debt. |
| **AV-4** (`github.py` = 8 functions; no single-PR/reviews/files/commit getters) | **SUPERSEDED** | `github.py` now has **14** public functions, including `get_pull`, `list_pull_reviews`, `list_pull_files`, `get_commit` (#1357 slice 1, PR #1641) and `submit_pull_review`, `request_reviewers` (#1657). `get_branch_protection` (`:269`) **already exists**, so AD-2's branch-protection item is **CLI exposure only**, not a new library function. The residual library work AD-2 assigns to #1542 slice 2 is now only issue events, repo labels, and merged-PRs-with-`merged_by`. Not slice 1's concern; recorded so slice 2's design does not re-derive it. *(Iteration 2, RC-9: count corrected from 13.)* |
| **AV-5** (#1580 call-a-function prose) | **HOLDS** | `overseer.md:286` (`merge_authority.py:check_required_content_checks`, "Call `check_required_content_checks(owner, repo, head_sha, …)` on every cycle") and `:288` (`record_pr_bounce(…)`) are present. This is the canary the call-a-function rule must catch (§13, `T-R-FNCALL-P1580`). |
| **AV-6** (worker lifecycle libraries have no runtime caller) | **HOLDS** | `git grep` for importers of `claim/breakers/budget/triage/correlation/envelope/ledger` under `scripts bin bootstrap` returns only the libraries themselves plus `observability.py`/`probe.py`. `bin/hos-cron:364` still imports only `cycle_log`. Narration at `worker.md:363-369`. |
| **AV-7** (enforcement posture uncharacterized; denial not a clean syntactic function) | **HOLDS** | `bin/hos-cron:1849` still launches `--permission-mode bypassPermissions` (was `:1764`). `contract/sandbox-policy.template.json` still has `autoAllowBashIfSandboxed: true` and `disableBypassPermissionsMode: "disable"`. Grounds §5. |
| **AV-8** (per-job CI workflows, several required) | **HOLDS, GREW** | `setup_branch_protection.sh` now declares **11** required contexts — the ADR's set plus `oversight-gate-lint` and `oversight-gate-type-check` (promoted 2026-09-14 under the ratchet ruling). `tests/framework/test_branch_protection_contexts.py` enforces that every required context has a producing job by exact `name:` (#737). §9 attaches to exactly this mechanism. |
| **AV-9** (`audit_predicate.py` is the convention model) | **HOLDS — with one anti-pattern to NOT copy** | Pure classifier + `classify` subcommand + fail-closed + "narrowing only" — adopted. **But** its `--allowlist <path>` flag is a policy-source selector on argv, the exact fail-open TD-1357's ARCH-1 closed. Slice 1's CLI takes **no** path argument of any kind (§8.4). |
| **AV-10/AV-11** (git-write surface, no trailer tooling) | **HOLDS** | Slice 1 does not build these; it makes them visible (rule `SB-RAWGIT`, §4). |
| **AV-12** (ship-set and protected surfaces) | **HOLDS, with a correction** | `protected_surfaces.txt` still lists `.claude/agents/**`, `contract/**`, `bootstrap/**`, `scripts/framework/**`, `.github/workflows/**` (and now also `AGENTS.md`, `CLAUDE.md`, `bin/**`, …). `gen_sandbox_config.py` unchanged: `TEMPLATE_RELPATH` `:122`, `SUPPORTED_ROLES = ("human",)` `:130`, `EXIT_UNSUPPORTED_ROLE = 3` `:164`. **Correction:** `framework_consumer_files.txt` is **not** the single source of truth for the ship-set — `bootstrap/hos_install.sh:1898-1906` copies `get_app_token.sh`, `hos_repo_sync.sh`, `validate_setup.sh`, `sync_apps_env.sh`, `apps.env.template` directly. This is why slice 1 does not mechanize AD-14 (§10, TD-O6). |
| **G11** (superseded by AM-11) | **CONFIRMED** | `scripts/automation/lib/next_candidates.jq` deleted; `select_work_candidates.py` is the entry point; the AM-11 conformance test is `tests/automation/test_hos_cron.py:3776` (`TestCronPromptFallbackIsSandboxAllowlistable`). |
| **G13** (out-of-scope-commit handling, slice 7) | **PREMISE CHANGED — routed** | #1615 (`492826cf`, 2026-09-14) *retired the SPEC-328 out-of-scope-commit register check* and re-homed the guarantee to #1626. `worker.md:452-480` (Option A: `git revert` / `git cherry-pick`) remains, but its trigger may no longer fire. Slice 7 may be a deletion, not a build. Routed to `architect` (§16.1, TD-O7); slice 1 only baselines the sites. |

### 0.3 Does anything resembling the detector already exist? (CLAUDE.md item 1 search, stated)

Searched `scripts/` (recursively), `bootstrap/`, `bin/`, `scripts/automation/lib/` and `tests/` for
construct scanners over the agent documents (`allowlistab`, `cron-prompt`, `substitution`,
`call-a-function`, `AD-13 test 7`, `doc↔tooling`). Found:

| Found | What it does | Why it is not the detector |
|---|---|---|
| `tests/automation/test_hos_cron.py:3776` (AM-11) | Asserts the **one** rendered Step-2 fallback line has no `$(`, `$`, inline `jq`, or trailing `\`. | One line, one file. It is the right *idea* and slice 1 generalizes it; it stays (it asserts the rendered bytes, which slice 1 does not — §5 N6). |
| `tests/framework/test_selection_call_sites.py` | Substring asserts about G11's collapse. | Not a construct scanner. |
| `scripts/framework/check_agents_static.sh` | Agent-name inventory; **every file path referenced in agent files exists**. | Path *existence* only, `.claude/agents/` only; no invocability, no constructs, no cron prompts. Coverage leg 1 (§7) is stricter and adds the prompts. Not modified by this slice. |
| ADR-1357 AD-13 **test 7** ("doc↔tooling reference check") | Specified, **not built** (`git grep` finds no implementation; #1357 slice 1 shipped tests 1–4). | AD-10 says this slice's coverage check *is* test 7 extended by one leg. §16.1 TD-O5 records the coordination so #1357 slice 6 does not build a second one. |
| #1123 (v0.7.14) | Planned "documentation-reality drift detector". | Unbuilt, broader scope. Slice 1's L1 is written to be reusable by it (§2), not to pre-empt it. |

**Conclusion: nothing equivalent exists.** Slice 1 is a new module.

### 0.4 New verification findings (TD-VF)

- **TD-VF-1 — inline code spans routinely cross line breaks.** 40+ lines in the four documents contain
  an unbalanced backtick count because a span continues onto the next line (e.g.
  `overseer.md:510-511`, `` `has_human_approval(reviews,⏎ human_reviewer, head_sha)` ``). A
  line-scoped scanner misses these. §3.2 therefore extracts spans per **block**, per CommonMark.
- **TD-VF-2 — the worker's inner-loop validator call is the fail-closed form.**
  `worker-cron-prompt.md:123` runs `bash scripts/oversight/run_validators.sh` with **no arguments**,
  which takes the `no files specified` branch (`run_validators.sh:126-134`) and writes a CRITICAL
  summary every time. The command is perfectly literal, so the detector will **not** flag it — a clean
  detector result is a statement about allowlistability, not correctness (§5, N2). Routed as an FR-9.1
  finding (§11).
- **TD-VF-3 — `pr_readiness` prose under-specifies a required argument set.** `worker.md:382` instructs
  `python -m scripts.automation.lib.pr_readiness --cid <cid> --base-sha <base> --head-sha <HEAD>`;
  `pr_readiness.py:767-771` also requires `--step` and `--risk-tier`. As written, the call exits 2.
  FR-9.1 finding (§11).
- **TD-VF-4 — the clone shallowness above.** Any provenance the tool computes must disclose it (§6.6).
- **TD-VF-5 — `check_pr_reviewed.sh`'s head SHA is now obtainable by a literal call.**
  `bash bootstrap/merge_authority.sh human-approval --app overseer --pr <N>` (#1357 slice 1) emits
  `head_sha`. The overseer can therefore reach `check_pr_reviewed.sh` through two literal calls with
  the SHA transcribed — strictly better than the raw `gh api … --jq .head.sha` the prompt instructs
  today (`overseer-cron-prompt.md:54`), though AD-4's self-derivation retrofit still binds (slice 3).

---

## 1. What slice 1 delivers, and what it deliberately does not

**Delivers:**
1. A **detector** (AD-11 / FR-9.2): a deterministic scanner over the four documents that emits one
   finding per (code unit, rule) for every construct on the rule list in §4, including the
   call-a-function rule.
2. A **coverage check** (AD-10): every script surface named in a role's two documents exists and is
   invocable as named (leg 1, **enforced**); the role-allowlist legs (legs 2 and 3) built and
   fixture-tested but **inactive** until slice 9 creates the per-role policy templates (§7.3, TD-D7).
3. A **closed debt baseline** (AD-11): an enumerated JSON file of every finding on HEAD at seal time,
   each with an owner, that can only shrink once the detector exists on `main` (§6).
4. **CI wiring**: one workflow, two jobs, two status contexts, required-capable from the first PR;
   promotion to *required* in a second, small PR (§9, §14).
5. **FR-9.1's re-audit** of the preliminary document's "already covered" table (§11) — a deliverable
   of *this document*, not of code.

**Does not deliver** (named so the coder does not drift):

| Not in slice 1 | Owner |
|---|---|
| Any edit to `worker.md`, `overseer.md`, or either cron prompt — including fixing a flagged site | slices 2–8 (each sweeps its own prose, AD-12); prose fixable with an existing surface → **slice 1b** (ADR AM2-4; iteration 2, RC-5) |
| Any new wrapper, any `github.py` function, any `query_prs.sh` | slice 2+ |
| The per-role sandbox policy templates, `gen_sandbox_config.py` changes, the AD-17 characterization run, the replay harness | slice 9 |
| Any mechanical ship-set (AD-14) check | not scheduled — TD-O6 |
| Scanning `CLAUDE.md`, `AGENTS.md`, specialist subagent definitions, or `hos-cron`'s injected context | not slice 1 (§5 N5/N6; AD-16 issue for subagents) |
| A rule for raw `git` beyond AD-9's binding read list | — it *is* in slice 1 (`SB-RAWGIT`); see TD-O2 |

**Hard prohibition:** slice 1 edits **no** file under `.claude/agents/` and **no** cron prompt. A PR
that does so is out of scope and also trips `validation-check.yml`'s stamp requirement.

---

## 2. Layer map (concrete paths)

```
L1  scripts/framework/sandbox_coverage.py            NEW — pure: extraction, rules, fingerprints,
                                                           baseline evaluation, coverage evaluation
      ^ imported by
L2  scripts/framework/sandbox_coverage_cli.py        NEW — argparse, git/filesystem facts, JSON out,
                                                           baseline write (init/prune only)
    scripts/framework/sandbox_coverage_baseline.json NEW — the closed debt baseline (data)
CI  .github/workflows/sandbox-coverage.yml           NEW — jobs `sandbox-detector`, `sandbox-coverage`
```

**TD-D1 — `scripts/framework/`, not `scripts/oversight/` or `bootstrap/`.** `scripts/framework/**` is a
protected surface, so the rules, the module and the baseline all inherit CODEOWNERS human gating on
every edit with no new mechanism — the same reason ADR-1542 AD-9 puts the FR-8 artifact in
`contract/**`. It is also where the AV-9 convention model (`audit_predicate.py`) and the other
merge-gate logic (`require_*.py`, `select_work_candidates.py`) live.

**TD-D2 — no L3 bash wrapper.** ADR-1357 AD-1's L3 exists to resolve a GitHub token and is placed in
`bootstrap/` because agents invoke it. This tool needs no token, makes no network call, and is not an
agent-instructed surface (no agent document will name it). The invocation is
`python3 scripts/framework/sandbox_coverage_cli.py <subcommand>` — the `audit_predicate.py` form
(AV-9). Its argv is fixed and literal, so it is allowlistable as-is should a later slice ever name it.

**TD-D3 — the L1/L2 split.** L1 must be **pure**: no `subprocess`, no network, no `git`, no filesystem
read or write. Everything it needs from the repository arrives in a `RepoFacts` value built by L2
(§8.6). This keeps every rule unit-testable from string fixtures, and makes L1 importable by #1123
later without dragging git in. L1 imports **stdlib only** (`re`, `json`, `hashlib`, `dataclasses`,
`typing`, `builtins`); L2 imports stdlib only plus L1. **No PyYAML, anywhere in the import graph** —
the CI job runs on bare `setup-python` (TD-1643 Amendment A is the precedent for what happens
otherwise). A test enforces this (`T-RP-07`).

**Import bootstrap (copied from TD-1357 §2).** L2 must insert `Path(__file__).resolve().parents[2]` at
`sys.path[0]` before importing L1, and must derive `repo_root` from `__file__` — never from the cwd,
never from a flag, never from an env var. The tool must produce identical output when invoked from any
working directory (`T-CLI-15`).

---

## 3. Inputs and the extraction model

### 3.1 The scanned documents — a closed constant

`SCANNED_DOCS` (L1 module constant, ordered):

```
worker:   .claude/agents/worker.md, bootstrap/worker-cron-prompt.md
overseer: .claude/agents/overseer.md, bootstrap/overseer-cron-prompt.md
```

Whole files are scanned, including frontmatter, CORE, PACK and PROJECT regions — every region is read
by the model. No argv, env var or file can add, remove or substitute a document (§8.4). Adding a fifth
document is a code change to a protected file (§6.4 rule C1′ governs what that change may bring with it: a newly scanned document absent at base must be clean).

### 3.2 Units — what the rules look at

A document is decomposed into **units**. Every finding is anchored to exactly one unit.

**Fences.** A line whose content, after stripping leading whitespace (any amount — fences nested in
list items are indented), begins with ≥3 backticks or ≥3 tildes opens a fence. The **info string** is
the first whitespace-delimited word after the fence characters, lower-cased (may be empty). The fence
closes on a later line whose stripped content is ≥ the same number of the same character and nothing
else. An unclosed fence runs to end of file (CommonMark). Fences are classified:

| Class | Info strings | Treatment |
|---|---|---|
| `shell` | `bash`, `sh`, `shell`, `console`, `zsh` | every non-blank, non-comment logical line is a command unit |
| `python` | `python`, `py`, `python3`, `pycon`, `ipython` | rules `SB-PYFENCE`, `SB-FNCALL`, `SB-PYIMPORT` only |
| `text` | **everything else, including empty** (`markdown`, `md`, `json`, `yaml`, `text`, `""`, unknown) | a logical line is a command unit **only if it is command-shaped** (§3.3) |

**TD-D4 — an unlabelled or text fence is scanned line-by-line for command-shaped lines rather than
either ignored or fully scanned.** Ignoring it would let anyone defeat the detector by relabelling a
shell fence `text`; fully scanning it produces false positives on PR-body templates, turn-header
templates and verdict-enum lists (all present today: `worker.md:57`, `worker.md:172-177`,
`overseer.md:618`, `worker-cron-prompt.md:145-156`). Command-shape is the discriminator that removes
the false positives while still catching `for pr in $(gh api …)` in a fence labelled `text`.

**Logical lines (fences).** Inside a non-`python` fence: physical lines are joined when a line ends
with an unquoted `\` (the backslash removed, one space inserted) — and that logical line carries the
`continued` mark (rule `SB-CONT`). Blank lines are skipped. In a `shell` fence, a line whose first
non-blank character is `#` is a comment and skipped. The unit's `line` is the first physical line.

**Inline code spans.** Outside fences, text is grouped into **blocks** (maximal runs of non-blank
lines). Within a block, a backtick string of length *n* opens a span closed by the next backtick string
of exactly length *n*; line endings inside a span become single spaces; an unmatched backtick string is
literal text (CommonMark §6.1). The unit's `line` is the line of the opening backticks. This is the
TD-VF-1 requirement.

**Not units:** prose outside code spans, HTML comments, indented (4-space) code blocks, link targets.
These are non-claims (§5 N1).

**Normalized text.** Every unit carries `text` = its content with every run of whitespace collapsed to
one space and leading/trailing whitespace removed (fence-level units, §4 `SB-MULTI`/`SB-PYFENCE`, join
their normalized logical lines with `"\n"`). This is the text that is fingerprinted (§6.2) and shown.

### 3.3 Command shape

A unit is **command-shaped** iff, after stripping one leading `$ ` prompt marker and applying
placeholder normalization (§3.4):

- it has **≥ 2** whitespace-separated words **and** its first word is one of:
  - (a) a member of `COMMAND_WORDS` (closed constant): `bash sh zsh dash env exec eval source . cd
    export unset set trap read test [ [[ if for while until case echo printf cat head tail grep egrep
    fgrep rg sed awk cut tr sort uniq xargs tee find ls jq yq curl wget gh git python python3 pip pip3
    pytest node npm npx make rm mv cp mkdir chmod ln sudo claude codex agy`, or matches
    `^python3\.\d+$`;
  - (b) a path token containing `/` that ends in `.sh` or `.py`, or begins with `./`;
  - (c) an assignment `^[A-Za-z_][A-Za-z0-9_]*=`;
  - (d) a member of `SHELL_LIB_FUNCS` — the names of functions defined in tracked `**/lib/*.sh`
    files (supplied by `RepoFacts`, §8.6) — e.g. `audit_read_stream`, `audit_write_event`;
  - (e) a token beginning with `(`, `{` or `$(`;
  - (f) an HTTP verb form: the unit matches `^(GET|POST|PUT|PATCH|DELETE)\s+/`;
- **or** it is a single word satisfying (b) (used by coverage leg 1 only; such a unit can trip no
  lexical rule).

Every logical line of a `shell` fence is treated as command-shaped regardless of the above (the label
asserts it). **The ≥2-word floor is what keeps the documentation of forbidden constructs from tripping
the rules** — `worker.md:81-83` writes `` `$(…)` ``, `` `for` ``/`` `while` ``, `` `source` ``,
`` `&&` ``/`` `;` `` as single-token fragments, and those must not be findings.

### 3.4 Placeholder normalization (lexing only)

Before the shell lexer runs (never before fingerprinting), replace every match of
`<(?![<!(=])[^<>\n]{1,60}>` with the literal word `X`, and leave `@@[A-Z_]+@@` untouched (it is a word
with no metacharacters, substituted by `hos-cron` with a literal). Effect: `<n>`, `<pr#>`,
`<UTC timestamp>`, `<approve|comment>` are inert words; `<<EOF`, `<(…)`, `<!-- … -->` and `<=` are not
placeholders.

---

## 4. Detection rules

### 4.1 The shell lexer (contract for command-shaped units)

A three-state scanner over the normalized-for-lexing text: `N` (unquoted), `SQ` (inside `'…'`), `DQ`
(inside `"…"`). In `SQ` nothing is special except the closing `'`. In `N` and `DQ`, `\` escapes the
next character (both are consumed). Operators are recognized **only in `N`** unless stated.
**Segments** are the maximal runs of `N`-state text between the unquoted operators `&&`, `||`, `;`,
`|`, `&`, `(`, `)`, `{`, `}` and newline; a segment's **command word** is its first word after quoted
substrings are replaced by a placeholder word. (Quote-aware segmentation is required: `jq` programs
such as `'.[] | select(.x)'` must not create a segment beginning `select`.)

### 4.2 The rule table (`RULE_IDS`, closed)

Grounding key: **C** = CLAUDE.md "What breaks allowlisting" table / "What to do instead"; **A11** =
ADR-1542 AD-11's list; **A9** = ADR-1542 AD-9's binding content rule; **E** = conservative extension
proposed here (TD-O2).

| Rule | Fires on | Applies to | Grounding |
|---|---|---|---|
| `SB-SUBST` | `$(` or a backtick in `N`/`DQ`; `<(` or `>(` in `N` | command-shaped units | C, A11 |
| `SB-HEREDOC` | `<<` (incl. `<<<`) in `N` | command-shaped | C, A11 |
| `SB-VAR` | `$` followed by `{`, a letter, `_`, a digit, or one of `?#@*!$-`, in `N`/`DQ` | command-shaped | C, A11 ("`$VAR` in an argument") |
| `SB-CHAIN` | `&&`, `\|\|`, `;`, or a lone `&` (not part of `&&`, `>&`, `&>`) in `N` | command-shaped | C, A11 (`&&`-chaining), C item 7 |
| `SB-PIPE` | `\|` (not `\|\|`) in `N` | command-shaped | A11 ("pipes into `grep`") — generalized to every pipe, E |
| `SB-LOOP` | a segment whose command word is `for`, `while` or `until` **and** which has ≥2 words | command-shaped | C, A11 |
| `SB-SOURCE` | a segment whose command word is `source` or `.` with ≥1 argument | command-shaped | C, A11 |
| `SB-CONT` | a fence logical line carrying the `continued` mark | shell fences; command-shaped lines of text fences | C |
| `SB-MULTI` | a non-`python` fence containing **≥2** command units | fences (one finding per fence) | C item 7 ("one command per Bash call"), E |
| `SB-RAWAPI` | a segment whose command word is `gh` with ≥1 argument, or `curl`/`wget`; or the unit matches `^(GET\|POST\|PUT\|PATCH\|DELETE)\s+/` | command-shaped | A11 ("bare `gh api`") — generalized to every raw `gh` subcommand and to the REST-verb form, E |
| `SB-RAWGIT` | a segment whose command word is `git` with ≥1 argument that does **not** fully match one of `^git log( .*)?$`, `^git status --short$`, `^git diff --stat( .*)?$`, `^git rev-parse( .*)?$`, `^git fetch origin$`; **or** (RC-7) any `git` segment containing an `--output` or `--output=…` argument, even if it otherwise matches the read-only list (`git log --output=<f>` and `git diff --stat --output=<f>` write files — AD-8) | command-shaped | A9 (the enumerated read-only set), E |
| `SB-PYC` | a segment whose command word matches `^python(3(\.\d+)?)?$` with a `-c` argument | command-shaped | A11 (`python3 -c`), #1155 |
| `SB-FNREF` | `[\w./-]*\w\.py::?[A-Za-z_]\w*` anywhere in the unit | **all units** | A11 (`` `module.py:function` ``) |
| `SB-FNCALL` | `(?<!\w)NAME\(` where `NAME ∈ FN_INDEX` (§4.4); in `shell`-class and command-shaped units, single-quoted substrings are removed first | **all units** | A11 ("call `function(...)`"), the #1580 lesson |
| `SB-PYIMPORT` | `(^\|\s)from\s+(scripts\|bin\|bootstrap)(\.\w+)*\s+import\b` or `(^\|\s)import\s+(scripts\|bin\|bootstrap)(\.\w+)*` | **all units** | A11 ("a bare `import` snippet") |
| `SB-PYFENCE` | any `python`-class fence | fences (one finding per fence) | A11 — Python in an agent document is executable only via `python3 -c` or a heredoc, both of which are themselves flagged rules, E |
| `SB-SRCLIB` | a path token `(?<![\w/.-])(?:\./)?(?:[\w.-]+/)+lib/[\w.-]+\.sh(?![\w])` anywhere in the unit | **all units** | C ("sourcing a runtime-named file"); every tracked `*/lib/*.sh` is a sourced-only library (verified: all nine carry "Sourced library/lib" headers; mode bits are not a reliable signal — `audit_log.sh` is `100755`), E |

A unit may produce several findings (one per distinct rule it trips); a rule fires **at most once per
unit**.

### 4.3 Positive and negative examples (each row is a required test case, §13)

| Rule | Must fire (P) | Must not fire (N) |
|---|---|---|
| `SB-SUBST` | `for pr in $(gh api …)` (overseer-cron:30); `source <(bootstrap/get_app_token.sh --app worker)` (worker.md:389); `git diff --name-only $(git merge-base main X) X` (overseer.md:250) | `grep -F '$(x)' f` (single-quoted); the fragment span `--body "$(…)"` (first word `--body`, not command-shaped); the fragment `` `$(…)` `` |
| `SB-HEREDOC` | `cat <<'EOF' > f`; `wc -l <<< "x"` | `bash bootstrap/x.sh --pr <n>` (placeholder); `echo '<<'` |
| `SB-VAR` | `cd "$REPO_ROOT"` (worker-cron:121); `[ "$HOS_BOT_LOGIN" = "hos-worker-hos[bot]" ] \|\| exit 1`; `MILESTONE="${HOS_TARGET_MILESTONE_NUMBER:-}"`; `gh api "repos/o/r/pulls/$pr"` | `grep -F '$HOME' f`; `python3 -m scripts.framework.select_work_candidates --milestone @@MILESTONE_NUMBER@@`; the fragment span `` `$HOS_BOT_LOGIN` `` (one word) |
| `SB-CHAIN` | the identity guard line; `make a && make b`; `a; b` | `cmd 2>&1`; `cmd &> f`; `grep -F ';' f`; the fragment `` `&&` `` |
| `SB-PIPE` | `audit_read_stream \| grep -F x` (overseer.md:154); `git log \| head` | `bash bootstrap/pr_review.sh submit-verdict --event <approve\|comment>` (placeholder); `gh api x --jq '.[] \| .n'` (pipe inside single quotes — the line is `SB-RAWAPI`, not `SB-PIPE`); a Markdown table row |
| `SB-LOOP` | `for pr in a b; do x; done`; `while read l; do echo; done` | the fragment `` `for` ``; prose "for each PR"; `jq 'select(.x)'` |
| `SB-SOURCE` | `source scripts/oversight/lib/audit_log.sh`; `. ./env.sh` | the fragment `` `source` ``; `bash bootstrap/x.sh --source y` |
| `SB-CONT` | a `bash` fence line ending in `\` (overseer-cron:30, :32, :45) | `echo 'a\'`; `` `---\n**Role…**` `` |
| `SB-MULTI` | the worker-cron Step 4 fence (`cd "$REPO_ROOT"` + two runners); overseer.md:337-340 (two `GET` lines) | a single-command `bash` fence; the commit-trailer fence (worker-cron:159-164 — no command-shaped line); a `markdown` PR-body template |
| `SB-RAWAPI` | `gh api repos/{o}/{r}/pulls/<n> --jq .head.sha`; `gh pr view 12`; `curl -s https://x`; `GET /repos/{o}/{r}/labels`; `PUT /repos/{o}/{r}/pulls/{n}/merge` | the fragment `` `gh` ``; `bash bootstrap/query_issues.sh --app worker --list --label release-request --state open`; prose "GITHUB API — REST only" |
| `SB-RAWGIT` | `git push`; `git checkout -b x`; `git show origin/main:path`; `git status`; `git diff --name-only A B`; `git remote get-url origin`; `git revert <sha>`; **P8 (RC-7):** `git log --output=/tmp/claude/x.txt` and `git diff --stat --output /tmp/claude/x.txt` | `git log --oneline -5`; `git status --short`; `git diff --stat origin/main...HEAD`; `git rev-parse HEAD`; `git fetch origin` |
| `SB-PYC` | `python3 -c "…post_comment(…)…"` (overseer.md:809) | `python3 -m scripts.automation.pre_pr_stale_check` |
| `SB-FNREF` | `correlation.py:already_exists` (worker.md:363); `merge_authority.py:check_required_content_checks` (overseer.md:286); `require_human_approval.py::is_bot_reviewer` (overseer.md:585) | `scripts/automation/lib/github.py`; `run_validators.sh:126`; `audit_log.py` |
| `SB-FNCALL` | **`T-R-FNCALL-P1580`:** `check_required_content_checks(owner, repo, head_sha, default_branch=<default_branch>)`; `bounce_count(cid) < 2`; the two-line span `has_human_approval(reviews,⏎ human_reviewer, head_sha)`; `merge_authority.decide_merge_authority(x)` | `pr.get("x")` (`get` excluded); `select(.merged_at != null)` inside a single-quoted `jq` program; `main()`; `frobnicate()` (not in `FN_INDEX`) |
| `SB-PYIMPORT` | `from scripts.automation.lib.merge_authority import detect_human_hold_directive` (overseer.md:374) | `python3 -m scripts.framework.select_work_candidates …`; prose "import the list" |
| `SB-PYFENCE` | the ```` ```python ```` fences at overseer.md:324 and :373 | a ```` ```json ```` fence |
| `SB-SRCLIB` | `scripts/oversight/lib/audit_log.sh` (overseer-cron:38); `bootstrap/lib/comment_format_check.sh` | `scripts/automation/lib/github.py` (`.py`); `bootstrap/query_issues.sh` |

### 4.4 `FN_INDEX` — what counts as a "repo function"

`FN_INDEX` = the names of every **top-level** `def`, `async def` and `class` in every **tracked**
`*.py` file under `scripts/`, `bin/` and `bootstrap/`, excluding any path with a `tests` or `fixtures`
component, **minus** `EXCLUDED_NAMES`.

**`EXCLUDED_NAMES` is a literal `frozenset` constant in L1 (RC-3), never computed at run time.** Its
contents are `set(dir(builtins)) | set(dir(dict)) | set(dir(list)) | set(dir(str)) | {"main"}` as
evaluated **once, under CPython 3.12** (the CI interpreter, `setup-python 3.12`), pasted as a sorted
literal with a comment naming the interpreter version and the one-line expression that produced it.
Reason: deriving it from the running interpreter makes the finding set depend on the Python version, and
the inner-loop `T-RP-01` runs under the oversight venv (3.14.4 on this host) while `sandbox-detector`
runs under 3.12 — the two would disagree whenever a version adds a builtin or method name that is also a
repo function. A frozen literal makes the finding set interpreter-independent; `T-FN-06` (§13.1) turns
any future collision into a named, failing test instead of a silent finding-set change. The coder
generates the literal with a 3.12 interpreter (e.g. `uv run --python 3.12`, or the CI job itself);
**this design does not enumerate it** — no 3.12 interpreter was available to `technical-design` on this
host (only 3.14.4), and a list typed from memory or from 3.14 would be the defect RC-3 removes.
Changing the constant later is a protected-surface code change.

Private names (`_find_human_approval`) are **included**. L2 builds it with `ast.parse`; **a tracked
file that fails to parse is an operational failure (exit 1, naming the file)** — silently skipping it
would silently shrink the rule.

**TD-D5 — the call-a-function rule fires whether or not the function has an invocable surface.** The
ADR words the rule as firing on functions "that ha[ve] no invocable surface." Deciding that requires a
function→surface registry that does not exist and would itself drift. The stricter rule needs none: if
a surface exists, the prose must name the **surface** (`bash bootstrap/merge_authority.sh gate --app
overseer`), not the function — a function name in a behaviour-driving document is an invitation to
`python3 -c` or to narration either way, which is exactly AV-5's lesson. **Ruled: TD-O1 accepted;
ADR AM2-1 amends AD-11 accordingly.** Corollary (AM2-1): for the call-a-function rule family
(`SB-FNCALL`, `SB-FNREF`, `SB-PYIMPORT`, `SB-PYC`, `SB-PYFENCE`), an entry may be `accepted` **only** as a
prohibition example — a "descriptive reference" to a function is debt (§6.3).

---

## 5. What the detector does NOT claim (AV-7 grounding)

AV-7 measured that, under `autoAllowBashIfSandboxed: true`, unmatched calls *are* denied, but **not on
any clean syntactic rule** — some `;`-chained and piped calls ran, others were denied. The detector is
therefore built as a **conservative syntactic over-approximation of CLAUDE.md's list**, and its output
must never be described as more than that. Specifically (each is a required sentence, verbatim in
substance, in L1's module docstring):

- **N1 — It sees code, not intent.** Only fenced code and inline code spans are scanned. An instruction
  written as prose ("fetch its current head SHA", "cherry-pick them onto a new branch") is invisible to
  it, and the model will synthesize a command for it that the detector never saw. FR-7's prose sweep,
  not this tool, owns those.
- **N2 — Clean ≠ correct.** A finding-free command can still be the wrong command (TD-VF-2's
  fail-closed `run_validators.sh`, TD-VF-3's missing `pr_readiness` arguments). The detector proves
  nothing about argument correctness or flag existence.
- **N3 — Clean ≠ allowed.** A finding-free command is allowed only if the eventual role policy has a rule
  matching it. That is coverage legs 2/3 (inactive until slice 9) plus AD-17's replay harness and
  characterization run — not this detector.
- **N4 — Flagged ≠ denied.** Some flagged commands may in fact run under the permissive posture (AV-7).
  The rule set is deliberately a superset; a finding means "relies on behaviour CLAUDE.md says breaks
  allowlisting," not "was measured to be denied."
- **N5 — Four documents only.** `CLAUDE.md` and `AGENTS.md` (read by every session and full of example
  heredocs), the specialist subagent definitions (AD-16's separate issue), and `docs/**` are not scanned.
- **N6 — Templates, not rendered prompts.** It scans the cron-prompt *templates*. `hos-cron`'s
  `@@…@@` substitution and its generated context block are not seen; the AM-11 test remains the only
  check on rendered bytes.
- **N7 — Label evasion is narrowed, not closed.** A `text`/unlabelled fence line that is not
  command-shaped (§3.3) is not lexed. Human CODEOWNERS review of the scanned documents (all four are
  protected surfaces) is the backstop.
- **N8 — The rule set is itself a human-gated widening point.** Narrowing a rule, or renaming one, is a
  code change to a protected file. Under RC-1's C1′ (§6.4) a rule *rename* can no longer admit new
  sites (only text that existed at base is admissible), but a rule *narrowing* still silently removes
  findings, and the detector cannot defend against its own rules being edited. CODEOWNERS review is the
  control. RC-6 makes it visible to that reviewer: `detect` reports `removed_since_base[]` and
  `l1_changed_since_base`, and prints a stderr line when both are present (§8.5).
- **N9 — Repo-function-index coupling (accepted, RC-8).** `FN_INDEX` is derived from the repository's
  Python code, not from the scanned documents. A code-only PR that adds a repo function whose name
  already appears as `name(` in a scanned document creates a **new finding in an unchanged document**.
  C1′ admits it, because the text existed at base. But X1 still requires a matching baseline entry, so
  that code-only PR must also edit the baseline, which is a protected-surface edit. This coupling is
  known and accepted: the alternative (freezing the index) would let new functions go unflagged. The
  stderr line for such a finding names the cause: `sandbox-coverage: <RULE> <doc>:<line>: text
  unchanged since base; repo-function index grew: <text>` (§8.5).

**Empirical characterization performed for this design.** A throwaway prototype of §3–§4 was run
against HEAD (results §12). It drove four design changes: the ≥2-word command-shape floor (§3.3),
quote-aware segmentation (§4.1), the `EXCLUDED_NAMES` exclusion (§4.4 — frozen as a 3.12 literal in iteration 2, RC-3), and block-scoped inline spans
(TD-VF-1). No live `claude --print` matcher measurement was made — that is AD-17's characterization
run (slice 9), and a nested agent session from a worker cycle is not an appropriate place to do it.

---

## 6. The baseline — format and "closed" semantics

### 6.1 File: `scripts/framework/sandbox_coverage_baseline.json`

One JSON object, serialized deterministically (`json.dumps(obj, indent=2, sort_keys=True,
ensure_ascii=False) + "\n"`; entries sorted by `(doc, line, rule, occurrence)`), so that `baseline-prune`
output is byte-stable and diffs are reviewable.

| Key | Type | Meaning |
|---|---|---|
| `schema_version` | int | `1` |
| `fingerprint_version` | int | Must equal L1's `FINGERPRINT_VERSION` (`1`) |
| `rules` | list[str] | Must equal L1's `RULE_IDS` exactly (sorted) |
| `docs` | list[str] | Must equal L1's flattened `SCANNED_DOCS` exactly |
| `entries` | list[object] | One per finding, below |

Each entry:

| Key | Type | Identity? | Meaning |
|---|---|---|---|
| `fingerprint` | str | **yes** | `"sha256:" + hex`, §6.2 |
| `doc` | str | (in fp) | repo-relative document path |
| `rule` | str | (in fp) | a `RULE_IDS` member |
| `text` | str | (in fp) | the unit's normalized text |
| `occurrence` | int ≥1 | (in fp) | §6.2 |
| `unit_kind` | `"inline" \| "fence-line" \| "fence"` | no | informational |
| `line` | int | no | informational; updated by `baseline-prune` |
| `disposition` | `"debt" \| "accepted"` | no | §6.3 |
| `rationale` | str | no | **required, non-empty iff `accepted`**; must be absent or `null` for `debt` |
| `owner` | str | no | matches `^(#\d+\|ADR-1542 slice (1b\|[2-9]))( — .+)?$`; §6.5. *(Iteration 2, RC-5(e): admits `ADR-1542 slice 1b` (AM2-4); the former `ADR-1542 FR-7` owner string is **retired** and is a schema violation.)* |
| `introduced_in` | str \| null | no | commit SHA that last touched the unit's first line at seal time; §6.6 |
| `introduced_at` | str \| null | no | that commit's author date, `YYYY-MM-DD` |

Schema violations — unknown top-level or entry key, wrong type, duplicate `fingerprint`, a `rule` not in
`rules`, a `doc` not in `docs`, `accepted` without `rationale`, an `owner` not matching the pattern —
are **operational failures** (exit 1). A baseline the tool cannot fully trust is never partially used.

### 6.2 Fingerprint

`fingerprint = "sha256:" + sha256( doc + "\0" + rule + "\0" + text + "\0" + str(occurrence) ).hexdigest()`,
UTF-8. `occurrence` is the 1-based index of this unit among all findings in the same `doc` with the
same `(rule, text)`, in document order. Consequences the coder must preserve: the fingerprint is
**stable under line shifts** and under whitespace re-flow; it **changes if the flagged text changes**
(editing a baselined site without fixing it reads as "one stale entry, one new finding" — the ratchet,
by design); removing one of two identical sites leaves `occurrence 1` and makes `occurrence 2` stale.

### 6.3 Dispositions

- **`debt`** — a site that must eventually be removed. The debt count is the number every later slice
  drives down, and FR-9.2's completion condition is **zero `debt` entries**.
- **`accepted`** — a site that stays: a prohibition example ("**Never** use `gh api -f body=@…`"), or —
  **for the shell-construct rules only** — a descriptive reference that instructs nothing. Requires a
  `rationale`. **For the call-a-function family (`SB-FNCALL`, `SB-FNREF`, `SB-PYIMPORT`, `SB-PYC`,
  `SB-PYFENCE`), `accepted` is permitted only with rationale `"prohibition example"`; a descriptive
  function reference is always `debt`** (AM2-1 corollary, RC-5(a)). L1's schema validation enforces
  this: an `accepted` entry in that family whose `rationale` is not exactly `"prohibition example"` is a
  schema violation (exit 1).

**TD-D6 — dispositions are closed in one direction.** After the detector exists on `main`, a change may
move an entry `accepted → debt` (stricter) but never `debt → accepted`; otherwise "reclassify it as a
prohibition" would be a way to make debt disappear from the metric. The slice-1 PR assigns the initial
dispositions (by hand, human-reviewed — the file is a protected surface), using §12.3's candidate list.
Prohibitions written in future should use fragment spans (`` `-f body=@path` ``), which are not
command-shaped and trip no rule — so no future change ever *needs* a new `accepted` entry.

### 6.4 "Closed" — the exact checks `detect` performs

Let **F** = the findings computed on the working tree; **H** = the head baseline (the committed file
in the working tree); **B** = the baseline at the **base commit**, where base = `git merge-base HEAD
refs/remotes/origin/main` (the constant `BASE_REF`; not configurable — §8.4).

| # | Check | Fails as |
|---|---|---|
| X1 | **Exactness:** `{fingerprints of F} == {fingerprints of H.entries}` | `unbaselined[]` (in F, not H) and `stale[]` (in H, not F) — exit 3 |
| X2 | **Metadata:** `H.rules == RULE_IDS`, `H.docs == SCANNED_DOCS`, `H.fingerprint_version == FINGERPRINT_VERSION` | exit 3 (`metadata_mismatch[]`) |
| C1′ | **Closure (RC-1):** every `e ∈ H.entries` has `e.fingerprint ∈ B.entries ∪ FP(scan_head_L1(base_docs, head_facts))`, where `base_docs` = each `SCANNED_DOCS` path read via `git show <base>:<path>` (a path absent at base reads as the empty document; any other `git show` failure is exit 1), scanned by the **head** L1 with the **head** `RepoFacts` | `closure.added[]` — exit 3 |
| C2 | **Disposition monotonicity:** for `e` in both `B` and `H`, `B.e.disposition == "debt"` and `H.e.disposition == "accepted"` is forbidden | `closure.disposition_flips[]` — exit 3 |
| C0 | **Introducing change (RC-2):** closure (C1′, C2) is `not_applicable` **only if** `scripts/framework/sandbox_coverage.py` is absent at **both** the merge-base **and** `refs/remotes/origin/main` (`git cat-file -e <commit>:<path>` fails for both). Then `closure.status = "not_applicable"` and `not_verified[]` says so | — |
| C0s | **Stale base (RC-2):** module **present at `refs/remotes/origin/main` but absent at the merge-base** | **exit 1**, `error: "stale base: merge origin/main"` |
| C4 | Module present at the merge-base but the baseline file absent (at base, or at head) | exit 1 |
| R1 | **Reporting, not failing (RC-6):** `removed_since_base[]` = entries in `B` whose fingerprint is not in `H` (each with `doc`, `line`, `rule`, `text`, `disposition`, `owner`); `l1_changed_since_base` = whether the git blob of `scripts/framework/sandbox_coverage.py` at the merge-base differs from the head file (`git rev-parse <base>:<path>` vs `git hash-object <path>`) | never changes the exit code; when `l1_changed_since_base` is true **and** `removed_since_base` is non-empty, one stderr line: `sandbox-coverage: NOTE L1 changed and <n> baseline entries were removed since base — rule narrowing or fixed sites; reviewer must confirm which (N8)` |

**Why both exactness and closure.** X1 keeps the baseline equal to reality, so a fixed site *must* be
pruned (the ratchet: debt can only shrink, and shrinkage is recorded). C1′ keeps the baseline from
growing; without it, X1 alone would let any change add a construct plus its matching entry.

**What C1′ admits, and why it replaced E1/E2/C3 (TD-D8, revised by RC-1).** Iteration 1 admitted every
entry under a rule absent from `B.rules` (E1) or a document absent from `B.docs` (E2), and fell back to
per-(doc, rule) counts on a fingerprint-version change (C3). E1 had a rename hole: renaming
`SB-RAWAPI` → `SB-RAWAPI2` (one protected edit) re-admitted all old debt **and any new raw-API site added
in the same PR**. C1′ replaces all three with one rule that implements ADR AM2-2's meaning of "addition"
(*construct text that did not exist in the base commit's scanned documents*): scanning the **base**
documents with the **head** rules admits exactly the pre-existing text, whatever made it newly
findable — a new or renamed rule, a newly scanned document, a fingerprint-version change, or growth of
`FN_INDEX` (N9) — and nothing else. Consequences the coder must preserve:
- a rule rename plus a new site → the new site is in `closure.added` (its text is not in the base docs);
- a new rule over unchanged documents → all its findings admitted;
- a newly scanned document **absent at base** reads as empty, so it must be **clean** — any finding in it
  is in `closure.added`;
- the fingerprint function is applied to both sides by the same (head) L1, so a fingerprint-version
  change needs no special case.

**C0 is the one-time seal moment** and is deterministic: it applies to exactly the PR that introduces
the module, while `origin/main` does not yet have it. In that PR `detect` runs X1 and X2 only. **RC-2:**
keying only on the merge-base would let any checkout whose merge-base predates PR 1 — a stale branch, or
a CI checkout of the PR head instead of the merge ref — silently skip closure and exit 0. Requiring
absence at `origin/main` too closes that; a stale base is an operational failure the author fixes by
merging `origin/main`, never a pass.

**Release branches.** A PR targeting `release/v*` resolves its closure base as the merge-base with
`origin/main` — the release branch's fork point from `main`. That is coherent: release-branch entries
can only shrink relative to the fork. It is deliberate and must not be "fixed" by reading
`GITHUB_BASE_REF`; §8.4 forbids every environment read.

**Base resolution failures are fail-closed:** if `refs/remotes/origin/main` does not resolve, or
`git merge-base` fails, or the repository is so shallow that the merge-base is missing, `detect` exits
1. There is no "skip closure" path (§8.4).

### 6.5 Owners

Every entry names who removes it. `baseline-init` (§8.2) assigns a **default owner by rule** from a
closed table in L2 (used only by `baseline-init`); the slice-1 coder then refines individual entries
using §12.3. Defaults:

| Rule | Default owner |
|---|---|
| `SB-RAWAPI` | `ADR-1542 slice 2` |
| `SB-FNCALL`, `SB-FNREF`, `SB-PYIMPORT`, `SB-PYFENCE`, `SB-PYC` | `#1357 — slice 6 prose replacement` |
| `SB-PIPE`, `SB-SRCLIB` | `#1538` |
| `SB-VAR`, `SB-CHAIN`, `SB-LOOP`, `SB-CONT`, `SB-MULTI` | `ADR-1542 slice 3` |
| `SB-RAWGIT` | `ADR-1542 slice 4` |
| `SB-SUBST`, `SB-SOURCE`, `SB-HEREDOC` | `ADR-1542 slice 1b` |

`owner` is **not** part of the fingerprint, so re-assigning an owner is always permitted. *(Iteration 2,
RC-5: the `ADR-1542 FR-7` default is retired. Every former FR-7 item now has a slice — prose fixable with
an existing surface belongs to **slice 1b** (ADR AM2-4); the rest to its owning slice. §12.3 lists the
per-site refinements.)*

### 6.6 Provenance

`baseline-init` sets `introduced_in`/`introduced_at` from `git blame --porcelain -L <line>,<line> HEAD
-- <doc>` for the unit's first line. **If `git rev-parse --is-shallow-repository` prints `true`, both
fields are `null` for every entry and `not_verified[]` says why** (TD-VF-4: in a shallow clone,
boundary attribution is wrong, not merely imprecise). Provenance is informational only — it feeds the
human's ESC-3 disposition (§6.7), never a check.

### 6.7 ESC-3 — a mechanism correct under every option

ESC-3 asks whether v0.7.0 work may add "call this function" prose **before the detector is required**.
The design does not answer it; it makes every answer executable:

- **After the detector exists on `main`:** C1′/C2 apply to everyone, under all three options. This is
  not an ESC-3 choice — ADR AD-11 binds it, and AM2-2 fixes its meaning (an addition is construct text
  absent from the base commit's scanned documents). There is deliberately **no admission flag, env var,
  label or file** for post-seal additions, and the architect does not recommend amending AD-11 (§16.2).
- **Before it (the window ESC-3 is actually about):** C0 makes the slice-1 PR absorb whatever has landed
  by the time it merges. Every absorbed entry carries an `owner` (satisfying option **(b)**) and, in a
  full-history checkout, `introduced_in`/`introduced_at` — so the slice-1 PR description must list every
  entry whose `introduced_at` is after **2026-09-12** (ADR acceptance). Under option **(a)** the human
  disposes of exactly that list (revert, or ship a surface); under **(c)** the list is informational.
  Today's list is §12.2.
- **Between merge and promotion to *required*:** the checks run and report but do not block merge until
  a human re-runs `setup_branch_protection.sh` from the HOS repo, which then picks up the HOS-only
  contexts from `scripts/framework/hos_required_contexts.txt` (§9.3, RC-4). An in-flight PR that adds a site in that window
  shows a red, non-required context. ESC-S1-2 asks the human to close that window promptly.

---

## 7. Coverage check (AD-10)

### 7.1 Named surfaces

For each role, from that role's two documents, L1 extracts **surface references** from command units:

| Form | Extracted reference |
|---|---|
| segment command word `bash`/`sh`, next non-option token is a path | path ref, `via_interpreter = true` |
| command word `python`/`python3`/`python3.N` then `-m <dotted>` | module ref |
| command word `python`/`python3` then a `.py` path | path ref, `via_interpreter = true` |
| command word is itself a path (form (b) of §3.3) | path ref, `via_interpreter = false` |
| a single-word unit that is a `.sh` path or `bin/…` path | path ref (mention), `via_interpreter = true` |

Paths are normalized (strip a leading `./`). References to `**/lib/*.sh` are **excluded** (they are
`SB-SRCLIB` findings, never surfaces). Paths containing a placeholder (`<…>`, `{…}`) or not under
`bootstrap/`, `scripts/` or `bin/` are ignored. Single-word `.py` mentions are **not** references (they
name libraries descriptively; the call-a-function rules own that).

### 7.2 Leg 1 — exists and is invocable (ENFORCED)

| Reference | Invocable iff | Finding otherwise |
|---|---|---|
| path ref, `.sh` or extensionless | tracked (`git ls-files`); first line matches `^#!.*\b(ba)?sh\b`; and if `via_interpreter = false`, git index mode is `100755` | `COV-MISSING` (untracked) / `COV-NOT-INVOCABLE` |
| path ref, `.py` | tracked; contains a line matching `^if __name__ == ['"]__main__['"]:` | same |
| module ref `a.b.c` | `a/b/c.py` tracked with a `__main__` guard, or `a/b/c/__main__.py` tracked (namespace subpackages are valid — `scripts/framework/` has no `__init__.py` and `select_work_candidates` works) | same |

**Verified on HEAD:** every reference I extracted from the four documents resolves and is invocable
(22 `.sh`/`bin` paths, all tracked with bash shebangs; `pre_pr_stale_check`, `pr_readiness` and
`select_work_candidates` all have `__main__` guards). Leg 1 is therefore expected **green with no
exceptions**, and the coverage check has **no baseline** (TD-D9). **If the coder finds leg 1 red on
HEAD, the coder must stop and route to `technical-design` — not add an exception mechanism.**
(Observed and harmless: `scripts/oversight/run_gates.sh` is mode `100644` while its own header documents
the `./scripts/oversight/run_gates.sh` form. None of the four documents invokes it, so leg 1 is
unaffected; recorded in §11.)

### 7.3 Legs 2 and 3 — the allowlist (BUILT, INACTIVE)

- **Leg 2 (`COV-NOT-ALLOWED`):** every reference with `via_interpreter` or path form appears in the
  role's policy as a `permissions.allow` entry `Bash(<cmd>)` or `Bash(<cmd> *)`, where `<cmd>` is the
  literal invocation prefix (`bash <path>` / `python3 -m <module>` / `<path>`). No prefix rule
  (`Bash(bash bootstrap/*)`) satisfies it — AD-10 forbids prefix rules for autonomous roles.
- **Leg 3 (`COV-DANGLING`):** every `Bash(…)` allow entry whose first or second word is a repo path
  resolves to a tracked file.
- **Role policy paths** (L1 constant): `contract/sandbox-policy.worker.template.json`,
  `contract/sandbox-policy.overseer.template.json` (AD-9's names).

**TD-D7 — legs 2/3 ship inactive behind a module constant `ALLOWLIST_LEGS_ACTIVE = False`.** The
templates are slice 9's artifact (gated on ESC-2) and do not exist; checking membership in a file that
does not exist is either a permanent failure (blocking every slice 2–8 PR that names a new wrapper) or a
silent pass. Neither is acceptable. While inactive, **every** `coverage` run emits
`not_verified: ["allowlist legs inactive: per-role policy templates not yet authored (ADR-1542 slice 9)"]`
— the check states that it is not checking, every time (AD-13's honesty rule). Slice 9 flips the
constant in the same PR that adds the templates; from then on an absent template is exit 1. The
constant is not reachable from argv or env; tests reach legs 2/3 through a keyword-only test injection
(§8.6). This is in tension with AD-12 for slices 2–8 — TD-O4.

---

## 8. CLI contract — `scripts/framework/sandbox_coverage_cli.py`

### 8.1 Argv

```
python3 scripts/framework/sandbox_coverage_cli.py <subcommand>
<subcommand> ∈ { scan | detect | coverage | baseline-init | baseline-prune }
```

**No flags.** Every subcommand takes zero options. There is no `--doc`, `--baseline`, `--base`,
`--repo-root`, `--rules`, `--force`, `--skip-*`, `--json`, `--quiet`. `-h/--help` prints usage to
**stderr**, a usage envelope to stdout, and exits 2 (help is not an answer).

### 8.2 Subcommands

| Subcommand | Kind | Does |
|---|---|---|
| `scan` | reporter | Computes F for all four documents; emits every finding. Reads no baseline, needs no base. |
| `detect` | gate | §6.4 checks X1, X2, C0/C0s, C1′, C2, C4, and the R1 reporting (RC-1, RC-2, RC-6). For C1′ it reads each scanned document at the merge-base with `git show <base>:<path>` and scans it with the head L1 and head `RepoFacts`. |
| `coverage` | gate | §7 legs; leg 1 enforced, legs 2/3 per `ALLOWLIST_LEGS_ACTIVE`. |
| `baseline-init` | writer | Writes the baseline from F (all `disposition: "debt"`, default owners, provenance) **only if C0 holds** (module absent at base); otherwise refuses. May overwrite an existing file *only* under C0 (so the introducing PR can re-seal after merging main). |
| `baseline-prune` | writer | Removes `stale[]` entries and refreshes `line` on surviving entries; **never adds an entry, never changes `disposition`/`owner`/`rationale`**. Reports `unbaselined[]` but does not act on it. |

### 8.3 Exit codes (AD-2 rule 3, applied)

| Condition | `scan` | `detect` | `coverage` | `baseline-init` | `baseline-prune` |
|---|---|---|---|---|---|
| answered / conformant / written | 0 | 0 | 0 | 0 | 0 |
| non-conformant (any §6.4 X/C failure; any active coverage finding) | — | **3** | **3** | — | — |
| refused (C0 does not hold) | — | — | — | **3** | — |
| operational: a scanned doc missing/unreadable; `git` missing or failing; `origin/main` or merge-base unresolvable (`detect`, `baseline-init`); **stale base — module at `origin/main` but not at the merge-base (C0s, RC-2; `detect` and `baseline-init`)**; a `git show <base>:<doc>` failure other than path-absent (C1′); baseline missing (C4) or schema-invalid; a tracked `.py` unparseable (§4.4); active legs with a missing template | 1 | 1 | 1 | 1 | 1 |
| usage: no subcommand, unknown subcommand, any flag | 2 | 2 | 2 | 2 | 2 |

`scan` never exits 3 and never exits non-zero because findings exist: "the documents contain
constructs" is an answer (the reporter convention). **Exit 3 on a gate is "the check answered: not
conformant"** — a normal outcome distinct from operational failure, which is the meaning AD-2 gives 3.
CI treats any non-zero as red.

### 8.4 Prohibited inputs (AD-2 rule 5 + TD-1357 ARCH-1)

No input — flag, env var, file, label, PR body — selects which documents are scanned, which baseline is
read, which commit is the base, which rules run, or whether a check runs. Concretely: the documents are
L1 constants; the baseline path is an L1 constant; the base is `merge-base(HEAD, refs/remotes/origin/main)`
with `BASE_REF` an L1 constant; the repo root is `parents[2]` of the module file. **No `os.environ`
read is permitted in L1 or L2** except what `git` itself inherits (`T-CLI-05` asserts that setting
plausible variables changes nothing).

### 8.5 Output

**stdout is exactly one JSON object on every path, including exit 2** (use an `ArgumentParser`
subclass whose `error()` emits the envelope — TD-1357 §3.3). Diagnostics go to stderr, one line per
finding in the form `sandbox-coverage: <RULE> <doc>:<line>: <text>` (truncated to 160 chars), so CI
logs are readable without parsing JSON. Stderr is never suppressed. Two cause-annotated forms (`detect`
only): an **unbaselined** finding whose fingerprint is in the base-scan set but not in `B` — i.e.
admissible pre-existing text that only needs an entry (N9, RC-8) — prints `sandbox-coverage: <RULE>
<doc>:<line>: text unchanged since base; repo-function index grew: <text>` when the rule is
`SB-FNCALL` and `l1_changed_since_base` is `false` (with L1 unchanged, the only input that can make
unchanged `SB-FNCALL` text newly findable is `FN_INDEX` — no base index is computed), and
`… text unchanged since base; newly findable: <text>` otherwise. The R1 rule-narrowing note (§6.4) is
one further line.

**Envelope (every record):**

| Key | Type | Meaning |
|---|---|---|
| `schema_version` | int | `1` |
| `tool` | str | `"sandbox_coverage"` |
| `subcommand` | str \| null | `null` only on a pre-dispatch exit 2 |
| `computed_at` | str | UTC `%Y-%m-%dT%H:%M:%SZ` |
| `repo_root` | str \| null | absolute |
| `head_sha` | str \| null | `git rev-parse HEAD` |
| `base_sha` | str \| null | merge-base, for `detect`/`baseline-init`; else `null` |
| `rules_version` | list[str] | `RULE_IDS` |
| `not_verified` | list[str] | **always present**, possibly empty |
| `error` | str \| null | single-line machine-stable reason on exit 1/2 |

**Payloads (merged at top level, never colliding with envelope keys):**

- `scan`: `findings[]` (each `{fingerprint, doc, line, rule, unit_kind, text, occurrence}`),
  `counts: {total, by_rule{}, by_doc{}}`.
- `detect`: `conformant`, `findings_total`, `baseline_entries`, `debt_count`, `accepted_count`,
  `unbaselined[]`, `stale[]`, `metadata_mismatch[]`,
  `closure: {status: "enforced"|"not_applicable", added[], disposition_flips[]}` *(iteration 2, RC-1:
  `count_growth[]` dropped)*, `removed_since_base[]` (each `{fingerprint, doc, line, rule, text,
  disposition, owner}`; empty when closure is `not_applicable`), `l1_changed_since_base` (bool; `false`
  when not applicable) *(RC-6)*.
- `coverage`: `conformant`, `legs: {exists_invocable: "enforced", allowlisted: "enforced"|"inactive",
  allow_entries_resolve: "enforced"|"inactive"}`, `roles: {worker: {refs[], findings[]}, overseer: {…}}`
  (each finding `{code, doc, line, ref, reason}`).
- `baseline-init`: `written`, `path`, `entries`, `refused_reason` (null unless exit 3),
  `post_adr_entries[]` (entries with `introduced_at > "2026-09-12"` — §6.7).
- `baseline-prune`: `removed[]`, `remaining`, `unbaselined_count`.

### 8.6 L1/L2 API (contract, not code)

L1 public surface — these names and shapes, nothing else exported:

- `RULE_IDS: tuple[str, ...]`, `SCANNED_DOCS: dict[str, tuple[str, str]]`, `FINGERPRINT_VERSION = 1`,
  `BASELINE_RELPATH`, `MODULE_RELPATH`, `BASE_REF = "refs/remotes/origin/main"`,
  `ROLE_POLICY_RELPATHS`, `ALLOWLIST_LEGS_ACTIVE = False`, `ADR_ACCEPTED_DATE = "2026-09-12"`.
- `RepoFacts` (frozen dataclass): `tracked: Mapping[str, str]` (path → git mode), `first_lines:
  Mapping[str, str]`, `main_guarded: frozenset[str]`, `fn_index: frozenset[str]`,
  `shell_lib_funcs: frozenset[str]`.
- `extract_units(doc: str, text: str) -> list[Unit]`
- `is_command_shaped(text: str, shell_lib_funcs) -> bool`
- `scan_document(doc: str, text: str, facts: RepoFacts) -> list[Finding]`
- `fingerprint(doc, rule, text, occurrence) -> str`
- `parse_baseline(text: str) -> Baseline` (raises `BaselineError`)
- `BaseState` (frozen dataclass, built by L2): `module_at_merge_base: bool`, `module_at_origin_main:
  bool`, `baseline: Baseline | None`, `doc_texts: Mapping[str, str]` (each scanned doc at the merge-base;
  `""` if absent there), `l1_changed: bool`.
- `evaluate_baseline(findings, head: Baseline, base: BaseState, facts: RepoFacts) -> BaselineVerdict` —
  decides C0/C0s from the two booleans (C0s is returned as an operational-error verdict that L2 maps to
  exit 1), computes the C1′ admissible set by calling `scan_document` on `base.doc_texts` with the head
  `facts`, and fills `removed_since_base`/`l1_changed_since_base`. *(Iteration 2: signature changed from
  `base: Baseline | None, base_has_module: bool` for RC-1/RC-2/RC-6.)*
- `EXCLUDED_NAMES: frozenset[str]` — the RC-3 literal (§4.4).
- `evaluate_coverage(docs_by_role: Mapping[str, Mapping[str, str]], facts, policies: Mapping[str, dict] | None, legs_active: bool) -> CoverageVerdict`

L2: `main(argv: list[str] | None = None, *, repo_root=None, legs_active=None) -> int` — the two
keyword-only parameters are **test-only injection points**; `argparse` must not define them and the
`__main__` block must not populate them (TD-1357 §3.4.0 pattern). L2 runs `git` via `subprocess.run`
with an argv list (never `shell=True`), `cwd=repo_root`, and a timeout (30 s per call); a timeout is
exit 1.

---

## 9. CI wiring

### 9.1 `.github/workflows/sandbox-coverage.yml`

| Key | Value | Why |
|---|---|---|
| `name` | `Sandbox coverage` | |
| `on` | `pull_request`, `branches: [main, "release/v*"]`, **no `paths`/`paths-ignore`** | A required context with a path filter stays "expected" forever on PRs it skips (#737). |
| trigger kind | `pull_request`, **never** `pull_request_target` | It executes PR code with the restricted token (the `tests.yml` reasoning). |
| `permissions` | `contents: read` | No GitHub API use at all. |
| `concurrency` | group `sandbox-coverage-${{ github.event.pull_request.number }}`, cancel-in-progress | Matches `tests.yml`. |
| job `sandbox-detector` | `name: sandbox-detector`; `ubuntu-latest`; `timeout-minutes: 10`; steps: `actions/checkout@v4` with `fetch-depth: 0`; `actions/setup-python@v5` `3.12`; run `python3 scripts/framework/sandbox_coverage_cli.py detect` | `fetch-depth: 0` makes `refs/remotes/origin/main` and full history (provenance, merge-base) available. |
| job `sandbox-coverage` | identical, running `coverage` | |

No venv step: the modules are stdlib-only (TD-D3). **TD verification item for the coder:** confirm on
the slice-1 PR's own CI run that `refs/remotes/origin/main` resolves in the `pull_request` checkout (the
tool fails closed with exit 1 if it does not, so a wrong assumption cannot pass silently).

### 9.2 Interaction with existing gates

- Once required, a red `sandbox-detector` on a worker PR is picked up by the overseer's
  `check_required_content_checks` bounce gate (`overseer.md:286`), which considers exactly the required
  list — i.e. it is routed back to the worker as worker-fixable, not to a human. That is the intended
  behaviour.
- The real-repo conformance tests (§13 `T-RP-*`) also run inside the existing required `tests` job and
  in `run_tests_inner_loop.sh`, so the worker sees an unbaselined finding **before** opening a PR.
  These call L1 directly and check exactness only (they cannot assume `origin/main` in every local
  clone); **closure is checked only by the `sandbox-detector` job.** One authority (L1), two call sites,
  no duplicated logic.

### 9.3 Promotion to required

**Iteration 2 (RC-4): the HOS-only contexts do NOT go into `setup_branch_protection.sh`'s literal
list.** That script ships to consumers (`framework_consumer_files.txt:64`). A consumer running it would
require `sandbox-detector`/`sandbox-coverage`, which nothing in a consumer repo produces, so every
consumer PR would stay "expected" forever (#737). ADR AM2-7(ii) records that the shipped list already
has seven such contexts; #1542 may not enlarge that defect.

**Mechanism (architect-ruled):**

1. **New file `scripts/framework/hos_required_contexts.txt`** — HOS-repo-only. It is **not** listed in
   `framework_consumer_files.txt`, not referenced by `hos_install.sh`, and protected via
   `scripts/framework/**`. Format: one context name per line; blank lines and `#` comment lines are
   ignored; every other line must match `^[A-Za-z0-9._-]+$`. A header comment states the file's purpose
   and that it is HOS-only. PR 2's content is two lines: `sandbox-detector` and `sandbox-coverage`.
2. **`setup_branch_protection.sh`** — before building `PAYLOAD`, if
   `${SCRIPT_DIR}/hos_required_contexts.txt` exists, the script reads it. Any line that fails the name
   pattern is a fatal error (`die`, before any API call), so the file cannot inject JSON. The valid names
   are rendered as a string of `, "<name>"` fragments in a variable (default empty, `set -u`-safe). That
   variable is appended **inside** the existing `"contexts": [ … ]` array, after the last literal
   element. The existing literal list stays byte-identical, so
   `test_branch_protection_contexts.py`'s regex extraction of the literal names keeps working. It sees
   the appended variable as a token without quotes and ignores it. If the file is absent, nothing is
   appended. Absence can only **narrow**, and only in a repo that never had the file; removing it from
   HOS is a protected-surface edit. `--dry-run` must print the appended contexts. The header comment
   gets one entry in the `#737` producer list explaining the file (rationale: "#1542 slice 1 —
   HOS-only required contexts; zero un-baselined findings by construction at seal; closed baseline per
   ADR-1542 AD-11/AD-19; kept out of the consumer-shipped literal list per ADR AM2-7(ii)").
3. **`tests/framework/test_branch_protection_contexts.py`** — `_required_contexts()` returns the
   literal list **∪** the file's names, so the existing "every required context has a producing job"
   test covers both lists (§13.4 `T-RP-05`, `T-RP-09`).

**Shaped to receive the pre-existing defect, which it does not fix.** The seven consumer-unproducible
contexts already in the literal list (`tests`, `oversight-gate-*`, `oversight-validator-*`) could later
move into this file. Moving them is AM2-7(ii)'s separate issue and is **not** done in this slice.

`test_branch_protection_contexts.py` then enforces that both new contexts have producing jobs. **The
live setting only changes when a human re-runs the script from the HOS repo** (it refuses bot callers),
per ESC-S1-2.

---

## 10. Ship-set (AD-14)

**Declared HOS-repo-only.** Reasons: the tool scans HOS's own agent documents; it is a required check
of this repository; no agent document names it, so there is no "agent file that names it" in which to
declare it, and the declaration is therefore made in **both module headers** (first docstring
paragraph: *"HOS-repo-only (ADR-1542 AD-14): not in `framework_consumer_files.txt`; consumer installs
do not receive it."*) and here. `framework_consumer_files.txt` is **not** modified; the six-uninstalled-
wrapper bug (AF-5) is neither fixed nor enlarged. The same applies to PR 2's
`scripts/framework/hos_required_contexts.txt` (§9.3, RC-4). It is HOS-only, and `T-RP-09` asserts it
is absent from the ship-set, so the consumer-required-context defect (AM2-7(ii)) is not enlarged
either.

**Why no mechanical AD-14 leg in slice 1 (TD-O6).** A leg asserting "every named wrapper is in
`framework_consumer_files.txt` or declared HOS-only" would give wrong answers today, because
`hos_install.sh:1898-1906` ships five `bootstrap/` files outside that list (§0.2 AV-12 correction).
Mechanizing AD-14 needs a single ship-set authority first. **Ruled (TD-O6, AM2-7(i)):** not mechanized
in slice 1; separate issue.

---

## 11. FR-9.1 — the "already covered" table, re-audited against *"invocable with literal arguments only?"*

Verdicts: **COVERED** (literal, self-deriving) · **COVERED-T** (literal, but the model must transcribe a
value from a prior literal call — AD-4 says the script should derive it) · **NOT-AGENT** (not
agent-invocable by design, and not needed autonomously) · **PROSE** (script fine, the documents invoke
it wrongly) · **NOT COVERED**.

| # | Entry (preliminary §3) | Verdict | Evidence | Routed to |
|---|---|---|---|---|
| 1 | `get_app_token.sh` | **NOT-AGENT** + **PROSE** | Output must be `source`d (header `:4-7`); sourcing is on CLAUDE.md's list. Autonomously unnecessary: `bin/hos-cron` mints pre-session and every wrapper mints internally. But `worker.md:389, :397` and `overseer.md:463` instruct `source <(bootstrap/get_app_token.sh …)`. | **slice 1b** (AM2-4: delete the instructions) — baselined `SB-SOURCE`/`SB-SUBST` |
| 2 | `revoke_app_token.sh` | COVERED | No arguments; reads `GH_TOKEN` from its environment (`:12-18`). | — |
| 3 | `query_issues.sh` | COVERED (FR-1.9 residual) | Literal modes; marker matching still needs `--contains/--author`. | slice 2 |
| 4–6 | `create_issue.sh`, `edit_issue.sh`, `post_comment.sh` | COVERED | `--body-file` only. | — |
| 7 | `post_review_thread.sh` | COVERED | `--pr <N> --body-file <path> --app <role>` (`:12`). | — |
| 8 | `create_branch.sh` | COVERED | `--issue <N> --slug <s>`. | — |
| 9 | `submit_pr.sh` | COVERED | AV-10's model of "covered". | — |
| 10 | `hos_repo_sync.sh` | COVERED (not needed autonomously) | Positional literal interval; launcher syncs. | — |
| 11 | `run_tests_inner_loop.sh` | COVERED + **PROSE** | No args. But worker-cron Step 4 wraps it in a two-command fence with `cd "$REPO_ROOT"`. | slice 3 (`$VAR`/`cd` sites) |
| 12 | `run_tests.sh`, `run_tests_release.sh` | COVERED | Optional literal flags. | — |
| 13 | `run_gates.sh` | COVERED (`bash` form only) | `--diff <ref>` is literal. File mode `100644` while its header documents `./scripts/oversight/run_gates.sh`, which would fail. Not invoked by the four documents. | note to `infra-reviewer`/FR-7 |
| 14 | `run_validators.sh` | **PROSE** (TD-VF-2) | worker-cron:123 invokes the no-argument form → fail-closed CRITICAL every time (`:126-134`). The literal scoped forms (`--diff <ref>`, `--step <N>`, file list) exist. | **standalone bug** (TD-O3 ruling; filed by the orchestrating session) — not baseline debt |
| 15 | `run_second_review.sh` | COVERED-T | `--score` transcribed from the risk-assessor's summary. | — (acceptable: the value is a judgement input, not repo state) |
| 16 | `run_review_chain.sh` | COVERED | `[--tier …] [--pr <N>]`. | — |
| 17 | `check_agents_static.sh` | COVERED | No args. | — |
| 18 | `cut_release.sh` | COVERED | Human-authorized verbatim command, literal flags. | — |
| 19 | `pre_pr_stale_check.py` | COVERED | `python3 -m …`, no args. | — |
| 20 | `check_pr_reviewed.sh` | **NOT COVERED as instructed**; COVERED-T available (TD-VF-5) | Still `<pr#> <head_sha> [root]` (`:20`); prompt feeds it from raw `gh api … --jq .head.sha` (overseer-cron:54). `merge_authority.sh human-approval` now emits `head_sha`. | slice 3 (AD-4 `--pr` retrofit) |
| 21 | `run_post_change_sweep.sh` | COVERED (HOS-only) | Literal ref/file forms. | — |
| 22 | `smoke_test.sh` | COVERED | No args. | — |
| — | **Added since the preliminary document** | | | |
| 23 | `merge_authority.sh` | COVERED | `--app --pr` (self-derives head SHA). | — |
| 24 | `pr_review.sh` | COVERED | `--tier` is a literal judgement input. | — |
| 25 | `escalate_to_human.sh`, `edit_issue_edges.sh` | COVERED | Literal flags, `--body-file`. | — |
| 26 | `select_work_candidates.py` | COVERED | AM-11 asserts the rendered form. | — |
| 27 | `pr_readiness.py` | **NOT COVERED** + **PROSE** (TD-VF-3) | Five required caller-supplied args (`:767-771`); prose passes three. | slice 3 (G3) for self-derivation; the prose defect is a **standalone bug** (TD-O3 ruling) — not baseline debt |
| 28 | `scripts/dev/commit_onto_base.sh` | **NOT COVERED** | #1552: prompts on a static invocation. | slice 4 |

**FR-9.1 findings and their routing** *(iteration 2, RC-9 — per the TD-O3 and TD-O7 rulings)*:
(1) the `run_validators.sh` no-argument invocation (TD-VF-2) and (2) the `pr_readiness` argument drift
(TD-VF-3) are **live correctness defects in literal commands, not baseline debt**. The detector
correctly does not flag them (N2). They are **filed as standalone bugs** by the orchestrating session
(architect review §F item 1). (3) The three `source <(get_app_token.sh …)` instructions are owned by
**slice 1b** (AM2-4: delete them). `git remote get-url origin` (`worker.md:65`, `overseer.md:46`) is
owned by **slice 2** (`--repo` defaulting). (4) **G13 is a deletion, not a build (AM2-5).** #1615
retired its trigger. `worker.md`'s "Out-of-scope commit bounce response (SPEC-328)" section and the
stale out-of-scope references in `overseer.md` (`:436`, `:572`, the `:635` worked example) are deleted
in **slice 1b**, and slice 7 is G12 only.

---

## 12. Empirical census (HEAD `5ee0412ba`) — indicative, not authoritative

### 12.1 Counts from the design prototype

A throwaway implementation of §3–§4 (block-scoped spans, ≥2-word floor, quote-aware segments,
`EXCLUDED_NAMES`) produced **156 findings**:

| By rule | | By document | |
|---|---|---|---|
| `SB-RAWAPI` 47 · `SB-FNCALL` 30 · `SB-RAWGIT` 17 · `SB-FNREF` 12 · `SB-SRCLIB` 10 · `SB-VAR` 10 | | `overseer.md` 82 | |
| `SB-CHAIN` 5 · `SB-SUBST` 5 · `SB-MULTI` 5 · `SB-PIPE` 4 · `SB-CONT` 3 · `SB-SOURCE` 3 | | `worker.md` 39 | |
| `SB-PYFENCE` 2 · `SB-LOOP` 1 · `SB-PYC` 1 · `SB-PYIMPORT` 1 · `SB-HEREDOC` 0 | | `overseer-cron-prompt.md` 23 · `worker-cron-prompt.md` 12 | |

The baseline written by `baseline-init` is authoritative, not this table. **If the implemented count
differs from 156 by more than ±25 %, the coder must reconcile the difference against §3–§4 before
sealing** (a divergence that large means a rule was implemented differently from its contract). The
slice-1 PR description must state the final per-rule and per-document counts and the debt/accepted
split.

### 12.2 Post-ADR sites (ESC-3 data; `introduced_at > 2026-09-12`)

From `git blame` on this clone (boundary-attributed lines are pre-ADR, since the boundary `823cea53` is
2026-09-11):

| Site | Commit | Nature |
|---|---|---|
| `overseer.md:337-340` — fence of two `GET /repos/{o}/{r}/…` reads (`SB-RAWAPI` ×2, `SB-MULTI`) | `f6a1aceb3` (#1657, 2026-09-24) | **New instruction** — an instance of a pre-existing class, added 12 days after the ADR. Owner `ADR-1542 slice 2` if absorbed (architect's ESC-S1-1 recommendation) |
| `overseer.md:585` — `require_human_approval.py::is_bot_reviewer` (`SB-FNREF`) | `f6a1aceb3` | descriptive function reference → **debt**, owner `ADR-1542 slice 1b` (AM2-1 corollary; iteration 2, RC-5(a)) |
| `overseer.md:435, :454, :751, :752` — "never a direct `POST /pulls/{n}/…`" (`SB-RAWAPI`) | `f6a1aceb3` | prohibitions → candidate `accepted` |
| `overseer.md:447, :449` — merge `PUT`, dismiss `PUT` | `f6a1aceb3` (rewrite) | pre-existing debt, re-worded (AV-3 already listed both) |
| `worker-cron-prompt.md:102` — "do NOT fall back to `gh api`" | `1e8d74479` (#1540 S2, 2026-09-27) | prohibition → candidate `accepted` |

No new call-a-function site (the AV-5 class) has landed since the ADR; #1580's (`overseer.md:286-289`)
predates it (2026-09-11).

### 12.3 Owner and disposition guidance for the slice-1 coder

Refinements to §6.5's defaults (everything else keeps its default):

| Sites | Owner | Disposition |
|---|---|---|
| `worker.md:363-369` lifecycle `SB-FNREF`; `overseer.md:228` `breakers.py:is_poisoned` | `ADR-1542 slice 8 — ESC-1` | debt |
| `overseer.md:447, :449, :753` merge/dismiss `PUT`; `:435, :751` request-reviewer | `#1357` | debt (447/449/753); accepted for the "never … directly" prohibitions |
| `overseer.md:154, :161, :182`, overseer-cron:38/48 audit-stream pipes and `audit_log.sh` refs | `#1538` | debt |
| **G13 section** — every finding in `worker.md`'s "Out-of-scope commit bounce response (SPEC-328)" section, incl. `SB-RAWGIT` `git revert`/`git cherry-pick` (`:463`, `:475`) and the Option-A credential-guard line's `git push`/`gh pr create` (`:501`) | `ADR-1542 slice 1b — G13 deletion (AM2-5)` | debt *(RC-5(b); was slice 7)* |
| Stale out-of-scope references in `overseer.md` (`:436`, `:572`, the `:635` worked example), wherever they produce findings | `ADR-1542 slice 1b — G13 deletion (AM2-5)` | debt *(RC-5(c))* |
| `source <(bootstrap/get_app_token.sh …)` (`worker.md:389, :397`, `overseer.md:463`) | `ADR-1542 slice 1b` | debt *(RC-5(c))* |
| overseer-cron:41-45 release-request listing (`MILESTONE=…` + `gh api … ${MILESTONE}`) | `ADR-1542 slice 1b — query_issues.sh --list --label release-request already covers it` | debt *(RC-5(c))* |
| `git remote get-url origin` (`worker.md:65`, `overseer.md:46`) | `ADR-1542 slice 2` | debt *(RC-5(d))* |
| `SB-RAWGIT` `git tag`/`git describe`/`gh release …` (worker.md:416-417, :511-512, :642) | `ADR-1542 slice 5` (release) | debt, except "never" lines → accepted |
| `SB-RAWGIT`/`SB-SUBST` `git show origin/main:…` (overseer.md:190), `git merge-base`/`git diff --name-only $(…)` (:241, :250) | `ADR-1542 slice 5` (VF-8, G2) | debt |
| overseer-cron:29-32 loop (incl. its `SB-SUBST`); both identity-guard lines per prompt; worker-cron `cd "$REPO_ROOT"` fences | `ADR-1542 slice 3` | debt |
| **Descriptive call-a-function / library references:** `overseer.md:585` (`::is_bot_reviewer`), `:758`, `:768`, `:810` (`post_comment()`), `:823` (`post_comment()` "remains the correct call") | `ADR-1542 slice 1b` | **debt** *(RC-5(a), AM2-1 corollary; were "accepted — descriptive reference" in iteration 1)* |
| Prohibition lists: `overseer.md:809` (`python3 -c "…post_comment(…)…"` — both its `SB-PYC` and `SB-FNCALL` findings), `:812-819`; `worker.md:370, :413, :440, :511-512` "never"-sentences; worker-cron:102, `:112` | — | **accepted**, rationale exactly `"prohibition example"` |

**Note on `:758`/`:768`.** These two are `SB-SRCLIB` findings, which is a shell-construct rule, so §6.3
would allow `accepted — descriptive reference` for them. RC-5(a) assigns them `debt` / slice 1b anyway.
That is the stricter choice, and it is applied as ruled.

The rule for the coder, applied entry by entry: **`accepted` only if the enclosing sentence prohibits the
construct (rationale `"prohibition example"`), or — for shell-construct rules only — names it without
instructing the agent to perform it (rationale `"descriptive reference"`); otherwise `debt`. A
call-a-function-family entry is never `accepted — descriptive reference`** (AM2-1; schema-enforced,
§6.3). When in doubt,
`debt` (stricter, and C2 permits moving it to `debt` later but not the reverse). The human reviewer of
the slice-1 PR confirms every `accepted` entry.

---

## 13. Tests

All under `tests/framework/`. Named cases are requirements; the coder may add more.

### 13.1 `test_sandbox_coverage_rules.py` — L1, pure (string fixtures only)

- **Extraction:** `T-EX-01` `bash` fence → shell-class logical lines; `T-EX-02` tilde fence; `T-EX-03`
  fence indented 3 spaces inside a list item; `T-EX-04` unclosed fence runs to EOF; `T-EX-05` inline
  span across two lines is one unit, `line` = opening line (TD-VF-1, the `has_human_approval(…)` case);
  `T-EX-06` double-backtick span containing a single backtick; `T-EX-07` unmatched backtick is literal;
  `T-EX-08` continuation join + `continued` mark; `T-EX-09` `#` comment lines skipped in shell fences
  only; `T-EX-10` HTML comment produces no unit.
- **Command shape:** `T-CS-01…12` — `bash x.sh --a` ✓; `$(…)` ✗; `for` ✗; `gh` ✗; `gh api` ✓;
  `audit_read_stream | grep x` ✓ (via `SHELL_LIB_FUNCS`); `MILESTONE=1 foo` ✓; `**Role: A | b**` ✗;
  `<!-- marker -->` ✗; `GET /repos/x` ✓; `bootstrap/x.sh` single word ✓; `$ git status --short` ✓
  (prompt marker stripped).
- **Placeholders:** `T-PH-01` `<approve|comment>` → no `SB-PIPE`; `T-PH-02` `<<EOF` still `SB-HEREDOC`;
  `T-PH-03` `<!--` untouched; `T-PH-04` `@@MILESTONE_NUMBER@@` → no `SB-VAR`.
- **Rules:** one test per §4.3 cell, named `T-R-<RULE>-P<n>` / `T-R-<RULE>-N<n>` — including
  **`T-R-FNCALL-P1580`** (the verbatim `overseer.md:286` sentence) and a **text-fence evasion** case
  `T-R-SUBST-P-TEXTFENCE` (`for pr in $(gh api x)` inside a ```` ```text ```` fence must fire).
- **`FN_INDEX` filtering:** `T-FN-01` builtins excluded; `T-FN-02` `get` excluded; `T-FN-03` a
  `_private` name included; `T-FN-04` a class name included; `T-FN-05` a call inside single quotes in a
  shell unit ignored, the same text in an inline span flagged; **`T-FN-06` (RC-3)** for the running
  interpreter, `(set(dir(builtins)) | set(dir(dict)) | set(dir(list)) | set(dir(str))) & FN_INDEX ⊆
  EXCLUDED_NAMES`, with `FN_INDEX` built from the real repository. A new Python version that introduces
  a colliding name fails this named test instead of silently changing the finding set; `T-FN-07`
  `EXCLUDED_NAMES` is a literal `frozenset` (AST check: L1 assigns it from a set/frozenset literal, with
  no call to `dir`).
- **`SB-RAWGIT` hardening (RC-7):** `T-R-RAWGIT-P8` — `git log --output=/tmp/claude/x.txt` and
  `git diff --stat --output /tmp/claude/x.txt` both fire, although `git log …` and `git diff --stat …`
  are otherwise in the read-only set.
- **Fingerprints:** `T-FP-01` stable under line shift; `T-FP-02` stable under whitespace re-flow;
  `T-FP-03` duplicate sites get occurrences 1 and 2; removing the first makes `2` stale; `T-FP-04`
  differs by doc; `T-FP-05` differs by rule.
- **Purity:** `T-PU-01` importing L1 performs no I/O (patch `open`, `subprocess.run` to raise).

### 13.2 `test_sandbox_coverage_baseline.py` — L1 baseline/coverage logic, pure

`T-BL-01` exact match → conformant; `T-BL-02` unbaselined finding → `unbaselined[]`; `T-BL-03` stale
entry → `stale[]`; `T-BL-04` C1′ added entry (new text, absent from the base docs) →
`closure.added[]`; **`T-BL-05` (RC-1)** rule rename (`SB-RAWAPI` → `SB-RAWAPI2`) over base docs plus one
new raw-API site at head → every old site admitted, **the new site is in `closure.added`**; **`T-BL-06`
(RC-1)** a new rule over unchanged docs → all its findings admitted; **`T-BL-10` (RC-1)** a newly scanned
document absent at base (empty `doc_texts` entry) with one finding → that finding is in
`closure.added` (a new document must be clean); a fingerprint-version change with unchanged docs → all
admitted; `T-BL-07` C2 `debt → accepted` flip rejected; `T-BL-08` `accepted → debt` allowed; `T-BL-09`
owner change allowed; `T-BL-11` X2 rules-list mismatch; `T-BL-12` schema errors each raise
`BaselineError`: unknown key, duplicate fingerprint, `accepted` without rationale, `debt` with
rationale, bad owner, `UNASSIGNED` owner, **the retired `ADR-1542 FR-7` owner (RC-5(e))**, and **an
`SB-FNCALL` entry `accepted` with rationale `"descriptive reference"` (AM2-1 corollary)**; `T-BL-13` C4
module-at-merge-base without baseline → error; `T-BL-14` C0 (module absent at both) →
`closure.status == "not_applicable"` and `not_verified` names it; **`T-BL-15` (RC-2)** module absent at
the merge-base but present at `origin/main` → stale-base error verdict; **`T-BL-16` (RC-6)** entries in
`B` not in `H` appear in `removed_since_base` with `doc/line/rule/text`, and the verdict exposes
`l1_changed_since_base` from `BaseState.l1_changed`; **`T-BL-17` (RC-8)** an unbaselined `SB-FNCALL`
finding whose fingerprint is in the base-scan set, with L1 unchanged → classified for the
"repo-function index grew" stderr cause. Coverage: `T-CV-01` missing script → `COV-MISSING`; `T-CV-02` `./x.sh` with
mode `100644` → `COV-NOT-INVOCABLE`; `T-CV-03` `bash x.sh` with mode `100644` → invocable; `T-CV-04`
`python3 -m a.b` without `__main__` → `COV-NOT-INVOCABLE`; `T-CV-05` namespace subpackage module
resolves; `T-CV-06` `lib/*.sh` reference is not a surface; `T-CV-07` single-word `.py` mention is not a
surface; `T-CV-08` legs inactive → `not_verified` contains the exact disclosure string and leg-2/3
findings are **not** reported; `T-CV-09` legs active with a fixture policy → `COV-NOT-ALLOWED` for a
missing entry, satisfied by an exact `Bash(bash <path> *)` entry, **not** satisfied by
`Bash(bash bootstrap/*)`; `T-CV-10` `COV-DANGLING` for an allow entry naming an untracked path.

### 13.3 `test_sandbox_coverage_cli.py` — L2 (temp git repositories)

Fixture: a temp repo built with `git init`, commits made with fixed author/committer dates, and
`refs/remotes/origin/main` created with `git update-ref`; `main(argv, repo_root=tmp)`.

`T-CLI-01` every subcommand prints exactly one JSON object with every envelope key; `T-CLI-02` unknown
subcommand → 2 with JSON on stdout; `T-CLI-03` no subcommand → 2; **`T-CLI-04` each of `--repo-root`,
`--baseline`, `--base`, `--doc`, `--force`, `--skip-closure`, `--json`, `-h` → exit 2 on every
subcommand**; `T-CLI-05` setting plausible override variables (`SANDBOX_COVERAGE_BASELINE`, `HOS_BASE_REF`,
`SANDBOX_COVERAGE_DOCS`; never `GIT_*`, which `git` legitimately reads) changes no output byte except
`computed_at`; `T-CLI-06` `scan` exits 0 with
findings present; `T-CLI-07` `detect` exits 3 on an unbaselined site; `T-CLI-08` `detect` exits 1 on an
unparseable baseline; `T-CLI-09` **closure:** base commit has module + baseline, head adds a site and a
matching entry → exit 3, `closure.added` names it; `T-CLI-10` `origin/main` absent → exit 1; `T-CLI-11`
`baseline-init` with module present at base → exit 3, file untouched (assert bytes); `T-CLI-12`
`baseline-init` under C0 writes a file that `detect` then accepts; `T-CLI-13` `baseline-prune` removes
a stale entry, preserves `disposition`/`owner`/`rationale` of the rest, adds nothing even with an
unbaselined finding present; `T-CLI-14` a tracked unparseable `.py` → exit 1 naming it; `T-CLI-15`
invoked as a subprocess from `/tmp` → identical JSON (cwd immunity); `T-CLI-16` shallow repo →
`baseline-init` writes `introduced_in: null` with a `not_verified` entry; `T-CLI-17` stdout is pure JSON
and every finding also appears on stderr in the `sandbox-coverage: …` form; `T-CLI-18` a `git`
subprocess timeout → exit 1; **`T-CLI-19` (RC-2)** a branch whose merge-base predates the module while
`refs/remotes/origin/main` has it → `detect` exits **1** with `error == "stale base: merge origin/main"`,
and `baseline-init` also exits 1; **`T-CLI-20` (RC-1)** end-to-end C1′ through real `git show`: base has
module + baseline; head renames a rule in L1 and adds a new site in a scanned doc with matching entries →
exit 3, `closure.added` contains only the new site; and a `git show <base>:<doc>` failure other than
path-absent → exit 1; **`T-CLI-21` (RC-6)** head edits L1 and removes a baselined site plus its entry →
exit 0, `removed_since_base` lists it, `l1_changed_since_base == true`, and stderr contains the
`NOTE L1 changed …` line. The same removal without an L1 change produces no NOTE line.

### 13.4 `test_sandbox_coverage_repo.py` — the real repository (runs in the inner loop and in `tests`)

`T-RP-01` L1 findings on HEAD's four documents == the committed baseline (X1 + X2) — the worker's
local early warning; `T-RP-02` coverage leg 1 on HEAD has zero findings; `T-RP-03` the baseline has
≥1 `debt` entry (**the slice gate's "detector red on today's documents"**, until FR-9.2 completes —
the test's docstring must say it is expected to be deleted when debt reaches zero); `T-RP-04`
`.github/workflows/sandbox-coverage.yml`: jobs named `sandbox-detector` and `sandbox-coverage`,
`pull_request` trigger, no `pull_request_target`, no `paths`/`paths-ignore`, `fetch-depth: 0`,
`permissions: {contents: read}` (this test may use the oversight venv's PyYAML — it is a test, not the
tool); **`T-RP-05` (PR 2, RC-4)** `scripts/framework/hos_required_contexts.txt` lists exactly
`sandbox-detector` and `sandbox-coverage`, every non-comment line matches `^[A-Za-z0-9._-]+$`, and
**neither name appears in `setup_branch_protection.sh`'s literal `contexts` array**; **`T-RP-09` (PR 2,
RC-4)** `hos_required_contexts.txt` is absent from `framework_consumer_files.txt` and is not mentioned
in `bootstrap/hos_install.sh` (it is HOS-only); `T-RP-06` every entry's owner matches the iteration-2
pattern (admits `ADR-1542 slice 1b`; rejects the retired `ADR-1542 FR-7`), none is `UNASSIGNED`, and
no call-a-function-family entry is `accepted` with a rationale other than `"prohibition example"`; `T-RP-07` L1 and L2 import only
`sys.stdlib_module_names` members plus L1 (AST walk); `T-RP-08` no `os.environ`/`getenv` reference in
L1 or L2 (AST walk).

**What these tests prove, stated per AD-13's distinction:** 13.1–13.2 prove the *rules and logic*;
13.3 proves the *wiring and the fail-closed paths*; 13.4 proves the *real repository is in the state the
gate claims*. None proves N1–N9 of §5.

---

## 14. Task breakdown

Two PRs, both within the ≤15-file / ≤10-commit limit (`worker-cron-prompt.md:106, :139`). Both touch
protected surfaces (`scripts/framework/**`, `.github/workflows/**`) and are CODEOWNERS-human-gated
regardless — correct for a new merge gate.

### PR 1 — detector, coverage check, baseline seal, advisory CI (11 files)

| # | Path | New/Mod | Content |
|---|---|---|---|
| 1 | `scripts/framework/sandbox_coverage.py` | new | L1 (§3, §4, §6, §7, §8.6) |
| 2 | `scripts/framework/sandbox_coverage_cli.py` | new | L2 (§8) |
| 3 | `scripts/framework/sandbox_coverage_baseline.json` | new | generated by `baseline-init`, then owners/dispositions refined per §12.3 |
| 4 | `tests/framework/test_sandbox_coverage_rules.py` | new | §13.1 |
| 5 | `tests/framework/test_sandbox_coverage_baseline.py` | new | §13.2 |
| 6 | `tests/framework/test_sandbox_coverage_cli.py` | new | §13.3 |
| 7 | `tests/framework/test_sandbox_coverage_repo.py` | new | §13.4 except `T-RP-05` |
| 8 | `.github/workflows/sandbox-coverage.yml` | new | §9.1 |
| 9 | `SCRIPTS-INDEX.md` | regenerated | `scripts/framework/gen_scripts_index.sh` |
| 10 | `DECISIONS.md` | appended | dated entry: rule set, seal counts (per rule / per doc / debt vs accepted), the post-ADR list (§12.2), and "advisory until PR 2" |
| 11 | `.github/CODEOWNERS` | regenerated **only if** `scripts/framework/regen_all.sh --check` reports drift (none expected) | |

Commit split (≤6): (a) L1 + rules/extraction tests; (b) baseline logic + coverage logic + their tests;
(c) L2 + CLI tests; (d) `baseline-init` run + §12.3 refinements + repo tests; (e) workflow + index +
DECISIONS. **Before (d), merge `origin/main`** so the seal absorbs everything landed to date; if main
moves again before merge, re-run `baseline-init` (permitted under C0) and refine any new entries.

### PR 2 — promotion to required (5 files; iteration 2, RC-4)

| # | Path | Content |
|---|---|---|
| 1 | `scripts/framework/hos_required_contexts.txt` | **new**, HOS-only: `sandbox-detector`, `sandbox-coverage` (§9.3) |
| 2 | `scripts/framework/setup_branch_protection.sh` | reads the file if present, validates names, appends to `contexts`; literal list **unchanged**; header entry (§9.3) |
| 3 | `tests/framework/test_branch_protection_contexts.py` | `_required_contexts()` = literal list ∪ file names |
| 4 | `tests/framework/test_sandbox_coverage_repo.py` | add `T-RP-05`, `T-RP-09` |
| 5 | `DECISIONS.md` | dated promotion entry, noting AM2-7(ii) is not enlarged |

PR 2 is the first change for which closure (C1′, C2) is **enforced** (the module exists at its base); its own
`sandbox-detector` run is the live end-to-end proof of the closure path. After PR 2 merges, the human
re-runs the script (ESC-S1-2).

**Explicitly not touched by either PR:** `.claude/agents/**`, `bootstrap/*-cron-prompt.md`,
`contract/**`, `scripts/framework/gen_sandbox_config.py`, `scripts/framework/framework_consumer_files.txt`,
`scripts/framework/check_agents_static.sh`, `CLAUDE.md`, any `prompts/**` file other than the prompt
artifacts the coder's own commits require.

---

## 15. Acceptance — the slice gate, made checkable

1. **"Detector red on today's four documents with every failing site enumerated":**
   `python3 scripts/framework/sandbox_coverage_cli.py scan` exits 0 with `counts.total > 0`, and every
   finding appears as an entry in the committed baseline (X1).
2. **"Check green":** `… detect` and `… coverage` both exit 0 on the PR 1 branch and in its CI run, with
   `closure.status == "not_applicable"` on PR 1 and `"enforced"` on PR 2.
3. **"No new baseline entries permitted after merge":** `T-CLI-09` passes, and on PR 2's CI run
   `closure.status == "enforced"`.
4. `coverage` output on HEAD contains the leg-2/3 inactivity disclosure in `not_verified`.
5. `bash scripts/framework/run_tests_inner_loop.sh` green; `bash scripts/oversight/run_gates.sh <changed
   files>` green (lint, type-check, secret-scan, portability) — on every changed file, not only new code.
6. `grep -n "environ\|getenv\|--force\|--skip\|shell=True\|2>/dev/null" scripts/framework/sandbox_coverage*.py`
   returns nothing.
7. The PR 1 description lists the final per-rule/per-document counts, the debt/accepted split, and every
   entry with `introduced_at > 2026-09-12` (§6.7).
8. **(iteration 2, RC-4)** After PR 2: neither `sandbox-detector` nor `sandbox-coverage` appears inside
   the literal `"contexts": [ … ]` array of `scripts/framework/setup_branch_protection.sh` (header
   comments may name the file that supplies them; `T-RP-05` asserts this); `scripts/framework/hos_required_contexts.txt` is absent from
   `framework_consumer_files.txt`; `setup_branch_protection.sh <owner/repo> --dry-run` (human-run) shows
   both contexts appended.
9. **(iteration 2, RC-2)** `T-CLI-19` passes: a stale-base checkout exits 1, never 0.

---

## 16. Open items

### 16.1 For `architect` — all RULED (architect review §C, 2026-10-03; ADR-1542 Amendment 2)

*(Iteration 2, RC-10: the iteration-1 questions are kept so the rulings have context. Each row is
closed and is not re-opened in this iteration.)*

| ID | Question (iteration 1) | Ruling | Where applied |
|---|---|---|---|
| **TD-O1** | Call-a-function rules fire whether or not a surface exists (TD-D5). | **RULED — accepted; AM2-1.** Corollary: for the call-a-function family, `accepted` only as a prohibition example. | §4.4, §6.3, §12.3 |
| **TD-O2** | Rules beyond AD-11's list (`SB-RAWGIT`, generalized `SB-RAWAPI`/`SB-PIPE`, `SB-MULTI`, `SB-SRCLIB`, `SB-PYFENCE`). | **RULED — all six stay**, with RC-7's `--output` hardening of `SB-RAWGIT`. | §4.2, §4.3, §13.1 |
| **TD-O3** | No slice owns pure-prose debt. | **RULED — new slice 1b "FR-7 residual prose sweep" (AM2-4)**; owner string `ADR-1542 slice 1b`. TD-VF-2/TD-VF-3 are standalone bugs, not baseline debt. | §6.1, §6.5, §11, §12.3 |
| **TD-O4** | AD-12's allowlist clause vs slice 9 (TD-D7). | **RULED — discharged by slice 9 (AM2-3).** | §7.3 (unchanged; now ruled) |
| **TD-O5** | This check is ADR-1357 AD-13 test 7. | **RULED — accepted (AM2-6)**; #1357 slice 6 consumes it and builds no second check. Annotation of #1357 is the orchestrating session's. | — |
| **TD-O6** | AD-14 not mechanized. | **RULED — accepted, separate issue (AM2-7(i))**; related defect AM2-7(ii) drives RC-4. | §9.3, §10 |
| **TD-O7** | G13's trigger retired by #1615. | **RULED — G13 is a deletion, in slice 1b (AM2-5)**; slice 7 is G12 only. | §11, §12.3 |

**No new architect question is raised in iteration 2.** One item is recorded because it was not fully
applied: **RC-3's literal contents.** The constant's derivation, location, form and guard tests are
specified in §4.4 and §13.1. The literal name list itself is not enumerated in this document, because
no CPython 3.12 interpreter was available to `technical-design` on this host (3.14.4 only). The coder
generates it under 3.12 in PR 1, and `T-FN-06`/`T-FN-07` verify it.

### 16.2 For the human (architect's sharpened forms, review §E)

ADR ESC-1, ESC-2 and ESC-3 are unchanged and still held. Slice 1 depends on none of them.

- **ESC-S1-1 — ESC-3's residue on slice 1.** *Question:* the seal will absorb #1657's post-ADR raw-API
  fence at `overseer.md:337-340` (two `GET` lines added 2026-09-24). Should it be absorbed as owned debt
  (owner `ADR-1542 slice 2`), or reverted / given a surface before slice 1 seals? **Architect
  recommendation: absorb it (ESC-3 option (b)).** Reverting would remove the #1207/#1657 two-list
  correctness fix, and slice 2's `query_prs.sh --reviews` plus `query_issues.sh --comments` is its
  surface. Post-seal additions need no ruling: AD-11 stands as clarified by AM2-2, and nothing new is
  admissible after the seal.
- **ESC-S1-2 — promotion is a human action.** *Action:* after PR 2 merges, re-run
  `setup_branch_protection.sh` **from the HOS repo**, which picks up `sandbox-detector` and
  `sandbox-coverage` from `scripts/framework/hos_required_contexts.txt` (§9.3). Per the #737 rule
  recorded in `DECISIONS.md`, do this only once both contexts have each produced at least one real run;
  PR 1's and PR 2's own CI runs satisfy that. **Recommendation: same day as PR 2's merge.** Until then
  the checks report but do not block.

---

## Human Review Required

**RISK: MEDIUM.** Slice 1 adds a new merge gate on every PR (once promoted) and a protected data file
whose closure semantics decide what may merge. A false positive blocks merges; a false negative is a
silent hole. Mitigations: the rule set is CLAUDE.md-grounded and examples-tested (§4.3); the gate is
green by construction at seal; promotion is a separate, human-executed step; every non-check is
disclosed in `not_verified` (§7.3) and every limit of the rule set is stated (§5).

**CONFIDENCE:** **HIGH** on §0 (every premise re-derived on `5ee0412ba`; the shallow-clone limit on
provenance is stated); **HIGH** on the CLI contract (§8 — inherited from ADR-1357 AD-2 and TD-1357, with
TD-1357's ARCH-1 lesson applied); **MEDIUM-HIGH** on the rule set (§4 — prototyped against HEAD and
corrected for four false-positive classes, but N1–N8 are real limits); **MEDIUM** on §12's counts
(prototype, ±25 % tolerance stated); **MEDIUM** on TD-D7/TD-O4, which resolves an ADR-internal
sequencing tension that `architect` must confirm.

**Change classification: `additive`.** This document creates a new contract surface (a module, a data
file, a CI check). It changes no previously-approved contract: no ADR-1357 decision is reversed (TD-O5
*consumes* AD-13 test 7 rather than redefining it), no existing check is altered, and the scanned
documents are not edited. The ADR's own requirement for an enumerated debt baseline and a required
check is implemented, not changed. Promotion to *required* is gated on a human action (ESC-S1-2).

**Startup-gap check (CORE).** *Should this have been settled before code was written against it?* The
detector itself is the ADR's remediation of a startup gap (ADR-1542 §6: nothing asked "what invokes
this?"), and nothing has been built against this design, so no sign-off is orphaned by it. Three
findings here **are** startup-gap-class against *existing* artifacts and are routed, not absorbed:
TD-VF-2 (the worker's validator call has been the fail-closed form), TD-VF-3 (`pr_readiness` prose cannot
run as written), and TD-O7 (G13's trigger retired under live prose). **Affected sign-offs:** none of the
three invalidates a register sign-off — no code was approved against them; they are documentation
defects in protected documents whose reviewers approved prose, not behaviour. Prior sign-offs on #1580,
#1657 and #1540 S2 **stand**: the detector is a forward control and baselines their sites as owned debt
rather than retroactively failing them.

**Iteration log:** iteration 1 of 5. Requesting `architect` review of the whole document, with
particular attention to TD-D4 (text-fence scanning), TD-D5/TD-O1, TD-D6, TD-D7/TD-O4 and TD-D8 (E1/E2
admissions).

### Iteration-2 addendum to the self-flag

**RISK: MEDIUM (unchanged).** **CONFIDENCE:** raised to **HIGH** on the closure semantics. RC-1's
base-scan rule closes iteration 1's rename hole. RC-2 closes the stale-base fail-open. Both are now
exercised by named tests through real `git` (`T-CLI-19`, `T-CLI-20`), not only in pure-logic tests.
**MEDIUM** on RC-3 until the coder pastes the 3.12 literal (§16.1).

**Change classification: `clarifying` for iteration 2.** Every edit applies an architect ruling or
required change to an unbuilt design. Nothing has been built or approved against iteration 1, so **no
sign-off is orphaned** and the affected-sign-offs analysis is empty.

**Startup-gap check on iteration 2's own changes.** *Should RC-1 and RC-2 have been settled in the
initial design?* Yes. Both are fail-open shapes in a merge gate, and both were caught by architect review
before any code existed. That is the loop working, not a startup gap against built work. RC-4 surfaced a
genuine pre-existing defect outside this slice (AM2-7(ii)), which is routed, not absorbed.

**Iteration log:** iteration 2 of 5. Requesting architect re-review: RC-1…RC-4 substantively, RC-5…RC-10
for presence.

---

## Architect review — iteration 1 (2026-10-03)

**Reviewer:** `architect`. **Verified against:** HEAD `1307f25f0` (this branch; `origin/main` `5ee0412ba`
plus this document's own commit). **Verdict: APPROVED WITH REQUIRED CHANGES.** The architecture is
right: a pure L1 / thin L2 split with no argv/env policy inputs, a closed fingerprinted baseline with
exactness *and* closure, an honest non-claims section, and inactive-but-disclosed allowlist legs. But
the closure check as written has a rename hole and a stale-base fail-open, the function-name exclusion
set is interpreter-dependent, and PR 2 would enlarge a consumer-blocking defect. Those are RC-1…RC-4
below and they touch the merge-gate semantics, so **iteration 2 comes back to me before `coder`**,
scoped to the RCs only. ADR-1542 is amended (Amendment 2, appended to the ADR) for the rulings that
change ADR text: TD-O1, TD-O3, TD-O4, TD-O5, TD-O6, TD-O7 and RC-1's interpretation of AD-11.

### A. Conformance with ADR-1542 and ADR-1357 AD-1/AD-2

- **AD-1/AD-2 contract — conforms.** One JSON object on every path including exit 2; stderr diagnostics
  never suppressed; 0/1/2/3 mapped; `schema_version`; no `--force`/`--skip-*`/env override; no path
  argument of any kind (correctly *not* copying `audit_predicate.py`'s `--allowlist <path>`, which is
  the ARCH-1 fail-open). Using exit 3 for "gate answered: non-conformant" is consistent with AD-2's
  "refused" and gives CI a red job; accepted.
- **TD-D2 (no L3 wrapper) — accepted.** AD-1's L3 exists to mint a token for an agent-invoked
  surface. This tool is CI-invoked, tokenless and named by no agent document. If a later slice ever
  instructs an agent to run it, the argv is already literal; it would still need no L3.
- **AD-8 (reads are reads) — conforms**, with one hardening (RC-7).
- **AD-10 — conforms.** Leg 1's "invocable *as named*" (exec bit required only for direct-path
  invocation) is the correct reading of "exists and is executable"; demanding `100755` for a
  `bash x.sh` invocation would be a spurious failure.
- **AD-11 — conforms in structure**, amended in scope by TD-O1 and in semantics by RC-1.
- **AD-13 — conforms.** §5 N1–N8 and the legs-inactive `not_verified` disclosure are exactly the
  honesty AD-13 demands. Keep N1 prominent: converting a flagged code span into prose ("call the API
  for the reviews") removes the finding and fixes nothing. CODEOWNERS on the four documents is the
  only control on that; RC-6 makes every debt reduction visible to that reviewer.
- **AD-14 — conforms for the module** (HOS-only, declared in both module headers since no agent file
  names it); **does not conform for PR 2** — RC-4.

### B. Spot-verification of the TD's factual claims (HEAD `1307f25f0`)

| Claim | Result |
|---|---|
| AV-4: `github.py` gained single-PR / reviews / files / commit getters | **HOLDS** (`get_pull :288`, `list_pull_reviews :300`, `list_pull_files :327`, `get_commit :357`, plus `submit_pull_review :416`, `request_reviewers :469`). **Count is wrong:** 14 public functions, not 13. Also, `get_branch_protection` (`:269`) already exists, so AD-2's "branch protection reads" residual is CLI exposure only — RC-9. |
| AV-3: `bootstrap/pr_review.sh` covers verdict + request-reviewer; `overseer_merge.sh` / `overseer_escalate.sh` absent | **HOLDS** (`pr_review.sh:13,:16,:133`). |
| AV-12: `hos_install.sh` copies five `bootstrap/` files directly | **HOLDS** (`get_app_token.sh`, `hos_repo_sync.sh`, `validate_setup.sh`, `apps.env.template`, `sync_apps_env.sh`, immediately before the `framework_consumer_files.txt` block). |
| G13 trigger retired by #1615 | **HOLDS** — `492826cf`; `overseer.md:275` records the retirement; no remaining producer of an `Out_of_scope_commits:` bounce. Stale out-of-scope mentions remain at `overseer.md:436`, `:572`, `:635`. |
| TD-VF-2: `worker-cron-prompt.md:123` runs `run_validators.sh` unscoped | **HOLDS** — the no-file branch at `run_validators.sh:125-134` writes a CRITICAL summary. |
| TD-VF-3: `worker.md:382` `pr_readiness` call lacks two required args | **HOLDS** — `--step` and `--risk-tier` are `required=True` (`pr_readiness.py:767-771`); the instructed call exits 2 every time. |
| #1657 raw-API prose at `overseer.md:337-340` | **HOLDS** — a fence of two `GET /repos/{o}/{r}/…` lines. |
| TD-VF-5: `merge_authority.sh human-approval --pr` emits `head_sha` | **HOLDS** (`merge_authority_cli.py:424`). |
| 15 textual `gh api` hits (4/4/3/4) | **HOLDS**. Clone shallow: **HOLDS**. |

### C. Rulings on TD-O1 … TD-O7

| ID | Ruling | Rationale |
|---|---|---|
| **TD-O1** | **ACCEPTED — the call-a-function rules fire whether or not a surface exists. ADR AD-11 amended (AM2-1).** Corollary: for `SB-FNCALL`/`SB-FNREF`/`SB-PYIMPORT`/`SB-PYC`/`SB-PYFENCE`, `accepted` is allowed **only** for prohibition examples, never for "descriptive reference". | The surface-existence test needs a registry that would drift; a function name in behaviour-driving prose invites `python3 -c` or narration either way. `post_comment()` "remains the correct call" (`overseer.md:823`) is an instruction, not a description. |
| **TD-O2** | **ACCEPTED — all six extended rules stay**, with RC-7's `--output` hardening of `SB-RAWGIT`. | Each is grounded in CLAUDE.md or AD-9, and each gives a later slice its red-to-green signal. `SB-MULTI` is not cosmetic: models do submit a multi-line fence as one Bash call, which is chaining. |
| **TD-O3** | **New slice 1b, "FR-7 residual prose sweep", after slice 1, no new code (ADR AM2-4).** Owner string `ADR-1542 slice 1b`. TD-VF-2 and TD-VF-3 are **not** baseline debt — they are live correctness defects in literal commands (the detector correctly does not flag them, N2), and are to be **filed as standalone bugs now** by the orchestrating session. | Prose that an existing surface already covers should not wait behind unrelated wrapper slices. TD-VF-3 means the worker's 8.9 gate cannot pass as written, and TD-VF-2 means every Step-4 validator run is CRITICAL. Those are running defects, not inventory. |
| **TD-O4** | **ACCEPTED — AD-12's allowlist clause for slices 2–8 is discharged by slice 9 (ADR AM2-3).** | The leg-2 activation in slice 9 enumerates *every* named surface at that moment, so an omission is a red required check, not a silent skip. Until then the disclosure in `not_verified` keeps the gap visible. |
| **TD-O5** | **ACCEPTED — slice 1's coverage check is ADR-1357 AD-13 test 7; #1357 slice 6 consumes it and builds no second one (ADR AM2-6).** The orchestrating session annotates #1357. | AD-10 already said "build it as one check, not two". Two document↔tooling checks is the #1135 duplicate-authority class. |
| **TD-O6** | **ACCEPTED — AD-14 is not mechanized in slice 1; separate issue (ADR AM2-7(i)).** Also, a second, related defect found in this review is recorded (AM2-7(ii)) and drives RC-4. | A ship-set leg against a non-authoritative list would give wrong answers. |
| **TD-O7** | **G13 becomes a deletion, not a build (ADR AM2-5).** `worker.md`'s "Out-of-scope commit bounce response (SPEC-328)" section and the stale `overseer.md:436/:572/:635` out-of-scope references are deleted in slice 1b. Slice 7 is G12 only. #1626 must ship any worker remediation path as an invocable surface. | No producer of that bounce remains, so the section instructs a response to an event that cannot occur. Per AD-6, a control the system does not run must not be written as an instruction. |

### D. Required changes for iteration 2 (design text only; `technical-design` applies them)

- **RC-1 — Replace E1, E2 and C3 with a single base-scan admission rule.** As written, E1 admits *every*
  entry under a rule absent from `B.rules`. A PR that renames `SB-RAWAPI` → `SB-RAWAPI2` (one protected
  edit) re-admits all old debt **and any new raw-API site added in the same PR**. Replace §6.4 C1/E1/E2/C3
  with: **C1′ — every `e ∈ H.entries` has `e.fingerprint ∈ B.entries ∪ FP(scan_headL1(base_docs,
  head_facts))`**, where `base_docs` = each `SCANNED_DOCS` path read via `git show <base>:<path>` (a path
  absent at base reads as empty; any other `git show` failure is exit 1). This admits exactly the
  pre-existing text (new rule, new scanned doc, fingerprint-version change, `FN_INDEX` growth) and
  nothing else. A newly scanned document that did not exist at base must be clean. Update §6.4's table,
  the TD-D8 paragraph, §8.2 `detect`, §8.5's `closure` payload (drop `count_growth[]`; keep `added[]`),
  and §13 (`T-BL-05/06/10` become: a rule rename plus a new site → the new site is in `closure.added`;
  a new rule over unchanged docs → admitted; a new doc absent at base with a finding → `added`). ADR
  AM2-2 states the interpretation this implements.
- **RC-2 — Close the C0 stale-base fail-open.** C0 keys on the merge-base, so any checkout whose
  merge-base predates PR 1 (a stale branch, or a CI checkout of the PR head instead of the merge ref)
  silently skips closure and exits 0. Amend C0: closure is `not_applicable` only if the module is absent
  at **both** the merge-base **and** `refs/remotes/origin/main`. Module present at `origin/main` but
  absent at the merge-base → **exit 1**, error `"stale base: merge origin/main"`. Add `T-CLI-19`.
- **RC-3 — Freeze `EXCLUDED_NAMES`.** Deriving it from the running interpreter makes findings depend on
  the Python version. CI pins 3.12, while this clone and the oversight venv run 3.14.4, so `T-RP-01`
  (which runs locally and in `tests`) can disagree with `sandbox-detector`. Make it a literal
  `frozenset` constant in L1, generated once from 3.12 plus `{"main"}`. Add `T-FN-06`: for the running
  interpreter, `(dir(builtins)|dir(dict)|dir(list)|dir(str)) ∩ FN_INDEX ⊆ EXCLUDED_NAMES`. On a new
  Python version a collision then fails a named test instead of silently changing the finding set.
- **RC-4 — PR 2 must not add HOS-only contexts to the consumer-shipped required list.**
  `setup_branch_protection.sh` ships to consumers (`framework_consumer_files.txt:64`); a consumer that
  runs it would require `sandbox-detector`/`sandbox-coverage`, which nothing in a consumer repo produces,
  blocking every PR (#737). **Ruling on mechanism:** add `scripts/framework/hos_required_contexts.txt`
  (HOS-repo-only, **not** in `framework_consumer_files.txt`, protected via `scripts/framework/**`).
  `setup_branch_protection.sh` appends its lines to `contexts` when the file is present.
  `test_branch_protection_contexts.py` covers both lists, and a new test asserts the file is absent from
  the ship-set. The file's absence can only *narrow*, and only in a repo that never had it. Removing it
  in HOS is a protected-surface edit. PR 2's file list becomes 5. Do **not** move the seven pre-existing
  unshipped contexts in this slice (AM2-7(ii)'s separate defect), but the design should note that the
  mechanism is shaped to receive them.
- **RC-5 — §12.3 and §6.5 owner/disposition corrections.** (a) Per TD-O1's corollary, the descriptive
  call-a-function refs (`overseer.md:585, :758, :768, :810, :823`) are **debt**, owner
  `ADR-1542 slice 1b`, not `accepted`. (b) The G13 sites (`worker.md:463, :475, :501` and the rest of
  that section) are owner `ADR-1542 slice 1b — G13 deletion (AM2-5)`, not slice 7. (c) `source
  <(get_app_token.sh …)` sites, the overseer-cron release-request listing, and the stale out-of-scope
  references are owned by `ADR-1542 slice 1b`. (d) `git remote get-url origin` is owned by
  `ADR-1542 slice 2`. (e) Extend the §6.1 owner pattern to admit `ADR-1542 slice 1b`, and retire the
  `ADR-1542 FR-7` owner string (every former FR-7 item now has a slice).
- **RC-6 — Make every debt reduction visible to the human reviewer.** Add to `detect`'s payload
  `removed_since_base[]` (entries in B not in H, with doc/line/rule/text) and `l1_changed_since_base:
  bool` (the L1 blob differs from base). When `l1_changed_since_base` is true and `removed_since_base`
  is non-empty, print one stderr line saying so. That combination is the rule-narrowing signature
  (N8), and CODEOWNERS review is the only control on it. Without this signal, a reviewer has to diff
  the JSON to notice.
- **RC-7 — `SB-RAWGIT`: an `--output` option disqualifies the read set.** `git log --output=<f>` and
  `git diff --stat --output=<f>` write files. Any `--output` / `--output=` argument in a `git` segment
  fires `SB-RAWGIT` even if the segment otherwise matches the read-only list. Add `T-R-RAWGIT-P8`.
- **RC-8 — §5: add N9 (index coupling).** A code-only PR that adds a repo function whose name already
  appears as `name(` in a scanned document creates a new finding in an unchanged document. RC-1 admits
  it as pre-existing text, but X1 still requires a baseline entry, so the PR becomes a
  protected-surface edit. State this as a known, accepted coupling. The stderr line for such a finding
  must name the cause ("text unchanged since base; repo-function index grew").
- **RC-9 — §0.2 factual corrections.** AV-4 row: "14 public functions" (not 13); add that
  `get_branch_protection` already exists, so slice 2's branch-protection item is CLI exposure only.
  §11 FR-9.1 findings list: replace "(4) G13's trigger retirement (TD-O7)" with the AM2-5 disposition,
  and route items (1)–(2) per TD-O3 (standalone bugs).
- **RC-10 — §16 and the iteration header.** Mark TD-O1…TD-O7 as ruled (cite this section), and replace
  ESC-S1-1/ESC-S1-2 with the sharpened forms in §E.

**Not required, noted:** PRs targeting `release/v*` resolve their closure base as the fork point from
`main`. That is coherent, because release-branch entries can only shrink relative to the fork, and it
needs no change. Restate it in one sentence in §6.4 so nobody "fixes" it with an env read of
`GITHUB_BASE_REF`, which §8.4 forbids.

### E. Human-held items — sharpened, not decided

- **ADR ESC-1, ESC-2, ESC-3** — unchanged, still held. Slice 1 depends on none of them.
- **ESC-S1-1 (ESC-3's residue on slice 1).** *Question for the human:* the seal will absorb #1657's
  post-ADR raw-API fence at `overseer.md:337-340` (two `GET` lines added 2026-09-24). Absorb it as
  owned debt (owner `ADR-1542 slice 2`), or require it reverted or given a surface before slice 1
  seals? **Architect recommendation: absorb it (ESC-3 option (b)).** Reverting would remove the
  #1207/#1657 two-list correctness fix, and slice 2's `query_prs.sh --reviews` plus
  `query_issues.sh --comments` is its surface. The sub-question about *post-seal* additions needs no
  ruling: AD-11 stands, and as clarified by AM2-2 nothing new may be admitted after the seal. I do not
  recommend amending it.
- **ESC-S1-2 (promotion is a human action).** *Action for the human:* after PR 2 merges, re-run
  `setup_branch_protection.sh` from the HOS repo. Per the #737 rule recorded in `DECISIONS.md`, do this
  only once both `sandbox-detector` and `sandbox-coverage` have each produced at least one real run
  (PR 1's and PR 2's own CI satisfy this). **Recommendation: same day as PR 2's merge.** Until then the
  checks report but do not block.

### F. Items for the orchestrating session (not decisions; architect cannot file or comment)

1. File two standalone bugs: TD-VF-2 (worker Step 4 runs `run_validators.sh` unscoped → CRITICAL every
   time) and TD-VF-3 (`worker.md:382` 8.9 `pr_readiness` call omits `--step`/`--risk-tier` → exits 2).
2. File the ship-set-authority issue (AM2-7(i)) and the consumer-required-context defect
   (AM2-7(ii): seven required contexts with unshipped producers in the consumer-shipped
   `setup_branch_protection.sh`).
3. Annotate #1357 with AM2-6 (test 7 is consumed, not built) and #1626 with AM2-5's binding note.
4. Annotate #1542 with AM2-3 as a `startup-artifact-gap`-class item.

**Iteration log:** architect round 1 of 5. Next: `technical-design` iteration 2 applies RC-1…RC-10.
Architect re-reviews RC-1, RC-2, RC-3 and RC-4 substantively, and the rest for presence.

---

## Architect review — iteration 2 (2026-10-04)

**Reviewer:** `architect`. **Verified against:** branch HEAD `99cedc00a`; the iteration-2 delta is
`git diff 7b61a313f 99cedc00a` on this file; ADR-1542 Amendment 2; `overseer.md:755-770`;
`.github/workflows/tests.yml:69-71`; `bootstrap/hos_install.sh:1908-1917`.

**Verdict: APPROVED WITH REQUIRED CHANGES. Ready for the coder, subject to RC2-1…RC2-4 below.** All
four RC2 changes are specified completely in this section, and they bind the coder **as written here**.
Where this section and the body differ, this section governs. `technical-design` folds them into the
body (§6.3, §6.4, §5, §8.2, §8.5, §12.3, §13) before PR 1 is opened. I will check that fold for
presence only; it is not another design round. RC2-1 is a correctness fix: a disposition-laundering
hole in closure that iteration 1 also had and I missed. RC2-2…RC2-4 are provenance, honesty and
consistency fixes.

### A. RC-1…RC-4 — substantive re-review

- **RC-1 (C1′): HOLDS.** §6.4 C1′ implements AM2-2 exactly. I stress-tested five edits. **Rule rename
  plus a new site:** the new text is absent from the base docs, so it lands in `added`. **Duplicate site
  inserted *above* a baselined one:** occurrences renumber, `occurrence 2` is not in the base scan, so it
  lands in `added`. This is correct: the count grew. **Site moved between documents:** `doc` is in the
  fingerprint, so it lands in `added`. This is correct and strict. **Baselined site edited but not
  fixed:** lands in `added`, the intended ratchet. **Fingerprint-version bump:** applied symmetrically
  by the head L1, so no special case is needed. The `B.entries ∪` term is redundant once X1 held at
  base, and it is harmless. **Residual:** closure fixes *which fingerprints* may exist. It does not fix
  *what disposition* a newly fingerprinted entry carries. That gap is RC2-1.
  Malicious edits to head L1 itself remain N8, disclosed, and now signalled by R1.
- **RC-2 (C0/C0s): HOLDS.** "Absent at both" closes the stale-base fail-open, and C0s is fail-closed
  (exit 1, `T-CLI-19`, acceptance item 9). In CI, the `pull_request` merge ref plus `fetch-depth: 0`
  puts the merge-base at the target tip, so a fresh PR is never C0s. **Disclosed, not a defect:** in a
  local clone whose `refs/remotes/origin/main` was never fetched after PR 1 merged, C0 holds and closure
  reads `not_applicable`. That is acceptable only because §9.2 already makes the `sandbox-detector` CI
  job the sole closure authority, and local runs check exactness only. Keep that sentence. One stale
  parenthetical remains (RC2-4(b)).
- **RC-3 (frozen `EXCLUDED_NAMES`): HOLDS in design. Item (a) is answered below.** It is a literal,
  AST-guarded (`T-FN-07`), and collision-guarded (`T-FN-06`). The finding set no longer depends on the
  interpreter. **Gap:** nothing verifies that the pasted literal actually *is* the 3.12 set. A literal
  generated under 3.14 would pass `T-FN-06` and `T-FN-07` on both interpreters. RC2-2 closes this.
- **RC-4 (HOS-only contexts): HOLDS.** Verified that `hos_install.sh:1908-1917` ships
  `scripts/framework/` **by list** (`framework_consumer_files.txt`), not by glob. An unlisted
  `hos_required_contexts.txt` therefore cannot reach a consumer. `T-RP-09` asserts that, and
  `setup_branch_protection.sh`'s "if present" read is a no-op in consumers. Name validation before any
  API call prevents JSON injection. The literal list stays byte-identical, so the existing regex test
  keeps working. AM2-7(ii) is not enlarged. PR 2 has 5 files. Correct.

### B. RC-5…RC-10 — presence

RC-5 (a)–(e): **present** (§6.1 pattern, §6.3 schema rule, §6.5, §11, §12.3, `T-BL-12`, `T-RP-06`). One
correction of my own ruling is in ruling (b). RC-6: **present** (R1 row, §8.5 payload, `T-BL-16`,
`T-CLI-21`). RC-7: **present** (§4.2, §4.3 P8, `T-R-RAWGIT-P8`). RC-8: **present** (N9, §8.5 cause line,
`T-BL-17`). Its wording is amended by RC2-3. RC-9: **present** (§0.2 AV-4: 14 functions and
`get_branch_protection`; §11 routing). RC-10: **present** (header, §16.1 ruled table, §16.2 sharpened
ESC-S1-1/2). Release-branch note: **present** (§6.4).

### C. Rulings on the three flagged items

- **(a) RC-3 literal not enumerated in the TD: ACCEPTED, conditional on RC2-2.** Producing the literal is
  mechanical, so the design does not need to contain it. A list typed here from memory or from 3.14
  would be worse than none. What the design must contain is a way to *verify* the literal, and RC2-2
  supplies it. The required `tests` job runs CPython 3.12 (`tests.yml:71`), so a version-gated equality
  test does run on every PR. The coder may generate the literal with any 3.12 interpreter, for example
  `uv run --python 3.12`, or a throwaway CI step. The PR 1 description must state the exact
  interpreter version and the one-line generating expression.
- **(b) `overseer.md:758`/`:768`: CORRECTED.** My iteration-1 RC-5(a) misclassified them. On HEAD,
  `:758` is `` `bootstrap/lib/comment_format_check.sh` `` and `:768` is
  `` `scripts/oversight/lib/detect_stack.sh` ``. Both are `SB-SRCLIB` (a shell-construct rule) inside
  explanatory prose that instructs nothing ("All three wrappers below call…", "same idiom as … in …").
  The AM2-1 corollary covers only the call-a-function family, so it does not apply. §6.3's rule governs
  and gives **`accepted`, rationale exactly `"descriptive reference"`**. The owner keeps the `SB-SRCLIB`
  default `#1538`. I am reversing my own ruling rather than keeping a "stricter" one, for three reasons.
  First, the iteration-1 basis was a factual error. Second, debt would assign slice 1b to "remove"
  accurate explanatory prose. The only way to do that is to strip the code-span backticks, which games
  the detector instead of fixing anything. Third, an inconsistent ad-hoc exception would weaken the one
  rule the human reviewer applies entry by entry. `:585`, `:810` and `:823` are call-a-function
  references and stay **debt / `ADR-1542 slice 1b`**, unchanged. The PR 1 human reviewer confirms every
  `accepted` entry, these two included (§12.3).
- **(c) RC-8 cause inference without a base function index: CONFIRMED, with a wording change (RC2-3).**
  The inference is sound with one exception. Assume L1 is unchanged (so `RULE_IDS`, `EXCLUDED_NAMES` and
  rule logic are unchanged) and the text is unchanged. The only input that can make an `SB-FNCALL` unit
  newly findable is then `RepoFacts.fn_index`. Building a base index would mean `ast.parse` over the
  base tree's Python files, which is cost with no gate value, because the line never changes the exit
  code. **The exception:** the same signature (admissible via the base scan, absent from `B`, L1
  unchanged) is also produced when **the base itself was non-conformant**. That happens when a site
  landed on `main` while `sandbox-detector` was advisory (the window between PR 1 and ESC-S1-2), or
  when a human merged over a red required check. In that case "index grew" is a misattribution, and a
  diagnostic must not assert a cause it has not established. RC2-3 fixes the wording and discloses the
  inheritance behaviour behind it.

### D. Required changes (binding as written; fold into the body before PR 1 opens)

- **RC2-1 — Close disposition laundering through new fingerprints (amends C2).** C2 compares
  dispositions only for fingerprints present in both `B` and `H`. A rule rename (or a fingerprint-version
  bump) gives every entry a new fingerprint, so C1′ admits them all (correctly) and C2 compares nothing.
  The same PR can then mark former `debt` entries `accepted`. R1 would list the removals, but nothing
  fails. That is exactly the "reclassify it as a prohibition" escape TD-D6 forbids. **New check C2′:**
  when closure is enforced, every `e ∈ H.entries` whose fingerprint is **not** in `B.entries` must have
  `disposition == "debt"`. Violations go in `closure.new_accepted[]` and exit 3. The C0 seal is exempt,
  because closure is `not_applicable` there and the seal assigns the initial dispositions. As a
  consequence, after the seal **no new `accepted` entry can ever be created.** A new or renamed rule that
  surfaces a prohibition sentence produces `debt`, and the remedy is to rewrite that sentence with a
  fragment span (§6.3, TD-D6). That is consistent with TD-D6's "no future change ever *needs* a new
  `accepted` entry". **Tests:** `T-BL-18` (rename plus a former-`debt` entry re-marked `accepted` →
  `new_accepted`, exit-3 verdict) and `T-BL-19` (fingerprint-version bump with an `accepted` entry
  carried across → `new_accepted`). Extend `T-CLI-20` to assert `closure.new_accepted == []` on its
  passing half. Add `new_accepted[]` to §8.5's `closure` payload.
- **RC2-2 — Prove the `EXCLUDED_NAMES` literal's provenance.** Add **`T-FN-08`**. When
  `sys.version_info[:2] == (3, 12)`, assert `EXCLUDED_NAMES == frozenset(set(dir(builtins)) |
  set(dir(dict)) | set(dir(list)) | set(dir(str)) | {"main"})`. On any other interpreter, skip with the
  reason `"EXCLUDED_NAMES provenance is verified only under CPython 3.12 (the tests job)"`. The required
  `tests` job runs 3.12, so this runs on every PR. Locally on 3.14 it is visibly skipped, never silently
  passed.
- **RC2-3 — Honest cause line and N10.** (i) In §8.5, change the `SB-FNCALL` cause text to
  `text unchanged since base and absent from the base baseline; L1 unchanged — repo-function index grew,
  or the base was non-conformant: <text>`. Change the other form to `text unchanged since base and
  absent from the base baseline — newly findable, or the base was non-conformant: <text>`. (ii) In §5,
  add **N10 — closure is relative to the base, not to the seal.** A site that reaches `main` without a
  baseline entry (during the advisory window before ESC-S1-2, or by a human merge over a red required
  check) is pre-existing text for every later PR. C1′ admits it, and X1 then forces the next PR that
  touches nothing related to add its entry. The control is to close the advisory window promptly
  (ESC-S1-2) and to treat a red `sandbox-detector` on `main` as a defect. The cause line makes the
  inheritance visible instead of attributing it to someone else's code. Update `T-BL-17` to the new
  text.
- **RC2-4 — Consistency fixes.** (a) §12.3: move `overseer.md:758`/`:768` out of the call-a-function
  debt row, give them `accepted`, `"descriptive reference"`, owner `#1538`, and replace the "Note on
  `:758`/`:768`" paragraph with ruling (b). (b) §8.2 `baseline-init`: change "(module absent at base)" to
  "(module absent at both the merge-base and `origin/main`; C0s is exit 1)". (c) §12.3: state that an
  Owner cell of "—" means *keep the §6.5 default*. Every entry, `accepted` ones included, carries an
  owner string matching the §6.1 pattern, which `T-RP-06` enforces. Never write `null` or `"—"`.

No ADR change is needed. C2′ refines TD-D6 within AD-11 as amended by AM2-2. AM2-2 governs which
entries are admissible, and C2′ governs their disposition.

### E. Human-held items — blocking status

| Item | Blocks coding PR 1? | Blocks merging PR 1? | Blocks later |
|---|---|---|---|
| ADR **ESC-1** | No | No | Slice 8 (lifecycle / `is_poisoned` debt owners) |
| ADR **ESC-2** | No | No | Slice 9 (policy templates; activation of coverage legs 2/3) |
| ADR **ESC-3** | No | No, because its slice-1 residue is ESC-S1-1 | Nothing further: post-seal additions are settled by AD-11 and AM2-2 |
| **ESC-S1-1** (absorb `overseer.md:337-340`?) | **No.** The coder seals under the recommended default (absorb as `debt`, owner `ADR-1542 slice 2`) | **Yes.** The human must answer it at or before PR 1's CODEOWNERS review. That review is where §6.7's post-ADR list is presented. If the answer is "revert", the revert lands as a separate protected-surface PR first, and PR 1 re-seals after merging `origin/main` (permitted under C0) | — |
| **ESC-S1-2** (re-run `setup_branch_protection.sh`) | No | No; it does not block PR 2 either | The **promotion** to required, after PR 2 merges. Per N10 (RC2-3), every day it slips is a day new sites can land on `main` and be inherited |

**Startup-gap check (CORE).** *Should RC2-1 have been settled in the initial architecture review?* No.
It is a property of this TD's closure design, and I should have caught it in round 1. It is caught
before any code exists. *Affected sign-offs:* none. Nothing has been built or approved against
iterations 1 or 2. Ruling (b) reverses a round-1 ruling of mine before anything was built on it, so no
orphaned approval exists.

**Iteration log:** architect round 2 of 5. Verdict APPROVED WITH REQUIRED CHANGES (RC2-1…RC2-4, fully
specified above). Next: `technical-design` folds RC2-1…RC2-4 into the body, and the architect checks
that fold for presence only. The coder may begin PR 1 against this document now, with this section
governing where it differs from the body.
