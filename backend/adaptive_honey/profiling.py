from __future__ import annotations

import re

from .models import BehaviorProfile, ProfileDimension


DISCOVERY = re.compile(r"\b(uname|id|whoami|hostname|ls|find|ps|ip|ifconfig|netstat|ss|lscpu|cat /etc)\b")
CREDENTIAL = re.compile(r"\b(passwd|shadow|\.env|credential|secret|id_rsa|authorized_keys|config)\b", re.I)
PAYLOAD = re.compile(r"\b(curl|wget|scp|ftp|base64|python.*http|chmod \+x)\b", re.I)
PERSISTENCE = re.compile(r"\b(crontab|systemctl enable|authorized_keys|rc\.local)\b", re.I)
RESOURCE = re.compile(r"\b(nproc|lscpu|free|cpuinfo|xmrig|miner)\b", re.I)
COMPLEX = re.compile(r"(\||&&|;|\$\(|`|awk|sed|xargs|/dev/tcp)")


def _normalize(scores: dict[str, float]) -> dict[str, float]:
    total = sum(scores.values()) or 1
    return {k: round(v / total, 3) for k, v in scores.items()}


def profile(history: list[str], intervals_ms: list[float] | None = None) -> BehaviorProfile:
    joined = "\n".join(history)
    count = len(history)
    repeated = count - len(set(history))
    burst = bool(intervals_ms and len(intervals_ms) >= 2 and sum(intervals_ms[-3:]) / min(3, len(intervals_ms)) < 350)

    auto_scores = {"automated": 1 + repeated * .8 + (2 if burst else 0), "interactive": 1 + min(count, 5) * .2, "mixed": .8, "unknown": 2 if count < 2 else .4}
    if any("--help" in c or c.strip().startswith("cd ") for c in history):
        auto_scores["interactive"] += 1

    complex_count = len(COMPLEX.findall(joined))
    breadth = sum(bool(rx.search(joined)) for rx in (DISCOVERY, CREDENTIAL, PAYLOAD, PERSISTENCE, RESOURCE))
    soph_scores = {"basic": 1.5 + count * .08, "intermediate": .7 + complex_count * .7 + breadth * .25, "advanced_behavior": .3 + max(0, complex_count - 2) * .8, "insufficient_evidence": 3 if count < 3 else .3}

    obj_scores = {
        "discovery": 1 + len(DISCOVERY.findall(joined)) * .7,
        "credential_seeking": .5 + len(CREDENTIAL.findall(joined)) * 1.2,
        "payload_deployment": .5 + len(PAYLOAD.findall(joined)) * 1.2,
        "persistence": .4 + len(PERSISTENCE.findall(joined)) * 1.4,
        "resource_abuse": .4 + len(RESOURCE.findall(joined)) * 1.0,
        "unknown": 2 if count < 2 else .3,
    }

    def dimension(scores: dict[str, float], evidence: list[str]) -> ProfileDimension:
        probs = _normalize(scores)
        label = max(probs, key=probs.get)
        return ProfileDimension(label=label, confidence=probs[label], probabilities=probs, evidence=evidence[:4])

    return BehaviorProfile(
        automation=dimension(auto_scores, (["rapid command timing"] if burst else []) + (["repeated command sequence"] if repeated else [])),
        sophistication=dimension(soph_scores, [f"{complex_count} complex shell constructs", f"{breadth} behavior categories observed"] if count else []),
        objective=dimension(obj_scores, [f"command evidence supports {max(obj_scores, key=obj_scores.get).replace('_', ' ')}"] if count else []),
    )

