"""Validate saved simulation, formal, and resource evidence independently."""
import csv,hashlib,json
import xml.etree.ElementTree as ET
from pathlib import Path
root=Path(__file__).resolve().parent
out=root/"results"
rows=list(csv.DictReader((out/"simulation.csv").open()))
assert len(rows)==96
assert len({tuple(r[k] for k in ["flow","width","pipe","seed","scenario"]) for r in rows})==96
for r in rows:
    assert int(r["accepted"])==512
    assert int(r["accepted"])==int(r["retired"])+int(r["dropped"])
    if r["scenario"]=="0":
        assert r["latency_min"]==r["latency_max"]==r["pipe"]
        assert int(r["max_output_gap"])==1
    if r["scenario"]=="2":assert int(r["reset_pending"])>0 and int(r["dropped"])>0
    if r["flow"]=="generic-netlist":
        reference=next(x for x in rows if x["flow"]=="rtl" and all(x[k]==r[k] for k in ["width","pipe","seed","scenario"]))
        assert all(r[k]==reference[k] for k in r if k!="flow")
resources=json.loads((out/"resources.json").read_text())
assert len(resources)==8
assert len(json.loads((out/"generic_netlists.json").read_text()))==8
for r in resources:
    for f in ["generic","ice40"]:
        assert not any("latch" in cell.lower() for cell in r[f]["num_cells_by_type"])
for pipe in [1,2]:
    text=(out/f"formal_{pipe}.log").read_text()
    assert "SUCCESS!" in text and "FAIL!" not in text and "model found" in text
assert "scoreboard mismatch" in (out/"mutation.log").read_text()
tool=json.loads((out/"toolchain.json").read_text())
for p,sha in tool["source_hashes"].items():assert hashlib.sha256((root/p).read_bytes()).hexdigest()==sha
assert len(list(csv.DictReader((out/"comparison.csv").open())))==8
ET.parse(out/"comparison.svg")
print("Validated 72 RTL and 24 generic-netlist runs, eight resource comparisons, two bounded proofs, mutation detection, and source hashes.")
