"""Small, independently testable dashboard data helpers."""
from datetime import datetime, timezone
import math
from zoneinfo import ZoneInfo


def local_time(zone, now=None):
    now = now or datetime.now(timezone.utc)
    return now.astimezone(ZoneInfo(zone)).strftime("%I:%M %p")


def parse_frankfurter(payload):
    rates = payload["rates"]
    usd_inr, usd_jpy = float(rates["INR"]), float(rates["JPY"])
    if not math.isfinite(usd_inr) or not math.isfinite(usd_jpy) or usd_inr <= 0 or usd_jpy <= 0:
        raise ValueError("Invalid FX rates")
    return {"INR": usd_inr, "JPY": usd_jpy, "INR_per_JPY": usd_inr / usd_jpy}, payload["date"]


def validate_cached_rates(rates):
    """Return normalized cached rates, or None when the cache is malformed."""
    try:
        inr, jpy = float(rates["INR"]), float(rates["JPY"])
        inr_per_jpy = float(rates["INR_per_JPY"])
        if (all(math.isfinite(value) and value > 0 for value in (inr, jpy, inr_per_jpy))
                and math.isclose(inr_per_jpy, inr / jpy, rel_tol=1e-6, abs_tol=1e-9)):
            return {"INR": inr, "JPY": jpy, "INR_per_JPY": inr_per_jpy}
    except (KeyError, TypeError, ValueError):
        pass
    return None


class CoalescingWorkQueue:
    """FIFO queue retaining at most one pending request per category."""
    def __init__(self):
        self._items = []
        self._categories = set()

    def enqueue(self, category, operation, callback):
        if category in self._categories:
            return False
        self._categories.add(category)
        self._items.append((category, operation, callback))
        return True

    def pop(self):
        category, operation, callback = self._items.pop(0)
        self._categories.remove(category)
        return category, operation, callback

    def __bool__(self):
        return bool(self._items)


def fetch_fx():
    import json
    from urllib.request import urlopen
    with urlopen("https://api.frankfurter.app/latest?from=USD&to=INR,JPY", timeout=10) as response:
        return parse_frankfurter(json.loads(response.read().decode("utf-8")))
