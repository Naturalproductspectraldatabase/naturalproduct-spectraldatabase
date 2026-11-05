"""Extract allowlisted source from an exact blobless Git revision. No datasets/assets."""
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

PREFIX = 'NMR_Database_Tyas_GitHub_Upload/'
ROOTS = ('.github/scripts/', PREFIX+'scripts/', PREFIX+'tests/', PREFIX+'supabase/')


def allowed(name):
    path=PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name:
        return False
    if name in ('requirements.txt',PREFIX+'requirements.txt'):
        return True
    return any(name.startswith(root) for root in ROOTS) and path.suffix.lower() in {'.py','.js','.sql','.sh'}


def main(sha):
    if not re.fullmatch('[0-9a-f]{40}',sha):
        raise ValueError('Exact commit required')
    output=subprocess.check_output(['git','ls-tree','-r','-z',sha,'--',*ROOTS,'requirements.txt',PREFIX+'requirements.txt'])
    count=0
    for entry in output.split(b'\0'):
        if not entry:continue
        metadata,name=entry.decode().split('\t',1)
        mode,kind,blob=metadata.split()
        if kind!='blob' or mode not in {'100644','100755'} or not allowed(name):continue
        target=Path(name)
        if target.is_symlink() or any(p.is_symlink() for p in target.parents):
            raise ValueError('Symlink destination refused')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(subprocess.check_output(['git','show',sha+':'+name]))
        count+=1
    if not Path(PREFIX+'scripts/app.py').is_file():raise ValueError('Application source missing')
    print(f'SYNTHETIC_SOURCE_ONLY files={count} exact_sha={sha}; no dataset/image/database/backup/credential files extracted')


if __name__=='__main__':main(sys.argv[1])
