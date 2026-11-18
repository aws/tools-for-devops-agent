"""Unit tests for .github/scripts/github_logins.py.

A fake HTTPS handler answers in place of GitHub, so no test reaches the network.
"""

from __future__ import annotations

import email.message
import io
import json
import sys
import unittest
import urllib.error
import urllib.request
import urllib.response
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

import github_logins as gl  # noqa: E402


def headers(**values: str) -> email.message.Message:
    message = email.message.Message()
    for name, value in values.items():
        message[name.replace("_", "-")] = value
    return message


class FakeGitHub(urllib.request.HTTPSHandler):
    """Answers each request with the next response in `answers`: (status, headers, body), or an exception to raise."""

    def __init__(self, *answers):
        super().__init__()
        self.answers = list(answers)
        self.requests: list[urllib.request.Request] = []
        self.timeouts: list[float] = []

    def https_open(self, request):
        self.requests.append(request)
        self.timeouts.append(request.timeout)
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        status, answer_headers, body = answer
        response = urllib.response.addinfourl(io.BytesIO(body), answer_headers, request.full_url, status)
        response.msg = "answer"
        return response


def resolver(*answers, token: str | None = "secret-token") -> tuple[gl.GitHubResolver, FakeGitHub, list[float]]:
    fake = FakeGitHub(*answers)
    sleeps: list[float] = []
    return gl.GitHubResolver(token, opener=gl.build_opener(fake), sleep=sleeps.append), fake, sleeps


def ok(account_type: str = "User"):
    return 200, headers(Content_Type="application/json"), json.dumps({"login": "x", "type": account_type}).encode()


class LookupTests(unittest.TestCase):
    def test_an_account_is_found_with_its_type(self):
        lookups, fake, _ = resolver(ok("Organization"))
        self.assertEqual(lookups.lookup("octo-org"), gl.Lookup(gl.FOUND, account_type="Organization"))
        request = fake.requests[0]
        self.assertEqual(request.full_url, "https://api.github.com/users/octo-org")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-token")
        self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
        self.assertTrue(request.get_header("User-agent"))
        self.assertEqual(fake.timeouts, [gl.TIMEOUT_SECONDS])

    def test_each_answer_and_what_it_does_to_later_lookups(self):
        missing = (404, headers(), b'{"message": "Not Found"}')
        rate_limited = gl.Lookup(gl.UNKNOWN, reason="GitHub's API rate limit was reached")
        failed = gl.Lookup(gl.UNKNOWN, reason="the request to GitHub failed or timed out")

        def http(status: int) -> gl.Lookup:
            return gl.Lookup(gl.UNKNOWN, reason=f"GitHub returned HTTP {status}")

        moved = (301, headers(Location="https://elsewhere.example/users/octocat"), b"")
        # label: (answers to the first lookup, its result, requests it makes, whether later lookups stop)
        rows = {
            "404": ([missing], gl.Lookup(gl.MISSING), 1, False),
            "403 with no requests left": ([(403, headers(X_RateLimit_Remaining="0"), b"{}")], rate_limited, 1, True),
            "429": ([(429, headers(Retry_After="60"), b"{}")], rate_limited, 1, True),
            "403": ([(403, headers(), b"{}")], http(403), 1, True),
            "401": ([(401, headers(), b"{}")], http(401), 1, True),
            "422": ([(422, headers(), b"{}")], http(422), 1, False),
            "a redirect, not followed": ([moved], http(301), 1, False),
            "502, then found": ([(502, headers(), b""), ok()], gl.Lookup(gl.FOUND, account_type="User"), 2, False),
            "a 5xx twice": ([(502, headers(), b""), (503, headers(), b"")], http(503), 2, True),
            "a timeout twice": ([TimeoutError("timed out")] * 2, failed, 2, True),
            "a refused connection twice": ([urllib.error.URLError("connection refused")] * 2, failed, 2, True),
            "a reset connection twice": ([ConnectionResetError()] * 2, failed, 2, True),
            "a timeout, then not found": ([TimeoutError("timed out"), missing], gl.Lookup(gl.MISSING), 2, False),
        }
        for label, (answers, expected, requests, stops) in rows.items():
            with self.subTest(label):
                lookups, fake, sleeps = resolver(*answers, ok())
                self.assertEqual(lookups.lookup("octocat"), expected)
                self.assertEqual(len(fake.requests), requests)
                self.assertEqual(sleeps, [gl.RETRY_DELAY_SECONDS] * (requests - 1))
                later = lookups.lookup("hubot")
                if stops:
                    # Nothing more is asked, so an outage costs one lookup's retry, not one per login.
                    reason = f"an earlier lookup showed that {expected.reason}"
                    self.assertEqual(later, gl.Lookup(gl.UNKNOWN, reason=reason))
                    self.assertEqual(len(fake.requests), requests)
                else:
                    self.assertEqual(later.status, gl.FOUND)
                    self.assertEqual(len(fake.requests), requests + 1)
                urls = {request.full_url for request in fake.requests}
                self.assertLessEqual(urls, {f"{gl.API_URL}/users/octocat", f"{gl.API_URL}/users/hubot"})

    def test_without_a_token_nothing_is_requested(self):
        for token in (None, ""):
            with self.subTest(token=token):
                lookups, fake, _ = resolver(token=token)
                self.assertEqual(
                    lookups.lookup("octocat"),
                    gl.Lookup(gl.UNKNOWN, reason="no GitHub token is set in GH_TOKEN or GITHUB_TOKEN"),
                )
                self.assertEqual(fake.requests, [])

    def test_each_login_is_looked_up_once_ignoring_case(self):
        lookups, fake, _ = resolver(ok(), ok())
        self.assertEqual(lookups.lookup("OctoCat"), lookups.lookup("octocat"))
        self.assertEqual(len(fake.requests), 1)

    def test_a_body_that_is_not_json_still_counts_as_found(self):
        lookups, _, _ = resolver((200, headers(), b"<html>"))
        self.assertEqual(lookups.lookup("octocat"), gl.Lookup(gl.FOUND))

    def test_the_token_comes_from_gh_token_then_github_token(self):
        cases = (
            ({"GH_TOKEN": "gh", "GITHUB_TOKEN": "github"}, "gh"),
            ({"GH_TOKEN": "", "GITHUB_TOKEN": "github"}, "github"),
            ({"GITHUB_TOKEN": "github"}, "github"),
            ({}, None),
        )
        for environment, token in cases:
            with self.subTest(environment=environment):
                with mock.patch.dict("os.environ", environment, clear=True):
                    self.assertEqual(gl.GitHubResolver.from_environment()._token, token)


if __name__ == "__main__":
    unittest.main()
