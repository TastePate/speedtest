import contextlib
import io
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import speedtest

PAYLOAD = b"x" * 150_000


class Handler(BaseHTTPRequestHandler):
    count = 0
    active = 0
    max_active = 0

    def do_GET(self):
        type(self).count += 1
        type(self).active += 1
        type(self).max_active = max(self.max_active, self.active)
        try:
            if self.path == "/error":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(PAYLOAD)))
            self.end_headers()
            self.wfile.write(PAYLOAD[:100] if self.path == "/short" else PAYLOAD)
        finally:
            type(self).active -= 1

    def log_message(self, *args):
        pass


class SpeedMeterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        Handler.count = Handler.active = Handler.max_active = 0

    def test_ten_sequential_downloads_and_calculation(self):
        output = io.StringIO()
        timestamps = [value for index in range(10) for value in (index * 3, index * 3 + 2)]
        with contextlib.redirect_stdout(output), patch("speedtest.time.perf_counter", side_effect=timestamps):
            self.assertEqual(speedtest.main([self.url]), 0)
        self.assertEqual(Handler.count, 10)
        self.assertEqual(Handler.max_active, 1)
        self.assertIn("1500000 байт", output.getvalue())
        self.assertIn("2.000 с", output.getvalue())
        self.assertIn("0.075 МБ/с (0.600 Мбит/с)", output.getvalue())

    def test_http_error_stops_series(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(speedtest.main([self.url + "/error"]), 1)
        self.assertEqual(Handler.count, 1)

    def test_incomplete_body(self):
        with self.assertRaises(OSError):
            speedtest.download(self.url + "/short", 2)

    def test_invalid_arguments(self):
        for args in (["ftp://host/file"], [self.url, "--timeout", "nan"], [self.url, "--timeout", "0"]):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                speedtest.main(args)
            self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
