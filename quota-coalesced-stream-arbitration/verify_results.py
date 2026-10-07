"""Validate checked-in evidence, paired flows, hashes, bounds, and coverage obligations."""
import base64,csv,gzip,hashlib,json
from pathlib import Path
from reference import self_test
ROOT=Path(__file__).resolve().parent
OUT=ROOT/"results"
rows=list(csv.DictReader((OUT/"simulation.csv").open()))
env=json.loads((OUT/"environment.json").read_text())
assert len(rows)==env["simulation_records"]==897
assert self_test()==env["reference_self_tests"]
keys=["n","width","quota","fixed","scenario","seed","cycles","warmup"]
index={tuple(r[k] for k in keys):r for r in rows if r["flow"]=="rtl"}
for r in rows:
    assert int(r["fires"])==int(r["opportunities"])
    assert sum(json.loads(r["service_counts"]))==int(r["fires"])
    if r["fixed"]=="0":assert int(r["serviced_wait_max"])<=(int(r["n"])-1)*int(r["quota"])
    if r["flow"]=="generic-netlist":
        baseline=index[tuple(r[k] for k in keys)]
        assert {k:v for k,v in r.items() if k!="flow"}=={k:v for k,v in baseline.items() if k!="flow"},"RTL/netlist mismatch"
    if r["scenario"]=="saturated":
        assert float(r["throughput"])==1
        if r["fixed"]=="0":assert int(r["serviced_wait_max"])==(int(r["n"])-1)*int(r["quota"])
for rel,h in env["source_sha256"].items():assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest()==h
coverage=json.loads((OUT/"coverage.json").read_text())
totals={k:sum(r["counts"][k] for r in coverage) for k in coverage[0]["counts"]}
assert all(v>0 for v in totals.values()),totals
for file in ("synthesis.log.gz.b64","formal.log.gz.b64","generic_netlists.json.gz.b64"):
    text=gzip.decompress(base64.b64decode((OUT/file).read_text())).decode()
    assert text
    if file.startswith("formal"):
        assert text.count("SAT proof finished - no model found: SUCCESS!")==3
        assert text.count("SAT solving finished - model found:")==3
resources=json.loads((OUT/"resources.json").read_text())
assert len(resources)==46
assert all(not any("latch" in k.lower() for k in r["num_cells_by_type"]) for r in resources)
assert "Expected failure: data_corruption" in (OUT/"mutation.log").read_text()
assert "Expected failure: missing_stall_lock" in (OUT/"mutation.log").read_text()
per_port=json.loads((OUT/"per_port_validation.json").read_text())
assert per_port["passed"] and per_port["matched_vector_replays"]==140
assert per_port["source_sha256"]==hashlib.sha256((ROOT/"per_port_analysis.py").read_bytes()).hexdigest()
(OUT/"validation.json").write_text(json.dumps(dict(
    passed=True,rtl_runs=sum(r["flow"]=="rtl" for r in rows),generic_netlist_runs=sum(r["flow"]=="generic-netlist" for r in rows),
    observed_cycles=sum(int(r["cycles"]) for r in rows),observed_transfers=sum(int(r["total_fires"]) for r in rows),
    synthesis_runs=len(resources),bounded_proofs=3,mutation_detections=2,functional_coverage=totals,
    checks=["cycle-exact independent reference","source and sink hold rules","one-hot conservation", "work conservation", "RTL/netlist equality", "resource latch check", "source hashes", "saturated closed form", "bounded safety/fairness", "mutation sensitivity"]),indent=2)+"\n")
print((OUT/"validation.json").read_text())
