#!/usr/bin/env python3
"""Custom check for WILEE's Forgejo Actions: gallery deploy and gallery
health cron. The ansible-runner image rebuild isn't checked: it pulls from
the internet and needs the host's Docker in jobs, so it would fail teams for
blocking egress or removing docker.sock from jobs. The app itself isn't requested
here: the healthcheck workflow tests it (on wilee and over the network)
every 15 minutes, and its max age below catches that going stale.

All are checked in parallel; any failure fails the check, and the output
lists every failure first, then the healthy ones, so the cause is visible
from one line.

Per workflow, from Forgejo's Actions API (public repos need no credentials):
  - the newest run (any trigger: push, schedule, manual) must have succeeded.
    Run status is the latest attempt, so a failed run re-run green counts;
  - it must be for the current head of main, so a push whose run never
    happened (runner down, workflow broken) is caught;
  - cron workflows' newest run must be recent, so a cron that stopped firing
    is caught.
A run still queued/running only counts against it once it's older than
GRACE; until then the previous finished run is judged.

TARGET can be any box in the team's /24 (e.g. ROADRUNNER .12): Forgejo is
reached at .121, like check_forgejo_auth.py. USERNAME/PASSWORD are accepted
and ignored.

    python3 check_forgejo_ci.py <TARGET> [USERNAME PASSWORD]
"""

import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import urllib3
import browser

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TIMEOUT = 10
PENDING = {"waiting", "running", "blocked"}
FORGEJO_HOST = "gitea.acme.anvil"
BRANCH = "main"
GRACE = timedelta(minutes=10)
PAGE_SIZE = 50
MAX_PAGES = 20

# (repo, workflow file, max age of newest run or None for push-only)
WORKFLOWS = [
    ("wile.coyote/gallery", "deploy.yml", None),
    ("wile.coyote/gallery", "healthcheck.yml", timedelta(minutes=25)),        # */15 cron
]


class CheckFailed(Exception):
    pass


def defang(text: str) -> str:
    # Commit titles etc. come from blue teams; keep them from smuggling the
    # scoring regex's keyword into a FAILURE line.
    return re.sub(r"correct", lambda m: m.group(0)[0] + "*" + m.group(0)[2:], text, flags=re.I)


def forgejo_ip_for(target: str) -> str:
    parts = target.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3] + ["121"])
    return target


def parse_time(s):
    # Never-started runs report the zero time (1970 or year 1).
    t = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return None if t.year <= 1970 else t


def ago(t, now):
    if t is None:
        return "never"
    m = int((now - t).total_seconds() // 60)
    return f"{m}m ago" if m < 60 else f"{m // 60}h{m % 60:02d}m ago"


def get_json(url, host):
    s = browser.session()
    s.headers["Host"] = host
    s.headers["Accept"] = "application/json"
    try:
        r = s.get(url, timeout=TIMEOUT)
    except Exception as e:
        raise CheckFailed(f"GET {url} (Host {host}) failed: {type(e).__name__}: {e}")
    if r.status_code != 200:
        raise CheckFailed(f"GET {url} (Host {host}) -> HTTP {r.status_code}: {r.text[:120]!r}")
    try:
        return r.json()
    except ValueError:
        raise CheckFailed(f"GET {url} (Host {host}) -> not JSON: {r.text[:120]!r}")


def describe(run, now):
    return (f"#{run['index_in_repo']} {run['status']} {ago(parse_time(run['created']), now)} "
            f"({run['trigger_event']}, {run['commit_sha'][:7]} {run['title']!r}) {run['html_url']}")


def evaluate(runs, head, workflow, grace, now, max_age=None):
    """Judge one workflow's runs; return a summary or raise CheckFailed."""
    candidates = sorted((r for r in runs if r["workflow_id"] == workflow),
                        key=lambda r: r["index_in_repo"], reverse=True)
    if not candidates:
        seen = sorted({r["workflow_id"] for r in runs})
        raise CheckFailed(f"no runs of {workflow} in the last {len(runs)} runs (saw {seen})")

    newest = candidates[0]
    judged = newest
    if newest["status"] in PENDING:
        if now - parse_time(newest["created"]) > grace:
            raise CheckFailed(f"newest run stuck {newest['status']} longer than "
                              f"{int(grace.total_seconds() // 60)}m (runner down/busy?): "
                              f"{describe(newest, now)}")
        judged = next((r for r in candidates if r["status"] not in PENDING), None)
        if judged is None:
            raise CheckFailed(f"only run so far is still {newest['status']}: {describe(newest, now)}")

    if judged["status"] != "success":
        raise CheckFailed(f"newest finished run did not succeed: {describe(judged, now)}")

    if max_age is not None and now - parse_time(newest["created"]) > max_age:
        raise CheckFailed(f"newest run older than {int(max_age.total_seconds() // 60)}m "
                          f"(cron not firing?): {describe(newest, now)}")

    if newest["commit_sha"] != head["id"]:
        pushed = datetime.fromisoformat(head["timestamp"].replace("Z", "+00:00"))
        if now - pushed > grace:
            raise CheckFailed(f"branch head {head['id'][:7]} (pushed {ago(pushed, now)}) has no "
                              f"run; newest is {describe(newest, now)}")

    note = f", max {int(max_age.total_seconds() // 60)}m" if max_age else ""
    return f"{describe(judged, now)}{note}"


def fetch_runs(api, workflow):
    """Runs newest first, paging until one of `workflow` has finished.

    Without ?page Forgejo ignores ?limit and returns every run ever, which
    grows every 15 minutes with the healthcheck cron; with ?page it pages.
    """
    runs = []
    for page in range(1, MAX_PAGES + 1):
        batch = get_json(f"{api}/actions/runs?page={page}&limit={PAGE_SIZE}",
                         FORGEJO_HOST).get("workflow_runs") or []
        runs += batch
        if not batch or any(r["workflow_id"] == workflow and r["status"] not in PENDING
                            for r in batch):
            break
    return runs


def check_workflow(forgejo, spec, branch, grace, now):
    repo, workflow, max_age = spec
    api = f"http://{forgejo}/api/v1/repos/{repo}"
    runs = fetch_runs(api, workflow)
    head = get_json(f"{api}/branches/{branch}", FORGEJO_HOST)["commit"]
    return evaluate(runs, head, workflow, grace, now, max_age)


def check_forgejo_ci(target: str) -> int:
    now = datetime.now(timezone.utc)
    forgejo = forgejo_ip_for(target)
    jobs = {f"{repo}:{wf}": (check_workflow, forgejo, (repo, wf, age), BRANCH, GRACE, now)
            for repo, wf, age in WORKFLOWS}

    ok, bad = [], []
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {name: pool.submit(fn, *a) for name, (fn, *a) in jobs.items()}
        for name, fut in futures.items():
            try:
                ok.append(f"ok {name}: {fut.result()}")
            except CheckFailed as e:
                bad.append(f"FAILED {name}: {e}")
            except Exception as e:
                bad.append(f"FAILED {name}: check error {type(e).__name__}: {e}")

    where = f"Forgejo {forgejo} (Host {FORGEJO_HOST}), branch {BRANCH}"
    if bad:
        print(defang(f"FAILURE: {len(bad)}/{len(jobs)} unhealthy on {where} | "
                     + " | ".join(bad + ok)))
        return 1
    print(f"CORRECT: {len(jobs)}/{len(jobs)} healthy on {where} | " + defang(" | ".join(ok)))
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 4):
        print("Usage: python3 check_forgejo_ci.py <TARGET> [USERNAME PASSWORD]")
        sys.exit(1)
    sys.exit(check_forgejo_ci(sys.argv[1]))
