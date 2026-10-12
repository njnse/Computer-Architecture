"""One-command reproduction; install pinned local tools only when necessary."""
import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path

root=Path(__file__).resolve().parent
for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[name]='1'
(root/'build').mkdir(exist_ok=True)
os.environ.setdefault('XDG_CACHE_HOME',str(root/'build/cache'))
os.environ.setdefault('MPLCONFIGDIR',str(root/'build/mpl'))
configured=all(os.environ.get(k) for k in ('IVERILOG','VVP','YOSYS'))
local=all((root/p).exists() for p in ('tools/iverilog/usr/bin/iverilog','tools/venv/bin/yowasp-yosys'))
if not configured and not local:
    subprocess.run([sys.executable,root/'tools/setup.py'],cwd=root,check=True)
python=sys.executable
try:
    matched=all(importlib.metadata.version(s.split('==')[0])==s.split('==')[1]
                for s in (root/'requirements.txt').read_text().splitlines() if s)
except importlib.metadata.PackageNotFoundError:
    matched=False
if not matched:
    venv=root/'build/python-venv'
    if not venv.exists():subprocess.run([sys.executable,'-m','venv',venv],check=True)
    python=str(venv/'bin/python')
    subprocess.run([python,'-m','pip','install','-r',root/'requirements.txt'],check=True)
subprocess.run([python,root/'preflight.py'],cwd=root,check=True)
subprocess.run([python,root/'reproduce.py']+(['synth'] if '--resume-synthesis' in sys.argv else []),cwd=root,check=True)
subprocess.run([python,root/'analyze.py'],cwd=root,check=True)
subprocess.run([python,root/'verify_results.py'],cwd=root,check=True)
subprocess.run([python,root/'write_report.py'],cwd=root,check=True)
subprocess.run([python,root/'pack_evidence.py'],cwd=root,check=True)
