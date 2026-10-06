"""Generate cycle/resource comparisons and a standalone mapped-resource figure."""
import csv,json
from pathlib import Path
root=Path(__file__).resolve().parent
out=root/"results"
resources=json.loads((out/"resources.json").read_text())
simulation=list(csv.DictReader((out/"simulation.csv").open()))
rows=[]
for r in resources:
    cells=r["ice40"]["num_cells_by_type"]
    measurements=[x for x in simulation if x["flow"]=="rtl" and int(x["width"])==r["width"] and int(x["pipe"])==r["pipe"] and x["scenario"]=="0"]
    assert len(measurements)==3
    rows.append(dict(width=r["width"],pipe=r["pipe"],lut4=cells.get("SB_LUT4",0),
        flip_flops=sum(n for cell,n in cells.items() if cell.startswith("SB_DFF")),
        carry=cells.get("SB_CARRY",0),clean_latency_cycles=int(measurements[0]["latency_min"]),
        clean_initiation_interval=int(measurements[0]["max_output_gap"])))
with (out/"comparison.csv").open("w",newline="") as h:
    w=csv.DictWriter(h,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
lines=["# Measured Cycle and Mapped Resource Comparison","",
       "| Width | Stages | Clean latency | Initiation interval | LUT4 | Flip-flops | Carry |",
       "| --- | --- | --- | --- | --- | --- | --- |"]
for r in rows:lines.append("| "+" | ".join(str(r[k]) for k in ["width","pipe","clean_latency_cycles","clean_initiation_interval","lut4","flip_flops","carry"])+" |")
(out/"MEASUREMENTS.md").write_text("\n".join(lines)+"\n")
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="1050" height="440" viewBox="0 0 1050 440">',
     '<rect width="1050" height="440" fill="white"/>',
     '<text x="25" y="30" font-family="sans-serif" font-size="20">Elastic sum: mapped resource tradeoff</text>',
     '<text x="25" y="55" font-family="sans-serif" font-size="13">iCE40 synthesis counts; both variants have initiation interval one; no physical frequency claim</text>']
colors={1:"#267daa",2:"#dc8c32"}
for panel,(key,title) in enumerate([("lut4","LUT4 primitives"),("flip_flops","Flip-flop primitives")]):
    left=65+panel*515
    maxval=max(r[key] for r in rows)*1.15
    svg.append(f'<text x="{left}" y="88" font-family="sans-serif" font-size="16">{title}</text>')
    for i,width in enumerate([1,8,16,32]):
        x=left+i*110
        for pipe in [1,2]:
            val=next(r[key] for r in rows if r["width"]==width and r["pipe"]==pipe)
            height=val/maxval*230;bx=x+(pipe-1)*43
            svg.append(f'<rect x="{bx}" y="{350-height:.2f}" width="33" height="{height:.2f}" fill="{colors[pipe]}"/>')
            svg.append(f'<text x="{bx}" y="{342-height:.2f}" font-family="sans-serif" font-size="12">{val}</text>')
        svg.append(f'<text x="{x}" y="375" font-family="sans-serif" font-size="13">W={width}</text>')
for pipe in [1,2]:
    x=180+(pipe-1)*420
    svg.append(f'<rect x="{x}" y="404" width="15" height="15" fill="{colors[pipe]}"/>')
    svg.append(f'<text x="{x+25}" y="417" font-family="sans-serif" font-size="14">{pipe}-stage pipeline</text>')
svg.append("</svg>")
(out/"comparison.svg").write_text("\n".join(svg)+"\n")
print("Generated eight matched cycle/resource comparisons and SVG.")
