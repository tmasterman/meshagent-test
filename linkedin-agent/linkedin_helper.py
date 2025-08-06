"""
linkedin_client.py  –  Personal-feed helper (Posts API)   2025-07

Env vars required
-----------------
LINKEDIN_ACCESS_TOKEN   token with scopes: w_member_social  openid  profile
Optional
LINKEDIN_VERSION_LOCK   pin a YYYYMM header instead of probing
LOG_LEVEL               e.g. DEBUG / INFO  (default INFO)

pip install requests python-dateutil
"""
from __future__ import annotations

import json, os, urllib.parse, logging
from datetime import datetime, timezone
from typing import Final

import requests
from dateutil.relativedelta import relativedelta   # tiny dep
from opentelemetry import trace


# ─────────────────────────────  logging  ─────────────────────────────
log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# ─────────────────────────────  endpoints  ───────────────────────────
POSTS_ENDPOINT:    Final[str] = "https://api.linkedin.com/rest/posts"
USERINFO_ENDPOINT: Final[str] = "https://api.linkedin.com/v2/userinfo"

_VERSION_CACHE: str | None = None          # module-wide cache (first good month)

# ─────────────────────────────  custom errors  ───────────────────────
class LinkedInError(RuntimeError): ...
class LinkedInVersionError(LinkedInError): ...
class ExpiredTokenError(LinkedInError): ...

# ─────────────────────────────  client  ──────────────────────────────
class LinkedInClient:
    MAX_LOOKBACK   = 3               # months to probe downward
    DEFAULT_VIS    = "PUBLIC"

    def __init__(self,
                 access_token: str | None = None,
                 start_version: str | None = None,
                 session: requests.Session | None = None) -> None:

        self.token = access_token or os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        if not self.token:
            raise LinkedInError("Set LINKEDIN_ACCESS_TOKEN or pass access_token=")

        self._session = session or requests.Session()

        # ── build header probe list ──────────────────────────────────
        env_lock = os.getenv("LINKEDIN_VERSION_LOCK")
        if env_lock:
            self._versions = [env_lock]
        else:
            first = start_version or datetime.now(timezone.utc).strftime("%Y%m")
            base  = datetime.strptime(first, "%Y%m")
            self._versions = [
                (base - relativedelta(months=i)).strftime("%Y%m")
                for i in range(self.MAX_LOOKBACK + 1)
            ]

        global _VERSION_CACHE
        if _VERSION_CACHE:
            self._versions.insert(0, _VERSION_CACHE)
            self._versions = list(dict.fromkeys(self._versions))

        self.version: str | None = None  # filled after first success

        # ── profile discovery ────────────────────────────────────────
        profile = self._fetch_profile()
        self.person_id  = profile["sub"]
        self.author_urn = f"urn:li:person:{self.person_id}"
        self.first_name = profile.get("given_name", "")
        self.last_name  = profile.get("family_name", "")

    # ─────────────────────────────  public API  ──────────────────────
    def preview(self, text: str) -> None:
        bar = "-" * 40
        log.info("\n%s\nLINKEDIN PREVIEW\n%s\n%s\n%s", bar, bar, text, bar)

    def post(self, text: str,
             visibility: str | None = None,
             dry_run: bool = False) -> str:
        payload = {
            "author": self.author_urn,
            "commentary": text,
            "visibility": visibility or self.DEFAULT_VIS,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": []
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False
        }
        if dry_run:
            log.info(json.dumps(payload, indent=2))
            return "dry_run"

        r = self._request("POST", POSTS_ENDPOINT, json=payload)
        r.raise_for_status()
        return r.headers["x-restli-id"]

    def try_read_latest(self, count: int = 1):
        params = {
            "q": "author",
            "author": urllib.parse.quote(self.author_urn, safe=""),
            "count": str(count),
            "sortBy": "LAST_MODIFIED",
        }
        r = self._request("GET", POSTS_ENDPOINT,
                          params=params,
                          headers={"Content-Type": None})
        if r.status_code == 403:
            log.warning("403 – token lacks r_member_social; read scope restricted.")
            return None
        r.raise_for_status()
        return r.json().get("elements", [])

    # ─────────────────────────────  internals  ───────────────────────
    def _fetch_profile(self) -> dict:
        r = self._request("GET", USERINFO_ENDPOINT)
        r.raise_for_status()
        return r.json()

    def _request(self, method: str, url: str, **kwargs) -> requests.Response:
        last_ex: Exception | None = None

        for ver in self._versions:
            # build headers FIRST  ──────────────────────────────
            hdrs = {k: v for k, v in (kwargs.pop("headers", {}) or {}).items()
                    if v is not None}
            hdrs.setdefault("Authorization", f"Bearer {self.token}")
            hdrs.setdefault("LinkedIn-Version", ver)
            hdrs.setdefault("X-Restli-Protocol-Version", "2.0.0")

            # now record the span & make the request  ───────────
            with tracer.start_as_current_span(
                "linkedin.http",
                attributes={
                    "http.method": method,
                    "url": url,
                    "linkedin.version": ver,
                },
            ):
                try:
                    resp = self._session.request(
                        method, url, headers=hdrs, timeout=30, **kwargs
                    )
                except requests.RequestException as ex:
                    last_ex = ex
                    continue

            # token expiry shortcut
            if resp.status_code == 401 and "LX401_Expired_Token" in resp.text:
                raise ExpiredTokenError("LinkedIn access token expired")

            # bad LinkedIn-Version?  (400 / 404 / 426 + message)
            bad_ver = resp.status_code in (400, 404, 426) \
                      and "version" in resp.text.lower()
            if bad_ver:
                last_ex = LinkedInVersionError(
                    f"{resp.status_code} for {ver}: {resp.text[:120]}…")
                log.debug("Version %s rejected for %s", ver, url)
                continue

            # success – remember good month & return
            global _VERSION_CACHE
            _VERSION_CACHE = self.version = ver
            return resp

        attempted = ", ".join(self._versions)
        raise LinkedInVersionError(
            f"All LinkedIn-Version headers failed: {attempted}\nLast error: {last_ex}"
        )


# ─────────────────────────────  CLI demo  ────────────────────────────
if __name__ == "__main__":
    li = LinkedInClient()
    log.info("Authenticated as: %s %s — %s (ver=%s)",
             li.first_name, li.last_name, li.author_urn,
             li.version or _VERSION_CACHE or li._versions[0])

    msg = "🚀 Programmatic post from Python!"
    li.preview(msg)

    if input("Post this? [y/N] ").lower() == "y":
        urn = li.post(msg, visibility="LOGGED_IN")
        log.info("Posted! URN: %s", urn)