"""Bootstrap pinned tools when needed, reproduce, then independently check artifacts."""
import importlib.metadata,os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent
configured=all(os.environ.get(k) for k in ("IVERILOG","VVP","YOSYS"))
local=all((root/p).exists() for p in ("tools/iverilog/usr/bin/iverilog","tools/venv/bin/yowasp-yosys"))
if not configured and not local:
    subprocess.run([sys.executable,root/"tools/setup.py"],check=True,cwd=root)
python=sys.executable
try:
    matched=all(importlib.metadata.version(line.split("==")[0])==line.split("==")[1]
                for line in (root/"analysis-requirements.txt").read_text().splitlines() if line)
except importlib.metadata.PackageNotFoundError:
    matched=False
if not matched:
    venv=root/"build/analysis-venv"
    if not venv.exists():subprocess.run([sys.executable,"-m","venv",venv],check=True)
    python=str(venv/"bin/python")
    subprocess.run([python,"-m","pip","install","--no-cache-dir","-r",root/"analysis-requirements.txt"],check=True)
subprocess.run([python,root/"reproduce.py"],check=True,cwd=root)
subprocess.run([python,root/"verify_results.py"],check=True,cwd=root)
