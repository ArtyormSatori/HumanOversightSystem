#!/usr/bin/env bash
# bootstrap/escalate_to_human.sh — record-first write path for a human wait (#1644 T3.0a,
# ADR-1644 AD-C6 H5 / AD-C10)
#
# Turns a human wait on an ISSUE into H1 (`needs-human` on the issue) after first recording
# the question, so the label never exists without its reason. Order: post the question
# comment, read it back and confirm it, add the label, verify the label, then write a
# best-effort audit event. Each step halts before the next on failure.
#
# Usage:
#   bash bootstrap/escalate_to_human.sh --number <N> --body-file <path> --reason <token> \
#     --app <worker|overseer|human>
#
# --body-file only, never inline --body <text> (same reasoning as post_comment.sh). The
# comment is posted through a jq-built JSON object piped to `gh api --input -`; a
# field-flag file reference silently posts the literal path string (the #1155 trap).
#
# --reason is a machine token (^[a-z][a-z0-9-]{1,63}$) naming the trigger. It is recorded
# in the comment's hidden marker and in the audit event.
#
# Idempotent. The marker line appended to the comment is
#   <!-- hos-escalation v=1 reason=<reason> key=<key> -->
# where key = first 16 hex of sha256("hos-escalation-v1" NUL <N> NUL <reason> NUL <body bytes>).
# A re-run finds its own unedited marker comment (bot-authored, updated_at == created_at)
# and does not post twice. A marker pasted by any other author is ignored.
#
# Targets: an OPEN ISSUE that is not a pull request and not a `release-request` issue (the
# removal of needs-human there is an authorization signal this script must never re-apply
# over). It never removes `needs-ai` and never touches `stage:*`.
#
# Exit codes (3 is deliberately unused, to avoid confusion with the selector's DEGRADED):
#   0  needs-human is on the issue and a confirmed own record exists
#      (escalated | already-escalated | label-repaired). One stdout line.
#   1  transient: token mint, identity, or a pre-write read failed. No writes. Retry unchanged.
#   2  refused: usage, body, or target precondition. No writes. Fix the input.
#   4  record-failed: the comment POST or its read-back failed. Label NOT applied.
#      Retry the identical command.
#   5  partial: record confirmed but needs-human not applied/verified. Retry the identical
#      command (takes the label-repaired path).
#   6  superseded: an own record exists and needs-human was removed after it (or that could
#      not be determined, supersede-undeterminable). Do not retry; a NEW body is a new
#      escalation.
#
# Requires: bootstrap/get_app_token.sh, gh, git, jq, curl, sha256sum (or shasum).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED="\033[31m"; YELLOW="\033[33m"; RESET="\033[0m"
err()  { echo -e "  ${RED}✘${RESET}  $*" >&2; exit 1; }
warn() { echo -e "  ${YELLOW}⚠${RESET}  $*" >&2; }

# shellcheck source=lib/comment_format_check.sh
source "$SCRIPT_DIR/lib/comment_format_check.sh"

NEEDS_HUMAN_LABEL="needs-human"
MAX_BODY_BYTES=65000
COMMENT_PAGE_BOUND=30
EVENT_PAGE_BOUND=10

# refuse <message>: exit 2, nothing written.
refuse() {
    echo "escalate_to_human: $*" >&2
    exit 2
}

NUMBER=""
BODY_FILE=""
REASON=""
APP_ROLE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --number)    [[ $# -ge 2 ]] || refuse "usage: --number requires a value"; NUMBER="$2"; shift 2 ;;
        --body-file) [[ $# -ge 2 ]] || refuse "usage: --body-file requires a value"; BODY_FILE="$2"; shift 2 ;;
        --reason)    [[ $# -ge 2 ]] || refuse "usage: --reason requires a value"; REASON="$2"; shift 2 ;;
        --app)       [[ $# -ge 2 ]] || refuse "usage: --app requires a value"; APP_ROLE="$2"; shift 2 ;;
        --body)      refuse "--body is not supported — write the body to a file and pass --body-file <path>. Inline text with newlines/quotes is exactly the unallowlistable shell pattern this script exists to eliminate." ;;
        *)           refuse "usage: $0 --number <N> --body-file <path> --reason <token> --app <worker|overseer|human>" ;;
    esac
done

# ── Validation: everything here runs before any token is minted ──────────────
[[ -n "$NUMBER" ]]    || refuse "usage: --number required"
[[ -n "$BODY_FILE" ]] || refuse "usage: --body-file required"
[[ -n "$REASON" ]]    || refuse "usage: --reason required"
[[ -n "$APP_ROLE" ]]  || refuse "usage: --app required (worker, overseer, or human)"
[[ "$NUMBER" =~ ^[1-9][0-9]*$ ]] || refuse "usage: --number must be a positive integer, got: $NUMBER"
[[ "$REASON" =~ ^[a-z][a-z0-9-]{1,63}$ ]] || refuse "usage: --reason must match ^[a-z][a-z0-9-]{1,63}\$, got: $REASON"
case "$APP_ROLE" in
    worker|overseer|human) ;;
    *) refuse "usage: --app must be 'worker', 'overseer', or 'human'" ;;
esac

[[ -f "$BODY_FILE" ]] || refuse "body-file-not-found: $BODY_FILE"
[[ -n "$(tr -d '[:space:]' < "$BODY_FILE")" ]] || refuse "body-empty: $BODY_FILE has no content"
hos_cfc_check_at_path_literal "$BODY_FILE" || refuse "$HOS_CFC_REASON"
if grep -qF -- '<!-- hos-escalation' "$BODY_FILE"; then
    refuse "body-carries-marker: the body must not contain an hos-escalation marker"
fi

if command -v sha256sum >/dev/null 2>&1; then
    SHA_CMD=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
    SHA_CMD=(shasum -a 256)
else
    refuse "no-sha256-tool: neither sha256sum nor shasum is available"
fi

KEY="$({ printf 'hos-escalation-v1\0%s\0%s\0' "$NUMBER" "$REASON"; cat "$BODY_FILE"; } | "${SHA_CMD[@]}" | cut -c1-16)"
MARKER="<!-- hos-escalation v=1 reason=${REASON} key=${KEY} -->"

BODY_BYTES="$(wc -c < "$BODY_FILE")"
# body + "\n\n" + marker + "\n"
if (( BODY_BYTES + ${#MARKER} + 3 > MAX_BODY_BYTES )); then
    refuse "body-too-large: body plus marker exceeds ${MAX_BODY_BYTES} bytes"
fi

# ── Resolve owner/repo from the origin remote (no auth required) ─────────────
REPO_URL="$(git -C "$SCRIPT_DIR/.." remote get-url origin 2>/dev/null)" \
    || err "issue=#${NUMBER} Could not read git remote 'origin' — run from inside the HOS repo"
REPO_SLUG="$(printf '%s' "$REPO_URL" | sed -E 's#^git@github\.com:##; s#^https://github\.com/##; s#\.git$##')"
[[ "$REPO_SLUG" == */* ]] || err "issue=#${NUMBER} Could not parse owner/repo from origin remote: $REPO_URL"

# ── Token: mint once, source, delete the file at once (#549); revoke in an EXIT trap ──
TOKEN_FILE="$(mktemp)"
MINTED=0

revoke_token() {
    curl -sf --connect-timeout 10 --max-time 30 -X DELETE -H "Authorization: token ${GH_TOKEN}" \
        -H "Accept: application/vnd.github+json" \
        https://api.github.com/installation/token >/dev/null 2>&1 \
        || warn "failed to revoke installation token (it will expire naturally within 1 hour)"
}

cleanup() {
    local rc=$?
    rm -f "$TOKEN_FILE"
    if [[ "$MINTED" -eq 1 ]]; then
        MINTED=0
        revoke_token
    fi
    return "$rc"
}
trap cleanup EXIT

bash "$SCRIPT_DIR/get_app_token.sh" --app "$APP_ROLE" > "$TOKEN_FILE" || err "issue=#${NUMBER} Failed to mint ${APP_ROLE} token"
# shellcheck source=/dev/null
source "$TOKEN_FILE"
rm -f "$TOKEN_FILE"
MINTED=1

[[ -n "${HOS_BOT_LOGIN:-}" ]] || err "issue=#${NUMBER} HOS_BOT_LOGIN is empty after token mint — cannot verify authorship"

# ── Audit: best-effort, same shape as submit_pr.sh::_hos_audit_stale_base_merge ──
# audit_event <outcome> <comment_id|""> ; always returns 0
audit_event() {
    local outcome="$1" comment_id="${2:-null}" ts json
    local audit_lib="$SCRIPT_DIR/../scripts/oversight/lib/audit_log.sh"
    if [[ ! -f "$audit_lib" ]]; then
        warn "audit event not written"
        return 0
    fi
    # shellcheck disable=SC1090
    source "$audit_lib" 2>/dev/null || { warn "audit event not written"; return 0; }
    if ! command -v audit_write_event >/dev/null 2>&1; then
        warn "audit event not written"
        return 0
    fi
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    json="$(jq -nc \
        --argjson issue "$NUMBER" --arg reason "$REASON" --arg key "$KEY" \
        --arg outcome "$outcome" --argjson comment_id "$comment_id" \
        --arg app "$APP_ROLE" --arg actor "$HOS_BOT_LOGIN" \
        --argjson label_present_before "$HAD_LABEL" --arg ts "$ts" \
        '{event:"escalated-to-human", issue:$issue, reason:$reason, key:$key, outcome:$outcome,
          comment_id:$comment_id, app:$app, actor:$actor,
          label_present_before:$label_present_before, timestamp:$ts}')" \
        || { warn "audit event not written"; return 0; }
    audit_write_event "$json" "$SCRIPT_DIR/.." >/dev/null \
        || warn "audit event not written"
    return 0
}

# fail_read <token> <detail>: pre-write failure, exit 1 (no audit event)
fail_read() {
    echo "escalate_to_human: $1 issue=#${NUMBER} $2" >&2
    exit 1
}

HAD_LABEL=false

# ── R1: the target issue ─────────────────────────────────────────────────────
ISSUE_JSON="$(gh api "repos/${REPO_SLUG}/issues/${NUMBER}")" \
    || fail_read "read-failed" "GET issue failed"
jq -e 'type == "object"' >/dev/null 2>&1 <<<"$ISSUE_JSON" \
    || fail_read "read-failed" "GET issue returned unparseable JSON"

if jq -e 'has("pull_request")' >/dev/null <<<"$ISSUE_JSON"; then
    refuse "target-is-pull-request issue=#${NUMBER}"
fi
if ! jq -e '.state == "open"' >/dev/null <<<"$ISSUE_JSON"; then
    refuse "target-not-open issue=#${NUMBER}"
fi
if jq -e '[(.labels // [])[] | (.name // .)] | index("release-request") != null' >/dev/null <<<"$ISSUE_JSON"; then
    refuse "target-is-release-request issue=#${NUMBER}"
fi
if jq -e --arg l "$NEEDS_HUMAN_LABEL" '[(.labels // [])[] | (.name // .)] | index($l) != null' >/dev/null <<<"$ISSUE_JSON"; then
    HAD_LABEL=true
fi

# ── R2: look for our own, unedited marker comment ────────────────────────────
OWN_ID=""
OWN_CREATED=""
OWN_URL=""
page=1
while (( page <= COMMENT_PAGE_BOUND )); do
    PAGE_JSON="$(gh api "repos/${REPO_SLUG}/issues/${NUMBER}/comments?per_page=100&page=${page}")" \
        || fail_read "read-failed" "GET comments page ${page} failed"
    FOUND="$(jq -r --arg marker "$MARKER" --arg login "$HOS_BOT_LOGIN" '
        if type == "array" then
          ([ .[] | select(
              ((.user.login // "") | ascii_downcase) == ($login | ascii_downcase)
              and .user.type == "Bot"
              and .updated_at == .created_at
              and ((.body // "") | split("\n") | any(. == $marker))
            ) ] | .[0] // empty | "\(.id)\t\(.created_at)\t\(.html_url)")
        else error("not an array") end' <<<"$PAGE_JSON")" \
        || fail_read "read-failed" "GET comments page ${page} returned unparseable JSON"
    if [[ -n "$FOUND" ]]; then
        IFS=$'\t' read -r OWN_ID OWN_CREATED OWN_URL <<<"$FOUND"
        break
    fi
    COUNT="$(jq 'length' <<<"$PAGE_JSON")"
    if (( COUNT < 100 )); then
        break
    fi
    if (( page == COMMENT_PAGE_BOUND )); then
        warn "comment-page-bound-reached; a duplicate question comment is possible"
    fi
    page=$((page + 1))
done

# ── R3: supersede check, only when an own record exists and the label is gone ─
SUPERSEDED=""
if [[ -n "$OWN_ID" && "$HAD_LABEL" == "false" ]]; then
    page=1
    SUPERSEDED="undetermined"
    while (( page <= EVENT_PAGE_BOUND )); do
        EV_JSON="$(gh api "repos/${REPO_SLUG}/issues/${NUMBER}/events?per_page=100&page=${page}")" \
            || fail_read "read-failed" "GET events page ${page} failed"
        HIT="$(jq -r --arg l "$NEEDS_HUMAN_LABEL" --arg t "$OWN_CREATED" '
            if type == "array" then
              ([ .[] | select(.event == "unlabeled" and .label.name == $l and .created_at >= $t) ] | length)
            else error("not an array") end' <<<"$EV_JSON")" \
            || fail_read "read-failed" "GET events page ${page} returned unparseable JSON"
        if (( HIT > 0 )); then
            SUPERSEDED="yes"
            break
        fi
        COUNT="$(jq 'length' <<<"$EV_JSON")"
        if (( COUNT < 100 )); then
            SUPERSEDED="no"
            break
        fi
        page=$((page + 1))
    done
fi

if [[ "$SUPERSEDED" == "yes" || "$SUPERSEDED" == "undetermined" ]]; then
    token="superseded"
    detail=""
    if [[ "$SUPERSEDED" == "undetermined" ]]; then
        token="supersede-undeterminable"
        detail=" events-page-bound-reached"
    fi
    audit_event "$token" "$OWN_ID"
    echo "escalate_to_human: ${token} issue=#${NUMBER}${detail} reason=${REASON} key=${KEY} comment=${OWN_URL} — do not retry; escalate again with a new body if still blocked" >&2
    exit 6
fi

# ── Writes ───────────────────────────────────────────────────────────────────
OUTCOME=""
COMMENT_ID="$OWN_ID"
COMMENT_URL="$OWN_URL"

if [[ -n "$OWN_ID" && "$HAD_LABEL" == "true" ]]; then
    OUTCOME="already-escalated"
else
    if [[ -n "$OWN_ID" ]]; then
        OUTCOME="label-repaired"
    else
        OUTCOME="escalated"

        # W1: record
        if ! POSTED="$(jq -n --rawfile body "$BODY_FILE" --arg marker "$MARKER" \
                '{body: ($body + "\n\n" + $marker + "\n")}' \
            | gh api --method POST "repos/${REPO_SLUG}/issues/${NUMBER}/comments" --input -)"; then
            audit_event "record-failed" "null"
            echo "escalate_to_human: record-failed issue=#${NUMBER} reason=${REASON} key=${KEY} — POST comment failed; the label was NOT applied; retry the identical command" >&2
            exit 4
        fi
        COMMENT_ID="$(jq -r 'if (.id | type) == "number" then .id else empty end' <<<"$POSTED" 2>/dev/null || true)"
        COMMENT_URL="$(jq -r '.html_url // empty' <<<"$POSTED" 2>/dev/null || true)"
        if [[ -z "$COMMENT_ID" ]]; then
            audit_event "record-failed" "null"
            echo "escalate_to_human: record-failed issue=#${NUMBER} reason=${REASON} key=${KEY} — POST comment returned no comment id; the label was NOT applied; retry the identical command" >&2
            exit 4
        fi

        # W2: confirm the record exists, is ours, and carries the marker
        if ! READBACK="$(gh api "repos/${REPO_SLUG}/issues/comments/${COMMENT_ID}")" \
            || ! jq -e --arg marker "$MARKER" --arg login "$HOS_BOT_LOGIN" '
                ((.user.login // "") | ascii_downcase) == ($login | ascii_downcase)
                and .user.type == "Bot"
                and ((.body // "") | split("\n") | any(. == $marker))' >/dev/null 2>&1 <<<"$READBACK"; then
            audit_event "record-failed" "$COMMENT_ID"
            echo "escalate_to_human: record-failed issue=#${NUMBER} reason=${REASON} key=${KEY} — comment ${COMMENT_ID} could not be confirmed (author/marker); the label was NOT applied; retry the identical command" >&2
            exit 4
        fi
    fi

    # W3: label (add endpoint; never replaces labels)
    if ! jq -nc --arg l "$NEEDS_HUMAN_LABEL" '{labels: [$l]}' \
        | gh api --method POST "repos/${REPO_SLUG}/issues/${NUMBER}/labels" --input - >/dev/null; then
        LABEL_ERR="POST labels failed"
    # W4: verify
    elif ! VERIFY="$(gh api "repos/${REPO_SLUG}/issues/${NUMBER}")" \
        || ! jq -e --arg l "$NEEDS_HUMAN_LABEL" '[(.labels // [])[] | (.name // .)] | index($l) != null' >/dev/null 2>&1 <<<"$VERIFY"; then
        LABEL_ERR="needs-human not present after the label POST"
    else
        LABEL_ERR=""
    fi
    if [[ -n "$LABEL_ERR" ]]; then
        audit_event "partial" "$COMMENT_ID"
        echo "escalate_to_human: partial issue=#${NUMBER} reason=${REASON} key=${KEY} — ${LABEL_ERR}" >&2
        echo "escalate_to_human: REPAIR — re-run the identical command; the question is recorded at ${COMMENT_URL} but needs-human is NOT applied, so the issue is still selectable" >&2
        exit 5
    fi
fi

# W5: audit (best-effort)
audit_event "$OUTCOME" "$COMMENT_ID"
echo "escalated issue=#${NUMBER} outcome=${OUTCOME} reason=${REASON} key=${KEY} comment=${COMMENT_URL}"
