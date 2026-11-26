"""
Part 4: traffic simulator for the analytics dashboard.

It sends REAL HTTP requests to the running web app (python web_app.py), like browsers would, so the
analytics are filled by the same tracking code that records real visits. Every simulated request carries
the header "X-Simulated-Traffic: 1": the app marks those sessions as simulated and the dashboard can
hide them ("Show only real visits").

What a simulated visitor does (random but reproducible with --seed):
  - has its own cookies (visitor id) and one browser/OS/device (User-Agent);
  - has 1-3 sessions (sit-downs); a new session is requested with "X-Simulated-New-Session: 1"
    instead of waiting 30 minutes;
  - in each session follows 1-2 missions: a broad query, then sometimes a refined one
    ("men jeans" -> "men slim jeans blue"), sometimes with a typo, a filter or page 2;
  - clicks results with position bias (rank 1 much more often than rank 10), stays on the product
    page for a random time (sent as dwell time), sometimes opens the original website.

Usage (with the app running on http://127.0.0.1:8088; "localhost" is slow on Windows, see README):
    python project_progress/part_4/simulate_traffic.py --visitors 40
"""
import argparse
import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

USER_AGENTS = [  # (weight, User-Agent)
    (30, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    (12, "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"),
    (10, "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15"),
    (8, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 Edg/120.0"),
    (20, "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"),
    (15, "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"),
    (5, "Mozilla/5.0 (iPad; CPU OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"),
]

# missions: a broad first query and possible refinements (same goal)
MISSIONS = [
    ["men jeans", "men slim jeans blue", "men slim fit jeans black"],
    ["women kurta", "women cotton printed kurta", "women kurta under 700"],
    ["men tshirt", "men black polo tshirt", "men polo tshirt under 500"],
    ["women jacket", "women winter hooded jacket", "women padded jacket"],
    ["men shoes", "men running sports shoes", "men running shoes under 1000"],
    ["men trousers", "men formal trousers", "men formal trousers black"],
    ["women sweatshirt", "women full sleeve sweatshirt cotton", "women hooded sweatshirt"],
    ["women track pants", "women solid track pants", "women track pants cotton"],
    ["men shirt", "men casual shirt cotton", "men checkered shirt slim fit"],
    ["socks", "men ankle socks pack of 3", "women socks"],
]
TYPOS = {"jeans": "jeens", "tshirt": "tshrt", "trousers": "trousres", "women": "womn", "jacket": "jackt"}
NO_RESULT_QUERIES = ["red silk saree", "laptop bag leather", "kids school uniform", "iphone case"]


class Visitor:
    def __init__(self, base, user_agent, rng):
        self.base, self.rng = base.rstrip("/"), rng
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()),
                                                  NoRedirect())
        self.headers = {"User-Agent": user_agent, "X-Simulated-Traffic": "1"}

    def get(self, path, new_session=False):
        headers = dict(self.headers, **({"X-Simulated-New-Session": "1"} if new_session else {}))
        req = urllib.request.Request(self.base + path, headers=headers)
        try:
            with self.opener.open(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:  # redirects (/out) are expected
            return e.read().decode("utf-8", "replace") if e.code >= 400 else ""

    def post_json(self, path, data):
        req = urllib.request.Request(self.base + path, data=json.dumps(data).encode(), method="POST",
                                     headers=dict(self.headers, **{"Content-Type": "application/json"}))
        try:
            self.opener.open(req, timeout=30).read()
        except urllib.error.HTTPError:
            pass

    def search(self, query, extra="", new_session=False):
        html = self.get("/search?" + urllib.parse.urlencode({"q": query}) + extra, new_session=new_session)
        qid = re.search(r'name="qid" value="(\d+)"', html)
        links = re.findall(r'/doc_details\?pid=([A-Z0-9]+)&amp;qid=(\d+)&amp;rank=(\d+)&amp;src=results', html)
        return (qid.group(1) if qid else None), [(pid, int(rank)) for pid, _, rank in dict.fromkeys(links)]

    def click(self, qid, pid, rank):
        html = self.get(f"/doc_details?pid={pid}&qid={qid}&rank={rank}&src=results")
        click_id = re.search(r"click_id: (\d+)", html)
        dwell_s = min(600, self.rng.lognormvariate(3.0, 1.0))  # median ~20 s, long tail
        if click_id and self.rng.random() < 0.85:  # some browsers do not send the beacon
            self.post_json("/track/dwell", {"click_id": int(click_id.group(1)), "ms": round(dwell_s * 1000)})
        if self.rng.random() < 0.2:
            self.get(f"/out?pid={pid}&qid={qid}&rank={rank}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # do not follow /out to the real website
        return None


def run_session(v: Visitor, rng, first):
    new_session = not first
    if rng.random() < 0.6:
        v.get("/", new_session=new_session)
        new_session = False
    for _ in range(rng.choice([1, 1, 2])):  # missions in this sit-down
        if rng.random() < 0.08:
            query_list = [rng.choice(NO_RESULT_QUERIES)]
        else:
            mission = rng.choice(MISSIONS)
            query_list = [mission[0]] + ([rng.choice(mission[1:])] if rng.random() < 0.6 else [])
        for query in query_list:
            if rng.random() < 0.12:
                for word, typo in TYPOS.items():
                    query = query.replace(word, typo)
            extra = ""
            if rng.random() < 0.25:
                extra = rng.choice(["&stock=1", "&sort=price_asc", "&min_rating=4", "&max_price=800"])
            qid, results = v.search(query, extra, new_session=new_session)
            new_session = False
            if not results:
                continue
            if rng.random() < 0.15:  # look at page 2
                v.get("/search?" + urllib.parse.urlencode({"q": query, "qid": qid, "page": 2}))
            # position bias: probability of clicking rank r ~ 1 / r
            n_clicks = rng.choice([0, 1, 1, 1, 2, 2, 3])
            weights = [1 / r for _, r in results]
            for pid, rank in rng.choices(results, weights=weights, k=n_clicks):
                v.click(qid, pid, rank)
                time.sleep(0.01)


def main():
    parser = argparse.ArgumentParser(description="Send simulated visits to the IRWA web app.")
    parser.add_argument("--base", default="http://127.0.0.1:8088", help="URL of the running app")
    parser.add_argument("--visitors", type=int, default=40)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    rng = random.Random(args.seed)
    weights, agents = zip(*USER_AGENTS)
    start = time.time()
    for i in range(args.visitors):
        v = Visitor(args.base, rng.choices(agents, weights=weights)[0], rng)
        for s in range(rng.choice([1, 1, 1, 2, 2, 3])):
            run_session(v, rng, first=(s == 0))
        print(f"\rVisitor {i + 1}/{args.visitors}", end="", flush=True)
    print(f"\nDone in {time.time() - start:.0f} s. Open {args.base}/dashboard")


if __name__ == "__main__":
    main()
