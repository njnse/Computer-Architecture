"""Cross-artifact acceptance checks independent of report generation."""
import csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
r=ROOT/'results'
v=json.loads((r/'validation.json').read_text())
with (r/'simulation.csv').open() as f:rows=list(csv.DictReader(f))
assert len(rows)==v['rtl_and_netlist_runs']==150
assert sum(int(x['cycles']) for x in rows)==v['cycles']
for x in rows:assert int(x['accepted'])==int(x['emitted'])+int(x['canceled'])
assert all(int(x['accepted'])==2000 and int(x['latency_max'])==1 and int(x['simultaneous'])==1999 for x in rows if x['label']=='saturation')
resources=json.loads((r/'resources.json').read_text())
assert len(resources)==85
assert len({(x['width'],x['mode'],x['flow']) for x in resources})==85
assert all(sum(x['cell_types'].values())==x['cell_count'] for x in resources)
assert all(x['ff']==sum(count for name,count in x['cell_types'].items() if name.startswith('FD') or 'DFF' in name) for x in resources)
assert sum(x['label']=='mapped_random' and x['netlist']=='True' for x in rows)==10
assert all(x['dsp']==0 for x in resources if x['flow'].startswith('xcup_lut'))
assert all(not any('LATCH' in k.upper() for k in x['cell_types']) for x in resources)
prov=json.loads((r/'workload_provenance.json').read_text())
a,b,c=[set(prov[k]) for k in ['training','validation','test']]
assert not a&b and not a&c and not b&c and len(a|b|c)==1797
assert (len(a),len(b),len(c))==(1077,360,360)
assert v['formal']['proved_configurations']==5 and all(x['detected'] for x in v['mutations'])
replay=json.loads((r/'replay.json').read_text())
assert len(replay)==10 and all(x['group_outputs']==57600 and x['images']==360 and x['rtl_equals_independent_integer_matmul'] for x in replay)
with (r/'classification.csv').open() as f:classification=list(csv.DictReader(f))
assert len(classification)==72
for x in replay:
    policy='index' if x['mode']=='code' else x['mode']
    row=next(a for a in classification if a['seed']=='7' and a['policy']==policy and a['stage']=='recovered' and int(a['width'])==x['width'])
    assert int(row['test_correct'])==x['test_correct']
env=json.loads((r/'environment.json').read_text())
for path,digest in env['source_sha256'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest,path
assert not v['uvm_executed'] and not v['board_executed'] and not v['placed_timing_executed']
result={'cross_artifact_checks':'PASS','checked_simulations':len(rows),'checked_synthesis':len(resources),'checked_classification_rows':len(classification),'checked_replays':len(replay),'source_hashes_verified':len(env['source_sha256'])}
(r/'artifact_checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
