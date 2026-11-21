"""Build a D-only, profile-independent stdlib runtime from installed Python3.12.10.
No download, registry edit, venv mutation, project credential or site-package copy.
"""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();target=a.output.resolve();source=a.source.resolve()
if os.name!='nt' or Path('D:/ZS-SMART-GATE').resolve() not in target.parents or target.exists():
 p.error('fresh owned D: runtime required')
version=subprocess.check_output([str(source/'python.exe'),'-I','-B','-c','import platform;print(platform.python_version())'],text=True).strip()
if version!='3.12.10':p.error('existing official Python3.12.10 required')
target.mkdir(parents=True)
files=[]
for item in source.iterdir():
 if item.is_file() and (item.suffix.lower() in ('.exe','.dll','.txt') or item.name.lower().startswith('license')):
  files.append(item)
for folder in ('Lib','DLLs','tcl'):
 for item in (source/folder).rglob('*'):
  if item.is_file() and not any(part.lower() in ('site-packages','__pycache__','test','tests') for part in item.relative_to(source).parts):
   files.append(item)
manifest=[]
for item in sorted(files):
 relative=item.relative_to(source);output=target/relative;output.parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(item,output)
 raw=output.read_bytes();pin=hashlib.sha256(raw).hexdigest()
 if pin!=hashlib.sha256(item.read_bytes()).hexdigest():raise SystemExit('RUNTIME_COPY_HASH_MISMATCH')
 manifest.append(dict(path=relative.as_posix(),bytes=len(raw),sha256=pin))
probe="import platform,sys,ssl,ctypes,sqlite3,unittest,json; print(json.dumps(dict(version=platform.python_version(),prefix=sys.prefix,stdlib=__import__('os').__file__,isolated=sys.flags.isolated)))"
result=json.loads(subprocess.check_output([str(target/'python.exe'),'-I','-B','-c',probe],text=True))
if result['version']!='3.12.10' or result['prefix'].lower()!=str(target).lower() or not result['stdlib'].lower().startswith(str(target).lower()):
 raise SystemExit('RUNTIME_PREFIX_NOT_D_ONLY')
record=dict(schema='zs.ops24.d-only-python.v1',version=version,origin='EXISTING_INSTALLED_PYTHON_COPY_NOT_NEW_DOWNLOAD',
 original_installation_unchanged=True,site_packages_copied=False,registry_changes=False,probe=result,files=manifest)
(target/'runtime-manifest.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status='D_ONLY_RUNTIME_VERIFIED',files=len(manifest),bytes=sum(r['bytes'] for r in manifest),runtime=str(target),version=version)))
