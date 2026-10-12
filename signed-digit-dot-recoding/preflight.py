"""Check actual installed pins and snapshot the executable measurement sources."""
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parent
r=root/'results'
r.mkdir(exist_ok=True)
observed={}
for line in (root/'requirements.txt').read_text().splitlines():
    package,pinned=line.split('==')
    observed[package]=importlib.metadata.version(package)
    assert observed[package]==pinned,(package,observed[package],pinned)
(r/'python_pin_check.json').write_text(json.dumps(dict(passed=True,observed=observed),indent=2)+'\n')
y=Path(os.environ.get('YOSYS',str(root/'tools/venv/bin/yowasp-yosys')))
toolpython=os.environ.get('YOSYS_PYTHON',str(y.parent/'python'))
program="import importlib.metadata,json; print(json.dumps({s.split('==')[0]:importlib.metadata.version(s.split('==')[0]) for s in open('tools/requirements.txt').read().splitlines()}))"
p=subprocess.run([toolpython,'-c',program],cwd=root,text=True,capture_output=True,check=True)
versions=json.loads(p.stdout)
for line in (root/'tools/requirements.txt').read_text().splitlines():
    package,pinned=line.split('==');assert versions[package]==pinned,(package,versions[package],pinned)
iv=Path(os.environ.get('IVERILOG',str(root/'tools/iverilog/usr/bin/iverilog')))
package=Path(os.environ.get('IVERILOG_PACKAGE',str(iv.parents[3]/'iverilog_12.0-2+b1_amd64.deb')))
digest=hashlib.sha256(package.read_bytes()).hexdigest()
assert digest=='febe027d2d3f5a7e570844d55758339ab5490acc09f404f214a8719d89d07056'
(r/'tool_pin_check.json').write_text(json.dumps(dict(passed=True,observed=versions,icarus_package_sha256=digest),indent=2)+'\n')
files=['rtl/dot_engine.sv','rtl/counter_engine.sv','rtl/booth_engine.sv','tb/check.sv','reference.py','reproduce.py','train_models.py','formal/numeric.sv','fixtures/provenance.json','SPEC.md','analyze.py','verify_results.py','preflight.py','run_project.py','write_report.py','requirements.txt','tools/requirements.txt','tools/setup.py']
(r/'measurement_sources.json').write_text(json.dumps({f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in files},indent=2)+'\n')
print('Actual Python/tool package pins and executable source snapshot verified')
