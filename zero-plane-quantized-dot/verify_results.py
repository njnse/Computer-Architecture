"""Audit emitted measurements and retained netlists; refresh source traceability."""
import base64,csv,gzip,hashlib,json,re
from pathlib import Path
root=Path(__file__).resolve().parent;r=root/'results'
rows=json.loads((r/'simulation.json').read_text());resources=json.loads((r/'resources.json').read_text());formal=json.loads((r/'formal.json').read_text())
assert len(rows)==768,len(rows)
assert len(resources)==30
assert len(formal)==6 and all(x['passed'] for x in formal)
assert all(x['emitted']+x['canceled']==x['count'] for x in rows)
assert all(x['latches']==0 for x in resources)
assert all(x['detected'] for x in json.loads((r/'mutations.json').read_text()))
netlists=json.loads(gzip.decompress(base64.b64decode((r/'netlists.json.gz.b64').read_text())))
for record in resources:
 key=f"w{record['width']}_n4_m{record['mode']}_{record['flow']}"
 assert hashlib.sha256(json.dumps(netlists[key],sort_keys=True,separators=(',',':')).encode()).hexdigest()==record['retained_design_sha256']
 types={}
 for cell in netlists[key]['modules']['dot_engine']['cells'].values():types[cell['type']]=types.get(cell['type'],0)+1
 assert types==record['types']
 if record['flow']!='generic':assert record['lut']==sum(v for k,v in types.items() if re.fullmatch(r'LUT[1-6]',k))
application=json.loads((r/'application.json').read_text());assert len(application)==24
for rec in application:assert rec['prediction_changes']==0 and rec['block_outputs']==57600
raw=list(csv.DictReader((r/'application_blocks.csv').open()));assert len(raw)==57600
assert sum(int(x['latency']) for x in raw)==next(x['total_latency'] for x in rows if x['run']=='app_8_dense_3')
log=gzip.decompress(base64.b64decode((r/'synthesis.log.gz.b64').read_text())).decode()
assert len(json.loads((r/'netlist_readback.json').read_text()))==30
assert all(x['returncode']==0 for x in json.loads((r/'commands.json').read_text()) if 'mutation_' not in ' '.join(x['argv']))
sources={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and not any(v in p.relative_to(root).parts for v in ['build','results','__pycache__','venv','iverilog']) and p.suffix!='.deb'}
(r/'source_hashes.json').write_text(json.dumps(sources,indent=2)+'\n')
(r/'validation.json').write_text(json.dumps({'passed':True,'rtl_runs':len(rows),'retained_netlists':len(netlists),'independent_netlist_readbacks':30,'synthesis_stdout':'partial at ABC/ABC9; retained without claiming complete logs','formal_checks':6,'python_tests':8,'raw_application_blocks':len(raw),'note':'Bounded formal and finite tests; no unbounded full-parameter proof or physical timing.'},indent=2)+'\n')
print('Artifact audit passed')
