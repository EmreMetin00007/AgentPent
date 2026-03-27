"""Startup smoke checks for Docker health probes and CI smoke runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from config.settings import settings
from core.orchestrator import Orchestrator
from core.runtime import enforce_supported_python, format_python_version
from core.scope_guard import scope_guard


def collect_startup_state() -> Dict[str, object]:
    scopes_path = Path(settings.scopes_file)
    if not scopes_path.exists():
        raise RuntimeError("Scope file is missing: {}".format(scopes_path))

    profile_names: List[str] = scope_guard.profile_names
    if not profile_names:
        raise RuntimeError("No scope profiles are configured.")

    orchestrator = Orchestrator()
    if not orchestrator.registered_agents:
        raise RuntimeError("No agents were registered during startup.")

    return {
        "python": format_python_version(),
        "active_profile": scope_guard._active_profile,
        "scope_profiles": profile_names,
        "registered_agents": len(orchestrator.registered_agents),
        "reports_dir": str(Path(settings.reports_dir)),
    }


def run_startup_smoke_check() -> Dict[str, object]:
    enforce_supported_python()
    return collect_startup_state()


def main() -> None:
    result = run_startup_smoke_check()
    print(json.dumps(result, sort_keys=True, ensure_ascii=True))


if __name__ == "__main__":
    main()
