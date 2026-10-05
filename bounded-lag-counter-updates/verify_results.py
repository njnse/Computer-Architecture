"""Validate every retained measurement and generated result artifact."""
import csv
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

p=Path(__file__).resolve().parent
rows=list(csv.DictReader((p/"results/raw.csv").open()))
meta=json.loads((p/"results/summary.json").read_text())
assert len(rows)==270==meta["evaluation_runs"]
assert len({tuple(r[k] for k in ["repeat","threads","work","policy"]) for r in rows})==270
assert hashlib.sha256((p/"bench.c").read_bytes()).hexdigest()==meta["source_sha256"]
for r in rows:
    threads=int(r["threads"]);n=int(r["iterations"]);batch=int(r["batch"])
    assert int(r["total"])==int(r["updates"])==threads*n
    assert int(r["flushes"])==threads*((n+batch-1)//batch)
    assert abs(float(r["ns_per_update"])-float(r["seconds"])*1e9/(threads*n))<1e-8
    assert float(r["worker_cpu_seconds"])>=0
    assert r["packed_alignment_mod64"]==r["padded_alignment_mod64"]=="0"
    assert math.isfinite(float(r["seconds"])) and float(r["seconds"])>0
for threads in ["1","2"]:
    for work in ["0","32","256"]:
        assert len({r["checksum"] for r in rows if r["threads"]==threads and r["work"]==work})==1
convergence=list(csv.DictReader((p/"results/convergence.csv").open()))
assert len(convergence)==45
for r in convergence:
    assert int(r["total"])==2*int(r["iterations"])
assert len(json.loads((p/"results/validation.json").read_text())["checks"])==15
ET.parse(p/"results/comparison.svg")
print("Validated 270 evaluation rows, 45 duration checks, 15 correctness cases, source hash, counts, checksums, layouts, timing arithmetic, and SVG.")
