import fcntl
import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from app.dates import now_iso, normalized


def canonical(url):
    p = urlsplit(url.strip())
    if p.scheme not in ('https', 'http') or not p.hostname or p.username or p.password:
        raise ValueError('URL HTTP(S) senza credenziali richiesto')
    query = sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                   if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid','trk'))
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', urlencode(query), ''))


def digest(text):
    return hashlib.sha256(re.sub(r'\s+', ' ', text).strip().lower().encode()).hexdigest()


@contextmanager
def connect(cfg):
    Path(cfg['db_path']).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(cfg['db_path'], timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db(cfg):
    Path(cfg['db_path']).parent.mkdir(parents=True, exist_ok=True)
    with Path(cfg['db_path'] + '.migration.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            _initialize(cfg)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _initialize(cfg):
    with connect(cfg) as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY, applied_at TEXT);
        CREATE TABLE IF NOT EXISTS items(
          id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL UNIQUE,
          original_url TEXT NOT NULL, source TEXT, author TEXT, published_at TEXT,
          updated_at TEXT, collected_at TEXT NOT NULL, publication_raw TEXT,
          date_zone TEXT, kind TEXT, language TEXT, text TEXT, partial INTEGER NOT NULL DEFAULT 1,
          content_hash TEXT, event_key TEXT, category TEXT, topics TEXT DEFAULT '[]', entities TEXT DEFAULT '[]',
          analysis TEXT, score REAL DEFAULT 0, state TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0,
          next_attempt TEXT, error TEXT, model TEXT, prompt_version TEXT, analyzed_at TEXT,
          priority INTEGER DEFAULT 0);
        CREATE INDEX IF NOT EXISTS items_queue ON items(state,next_attempt,collected_at);
        CREATE INDEX IF NOT EXISTS items_period ON items(published_at);
        CREATE INDEX IF NOT EXISTS items_event ON items(event_key);
        CREATE TABLE IF NOT EXISTS provenance(
          item_id TEXT REFERENCES items(id), url TEXT, source TEXT, seen_at TEXT,
          PRIMARY KEY(item_id,url,source));
        CREATE TABLE IF NOT EXISTS reports(
          id TEXT PRIMARY KEY, kind TEXT NOT NULL, start_at TEXT, end_at TEXT, created_at TEXT,
          payload TEXT, html_path TEXT, text_path TEXT, UNIQUE(kind,start_at,end_at));
        CREATE TABLE IF NOT EXISTS report_items(
          report_id TEXT REFERENCES reports(id), item_id TEXT REFERENCES items(id), section TEXT,
          PRIMARY KEY(report_id,item_id));
        CREATE TABLE IF NOT EXISTS runs(
          id INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT, state TEXT,
          counts TEXT, coverage TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS deliveries(
          report_id TEXT REFERENCES reports(id), recipient TEXT, state TEXT, attempts INTEGER DEFAULT 0,
          updated_at TEXT, error TEXT, PRIMARY KEY(report_id,recipient));
        CREATE TABLE IF NOT EXISTS feed_cache(url TEXT PRIMARY KEY, etag TEXT, modified TEXT);
        CREATE TABLE IF NOT EXISTS trend_reports(
          id INTEGER PRIMARY KEY, overview TEXT, trends_json TEXT, created_at TEXT);
        ''')
        old = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='articles'").fetchone()
        migrated = db.execute('SELECT 1 FROM schema_versions WHERE version=1').fetchone()
        if old and not migrated:
            # Online SQLite backup preserves every legacy table before migration.
            backup = sqlite3.connect(str(Path(cfg['db_path']).with_suffix('.pre-observatory.bak')))
            db.backup(backup)
            backup.close()
            for r in db.execute('SELECT * FROM articles').fetchall():
                r = dict(r)
                try:
                    url = canonical(r['url'])
                except ValueError:
                    continue  # Original record remains intact in articles and backup.
                text = r.get('original_summary') or ''
                title = r.get('title') or ''
                db.execute('''INSERT OR IGNORE INTO items
                  (id,title,url,original_url,source,published_at,publication_raw,collected_at,
                   kind,text,content_hash,event_key,category)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                  (digest(url),title,url,r['url'],r.get('source'),normalized(r.get('published')),
                   r.get('published'),normalized(r.get('created_at')) or now_iso(),
                   'legacy',text,digest(text) if text else None,digest(title),r.get('category')))
            # Legacy AI is preserved in articles. New scope requires fresh classification.
        db.execute('INSERT OR IGNORE INTO schema_versions VALUES (1,?)', (now_iso(),))


def ingest(cfg, item):
    url = canonical(item['url'])
    title = (item.get('title') or '').strip()
    if not title:
        return 'discarded'
    content = (item.get('text') or '').strip()
    h = digest(content) if len(content) >= 160 else None
    now = now_iso()
    with connect(cfg) as db:
        existing = db.execute('SELECT * FROM items WHERE url=?', (url,)).fetchone()
        if existing:
            # Enrich missing dates/authors when a later source supplies them. Never use collection time.
            db.execute('''UPDATE items SET published_at=COALESCE(published_at,?),
                publication_raw=COALESCE(publication_raw,?),
                author=CASE WHEN author IS NULL OR author='' THEN ? ELSE author END WHERE id=?''',
                (normalized(item.get('published_at'),item.get('date_zone','UTC')),
                 item.get('published_at'),item.get('author',''),existing['id']))
            db.execute('INSERT OR IGNORE INTO provenance VALUES(?,?,?,?)',
                       (existing['id'],item['url'],item.get('source',''),now))
            changed = bool(h and h != existing['content_hash'])
            # Never replace a complete extraction by a search snippet.
            if changed and (not item.get('partial', True) or existing['partial']):
                db.execute('''UPDATE items SET text=?,content_hash=?,updated_at=?,state='pending',
                   attempts=0,next_attempt=NULL,error=NULL,analysis=NULL,partial=? WHERE id=?''',
                   (content,h,normalized(item.get('updated_at')),int(item.get('partial',True)),existing['id']))
                return 'updated'
            return 'duplicates'
        equivalent = db.execute('SELECT event_key FROM items WHERE content_hash=?', (h,)).fetchone() if h else None
        event = equivalent['event_key'] if equivalent else digest(title)
        ident = digest(url)
        db.execute('''INSERT INTO items
          (id,title,url,original_url,source,author,published_at,updated_at,collected_at,publication_raw,
           date_zone,kind,language,text,partial,content_hash,event_key,priority)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
          (ident,title,url,item['url'],item.get('source',''),item.get('author',''),
           normalized(item.get('published_at'),item.get('date_zone','UTC')),
           normalized(item.get('updated_at'),item.get('date_zone','UTC')),now,item.get('published_at'),
           item.get('date_zone','UTC'),item.get('kind','news'),item.get('language',''),content,
           int(item.get('partial',True)),h,event,item.get('priority',0)))
        db.execute('INSERT INTO provenance VALUES(?,?,?,?)',(ident,item['url'],item.get('source',''),now))
    return 'new'


def rows(cfg, sql, args=()):
    with connect(cfg) as db:
        return [dict(r) for r in db.execute(sql,args)]
