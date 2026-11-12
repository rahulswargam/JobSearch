"""Minimal Apify API client (standard library only).

Runs an actor with a hard spending cap, waits for it, and reads its dataset.
Docs: https://docs.apify.com/api/v2
"""
import json
import ssl
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.apify.com/v2"
TERMINAL = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}


def _tls():
    """Use certifi's up-to-date certificates when installed (python.org builds on macOS ship without any)."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


TLS = _tls()


class ApifyError(Exception):
    def __init__(self, message, status=None, kind=None):
        super().__init__(message)
        self.status, self.kind = status, kind


class Apify:
    def __init__(self, token, timeout=60):
        self.token = token.strip()
        self.timeout = timeout

    def _req(self, method, path, params=None, body=None, timeout=None):
        url = API + path + ("?" + urlencode(params) if params else "")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(url, data=data, method=method, headers={
            "Authorization": f"Bearer {self.token}", "Content-Type": "application/json", "User-Agent": "jobsearch-cli/1.0"})
        try:
            with urlopen(req, timeout=timeout or self.timeout, context=TLS) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            try:
                err = json.loads(detail).get("error", {})
                msg, kind = err.get("message") or detail, err.get("type")
            except (ValueError, AttributeError):
                msg, kind = detail[:300], None
            if e.code == 401:
                msg = "The Apify API token was rejected. Check it at https://console.apify.com/settings/integrations"
            raise ApifyError(f"Apify {e.code}: {msg}", status=e.code, kind=kind) from None
        except URLError as e:
            raise ApifyError(f"Can't reach Apify ({e.reason}). Check your internet connection.") from None

    # -------------------------------------------------------------- account
    def me(self):
        return self._req("GET", "/users/me")["data"]

    def account(self):
        """Who the key belongs to and how much credit is left this billing cycle.

        Raises ApifyError (status 401) for a bad key. Credit fields are None when Apify doesn't report them."""
        me = self.me()
        acct = {"username": me.get("username") or "", "plan": str((me.get("plan") or {}).get("id") or "").upper(),
                "used": None, "limit": None, "left": None, "cycle_start": None, "cycle_end": None}
        try:
            d = self._req("GET", "/users/me/limits")["data"]
            used, limit = d["current"]["monthlyUsageUsd"], d["limits"]["maxMonthlyUsageUsd"]
            acct.update(used=float(used), limit=float(limit), left=max(0.0, float(limit) - float(used)),
                        cycle_start=(d.get("monthlyUsageCycle") or {}).get("startAt"),
                        cycle_end=(d.get("monthlyUsageCycle") or {}).get("endAt"))
        except (ApifyError, KeyError, TypeError, ValueError):
            pass
        return acct

    def usage_by_actor(self, since=None):
        """{actor id: {"runs": n, "usd": x}} from your run history since an ISO time (the cycle start)."""
        params = {"desc": 1, "limit": 1000}
        if since:
            params["startedAfter"] = since
        try:
            items = self._req("GET", "/actor-runs", params)["data"]["items"]
        except (ApifyError, KeyError, TypeError):
            return {}
        out = {}
        for r in items:
            if since and str(r.get("startedAt") or since) < since:
                continue
            a = out.setdefault(r.get("actId"), {"runs": 0, "usd": 0.0})
            a["runs"] += 1
            a["usd"] += float(r.get("usageTotalUsd") or 0)
        return out

    # -------------------------------------------------------------- runs
    def start(self, actor, run_input, max_items=None, max_charge_usd=None, timeout_secs=None, memory_mb=None):
        params = {}
        if max_items:
            params["maxItems"] = int(max_items)
        if max_charge_usd:
            params["maxTotalChargeUsd"] = f"{max_charge_usd:.4f}"
        if timeout_secs:
            params["timeout"] = int(timeout_secs)
        if memory_mb:
            params["memory"] = int(memory_mb)
        return self._req("POST", f"/acts/{actor.replace('/', '~')}/runs", params, run_input)["data"]

    def get_run(self, run_id, wait=0):
        return self._req("GET", f"/actor-runs/{run_id}", {"waitForFinish": int(wait)} if wait else None,
                         timeout=max(self.timeout, wait + 15))["data"]

    def abort(self, run_id):
        try:
            return self._req("POST", f"/actor-runs/{run_id}/abort")["data"]
        except ApifyError:
            return None

    def items(self, dataset_id, limit=None):
        out, offset, page = [], 0, 1000
        while True:
            n = page if limit is None else min(page, limit - len(out))
            if n <= 0:
                break
            batch = self._req("GET", f"/datasets/{dataset_id}/items",
                              {"clean": "true", "format": "json", "offset": offset, "limit": n}) or []
            out.extend(batch)
            offset += len(batch)
            if len(batch) < n:
                break
        return out

    def run(self, actor, run_input, *, max_items=None, max_charge_usd=None, timeout_secs=600, memory_mb=None,
            on_status=None, retries_on_busy=6):
        """Start, wait, fetch. Returns (items, run). Partial results are returned for aborted/timed-out runs."""
        attempt = 0
        while True:
            try:
                run = self.start(actor, run_input, max_items, max_charge_usd, timeout_secs, memory_mb)
                break
            except ApifyError as e:
                busy = e.status in (402, 429) and ("memory" in str(e).lower() or "concurrent" in str(e).lower() or e.status == 429)
                if busy and attempt < retries_on_busy:
                    attempt += 1
                    if on_status:
                        on_status("waiting for account memory to free up")
                    time.sleep(10 * attempt)
                    continue
                raise
        deadline = time.time() + timeout_secs + 120
        last = None
        while run.get("status") not in TERMINAL:
            if time.time() > deadline:
                self.abort(run["id"])
                run = self.get_run(run["id"])
                break
            if on_status and run.get("status") != last:
                on_status(run.get("status", "").lower())
                last = run.get("status")
            run = self.get_run(run["id"], wait=30)
        dataset = run.get("defaultDatasetId")
        items = self.items(dataset, limit=max_items) if dataset else []
        return items, run


def run_cost(run):
    """Best estimate of what a run cost you, in USD."""
    events = run.get("chargedEventCounts") or {}
    pricing = (run.get("pricingInfo") or {}).get("pricingPerEvent", {}).get("actorChargeEvents", {})
    total = 0.0
    for name, count in events.items():
        ev = pricing.get(name) or {}
        price = ev.get("eventPriceUsd")
        if price is None:
            tiers = ev.get("eventTieredPricingUsd") or {}
            price = (tiers.get("FREE") or next(iter(tiers.values()), {})).get("tieredEventPriceUsd", 0)
        total += (price or 0) * (count or 0)
    if total:
        return total
    return float(run.get("usageTotalUsd") or 0)
