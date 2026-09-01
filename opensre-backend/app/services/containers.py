import json
import shutil

from app.utils.command import run_command


def _runtime():
    for name in ("podman", "docker"):
        if shutil.which(name):
            return name
    return None


def _inspect(name):
    runtime = _runtime()

    if not runtime:
        return {"success": False, "error": "No container runtime found (podman/docker)"}

    return run_command([runtime, "inspect", name, "--format", "{{json .State}}"])


def container_state(name):
    result = _inspect(name)

    if not result.get("success"):
        return result

    try:
        state = json.loads(result.get("stdout", "").strip().splitlines()[-1])
    except Exception as e:
        return {"success": False, "error": str(e), "raw": result.get("stdout")}

    return {
        "success": True,
        "name": name,
        "running": state.get("Running"),
        "status": state.get("Status"),
        "exit_code": state.get("ExitCode"),
        "restart_count": state.get("RestartCount"),
        "oom_killed": state.get("OOMKilled"),
        "error": state.get("Error"),
        "started_at": state.get("StartedAt"),
        "finished_at": state.get("FinishedAt"),
        "raw": state,
    }


def container_logs(name, tail=150):
    runtime = _runtime()

    if not runtime:
        return {"success": False, "error": "No container runtime found (podman/docker)"}

    return run_command([runtime, "logs", "--tail", str(tail), name])