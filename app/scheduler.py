import logging
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from app.config import load
from app.database import init_db
from app.pipeline import execute, dispatch
from app.dates import scheduled

logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')


def next_run(cfg,now):
    local=now.astimezone(ZoneInfo(cfg['timezone']))
    start=scheduled(local.date(),cfg['start_time'],cfg['timezone'])
    return start if local<start else scheduled(local.date()+timedelta(days=1),cfg['start_time'],cfg['timezone'])


def tick(cfg,now=None):
    now=now or datetime.now(timezone.utc)
    local=now.astimezone(ZoneInfo(cfg['timezone']))
    if local>=scheduled(local.date(),cfg['start_time'],cfg['timezone']):
        execute(cfg,now)
    if local>=scheduled(local.date(),cfg['delivery_time'],cfg['timezone']):
        dispatch(cfg)


def main():
    cfg=load()
    init_db(cfg)
    while True:
        try:
            cfg=load()
            tick(cfg)
        except Exception:
            logging.exception('Ciclo incompleto, nuovo tentativo tra 60 secondi')
        time.sleep(60)


if __name__=='__main__':
    main()
