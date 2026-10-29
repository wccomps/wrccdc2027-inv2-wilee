#!/usr/bin/env python3
"""Custom check for WILEE Roundcube webmail: AD user logs in and lists INBOX.

Roundcube has no public API, so this drives the same requests the browser
makes: login form (CSRF token + session cookie), login POST, the mail page,
then the inbox list over Roundcube's internal AJAX endpoint (JSON). The list
step proves Roundcube can reach IMAP (hMailServer) and its database, not just
render a page. Logs out at the end so checks don't pile up sessions.

    python3 check_roundcube.py <TARGET> <USERNAME> <PASSWORD>
"""

import re
import sys
import urllib3
import browser

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TIMEOUT = 10
HOST = "wilee.acme.anvil"


def defang(text: str) -> str:
    # Keep server-supplied text from smuggling the scoring regex's keyword
    # into a FAILURE line.
    return re.sub(r"correct", lambda m: m.group(0)[0] + "*" + m.group(0)[2:], text, flags=re.I)


def check_roundcube(target: str, username: str, password: str) -> int:
    s = browser.session()
    s.headers["Host"] = HOST
    base = f"http://{target}"
    where = f"{base}/ (Host {HOST})"

    try:
        # 1. Login page: session cookie + CSRF token.
        r = s.get(f"{base}/", timeout=TIMEOUT)
        m = re.search(r'name="_token" value="([^"]+)"', r.text)
        if r.status_code != 200 or not m:
            print(f"FAILURE: Roundcube login page at {where} -> HTTP {r.status_code}, "
                  f"{'no _token field (not Roundcube?)' if r.status_code == 200 else 'not 200'}")
            return 1

        # 2. Log in. Success redirects to the mail task; Roundcube answers a
        # failed login (bad password or IMAP down) with 401.
        r = s.post(f"{base}/?_task=login", timeout=TIMEOUT, data={
            "_token": m.group(1),
            "_task": "login",
            "_action": "login",
            "_timezone": "_default_",
            "_url": "",
            "_user": username,
            "_pass": password,
        })
        if r.status_code == 401:
            print(f"FAILURE: Roundcube at {where} rejected login for {username} (HTTP 401: "
                  f"bad credentials, or Roundcube can't log in to IMAP localhost:143)")
            return 1
        if r.status_code != 200 or ("_task=mail" not in r.url and '"task":"mail"' not in r.text):
            print(f"FAILURE: Roundcube at {where} login for {username} didn't reach the mailbox "
                  f"(HTTP {r.status_code}, ended at {r.url})")
            return 1

        # 3. Mail page carries the token AJAX calls need.
        r = s.get(f"{base}/?_task=mail&_mbox=INBOX", timeout=TIMEOUT)
        m = re.search(r'"request_token":"([^"]+)"', r.text)
        if not m:
            print(f"FAILURE: Roundcube at {where} mail page for {username} has no session "
                  f"(HTTP {r.status_code}, no request_token; session/cookie or DB problem?)")
            return 1
        token = m.group(1)

        try:
            # 4. List the inbox the way the UI does.
            r = s.get(f"{base}/?_task=mail&_action=list&_mbox=INBOX&_remote=1", timeout=TIMEOUT,
                      headers={"X-Roundcube-Request": token, "X-Requested-With": "XMLHttpRequest"})
            try:
                env = r.json().get("env", {})
            except ValueError:
                env = {}
            if "messagecount" not in env:
                print(f"FAILURE: Roundcube at {where} couldn't list INBOX for {username} "
                      f"(HTTP {r.status_code}, no messagecount in list response; IMAP error?)")
                return 1
        finally:
            # 5. Best-effort logout.
            try:
                s.get(f"{base}/?_task=logout&_token={token}", timeout=TIMEOUT)
            except Exception:
                pass

        print(f"CORRECT: Roundcube login and INBOX list succeeded for {username} "
              f"({env['messagecount']} messages)")
        return 0
    except Exception as e:
        print(defang(f"FAILURE: Roundcube at {where}: {type(e).__name__}: {e}"))
        return 1


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 check_roundcube.py <TARGET> <USERNAME> <PASSWORD>")
        sys.exit(1)
    sys.exit(check_roundcube(sys.argv[1], sys.argv[2], sys.argv[3]))
