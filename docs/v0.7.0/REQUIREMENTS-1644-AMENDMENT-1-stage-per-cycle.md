# REQUIREMENTS-1644 — Amendment 1: stage-per-cycle — REQ-C re-derived under the Q4+Q6 ruling, plus stage routing

**Status:** DRAFT for `architect`. **Nine product/boundary decisions escalated to the human (§7, ESC-1…ESC-9).**
`architect` may proceed on the settled requirements in §3–§5. It MUST NOT bind the items each ESC names
until the human rules. **Change classification: STRUCTURAL** (see "Human Review Required").
**Date:** 2026-09-27
**Author:** pm-agent (autonomous bounded delta pass; no human was available during authoring)
**Amends:** `docs/v0.7.0/REQUIREMENTS-1643-1644-deterministic-agent-invocation.md` (the "joint doc").

---

## 0. Scope — read this first

**This amendment supersedes exactly two parts of the joint doc, and only for #1644:**

1. **§3.3 (REQ-C1…REQ-C8)**, replaced by §3 below; and
2. **§6 Track 3 (W13…W18)**, replaced by §6 below.

**Everything else in the joint doc is unchanged and binding**: §0 (VF-1…VF-12), §1, §2 (one primitive,
one result schema, two control-flow shapes), REQ-A, REQ-B, REQ-D, §4 non-goals, and Tracks 0–2. None of
them is re-derived here, and where this amendment cites them it cites them as settled.

**Binding inputs this amendment is written against:**

- The human's rulings on the joint doc's §5 (Q1–Q8), posted by ScottThurlow on #1643 on 2026-09-14T20:09Z
  (issuecomment-5670120181) and cross-referenced on #1644 at 20:09:24Z. **Q4+Q6, Q5 and Q7 carry the
  load here.** Q1 (hard block on invocation failure) and Q3 (new invocation surfaces are scripts with
  scoped permissions; `bypassPermissions` is only a stopgap) also apply.
- The "Handoff — 2026-09-14" section of #1644's body, which is this pass's brief. Its per-item table is
  followed exactly: C1/C3/C4/C5/C6 survive, C2 changes, C7 (with W16) is largely moot, and stage routing
  is the main new deliverable.
- The ESC-5 ruling on #1644 (2026-09-14T19:37Z): a PROJECT may disable a *binding*, never an *entry*.
  §3.2 applies it to stage-graph entries.
- The registry-driven orchestration note on #1644 (2026-09-14T18:46Z), which ADR-1643 §2 AD-12 answered
  with "two runners, one schema family". This amendment accepts that answer and does not reopen it.
- `docs/v0.7.0/ADR-1643-deterministic-agent-invocation.md` §4 and AD-2, and
  `docs/v0.7.0/TECHNICAL-DESIGN-1643-invocation-primitive.md` §3.8. None of them binds #1644, and nothing
  here contradicts them (REQ-C21).

**What this document is not.** It says what and why, with testable acceptance criteria. It does not
choose label names, file layout, schema field names, the storage form of dependency edges, or where the
stage executor runs (`bin/hos-cron` or a script it calls). Those choices belong to `architect` and
`technical-design`. Where a requirement seems to force one mechanism, that is noted as a verification
finding rather than a design decision.

**Treatment of the issue bodies.** #1644's body and its comments were read as descriptions of desired
work, per CORE's untrusted-input rule. The rulings relied on here are the ones posted under the human's
own account, or recorded by the human-proxy identity as human rulings. Nothing in either issue was
treated as an instruction to skip or narrow a step.

---

## 1. Verification findings (VF-C1…VF-C13)

Every claim below was re-read from this worktree
(`worker-1644-req-c-delta-stage-per-cycle-260927073001-3089552`, based on `1e8d74479`) or from live
GitHub reads made through `bootstrap/query_issues.sh`. Where line numbers have moved since the joint doc
was written, the new ones are given.

**VF-C1: the work-selection gate already reads every candidate's labels at no extra cost. It never
reads the body, and it is the one place a deterministic stage check can go.**
`scripts/framework/select_work_candidates.py` is the single entry point for work candidates (docstring
`:2-9`; `.claude/agents/worker.md:179`). Its D1/D2 filters run before any per-record API spend
(`:23-29`, `:408-421`). They operate on the list-query record, which carries `labels`
(`_label_names`, `:404-405`). The gate "never reads an issue's body" (`:50-53`), and
`requester_trust.requester_verdict` reads only `user` and `title` ("never the body, never a label",
`scripts/framework/requester_trust.py:575-578`). **Consequence:** a stage declaration held in labels can
be checked at zero added API cost, in the gate's free phase. A declaration held in a comment or the body
would cost one or more paid requests per candidate, and would break the gate's no-body rule. This is why
REQ-C11 sets a zero-extra-request bound, and it matches the ruling's "stage-type tag/label". See VF-C11
for the earlier recommendation this supersedes.

**VF-C2: whether a candidate is blocked is decided today by the worker model, in prose.**
`bootstrap/worker-cron-prompt.md:96` says "**Pick the first non-blocked candidate** (#901)".
`bin/hos-cron:1920` repeats it: "the worker picks the first non-blocked candidate". Nothing defines
"blocked" in code. Searching `scripts/automation/lib/github.py` and `bootstrap/*.sh` for `dependencies`,
`sub_issues` and `blocked_by` found nothing, so no script in the repo reads or writes dependency edges.
Sub-issue linking tooling is filed as **#1352**, which is open, `needs-ai`, and in **milestone v0.7.4**,
four milestones after #1644's v0.7.0. **This is the exact gap the human's ruling names:** a code-issue can
be picked before its spec-issue today, unless the model happens to notice.

**VF-C3: which stage runs is also decided by the model today.**
`bootstrap/worker-cron-prompt.md:112-115` ("Step 3 — Pipeline discipline") asks the worker to classify
each issue as "Spec/behavioral → pm-agent + architect + technical-design" or "Bug fix/tweak → proceed
directly". This is the model classification VF-8 of the joint doc identified, and under stage-per-cycle
it becomes the stage-routing decision.

**VF-C4: the #1349 taxonomy was decided but not implemented. `needs-worker` and `needs-overseer` are
not live anywhere.**
`DECISIONS.md:748-762` (2026-09-06) adopts `needs-worker` (a rename of `needs-ai`), `needs-overseer`
(new) and `needs-human` (unchanged). It records the decision only and defers implementation (`:758`).
`docs/LABELS.md:20-25` says "That migration has **not** happened yet". A grep of `scripts/`, `bin/` and
`.github/` for `needs-worker|needs-overseer` in `.py/.sh/.jq/.yml` files returned **zero** matches.
#1349 is **closed**. The implementation is **#1520**: open, `needs-ai`, v0.7.0, and it names a
consumer breaking change (`cps` would find zero eligible work after the upgrade, with no error) that
needs a dual-read or cutover plan. Also, `docs/LABELS.md` "Known gaps" says there is **no idempotent
label-provisioning path** and **no conformance test** tying label literals to the registry. A new stage
label namespace would inherit both gaps.

**VF-C5: under the #1540 S2 gate, child issues the worker's planner writes would NOT be trusted, so each
one would wait for a human authorizing act.**
`requester_trust.py:127-129`: `MACHINE_FILING_MARKERS` is "Closed against sub-issue filing (AM-10/D-7):
entries are REMOVED, never relaxed, the moment an emitting site becomes LLM-composed". `:585-591`: an
App-authored issue with no machine-filing marker gets `trusted-app-no-machine-filing-marker`, which is
untrusted. Planner decomposition is LLM-composed by definition. **Consequence:** the Q4+Q6 ruling's
"planner … decomposes … into linked issues (e.g. a spec-issue and a code-issue)" collides with a
security gate that was built on purpose. Every such child would stop at `gated`. Loosening the gate to
let children through would re-open the laundering path #1539/#1540 closed, because an untrusted parent
body would become a trusted child body. **→ ESC-2.**

**VF-C6: a cross-cycle "round" mechanism already exists (the PR bounce), with its own cap, and its
counter lives in clone-local audit state.**
`bin/hos-cron:1080-1110` routes the worker's open PRs to `needs-fix` / `needs-fix-bounce` /
`needs-attention` from draft state, labels, and review counts. The overseer caps bounces at
`bounce_count(cid) < 2` (`.claude/agents/overseer.md:273-274`, `:288-289`). `bounce_count`
(`scripts/automation/lib/merge_authority.py:1132-1149`) counts `pr-bounced` events in `audit/log/`,
and this clone's own `git status` shows thousands of untracked `audit/log/**` records, so that log is
not reliably durable across clones. Worker and overseer run in separate clones. **Consequence:** (a)
#1644's code rounds must not become a second, independently capped retry path next to the bounce path
(REQ-C2(g)); (b) a round counter derived only from `audit/log/` would not meet the ruling's "durable
(issue labels/comments)" requirement.

**VF-C7: the cap precedent keeps its counter in `.claudetmp`, which the ruling forbids for this use.**
`scripts/framework/validate_self.sh:67` sets `OUT_DIR=".claudetmp/framework"`; `:89` puts the pass
counter at `$OUT_DIR/self-review-pass-count`; `:181-182` increments it per invocation. The 0/1/3 exit
vocabulary carries over (REQ-C6). **The storage location does not** (REQ-C2(a)).

**VF-C8: two different `fingerprint()` functions exist.**
`scripts/oversight/validation_logic.py:223` (a JSON string over sorted files and class; the one ADR-1643
AD-6 binds; `load_ledger` is at `:272`, moved from the joint doc's `:170`/`:210`) and
`scripts/automation/lib/self_review_source.py:33` (a 16-hex sha256 prefix over the same inputs). They
agree on inputs and disagree on output format. Stuck detection compares fingerprints across cycles
through durable records, so mixing the two would make every comparison "different", and REQ-C3(i)
would never fire. REQ-C4 requires exactly one.

**VF-C9: the branch-ownership rule rules out "resume the previous cycle's branch". Cross-cycle work
continues today only through committed artifacts or the open-PR path.**
`bootstrap/worker-cron-prompt.md:110`: "Never continue work on a branch you did not create in this
cycle". `:133`: "Ownership is **recorded, never inferred**". `bootstrap/create_branch.sh:5-6` and
`:123` enforce it ("never adopts an existing branch"). The only sanctioned continuation of earlier work
is Step 1's open-PR handling (`worker-cron-prompt.md:85-93`: cherry-pick onto a fresh branch, then
force-push to the same remote branch name). #1354's design comment (2026-08-13T23:12Z, item 3) chose
stage-per-cycle partly *because* it leaves this rule intact: each stage reads a committed document on
`main`.

**VF-C10: the primitive is stateless by binding decision. The stage graph is reserved for #1644.**
ADR-1643 AD-2 (`:303-312`): no `--round`, no resume token, no parent-session awareness. TD-1643 §3.8
(`:933-937`) turns that into a prohibition. ADR-1643 `:587-597` says the worker's runner executes
"**exactly one** stage" per cycle, and that "the durable state *is* the mechanism — GitHub labels, issue
bodies, dependency edges". ADR-1643 §4 (`:762-769`) and TD-1643 `:1975` reserve `stage_label`,
`blocked_by`, `next_stage_on`, `cap` and `stuck_criteria` for #1644's own registry file, which shares
AD-9's format, ownership model and loader. ADR-1643 AD-7 (`:458-460`) gives `coder` **no** posture,
leaving it to this re-derivation.

**VF-C11: #1354 earlier recommended routing by a structured comment, not labels. The later ruling
supersedes that.**
#1354's comment of 2026-08-13T23:12Z ("Routing the handoff — RECOMMENDED, not yet confirmed")
proposed a `NEXT-STAGE:` comment block and argued against labels, citing drift and provisioning. The
human's Q4+Q6 ruling (2026-09-14) calls for "an explicit stage-type tag/label mechanism … a cheap,
deterministic label check". It is later, it is a human ruling, and VF-C1 supports it on cost grounds.
The #1349 ruling also reversed the "labels drift" premise (`DECISIONS.md:754`). **This amendment treats
labels as the stage-routing carrier, per the ruling.** #1354's structured block survives in a different
role: it carries the *reason* and the round record (REQ-C14), not the routing state. The drift concern
is answered by REQ-C10 (one taxonomy) and REQ-C15 (actor verification), not by avoiding labels.

**VF-C12: the timeout-side mechanisms #1644 must compose with are all still open.**
#1600 (measure chain duration), #1601 (attributed timeout counter), #1602 (WIP checkpoint), #1603
(streamed record) and #1604 (self-split after a detected timeout) are all open with `needs-ai`, in
v0.7.0. #1354 is the open tracking parent. #1604 sets the recursion bound this amendment adopts: the
original attempt, one split round, then a human.

**VF-C13: cross-vendor second review is tier-gated today.**
`.claude/agents/worker.md:379`, step 8.4: "Second review (MEDIUM+ tier only) — `scripts/run_review_chain.sh`
… At MEDIUM+ this invokes agy; at HIGH+ also codex." The Q5 ruling says a round may not declare itself
converged, and sends convergence confirmation through this mechanism. As written, a LOW-tier loop would
have no confirming actor. **→ ESC-9.**

**Verification gaps.** No behavior was run under `bin/hos-cron`. GitHub's native issue-dependency and
sub-issue APIs were not probed, so whether they meet REQ-C16's cost bound is an open design question,
not a finding. The live GitHub label set was not queried.

---

## 2. What the ruling changed, in one paragraph

REQ-C as first drafted described **one session that loops**: a script, inside one cron cycle, calling
`coder` and `code-reviewer` in turn up to a cap. The Q4+Q6 ruling replaces this with **a queue that
advances one step per cycle**. Each cycle runs exactly one stage (or one round) as a top-level
invocation, writes what happened to GitHub, and exits. The next cycle reads GitHub, decides what is
actionable, and continues. What moves out of the process is state: the round counter, the previous
round's findings, and the knowledge of which stage comes next all have to live in GitHub. They must be
readable by code, trusted only when written by the right actor, and read before any model turn is spent.
REQ-C1/C3/C4/C5/C6 are unchanged in intent. REQ-C2 and REQ-C7 change because their state and budget
assumptions changed. REQ-C9…C22 are new, because nothing previously had to answer "what does the next
cycle do".

---

## 3. REQ-C (revised) — carried-forward items

**REQ-C1 — Each stage is one REQ-A invocation made by deterministic code, and code judges whether it
completed.** *(Survives intact; wording adjusted for the cross-cycle shape.)* pm-agent, architect,
technical-design, coder, code-reviewer, and any other agent the stage graph names are invoked through
the primitive (`bootstrap/invoke_agent.sh`). **Code resolves which agent runs from the issue's declared
stage (REQ-C9). The worker model does not choose it.** Completion is read from the REQ-A8 verdict, never
from a model's summary.
- *AC:* for every stage in the graph, a test shows that the agent invoked is a pure function of the
  declared stage (and of the ESC-4 round rules). No prompt text in `worker.md` or
  `worker-cron-prompt.md` chooses between pipeline agents for staged work.
- *AC:* a stage whose invocation returns REQ-A7(i) (invocation failure) is not "complete". It follows
  REQ-C6's exit-3 path, consistent with Q1 (hard block, fail-closed).

**REQ-C2 — Every iterative loop has a hard round cap. The count is durable cross-cycle state.**
*(Re-specified. The finite, non-disableable floor is retained.)*
- **(a) Storage.** The round count for a loop can be rebuilt **from GitHub state alone**: labels,
  comments, events and linked PRs on the issue or its PR, written by verified HOS identities (REQ-C15).
  It is **never** held in `.claudetmp/` (VF-7 of the joint doc, VF-C7), and **never** only in the
  clone-local audit log (VF-C6). The audit log may mirror it but is not the source.
- **(b) Floor.** The cap is finite, has a documented maximum, and defaults to **3** (matching
  `SELF_REVIEW_MAX_PASSES`; reaffirmed by the Q8 ruling). No environment variable, flag or config value
  can disable it or make it unbounded. A PROJECT layer may lower it, never raise it above the documented
  maximum.
- **(c) Read before spend.** The next cycle reads the count **before any model turn** on that issue. A
  loop already at cap goes straight to escalation (REQ-C5) and invokes nothing.
- **(d) Fail closed on unreadable state.** A count that is missing where the stage record says one
  should exist, contradictory, unparseable, or written by an unverified actor is treated as **at cap**:
  escalate. It is never treated as round 1.
- **(e) Scope.** Applies to every loop the stage graph declares: code-phase rounds and plan-phase back
  edges (for example, architect rejecting requirements and sending the issue back to pm-agent). Each
  loop has its own count, and all counts are subject to the same floor.
- **(f) Reset.** Bot activity can never reset a count. Whether a verified human resume act starts a new
  budget is **ESC-6**.
- **(g) No second parallel retry budget.** The code-round cap and the overseer's existing bounce budget
  (`bounce_count(cid) < 2`, VF-C6) must be reconciled explicitly. One must subsume the other, or the
  design must state how they compose. **The worst-case total number of automatic worker attempts on one
  change must be stated as a number and be finite.**
- *AC:* delete the clone's `.claudetmp/` and `audit/log/` between two cycles. The next cycle still
  derives the same round number.
- *AC:* set any environment variable or config value to 0, a negative number, "unlimited" or a huge
  number. The effective cap stays at or below the documented maximum.
- *AC:* a corrupted or forged round record produces escalation, not a fresh round.

**REQ-C3 — The loop detects non-progress and bails on the round it detects it.** *(Survives intact.)*
"Stuck" means at least one of: (i) a finding with the same fingerprint recurs in consecutive rounds;
(ii) the blocking-finding count does not decrease from one round to the next; (iii) the reviewer's
verdict is unchanged although the diff changed materially. Detection is done **by code**, comparing the
current round's record with the previous round's durable record (REQ-C14), and the loop escalates on
that round without spending the remaining cap. Criterion (iii) needs a cross-cycle identity for the diff
(e.g. head SHA), which the round record must carry.
- *AC:* three fixture pairs of consecutive round records, one per criterion, each make the next cycle
  escalate with the matched criterion named. A fixture with a strictly decreasing count, no recurring
  fingerprints and a changed verdict does not escalate.

**REQ-C4 — Stuck detection uses exactly one `fingerprint()`, and never `load_ledger()`'s silencing.**
*(Survives intact, now settled by the Q5 ruling.)* **Within a convergence loop, recurrence always wins
and always escalates.** The ledger's silencing of findings with a resolving disposition applies only to
the one-shot validators it was built for. One fingerprint function is used for every round record
(VF-C8: two exist today with incompatible outputs). `architect` chooses which. ADR-1643 AD-6 already
binds `validation_logic.fingerprint()` for the shared layer.
- *AC:* a finding recorded `fixed` in any ledger that recurs in the next round escalates (REQ-C3(i)).
  A test proves the loop's code path cannot import or call `load_ledger`, matching TD-1643 T2.8.

**REQ-C5 — Non-convergence and stuck both exit to the existing human path, and the issue thread is the
record.** *(Survives; easier now.)* The outcome is the existing "a human decides fix / accept / file"
escalation (`needs-human`, today's `HUMAN_REQUIRED` form). It is not a new outcome class. The
round-by-round record already sits in the thread as durable round records (REQ-C14). The escalation
comment must **name the trigger** (cap reached, or stuck criterion (i)/(ii)/(iii)), **link each round
record**, and state what recurred. The human should not have to reconstruct it.
- *AC:* every escalation comment contains the trigger and a link to every prior round record for that
  loop. A test fails if either is missing.

**REQ-C5b — A loop cannot certify its own convergence. A distinct cross-vendor actor confirms it.**
*(New, from the layered part of the Q5 ruling.)* A loop only exits as *converged* after the existing
cross-vendor second-review mechanism (`scripts/run_second_review.sh`, reached today through
`scripts/run_review_chain.sh`) confirms it. The same-vendor loop's last "approved" verdict is not
enough. Per #1354's ruling on panels, all second-review arms for a round run **in one stage**, so no arm
can read another arm's committed output. A second-review rejection counts as a round result: its
findings feed REQ-C3's comparison and the round counts toward REQ-C2's cap. A second-review invocation
failure is REQ-A7(i), so it escalates and never passes as converged (Q1). Which tiers this applies to is
**ESC-9** (VF-C13).
- *AC:* no path moves a looped issue to "PR ready for overseer" without a recorded second-review
  confirmation for the final round, within the ESC-9 scope.

**REQ-C6 — Every stage uses the three-outcome vocabulary.** *(Survives intact.)* `0` means the stage is
complete or the loop converged: advance along `next_stage_on`. `1` means not converged but actionable:
the next round runs in a **later cycle**. `3` means escalate and do not auto-retry. There is **no fourth
convergence outcome.** The wrong-stage and malformed-state conditions of REQ-C12/C13 are **selection**
outcomes: nothing ran, so they are reported by the selector or pre-check, never as a stage result. A
cycle killed by the wall clock is a #1601 timeout, not a stage outcome (REQ-C7).

**REQ-C7 — RETIRED as written. Replaced by a residual requirement: "every stage fits one cycle".**
*(Largely moot per the handoff table.)* No nesting is left to budget: one stage per cycle means per-cycle
cost is bounded by the ordinary single-session budget (`HOS_CRON_MAX_SECONDS`, default 1800s,
`bin/hos-cron:308`). What remains:
- **(a)** Every stage in the graph declares its invocations' timeouts. When the graph loads, code checks
  that their sum plus a documented margin fits inside the cycle budget. A stage that cannot fit fails
  the load. It is not discovered at 1800s.
- **(b)** A stage killed by the cycle wall anyway is handled by the timeout mechanisms #1601
  (attributed counter), #1602 (WIP checkpoint) and #1604 (self-split, then escalate). #1644 builds **no**
  budget or resume mechanism of its own.
- **(c)** A timed-out stage **does not consume a convergence round** (it produced no verdict), but it
  does count under #1601's timeout counter. Both counters are finite, so repeated timeouts still end at
  a human.
- *AC:* a stage whose declared timeouts exceed the cycle budget minus the margin is rejected at load
  time. A timed-out round leaves REQ-C2's count unchanged and raises #1601's.

**REQ-C8 — Every stage transition gates something, so every transition goes through REQ-A and code.**
*(Survives, sharpened.)* Under stage-per-cycle, each transition decides whether the next stage may
start, so each counts as "gating" in the joint doc's sense. Non-gating, fast-feedback Agent-tool
dispatch **inside** a stage stays at `architect`'s discretion. It can never decide a stage outcome,
advance a stage, or open a PR.

---

## 4. REQ-C (new) — stage routing

This is the main new deliverable the handoff named. The human's ruling identifies four parts:
(1) issues declare their stage; (2) agents check it cheaply and deterministically before acting;
(3) there is a defined behavior when an agent lands on a stage it cannot act on; (4) decomposed issues
carry blocking edges. REQ-C9…C13 cover the first three, REQ-C16 the fourth, and REQ-C14/C15/C17 cover
what these rest on.

**REQ-C9 — Every issue in the worker's court declares exactly one stage, from a finite, registry-declared
vocabulary.**
- The stage vocabulary and the transitions between stages are **declared data**: #1644's own registry
  file, using ADR-1643 AD-9's format, ownership model and loader, with the graph keys ADR-1643 §4
  reserves (`stage_label`, `blocked_by`, `next_stage_on`, `cap`, `stuck_criteria` or equivalents).
  **They are not prose in `worker.md`.**
- The vocabulary must cover at least: a **plan/triage** stage (deciding whether to decompose), the
  **requirements**, **architecture** and **technical-design** stages (#1354's design chain), a
  **code round**, the **cross-vendor convergence confirmation** (REQ-C5b), and the **hand-off to the
  overseer**. `architect` may merge or split these. Stage names are `architect`'s.
- Per the Q4+Q6 ruling and VF-C1/VF-C11, the declaration is a **label or tag readable from the
  work-selection list record**, not from the body or comments.
- Per the ESC-5 ruling, applied here: CORE owns the existence of each stage-graph entry. A PROJECT may
  change *bindings* (for example, which agent serves a stage in its stack) but may never remove an
  entry, so a PROJECT can never skip a stage by configuration.
- *AC:* the loader rejects a graph with an unreachable stage, a stage with no outgoing transition that
  is not terminal, or a PROJECT overlay that removes a CORE entry.

**REQ-C10 — Stage is a sub-state of the #1349 pending-actor taxonomy. It is not a second, parallel
labelling scheme.**
- **(a)** The pending-actor label (`needs-ai` today, `needs-worker` after #1520) **remains the only
  eligibility and authorization carrier.** A stage label never makes an issue eligible, never authorizes
  it, and never overrides the `needs-human` exclusion (`select_work_candidates.EXCLUDED_LABELS`, `:99`).
  The S2 authorizing act (`docs/LABELS.md`, "The `needs-ai` authorizing act") is unchanged.
- **(b)** A stage label only means something on an issue in the worker's court. `architect` defines, as
  one rule, what happens to it when the issue moves to the overseer's or the human's court: kept as a
  "resume here" marker, or cleared.
- **(c)** Stage labels get rows in `docs/LABELS.md`, with the same writer / control-flow-effect columns
  as every other label. There is one registry, not two.
- **(d)** Provisioning and consumer migration follow the same plan #1520 adopts (dual-read or
  coordinated cutover), so a consumer is never upgraded into a silently empty queue (VF-C4). Sequencing
  against #1520 is **ESC-5**.
- *AC:* an issue carrying a stage label but no pending-actor label is never emitted as a candidate. A
  stage label applied to a `needs-human` issue does not make it eligible.

**REQ-C11 — The stage check runs in the selector, before any model turn, at zero added API cost.**
- `scripts/framework/select_work_candidates.py` stays the **single** entry point for candidates (AD-3 of
  TD-1540). Stage actionability is decided there, or by a deterministic step that consumes its output,
  **before** any model is invoked for the cycle. It is never decided by a model reading the issue.
- Reading the stage declaration adds **zero** API requests per candidate beyond the existing list query
  (VF-C1), and runs with the free filters, before the paid D5 walk (`:23-29`). Dependency edges
  (REQ-C16) may need paid requests. Those count against the gate's existing request budget, and running
  out of budget is DEGRADED (exit 3, "unknown"), never "not blocked".
- Every emitted candidate includes its stage, so no later step has to derive it again.
- *AC:* a test with a mocked `gh` shows that adding stage checks leaves the request count of a run with
  no dependency edges unchanged. No path from cycle start to the first model invocation contains a model
  call that decides stage.

**REQ-C12 — A malformed or ambiguous stage state is not selectable and is reported. It is never guessed.**
An issue with **more than one** stage label, an **unknown** stage label, a stage label written by an
unverified actor (REQ-C15), or a stage that contradicts the graph (for example, a code stage while a
declared blocker is open) is excluded and reported under its own reason, the same way the S2 gate
reports `gated` reasons. The one exception is an issue with **no** stage label, whose default is
**ESC-1**.
- *AC:* each malformed case is covered by a fixture and yields "excluded, reason X", never a candidate.

**REQ-C13 — Landing on a stage it cannot act on costs no model turn, writes nothing, and is recorded.**
Routing (REQ-C11) should make this impossible, but a label can change between selection and invocation
(for example, a human re-routes mid-cycle). So the stage executor **re-reads the live stage** just
before invoking. It also checks the stage's **preconditions** (for example, a code stage needs the
approved design artifact its graph entry names).
- On a mismatch or a missing precondition: **no model invocation**, no branch, no commit, no label
  change. An audit event records "stage mismatch", and the cycle continues or ends per `architect`'s
  rule.
- The mismatch is **not** a round (REQ-C2) and **not** a stage outcome (REQ-C6).
- The same issue hitting a mismatch on a documented number of consecutive cycles (recommended: 2)
  **escalates**, because it means the routing state is corrupt.
- The same applies inside a correctly routed stage: an agent that finds nothing it can act on (for
  example, `coder` given an issue with nothing to build) must **state** "not applicable" as a REQ-A8
  verdict (REQ-B3's principle). The executor routes that to escalation. It is never treated as "stage
  complete".
- *AC:* a fixture in which the stage label changes between selection and execution produces no
  invocation of `invoke_agent.sh`, no writes, and exactly one audit event.

**REQ-C14 — Code writes stage advancement and round records, in a durable, structured form.**
- After a stage outcome, **code, not the model**, writes the next stage (per `next_stage_on`) and posts
  a **structured stage/round record** on the issue (or on its PR, if the work item currently lives
  there). The record carries at least: stage, loop identity and round number, the REQ-A8 verdict, the
  fingerprint set of blocking findings, the blocking count, the identity of the diff or artifact (head
  SHA or committed-artifact path + SHA), and the writing identity. This is #1354's structured-block
  idea, reused as the record, not as the router (VF-C11).
- A cycle killed between finishing a stage and recording it must **not** silently re-run a completed
  stage as though it were fresh, and must **not** advance without a record. How this reconciles with
  #1602's checkpoint is `architect`'s decision. The requirement is that the next cycle can tell
  "done but unrecorded" from "not done", or else escalates.
- *AC:* the round record parses deterministically (no model). A killed-between-steps fixture either
  resumes correctly or escalates, and never double-counts or skips a round.

**REQ-C15 — Routing state is trusted only when the right actor wrote it.**
- Stage labels, round records and dependency edges count only when written by the HOS worker identity
  or by a **verified individual human CODEOWNER from their own account**. Verification uses the same
  events-API actor check `requester_trust.verify_codeowner_actor` already uses. **Any other actor's
  change is treated as malformed (REQ-C12).** Otherwise anyone with triage permission could relabel an
  issue from "requirements" to "code" and **skip the design chain**, which is a governance bypass.
- A verified human CODEOWNER **may** re-route (for example, send an issue back to pm-agent). That is the
  human back edge #1354 already decided. Bots other than the worker identity may not.
- A round record edited after posting is treated as untrusted, so escalate.
- The issue body is never routing evidence, consistent with FR5 of the S2 gate.
- *AC:* fixtures in which a stage label is applied by (i) an arbitrary collaborator, (ii) the human-proxy
  App, or (iii) `github-actions[bot]` all make the issue non-selectable with a reason. The same label
  applied by the worker App or a verified CODEOWNER is accepted.

**REQ-C16 — Decomposed issues carry explicit blocking edges. The selector excludes blocked candidates
deterministically.**
- Blocked-ness moves from the model's "first non-blocked candidate" judgment (VF-C2) into code. A
  candidate with any **unsatisfied** blocker is excluded before the model runs. The prompt text at
  `worker-cron-prompt.md:96` and `bin/hos-cron:1920` must then stop asking the model to judge it.
- What "satisfied" means (the ruling's "approved") is **ESC-3**.
- An edge that cannot be read, or has a dangling reference, is **fail-closed**: not selectable, and
  reported. A **dependency cycle** is detected and escalated.
- Edges are written **in the same operation that creates the child issues** (REQ-C17), so no split can
  leave a dependency implicit. #1604 calls this "the single most important acceptance criterion".
- The storage form is `architect`'s choice: native GitHub issue dependencies, sub-issues plus a declared
  order, or a structured record. It must meet REQ-C11's cost rule and REQ-C15's actor rule. The tooling
  dependency on #1352 (v0.7.4) is **ESC-5**.
- *AC:* a code-issue whose spec-issue blocker is unsatisfied is never emitted. Once the blocker is
  satisfied, it is emitted with no model involvement.

**REQ-C17 — The planner decomposes oversized work into linked issues, within bounds.**
- A **plan/triage stage** decides whether a unit of work fits the stage-per-cycle model or has to be
  split. When it splits: (a) it creates child issues **through the canonical scripts**
  (`bootstrap/create_issue.sh`, `bootstrap/edit_issue.sh`, plus whatever #1352 provides), never
  hand-rolled `gh`; (b) every child is created **with** its stage declaration and blocking edges
  (REQ-C16); (c) the parent becomes a **tracking parent** that is not itself selectable; (d) the parent
  carries a durable decomposition record listing its children and their edges.
- **Children never have more authorization than their parent.** Under the S2 gate an LLM-composed child
  is untrusted (VF-C5). Decomposition must never be a route by which an untrusted parent's content comes
  out as a trusted child. How children become selectable is **ESC-2**.
- **Recursion is bounded, consistent with #1604:** at most one level of planner decomposition per
  original issue. A child that needs to be split again escalates to a human.
- The #1604 timeout-triggered self-split and the planner split **must be one mechanism with two
  triggers**, not two splitters (CLAUDE.md "Use the Code, Don't Roll It Yourself").
- *AC:* a split produces children that each have exactly one stage, all edges present, and the parent
  marked non-selectable, all in one recorded operation. A second-level split attempt escalates instead.

**REQ-C18 — What the next cycle does is deterministic and stated.**
Candidate ordering between **in-flight** staged work (an issue mid-graph, or a round waiting for its next
cycle) and **new** work, and its interaction with #901's priority bands and with Step 1's open-PR-first
rule (`worker-cron-prompt.md:85-93`), is one documented, code-implemented rule. It is never model
choice. The rule itself is **ESC-8**.

**REQ-C19 — Code rounds that live on a PR reuse the existing PR routing, not a parallel scheme.**
Once a code round has an open PR, its next round goes through `bin/hos-cron`'s existing PR routing
(`needs-fix` / `needs-fix-bounce`, `:1080-1110`) and Step 1's open-PR path, extended as needed. #1644
does not add a second way of telling the worker "fix this PR". REQ-C2(g) governs how the caps combine.

**REQ-C20 — The branch-ownership rule is not relaxed.**
Stage-per-cycle must work under `worker-cron-prompt.md:110`'s "never continue on a branch you did not
create in this cycle" and `create_branch.sh`'s never-adopt rule (VF-C9). Work continues across cycles
**only** through artifacts committed to `main` (the #1354 pattern) or the existing open-PR path. If
`architect` finds neither works for some stage, that is a structural change to #967 and must go to the
human. It must not be designed around.

**REQ-C21 — Nothing in #1644 adds state to the primitive.**
Round, stage and resume information live in the stage executor and in GitHub. They are never passed to
`invoke_agent.sh` as flags or tokens (ADR-1643 AD-2; TD-1643 §3.8). An agent receives the prior round's
findings only as part of its **input file content**, assembled by the executor.
- *AC:* the existing TD-1643 §3.8 prohibition tests stay green, with no new primitive flags.

**REQ-C22 — Each stage runs under an explicit, scoped posture. `coder` is the open case.**
Per Q3, the plan-phase and review stages run through the primitive under explicit postures (ADR-1643
AD-7's `review-read-only` family or narrower). The primitive refuses `bypassPermissions` outright
(ADR-1643 `:452-453`). `coder` has no posture (VF-C10). It needs write access and test execution, and
#1678 showed that prefix-matched Bash allowlists are "either exploitable or inert". How the code stage
runs until a scoped posture exists is **ESC-7**.

---

## 5. The accepted latency tradeoff (recorded as the human accepted it)

**Accepted by the human in the Q4+Q6 ruling (2026-09-14), knowingly:** latency goes up. **A 3-round
code convergence now takes at least 3 cron intervals** instead of finishing inside one session. A design
chain takes at least one interval per stage (the three design stages, plus any back edges). A decomposed
issue adds at least one planner interval, plus the blocking wait for its spec-issue. The human's stated
reason: this is **the same tradeoff already accepted for the design chain via #1354**, applied
consistently, so it is **not a new class of cost**. In return, Q6's nested-budget risk (VF-11: up to 9
nested sessions inside 1800s) disappears by construction, REQ-C5's round-by-round record comes for free,
and a human can review each stage's artifact before the next stage runs (#1354 item 5).

**Requirement that follows (REQ-C23 — measure it, don't assume it):** each stage transition emits an
audit event carrying issue, stage, round and a timestamp. The number of cycles and the elapsed time per
issue can then be computed from records, feeding #1600's measurement. If measured latency turns out much
worse than "about one interval per stage", that is new evidence for the human. It is not a reason for a
worker to batch stages quietly.

---

## 6. Revised Track 3 — replaces W13…W18

Do **not** file these until `architect` and `technical-design` have run. They may merge, split or
reorder items. Items that touch protected surfaces (`select_work_candidates.py`, `bin/hos-cron`,
`.claude/agents/**`, `bootstrap/worker-cron-prompt.md`) go through the CODEOWNERS human gate as usual.

**Mapping from the retired items.** W13 (in-script cap, exit vocabulary) → T3.4. W14 (stuck detection)
→ T3.5. W15 (escalation record) → T3.6. **W16 (nested-invocation budget) → RETIRED** (REQ-C7; its
residual "fits one cycle" load check folds into T3.1, and timeout handling belongs to #1601/#1602/#1604).
W17 (code phase) → T3.7b. W18 (plan phase) → T3.7a, **re-ordered to go first**, because stage-per-cycle
for the design chain is #1354's already-decided pattern with no rounds, while code rounds are the new
and riskier part.

**Prerequisites outside #1644 (not re-scoped here, but sequenced against):** #1643's primitive (W1,
merged via PR #1720) and result schema (W2); ADR-1643 AD-9's registry loader; the #1520 migration design
(ESC-5); #1601 and #1602 (timeout counter, WIP checkpoint); the relevant part of #1352 (ESC-5).

- **T3.1 — Stage vocabulary and stage-graph registry** (REQ-C9, C10(b)(c), C7(a)). Declare stages,
  transitions, loop caps and stuck criteria as #1644's registry file on AD-9's loader, with the
  unreachable-stage, CORE-entry-removal and fits-one-cycle load checks, and `docs/LABELS.md` rows.
  *Designed together with #1520. Blocked on ESC-1, ESC-5.*
- **T3.2 — Deterministic stage pre-check in the selector** (REQ-C11, C12, C15 for labels). Extend
  `select_work_candidates.py`'s free phase: include stage in each emitted candidate, and add malformed
  and actor-unverified reasons. *Depends on T3.1. Protected surface. Must keep the S2 gate's
  request-budget and exit-code contract exactly.*
- **T3.3 — Blocking edges and deterministic blocked-exclusion** (REQ-C16). Choose the edge
  representation, add read and write paths through the canonical scripts, handle cycles and dangling
  edges, and remove "first non-blocked candidate" from the prompts. *Depends on T3.2. Blocked on ESC-3,
  ESC-5.*
- **T3.4 — Durable round records and the cross-cycle cap** (REQ-C2, C6, C14). Define the record format,
  deterministic parse, actor verification, fail-closed reads, killed-between-steps reconciliation, and
  the composition with `bounce_count` (REQ-C2(g)). *Depends on W2 and T3.1. Blocked on ESC-6.*
- **T3.5 — Cross-cycle stuck detection** (REQ-C3, C4). One `fingerprint()`, and never `load_ledger`.
  *Depends on T3.4. **The highest-subtlety item**: recommend its own TD section and adversarial review,
  as W14 had.*
- **T3.6 — Escalation and convergence confirmation** (REQ-C5, C5b). The escalation comment with trigger
  and round links, and the cross-vendor confirmation stage. *Depends on T3.5. Blocked on ESC-9.*
- **T3.7a — Plan-phase stage executor** (REQ-C1, C8, C13, C20, C21, C22 for read-only postures, C23).
  The design chain, one stage per cycle, with REQ-C2(e) back edges. *Depends on T3.2, T3.4.*
- **T3.7b — Code-phase stage executor** (the same requirements for code rounds, plus REQ-C19). *Depends
  on T3.5, T3.6, T3.7a. Blocked on ESC-4, ESC-7.*
- **T3.8 — Planner decomposition, unified with the #1604 self-split** (REQ-C17). *Depends on T3.3, and on
  #1604's own sequencing after #1601/#1602. Blocked on ESC-2.*
- **T3.9 — Prose retirement in `worker.md` and `worker-cron-prompt.md`** (REQ-C1, C18). Replace the
  Step 2 "first non-blocked" and Step 3 classification prose with the code paths above. *Last; depends on
  T3.7a/b. Blocked on ESC-8.*

**Recommended boundary if v0.7.0 runs short:** T3.1, T3.2, T3.4 and T3.7a make a coherent first release.
The design chain would run stage-per-cycle with deterministic routing and a durable cap, closing the
#1354 failure without taking on the code-round or decomposition risk. T3.3, T3.5, T3.6, T3.7b, T3.8 and
T3.9 can follow. ESC-2 and ESC-7 are the likeliest items to push work into a later milestone.

---

## 7. Escalated to the human

`architect` may proceed on §3–§5. It must not bind the items each ESC names until the human rules.

**ESC-1 — What is the stage of an issue with no stage label (every existing issue, and any hand-filed
one)?** Options: (a) it defaults to the **plan/triage** stage, so the planner decides; (b) legacy
behavior, meaning today's whole-issue worker flow; (c) not selectable until someone assigns a stage.
**PM recommendation: (a).** It strands nothing, costs one planner cycle, and sends every issue through
the same deterministic entry point. (b) keeps a second, un-routed path alive indefinitely. (c) turns
every existing `needs-ai` issue into a silently empty queue, which is the #1520 consumer failure again.

**ESC-2 — How do planner-created child issues become selectable, given that the #1540 S2 gate treats
LLM-composed filings as untrusted (VF-C5)?** Options: (a) **each child needs a human authorizing act**
(the existing CODEOWNER label act). This is safe and needs no gate change, but adds human latency per
child. (b) **Lineage inheritance:** a child is eligible if and only if its parent was authorized and it
is linked by a worker-App-written edge. This amends the S2 gate, a protected surface whose
`MACHINE_FILING_MARKERS` comment explicitly closes sub-issue filing (AM-10/D-7), so it is structural and
security-relevant. (c) **Stage-per-cycle within one issue by default:** the spec→code progression
happens on the **same** issue through stage labels (no new issue, no new authorization question), and
only genuinely multi-deliverable splits create children, which then fall under (a). **PM
recommendation: (c) with (a) for the remaining splits.** Note that the ruling's own example, "a
spec-issue and a code-issue", would under (c) be one issue with two stages, unless the human
specifically wants separate issues. Option (b) needs its own security review. This amendment does not
recommend it.

**ESC-3 — What does "approved" mean for a blocking spec-issue, i.e. when is a blocking edge satisfied?**
Options: (a) the blocker is **closed as completed**, meaning its design artifact merged to `main`
through the normal PR/overseer path; (b) (a) plus an **explicit human approval** of the spec before any
dependent code-issue is selectable; (c) the pipeline's own verdict (for example, architect/technical-design
PROCEED) with no merge required. **PM recommendation: (a).** It is deterministic and cheap to check,
and it matches #1354's "the next stage reads a committed document on `main`" (and REQ-C20). Human gates
then apply only where existing risk-tier and protected-surface rules already require them. (b) adds a
human gate to every decomposed item, which is a real policy choice. (c) lets code start on an unmerged
design, against REQ-C20.

**ESC-4 — What is the unit of one cron cycle in the code phase: a whole round (coder, then
code-reviewer), or a single invocation?** The ruling's "a 3-round convergence now costs at least 3 cron
intervals" reads most naturally as **one round per cycle**. Two sequential top-level primitive
invocations from the stage executor are not nesting. **PM recommendation: one round per cycle, as
read**, with REQ-C7(a)'s load check confirming that both invocations fit. Please confirm, because the
alternative doubles code-phase latency (at least 6 intervals for 3 rounds).

**ESC-5 — Sequencing against #1520 (label rename) and #1352 (sub-issue tooling, currently v0.7.4).**
Options: (a) stage labels ship **in the same consumer-migration window** as #1520's rename, so consumers
absorb one label breaking change; (b) stage labels ship on `needs-ai` first, and #1520 renames
everything later (two breaking changes); (c) #1644 waits for #1520 to finish completely. Separately:
REQ-C16/C17 need the part of #1352 that deals with edges/sub-issues in v0.7.x, ahead of T3.3. **PM
recommendation: (a), and pull the needed part of #1352 forward into v0.7.0 or the same milestone as
T3.3.**

**ESC-6 — After a cap or stuck escalation, does a verified human "resume" give the loop a new round
budget?** Options: (a) yes, one fresh budget per verified human resume act, with the prior records kept
and a second exhaustion escalating again; (b) no, a human must file a new issue; (c) the human chooses
the number of extra rounds. **PM recommendation: (a).** It matches "a human decides fix/accept/file",
keeps the loop finite because each budget costs one human act, and no bot can reset anything
(REQ-C2(f)).

**ESC-7 — How does the code stage run until a scoped `coder` posture exists?** VF-C10 and #1678 suggest a
genuinely scoped posture for a write-and-execute agent may not be buildable before the sandbox (#1542).
Options: (a) the code stage stays in the launcher's existing session under Q3's **stopgap**
`bypassPermissions`, with a recorded reason, while plan and review stages move onto primitive postures
now; (b) T3.7b is **blocked** until #1542 or a scoped posture exists; (c) a dedicated coder posture
is designed now as part of #1644. **PM recommendation: (a), explicitly time-boxed to #1542, re-evaluated
at each release as Q3 requires ("reconsidered every time, not treated as a default").** This is a
security-posture decision and belongs to the human.

**ESC-8 — Selection order between in-flight staged work and new work.** Options: (a) **in-flight
first** (an issue mid-graph, or a round waiting for its next cycle, beats any new issue regardless of
priority band), which bounds work in progress and per-issue latency; (b) strict #901 priority across both;
(c) in-flight first within the same priority band only. **PM recommendation: (a),** because it stops the
queue from starting many stage-1s and finishing none, and it matches Step 1's existing open-PR-first
rule. It does change #901's documented selection semantics, which is why it is escalated.

**ESC-9 — Which tiers need REQ-C5b's cross-vendor convergence confirmation?** It is MEDIUM+ only today
(VF-C13). Options: (a) **every tier**, following the ruling's "a round is not allowed to declare itself
converged" literally, with LOW using a single agy arm; (b) any loop that actually iterated (2 or more
rounds), at any tier, with single-round LOW-tier passes unchanged; (c) MEDIUM+ only, as today. **PM
recommendation: (a),** because the ruling states it without a tier qualifier. (b) is the cost-saving
fallback. (c) leaves LOW-tier loops certifying themselves, which is what the ruling forbids.

---

## Human Review Required

**RISK: HIGH.** This amendment specifies new routing state that decides which work runs and in what
order. It adds a deterministic filter to a protected, security-scoped gate (`select_work_candidates.py`).
It proposes a new autonomous write surface (planner decomposition, REQ-C17) that collides with the #1540
S2 trust boundary (VF-C5 / ESC-2), and it leaves a code-writing agent's permission posture open
(ESC-7).

**CONFIDENCE: HIGH on the findings, MEDIUM on the routing requirements.**
- *High* on §1: every VF cites a file:line read in this worktree or a live issue read. VF-C1 (labels are
  free in the gate, the body is never read), VF-C2 (blocked-ness is judged by the model), VF-C5 (children
  are untrusted under S2) and VF-C6 (the existing bounce budget is kept in clone-local state) are read
  directly from source.
- *Medium* on §4: stage routing is new, and its core choices (stage carried by label, same taxonomy as
  #1349, selector-side check, actor-verified state) follow from the ruling and from VF-C1. But four ESCs
  (ESC-1, 2, 3, 5) could each change the shape of T3.1–T3.3. The 2-consecutive-mismatch threshold in
  REQ-C13 and the default cap of 3 are recommendations, not measurements.
- *Not verified:* no behavior was run under `bin/hos-cron`, and GitHub's native dependency/sub-issue APIs
  were not probed for cost.

**Change classification: STRUCTURAL.** This amendment introduces new decision points (stage routing,
blocked-exclusion), a new state carrier (stage labels and round records), a new permission (a verified
human may re-route stages, REQ-C15), and a new autonomous write surface (decomposition). Under the
spec-update path every one of these requires explicit human sign-off before `architect` binds it. It
also supersedes a previously approved section (joint doc §3.3 and Track 3) under an explicit human
instruction (Q7 and the #1644 handoff). **No spec, agent definition, script, label or issue was changed
in producing it.** This file is the only artifact.

**Not done here, deliberately:** no test-plan sign-off (nothing is built yet); no register entry (this
is a requirements document, not a reviewed artifact); no spec-gap issues filed for the ESCs (the
orchestrating worker files and routes them per its own instructions, and this pass was told not to write
to GitHub).
