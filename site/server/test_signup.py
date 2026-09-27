import http.client
import importlib.util
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode


spec = importlib.util.spec_from_file_location("signup", Path(__file__).with_name("signup.py"))
signup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signup)


class SignupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        signup.DATABASE = str(Path(self.temp.name, "subscribers.sqlite3"))
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), signup.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def post(self, path, fields, origin=signup.ORIGIN):
        body = urlencode(fields)
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port)
        conn.request("POST", path, body, {"Content-Type": "application/x-www-form-urlencoded", "Origin": origin})
        response = conn.getresponse()
        status, location = response.status, response.getheader("Location")
        response.read()
        conn.close()
        return status, location

    def emails(self):
        if not Path(signup.DATABASE).exists():
            return []
        with sqlite3.connect(signup.DATABASE) as db:
            return [row[0] for row in db.execute("SELECT email FROM subscribers")]

    def test_subscribe_deduplicates_and_unsubscribe_removes(self):
        self.assertEqual(self.post("/subscribe", {"email": " Ben@Example.org ", "consent": "yes"}), (303, "/subscribed.html"))
        self.assertEqual(self.post("/subscribe", {"email": "ben@example.org", "consent": "yes"})[0], 303)
        self.assertEqual(self.emails(), ["ben@example.org"])
        self.assertEqual(self.post("/unsubscribe", {"email": "ben@example.org"}), (303, "/unsubscribed.html"))
        self.assertEqual(self.emails(), [])

    def test_rejects_missing_consent_invalid_email_and_foreign_origin(self):
        self.assertEqual(self.post("/subscribe", {"email": "a@example.org"})[0], 400)
        self.assertEqual(self.post("/subscribe", {"email": "not-an-email", "consent": "yes"})[0], 400)
        self.assertEqual(self.post("/subscribe", {"email": "a@example.org", "consent": "yes"}, "https://other.example")[0], 403)
        self.assertEqual(self.emails(), [])

    def test_honeypot_does_not_store(self):
        self.assertEqual(self.post("/subscribe", {"email": "bot@example.org", "consent": "yes", "website": "spam"})[0], 303)
        self.assertEqual(self.emails(), [])


if __name__ == "__main__":
    unittest.main()
