"""Compress redundant raw logs without changing executed measurements."""
import base64,gzip
from pathlib import Path
r=Path(__file__).resolve().parent/'results'
for name in ['execution_trace.log','simulation_incremental.jsonl']:
 p=r/name
 if p.exists():
  (r/(name+'.gz.b64')).write_text(base64.b64encode(gzip.compress(p.read_bytes(),mtime=0)).decode()+'\n')
  p.unlink()

# Remove nondeterministic wall-clock metadata while retaining all signal events.
import re
p=r/'protocol.vcd'
if p.exists():p.write_text(re.sub(r'\$date.*?\$end\n','',p.read_text(),flags=re.S))
