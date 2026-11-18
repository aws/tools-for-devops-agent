"""Look up GitHub accounts with GET /users/<login>, so that metadata.author names one that exists.

validate_skills.py --check-github-logins uses this module; the rules are in the
metadata.author row of "Skill Publishing Rules" in CONTRIBUTING.md. The token,
from GH_TOKEN or GITHUB_TOKEN, is sent only to api.github.com.
"""

from __future__ import annotations

import http.client
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Protocol

API_URL = "https://api.github.com"
# Read in this order, as the GitHub CLI reads them.
TOKEN_VARIABLES = ("GH_TOKEN", "GITHUB_TOKEN")
TIMEOUT_SECONDS = 10
# One retry, for a server error or a request that fails or times out.
ATTEMPTS = 2
RETRY_DELAY_SECONDS = 1.0
# Answers that hold for every login in the run: the token was refused, or a rate limit was reached. Any other
# 3xx or 4xx answer, such as a redirect, is about one login only.
RUN_WIDE_STATUSES = frozenset({401, 403, 429})
# A user or organization record is a few kilobytes.
MAX_RESPONSE_BYTES = 1_048_576
USER_AGENT = "tools-for-devops-agent-validate-skills"

FOUND = "found"
MISSING = "missing"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class Lookup:
    """What GitHub said about one login.

    `status` is FOUND, MISSING (HTTP 404) or UNKNOWN. `account_type` is
    GitHub's "User" or "Organization" when the account was found, and `reason`
    says why GitHub couldn't answer when the status is UNKNOWN.
    """

    status: str
    account_type: str | None = None
    reason: str | None = None


class Resolver(Protocol):
    def lookup(self, login: str) -> Lookup: ...


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Turns a redirect into an HTTP error, so the token never goes to another address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def build_opener(*handlers: urllib.request.BaseHandler) -> urllib.request.OpenerDirector:
    """An opener that refuses redirects. The tests pass a handler that answers in place of the network."""
    return urllib.request.build_opener(_RefuseRedirects(), *handlers)


class GitHubResolver:
    """Looks up logins with GET /users/<login>, once per login per run, ignoring case as GitHub does.

    Once GitHub can't answer a lookup (a refused token, a rate limit, or a
    server error or failed request even after the retry), no more requests are
    made: each later login is UNKNOWN straight away, with the reason of the
    lookup that stopped them. An outage then costs one lookup's timeout and
    retry, not one per login, and a rate limit isn't hit again.
    """

    def __init__(
        self,
        token: str | None,
        *,
        opener: urllib.request.OpenerDirector | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._token = token or None
        self._opener = opener or build_opener()
        self._sleep = sleep
        self._cache: dict[str, Lookup] = {}
        # Why GitHub stopped answering, once a lookup has found that it can't.
        self._stopped: str | None = None

    @classmethod
    def from_environment(cls) -> GitHubResolver:
        return cls(next((os.environ[name] for name in TOKEN_VARIABLES if os.environ.get(name)), None))

    def lookup(self, login: str) -> Lookup:
        key = login.lower()
        if key not in self._cache:
            self._cache[key] = self._fetch(login)
        return self._cache[key]

    def _fetch(self, login: str) -> Lookup:
        if self._token is None:
            return Lookup(UNKNOWN, reason=f"no GitHub token is set in {' or '.join(TOKEN_VARIABLES)}")
        if self._stopped is not None:
            return Lookup(UNKNOWN, reason=f"an earlier lookup showed that {self._stopped}")
        request = urllib.request.Request(
            f"{API_URL}/users/{urllib.parse.quote(login, safe='')}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": USER_AGENT,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        reason = "GitHub didn't answer"
        for attempt in range(ATTEMPTS):
            if attempt:
                self._sleep(RETRY_DELAY_SECONDS)
            try:
                with self._opener.open(request, timeout=TIMEOUT_SECONDS) as response:
                    body = response.read(MAX_RESPONSE_BYTES)
                return Lookup(FOUND, account_type=_account_type(body))
            except urllib.error.HTTPError as exc:
                exc.close()
                if exc.code == 404:
                    return Lookup(MISSING)
                reason = _http_error_reason(exc)
                if exc.code < 500:
                    # A retry wouldn't get another answer within the run.
                    if exc.code in RUN_WIDE_STATUSES:
                        self._stopped = reason
                    return Lookup(UNKNOWN, reason=reason)
            except (urllib.error.URLError, http.client.HTTPException, OSError):
                # TimeoutError is an OSError, and URLError wraps a failed connection.
                reason = "the request to GitHub failed or timed out"
        # A server error or a failed request, even after the retry: GitHub isn't answering, so stop asking.
        self._stopped = reason
        return Lookup(UNKNOWN, reason=reason)


def _account_type(body: bytes) -> str | None:
    try:
        document = json.loads(body)
    except ValueError:
        return None
    kind = document.get("type") if isinstance(document, dict) else None
    return kind if isinstance(kind, str) else None


def _http_error_reason(exc: urllib.error.HTTPError) -> str:
    remaining = exc.headers.get("X-RateLimit-Remaining") if exc.headers else None
    if exc.code == 429 or (exc.code == 403 and remaining == "0"):
        return "GitHub's API rate limit was reached"
    return f"GitHub returned HTTP {exc.code}"
