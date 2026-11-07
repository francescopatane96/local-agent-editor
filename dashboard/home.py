import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import streamlit as st
from app.config import load
from app.database import init_db, rows
from app.scheduler import next_run

st.set_page_config(page_title='Osservatorio biotech',page_icon='🧬',layout='wide')
cfg=load()
init_db(cfg)
st.title('🧬 Osservatorio biotech')
st.caption('La ricerca e le analisi lavorano di notte. Qui trovi risultati, fonti e stato del sistema.')
page=st.sidebar.radio('Navigazione',['Oggi','Archivio','Impostazioni'])


def display_report(report):
    p=json.loads(report['payload'])
    st.subheader(p['title'])
    st.caption(f"Periodo {p['start_local']} → {p['end_local']} · fine esclusa · {p['timezone']}")
    for field,label in [('html_path','Scarica HTML'),('text_path','Scarica testo')]:
        path=Path(report[field])
        if path.exists():
            st.download_button(label,path.read_bytes(),file_name=path.name,key=report['id']+field)
    if not p['items']:
        st.info('Nessuna notizia pertinente analizzata nel periodo. Controlla la copertura qui sotto.')
    from app.reporter import SECTIONS
    for item in p['items']:
        with st.expander(item['title']):
            st.caption(f"{SECTIONS.get(item['section'],item['section'])} · {item['published_at'] or 'Data non verificabile'} · {item['source']} · {item['author'] or ''}")
            st.write(item['analysis']['summary'])
            st.write('Perché conta: '+item['analysis']['reason'])
            st.write('Limiti: '+item['analysis']['limitations'])
            if item['partial']:
                st.caption('Analisi basata su un estratto o testo parziale.')
            st.link_button('Fonte originale',item['url'])
            for r in item['related']:
                st.link_button('Altra fonte: '+r['source'],r['url'])
    if p.get('trends'):
        st.subheader('Trend della settimana')
        st.write(p['trends']['overview'])
        index={i['id']:i for i in p['items']}
        for trend in p['trends']['trends']:
            with st.expander(trend['name']):
                st.write('Evidenze: '+trend['evidence'])
                st.write('Ipotesi: '+trend['hypothesis'])
                st.write('Da approfondire: '+trend['next_steps'])
                for ident in trend['source_ids']:
                    st.link_button(index[ident]['title'],index[ident]['url'])
    with st.expander('Copertura, conteggi e limiti'):
        st.json(p['counts'])
        st.dataframe(p['coverage'],use_container_width=True)
        for warning in p['warnings']:
            st.warning(warning)


if page=='Oggi':
    st.caption('Prossimo avvio: '+next_run(cfg,datetime.now(timezone.utc)).isoformat())
    latest=rows(cfg,'SELECT * FROM runs ORDER BY id DESC LIMIT 1')
    if latest:
        st.write('Ultima esecuzione',latest[0]['started_at'],latest[0]['state'])
        st.json(json.loads(latest[0]['counts'] or '{}'),expanded=False)
    else:
        st.info('In attesa del primo ciclo automatico.')
    deliveries=rows(cfg,'SELECT report_id,state,updated_at,error FROM deliveries ORDER BY updated_at DESC LIMIT 5')
    if deliveries:
        st.dataframe(deliveries,use_container_width=True)
    else:
        st.caption('Nessun invio reale registrato. La modalità iniziale prepara anteprime email.')
    reports=rows(cfg,'SELECT * FROM reports ORDER BY created_at DESC LIMIT 2')
    for report in reports:
        display_report(report)
elif page=='Archivio':
    query=st.text_input('Cerca titolo, testo, azienda o strumento')
    category=st.selectbox('Categoria',['Tutte','tools','research','companies','linkedin'])
    source=st.text_input('Fonte')
    dates=st.date_input('Intervallo di pubblicazione',value=[])
    sql='SELECT * FROM items WHERE 1=1'
    args=[]
    if query:
        sql+=' AND (title LIKE ? OR text LIKE ? OR entities LIKE ?)'
        args += ['%'+query+'%']*3
    if category!='Tutte':
        sql+=' AND category=?'
        args.append(category)
    if source:
        sql+=' AND source LIKE ?'
        args.append('%'+source+'%')
    if len(dates)==2:
        from app.dates import scheduled
        from datetime import timedelta
        sql+=' AND published_at>=? AND published_at<?'
        args += [scheduled(dates[0],'00:00',cfg['timezone']).astimezone(timezone.utc).isoformat(),
                 scheduled(dates[1]+timedelta(days=1),'00:00',cfg['timezone']).astimezone(timezone.utc).isoformat()]
    results=rows(cfg,sql+' ORDER BY collected_at DESC LIMIT 200',args)
    st.caption('Fino a 200 risultati più recenti. Restringi i filtri per esplorare l’archivio.')
    for item in results:
        with st.expander(item['title']):
            st.write(item['source'],item['published_at'] or 'Data sconosciuta',item['state'])
            st.link_button('Apri fonte',item['url'])
            if item['analysis']:
                st.json(json.loads(item['analysis']))
            if item['error']:
                st.warning(item['error'])
    st.subheader('Report salvati')
    reports=rows(cfg,'SELECT * FROM reports ORDER BY end_at DESC LIMIT 100')
    if reports:
        selected=st.selectbox('Report',reports,format_func=lambda r:f"{r['kind']} · {r['start_at']}")
        display_report(selected)
else:
    st.subheader('Configurazione')
    st.write(f"Avvio {cfg['start_time']} · invio {cfg['delivery_time']} · {cfg['timezone']}")
    st.write('Modello locale: '+cfg['model'])
    st.info('Imposta fonti, argomenti e orari qui sotto. Il modello e le credenziali email si configurano nel file .env. Lo scheduler rilegge le preferenze a ogni ciclo.')
    with st.form('preferences'):
        from datetime import time as clock_time
        start=st.time_input('Avvio notturno',value=clock_time.fromisoformat(cfg['start_time']))
        delivery=st.time_input('Invio mattutino',value=clock_time.fromisoformat(cfg['delivery_time']))
        threshold=st.slider('Soglia di interesse',0,10,int(cfg['min_score']))
        queries=st.text_area('Ricerche, una per riga',value='\n'.join(cfg['queries']))
        authors=st.text_area('Autori LinkedIn preferiti, uno per riga',value='\n'.join(cfg['linkedin_authors']))
        feeds=st.text_area('Fonti RSS in formato JSON',value=json.dumps(cfg['rss'],indent=2,ensure_ascii=False),height=250)
        if st.form_submit_button('Salva impostazioni'):
            try:
                import os
                from app.config import ROOT
                from app.database import canonical
                parsed=json.loads(feeds)
                if not isinstance(parsed,list) or any(not isinstance(f,dict) or not f.get('name') or not f.get('url') for f in parsed):
                    raise ValueError('Ogni fonte richiede name e url')
                for feed in parsed:
                    canonical(feed['url'])
                if start>=delivery or delivery.hour==0:
                    raise ValueError('Invio deve seguire avvio, con margine per la chiusura')
                path=Path(os.getenv('OBS_CONFIG',ROOT/'config/observatory.json'))
                settings=json.loads(path.read_text())
                settings.update(start_time=start.strftime('%H:%M'),delivery_time=delivery.strftime('%H:%M'),
                    min_score=threshold,queries=[q.strip() for q in queries.splitlines() if q.strip()],
                    linkedin_authors=[a.strip() for a in authors.splitlines() if a.strip()],rss=parsed)
                temporary=path.with_suffix('.tmp')
                temporary.write_text(json.dumps(settings,ensure_ascii=False,indent=2)+'\n')
                temporary.replace(path)
                st.success('Impostazioni salvate. Saranno lette dal prossimo ciclo.')
            except (ValueError,OSError) as exc:
                st.error(str(exc))
    st.subheader('LinkedIn')
    st.write('Copertura limitata ai post importati. Nessun accesso automatico al feed personale o alle persone seguite.')
    st.caption('Copia gli estratti autorizzati in data/imports/linkedin.json usando config/linkedin.example.json.')
    st.subheader('Email')
    from app.mailer import settings
    s=settings()
    st.write('Invio abilitato' if s['EMAIL_ENABLED'].lower()=='true' else 'Anteprima, nessun invio reale')
    st.caption('Configura .env, esegui email-verify e abilita EMAIL_ENABLED. I file .eml sono conservati in data/outbox.')
