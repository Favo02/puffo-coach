"""Strava OAuth 2.0 token manager."""

from __future__ import annotations

import json
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests

from puffo_coach.config import require_strava

PRIMARY_TOKEN_PATH = Path.home() / '.puffo-coach' / 'strava_tokens.json'
LEGACY_TOKEN_PATH = Path.home() / '.health-context' / 'strava_tokens.json'
CALLBACK_PORT = 5739


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    auth_code: str | None = None

    def do_GET(self) -> None:
        query = parse_qs(urlparse(self.path).query)
        if "code" in query:
            OAuthCallbackHandler.auth_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Authorization successful!</h1><p>You can close this tab.</p></body></html>")
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Authorization failed.</h1></body></html>")
            
    def log_message(self, format: str, *args: tuple[str, ...]) -> None:
        pass


class StravaTokenManager:
    def __init__(self) -> None:
        self.client_id, self.client_secret = require_strava()

    def get_access_token(self) -> str:
        tokens = self._load_tokens()
        if tokens:
            if tokens.get("expires_at", 0) > time.time():
                return tokens["access_token"]
            if "refresh_token" in tokens:
                return self._refresh(tokens["refresh_token"])
        return self._authorize_interactive()

    def _authorize_interactive(self) -> str:
        url = (
            f"https://www.strava.com/oauth/authorize"
            f"?client_id={self.client_id}"
            f"&redirect_uri=http://localhost:{CALLBACK_PORT}/callback"
            f"&response_type=code"
            f"&scope=activity:read_all"
            f"&approval_prompt=auto"
        )
        print("Please authorize Puffo Coach to access your Strava data.")
        print(f"Opening browser to: {url}")
        webbrowser.open(url)

        server = HTTPServer(("localhost", CALLBACK_PORT), OAuthCallbackHandler)
        OAuthCallbackHandler.auth_code = None
        while OAuthCallbackHandler.auth_code is None:
            server.handle_request()

        auth_code = OAuthCallbackHandler.auth_code
        server.server_close()

        resp = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": auth_code,
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        
        self._save_tokens(data)
        return data["access_token"]

    def _refresh(self, refresh_token: str) -> str:
        resp = requests.post(
            "https://www.strava.com/oauth/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._save_tokens(data)
        return data["access_token"]

    def _load_tokens(self) -> dict | None:
        path = PRIMARY_TOKEN_PATH if PRIMARY_TOKEN_PATH.exists() else LEGACY_TOKEN_PATH
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _save_tokens(self, tokens: dict) -> None:
        PRIMARY_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PRIMARY_TOKEN_PATH, "w") as f:
            json.dump(tokens, f)
