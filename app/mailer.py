"""SMTP outbox with conservative handling of ambiguous delivery outcomes."""
import hashlib
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import parseaddr
from pathlib import Path
from app.database import connect, rows
from app.dates import now_iso


def settings():
    return {k:os.getenv(k,'') for k in ('SMTP_HOST','SMTP_PORT','SMTP_USER','SMTP_PASSWORD',
        'SMTP_FROM','EMAIL_TO','SMTP_SECURITY','EMAIL_ENABLED')}


def fingerprint(s):
    return hashlib.sha256(json.dumps({k:v for k,v in s.items() if k!='EMAIL_ENABLED'},sort_keys=True).encode()).hexdigest()


def validate_settings(s):
    for k in ('SMTP_HOST','SMTP_FROM','EMAIL_TO'):
        if not s[k] or '\n' in s[k] or '\r' in s[k]:
            raise ValueError(k+' mancante o non valido')
    for k in ('SMTP_FROM','EMAIL_TO'):
        address=parseaddr(s[k])[1]
        if address != s[k] or '@' not in address or ',' in address:
            raise ValueError(k+' deve contenere un solo indirizzo email')
    if s['SMTP_SECURITY'] not in ('starttls','ssl'):
        raise ValueError('SMTP_SECURITY deve essere starttls o ssl')


def client(s):
    validate_settings(s)
    context=ssl.create_default_context()
    if s['SMTP_SECURITY']=='ssl':
        smtp=smtplib.SMTP_SSL(s['SMTP_HOST'],int(s['SMTP_PORT'] or 465),timeout=30,context=context)
    else:
        smtp=smtplib.SMTP(s['SMTP_HOST'],int(s['SMTP_PORT'] or 587),timeout=30)
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
    try:
        if s['SMTP_USER']:
            smtp.login(s['SMTP_USER'],s['SMTP_PASSWORD'])
        return smtp
    except Exception:
        smtp.close()
        raise


def verify(cfg):
    s=settings()
    smtp=client(s)
    try:
        smtp.noop()
    finally:
        smtp.close()
    path=Path(cfg['data_dir'])/'email-verified.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'fingerprint':fingerprint(s),'verified_at':now_iso()}))
    path.chmod(0o600)
    return 'Connessione e autenticazione verificate. Nessun messaggio inviato. Controlla EMAIL_TO prima di abilitare.'


def deliver(cfg,report,force_preview=False):
    s=settings()
    payload=json.loads(report['payload'])
    message=EmailMessage()
    message['Subject']=payload['title']
    message['From']=s['SMTP_FROM'] or 'preview@example.invalid'
    message['To']=s['EMAIL_TO'] or 'preview@example.invalid'
    message['Message-ID']=f"<{report['id']}@biotech-observatory.local>"
    message.set_content(Path(report['text_path']).read_text())
    message.add_alternative(Path(report['html_path']).read_text(),subtype='html')
    out=Path(cfg['data_dir'])/'outbox'
    out.mkdir(parents=True,exist_ok=True)
    preview=out/(report['id']+'.eml')
    preview.write_bytes(message.as_bytes())
    preview.chmod(0o600)
    if force_preview or s['EMAIL_ENABLED'].lower()!='true':
        return 'preview'
    validate_settings(s)
    verification=Path(cfg['data_dir'])/'email-verified.json'
    if not verification.exists() or json.loads(verification.read_text()).get('fingerprint')!=fingerprint(s):
        raise ValueError('Eseguire email-verify per questa configurazione prima di inviare')
    recipient=s['EMAIL_TO']
    with connect(cfg) as db:
        db.execute('INSERT OR IGNORE INTO deliveries(report_id,recipient,state,updated_at) VALUES(?,?,?,?)',
                   (report['id'],recipient,'pending',now_iso()))
        d=db.execute('SELECT * FROM deliveries WHERE report_id=? AND recipient=?',(report['id'],recipient)).fetchone()
        if d['state'] in ('sent','sending','uncertain'):
            return d['state']
        if d['attempts']>=cfg['max_attempts']:
            return 'failed'
        db.execute("UPDATE deliveries SET attempts=attempts+1,updated_at=? WHERE report_id=? AND recipient=?",
                   (now_iso(),report['id'],recipient))
    # Connect/authentication failures happen before any message can be accepted and can be retried.
    try:
        smtp=client(s)
    except Exception as exc:
        with connect(cfg) as db:
            db.execute("UPDATE deliveries SET state='retry',error=?,updated_at=? WHERE report_id=? AND recipient=?",
                       (type(exc).__name__,now_iso(),report['id'],recipient))
        return 'retry'
    with connect(cfg) as db:
        changed=db.execute("UPDATE deliveries SET state='sending' WHERE report_id=? AND recipient=? AND state IN ('pending','retry')",
                           (report['id'],recipient)).rowcount
    if not changed:
        smtp.close()
        return 'sending'
    try:
        smtp.send_message(message,from_addr=s['SMTP_FROM'],to_addrs=[recipient])
    except Exception as exc:
        # SMTP cannot guarantee exactly-once. Do not blindly resend after ambiguous DATA failures.
        with connect(cfg) as db:
            db.execute("UPDATE deliveries SET state='uncertain',error=?,updated_at=? WHERE report_id=? AND recipient=?",
                       (type(exc).__name__,now_iso(),report['id'],recipient))
        return 'uncertain'
    else:
        with connect(cfg) as db:
            db.execute("UPDATE deliveries SET state='sent',error=NULL,updated_at=? WHERE report_id=? AND recipient=?",
                       (now_iso(),report['id'],recipient))
        return 'sent'
    finally:
        smtp.close()
