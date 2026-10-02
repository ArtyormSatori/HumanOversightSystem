# REQUIREMENTS-1644 — Amendment 2: ESC-8's exception on the PR side, under the ARCH-ESC-1 ruling (PM-6)

**Status:** DRAFT for `technical-design` (slice T3.0b). **Change classification: STRUCTURAL, human-ruled**
(ARCH-ESC-1). This document records the ruled semantics; it introduces no behavior beyond the ruling except
where §5 flags an open question. **Date:** 2026-10-02. **Author:** pm-agent (autonomous cycle).
**Amends:** `REQUIREMENTS-1644-AMENDMENT-1-stage-per-cycle.md` (adds REQ-C24). It closes ADR-1644 §7 PM-6.

## 0. Binding inputs

- **ARCH-ESC-1 ruling** (#1912): posted by the human-proxy App at 2026-10-02T04:52:48Z and ratified from the
  human's own account (`ScottThurlow`) at 04:55:46Z: *"(clear, bound 3) — relax #1198's serialization so new
  work isn't blocked while ≤3 worker PRs are human-pending; blocks at 3. PRs pending on the overseer keep
  blocking as today."*
- ADR-1644 AF-C2, AD-C6 (H4 row, T-NS5), §6 ARCH-ESC-1, and the T3.0b row ("behavior is preserved, except that
  H4 shapes no longer block new work. Closes #1847").
- #1198 (the serialization's rationale; #1162 is its prerequisite, now present in `bootstrap/submit_pr.sh`);
  #1847's acceptance criteria.

## 1. Verification findings (read from this worktree; line numbers as of `0eabb8685`)

- **VF-P1.** `bin/hos-cron:1048-1110` classifies the worker's open PRs into **one aggregate** routing value.
  Per PR, in order: `mergeable_state == dirty` → `needs-fix` (:1079); draft + `needs-ai` → `needs-fix-bounce`
  (:1085); `needs-ai` without `needs-human` → `needs-fix` (:1099, #1522/#1526); any `CHANGES_REQUESTED` review →
  `needs-fix` (:1105); zero `APPROVED` reviews → `needs-attention` (:1109). If no PR hits any of these, the result
  is `awaiting-merge`. Any open worker PR prints `NEW WORK: BLOCKED` (:1947-1962).
- **VF-P2.** A `HUMAN_REQUIRED` decision reaches the PR as the **`needs-human` label**. `merge_authority.py`
  applies it on every `HUMAN_REQUIRED` path (:579, :593, :611, :619, :645 and later) except two. :563 fires only
  when `needs-human`/`hos-halt` is already present. :633 applies `needs-ai` on a non-ESCALATE verdict, and
  VF-P1 routes that to `needs-fix`. The verdict text itself is an inline review comment (#1847), which needs
  paid reads. The label is already fetched (:1070-1078) at no extra cost.
- **VF-P3 (#1847).** A PR that carries `needs-human` and has an overseer `HUMAN_REQUIRED` verdict but no `APPROVED`
  review lands in `needs-attention`, and the worker is told "not yet reviewed". The overseer never posts `APPROVED`
  on protected-surface PRs (#1657).
- **VF-P4.** If the PR list fetch fails, `_OPEN_PR_NUMS` is empty (:1053-1054), so the directive prints
  `NEW WORK: ALLOWED` (:1964). This is fail-open, and it exists today (see §5 Q3).

## 2. REQ-C24 — Per-PR classification

T3.0b's classifier assigns **each** open PR authored by the worker identity to exactly one class. It
evaluates the classes in the order below, and the first one that matches wins.

1. **Worker-actionable**. This uses today's rules, unchanged and in today's order: `needs-fix` (dirty;
   `needs-ai` without `needs-human`; `CHANGES_REQUESTED` > 0) and `needs-fix-bounce` (draft + `needs-ai`).
   These rules take precedence over the human-pending checks, so a PR with `needs-human` that is also dirty,
   bounced, or has `CHANGES_REQUESTED` stays worker-actionable, as it is today.
2. **Human-pending (H4)**. Not worker-actionable, and **either** (a) the PR carries the `needs-human` label (this
   is the carrier for both the "HUMAN_REQUIRED" shape and the "`needs-human` on the PR" shape, VF-P2), **or**
   (b) it has ≥ 1 `APPROVED` review, which is today's `awaiting-merge` ("awaiting a human merge").
3. **Overseer-pending**. Every other open worker PR. This covers a PR with no review, a PR reviewed `COMMENTED`
   without `needs-human` (#1847 state 2), and any PR whose labels or reviews could not be read (the existing
   fallbacks at :1072 and :1103/:1107 produce this).

**Fail-closed rule.** The classifier counts a PR as human-pending **only** when it has positively read a
carrier listed in item 2. A HUMAN_REQUIRED verdict comment with no `needs-human` label is **not** a carrier.
Neither is `hos-halt` (see §5 Q2). Unknown state always resolves to a class that blocks.

## 3. REQ-C25 — The directive

Let **H** be the number of human-pending PRs. **The bound B = 3** is a fixed constant. No environment
variable, flag or config value can raise it.

| Condition (evaluated in order) | Directive |
|---|---|
| any PR is worker-actionable | `NEW WORK: BLOCKED`, using today's `needs-fix` / `needs-fix-bounce` reason and text, unchanged |
| any PR is overseer-pending | `NEW WORK: BLOCKED`, `needs-attention`, today's text, unchanged |
| H ≥ 3 | `NEW WORK: BLOCKED`. The reason uses a routing token **distinct from `needs-attention`**. It states that the PRs **are reviewed and are awaiting a human**, and it gives H, the bound, and the PR numbers |
| H < 3 (including 0 PRs) | `NEW WORK: ALLOWED`. When H > 0, the reason names the human-pending PRs and states H and the bound (e.g. "2 of 3") |

**Threshold interpretation (precision point).** The ruling and ADR §6 contain two phrasings: "while ≤ 3 …
human-pending" and "blocks at 3". They disagree at exactly H = 3. **This amendment reads it as ALLOWED iff
H < 3, BLOCKED iff H ≥ 3.** The reasons are as follows.
(i) "Blocks at 3" is the specific trigger the ruling states. "While ≤ 3" describes the queue the bound
maintains.
(ii) Overseer-pending PRs block. So each new-work start adds at most one PR, and that PR becomes
human-pending only later. With the H < 3 gate, the human's queue therefore tops out at 3, so "≤ 3
human-pending" holds. Allowing new work at H = 3 would let the queue reach 4 and break the stated bound.
(iii) Where two readings of a ruling differ, the stricter one is chosen.
The exact token and wording are `technical-design`'s to choose. The required content is fixed by the table
above.

**One decision authority (#1198 item 6).** `bootstrap/worker-cron-prompt.md` Step 1 must follow the directive
and must not restate a rule that re-blocks on `awaiting-merge`. When the directive is ALLOWED, the worker takes
no action on human-pending PRs beyond the visibility notice (REQ-C26) and proceeds to Step 2.

## 4. REQ-C26 — Visibility of a human-pending PR (#1847)

Each human-pending PR receives the one-time visibility notice that `awaiting-merge` PRs get today (the
`<!-- hos-worker-merge-block -->` pattern, `worker-cron-prompt.md:76`). The notice fires whether or not new work
is allowed. It uses a marker, so it is idempotent across cycles. For a `needs-human` PR, it says the PR is
waiting on a human decision. That content is TD's, but it must not say "not yet reviewed".

## 5. Acceptance criteria

- **AC-1 (T-NS5, restated).** There are two concrete H4 carriers (VF-P2), not three. Fixture: one open worker PR
  per carrier, plus an eligible issue. The carriers are (a) `needs-human` with a `HUMAN_REQUIRED` inline verdict
  and no `APPROVED` review (the #1845 shape) and (b) ≥ 1 `APPROVED` review with no other signal. Expected:
  `NEW WORK: ALLOWED`, the reason names both, and H = 2. Each carrier alone gives ALLOWED with H = 1.
- **AC-2 (bound).** Three human-pending PRs (any mix of carriers) plus an eligible issue → `BLOCKED`, with the
  distinct human-pending reason token. Four → `BLOCKED`.
- **AC-3 (overseer-pending still blocks).** One unreviewed PR plus 0, 1 or 2 human-pending PRs → `BLOCKED`,
  `needs-attention`, today's text.
- **AC-4 (worker-actionable precedence).** For each of the four `needs-fix`/`needs-fix-bounce` triggers, combined
  with up to 2 human-pending PRs → `BLOCKED` with today's reason and text. A PR that has both `needs-human` and a
  trigger (dirty, `CHANGES_REQUESTED`, or draft + `needs-ai`) → worker-actionable.
- **AC-5 (fail-closed).** If a PR's detail or review read fails, that PR is never counted as human-pending. A
  `HUMAN_REQUIRED` comment without the label, or `hos-halt` alone, → overseer-pending → `BLOCKED`.
- **AC-6 (#1847 closure).** These are the three fall-through states #1847 lists. (1) An unreviewed PR → `needs-attention`, with today's
  text. (2) A PR reviewed `COMMENTED`, with no `needs-human` → blocks as overseer-pending. (3) A PR reviewed
  `COMMENTED` with `needs-human` and `HUMAN_REQUIRED` → human-pending: never "not yet reviewed", and the notice is
  posted exactly once across two cycles. When these pass, #1847's acceptance criteria are met, adjusted by
  ARCH-ESC-1, which takes precedence over #1847's "blocks new work (unchanged)".
- **AC-7 (behavior otherwise preserved).** For every fixture with no human-pending PR, the classifier's directive
  is byte-identical to today's `bin/hos-cron`. The bound cannot be raised by env/config. The #1162 merge-from-base
  guard in `submit_pr.sh` is not modified.
- **AC-8 (zero added requests).** The human-pending carriers come only from fields today's routing already reads.
  A mocked-`gh` request-count test shows no increase.

## 6. Open questions (not resolvable from repo state; defaults above are the conservative ones)

- **Q1: T-NS5's wording.** ADR AD-C6 says "one open PR in each H4 shape", which names three shapes. Read
  literally as three PRs, H = 3 and the ruling blocks, which contradicts T-NS5's expected `ALLOWED`. AC-1 resolves
  this by collapsing the shapes to two carriers (VF-P2). `architect` should confirm. This is a clarification of
  the test, not of the ruling.
- **Q2: `hos-halt` on a PR.** It is a human-gate label (`merge_authority.py:494`), but it is not named in H4.
  The default is to block. Whether a halted PR should count toward H, and so release new work, is for the human
  to decide.
- **Q3: VF-P4's fail-open.** On a PR-list fetch failure, today's directive prints `ALLOWED`. Closing that hole
  changes existing behavior outside H4, so it is not required here. The recommendation is to file it as a
  spec-gap for a human decision.
- **Q4: stale approvals.** Carrier (b) counts any `APPROVED` review, as `awaiting-merge` does today, even one on
  an older head SHA. That behavior is preserved, and it is flagged rather than changed.

## Human Review Required

**RISK: MEDIUM.** The amendment specifies the relaxation of a deliberate safety serialization (#1198), which is a
protected surface (`bin/hos-cron`). The human ruled on the relaxation itself. The threshold reading and the
fail-closed defaults are PM choices within that ruling. **CONFIDENCE: HIGH** on VF-P1 to VF-P4, which were read from
source and from #1847/#1912. **MEDIUM** on the threshold reading, which is stated with its rationale. Q1 to Q4
are open. **Classification:** this records a STRUCTURAL change that the human ruled on (ARCH-ESC-1). The
precision points in §2 and §3 are clarifying and make the ruling's implicit content explicit. Each of them
chooses the stricter option. Nothing in Q1 to Q4 is bound without a ruling. No spec, agent file, code, label
or issue was changed. This file is the only artifact.
