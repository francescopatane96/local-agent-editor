import copy
import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, Mock
from app.config import load
from app.database import init_db, ingest, rows, connect, canonical
from app.dates import period, normalized
from app.collector import parse_feed, collect
from app.analyzer import SCHEMA, validate, analyze_pending, PROMPT_VERSION
from app.reporter import generate_report, select
from app.pipeline import execute, exclusive
from app.mailer import deliver, fingerprint
from app.scheduler import next_run


def analysis():
    result={k:'' for k,v in SCHEMA['properties'].items() if v['type']=='string'}
    result.update({k:[] for k,v in SCHEMA['properties'].items() if v['type']=='array'})
    result.update(relevant=True,category='tools',summary='Nuovo strumento per analizzare dati genomici.',
        reason='Applicazione documentata alla bioinformatica.',novelty='Nuovo metodo',limitations='Preprint non validato',
        software={k:'' for k in SCHEMA['properties']['software']['properties']},
        scores={k:8 for k in ('relevance','novelty','evidence','utility')})
    return result


class ObservatoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.cfg=load()
        self.cfg.update(data_dir=self.temp.name,db_path=self.temp.name+'/news.db',extract_full_text=False,
                        rss=[],queries=[],max_analysis_per_run=20)
        init_db(self.cfg)
        self.now=datetime(2026,11,9,6,tzinfo=timezone.utc)

    def tearDown(self):
        self.temp.cleanup()

    def add(self,url='https://example.org/paper',date='2026-11-08T10:00:00Z',text='Genomics research '*30):
        ingest(self.cfg,{'url':url,'title':'New biotech '+url,'text':text,'published_at':date,'source':'Journal','kind':'preprint'})
        return rows(self.cfg,'SELECT * FROM items WHERE url=?',(canonical(url),))[0]

    def analyzed(self,**kwargs):
        item=self.add(**kwargs)
        with connect(self.cfg) as db:
            db.execute("UPDATE items SET state='analyzed',analysis=?,category='tools',score=8,prompt_version=? WHERE id=?",
                       (json.dumps(analysis()),PROMPT_VERSION,item['id']))
        return item

    def test_empty_database_all_tables(self):
        init_db(self.cfg)
        for table in ('items','reports','runs','deliveries','trend_reports','report_items'):
            self.assertEqual(rows(self.cfg,'SELECT * FROM '+table),[])

    def test_legacy_migration_preserves_and_backs_up(self):
        with connect(self.cfg) as db:
            db.execute('DELETE FROM schema_versions')
            db.execute('CREATE TABLE articles(id INTEGER,title TEXT,url TEXT,source TEXT,published TEXT,original_summary TEXT,created_at TEXT,ai_summary TEXT)')
            db.execute("INSERT INTO articles VALUES(1,'Old','https://example.org/old','test','2026-11-06T12:00:00Z','legacy','2026-11-06','preserved')")
        init_db(self.cfg)
        init_db(self.cfg)
        self.assertEqual(len(rows(self.cfg,'SELECT * FROM items')),1)
        self.assertEqual(rows(self.cfg,'SELECT * FROM articles')[0]['ai_summary'],'preserved')
        self.assertTrue(Path(self.temp.name+'/news.pre-observatory.bak').exists())

    def test_normalization_dedup_and_updates(self):
        self.add(url='https://example.org/paper?utm_source=x&a=1')
        state=ingest(self.cfg,{'title':'New','url':'https://example.org/paper?a=1#part','text':'Genomics research '*30})
        self.assertEqual(state,'duplicates')
        self.assertEqual(len(rows(self.cfg,'SELECT * FROM items')),1)
        self.assertEqual(ingest(self.cfg,{'title':'New','url':'https://example.org/paper?a=1','text':'Changed sequence '*30}),'updated')

    def test_complete_content_not_replaced_by_excerpt(self):
        ingest(self.cfg,{'url':'https://example.org/x','title':'A','text':'complete '*40,'partial':False})
        self.assertEqual(ingest(self.cfg,{'url':'https://example.org/x','title':'A','text':'snippet '*40}),'duplicates')
        self.assertEqual(rows(self.cfg,'SELECT partial FROM items')[0]['partial'],0)

    def test_equivalent_content_grouped_preserves_links(self):
        self.analyzed(url='https://example.org/a')
        self.analyzed(url='https://example.org/b')
        start,end=period('daily',self.now)
        items,n,duplicates=select(self.cfg,'daily',start,end)
        self.assertEqual((len(items),n,duplicates),(1,2,1))
        self.assertEqual(len(items[0]['related']),1)

    def test_dst_calendar_days(self):
        for now,hours in [(datetime(2026,3,30,6,tzinfo=timezone.utc),23),
                          (datetime(2026,10,26,6,tzinfo=timezone.utc),25)]:
            start,end=period('daily',now)
            self.assertEqual((end-start).total_seconds()/3600,hours)
        start,end=period('weekly',self.now)
        self.assertEqual(start.isoformat(),'2026-11-01T23:00:00+00:00')
        self.assertEqual(end.isoformat(),'2026-11-08T23:00:00+00:00')
        self.assertIsNone(normalized('not a date'))
        self.assertIsNone(normalized(None))

    def test_rss_and_atom_dates_not_substituted(self):
        atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Biotech</title><link href="https://example.org/a"/><updated>2026-11-07T09:00:00Z</updated><summary>Text</summary></entry></feed>'
        item=parse_feed(atom,{'name':'Atom'})[0]
        self.assertIsNone(item['published_at'])
        self.assertTrue(item['updated_at'])
        rss=b'<rss><channel><item><title>R genomics</title><link>https://example.org/r</link><pubDate>Sun, 08 Nov 2026 12:00:00 GMT</pubDate><description>Test</description></item></channel></rss>'
        self.assertEqual(normalized(parse_feed(rss,{'name':'rss'})[0]['published_at']),'2026-11-08T12:00:00+00:00')
        with self.assertRaises(ValueError):
            parse_feed(b'<!DOCTYPE foo><rss/>',{'name':'x'})

    def test_validation_rejects_incomplete_and_wrong_types(self):
        validate(analysis())
        for data in ({},[],{**analysis(),'scores':{'relevance':True}}, {**analysis(),'category':'AI'}):
            with self.assertRaises(ValueError):
                validate(data)

    def test_oldest_first_and_invalid_retry(self):
        old=self.add(url='https://example.org/old',text='old text')
        new=self.add(url='https://example.org/new',text='new text')
        self.cfg['max_analysis_per_run']=1
        with patch('app.analyzer.generate',return_value=analysis()) as call:
            result=analyze_pending(self.cfg)
            self.assertIn('old text',call.call_args.args[1])
            self.assertEqual(result['analyzed'],1)
        with patch('app.analyzer.generate',side_effect=ValueError('bad JSON')):
            result=analyze_pending(self.cfg)
        self.assertEqual(result['failed'],1)
        item=rows(self.cfg,'SELECT * FROM items WHERE id=?',(new['id'],))[0]
        self.assertEqual(item['state'],'retry')
        with patch('app.analyzer.generate') as call:
            analyze_pending(self.cfg)
            call.assert_not_called()

    def test_equivalent_analysis_reused(self):
        self.analyzed(url='https://example.org/a')
        self.add(url='https://example.org/b')
        with patch('app.analyzer.generate') as call:
            result=analyze_pending(self.cfg)
            call.assert_not_called()
        self.assertEqual(result['reused'],1)

    def test_daily_boundaries_unknown_late_and_idempotence(self):
        self.analyzed(url='https://example.org/start',date='2026-11-07T23:00:00Z',text='start')
        self.analyzed(url='https://example.org/end',date='2026-11-08T23:00:00Z',text='end')
        self.analyzed(url='https://example.org/unknown',date=None,text='unknown')
        self.analyzed(url='https://example.org/late',date='2026-11-01T10:00:00Z',text='late')
        r=generate_report(self.cfg,now=self.now)
        p=json.loads(r['payload'])
        self.assertEqual(p['eligible_count'],1)
        self.assertEqual({i['section'] for i in p['items']},{'tools','late','unknown'})
        self.assertEqual(r['id'],generate_report(self.cfg,now=self.now)['id'])
        self.assertEqual(len(rows(self.cfg,'SELECT * FROM reports')),1)
        next_report=generate_report(self.cfg,now=self.now+timedelta(days=1))
        self.assertNotIn('unknown',[i['section'] for i in json.loads(next_report['payload'])['items']])
        self.assertTrue(Path(r['html_path']).exists())

    def test_weekly_real_synthesis_and_invalid_citations(self):
        item=self.analyzed()
        model={'overview':'Sintesi','trends':[{'name':'Genomics','evidence':'Un metodo','hypothesis':'Possibile prodotto',
                 'next_steps':'Validare','source_ids':[item['id']]}]}
        with patch('app.reporter.generate',return_value=model):
            report=generate_report(self.cfg,'weekly',self.now)
        self.assertEqual(json.loads(report['payload'])['trends']['input_count'],1)
        self.assertTrue(Path(report['html_path']).exists())

    def test_weekly_failure_still_archived(self):
        self.analyzed()
        with patch('app.reporter.generate',side_effect=TimeoutError()):
            report=generate_report(self.cfg,'weekly',self.now)
        self.assertIn('parziale',' '.join(json.loads(report['payload'])['warnings']))

    def test_collection_partial_failure_and_linkedin_import(self):
        self.cfg['queries']=['genomics']
        path=Path(self.temp.name)/'imports'
        path.mkdir()
        (path/'linkedin.json').write_text(json.dumps([{'title':'Tool','url':'https://www.linkedin.com/posts/test',
            'author':'Author','text':'genomics','published_at':None}]))
        self.cfg['linkedin_authors']=['Author']
        with patch('app.collector.json_request',side_effect=TimeoutError()):
            counts,coverage=collect(self.cfg)
        self.assertEqual(counts['new'],1)
        self.assertEqual(counts['failed'],1)
        self.assertEqual(rows(self.cfg,'SELECT priority FROM items')[0]['priority'],10)
        self.assertTrue(any(c['status']=='import_only' for c in coverage))

    def test_run_lock(self):
        with exclusive(self.cfg):
            with self.assertRaises(RuntimeError):
                with exclusive(self.cfg):
                    pass

    def test_simulated_end_to_end(self):
        self.cfg['queries']=['bioinformatics']
        self.cfg['extract_full_text']=False
        self.now=datetime.now(timezone.utc)
        yesterday=(self.now-timedelta(days=1)).isoformat()
        with patch('app.collector.json_request',return_value={'results':[{'title':'R genomics tool',
             'url':'https://example.org/tool','publishedDate':yesterday,'content':'Software genome analysis'}]}),\
             patch('app.analyzer.generate',return_value=analysis()),\
             patch.dict(os.environ,{'EMAIL_ENABLED':'false'}):
            execute(self.cfg,now=self.now,finalize=True,preview=True)
        reports=rows(self.cfg,'SELECT * FROM reports')
        self.assertGreaterEqual(len(reports),1)
        self.assertEqual(rows(self.cfg,'SELECT state FROM items')[0]['state'],'analyzed')
        self.assertTrue(list((Path(self.temp.name)/'outbox').glob('*.eml')))

    def email_env(self):
        return {'SMTP_HOST':'smtp.example.org','SMTP_PORT':'587','SMTP_USER':'user','SMTP_PASSWORD':'test-only',
                'SMTP_FROM':'sender@example.org','EMAIL_TO':'reader@example.org','SMTP_SECURITY':'starttls','EMAIL_ENABLED':'true'}

    def test_email_preview_does_not_send(self):
        r=generate_report(self.cfg,now=self.now)
        with patch('app.mailer.client') as client:
            self.assertEqual(deliver(self.cfg,r,force_preview=True),'preview')
            client.assert_not_called()
        self.assertEqual(rows(self.cfg,'SELECT * FROM deliveries'),[])

    def test_email_requires_verification(self):
        r=generate_report(self.cfg,now=self.now)
        with patch.dict(os.environ,self.email_env()):
            with self.assertRaises(ValueError):
                deliver(self.cfg,r)

    def test_email_no_duplicate_and_uncertain_not_retried(self):
        r=generate_report(self.cfg,now=self.now)
        env=self.email_env()
        (Path(self.temp.name)/'email-verified.json').write_text(json.dumps({'fingerprint':fingerprint(env)}))
        smtp=Mock()
        with patch.dict(os.environ,env),patch('app.mailer.client',return_value=smtp):
            self.assertEqual(deliver(self.cfg,r),'sent')
            self.assertEqual(deliver(self.cfg,r),'sent')
            smtp.send_message.assert_called_once()
            r2=generate_report(self.cfg,now=self.now+timedelta(days=1))
            smtp.send_message.side_effect=TimeoutError()
            self.assertEqual(deliver(self.cfg,r2),'uncertain')
            n=smtp.send_message.call_count
            self.assertEqual(deliver(self.cfg,r2),'uncertain')
            self.assertEqual(smtp.send_message.call_count,n)

    def test_email_connection_failure_retried(self):
        r=generate_report(self.cfg,now=self.now)
        env=self.email_env()
        (Path(self.temp.name)/'email-verified.json').write_text(json.dumps({'fingerprint':fingerprint(env)}))
        with patch.dict(os.environ,env),patch('app.mailer.client',side_effect=ConnectionError()):
            self.assertEqual(deliver(self.cfg,r),'retry')
        with patch.dict(os.environ,env),patch('app.mailer.client',return_value=Mock()):
            self.assertEqual(deliver(self.cfg,r),'sent')

    def test_source_html_escaped(self):
        self.analyzed()
        with connect(self.cfg) as db:
            db.execute('UPDATE items SET title=?',('<script>alert(1)</script>',))
        r=generate_report(self.cfg,now=self.now)
        self.assertNotIn('<script>',Path(r['html_path']).read_text())

    def test_next_schedule_dst(self):
        now=datetime(2026,10,25,23,30,tzinfo=timezone.utc)
        self.assertEqual(next_run(self.cfg,now).hour,1)
        self.assertEqual(next_run(self.cfg,now).day,26)


    def test_dates_enriched_without_reprocessing_unchanged_text(self):
        self.add(date=None)
        state=ingest(self.cfg,{'title':'Same','url':'https://example.org/paper',
             'text':'Genomics research '*30,'published_at':'2026-11-08T09:00:00Z','author':'Researcher'})
        self.assertEqual(state,'duplicates')
        item=rows(self.cfg,'SELECT * FROM items')[0]
        self.assertEqual(item['published_at'],'2026-11-08T09:00:00+00:00')
        self.assertEqual(item['author'],'Researcher')

    def test_restart_during_collection_resumes(self):
        now=datetime.now(timezone.utc)
        with connect(self.cfg) as db:
            db.execute("INSERT INTO runs(started_at,state,counts,coverage) VALUES(?,'collecting','{}','[]')",(now.isoformat(),))
        with patch('app.pipeline.collect',return_value=({'new':0},[])) as collect_mock, patch('app.pipeline.analyze_pending',return_value={}):
            execute(self.cfg,now=now,finalize=True)
            collect_mock.assert_called_once()
        self.assertEqual(rows(self.cfg,'SELECT state FROM runs')[0]['state'],'finished')

    def test_interrupted_analysis_recovers(self):
        self.add()
        with connect(self.cfg) as db:
            db.execute("UPDATE items SET state='processing',attempts=1")
        with patch('app.analyzer.generate',return_value=analysis()):
            analyze_pending(self.cfg)
        self.assertEqual(rows(self.cfg,'SELECT state FROM items')[0]['state'],'analyzed')

    def test_trend_rejects_unknown_evidence(self):
        self.analyzed()
        model={'overview':'Bad','trends':[{'name':'X','evidence':'X','hypothesis':'X','next_steps':'X','source_ids':['invented']}]}
        with patch('app.reporter.generate',return_value=model):
            report=generate_report(self.cfg,'weekly',self.now)
        payload=json.loads(report['payload'])
        self.assertNotIn('trends',payload)
        self.assertTrue(any('ValueError' in w for w in payload['warnings']))

    def test_report_title_uses_local_day(self):
        report=generate_report(self.cfg,now=self.now)
        self.assertIn('2026-11-08',json.loads(report['payload'])['title'])

    def test_rss_cache_304_and_source_failures(self):
        self.cfg['rss']=[{'name':'feed','url':'https://example.org/rss'}]
        with connect(self.cfg) as db:
            db.execute('INSERT INTO feed_cache VALUES(?,?,?)',('https://example.org/rss','tag','date'))
        with patch('app.collector.fetch',return_value=(None,{})) as fetch_mock:
            counts,coverage=collect(self.cfg)
        self.assertEqual(counts['found'],0)
        self.assertEqual(coverage[0]['status'],'unchanged')
        self.assertEqual(fetch_mock.call_args.kwargs['headers']['If-None-Match'],'tag')

    def test_public_network_filter(self):
        from app.http import check_public
        with patch('app.http.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',80))]):
            with self.assertRaises(ValueError):
                check_public('https://example.org/private')
        with self.assertRaises(ValueError):
            check_public('file:///etc/passwd')


    def test_truncated_prompt_is_marked_partial(self):
        self.cfg['article_chars']=20
        item=self.add(text='Complete content '*30)
        with connect(self.cfg) as db:
            db.execute('UPDATE items SET partial=0 WHERE id=?',(item['id'],))
        with patch('app.analyzer.generate',return_value=analysis()):
            analyze_pending(self.cfg)
        self.assertEqual(rows(self.cfg,'SELECT partial FROM items')[0]['partial'],1)

    def test_failed_collection_is_retried_and_counts_preserved(self):
        now=datetime.now(timezone.utc)
        with connect(self.cfg) as db:
            db.execute("INSERT INTO runs(started_at,state,counts,coverage) VALUES(?,'running',?,?)",
                (now.isoformat(),json.dumps({'new':2,'collection_attempts':1}),
                 json.dumps([{'source':'feed','status':'error'}])))
        with patch('app.pipeline.collect',return_value=({'new':1},[{'source':'feed','status':'ok'}])) as collect_mock, patch('app.pipeline.analyze_pending',return_value={}):
            execute(self.cfg,now=now,finalize=True)
            collect_mock.assert_called_once()
        counts=json.loads(rows(self.cfg,'SELECT counts FROM runs')[0]['counts'])
        self.assertEqual(counts['new'],3)
        self.assertEqual(counts['collection_attempts'],2)


if __name__=='__main__':
    unittest.main()
