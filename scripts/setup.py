"""Create local configuration without overwriting existing credentials or data."""
import os
from pathlib import Path
import secrets

root=Path(__file__).resolve().parents[1]
for name in ('data','data/imports','data/reports','data/outbox'):
    (root/name).mkdir(parents=True,exist_ok=True)
path=root/'.env'
if not path.exists():
    template=(root/'.env.example').read_text()
    template=template.replace('SEARXNG_SECRET=\n','SEARXNG_SECRET='+secrets.token_hex(32)+'\n')
    template=template.replace('LOCAL_UID=1000','LOCAL_UID='+str(os.getuid()))
    template=template.replace('LOCAL_GID=1000','LOCAL_GID='+str(os.getgid()))
    path.write_text(template)
    path.chmod(0o600)
    print('.env creato. Configura Ollama ed email prima di abilitare gli invii.')
else:
    print('.env esistente preservato. Verifica che SEARXNG_SECRET sia nuovo e non vuoto.')
