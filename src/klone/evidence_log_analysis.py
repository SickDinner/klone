"""Parse bounded log text as untrusted claims, never as executable instructions."""
from __future__ import annotations

import re

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
COUNTS = re.compile(r"(?<!\w)(\d+) (passed|failed|errors?|skipped|warnings?|xfailed|xpassed|deselected)\b")
PYTEST_SUMMARY = re.compile(
    r"^\s*(?:=+\s*)?(?:\d+ (?:passed|failed|errors?|skipped|warnings?|xfailed|xpassed|deselected|subtests passed)"
    r"(?:, )?\s*)+in \d+(?:\.\d+)?s(?:\s*\([^\n]*\))?\s*=*\s*$"
)


def analyze(raw: bytes, stage: str) -> dict:
    result = {"reported_status": "unknown", "framework": None, "summary": None,
              "counts": {}, "empty": not raw,
              "execution_authenticated": False}
    if not raw:
        result["reason"] = "empty_log_is_not_proof_of_failure_or_success"
        return result
    try:
        text = ANSI.sub("", raw.decode("utf-8"))
    except UnicodeError:
        result["reason"] = "invalid_utf8"
        return result
    candidates = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if PYTEST_SUMMARY.fullmatch(line):
            counts = {}
            for match in COUNTS.finditer(line):
                key = {"error": "errors", "warning": "warnings"}.get(match[2], match[2])
                counts[key] = int(match[1])
            subs = re.search(r"(\d+) subtests passed", line)
            if subs:
                counts["subtests"] = int(subs[1])
            status = ("failed" if counts.get("failed", 0) or counts.get("errors", 0)
                      else "passed" if counts.get("passed", 0) else "unknown")
            candidates.append((index, "pytest", status, line, counts))
        if re.fullmatch(r"OK(?: \([^\n]*\))?", line.strip()):
            prior = "\n".join(lines[max(0, index - 5):index])
            ran = re.search(r"Ran (\d+) tests? in [\d.]+s", prior)
            if ran:
                candidates.append((index, "unittest", "passed" if int(ran[1]) else "unknown",
                                   line, {"tests": int(ran[1])}))
        if re.fullmatch(r"FAILED \((?:failures=\d+|errors=\d+|skipped=\d+)(?:, (?:failures=\d+|errors=\d+|skipped=\d+))*\)", line.strip()):
            counts = {key: int(value) for key, value in re.findall(r"(failures|errors|skipped)=(\d+)", line)}
            candidates.append((index, "unittest", "failed", line, counts))
    if candidates:
        _, framework, status, summary, counts = candidates[-1]
        result.update(reported_status=status, framework=framework,
                      summary=summary.strip()[:512], counts=counts,
                      summary_count=len(candidates), reason="untrusted_test_summary_claim")
    elif stage == "torch_probe" and text.strip() == "Optional torch demo not present in this checkout":
        result.update(reported_status="not_present", framework="termux_battery",
                      summary=text.strip(), reason="untrusted_optional_stage_claim")
    elif stage == "syntax" and any(re.match(r"^(?:\*\*\* Error compiling|(?:\w*Error|SyntaxError):)", line) for line in lines):
        result.update(reported_status="failed", reason="reported_compilation_error")
    else:
        result["reason"] = "no_recognized_test_summary"
    return result
