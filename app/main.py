import argparse
from app.config import load
from app.database import init_db
from app.pipeline import execute, exclusive
from app.mailer import verify


def main():
    parser=argparse.ArgumentParser(description='Osservatorio biotech locale')
    parser.add_argument('command',choices=['init','run','email-verify','retry-failed'])
    args=parser.parse_args()
    cfg=load()
    if args.command=='run':
        print(execute(cfg,finalize=True,preview=True))
        return
    with exclusive(cfg):
        init_db(cfg)
        if args.command=='email-verify':
            print(verify(cfg))
        elif args.command=='retry-failed':
            from app.database import connect
            with connect(cfg) as db:
                n=db.execute("UPDATE items SET state='pending',attempts=0,next_attempt=NULL WHERE state='failed'").rowcount
            print(f'{n} elementi rimessi in coda')


if __name__=='__main__':
    main()
