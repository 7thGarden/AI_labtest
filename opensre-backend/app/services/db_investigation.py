"""Database Investigation Service.

Orchestrates read-only database investigations for YugabyteDB and Aerospike,
providing structured evidence for OpenSRE root-cause analysis.
"""

from app.services import aerospike
from app.services import yugabyte
from app.core.config import settings


def investigate_yugabyte():
    """Run comprehensive YugabyteDB investigation."""
    evidence = {
        "database": "yugabyte",
        "endpoint": f"{settings.YUGABYTE_HOST}:{settings.YUGABYTE_PORT}",
        "investigations": {},
    }

    # Health check
    evidence["investigations"]["health"] = yugabyte.health()

    # Cluster health
    evidence["investigations"]["cluster_health"] = yugabyte.cluster_health()

    # Connection status
    evidence["investigations"]["connections"] = yugabyte.connection_status()

    # Slow queries
    evidence["investigations"]["slow_queries"] = yugabyte.slow_queries(limit=20)

    # Recent errors/active queries
    evidence["investigations"]["recent_errors"] = yugabyte.recent_errors(limit=50)

    # Schema information
    evidence["investigations"]["schema"] = yugabyte.schema_info("public")

    # Table statistics
    evidence["investigations"]["table_stats"] = yugabyte.table_statistics("public")

    # Data integrity checks
    evidence["investigations"]["data_integrity"] = yugabyte.data_integrity_checks("public")

    # Replication status (YugabyteDB-specific)
    evidence["investigations"]["replication"] = yugabyte.replication_status()

    return evidence


def investigate_aerospike():
    """Run comprehensive Aerospike investigation."""
    evidence = {
        "database": "aerospike",
        "endpoint": settings.AEROSPIKE_HOSTS,
        "investigations": {},
    }

    # Health check
    evidence["investigations"]["health"] = aerospike.health()

    # Cluster health
    evidence["investigations"]["cluster_health"] = aerospike.cluster_health()

    # Namespace information
    evidence["investigations"]["namespaces"] = aerospike.namespace_info()

    # Operation errors
    evidence["investigations"]["operation_errors"] = aerospike.operation_errors()

    # Latency information
    evidence["investigations"]["latency"] = aerospike.latency_info()

    # Data integrity checks for demo namespace/set
    evidence["investigations"]["data_integrity"] = aerospike.data_integrity_checks(
        namespace="test",
        set_name="demo",
        required_fields=["name", "status"],
        unique_fields=["_key"],
        limit=100
    )

    # Namespace/set stats for demo
    evidence["investigations"]["demo_set_stats"] = aerospike.namespace_set_stats("test", "demo")

    return evidence


def investigate_all_databases():
    """Run investigation on both databases."""
    return {
        "yugabyte": investigate_yugabyte(),
        "aerospike": investigate_aerospike(),
    }


def investigate_yugabyte_targeted(
    include_schema: bool = True,
    include_data_integrity: bool = True,
    include_slow_queries: bool = True,
    include_recent_errors: bool = True,
    include_table_stats: bool = True,
    include_replication: bool = True,
):
    """Run targeted YugabyteDB investigation with configurable checks."""
    evidence = {
        "database": "yugabyte",
        "endpoint": f"{settings.YUGABYTE_HOST}:{settings.YUGABYTE_PORT}",
        "investigations": {},
    }

    evidence["investigations"]["health"] = yugabyte.health()
    evidence["investigations"]["cluster_health"] = yugabyte.cluster_health()
    evidence["investigations"]["connections"] = yugabyte.connection_status()

    if include_slow_queries:
        evidence["investigations"]["slow_queries"] = yugabyte.slow_queries(limit=20)
    if include_recent_errors:
        evidence["investigations"]["recent_errors"] = yugabyte.recent_errors(limit=50)
    if include_schema:
        evidence["investigations"]["schema"] = yugabyte.schema_info("public")
    if include_table_stats:
        evidence["investigations"]["table_stats"] = yugabyte.table_statistics("public")
    if include_data_integrity:
        evidence["investigations"]["data_integrity"] = yugabyte.data_integrity_checks("public")
    if include_replication:
        evidence["investigations"]["replication"] = yugabyte.replication_status()

    return evidence


def investigate_aerospike_targeted(
    include_namespaces: bool = True,
    include_operation_errors: bool = True,
    include_latency: bool = True,
    include_data_integrity: bool = True,
    include_demo_stats: bool = True,
):
    """Run targeted Aerospike investigation with configurable checks."""
    evidence = {
        "database": "aerospike",
        "endpoint": settings.AEROSPIKE_HOSTS,
        "investigations": {},
    }

    evidence["investigations"]["health"] = aerospike.health()
    evidence["investigations"]["cluster_health"] = aerospike.cluster_health()

    if include_namespaces:
        evidence["investigations"]["namespaces"] = aerospike.namespace_info()
    if include_operation_errors:
        evidence["investigations"]["operation_errors"] = aerospike.operation_errors()
    if include_latency:
        evidence["investigations"]["latency"] = aerospike.latency_info()
    if include_data_integrity:
        evidence["investigations"]["data_integrity"] = aerospike.data_integrity_checks(
            namespace="test",
            set_name="demo",
            required_fields=["name", "status"],
            unique_fields=["_key"],
            limit=100
        )
    if include_demo_stats:
        evidence["investigations"]["demo_set_stats"] = aerospike.namespace_set_stats("test", "demo")

    return evidence