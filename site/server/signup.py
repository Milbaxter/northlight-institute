"""Private, dependency-free email list collector for the Northlight site."""

import os
import re
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs


DATABASE = os.environ.get("NORTHLIGHT_SIGNUPS_DB", "/var/lib/northlight-signups/subscribers.sqlite3")
ORIGIN = os.environ.get("NORTHLIGHT_PUBLIC_ORIGIN", "https://80.47.227.4")
EMAIL_RE = re.compile(r"^[^\s@\x00-\x1f\x7f]+@[^\s@\x00-\x1f\x7f]+\.[^\s@\x00-\x1f\x7f]+$")


def normalise_email(value):
    email = value.strip().casefold()
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        raise ValueError("invalid email")
    return email


def connect():
    db = sqlite3.connect(DATABASE)
    db.execute("""CREATE TABLE IF NOT EXISTS subscribers (
        email TEXT PRIMARY KEY,
        consented_at TEXT NOT NULL,
        consent_version TEXT NOT NULL
    )""")
    return db


def subscribe(email):
    with connect() as db:
        db.execute(
            "INSERT OR IGNORE INTO subscribers VALUES (?, ?, ?)",
            (normalise_email(email), datetime.now(timezone.utc).isoformat(), "2026-09-27"),
        )


def unsubscribe(email):
    with connect() as db:
        db.execute("DELETE FROM subscribers WHERE email = ?", (normalise_email(email),))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Do not put visitor addresses or submitted data in the service journal.
        pass

    def do_POST(self):
        if self.path not in ("/subscribe", "/unsubscribe"):
            return self.send_error(404)
        if self.headers.get("Origin") != ORIGIN:
            return self.send_error(403)
        if self.headers.get_content_type() != "application/x-www-form-urlencoded":
            return self.send_error(415)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.send_error(400)
        if not 1 <= length <= 4096:
            return self.send_error(413)
        try:
            fields = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True, strict_parsing=True)
            email = fields["email"][0]
            if len(fields["email"]) != 1:
                raise ValueError("multiple emails")
            if self.path == "/subscribe":
                if fields.get("consent") != ["yes"]:
                    raise ValueError("consent required")
                if fields.get("website", [""]) != [""]:
                    return self.redirect("/subscribed.html")
                subscribe(email)
                return self.redirect("/subscribed.html")
            unsubscribe(email)
            return self.redirect("/unsubscribed.html")
        except (KeyError, UnicodeDecodeError, ValueError):
            self.send_error(400, "Invalid form submission")

    def redirect(self, path):
        self.send_response(303)
        self.send_header("Location", path)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 8766), Handler).serve_forever()
