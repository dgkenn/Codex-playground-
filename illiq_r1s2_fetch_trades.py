import json, time, random, urllib.request, urllib.error, os, sys

CACHE = os.path.dirname(os.path.abspath(__file__)) + "/cache"

def fetch(url, retries=6):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'research-bot/1.0'})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = (2 ** attempt) + random.uniform(0, 1)
                print(f"429, backoff {wait:.1f}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"err {e}, backoff {wait:.1f}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"failed after {retries} retries: {url}")

def fetch_all_trades(ticker):
    base = "https://api.elections.kalshi.com/trade-api/v2/markets/trades"
    all_trades = []
    cursor = ""
    while True:
        url = f"{base}?ticker={ticker}&limit=200"
        if cursor:
            url += f"&cursor={cursor}"
        d = fetch(url)
        trades = d.get('trades', [])
        all_trades.extend(trades)
        cursor = d.get('cursor', '')
        time.sleep(0.15 + random.uniform(0, 0.15))
        if not cursor or not trades:
            break
    return all_trades

def load_market_list():
    markets = []
    # fed: single accessible event
    d = json.load(open(f"{CACHE}/markets_fed_KXFEDMENTION-26JUN.json"))
    for m in d['markets']:
        markets.append(m)
    # hannity: two accessible events
    for f in ["markets_han_KXHANNITYMENTION-26MAY21.json", "markets_han_KXHANNITYMENTION-26MAY19.json"]:
        d = json.load(open(f"{CACHE}/{f}"))
        for m in d['markets']:
            markets.append(m)
    return markets

if __name__ == "__main__":
    markets = load_market_list()
    print(f"total markets to fetch: {len(markets)}", file=sys.stderr)
    out = {}
    for i, m in enumerate(markets):
        tk = m['ticker']
        fp = f"{CACHE}/trades_{tk}.json"
        if os.path.exists(fp):
            trades = json.load(open(fp))
        else:
            trades = fetch_all_trades(tk)
            json.dump(trades, open(fp, 'w'))
        out[tk] = len(trades)
        print(i, tk, len(trades), file=sys.stderr)
    json.dump(out, open(f"{CACHE}/trade_counts.json", 'w'))
    print("done", file=sys.stderr)
