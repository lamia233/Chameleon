from __future__ import annotations

import threading
import time
from collections import defaultdict
from pathlib import Path

from .deception import choose_and_apply
from .emulator import SafeShellEmulator
from .evidence import extract_indicators, map_techniques
from .models import BehaviorProfile, SessionEvent, SessionState
from .personas import PERSONAS, initial_files
from .profiling import profile
from .store import EventStore


class HoneyService:
    def __init__(self, db_path: str | Path):
        self.store = EventStore(db_path)
        self.emulator = SafeShellEmulator()
        self.locks: defaultdict[str, threading.RLock] = defaultdict(threading.RLock)
        self.command_times: defaultdict[str, list[float]] = defaultdict(list)

    def create(self, persona_id: str, source_ip: str, username: str) -> tuple[SessionState, BehaviorProfile]:
        persona = PERSONAS[persona_id]
        state = SessionState(persona=persona, username=username, source_ip=source_ip, cwd=f"/home/{username}", files=initial_files(persona_id, username))
        current_profile = profile([])
        self.store.save_session(state.id, state.model_dump(), current_profile.model_dump(), state.created_at)
        return state, current_profile

    def command(self, session_id: str, command: str):
        with self.locks[session_id]:
            record = self.store.get_session(session_id)
            if not record: raise KeyError(session_id)
            state = SessionState.model_validate(record["state"])
            if state.status != "active": raise ValueError("session is closed")
            events = self.store.events(session_id)
            state.history.append(command)
            intervals = []
            now = time.perf_counter()
            if self.command_times[session_id]: intervals.append((now-self.command_times[session_id][-1])*1000)
            self.command_times[session_id].append(now)
            current_profile = profile(state.history, intervals)
            decision = choose_and_apply(state, current_profile)
            cwd_before = state.cwd
            started = time.perf_counter()
            response, diff = self.emulator.execute(state, command)
            latency = (time.perf_counter()-started)*1000
            event = SessionEvent(session_id=session_id, sequence=len(events)+1, command=command, response=response, cwd_before=cwd_before, cwd_after=state.cwd, latency_ms=round(latency, 3), state_diff=diff, deception=decision)
            techniques = map_techniques(command, event.id, response.exit_code)
            indicators = extract_indicators(command, event.id)
            self.store.add_event(session_id, event.model_dump(), [t.model_dump() for t in techniques], [i.model_dump() for i in indicators])
            self.store.save_session(state.id, state.model_dump(), current_profile.model_dump(), state.created_at)
            return state, current_profile, event, techniques, indicators

