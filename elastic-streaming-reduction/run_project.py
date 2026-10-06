"""One-command bootstrap, executed experiment, and artifact validation."""
import os,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent
configured=all(os.environ.get(k) for k in ["IVERILOG","VVP","YOSYS"])
local=all((root/p).exists() for p in ["tools/iverilog/usr/bin/iverilog","tools/venv/bin/yowasp-yosys"])
if not configured and not local:
    subprocess.run([sys.executable,str(root/"tools/setup.py")],check=True,cwd=root)
subprocess.run([sys.executable,str(root/"reproduce.py")],check=True,cwd=root)
subprocess.run([sys.executable,str(root/"verify_results.py")],check=True,cwd=root)
