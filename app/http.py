"""Bounded HTTP reads. Only configured service endpoints may use private networks."""
import ipaddress
import json
import socket
import time
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit


def check_public(url):
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('URL non consentito')
    if p.port not in (None,80,443):
        raise ValueError('Porta pubblica non consentita')
    addresses = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError('Indirizzo privato o riservato non consentito')


class CheckedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_public(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, *, data=None, headers=None, timeout=30, public=True, max_bytes=4_000_000, retries=1):
    if public:
        check_public(url)
    request_headers = {'User-Agent':'BiotechObservatory/2.0', **(headers or {})}
    payload = None
    if data is not None:
        payload = json.dumps(data).encode()
        request_headers['Content-Type'] = 'application/json'
    for attempt in range(retries+1):
        try:
            opener = build_opener(CheckedRedirect()) if public else build_opener()
            with opener.open(Request(url, data=payload, headers=request_headers), timeout=timeout) as response:
                body = response.read(max_bytes+1)
                if len(body) > max_bytes:
                    raise ValueError('Risposta troppo grande')
                return body, dict(response.headers)
        except HTTPError as exc:
            if exc.code == 304:
                return None, dict(exc.headers)
            if exc.code not in (429,500,502,503,504) or attempt == retries:
                raise
        except (URLError, TimeoutError):
            if attempt == retries:
                raise
        time.sleep(min(2**attempt, 4))


def json_request(url, **kwargs):
    body, _ = fetch(url, **kwargs)
    return json.loads(body)
