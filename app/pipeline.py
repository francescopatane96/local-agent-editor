import fcntl
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from app.database import init_db, connect, rows
from app.dates import now_iso, scheduled
from app.collector import collect
from app.analyzer import analyze_pending
from app.reporter import generate_report
from app.mailer import deliver


@contextmanager
def exclusive(cfg):
    Path(cfg['data_dir']).mkdir(parents=True,exist_ok=True)
    with (Path(cfg['data_dir'])/'pipeline.lock').open('a') as handle:
        try:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Pipeline già in esecuzione') from None
        try:
            yield
        finally:
            fcntl.flock(handle,fcntl.LOCK_UN)


def execute(cfg,now=None,finalize=False,preview=False):
    now=now or datetime.now(timezone.utc)
    local=now.astimezone(ZoneInfo(cfg['timezone']))
    cutoff=scheduled(local.date(),cfg['delivery_time'],cfg['timezone'])-timedelta(minutes=10)
    seconds=max(0,(cutoff-now).total_seconds())
    deadline=time.monotonic()+seconds
    with exclusive(cfg):
        init_db(cfg)
        day_start=scheduled(local.date(),'00:00',cfg['timezone']).astimezone(timezone.utc).isoformat()
        run=rows(cfg,'SELECT * FROM runs WHERE started_at>=? ORDER BY id DESC LIMIT 1',(day_start,))
        if run and run[0]['state']=='finished' and not finalize:
            return run[0]
        retry_collection=bool(run and run[0]['state']=='running'
            and json.loads(run[0]['counts']).get('collection_attempts',1)<cfg['max_attempts']
            and any(c['status']=='error' for c in json.loads(run[0]['coverage'])))
        if not run or run[0]['state']=='collecting' or retry_collection:
            if run:
                rid=run[0]['id']
            else:
                with connect(cfg) as db:
                    rid=db.execute("INSERT INTO runs(started_at,state,counts,coverage) VALUES(?,'collecting','{}','[]')",(now.isoformat(),)).lastrowid
            if seconds>60 or finalize:
                counts,coverage=collect(cfg, min(deadline,time.monotonic()+cfg['collection_budget_seconds']) if not finalize else time.monotonic()+cfg['collection_budget_seconds'])
            else:
                counts,coverage={},[{'source':'scheduler','status':'partial','detail':'Avvio tardivo, raccolta rinviata al ciclo successivo'}]
            previous_counts=json.loads(run[0]['counts']) if run else {}
            for k,v in previous_counts.items():
                counts[k]=counts.get(k,0)+v
            counts['collection_attempts']=previous_counts.get('collection_attempts',0)+1
            with connect(cfg) as db:
                db.execute("UPDATE runs SET state='running',counts=?,coverage=? WHERE id=?",(json.dumps(counts),json.dumps(coverage),rid))
        else:
            rid=run[0]['id']
            counts=json.loads(run[0]['counts'])
            coverage=json.loads(run[0]['coverage'])
        if seconds>30 or finalize:
            analysis=analyze_pending(cfg,deadline if not finalize else time.monotonic()+cfg['manual_budget_seconds'])
            for k,v in analysis.items():
                counts['analysis_'+k]=counts.get('analysis_'+k,0)+v
        with connect(cfg) as db:
            db.execute('UPDATE runs SET counts=? WHERE id=?',(json.dumps(counts),rid))
        if finalize or datetime.now(timezone.utc)>=cutoff or seconds<=0:
            generate_report(cfg,'daily',now,coverage,counts)
            if local.weekday()==0:
                generate_report(cfg,'weekly',now,coverage,counts)
            with connect(cfg) as db:
                db.execute("UPDATE runs SET state='finished',finished_at=? WHERE id=?",(now_iso(),rid))
        if preview:
            for r in rows(cfg,'SELECT * FROM reports ORDER BY created_at DESC LIMIT 2'):
                deliver(cfg,r,force_preview=True)
        return {'counts':counts,'coverage':coverage}


def dispatch(cfg):
    with exclusive(cfg):
        init_db(cfg)
        # Retry only current reports. Never flood a newly configured inbox with an old archive.
        for kind in ('daily','weekly'):
            latest=rows(cfg,'SELECT * FROM reports WHERE kind=? ORDER BY end_at DESC LIMIT 1',(kind,))
            if latest:
                deliver(cfg,latest[0])
