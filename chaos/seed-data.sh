#!/usr/bin/env bash
#
# Seed sample data into YugabyteDB and Aerospike so the demo dashboard pages
# show live, browsable data.
#
# Uses the OpenSRE backend virtualenv for the database drivers.
#
#   ./chaos/seed-data.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${ROOT}/opensre-backend/.venv/bin/python"

if [[ ! -x "${PY}" ]]; then
  echo "Backend virtualenv not found at ${PY}" >&2
  exit 1
fi

"${PY}" - <<'PY'
import aerospike
import psycopg2
from psycopg2.extras import RealDictCursor

# ---------------------------------------------------------------------------
# YugabyteDB  (table: test_table  cols: id INT, name TEXT)
# ---------------------------------------------------------------------------
print("== YugabyteDB ==")
yb = psycopg2.connect(
    host="127.0.0.1", port=5433,
    database="yugabyte", user="yugabyte", password="yugabyte",
)
cur = yb.cursor(cursor_factory=RealDictCursor)
cur.execute('''
    CREATE TABLE IF NOT EXISTS test_table (
        id   INT PRIMARY KEY,
        name TEXT
    );
''')
cur.execute("TRUNCATE test_table;")
names = [
    "Aviator Headphones", "Quantum Mouse", "Nebula Keyboard", "Titan Speakers",
    "Echo Smartwatch", "Vertex SSD", "Pulse GPU", "Orion Monitor",
    "Fable E-Reader", "Zen Router", "Cinder Webcam", "Drift Drone",
    "Solar Power Bank", "Apex Headset", "Nova Tablet", "Ark Mechanical Keys",
    "Cloud Laptop Stand", "Prism USB Hub", "Halo Projector", "Summit Dock",
]
rows = [(i + 1, name) for i, name in enumerate(names)]
cur.executemany("INSERT INTO test_table (id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING;", rows)
yb.commit()

cur.execute("SELECT count(*) AS n FROM test_table;")
print(f"  inserted {cur.fetchone()['n']} rows into test_table")
cur.close()
yb.close()

# ---------------------------------------------------------------------------
# Aerospike  (namespace: test, set: demo  bins: name, value)
# ---------------------------------------------------------------------------
print("== Aerospike ==")
client = aerospike.client({"hosts": [("127.0.0.1", 3001)]}).connect()

# clear any existing records in the set
seen = {}
try:
    scan = client.scan("test", "demo")
    scan.foreach(lambda r: seen.update({r[0][2]: None}))
except Exception:
    pass
for key in seen:
    try:
        client.remove(("test", "demo", key))
    except Exception:
        pass

catalog = [
    ("headphones", "Aviator Headphones", 249),
    ("mouse", "Quantum Mouse", 59),
    ("keyboard", "Nebula Keyboard", 129),
    ("speakers", "Titan Speakers", 399),
    ("watch", "Echo Smartwatch", 199),
    ("ssd", "Vertex SSD", 89),
    ("monitor", "Orion Monitor", 349),
    ("router", "Zen Router", 79),
    ("drone", "Drift Drone", 599),
    ("powerbank", "Solar Power Bank", 45),
    ("tablet", "Nova Tablet", 279),
    ("hub", "Prism USB Hub", 39),
    ("projector", "Halo Projector", 449),
]
for key, name, value in catalog:
    client.put(("test", "demo", key), {"name": name, "value": value, "_key": key})

# count records
recs = []
scan = client.scan("test", "demo")
scan.foreach(lambda r: recs.append(r[0][2]))
print(f"  wrote {len(recs)} records into test:demo")
client.close()

print("\nSeeding complete. Refresh the Aerospike & YugabyteDB pages.")
PY
