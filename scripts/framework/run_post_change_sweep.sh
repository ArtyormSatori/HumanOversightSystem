#!/usr/bin/env bash
# run_post_change_sweep.sh — explain which review dimensions apply to a diff (ADR-1643 AD-11).
#
# Computes the changed-file set, asks the dimension registry
# (scripts/automation/dimension_registry_cli.py) which dimensions and bindings
# apply to it, and prints that explanation. It EXECUTES NO BINDING: its only
# subprocesses are git and the resolved Python interpreter (ADR-1643 TD-D50).
# Execution belongs to AD-13's runner, not to this script.
#
# HOS repository only until #1643 W7 (#1930). It is not shipped to consumer installs.
#
# Usage:
#   run_post_change_sweep.sh [--json] [HEAD<ref-suffix> | --staged | <file> ...]
#
#   (no argument)   git diff --name-only HEAD; if that is empty, HEAD~1 when it exists
#   HEAD~1          git diff --name-only HEAD~1   (any positional starting with HEAD)
#   --staged        git diff --cached --name-only
#   file1 file2     explicit repo-relative files (no repository needed)
#                   (a positional beginning with HEAD is treated as a ref, so a file
#                   such as HEADER.md must be passed as ./HEADER.md)
#   --json          stdout is exactly the registry CLI's `plan` JSON ("[]" for an empty set)
#
# A positional argument that is neither an existing path nor HEAD* but resolves
# to a commit (e.g. a branch name) is rejected: use the HEAD-relative form.
# --framework-only was removed by ADR-1643 W5 (AD-11).
#
# Exit codes:
#   0 — explained (includes an empty change set: no review dimension applies)
#   1 — could not explain: a registry failure (the CLI's one-line stderr is
#       passed through), a failed git diff (TD-D51: fail closed, empty stdout),
#       no interpreter resolvable, or the registry CLI is not installed
#   2 — usage error
#
# Interpreter ladder (same rungs, same order as bootstrap/invoke_agent.sh):
# $HOS_REGISTRY_PYTHON, then scripts/oversight/.venv/bin/python, then python3.

set -euo pipefail

SELF="run_post_change_sweep.sh"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
CLI="$REPO_ROOT/scripts/automation/dimension_registry_cli.py"
VENV_PYTHON="$REPO_ROOT/scripts/oversight/.venv/bin/python"

# Renderer for the human-readable form (TD-D53). Imports only json and sys.
_RENDER_PY='
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(sys.stdin)
files = d["changed_files"]
print("Changed files (%d):" % len(files))
for f in files:
    print("  " + f)
print()
print("Review dimensions (registry %s, packs: %s):" % (d["digest"][:12], ", ".join(d["packs"]) or "none"))
order, by = [], {}
for it in d["plan"]:
    if it["entry"] not in by:
        by[it["entry"]] = []
        order.append(it["entry"])
    by[it["entry"]].append(it)
applying = fired = 0
for e in order:
    ap = any(i["applicable"] for i in by[e])
    applying += 1 if ap else 0
    print("  %s: %s" % (e, "APPLIES" if ap else "not applicable"))
    for i in by[e]:
        if i["applicable"]:
            fired += 1
            m = i["matched_files"]
            print("    + %s [%s] matched %d file(s): %s" % (i["binding"], i["kind"], len(m), ", ".join(m)))
        else:
            print("    - %s [%s] %s" % (i["binding"], i["kind"], i["reason"]))
print()
print("%d of %d dimension(s) apply; %d of %d binding(s) fired." % (applying, len(order), fired, len(d["plan"])))
'

die() { echo "$SELF: $*" >&2; exit 1; }
usage_die() { echo "$SELF: $*" >&2; exit 2; }

JSON=false
STAGED=false
REF=""
FILES=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --json)           JSON=true; shift ;;
        --framework-only) usage_die "--framework-only was removed by ADR-1643 W5 (AD-11); the plan now comes from the registry" ;;
        --staged)         STAGED=true; shift ;;
        HEAD*)            REF="$1"; shift ;;
        -*)               usage_die "unknown option: $1" ;;
        *)                FILES+=("$1"); shift ;;
    esac
done

# A branch/tag/sha is not a file: refuse rather than answer for a diff never computed.
# Both probes are boolean — a non-zero exit means "no", never "abort".
for arg in ${FILES[@]+"${FILES[@]}"}; do
    if [[ -e "$REPO_ROOT/$arg" ]] || git -C "$REPO_ROOT" ls-files --error-unmatch -- "$arg" >/dev/null 2>&1; then
        continue
    fi
    if git -C "$REPO_ROOT" rev-parse --verify --quiet "$arg^{commit}" >/dev/null 2>&1; then
        usage_die "'$arg' is a commit, not a path; use the HEAD-relative form (e.g. HEAD~1) or pass file names"
    fi
done

# ── Interpreter ladder and absent-CLI guard (TD-D30) ─────────────────────────
PY=""
if [[ -n "${HOS_REGISTRY_PYTHON:-}" ]]; then
    [[ -x "$HOS_REGISTRY_PYTHON" ]] || die "HOS_REGISTRY_PYTHON is set but not executable: $HOS_REGISTRY_PYTHON"
    PY="$HOS_REGISTRY_PYTHON"
elif [[ -x "$VENV_PYTHON" ]]; then
    PY="$VENV_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
else
    die "no interpreter found — checked \$HOS_REGISTRY_PYTHON (unset), $VENV_PYTHON, and python3 on PATH — run: bash scripts/oversight/ensure_venv.sh"
fi
[[ -f "$CLI" ]] || die "scripts/automation/dimension_registry_cli.py is not installed — the registry is not available in this checkout (ADR-1643 TD-VF-21)"

TMPD="$(mktemp -d)"
trap 'rm -rf "$TMPD"' EXIT

# ── Changed-file set (TD-D51: fail closed, NUL-separated) ────────────────────
CHANGED=()

# git_diff_paths <git diff args...>: appends the NUL-separated paths to CHANGED.
git_diff_paths() {
    local rc=0 p msg
    git -C "$REPO_ROOT" diff --name-only -z "$@" >"$TMPD/diff.out" 2>"$TMPD/diff.err" || rc=$?
    if [[ $rc -ne 0 ]]; then
        msg="$(grep -m1 '^fatal:' "$TMPD/diff.err" || head -n 1 "$TMPD/diff.err")"
        die "git diff failed (diff --name-only -z $*): $msg"
    fi
    while IFS= read -r -d '' p; do
        CHANGED+=("$p")
    done <"$TMPD/diff.out"
}

if [[ ${#FILES[@]} -gt 0 ]]; then
    CHANGED=("${FILES[@]}")
elif $STAGED; then
    git_diff_paths --cached
elif [[ -n "$REF" ]]; then
    git_diff_paths "$REF"
else
    git_diff_paths HEAD
    if [[ ${#CHANGED[@]} -eq 0 ]] && git -C "$REPO_ROOT" rev-parse --verify --quiet HEAD~1 >/dev/null 2>&1; then
        git_diff_paths HEAD~1
    fi
fi

# ── Ask the registry (TD-D52) ────────────────────────────────────────────────
CLI_ARGS=()
if [[ ${#CHANGED[@]} -gt 0 ]]; then
    CLI_ARGS=(plan)
    for p in "${CHANGED[@]}"; do
        CLI_ARGS+=("--changed-file=$p")
    done
else
    CLI_ARGS=(resolve)   # an empty set must still prove the registry loads
fi

CLI_RC=0
CLI_OUT="$("$PY" "$CLI" "${CLI_ARGS[@]}" 2>"$TMPD/cli.err")" || CLI_RC=$?
if [[ $CLI_RC -ne 0 ]]; then
    cat "$TMPD/cli.err" >&2
    if [[ $CLI_RC -ne 1 ]]; then
        echo "$SELF: internal error: dimension_registry_cli.py exited $CLI_RC" >&2
    fi
    exit 1
fi

# ── Render (only after the CLI succeeded) ────────────────────────────────────
if [[ ${#CHANGED[@]} -eq 0 ]]; then
    if $JSON; then
        printf '[]\n'
    else
        echo "No changed files — no review dimension applies."
    fi
    exit 0
fi

if $JSON; then
    printf '%s\n' "$CLI_OUT"
    exit 0
fi

RENDERED=""
RENDER_RC=0
RENDERED="$("$PY" -c "$_RENDER_PY" <<<"$CLI_OUT")" || RENDER_RC=$?
if [[ $RENDER_RC -ne 0 ]]; then
    die "renderer failed (exit $RENDER_RC)"
fi
printf '%s\n' "$RENDERED"
