from __future__ import annotations

from .models import BehaviorProfile, DeceptionDecision, SessionState, VirtualFile


def choose_and_apply(state: SessionState, profile: BehaviorProfile) -> DeceptionDecision:
    objective = profile.objective.label
    confidence = profile.objective.confidence
    eligible = ["do_nothing"]
    action = "do_nothing"
    reason = "Insufficient evidence; preserving the neutral persona"

    if objective == "discovery":
        eligible.append("reveal_service_metadata")
        if confidence >= .32 and "service_metadata" not in state.exposed_artifacts:
            action, reason = "reveal_service_metadata", "Discovery behavior makes synthetic service metadata relevant"
    elif objective == "credential_seeking":
        eligible.extend(["reveal_backup_directory", "reveal_app_config"])
        if confidence >= .35 and "app_config" not in state.exposed_artifacts:
            action, reason = "reveal_app_config", "Configuration searches justify a synthetic, nonfunctional credential lure"
    elif objective == "persistence":
        eligible.append("enable_virtual_persistence")
        action, reason = "enable_virtual_persistence", "Persistence changes can be recorded safely in virtual state"
    elif objective == "resource_abuse":
        eligible.append("reveal_resource_profile")
        if "resource_profile" not in state.exposed_artifacts:
            action, reason = "reveal_resource_profile", "Resource inspection supports revealing consistent virtual capacity"

    applied = action != "do_nothing"
    if action == "reveal_service_metadata":
        path = "/opt/api/.service-info" if state.persona.id == "development" else "/srv/archive/.service-info"
        state.files[path] = VirtualFile(path=path, owner=state.username, mode="640", content="role=internal\nenvironment=staging\nregion=dhaka-1\n")
        state.exposed_artifacts.append("service_metadata")
    elif action == "reveal_app_config":
        base = "/opt/api" if state.persona.id == "development" else "/srv/archive"
        path = f"{base}/.env.backup"
        state.files[path] = VirtualFile(path=path, owner=state.username, mode="640", content="DB_HOST=db-internal.invalid\nDB_USER=app_readonly\nDB_PASSWORD=SYNTHETIC-NOT-VALID\n")
        state.exposed_artifacts.append("app_config")
    elif action == "reveal_resource_profile":
        state.files["/tmp/.capacity"] = VirtualFile(path="/tmp/.capacity", owner=state.username, mode="600", content="vcpus=8\nmemory_gb=16\n")
        state.exposed_artifacts.append("resource_profile")

    return DeceptionDecision(action=action, reason=reason, eligible_actions=eligible, applied=applied)

