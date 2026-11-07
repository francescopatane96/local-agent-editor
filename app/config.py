import json
import os
from pathlib import Path
from datetime import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def load():
    path = Path(os.getenv('OBS_CONFIG', ROOT / 'config/observatory.json'))
    cfg = json.loads(path.read_text())
    cfg['data_dir'] = str(Path(os.getenv('DATA_DIR', ROOT / 'data')).resolve())
    cfg['db_path'] = str(Path(os.getenv('DB_PATH', Path(cfg['data_dir']) / 'news.db')))
    cfg['ollama_url'] = os.getenv('OLLAMA_URL', 'http://host.docker.internal:11434').rstrip('/')
    cfg['model'] = os.getenv('OLLAMA_MODEL', 'qwen3.5:4b')
    cfg['searxng_url'] = os.getenv('SEARXNG_URL', 'http://searxng:8080').rstrip('/')
    ZoneInfo(cfg['timezone'])
    for key in ('start_time', 'delivery_time'):
        time.fromisoformat(cfg[key])
    if cfg['start_time'] >= cfg['delivery_time']:
        raise ValueError('start_time deve precedere delivery_time')
    if not 0 <= cfg['min_score'] <= 10:
        raise ValueError('min_score deve essere tra 0 e 10')
    if set(cfg['weights']) != {'relevance','novelty','evidence','utility'} or any(v < 0 for v in cfg['weights'].values()) or sum(cfg['weights'].values()) <= 0:
        raise ValueError('Pesi di selezione non validi')
    for key in ('max_attempts', 'max_analysis_per_run', 'request_timeout', 'max_per_section'):
        if cfg[key] <= 0:
            raise ValueError(f'{key} deve essere positivo')
    return cfg
