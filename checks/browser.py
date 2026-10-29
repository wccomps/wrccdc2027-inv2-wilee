"""Requests that look like a browser, not like the scoring engine.

Every check builds its session here so its User-Agent and Accept-Language
vary per run like web-host-check.sh's, instead of announcing
"python-requests/x.y" (CCDC cheese pattern 1: teams serving scoring
traffic differently from everyone else).
"""
import random
import urllib.parse
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:133.0) Gecko/20100101 Firefox/133.0",
]
LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.9,es;q=0.8",
    "en-GB,en;q=0.9,en-US;q=0.8",
    "en-US,en;q=0.9,fr;q=0.8",
    "en-US,en;q=0.9,de;q=0.8,ja;q=0.7",
    "en,en-US;q=0.9",
]


class _Session(requests.Session):
    """Follows a redirect to the vhost's own name (http -> https://daffy.acme.anvil/)
    on the IP already being checked, since the runner can't resolve team names."""

    def get_redirect_target(self, resp):
        location = super().get_redirect_target(resp)
        if not location:
            return location
        loc = urllib.parse.urlsplit(location)
        vhost = resp.request.headers.get("Host", "").split(":")[0].lower()
        if not loc.hostname or loc.hostname.lower() != vhost:
            return location
        ip = urllib.parse.urlsplit(resp.request.url).hostname
        netloc = ip if loc.port is None else f"{ip}:{loc.port}"
        return urllib.parse.urlunsplit((loc.scheme, netloc, loc.path, loc.query, loc.fragment))


def session() -> requests.Session:
    """A requests.Session with a random browser User-Agent and language."""
    s = _Session()
    s.verify = False
    s.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": random.choice(LANGUAGES),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return s
