"""Run BEFORE switching to the migration branch: preserve Git-tracked runtime files."""
import argparse
import shutil
import sqlite3
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('destination',help='Directory di backup esterna alla repository')
args=parser.parse_args()
root=Path.cwd().resolve()
dest=Path(args.destination).resolve()
if dest==root or root in dest.parents or dest.exists():
    raise SystemExit('Usa una nuova directory esterna alla repository')
dest.mkdir(parents=True)
source=root/'data'
if source.exists():
    shutil.copytree(source,dest/'data',ignore=shutil.ignore_patterns('news.db','news.db-wal','news.db-shm'))
    db_path=source/'news.db'
    if db_path.exists():
        src=sqlite3.connect(str(db_path))
        dst=sqlite3.connect(str(dest/'data/news.db'))
        src.backup(dst)
        dst.close()
        src.close()
print('Backup creato in',dest)
