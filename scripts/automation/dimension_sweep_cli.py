#!/usr/bin/env python3
"""
dimension_sweep_cli.py — L2 measurement runner (ADR-1643 AD-13, W6; TD Amendment G,
docs/v0.7.0/TECHNICAL-DESIGN-1643-invocation-primitive.md §G.1-§G.12).

    dimension_sweep_cli.py measure --base <ref> [--allow-keychain-auth] [--document-out <path>]
    dimension_sweep_cli.py report  [--since <YYYY-MM-DD>]

OBSERVATION ONLY. `measure` runs ONE observation of ONE binding (MEASURED_BINDING)
against the current checkout through bootstrap/invoke_agent.sh and records what
happened. It gates nothing: no merge path, bounce path or required check reads
its records, and they are never AD-14 dimension results (TD-D63). `report`
aggregates the records into raw numbers and calibrates nothing (TD-D65).

WHO RUNS IT: a human, by hand, in a plain terminal. It refuses (exit 2, one
stderr line, no I/O, no record) when HOS_CYCLE_ROLE, CLAUDECODE or
CLAUDE_CODE_ENTRYPOINT is set and non-empty. The refusals are an accident
guard, never a security boundary, and no environment signal relaxes anything
(AD-16.7). Auth is strict by default (`--require-env-auth`);
`--allow-keychain-auth` is the human-only opt-out.

OPERATOR PROCEDURE (TD-D63's durable path, TD §G.8). Use a dedicated linked
worktree of the Human clone, never the Worker or Overseer clone, and run it with
the oversight venv's interpreter by absolute path (a fresh worktree has no
.venv; without PyYAML the failure is recorded as `registry_error`):

    git worktree add --detach <dir> origin/main        # once
    git checkout --detach <head>                       # per measured head
    <human-clone>/scripts/oversight/.venv/bin/python \\
        scripts/automation/dimension_sweep_cli.py measure --base origin/main
    <human-clone>/scripts/oversight/.venv/bin/python \\
        scripts/automation/dimension_sweep_cli.py report

CAVEATS. (1) Measure only heads that are already reviewed or merged: the runner,
bootstrap/invoke_agent.sh, the agent file and the posture all execute from the
checked-out head, with the operator's credentials. (2) On Ctrl-C or a runner
timeout the runner kills the wrapper's process group, but the primitive's own
`claude` child runs in its own session and may survive. After an interrupted run,
check `pgrep -af -- "--output-format json --agent code-reviewer"` and stop any
leftover. This is a known W1 gap, tracked separately.

Pilot with 3 launched runs first and stop if `report` shows
terminal_reason_missing_count > 0, two of three runs without
payload_extractable, or input_digest_mismatch_count > 0. Then (1) commit
exactly the audit/log/**/*-dimension-measurement*.json files on a branch and
open a PR (data only, no protected surface); (2) post `report`'s JSON to #1643
through the repository's issue-comment entry point listed in CLAUDE.md. The
committed records are the audit trail; the comment is the pointer.
`--document-out` (outside the work tree only) keeps the full document for
diagnosis; it carries agent prose and is never committed, never read by `report`.

Exit codes for `measure`: 0 an observation was recorded (measured, reused,
not_applicable); 1 a run failure was recorded or a record could not be written;
2 usage error or refusal. `report`: 0, or 1 on a malformed audit record.

Importing this module performs no I/O. Records carry no prose (no prompt text,
agent output, finding text or file content).
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, NoReturn

_DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_ROOT_STR = str(_DEFAULT_REPO_ROOT)
if _REPO_ROOT_STR not in sys.path:
    sys.path.insert(0, _REPO_ROOT_STR)

from scripts.automation import agent_invoke_cli as aic  # noqa: E402
from scripts.automation.lib import dimension_registry as dr  # noqa: E402
from scripts.automation.lib import posture as posture_lib  # noqa: E402

MEASURED_BINDING = "core:code-review/code"

EVENT_RESULT = "dimension-measurement"
EVENT_START = "dimension-measurement-start"
SCHEMA_VERSION = 1
REPORT_SCHEMA = "hos.dimension-measurement-report"

_GIT_TIMEOUT_S = 60
_RUNNER_EXTRA_S = 60
_KILL_GRACE_S = 5
# Test-only seam: lowers the runner-side wall clock cap (T6.12). Never set in production.
_RUNNER_TIMEOUT_OVERRIDE_S: int | None = None

_LOCK_NAME = "hos-w6-measure.lock"
_ERROR_DETAIL_MAX = 500
_UNKNOWN_FIELDS_MAX = 50
_DENIED_TOOLS_MAX = 20
_USAGE_KEYS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "output_tokens",
)
_PRE_EVALUATION_DETAILS = frozenset({"timeout", "unparseable", "envelope_shape_violation"})
_SINCE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_REFUSALS = (
    ("HOS_CYCLE_ROLE", "W6 is never run from a cron cycle (ADR-1643 ESC-2)"),
    (
        "CLAUDECODE",
        "running inside a Claude Code session — W6 must be run from a plain terminal "
        "(ADR-1643 Q4+Q6, no nested sessions)",
    ),
    (
        "CLAUDE_CODE_ENTRYPOINT",
        "running inside a Claude Code session — W6 must be run from a plain terminal "
        "(ADR-1643 Q4+Q6, no nested sessions)",
    ),
)

# TD-D62 part 3: the one payload instruction, never one per dimension. Any change moves
# every input_digest and needs a TD amendment.
PAYLOAD_INSTRUCTION = (
    "\n## Response format\n\n"
    "Respond with exactly one JSON object and nothing else.\n\n"
    "- `verdict` is one of `approve` or `request_changes`.\n"
    "- `findings` is a list. Each finding has `severity` (one of "
    f"{', '.join(aic.SEVERITIES)}), `file`, `line`, `category` and `description`.\n"
    "- `summary` is a string.\n"
    "- The keys `applicability`, `outcome`, `input` and `invocation` must not appear.\n"
)

_AUDIT_LOG_MODULE = None


class _UsageError(Exception):
    pass


class _Refusal(Exception):
    pass


class _Fail(Exception):
    """A recorded run failure (§G.6): becomes a result record and exit 1."""

    def __init__(self, outcome: str, code: str | None, detail: str):
        super().__init__(outcome, code, detail)
        self.outcome = outcome
        self.code = code
        self.detail = detail


class _PrimitiveTimeout(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _UsageError(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="dimension_sweep_cli.py", add_help=False)
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)
    measure = sub.add_parser("measure", add_help=False)
    measure.add_argument("--base", required=True)
    measure.add_argument("--allow-keychain-auth", action="store_true")
    measure.add_argument("--document-out", default=None)
    report = sub.add_parser("report", add_help=False)
    report.add_argument("--since", default=None)
    return parser


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _audit_log():
    """Load scripts/oversight/lib/audit_log.py by file path (same idiom as
    merge_authority's loader); lazily, so importing this module does no I/O."""
    global _AUDIT_LOG_MODULE
    if _AUDIT_LOG_MODULE is None:
        path = _DEFAULT_REPO_ROOT / "scripts" / "oversight" / "lib" / "audit_log.py"
        spec = importlib.util.spec_from_file_location("hos_audit_log", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        _AUDIT_LOG_MODULE = mod
    return _AUDIT_LOG_MODULE


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def _bounded_detail(text: str) -> str | None:
    return aic.bounded_audit_str(_one_line(text))


def _emit(obj: object) -> None:
    sys.stdout.write(json.dumps(obj, sort_keys=True) + "\n")
    sys.stdout.flush()


def _refuse_if_nested() -> None:
    for var, why in _REFUSALS:
        if os.environ.get(var):
            raise _Refusal(f"dimension_sweep: refused: {var} is set — {why}")


def _check_document_out(path: str | None, root: Path) -> None:
    if path is None:
        return
    resolved = Path(path).resolve()
    if resolved == root or root in resolved.parents:
        raise _UsageError(f"--document-out must resolve outside the repository work tree: {path}")


def _write_document(path: Path, data: bytes, root: Path) -> None:
    """Create-only, no-follow write of the full W1 document (CWE-367/59). The confinement
    check is re-run on the resolved parent immediately before the write."""
    parent = path.parent.resolve()
    if parent == root or root in parent.parents:
        raise OSError("--document-out now resolves inside the repository work tree")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    with os.fdopen(os.open(path, flags, 0o600), "wb") as fh:
        fh.write(data)


def _run_git(root: Path, *args: str) -> bytes:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(root),
            capture_output=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _Fail("git_error", "git_failed", f"git {args[0]} could not run: {exc}") from None
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", errors="replace")
        raise _Fail(
            "git_error", "git_failed", f"git {args[0]} exited {proc.returncode}: {_one_line(tail)}"
        )
    return proc.stdout


def _decode_path(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise _Fail("git_error", "bad_changed_file", "a changed path is not valid UTF-8") from None


def _parse_numstat(out: bytes) -> dict[str, int]:
    """`git diff -z --numstat`: `<add>\\t<del>\\t<path>\\0`, or for a rename
    `<add>\\t<del>\\t\\0<old>\\0<new>\\0`. A binary file's `-` counts as 0."""
    tokens = out.split(b"\0")
    lines: dict[str, int] = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if not token:
            i += 1
            continue
        parts = token.split(b"\t", 2)
        if len(parts) != 3:
            raise _Fail("git_error", "git_failed", "unparseable git numstat output")
        added, deleted, raw_path = parts
        if raw_path == b"":
            if i + 2 >= len(tokens) or not tokens[i + 2]:
                raise _Fail("git_error", "git_failed", "unparseable git numstat rename entry")
            raw_path = tokens[i + 2]
            i += 3
        else:
            i += 1
        count = sum(int(x) if x.isdigit() else 0 for x in (added, deleted))
        lines[_decode_path(raw_path)] = count
    return lines


def _render_input(template: bytes, base_sha: str, head_sha: str, matched: list[str]) -> bytes:
    """TD-D62: template bytes verbatim + the change block + PAYLOAD_INSTRUCTION. Pure and
    deterministic: no timestamp, run id, absolute path, hostname or environment value."""
    selected = "".join(f"- {path}\n" for path in sorted(matched))
    block = (
        "\n## Changes under review\n\n"
        f"Base commit: {base_sha}\n"
        f"Head commit: {head_sha}\n"
        f"Inspect each selected file's change with: git diff {base_sha}...{head_sha} -- <path>\n\n"
        f"Selected files:\n{selected}"
    )
    return template + block.encode("utf-8") + PAYLOAD_INSTRUCTION.encode("utf-8")


def _runner_timeout_s(binding_timeout: int) -> int:
    if _RUNNER_TIMEOUT_OVERRIDE_S is not None:
        return _RUNNER_TIMEOUT_OVERRIDE_S
    return binding_timeout + aic.DEFAULT_GRACE_S + _RUNNER_EXTRA_S


def _raise_interrupt(signum: int, _frame: object) -> NoReturn:
    raise KeyboardInterrupt(f"signal {signum}")


@contextlib.contextmanager
def _signals_as_interrupt():
    """SIGTERM/SIGHUP become KeyboardInterrupt while the primitive runs, so the group kill and
    the best-effort `interrupted` record run. Previous handlers are restored on exit."""
    previous: dict[int, object] = {}
    try:
        for sig in (signal.SIGTERM, signal.SIGHUP):
            previous[sig] = signal.signal(sig, _raise_interrupt)
    except ValueError:  # not the main thread: handlers cannot be installed
        pass
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)  # type: ignore[arg-type]


def _run_primitive(argv: list[str], *, timeout_s: int) -> tuple[int, bytes, bytes]:
    """The one seam to the primitive (AD-16): an argv list, shell=False, its own session so
    the whole group can be killed. Raises _PrimitiveTimeout after killing the group."""
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        raise _PrimitiveTimeout() from None
    except BaseException:
        _kill_group(proc)
        raise
    return proc.returncode, out, err


def _kill_group(proc: subprocess.Popen) -> None:
    """SIGTERM the group, wait out the grace, then ALWAYS SIGKILL the whole group (TD §G.13
    item 6): the leader exiting early must not spare a member that ignores SIGTERM."""
    for sig, wait_s in ((signal.SIGTERM, _KILL_GRACE_S), (signal.SIGKILL, _KILL_GRACE_S)):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass
        try:
            proc.communicate(timeout=wait_s)
        except subprocess.TimeoutExpired:
            pass


class _Lock:
    """Per-repository, non-blocking flock in the git common dir, which every linked
    worktree shares (TD-D60, architect round 1): concurrency 1 is a quota bound."""

    def __init__(self) -> None:
        self._fh: IO[str] | None = None

    def acquire(self, path: Path) -> None:
        try:
            fh = open(path, "a")
        except OSError as exc:
            raise _Fail("git_error", "lock_unopenable", f"cannot open {path}: {exc}") from None
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            raise _Fail("lock_held", None, f"another measure run holds {path}") from None
        self._fh = fh

    def release(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None


def _blank_record(run_id: str, auth_mode: str) -> dict:
    keys = (
        "error_code error_detail entry agent posture registry_digest prompt_template_version "
        "base_sha head_sha changed_files_count matched_files_count matched_lines_changed "
        "input_bytes input_digest input_digest_match reused_from primitive_exit_code outcome "
        "outcome_detail verdict terminal_reason_missing findings_count blocking_findings_count "
        "duration_ms runner_wall_ms timeout_seconds timed_out model cli_version num_turns "
        "total_cost_usd usage envelope_unknown_fields primitive_audit_record "
        "permission_denied_tools payload_extractable"
    ).split()
    rec: dict = dict.fromkeys(keys)
    rec.update(
        event=EVENT_RESULT,
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        mode="observation",
        runner_outcome=None,
        binding=MEASURED_BINDING,
        launched=False,
        auth_mode=auth_mode,
    )
    return rec


def _write(event: dict, root: Path) -> str:
    return _audit_log().write_event(event, root=str(root))


def _publish(rec: dict, root: Path, exit_code: int) -> int:
    rec["timestamp"] = _now_iso()
    try:
        _write(rec, root)
    except Exception as exc:  # noqa: BLE001 — the record still goes to stdout (§G.6)
        sys.stderr.write(f"dimension_sweep: record not written: {_one_line(str(exc))}\n")
        exit_code = 1
    _emit(rec)
    return exit_code


# ---------------------------------------------------------------------------
# document -> record
# ---------------------------------------------------------------------------


def _parse_document(stdout: bytes) -> dict | None:
    try:
        doc = json.loads(stdout.decode("utf-8"))
    except (ValueError, RecursionError):  # UnicodeDecodeError is a ValueError
        return None
    if not isinstance(doc, dict) or doc.get("schema") != aic.SCHEMA:
        return None
    return doc


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _denied_tools(envelope: dict) -> list[str] | None:
    denials = envelope.get("permission_denials")
    if not isinstance(denials, list):
        return []
    names: set[str] = set()
    for denial in denials:
        name = aic.bounded_audit_str(_as_dict(denial).get("tool_name"))
        names.add(name if name is not None else "<malformed>")
    return sorted(names)[:_DENIED_TOOLS_MAX]


def _ingest_document(rec: dict, doc: dict) -> None:
    inv = _as_dict(doc.get("invocation"))
    findings = doc.get("findings")
    findings = findings if isinstance(findings, list) else []
    detail = aic.bounded_audit_str(doc.get("outcome_detail"))
    timed_out = inv.get("timed_out") is True
    unknown = inv.get("envelope_unknown_fields")
    unknown = unknown if isinstance(unknown, list) else []
    usage = inv.get("usage")
    envelope = inv.get("envelope")
    rec.update(
        outcome=aic.bounded_audit_str(doc.get("outcome")),
        outcome_detail=detail,
        verdict=aic.bounded_audit_str(doc.get("verdict")),
        terminal_reason_missing=detail == "terminal_reason_missing",
        findings_count=len(findings),
        blocking_findings_count=sum(
            1
            for f in findings
            if str(_as_dict(f).get("severity", "")).lower() in aic.blocking_severities
        ),
        duration_ms=aic.bounded_audit_number(inv.get("duration_ms")),
        timeout_seconds=aic.bounded_audit_number(inv.get("timeout_seconds")),
        timed_out=timed_out,
        launched=inv.get("exit_code") is not None or timed_out,
        model=aic.bounded_audit_str(inv.get("model")),
        cli_version=aic.bounded_audit_str(inv.get("cli_version")),
        num_turns=aic.bounded_audit_number(inv.get("num_turns")),
        total_cost_usd=aic.bounded_audit_number(inv.get("total_cost_usd")),
        usage=(
            {k: aic.bounded_audit_number(usage.get(k)) for k in _USAGE_KEYS}
            if isinstance(usage, dict)
            else None
        ),
        envelope_unknown_fields=[
            s
            for s in (aic.bounded_audit_str(x) for x in unknown[:_UNKNOWN_FIELDS_MAX])
            if s is not None
        ],
        primitive_audit_record=aic.bounded_audit_str(
            _as_dict(doc.get("observability")).get("audit_record")
        ),
    )
    if isinstance(envelope, dict):
        rec["permission_denied_tools"] = _denied_tools(envelope)
        try:
            rec["payload_extractable"] = aic.extract_payload(envelope) is not None
        except Exception:  # noqa: BLE001 — a diagnostic must never lose the observation
            rec["payload_extractable"] = None


# ---------------------------------------------------------------------------
# measure
# ---------------------------------------------------------------------------


def _resolve_git_inputs(root: Path, base: str, rec: dict) -> tuple[str, str, list[str], dict]:
    base_commit = _run_git(root, "rev-parse", "--verify", f"{base}^{{commit}}").decode().strip()
    head_sha = _run_git(root, "rev-parse", "HEAD").decode().strip()
    base_sha = _run_git(root, "merge-base", base_commit, "HEAD").decode().strip()
    rec.update(base_sha=base_sha, head_sha=head_sha)
    spec = f"{base_commit}...HEAD"
    names = _run_git(root, "diff", "-z", "--name-only", spec, "--")
    changed = sorted({_decode_path(p) for p in names.split(b"\0") if p})
    numstat = _parse_numstat(_run_git(root, "diff", "-z", "--numstat", spec, "--"))
    rec["changed_files_count"] = len(changed)
    return base_sha, head_sha, changed, numstat


def _lock_path(root: Path) -> Path:
    out = _run_git(root, "rev-parse", "--git-common-dir").decode().strip()
    common = Path(out)
    if not common.is_absolute():
        common = root / common
    return common.resolve() / _LOCK_NAME


def _precompute_digest(
    root: Path, binding: dr.Binding, *, rec: dict, matched: list[str], rendered: bytes | None
) -> str | None:
    """TD-D64: W1's own functions, so the key equals L2's. None when a component cannot be
    computed (the primitive then records its own preflight document)."""
    assert binding.agent is not None
    try:
        agent_sha = _sha256((root / ".claude" / "agents" / f"{binding.agent}.md").read_bytes())
        posture = None
        if rendered is not None:
            assert binding.posture is not None
            posture = posture_lib.load_posture(root, binding.posture)
    except (OSError, posture_lib.PostureError):
        return None
    return aic.compute_input_digest(
        agent=binding.agent,
        agent_file_sha256=agent_sha,
        posture_id=posture.id if posture else None,
        posture_sha256=posture.sha256 if posture else None,
        input_file_sha256=_sha256(rendered) if rendered is not None else None,
        prompt_template_version=rec["prompt_template_version"],
        dimension=binding.entry,
        binding=binding.id,
        matched_files_sha256=aic.matched_files_digest(root, matched),
        base_sha=rec["base_sha"],
        head_sha=rec["head_sha"],
    )


def _find_prior(root: Path, digest: str) -> str | None:
    audit = _audit_log()
    try:
        for raw in audit.read_stream(str(root)):
            record = json.loads(raw)
            if (
                isinstance(record, dict)
                and record.get("event") == EVENT_RESULT
                and record.get("runner_outcome") in ("measured", "not_applicable")
                and record.get("input_digest") == digest
            ):
                ts = audit.normalize_ts(record["timestamp"])
                return audit.record_relpath(record, ts)
    except (OSError, ValueError, KeyError) as exc:
        # Fail closed: launching would spend quota on a state the reuse check could not verify.
        detail = f"reuse check: {_one_line(str(exc))[:300]} — repair or move that file and re-run"
        raise _Fail("audit_unwritable", "audit_tree_unreadable", detail) from None
    return None


def _base_primitive_args(binding: dr.Binding, rec: dict, matched: list[str]) -> list[str]:
    argv = [
        "--timeout",
        str(binding.timeout_seconds),
        "--dimension",
        binding.entry,
        "--binding",
        binding.id,
        "--lens",
        binding.entry,
        "--base-sha",
        rec["base_sha"],
        "--head-sha",
        rec["head_sha"],
        "--prompt-template-version",
        rec["prompt_template_version"],
    ]
    for path in matched:
        argv.append(f"--matched-file={path}")
    return argv


def _cmd_measure(args: argparse.Namespace, root: Path) -> int:
    rec = _blank_record(
        str(uuid.uuid4()), "keychain" if args.allow_keychain_auth else "require-env-auth"
    )
    lock = _Lock()
    exit_code = 0
    try:
        _measure(args, root, rec, lock)
    except _Fail as fail:
        rec.update(
            runner_outcome=fail.outcome,
            error_code=fail.code,
            error_detail=_bounded_detail(fail.detail),
        )
        sys.stderr.write(
            f"dimension_sweep: {fail.outcome}: {fail.code or '-'}: {rec['error_detail']}\n"
        )
        exit_code = 1
    finally:
        lock.release()
    return _publish(rec, root, exit_code)


def _measure(args: argparse.Namespace, root: Path, rec: dict, lock: _Lock) -> None:
    try:
        reg = dr.load(root)
    except dr.RegistryError as exc:
        raise _Fail("registry_error", exc.code, exc.message) from None
    rec["registry_digest"] = reg.digest
    binding = reg.bindings.get(MEASURED_BINDING)
    if binding is None or binding.kind != "judgment":
        raise _Fail("binding_absent", None, f"{MEASURED_BINDING} is absent from the registry")
    assert binding.agent and binding.posture and binding.prompt_template
    rec.update(
        entry=binding.entry,
        agent=binding.agent,
        posture=binding.posture,
        timeout_seconds=binding.timeout_seconds,
    )
    try:
        template = (root / binding.prompt_template).read_bytes()
    except OSError as exc:
        raise _Fail("registry_error", "prompt_unreadable", str(exc)) from None
    rec["prompt_template_version"] = f"sha256:{_sha256(template)}"

    base_sha, head_sha, changed, numstat = _resolve_git_inputs(root, args.base, rec)
    if _run_git(root, "status", "--porcelain", "--untracked-files=no").strip():
        raise _Fail("dirty_tree", None, "the tracked tree has uncommitted changes")
    lock.acquire(_lock_path(root))

    try:
        items = dr.resolve_for_diff(reg, changed)
    except dr.RegistryError as exc:
        raise _Fail("git_error", exc.code, exc.message) from None
    item = next(i for i in items if i.binding.id == MEASURED_BINDING)
    matched = list(item.matched_files)
    rec["matched_files_count"] = len(matched)
    rec["matched_lines_changed"] = sum(numstat.get(p, 0) for p in matched)

    rendered = _render_input(template, base_sha, head_sha, matched) if matched else None
    if rendered is not None:
        rec["input_bytes"] = len(rendered)
    digest = _precompute_digest(root, binding, rec=rec, matched=matched, rendered=rendered)
    rec["input_digest"] = digest

    prior = _find_prior(root, digest) if digest else None
    if prior is not None:
        rec.update(runner_outcome="reused", reused_from=prior)
        return

    prefix = ["bash", str(root / "bootstrap" / "invoke_agent.sh"), "--agent", binding.agent]
    common = _base_primitive_args(binding, rec, matched)
    if rendered is None:
        argv = prefix + ["--posture", binding.posture] + common
        argv.append(f"--not-applicable={item.reason}")
        _launch(args, root, rec, argv, binding, None, is_launch=False)
        rec["runner_outcome"] = "not_applicable"
        return

    argv = prefix + ["--posture", binding.posture]
    if not args.allow_keychain_auth:
        argv.append("--require-env-auth")
    try:
        fd, tmp_name = tempfile.mkstemp(prefix="hos-w6-input-")
    except OSError as exc:
        raise _Fail("audit_unwritable", "input_tempfile_unwritable", str(exc)) from None
    try:
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(rendered)
        except OSError as exc:
            raise _Fail("audit_unwritable", "input_tempfile_unwritable", str(exc)) from None
        _launch(args, root, rec, argv + ["--input-file", tmp_name] + common, binding, digest)
    finally:
        os.unlink(tmp_name)
    rec["runner_outcome"] = "measured"


def _launch(
    args: argparse.Namespace,
    root: Path,
    rec: dict,
    argv: list[str],
    binding: dr.Binding,
    digest: str | None,
    *,
    is_launch: bool = True,
) -> None:
    """Start record, seam call, document ingestion. Raises _Fail on any no-document path."""
    if is_launch:
        start = {
            "event": EVENT_START,
            "schema_version": SCHEMA_VERSION,
            "timestamp": _now_iso(),
            "run_id": rec["run_id"],
            "binding": MEASURED_BINDING,
            "base_sha": rec["base_sha"],
            "head_sha": rec["head_sha"],
            "input_digest": digest,
            "auth_mode": rec["auth_mode"],
        }
        try:
            _write(start, root)
        except Exception as exc:  # noqa: BLE001 — never launch without a durable start record
            sys.stderr.write(f"dimension_sweep: record not written: {_one_line(str(exc))}\n")
            raise _Fail("audit_unwritable", "start_record_unwritable", str(exc)) from None
    began = time.monotonic()
    try:
        _observe(args, root, rec, argv, binding, digest, began)
    except _Fail:
        raise
    except BaseException as exc:
        # §G.6: SIGINT or any other exception after the start record — record it, re-raise.
        rec.update(
            runner_outcome="interrupted",
            error_code=type(exc).__name__,
            error_detail=_bounded_detail(str(exc)),
            runner_wall_ms=int((time.monotonic() - began) * 1000),
        )
        rec["timestamp"] = _now_iso()
        try:
            _write(rec, root)
        except Exception:  # noqa: BLE001 — best effort while already unwinding
            pass
        raise


def _observe(
    args: argparse.Namespace,
    root: Path,
    rec: dict,
    argv: list[str],
    binding: dr.Binding,
    digest: str | None,
    began: float,
) -> None:
    """Seam call and document ingestion. Raises _Fail on any no-document path."""
    try:
        with _signals_as_interrupt():
            rc, out, err = _run_primitive(
                argv, timeout_s=_runner_timeout_s(binding.timeout_seconds)
            )
    except _PrimitiveTimeout:
        rec["runner_wall_ms"] = int((time.monotonic() - began) * 1000)
        raise _Fail(
            "runner_timeout", None, "the primitive exceeded the runner wall clock"
        ) from None
    rec["runner_wall_ms"] = int((time.monotonic() - began) * 1000)
    rec["primitive_exit_code"] = rc
    if err:
        sys.stderr.write(err.decode("utf-8", errors="replace"))
        sys.stderr.flush()
    if rc != 0:
        tail = _one_line(err.decode("utf-8", errors="replace")[-_ERROR_DETAIL_MAX:])
        raise _Fail("primitive_no_document", f"exit_{rc}", tail)
    doc = _parse_document(out)
    if doc is None:
        raise _Fail("primitive_bad_output", None, "stdout is not exactly one W1 document")
    _ingest_document(rec, doc)
    if digest is not None:
        rec["input_digest_match"] = digest == _as_dict(doc.get("input")).get("input_digest")
    if args.document_out:
        try:
            _write_document(Path(args.document_out), out, root)
        except OSError as exc:
            sys.stderr.write(f"dimension_sweep: --document-out not written: {exc}\n")


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


def _stats(values: list, *, with_sum: bool = False) -> dict:
    nums = sorted(v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool))
    if not nums:
        return {"n": 0}
    n = len(nums)

    def rank(percent: int) -> float:
        return nums[max(-(-percent * n // 100), 1) - 1]

    out = {"n": n, "min": nums[0], "p50": rank(50), "p90": rank(90), "max": nums[-1]}
    if with_sum:
        out["sum"] = round(sum(nums), 6)
    return out


def _count_by(values: list) -> dict:
    counts: dict[str, int] = {}
    for value in values:
        key = "null" if value is None else str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _read_measurements(root: Path, since: str | None) -> tuple[list[dict], list[dict]]:
    results: list[dict] = []
    starts: list[dict] = []
    for raw in _audit_log().read_stream(str(root)):
        record = json.loads(raw)
        if not isinstance(record, dict) or record.get("event") not in (EVENT_RESULT, EVENT_START):
            continue
        if since is not None and str(record.get("timestamp", ""))[:10] < since:
            continue
        (results if record["event"] == EVENT_RESULT else starts).append(record)
    return results, starts


def _build_report(results: list[dict], starts: list[dict], since: str | None) -> dict:
    # Document-bearing records only (TD-D65): a run with no document is never "launched".
    launched = [
        r for r in results if r.get("launched") is True and r.get("runner_outcome") == "measured"
    ]
    evaluated = [r for r in launched if r.get("outcome_detail") not in _PRE_EVALUATION_DETAILS]
    produced = [r for r in launched if r.get("payload_extractable") is True]
    completed = [r for r in launched if r.get("outcome") == "completed"]
    tool_runs: list[str] = []
    for r in launched:
        tools = r.get("permission_denied_tools")
        tool_runs += [t for t in tools if isinstance(t, str)] if isinstance(tools, list) else []

    def dist(rows: list[dict], key: str, **kw: bool) -> dict:
        return _stats([r.get(key) for r in rows], **kw)

    unknown = {f for r in results for f in (r.get("envelope_unknown_fields") or [])}
    versions = {r["cli_version"] for r in results if isinstance(r.get("cli_version"), str)}
    result_ids = {r.get("run_id") for r in results}
    return {
        "schema": REPORT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "binding": MEASURED_BINDING,
        "since": since,
        "runs": len(results),
        "abandoned": sum(1 for s in starts if s.get("run_id") not in result_ids),
        "by_runner_outcome": _count_by([r.get("runner_outcome") for r in results]),
        "launched": len(launched),
        "by_outcome_detail": _count_by([r.get("outcome_detail") for r in launched]),
        "terminal_reason_evaluated": len(evaluated),
        "terminal_reason_missing_count": sum(
            1 for r in launched if r.get("terminal_reason_missing") is True
        ),
        "usage_limit_count": sum(1 for r in launched if r.get("outcome_detail") == "usage_limit"),
        "timed_out_count": sum(1 for r in launched if r.get("timed_out") is True),
        "input_digest_mismatch_count": sum(
            1 for r in results if r.get("input_digest_match") is False
        ),
        "payload_extractable_count": len(produced),
        "by_permission_denied_tool": _count_by(tool_runs),
        "duration_ms": dist(launched, "duration_ms"),
        "duration_ms_completed_only": dist(completed, "duration_ms"),
        "duration_ms_payload_produced": dist(produced, "duration_ms"),
        "total_cost_usd": dist(launched, "total_cost_usd", with_sum=True),
        "num_turns": dist(launched, "num_turns"),
        "matched_lines_changed": dist(launched, "matched_lines_changed"),
        "envelope_unknown_fields": sorted(unknown),
        "cli_versions": sorted(versions),
    }


def _cmd_report(args: argparse.Namespace, root: Path) -> int:
    if args.since is not None and not _SINCE_RE.match(args.since):
        raise _UsageError(f"--since must be YYYY-MM-DD, got: {args.since!r}")
    try:
        results, starts = _read_measurements(root, args.since)
    except ValueError as exc:
        sys.stderr.write(f"dimension_sweep: {_one_line(str(exc))}\n")
        return 1
    report = _build_report(results, starts, args.since)
    evaluated = report["terminal_reason_evaluated"]
    missing = report["terminal_reason_missing_count"]
    if evaluated == 0:
        sys.stderr.write(
            "dimension_sweep: terminal_reason evaluated on 0 runs — "
            "ADR-1643 §9.2 residual not yet discharged\n"
        )
    elif missing > 0:
        sys.stderr.write(
            f"dimension_sweep: terminal_reason_missing observed {missing}/{evaluated} launched — "
            "ADR-1643 §9.2: A4 reverts to tolerating absence; route to architect\n"
        )
    sys.stdout.write(json.dumps(report, sort_keys=True, indent=2) + "\n")
    return 0


def main(argv: list[str] | None = None, *, repo_root: str | Path | None = None) -> int:
    """`repo_root` is a test-only injection point; argparse never defines it."""
    root = Path(repo_root).resolve() if repo_root is not None else _DEFAULT_REPO_ROOT
    real_argv = sys.argv[1:] if argv is None else list(argv)
    try:
        args = _build_parser().parse_args(real_argv)
        if args.command is None:
            raise _UsageError("a subcommand is required: measure | report")
        if args.command == "report":
            return _cmd_report(args, root)
        if args.base.startswith("-"):
            raise _UsageError(f"--base must be a ref, not an option: {args.base!r}")
        _refuse_if_nested()
        _check_document_out(args.document_out, root)
        return _cmd_measure(args, root)
    except _Refusal as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    except _UsageError as exc:
        sys.stderr.write(f"dimension_sweep_cli.py: usage: {_one_line(str(exc))}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
