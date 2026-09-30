# Prompt Artifact — select_work_candidates.py

| Field | Value |
|---|---|
| **Generated file** | `scripts/framework/select_work_candidates.py` |
| **Description** | #1644 T3.0a D2b native-blocker and parent exclusion (free filter) |
| **Date** | 2026-09-30 |
| **Model** | claude-opus-5-5 |
| **Risk level** | HIGH (coder/TD declared MEDIUM; risk-assessor raised on deterministic floors) |
| **Human review status** | ⬜ Pending |

---

## Prompt

Dispatched by the autonomous worker to the `coder` subagent (exact text):

```
You are implementing the SELECTOR half of #1644 slice T3.0a in the HOS repo at /home/scott/Code/HumanOversightSystem/Worker (branch `worker-1644-t3-0a-no-idle-selection-260930181001-4069397`, already checked out — do NOT create or switch branches, do NOT commit, do NOT push, do NOT file issues or touch labels).

Binding design: `docs/v0.7.0/TECHNICAL-DESIGN-1644-T3.0a-no-idle-selection.md` (architect-approved). Read it in full, especially §2 (D2b predicate, constants, types, exact function signatures, rule order R1–R5), §3 (report/exit deltas — exact stderr line texts and emission order, `_report_and_exit` signature delta: two params after `ceiling_refused_at_list`, no `*` marker), §6 (fixtures), §7.1, §7.2, §7.4, §8. Controlling ADR: `docs/v0.7.0/ADR-1644-stage-per-cycle.md` (AD-C4, AD-C6, Erratum 1).

YOUR FILES (only these):
1. `scripts/framework/select_work_candidates.py` — add D2b (`_nonneg_int`, `_dependency_counts`, `_sub_issue_total`, `_native_verdict`, `_NativeVerdict`, `_FreeFilterResult`, constants `NATIVE_EXCLUSION_REASONS`, `UNEVALUATED_EDGE_SUMMARY`, `_EXCLUDED_LIST_BOUND`), change `_apply_free_filters` to return `_FreeFilterResult` and update `main`, the §2.5 REFUSED-path accounting, the §3.2 stderr lines in the §3.2 emission order, the docstring algorithm line and the §2.6 paragraph verbatim.
2. `tests/framework/test_select_work_candidates.py` — TD-F2 fixture correction (`_issue` gains `deps`/`subs` overrides with `_OMIT` sentinel; the two raw literals in `test_missing_or_null_labels_does_not_crash` gain zero summaries; PR literals NOT changed) plus exactly the two §8 test changes (rename to `..._four_named_reasons` with the new term; add the new token to the forbidden tuple). No other expectation changes.
3. `tests/framework/test_select_work_candidates_native.py` (new) — T-NB1..T-NB13, T-EX1..T-EX6, T-NS1, T-NS2 (as `pytest.mark.xfail(strict=True, raises=AssertionError, reason="in-flight ordering is T3.2's gate (ADR-1644 Erratum 1, E1)")`, NO T-NS2-pre), T-NS3a, T-NS3b, T-NS4a, T-NS4b, T-ZC1, T-ZC3, T-ZC4. T-NB7's docstring must state the #51 limb pins T3.0a's scope and T3.2 inverts it. T-NS4b's docstring must state it pins the H5 limit.
4. `tests/framework/test_select_work_candidates_ghshim.py` (new) — T-ZC2 PATH-level fake `gh`, exactly per §7.2.
5. `tests/automation/test_hos_cron.py` — `_candidates_json` gains zero summaries + optional 4th tuple element overriding `issue_dependencies_summary`; add T-HC1 (§7.4).

Do NOT touch any other file (another coder owns bootstrap/escalate_to_human.sh, its tests, worker-cron-prompt.md, LABELS.md, CLAUDE.md, SCRIPTS-INDEX.md). Do not touch requester_trust.py or bin/hos-cron.

Reuse existing fixtures (`gate_repo`, `stub`, `run_gate`) from the existing test module — import or duplicate as the TD says. Match surrounding code style and comment density.

Verify with the oversight venv: `scripts/oversight/.venv/bin/python -m pytest tests/framework/test_select_work_candidates.py tests/framework/test_select_work_candidates_native.py tests/framework/test_select_work_candidates_ghshim.py tests/framework/test_selection_call_sites.py tests/automation/test_hos_cron.py -q` — all must pass (T-NS2 reports xfailed). Also run black/ruff if configured for these paths (check `scripts/oversight/.venv/bin/`).

Return: list of files changed, test results (counts), any deviation from the TD and why, and your self-flag (RISK/CONFIDENCE/BLAST RADIUS per AGENTS.md). If the TD is ambiguous or wrong on any point, say so explicitly rather than guessing silently.
```

## Constraints Specified

- Binding spec: `docs/v0.7.0/TECHNICAL-DESIGN-1644-T3.0a-no-idle-selection.md` §2, §3, §6, §7, §8, §10.
- Pure predicate: reads only `issue_dependencies_summary` and `sub_issues_summary`; no network, filesystem or clock.
- Zero added GitHub requests; no new exit-2 path; no trust input.
- Provenance: the prompt's "§2.6 paragraph verbatim" refers to this repo's own TD text (a docstring paragraph), not to external code; no third-party source was referenced (ip_check `attribution-trigger` on this word is a false positive).
- Must NOT: touch `requester_trust.py`, `bin/hos-cron`, or any file outside the five listed; commit, push, file issues, or change labels.

## Refinement History

Refinements after review, if any, are recorded in the sign-off register and commit history of this PR.

## Human Review Notes

<!-- After human review, record findings here. -->

---

## Reproducibility Check

To verify this prompt still produces equivalent output in a new session:
1. Open a fresh Claude Code session
2. Paste the prompt above verbatim
3. Compare key logic paths against `scripts/framework/select_work_candidates.py`
4. Note any drift in a new version artifact (`select_work_candidates.v1.md`)
