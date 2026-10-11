"""Install pinned workspace-local tools on Linux x86-64; needs network access."""
import hashlib,platform,subprocess,sys,urllib.request
from pathlib import Path
HERE=Path(__file__).resolve().parent
if platform.system()!="Linux" or platform.machine() not in ["x86_64","amd64"]:
    raise SystemExit("Pinned Icarus package requires Linux x86-64.")
venv=HERE/"venv"
if not venv.exists():subprocess.run([sys.executable,"-m","venv",str(venv)],check=True)
subprocess.run([str(venv/"bin/pip"),"install","--no-cache-dir","-r",str(HERE/"requirements.txt")],check=True)
name="iverilog_12.0-2+b1_amd64.deb"
package=HERE/name
url="https://deb.debian.org/debian/pool/main/i/iverilog/"+name
if not package.exists():package.write_bytes(urllib.request.urlopen(url,timeout=60).read())
assert hashlib.sha256(package.read_bytes()).hexdigest()=="febe027d2d3f5a7e570844d55758339ab5490acc09f404f214a8719d89d07056"
subprocess.run(["dpkg-deb","-x",str(package),str(HERE/"iverilog")],check=True)
print("Pinned tools prepared locally; run python3 reproduce.py.")
