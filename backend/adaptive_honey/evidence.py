from __future__ import annotations

import re

from .models import Indicator, TechniqueEvidence


RULES = [
    (r"^\s*(?:sudo\s+)?(?:sh|bash|zsh)\b|[|;&]", "T1059.004", "Unix Shell", "Shell-mediated execution syntax was observed"),
    (r"\b(uname|hostnamectl|lscpu|cat\s+/etc/(?:os-release|issue))\b", "T1082", "System Information Discovery", "The command requested operating-system or architecture information"),
    (r"\b(ls|find|tree|dir)\b", "T1083", "File and Directory Discovery", "The command enumerated files or directories"),
    (r"\b(curl|wget|scp|ftp)\b", "T1105", "Ingress Tool Transfer", "An external tool transfer was attempted"),
    (r"\b(crontab|/etc/cron|cron\.d)\b", "T1053.003", "Cron", "A scheduled-job operation was attempted"),
    (r"authorized_keys", "T1098.004", "SSH Authorized Keys", "An SSH authorized-key operation was attempted"),
]


def map_techniques(command: str, event_id: str, exit_code: int) -> list[TechniqueEvidence]:
    status = "simulated_success" if exit_code == 0 else "attempted"
    return [
        TechniqueEvidence(technique_id=tid, name=name, confidence=.92 if exit_code == 0 else .78, status=status, explanation=explanation, event_ids=[event_id])
        for pattern, tid, name, explanation in RULES if re.search(pattern, command, re.I)
    ]


def extract_indicators(command: str, event_id: str) -> list[Indicator]:
    found: list[Indicator] = []
    patterns = {
        "url": r"https?://[^\s'\"<>]+",
        "ipv4": r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])",
        "domain": r"(?<![/\w.-])(?:[a-z0-9-]+\.)+[a-z]{2,}(?![\w.-])",
        "sha256": r"\b[a-fA-F0-9]{64}\b",
    }
    seen: set[tuple[str, str]] = set()
    for kind, pattern in patterns.items():
        for value in re.findall(pattern, command, re.I):
            key = (kind, value)
            if key not in seen:
                found.append(Indicator(kind=kind, value=value, event_id=event_id))
                seen.add(key)
    return found

