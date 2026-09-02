import re
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.utils.command import run_command

router = APIRouter(
    prefix="/api/chaos",
    tags=["Chaos"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNBOOK = PROJECT_ROOT / "chaos" / "runbook.sh"
SEED_SCRIPT = PROJECT_ROOT / "chaos" / "seed-data.sh"

INJECT_ACTIONS = {
    "aerospike-down": "aerospike-down",
    "yugabyte-down": "yugabyte-down",
    "pod-crash": "pod-crash",
    "pod-delete": "pod-delete",
    "pod-cpu": "pod-cpu",
    "pod-memory": "pod-memory",
    "pod-latency": "pod-latency",
    "flaky-latency": "flaky-latency",
    "system-pod-kill": "system-pod-kill",
    "node-cordon": "node-cordon",
    "node-drain": "node-drain",
    "node-network-latency": "node-network-latency",
}

RECOVER_ACTIONS = {
    "aerospike-up": "aerospike-up",
    "yugabyte-up": "yugabyte-up",
    "latency-off": "latency-off",
    "flaky-latency-off": "flaky-latency-off",
    "network-latency-off": "network-latency-off",
    "uncordon": "uncordon",
    "all": "all",
}

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class ActionRequest(BaseModel):
    action: str


class GameDayRequest(BaseModel):
    action: str
    duration_s: int = 30


def _strip_ansi(text):
    return ANSI_RE.sub("", text or "")


def _command(command):
    result = run_command(command)
    return {
        "success": result.get("success", False),
        "stdout": _strip_ansi(result.get("stdout", "")),
        "stderr": _strip_ansi(result.get("stderr", "")),
        "returncode": result.get("returncode", -1),
    }


def _container_state(name):
    docker = _command(
        ["docker", "ps", "-a", "--filter", f"name={name}", "--format", "{{.Status}}"]
    )
    stdout = docker.get("stdout", "").strip()

    if not stdout and (not docker.get("success") or docker.get("returncode") != 0):
        podman = _command(
            ["podman", "ps", "-a", "--filter", f"name={name}", "--format", "{{.Status}}"]
        )
        stdout = podman.get("stdout", "").strip()

    if stdout.startswith("Up"):
        return "running"
    if stdout:
        return "stopped"
    return "missing"


def _worker_node_state():
    result = _command(["kubectl", "get", "nodes", "--no-headers"])
    for line in result.get("stdout", "").splitlines():
        columns = line.split()
        if columns and columns[0] == "opensre-demo-worker" and len(columns) > 1:
            status = columns[1]
            if "SchedulingDisabled" in status:
                return "cordoned"
            if status == "Ready":
                return "ready"
            return status.lower()
    return "unknown"


def _opensre_pods():
    result = _command(["kubectl", "get", "pods", "-n", "opensre", "--no-headers"])
    pods = []
    for line in result.get("stdout", "").splitlines():
        columns = line.split()
        if len(columns) >= 4:
            pods.append(
                {
                    "name": columns[0],
                    "ready": columns[1],
                    "status": columns[2],
                    "restarts": columns[3],
                }
            )
    return pods


def _action_failed(action, result):
    return {
        "success": False,
        "action": action,
        "error": result.get("stderr") or result.get("stdout") or "Unknown failure",
    }


@router.get("/actions")
def actions():
    return {
        "success": True,
        "inject": list(INJECT_ACTIONS.keys()),
        "recover": list(RECOVER_ACTIONS.keys()),
        "ops": ["seed"],
    }


@router.get("/history")
def history(limit: int = 200):
    """Newest-first experiment timeline from chaos/experiments/events.jsonl."""
    from app.services import game_day

    return game_day.history(limit=min(limit, 500))


@router.get("/active")
def active_faults():
    """Currently-active faults tracked in chaos/experiments/active.json."""
    from app.services import game_day

    return game_day.active()


@router.get("/status")
def status():
    runbook = _command(["bash", str(RUNBOOK), "status"])

    return {
        "success": True,
        "containers": {
            "aerospike": _container_state("aerospike"),
            "yugabyte": _container_state("yugabyte"),
        },
        "node": {
            "name": "opensre-demo-worker",
            "state": _worker_node_state(),
        },
        "pods": _opensre_pods(),
        "runbook": runbook,
    }


@router.post("/inject")
def inject(request: ActionRequest):
    action = INJECT_ACTIONS.get(request.action)
    if not action:
        return {
            "success": False,
            "error": f"Unknown failure '{request.action}'. Available: {list(INJECT_ACTIONS.keys())}",
        }

    result = _command(["bash", str(RUNBOOK), action])
    if not result.get("success"):
        return _action_failed(action, result)

    return {
        "success": True,
        "action": action,
        "stdout": result.get("stdout", ""),
    }


@router.post("/recover")
def recover(request: ActionRequest):
    action = RECOVER_ACTIONS.get(request.action)
    if not action:
        return {
            "success": False,
            "error": f"Unknown recovery '{request.action}'. Available: {list(RECOVER_ACTIONS.keys())}",
        }

    result = _command(["bash", str(RUNBOOK), "recover", action])
    if not result.get("success"):
        return _action_failed(action, result)

    return {
        "success": True,
        "action": action,
        "stdout": result.get("stdout", ""),
    }


@router.post("/seed")
def seed():
    result = _command(["bash", str(SEED_SCRIPT)])
    if not result.get("success"):
        return _action_failed("seed", result)

    return {
        "success": True,
        "action": "seed",
        "stdout": result.get("stdout", ""),
    }


@router.post("/game-day")
def game_day(request: GameDayRequest):
    """Run a full baseline -> inject -> measure -> recover -> report cycle."""
    from app.services import game_day as game_day_service

    return game_day_service.run_game_day(request.action, request.duration_s)