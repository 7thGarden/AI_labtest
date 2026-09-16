import json
import tempfile
import os
import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import investigation
from app.services import opensre_cli
from app.services import kubectl
from app.services import yugabyte
from app.services import aerospike
from app.utils.command import run_command

router = APIRouter(
    prefix="/api/demo",
    tags=["Demo"],
)

WORKER_NODE = "opensre-demo-worker"
STRESS_POD = "node-stress-demo"
STRESS_NAMESPACE = "opensre"

INSTANCE_ROWS = [
    (21, "OrderService-001-instance"),
    (22, "OrderService-002-instance"),
    (23, "CatalogSync-instance"),
]

AEROSPIKE_INSTANCES = [
    ("instance-001", "OrderService-001", "active"),
    ("instance-002", "OrderService-002", "active"),
    ("instance-003", "CatalogSync-instance", "stale"),
]


class TargetRequest(BaseModel):
    target: str  # "yugabyte" or "aerospike"


def _target_to_container(target: str):
    return {"yugabyte": "yugabyte", "aerospike": "aerospike"}.get(target, target)


def _seed_yugabyte():
    yugabyte.execute(
        "CREATE TABLE IF NOT EXISTS service_instances "
        "(id INT PRIMARY KEY, name TEXT NOT NULL)"
    )
    inserted = []
    for row_id, name in INSTANCE_ROWS:
        res = yugabyte.execute(
            f"INSERT INTO service_instances (id, name) "
            f"VALUES ({row_id}, '{name}') "
            f"ON CONFLICT (id) DO UPDATE SET name = '{name}' "
            f"RETURNING *"
        )
        if res.get("success"):
            inserted.append(name)
    return {"success": True, "inserted": inserted, "table": "service_instances"}


def _seed_aerospike():
    inserted = []
    for key, name, status in AEROSPIKE_INSTANCES:
        res = aerospike.write("test", "demo", key, {
            "name": name, "status": status, "_key": key,
        })
        if res.get("success"):
            inserted.append(name)
    return {"success": True, "inserted": inserted}


def _stop_container(name: str):
    result = run_command(["docker", "stop", name])
    return {
        "success": result.get("success", False),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    }


def _start_container(name: str):
    result = run_command(["docker", "start", name])
    return {
        "success": result.get("success", False),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    }


# ------------------------------------------------------------------
# Step 1: Seed + stop  (leaves DB DOWN so audience can see red health)
# ------------------------------------------------------------------
@router.post("/db-failure/fail")
def fail(request: TargetRequest):
    target = request.target.lower()
    container = _target_to_container(target)

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    seed = _seed_yugabyte() if target == "yugabyte" else _seed_aerospike()
    stop = _stop_container(container)

    return {
        "success": stop.get("success", False),
        "target": target,
        "container": container,
        "seed": seed,
        "fault": {
            "action": f"{target}-down",
            "injected": stop.get("success", False),
            "container_stopped": container,
        },
    }


# ------------------------------------------------------------------
# Step 2: Investigate (DB is still DOWN — collect evidence + RCA)
# ------------------------------------------------------------------
@router.post("/db-failure/investigate")
def investigate(request: TargetRequest):
    target = request.target.lower()
    container = _target_to_container(target)

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    evidence_result = investigation.collect_target_evidence(target)

    if not evidence_result.get("success"):
        return {
            "success": False,
            "error": evidence_result.get("error", "Evidence collection failed"),
        }

    evidence = evidence_result["evidence"]
    opensre_result = opensre_cli.investigate(evidence)

    return {
        "success": opensre_result.get("returncode") == 0,
        "target": target,
        "container": container,
        "evidence": evidence,
        "opensre": opensre_result,
    }


# ------------------------------------------------------------------
# Step 3: Recover  (DB comes back UP — health flips green)
# ------------------------------------------------------------------
@router.post("/db-failure/recover")
def recover(request: TargetRequest):
    target = request.target.lower()
    container = _target_to_container(target)

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    start = _start_container(container)
    health = investigation.collect_target_evidence(target)

    return {
        "success": start.get("success", False),
        "target": target,
        "container": container,
        "recovery": {
            "action": f"{target}-up",
            "success": start.get("success", False),
            "container_restarted": container,
        },
        "health": health.get("evidence", {}),
    }


# ==================================================================
# NODE FAILURE DEMO
# ==================================================================

class NodeRequest(BaseModel):
    node: str = WORKER_NODE
    context: str | None = "kind-opensre-demo"


STRESS_YAML = """\
apiVersion: v1
kind: Pod
metadata:
  name: {pod}
  namespace: {ns}
  labels:
    app: node-stress-demo
spec:
  nodeName: {node}
  terminationGracePeriodSeconds: 5
  containers:
  - name: stress
    image: busybox:1.36
    command: ["sh", "-c", "while true; do dd if=/dev/urandom of=/tmp/fill bs=64M count=1 2>/dev/null; sleep 0.5; done"]
    resources:
      requests:
        cpu: "999m"
        memory: "512Mi"
      limits:
        cpu: "999m"
        memory: "512Mi"
"""


def _kubectl_cmd(context: str | None = None):
    cmd = ["kubectl"]
    if context:
        cmd.extend(["--context", context])
    return cmd


# ------------------------------------------------------------------
# Step 1: Cordons the worker node + deploys a stress pod
# ------------------------------------------------------------------
@router.post("/node-failure/fail")
def node_fail(request: NodeRequest):
    node = request.node
    ctx = request.context

    # Cordon node
    cordon_result = kubectl.cordon_node(node, ctx)

    # Deploy stress pod
    yaml_content = STRESS_YAML.format(pod=STRESS_POD, ns=STRESS_NAMESPACE, node=node)
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    try:
        tmp.write(yaml_content)
        tmp.close()
        apply_result = run_command(_kubectl_cmd(ctx) + ["apply", "-f", tmp.name])
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    # Get node state after cordon
    node_state = kubectl.get_node_state(node, ctx)
    node_usage = kubectl.get_node_resource_usage(node, ctx)

    return {
        "success": cordon_result.get("success", False),
        "node": node,
        "fault": {
            "action": "node-cordon",
            "cordon_success": cordon_result.get("success", False),
            "stress_pod_deployed": apply_result.get("success", False),
            "stress_pod": STRESS_POD,
            "namespace": STRESS_NAMESPACE,
        },
        "node_state": node_state.get("node") if node_state.get("success") else node_state,
        "node_usage": node_usage if node_usage.get("success") else None,
    }


# ------------------------------------------------------------------
# Step 2: Collect evidence + run OpenSRE investigation
# ------------------------------------------------------------------
@router.post("/node-failure/investigate")
def node_investigate(request: NodeRequest):
    node = request.node
    ctx = request.context

    # Collect node state
    node_state = kubectl.get_node_state(node, ctx)
    node_usage = kubectl.get_node_resource_usage(node, ctx)

    # Get node conditions for evidence summary
    conditions = []
    if node_state.get("success"):
        for c in node_state.get("node", {}).get("conditions", []):
            if c.get("status") != "True":
                continue
            conditions.append(f"{c['type']}={c['status']} ({c.get('reason', '')})")

    # Collect stack-level evidence (includes Kubernetes + VM + Grafana)
    evidence_result = investigation.collect_stack_evidence(ctx)

    evidence = evidence_result.get("evidence", {}) if evidence_result.get("success") else {}

    # Inject the node problem into evidence for OpenSRE
    evidence["node_problem"] = {
        "node": node,
        "unschedulable": node_state.get("node", {}).get("unschedulable", False) if node_state.get("success") else None,
        "conditions": conditions,
        "pod_count": node_usage.get("pod_count"),
        "restarts_total": node_usage.get("restarts_total"),
        "pods": node_usage.get("pods", []),
    }

    evidence["target"] = {
        "type": "node",
        "name": node,
    }

    # Build a question for OpenSRE
    evidence["question"] = (
        f"The Kubernetes node {node} is reporting as SchedulingDisabled "
        f"and has {node_usage.get('restarts_total', 0)} pod restarts across "
        f"{node_usage.get('pod_count', 0)} pods. "
        f"What is causing this node degradation and what should be done?"
    )

    # Run OpenSRE
    opensre_result = opensre_cli.investigate(evidence)

    return {
        "success": opensre_result.get("returncode") == 0,
        "node": node,
        "evidence": evidence,
        "opensre": opensre_result,
    }


# ------------------------------------------------------------------
# Step 3: Uncordon node + remove taint + delete stress pod
# ------------------------------------------------------------------
@router.post("/node-failure/recover")
def node_recover(request: NodeRequest):
    node = request.node
    ctx = request.context

    # Delete stress pod
    delete_result = run_command(
        _kubectl_cmd(ctx) + ["delete", "pod", STRESS_POD, "-n", STRESS_NAMESPACE, "--ignore-not-found"]
    )

    # Delete permanent stress pod too
    run_command(
        _kubectl_cmd(ctx) + ["delete", "pod", "node-stress-permanent", "-n", "opensre", "--ignore-not-found"]
    )

    # Remove taint
    untaint_result = run_command(
        _kubectl_cmd(ctx) + ["taint", "nodes", node, "demo-unhealthy-", "--overwrite"]
    )

    # Uncordon node
    uncordon_result = kubectl.uncordon_node(node, ctx)

    # Get post-recovery state
    node_state = kubectl.get_node_state(node, ctx)

    return {
        "success": uncordon_result.get("success", False),
        "node": node,
        "recovery": {
            "action": "node-uncordon",
            "uncordon_success": uncordon_result.get("success", False),
            "stress_pod_deleted": delete_result.get("success", False),
            "taint_removed": untaint_result.get("success", False),
        },
        "node_state": node_state.get("node") if node_state.get("success") else node_state,
    }


# ------------------------------------------------------------------
# List available nodes
# ------------------------------------------------------------------
@router.get("/node-failure/nodes")
def list_nodes():
    ctx = "kind-opensre-demo"
    result = kubectl.get_nodes(ctx)
    return {
        "success": result.get("success", False),
        "nodes": result.get("stdout", ""),
    }


@router.post("/node-failure/re-fail")
def node_refail(request: NodeRequest):
    """Re-cordon the node + deploy stress pod after recovery."""
    node = request.node
    ctx = request.context

    # Cordon node
    cordon_result = kubectl.cordon_node(node, ctx)

    # Add taint
    taint_result = run_command(
        _kubectl_cmd(ctx) + [
            "taint", "nodes", node, "demo-unhealthy=true:NoExecute", "--overwrite"
        ]
    )

    # Deploy stress pod
    yaml_content = STRESS_YAML.format(pod=STRESS_POD, ns=STRESS_NAMESPACE, node=node)
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    try:
        tmp.write(yaml_content)
        tmp.close()
        apply_result = run_command(_kubectl_cmd(ctx) + ["apply", "-f", tmp.name])
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    # Get node state
    node_state = kubectl.get_node_state(node, ctx)

    return {
        "success": cordon_result.get("success", False),
        "node": node,
        "fault": {
            "action": "node-cordon",
            "cordon_success": cordon_result.get("success", False),
            "taint_applied": taint_result.get("success", False),
            "stress_pod_deployed": apply_result.get("success", False),
            "stress_pod": STRESS_POD,
            "namespace": STRESS_NAMESPACE,
        },
        "node_state": node_state.get("node") if node_state.get("success") else node_state,
    }


@router.get("/node-failure/health")
def node_health():
    """Check the health status of the worker node."""
    ctx = "kind-opensre-demo"
    node = WORKER_NODE

    node_state = kubectl.get_node_state(node, ctx)
    node_usage = kubectl.get_node_resource_usage(node, ctx)

    is_unschedulable = False
    taints = []
    conditions = []

    if node_state.get("success"):
        is_unschedulable = node_state.get("node", {}).get("unschedulable", False)
        taints = node_state.get("node", {}).get("taints", [])
        conditions = node_state.get("node", {}).get("conditions", [])

    # Check for stress pod
    stress_check = run_command(
        _kubectl_cmd(ctx) + [
            "get", "pod", STRESS_POD, "-n", STRESS_NAMESPACE, "--ignore-not-found"
        ]
    )
    stress_pod_running = STRESS_POD in stress_check.get("stdout", "")

    healthy = not is_unschedulable and not any(
        t.get("key") == "demo-unhealthy" for t in taints
    )

    return {
        "success": True,
        "node": node,
        "healthy": healthy,
        "unschedulable": is_unschedulable,
        "taints": taints,
        "conditions": conditions,
        "stress_pod_running": stress_pod_running,
        "pod_count": node_usage.get("pod_count"),
        "restarts_total": node_usage.get("restarts_total"),
    }


# ==================================================================
# UNHEALTHY POD DEMO
# ==================================================================

UNHEALTHY_POD_YAML = """\
apiVersion: v1
kind: Pod
metadata:
  name: order-service-bad
  namespace: opensre
  labels:
    app: order-service
    version: bad
spec:
  containers:
  - name: order-service
    image: busybox:1.36
    command:
    - sh
    - -c
    - |
      echo "[order-service] Starting v2.3.1 ..."
      echo "[order-service] ERROR: Failed to connect to database at yugabyte:5433"
      echo "[order-service] ERROR: connection refused (host=127.0.0.1 port=5433)"
      echo "[order-service] WARN: Retry 1/3 ..."
      sleep 1
      echo "[order-service] WARN: Retry 2/3 ..."
      sleep 1
      echo "[order-service] WARN: Retry 3/3 ..."
      sleep 1
      echo "[order-service] FATAL: Could not initialize database connection after 3 retries"
      echo "[order-service] FATAL: Exiting with code 1"
      exit 1
    resources:
      requests:
        cpu: "100m"
        memory: "64Mi"
      limits:
        cpu: "200m"
        memory: "128Mi"
  restartPolicy: Always
"""


@router.post("/unhealthy-pod/deploy")
def deploy_unhealthy_pod():
    ctx = "kind-opensre-demo"

    # Check if already exists
    check = run_command(
        _kubectl_cmd(ctx) + [
            "get", "pod", "order-service-bad", "-n", "opensre", "--ignore-not-found"
        ]
    )
    stdout = check.get("stdout", "").strip()
    if "order-service-bad" in stdout:
        return {
            "success": True,
            "status": "already_exists",
            "pod": "order-service-bad",
            "namespace": "opensre",
        }

    # Deploy
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    try:
        tmp.write(UNHEALTHY_POD_YAML)
        tmp.close()
        result = run_command(_kubectl_cmd(ctx) + ["apply", "-f", tmp.name])
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

    return {
        "success": result.get("success", False),
        "status": "deployed",
        "pod": "order-service-bad",
        "namespace": "opensre",
    }


@router.post("/unhealthy-pod/delete")
def delete_unhealthy_pod():
    ctx = "kind-opensre-demo"
    result = run_command(
        _kubectl_cmd(ctx) + [
            "delete", "pod", "order-service-bad", "-n", "opensre", "--ignore-not-found"
        ]
    )
    return {
        "success": result.get("success", False),
        "pod": "order-service-bad",
        "namespace": "opensre",
    }


@router.get("/unhealthy-pod/status")
def unhealthy_pod_status():
    ctx = "kind-opensre-demo"
    result = run_command(
        _kubectl_cmd(ctx) + [
            "get", "pod", "order-service-bad", "-n", "opensre",
            "-o", "json"
        ]
    )

    if not result.get("success"):
        return {"exists": False}

    try:
        pod = json.loads(result.get("stdout", "{}"))
    except (TypeError, ValueError):
        return {"exists": False}

    status = pod.get("status", {})
    phase = status.get("phase", "Unknown")
    container_status = status.get("containerStatuses", [{}])[0] if status.get("containerStatuses") else {}
    restart_count = container_status.get("restartCount", 0)
    last_reason = None
    if container_status.get("lastState", {}).get("terminated"):
        last_reason = container_status["lastState"]["terminated"].get("reason")

    return {
        "exists": True,
        "phase": phase,
        "restarts": restart_count,
        "last_reason": last_reason,
        "node": pod.get("spec", {}).get("nodeName"),
    }


# ==================================================================
# DATABASE INVESTIGATION DEMO WORKFLOWS
# ==================================================================

class DBScenarioRequest(BaseModel):
    target: str  # "yugabyte" or "aerospike"


# ------------------------------------------------------------------
# SCENARIO 1: Database Unavailable / Connection Refused
# ------------------------------------------------------------------
@router.post("/db-scenario/unavailable/fail")
def db_unavailable_fail(request: DBScenarioRequest):
    """Step 1: Stop the database container to simulate unavailability."""
    target = request.target.lower()
    container = _target_to_container(target)

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    # Seed data first
    seed = _seed_yugabyte() if target == "yugabyte" else _seed_aerospike()
    # Stop container
    stop = _stop_container(container)

    return {
        "success": stop.get("success", False),
        "scenario": "database-unavailable",
        "target": target,
        "container": container,
        "seed": seed,
        "fault": {
            "action": f"{target}-down",
            "injected": stop.get("success", False),
            "container_stopped": container,
            "description": f"{target.capitalize()} container stopped - simulating connection refused/unavailable"
        },
    }


@router.post("/db-scenario/unavailable/investigate")
def db_unavailable_investigate(request: DBScenarioRequest):
    """Step 2: Collect evidence and run OpenSRE investigation while DB is down."""
    target = request.target.lower()

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    evidence_result = investigation.collect_database_evidence(target)

    if not evidence_result.get("success"):
        return {
            "success": False,
            "error": evidence_result.get("error", "Evidence collection failed"),
        }

    evidence = evidence_result["evidence"]
    evidence["question"] = (
        f"The {target.capitalize()} database appears to be unavailable. "
        f"Applications are reporting connection refused errors. "
        f"Investigate the database state and determine the root cause. "
        f"Provide: root cause, confidence, evidence, timeline, affected component, "
        f"and recommended remediation."
    )

    opensre_result = opensre_cli.investigate(evidence)

    return {
        "success": opensre_result.get("returncode") == 0,
        "scenario": "database-unavailable",
        "target": target,
        "evidence": evidence,
        "opensre": opensre_result,
    }


@router.post("/db-scenario/unavailable/recover")
def db_unavailable_recover(request: DBScenarioRequest):
    """Step 3: Restart the database container to recover."""
    target = request.target.lower()
    container = _target_to_container(target)

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    start = _start_container(container)
    # Wait a bit for DB to be ready
    import time
    time.sleep(3)
    health = investigation.collect_database_evidence(target)

    return {
        "success": start.get("success", False),
        "scenario": "database-unavailable",
        "target": target,
        "container": container,
        "recovery": {
            "action": f"{target}-up",
            "success": start.get("success", False),
            "container_restarted": container,
        },
        "health": health.get("evidence", {}),
    }


# ------------------------------------------------------------------
# SCENARIO 2: Database/Query Latency Problem
# ------------------------------------------------------------------
@router.post("/db-scenario/latency/induce")
def db_latency_induce(request: DBScenarioRequest):
    """Step 1: Induce latency by running heavy queries/operations."""
    target = request.target.lower()

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    if target == "yugabyte":
        # Create a large table and run heavy queries to induce latency
        yugabyte.execute("""
            CREATE TABLE IF NOT EXISTS latency_test (
                id BIGSERIAL PRIMARY KEY,
                data TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        # Insert many rows
        for i in range(100):
            yugabyte.execute(
                "INSERT INTO latency_test (data) VALUES (%s)",
                (f"test-data-{'x' * 1000}",)
            )
        # Run a slow query (no index on data column)
        result = yugabyte.query("""
            SELECT * FROM latency_test 
            WHERE data LIKE '%test%' 
            ORDER BY created_at DESC 
            LIMIT 100
        """)
        return {
            "success": True,
            "scenario": "database-latency",
            "target": target,
            "action": "induced-latency",
            "details": "Created large table with unindexed column, ran heavy queries",
            "query_result": result,
        }
    else:
        # Aerospike: write many large records
        for i in range(200):
            aerospike.write("test", "latency", f"key-{i}", {
                "data": "x" * 5000,
                "index": i,
                "timestamp": time.time(),
            })
        # Scan to induce load
        result = aerospike.scan("test", "latency")
        return {
            "success": True,
            "scenario": "database-latency",
            "target": target,
            "action": "induced-latency",
            "details": "Wrote 200 large records (5KB each), scanned set",
            "scan_result": result,
        }


@router.post("/db-scenario/latency/investigate")
def db_latency_investigate(request: DBScenarioRequest):
    """Step 2: Collect evidence and run OpenSRE investigation for latency."""
    target = request.target.lower()

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    evidence_result = investigation.collect_database_evidence(target)

    if not evidence_result.get("success"):
        return {
            "success": False,
            "error": evidence_result.get("error", "Evidence collection failed"),
        }

    evidence = evidence_result["evidence"]
    evidence["question"] = (
        f"The {target.capitalize()} database is experiencing high query latency. "
        f"Applications are timing out or responding slowly. "
        f"Investigate the database for slow queries, resource contention, "
        f"lock waits, or other latency causes. "
        f"Provide: root cause, confidence, evidence, timeline, affected component, "
        f"and recommended remediation."
    )

    opensre_result = opensre_cli.investigate(evidence)

    return {
        "success": opensre_result.get("returncode") == 0,
        "scenario": "database-latency",
        "target": target,
        "evidence": evidence,
        "opensre": opensre_result,
    }


@router.post("/db-scenario/latency/recover")
def db_latency_recover(request: DBScenarioRequest):
    """Step 3: Clean up latency-inducing data."""
    target = request.target.lower()

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    if target == "yugabyte":
        yugabyte.execute("DROP TABLE IF EXISTS latency_test")
    else:
        # Delete latency test records
        for i in range(200):
            aerospike.delete("test", "latency", f"key-{i}")

    health = investigation.collect_database_evidence(target)

    return {
        "success": True,
        "scenario": "database-latency",
        "target": target,
        "recovery": {
            "action": "cleanup-latency-data",
            "success": True,
        },
        "health": health.get("evidence", {}),
    }


# ------------------------------------------------------------------
# SCENARIO 3: Data Quality / Data Integrity Problem
# ------------------------------------------------------------------
@router.post("/db-scenario/data-integrity/corrupt")
def db_data_integrity_corrupt(request: DBScenarioRequest):
    """Step 1: Introduce data integrity issues (duplicates, NULLs, invalid values)."""
    target = request.target.lower()

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    if target == "yugabyte":
        # Create test table and insert problematic data
        yugabyte.execute_raw("""
            CREATE TABLE IF NOT EXISTS integrity_test (
                id INT PRIMARY KEY,
                name TEXT,
                email TEXT UNIQUE,
                status TEXT DEFAULT 'active',
                count INT CHECK (count >= 0)
            )
        """)
        # Insert good data
        yugabyte.execute_raw("INSERT INTO integrity_test (id, name, email, status, count) VALUES (1, 'Good User', 'good@test.com', 'active', 10)")
        # Insert duplicate email (violates UNIQUE)
        yugabyte.execute_raw("INSERT INTO integrity_test (id, name, email, status, count) VALUES (2, 'Dup User', 'good@test.com', 'active', 5)")
        # Insert NULL name
        yugabyte.execute_raw("INSERT INTO integrity_test (id, name, email, status, count) VALUES (3, NULL, 'null@test.com', 'active', 3)")
        # Insert empty string name
        yugabyte.execute_raw("INSERT INTO integrity_test (id, name, email, status, count) VALUES (4, '', 'empty@test.com', 'active', 4)")
        # Insert negative count (violates CHECK)
        yugabyte.execute_raw("INSERT INTO integrity_test (id, name, email, status, count) VALUES (5, 'Bad Count', 'bad@test.com', 'active', -5)")
        # Insert duplicate primary key
        yugabyte.execute_raw("INSERT INTO integrity_test (id, name, email, status, count) VALUES (1, 'Dup PK', 'dup@test.com', 'inactive', 1)")
    else:
        # Aerospike: write records with missing required fields, duplicates
        aerospike.write("test", "integrity", "good-1", {"name": "Good User", "status": "active", "_key": "good-1"})
        aerospike.write("test", "integrity", "dup-key", {"name": "Dup User", "status": "active", "_key": "dup-key"})
        aerospike.write("test", "integrity", "dup-key", {"name": "Another Dup", "status": "inactive", "_key": "dup-key"})  # Overwrite
        aerospike.write("test", "integrity", "missing-name", {"status": "active", "_key": "missing-name"})  # Missing required 'name'
        aerospike.write("test", "integrity", "invalid-count", {"name": "Bad Count", "status": "active", "count": -10, "_key": "invalid-count"})

    return {
        "success": True,
        "scenario": "data-integrity",
        "target": target,
        "action": "corrupted-data",
        "details": "Introduced: duplicate keys, NULL required fields, constraint violations, invalid values",
    }


# ------------------------------------------------------------------
# NEW: Data injection endpoints for testing
# ------------------------------------------------------------------
@router.post("/db-scenario/data-integrity/insert-empty")
def db_data_integrity_insert_empty(request: DBScenarioRequest):
    """Insert empty/missing required field data for testing."""
    target = request.target.lower()

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    if target == "yugabyte":
        yugabyte.execute_raw("""
            CREATE TABLE IF NOT EXISTS integrity_test (
                id INT PRIMARY KEY,
                name TEXT,
                email TEXT UNIQUE,
                status TEXT DEFAULT 'active',
                count INT CHECK (count >= 0)
            )
        """)
        for i in range(10, 15):
            yugabyte.execute_raw(
                "INSERT INTO integrity_test (id, name, email, status, count) VALUES (%s, NULL, %s, 'active', %s)",
                (i, f"empty-name-{i}@test.com", i)
            )
        for i in range(20, 25):
            yugabyte.execute_raw(
                "INSERT INTO integrity_test (id, name, email, status, count) VALUES (%s, '', %s, 'active', %s)",
                (i, f"empty-string-{i}@test.com", i)
            )
    else:
        for i in range(100, 105):
            aerospike.write("test", "integrity", f"empty-name-{i}", {
                "status": "active", "count": i, "_key": f"empty-name-{i}"
            })
        for i in range(110, 115):
            aerospike.write("test", "integrity", f"empty-string-{i}", {
                "name": "", "status": "active", "count": i, "_key": f"empty-string-{i}"
            })
        for i in range(120, 125):
            aerospike.write("test", "integrity", f"missing-status-{i}", {
                "name": f"User {i}", "count": i, "_key": f"missing-status-{i}"
            })

    return {
        "success": True,
        "scenario": "data-integrity",
        "target": target,
        "action": "insert-empty-fields",
        "details": "Inserted records with NULL/empty required fields (name, status)",
    }


@router.post("/db-scenario/data-integrity/insert-duplicates")
def db_data_integrity_insert_duplicates(request: DBScenarioRequest):
    """Insert duplicate data for testing."""
    target = request.target.lower()

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    if target == "yugabyte":
        yugabyte.execute_raw("""
            CREATE TABLE IF NOT EXISTS integrity_test (
                id INT PRIMARY KEY,
                name TEXT,
                email TEXT UNIQUE,
                status TEXT DEFAULT 'active',
                count INT CHECK (count >= 0)
            )
        """)
        for i in range(30, 35):
            yugabyte.execute_raw(
                "INSERT INTO integrity_test (id, name, email, status, count) VALUES (%s, %s, 'duplicate@test.com', 'active', %s)",
                (i, f"Dup User {i}", i)
            )
        for i in range(40, 45):
            yugabyte.execute_raw(
                "INSERT INTO integrity_test (id, name, email, status, count) VALUES (1, %s, %s, 'active', %s)",
                (f"Dup PK {i}", f"dup-pk-{i}@test.com", i)
            )
    else:
        for i in range(200, 205):
            aerospike.write("test", "integrity", f"dup-email-{i}", {
                "name": f"Dup User {i}", "email": "duplicate@test.com",
                "status": "active", "count": i, "_key": f"dup-email-{i}"
            })
        for i in range(210, 215):
            aerospike.write("test", "integrity", "dup-key", {
                "name": f"Overwrite {i}", "status": "active",
                "count": i, "_key": "dup-key"
            })

    return {
        "success": True,
        "scenario": "data-integrity",
        "target": target,
        "action": "insert-duplicates",
        "details": "Inserted duplicate emails, duplicate primary keys, and key overwrites",
    }


@router.post("/db-scenario/data-integrity/insert-invalid")
def db_data_integrity_insert_invalid(request: DBScenarioRequest):
    """Insert invalid data (negative values, wrong types) for testing."""
    target = request.target.lower()

    if target not in ("yugabyte", "aerospike"):
        raise HTTPException(status_code=400, detail=f"Unknown target '{target}'")

    if target == "yugabyte":
        yugabyte.execute_raw("""
            CREATE TABLE IF NOT EXISTS integrity_test (
                id INT PRIMARY KEY,
                name TEXT,
                email TEXT UNIQUE,
                status TEXT DEFAULT 'active',
                count INT CHECK (count >= 0)
            )
        """)
        for i in range(50, 55):
            yugabyte.execute_raw(
                "INSERT INTO integrity_test (id, name, email, status, count) VALUES (%s, %s, %s, 'active', %s)",
                (i, f"Bad Count {i}", f"bad-{i}@test.com", -i)
            )
        for i in range(60, 65):
            yugabyte.execute_raw(
                "INSERT INTO integrity_test (id, name, email, status, count) VALUES (%s, %s, %s, 'active', %s)",
                (i, f"Bad Email {i}", f"not-an-email-{i}", i)
            )
    else:
        for i in range(300, 305):
            aerospike.write("test", "integrity", f"invalid-count-{i}", {
                "name": f"Bad Count {i}", "status": "active",
                "count": -i, "_key": f"invalid-count-{i}"
            })
        for i in range(310, 315):
            aerospike.write("test", "integrity", f"invalid-email-{i}", {
                "name": f"Bad Email {i}", "email": f"not-an-email-{i}",
                "status": "active", "count": i, "_key": f"invalid-email-{i}"
            })

    return {
        "success": True,
        "scenario": "data-integrity",
        "target": target,
        "action": "insert-invalid-values",
        "details": "Inserted negative counts, invalid emails, and other invalid values",
    }


# ------------------------------------------------------------------
# Combined scenario: Run all three scenarios for a target
# ------------------------------------------------------------------
@router.get("/db-scenario/list")
def list_db_scenarios():
    """List available database investigation demo scenarios."""
    return {
        "scenarios": [
            {
                "id": "unavailable",
                "name": "Database Unavailable / Connection Refused",
                "description": "Simulate database container stop, investigate connection failures, then recover",
                "steps": ["fail", "investigate", "recover"],
                "targets": ["yugabyte", "aerospike"],
            },
            {
                "id": "latency",
                "name": "Database/Query Latency Problem",
                "description": "Induce high latency via heavy queries, investigate slow queries, then clean up",
                "steps": ["induce", "investigate", "recover"],
                "targets": ["yugabyte", "aerospike"],
            },
            {
                "id": "data-integrity",
                "name": "Data Quality / Data Integrity Problem",
                "description": "Introduce duplicates, NULLs, constraint violations, investigate, then clean up",
                "steps": ["corrupt", "investigate", "recover"],
                "targets": ["yugabyte", "aerospike"],
            },
        ]
    }
