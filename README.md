# Osservatorio personale biotech

Ricerca RSS e SearXNG, selezione con Ollama, archivio SQLite, report quotidiani e settimanali in italiano, email SMTP e dashboard Streamlit. Tutte le analisi si eseguono sul modello locale. Le ricerche e i download contattano Internet, gli invii contattano il servizio email configurato.

## Prima installazione

Prerequisiti: Docker con Compose, Python 3 per la configurazione iniziale, Ollama raggiungibile dal container e un modello già scaricato. Il modello iniziale è `qwen3.5:4b`, modificabile in `.env`. Memoria e durata dipendono da hardware, modello e contesto.

```bash
python scripts/setup.py
# Modifica .env per indicare OLLAMA_URL e OLLAMA_MODEL
# Scarica sul computer che ospita Ollama il modello scelto
ollama pull qwen3.5:4b
docker compose up -d --build
```

Apri http://localhost:8501. I servizi web sono pubblicati solo su localhost. La dashboard non ha autenticazione e va mantenuta locale. Per accesso remoto usa un tunnel autenticato.

Il setup crea una chiave SearXNG casuale senza sovrascrivere configurazioni esistenti. Se un vecchio container occupa le porte 8080 o 8501, arrestalo prima di avviare il nuovo stack.

Su Linux `host.docker.internal` punta al gateway host, non al suo loopback. Ollama deve ascoltare su un indirizzo raggiungibile dalla rete Docker. Configura il bind e il firewall per consentire esclusivamente la rete necessaria, oppure usa un endpoint Ollama già accessibile. Non pubblicare Ollama su Internet. Su Docker Desktop verifica ugualmente la raggiungibilità.

`LOCAL_UID` e `LOCAL_GID` vengono impostati dal setup per consentire ai container di scrivere nel volume `data`. Se i dati preesistenti appartengono a un altro utente, adegua la proprietà prima di avviare. Il Dockerfile usa un utente non privilegiato anche senza Compose.

## Migrazione dalla versione precedente: prima preserva i dati

La vecchia repository traccia `data/news.db` e report generati. Passare a un branch che rimuove questi file può rimuoverli dal working tree. Fai un backup esterno PRIMA del checkout o del merge. Non usare `git reset --hard` sui dati operativi.

1. Arresta i vecchi container per evitare scritture durante il trasferimento.
2. Copia l'intera directory `data` in una directory esterna alla repository, con database e report. Se scarichi preventivamente `scripts/backup_legacy.py` dalla pull request, puoi eseguirlo dalla radice della vecchia checkout con una destinazione nuova esterna. Lo script usa l'API SQLite backup.
3. Passa al nuovo branch soltanto dopo aver verificato il backup.
4. Ripristina la directory `data` dal backup, poi esegui setup e avvio.

All'avvio la migrazione crea inoltre `news.pre-observatory.bak`, mantiene la tabella originale `articles` e importa i record nel nuovo schema `items`. Le vecchie analisi restano in `articles`, mentre i contenuti vengono riclassificati rispetto al nuovo ambito biotech. Le migrazioni sono idempotenti e protette da lock. URL legacy non validi restano nella tabella originale e nel backup.

Database, report, email, backup, import e credenziali sono ora esclusi da Git. La cronologia non viene riscritta. La vecchia chiave SearXNG pubblicata deve essere considerata esposta: sostituiscila con quella generata dal setup anche nelle altre installazioni che la utilizzano.

## Funzionamento automatico

Tutti gli orari sono in `Europe/Rome`, con ora legale gestita mediante `zoneinfo`.

| Momento | Attività |
| --- | --- |
| 01:00 | Raccolta RSS, ricerche web, import LinkedIn e inizio analisi |
| Durante la notte | Lotti in ordine di raccolta, recupero dei tentativi falliti con attesa crescente |
| 06:50 | Chiusura delle analisi e salvataggio del report quotidiano |
| Lunedì, alla chiusura | Salvataggio del report della settimana precedente e sintesi dei trend |
| 07:00 | Invio dei report, se email configurata, verificata e abilitata |

Lo scheduler controlla ogni minuto. L'obiettivo è consegnare intorno alle 07:00, ma disponibilità di rete, hardware, server SMTP e riavvii non permettono una garanzia assoluta dell'orario. I timeout limitano il lavoro, le analisi residue passano al ciclo successivo. Se il computer è spento alle 07:00, il report viene preparato e inviato dopo il riavvio, con copertura parziale dichiarata. Non vengono inventate edizioni complete per giorni interamente persi.

La pipeline usa un lock di processo condiviso tra comandi e scheduler. Il sistema riprende una raccolta interrotta e rimette in coda analisi interrotte. Le attività sono persistite in SQLite. Non eseguire copie concorrenti dello stack con database o directory di lock diversi sulla stessa raccolta.

Le finestre sono `[inizio, fine)`: giorno precedente da mezzanotte a mezzanotte, settimana precedente da lunedì a lunedì. Le giornate del cambio dell'ora possono durare 23 o 25 ore. Data di raccolta, pubblicazione e aggiornamento restano separate. Le date senza fuso usano il fuso dichiarato dalla fonte, altrimenti UTC. Non vengono dedotte date dai titoli o dai risultati del modello.

Gli articoli vecchi scoperti successivamente compaiono nella sezione ritardi. Quelli senza data verificabile compaiono in una sezione separata, una sola volta nei quotidiani. Gli elementi non analizzati o falliti sono dichiarati nella copertura. I report sono snapshot immutabili identificati per periodo, così un riavvio non genera una seconda edizione.

## Fonti, selezione e limiti

Modifica le preferenze nella pagina Impostazioni oppure in `config/observatory.json`. Lo scheduler rilegge la configurazione a ogni ciclo. RSS iniziali: bioRxiv Bioinformatics, bioRxiv Bioengineering e Nature Biotechnology. Le query coprono startup, AI biologica, R, Python, Bioconductor, biologia sintetica e applicazioni industriali. Puoi aggiungere feed ufficiali di aziende o progetti specifici. Gli endpoint live vanno verificati sulla macchina di destinazione.

I feed bioRxiv contengono una finestra limitata di post recenti, quindi una sola raccolta quotidiana può non vedere tutti gli elementi nei giorni molto prolifici. SearXNG integra la scoperta ma non garantisce copertura esaustiva né date per ogni risultato. Stati delle fonti e problemi di estrazione sono visibili nei report. Un estratto resta dichiarato parziale. Non vengono aggirati paywall o autenticazione.

Deduplicazione: URL normalizzati senza parametri di tracking, contenuto normalizzato identico, raggruppamento conservativo per titolo identico. Tutti gli URL restano nell'archivio e nelle fonti correlate. Eventi descritti con titoli e testi diversi possono restare separati. Non viene dichiarata una deduplicazione semantica perfetta.

Le risposte Ollama devono rispettare uno schema JSON validato. Punteggio iniziale: pertinenza 40%, novità 20%, evidenze 20%, utilità 20%, soglia 6/10. Valori e soglia sono configurabili. La coda è FIFO per evitare che le nuove notizie blocchino quelle vecchie. La priorità della fonte e degli autori LinkedIn risolve parità nel ranking. Un modello locale può comunque sbagliare: sintesi, ipotesi e applicazioni richiedono verifica nelle fonti citate.

La sintesi settimanale usa al massimo 40 eventi selezionati, con conteggio esplicito, fonti referenziate per ID e confronto con il precedente report disponibile. Il confronto riguarda il campione osservato, non la crescita di un mercato. Se il modello fallisce, l'archivio conserva un report parziale con la limitazione.

L'estrazione è limitata a pagine pubbliche HTTP(S), con verifica di indirizzi e redirect e limite di dimensione. Mantieni la macchina isolata da servizi sensibili: questi controlli applicativi non sostituiscono un filtro di rete contro ogni scenario di DNS rebinding.

## LinkedIn: import autorizzati, non feed personale

Non è configurato accesso al tuo account LinkedIn. La ricerca delle integrazioni disponibili non ha individuato un connettore per leggere il feed personale e le persone seguite. La documentazione LinkedIn indica che `r_member_social` è un permesso chiuso. Non si presume un accesso disponibile e non viene eseguito scraping di LinkedIn.

1. Copia `config/linkedin.example.json` in `data/imports/linkedin.json`.
2. Sostituisci l'esempio con post, URL, autori e testi che sei autorizzato a utilizzare.
3. Inserisci date reali ISO 8601 oppure `null`, mai la data di import al posto di quella originale.
4. Mantieni `partial: true` per estratti. Imposta `false` solo per testo completo.
5. Elenca gli autori preferiti in `linkedin_authors`.

Il file è importato automaticamente durante la raccolta. Non va riscritto ogni giorno se non ci sono nuovi post. Gli import non garantiscono la copertura di tutti i post degli autori preferiti. La classificazione valuta pertinenza, novità, qualità delle evidenze e utilità, senza usare like o follower. Un eventuale futuro connettore autorizzato potrà produrre lo stesso formato.

Riferimenti: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview e https://connect.biorxiv.org/.

## Email

L'impostazione iniziale `EMAIL_ENABLED=false` non invia messaggi. Sono preparati file `.eml` in `data/outbox`, con versione HTML e alternativa testuale.

Configura in `.env` un solo destinatario, mittente e servizio SMTP:

```dotenv
SMTP_HOST=smtp.example.org
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=nome-utente
SMTP_PASSWORD=password-app-del-provider
SMTP_FROM=mittente@example.org
EMAIL_TO=destinatario@example.org
EMAIL_ENABLED=false
```

Gli indirizzi qui sono esempi, non destinatari configurati. Usa una password applicativa quando richiesta dal provider. È obbligatorio TLS con verifica dei certificati, via STARTTLS o SSL.

```bash
# Verifica connessione e autenticazione, senza inviare alcun messaggio
docker compose run --rm ai-scheduler python -m app.main email-verify
# Dopo aver controllato EMAIL_TO, cambia EMAIL_ENABLED=true in .env
docker compose up -d --force-recreate ai-scheduler
```

La verifica valida formato dell'indirizzo, TLS, connessione e autenticazione, non la proprietà della casella né la consegna finale. La verifica è legata alla configurazione e va ripetuta se cambi server, credenziali, mittente o destinatario. Nessun segreto viene salvato nel database o mostrato nella dashboard.

Una tabella persistente impedisce di rispedire report già inviati. Errori di connessione precedenti all'invio vengono ritentati fino al limite configurato. Un'interruzione durante l'invio SMTP può lasciare un esito `uncertain` o `sending`: in quel caso non si ritenta automaticamente, perché SMTP non garantisce la consegna esattamente una volta. Controlla casella e log del provider prima di qualsiasi recupero manuale. I report e le anteprime restano disponibili anche se l'invio fallisce.

## Comandi e diagnostica

```bash
docker compose logs -f ai-scheduler
# Esecuzione manuale di recupero: un lotto con budget, chiusura immediata e anteprima email
docker compose run --rm ai-scheduler python -m app.main run
# Rimette in coda soltanto analisi che hanno esaurito i tentativi
docker compose run --rm ai-scheduler python -m app.main retry-failed
```

Il comando `run` finalizza uno snapshot del periodo corrente e non invia email, ma lo scheduler potrà inviarlo all'orario previsto se l'invio è abilitato. Usalo su dati di prova per la prima verifica, oppure quando vuoi chiudere intenzionalmente il report prima dell'orario automatico.

Senza Docker, il nucleo usa Python 3.12 standard library. Installa `requirements.txt` per dashboard ed estrazione. Esporta le variabili d'ambiente, perché l'esecuzione Python diretta non carica `.env` automaticamente. Imposta `DATA_DIR`, `OLLAMA_URL` e `SEARXNG_URL` adatti al computer.

## Test e CI

```bash
python -m unittest discover -s tests -v
python -m compileall -q app dashboard
```

La suite usa database temporanei e servizi simulati. Copre migrazione, deduplicazione, RSS/Atom, confini e ora legale, schemi AI, FIFO, recupero, report, riferimenti, lock ed email. Non richiede credenziali, non invia messaggi e non chiama Ollama.

GitHub Actions esegue test, parsing Compose, build Docker da checkout pulito e inizializzazione nel container. Docker non è disponibile nell'ambiente di sviluppo dell'agente: l'esito reale della build va verificato nel workflow. Modello locale, prestazioni hardware, disponibilità delle fonti e recapito email richiedono una prova sull'installazione finale.

L'immagine SearXNG predefinita usa `latest`. Per installazioni riproducibili imposta `SEARXNG_IMAGE` a un digest verificato del tuo ambiente. Le dipendenze Python dirette sono fissate, quelle transitive non costituiscono un lock completo.
