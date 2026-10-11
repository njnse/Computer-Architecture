"""Retain command evidence compactly and generate a content manifest."""
import base64
import gzip
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent
for path in (root/'results').glob('*.log'):
    path.with_suffix('.log.gz.b64').write_text(base64.b64encode(gzip.compress(path.read_bytes(),mtime=0)).decode()+'\n')
    path.unlink()
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
          for p in root.rglob('*') if p.is_file() and p.name!='MANIFEST.json' and
          not any(s in ['build','__pycache__','venv','iverilog'] for s in p.relative_to(root).parts) and p.suffix!='.deb'}
(root/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Manifest files',len(manifest))
