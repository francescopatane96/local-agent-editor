import html
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from app.http import fetch, json_request
from app.database import ingest, rows, connect, canonical


def plain(value):
    return html.unescape(re.sub(r'<[^>]+>', ' ', value or '')).strip()


def parse_feed(body, source):
    if b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():
        raise ValueError('DTD o entità XML non consentite')
    root = ET.fromstring(body)
    def tag(e):
        return e.tag.rsplit('}',1)[-1]
    items = []
    for entry in root.iter():
        if tag(entry) not in ('item','entry'):
            continue
        fields = {}
        for child in entry:
            name = tag(child)
            value = ''.join(child.itertext()).strip()
            if name == 'link':
                if child.get('rel','alternate') == 'alternate':
                    fields['url'] = child.get('href') or value
            elif name == 'author':
                fields['author'] = value
            else:
                fields[name] = value
        items.append({'title':plain(fields.get('title')), 'url':fields.get('url',''),
                      'text':plain(fields.get('encoded') or fields.get('content') or fields.get('summary') or fields.get('description')),
                      'published_at':fields.get('published') or fields.get('pubDate') or fields.get('date'),
                      'updated_at':fields.get('updated'), 'author':fields.get('author') or fields.get('creator',''),
                      'source':source['name'], 'kind':source.get('kind','research'),
                      'date_zone':source.get('timezone','UTC'), 'language':source.get('language',''),
                      'priority':source.get('priority',0), 'partial':True})
    return items


def extract(url):
    # LinkedIn is import-only: no scraping of profiles, feeds or posts.
    host = (urlsplit(url).hostname or '').lower()
    if host == 'linkedin.com' or host.endswith('.linkedin.com'):
        return ''
    body, _ = fetch(url, retries=0, timeout=15)
    import trafilatura
    return (trafilatura.extract(body.decode('utf-8',errors='replace'),
            include_comments=False, include_tables=False) or '')[:16000]


def collect(cfg, deadline=None):
    counts = dict.fromkeys(('found','new','updated','duplicates','discarded','failed'),0)
    coverage = []
    def accept(items):
        for item in items:
            if deadline and time.monotonic() >= deadline:
                coverage.append({'source':'budget','status':'partial','detail':'Tempo di raccolta esaurito'})
                break
            counts['found'] += 1
            try:
                counts[ingest(cfg,item)] += 1
            except Exception as exc:
                counts['failed'] += 1
                coverage.append({'source':item.get('source','import'), 'status':'error', 'detail':type(exc).__name__})
    for source in cfg['rss']:
        if not source.get('enabled',True):
            continue
        if deadline and time.monotonic() >= deadline:
            coverage.append({'source':source['name'],'status':'skipped','detail':'Budget esaurito'})
            continue
        try:
            cached = rows(cfg,'SELECT * FROM feed_cache WHERE url=?',(source['url'],))
            headers = {}
            if cached:
                if cached[0]['etag']:
                    headers['If-None-Match'] = cached[0]['etag']
                if cached[0]['modified']:
                    headers['If-Modified-Since'] = cached[0]['modified']
            body, response_headers = fetch(source['url'],headers=headers,timeout=20,retries=0)
            if body is not None:
                accept(parse_feed(body,source))
                h = {k.lower():v for k,v in response_headers.items()}
                with connect(cfg) as db:
                    db.execute('INSERT OR REPLACE INTO feed_cache VALUES(?,?,?)',
                               (source['url'],h.get('etag'),h.get('last-modified')))
            coverage.append({'source':source['name'],'status':'ok' if body is not None else 'unchanged'})
        except Exception as exc:
            coverage.append({'source':source['name'],'status':'error','detail':type(exc).__name__})
            counts['failed'] += 1
    for query in cfg['queries']:
        if deadline and time.monotonic() >= deadline:
            coverage.append({'source':query,'status':'skipped','detail':'Budget esaurito'})
            continue
        try:
            result = json_request(cfg['searxng_url']+'/search?'+urlencode({
                'q':query,'format':'json','time_range':'week','language':cfg['search_language']}),
                public=False,timeout=20,retries=0)
            items = []
            for hit in result.get('results',[])[:cfg['results_per_query']]:
                url = hit.get('url','')
                host = (urlsplit(url).hostname or '').lower()
                if host == 'linkedin.com' or host.endswith('.linkedin.com'):
                    continue
                items.append({'title':hit.get('title'), 'url':url, 'source':host,
                              'text':plain(hit.get('content')), 'published_at':hit.get('publishedDate'),
                              'kind':'web', 'partial':True})
            accept(items)
            coverage.append({'source':query,'status':'ok'})
        except Exception as exc:
            counts['failed'] += 1
            coverage.append({'source':query,'status':'error','detail':type(exc).__name__})
    path = Path(cfg['data_dir'])/'imports/linkedin.json'
    if path.exists():
        try:
            posts = json.loads(path.read_text())
            if not isinstance(posts,list):
                raise ValueError('Import deve essere una lista')
            for post in posts:
                host = (urlsplit(post['url']).hostname or '').lower()
                if not (host == 'linkedin.com' or host.endswith('.linkedin.com')):
                    raise ValueError('Import LinkedIn contiene URL estraneo')
                post.update(kind='linkedin', source='LinkedIn import autorizzato')
                post['partial'] = post.get('partial',True)
                post['priority'] = 10 if post.get('author') in cfg['linkedin_authors'] else 0
            accept(posts)
            coverage.append({'source':'LinkedIn','status':'import_only','detail':f'{len(posts)} post forniti, nessun accesso al feed personale'})
        except Exception as exc:
            counts['failed'] += 1
            coverage.append({'source':'LinkedIn','status':'error','detail':type(exc).__name__})
    else:
        coverage.append({'source':'LinkedIn','status':'unconfigured','detail':'Solo import autorizzati, nessuna copertura del feed personale'})
    return counts, coverage
