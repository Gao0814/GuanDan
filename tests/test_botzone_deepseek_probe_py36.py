from __future__ import annotations

import ast
import importlib.util
import json
import socket
import ssl
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import urllib.error
from unittest.mock import patch
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "botzone_deepseek_probe_py36" / "__main__.py"
BASELINE = ROOT / "botzone_upload_py36" / "__main__.py"
ARCHIVE = ROOT / "dist" / "guandan_deepseek_probe_py36.zip"


def _load_probe():
    spec = importlib.util.spec_from_file_location("botzone_deepseek_probe_py36_test", str(SOURCE))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _deal():
    return {
        "stage": "deal",
        "deliver": list(range(27)),
        "your_id": 0,
        "global": {"level": "2", "tribute": 0, "first": None, "last": None},
    }


def _play():
    return {
        "stage": "play",
        "history": [[], [], [], []],
        "done": [],
        "pass_on": -1,
        "global": {
            "level": "2",
            "tribute": 0,
            "first": None,
            "last": None,
            "resist": False,
            "tribute_cards": {},
            "return_cards": {},
        },
    }


def _payload(play=False, data=None):
    result = {"requests": [_deal()], "responses": []}
    if play:
        result["requests"].append(_play())
        result["responses"].append([])
    if data is not None:
        result["data"] = data
    return result


class _Response:
    def __init__(self, body):
        self._body = body
        self.closed = False

    def read(self):
        return self._body

    def close(self):
        self.closed = True


class BotzoneDeepSeekProbePython36Tests(unittest.TestCase):
    def setUp(self):
        self.probe = _load_probe()

    def _credential(self, root, name, value):
        path = Path(root) / name
        path.write_text(value, encoding="utf-8")
        return path

    def test_source_is_python_36_stdlib_and_archive_has_root_main(self):
        source = SOURCE.read_text(encoding="utf-8")
        ast.parse(source, filename=str(SOURCE), feature_version=(3, 6))
        self.assertNotIn("from __future__ import annotations", source)
        self.assertNotIn("dotenv", source)
        self.assertTrue(ARCHIVE.is_file())
        self.assertLessEqual(ARCHIVE.stat().st_size, 4 * 1024 * 1024)
        with zipfile.ZipFile(ARCHIVE) as archive:
            self.assertEqual(archive.namelist(), ["__main__.py"])
            self.assertEqual(archive.read("__main__.py").decode("utf-8"), source)

    def test_unavailable_credentials_never_open_network(self):
        with TemporaryDirectory() as root:
            missing = Path(root) / "missing.json"
            for path in (missing, self._credential(root, "empty.json", ""), self._credential(root, "malformed.json", "not-json")):
                with self.subTest(path_kind=path.name):
                    with patch.object(self.probe, "PROBE_CREDENTIAL_PATH", str(path)), patch.object(
                        self.probe, "_open_url", side_effect=AssertionError("network_must_not_run")
                    ):
                        self.assertEqual(self.probe._probe_once({}), "credential_unavailable")
            with patch("builtins.open", side_effect=OSError), patch.object(
                self.probe, "_open_url", side_effect=AssertionError("network_must_not_run")
            ):
                self.assertEqual(self.probe._probe_once({}), "credential_unavailable")

    def test_fake_success_uses_fixed_minimal_request_once(self):
        with TemporaryDirectory() as root:
            credential = self._credential(root, "credential.json", json.dumps({"api_key": "synthetic-test-credential"}))
            calls = []
            response = _Response(b'{"choices":[]}')

            def opener(request, timeout):
                calls.append((request, timeout))
                return response

            with patch.object(self.probe, "PROBE_CREDENTIAL_PATH", str(credential)), patch.object(self.probe, "_open_url", side_effect=opener):
                self.assertEqual(self.probe._probe_once({}), "probe_ok")
                self.assertEqual(self.probe._probe_once({"data": "probe_ok"}), "probe_ok")
                self.assertEqual(
                    self.probe._output_for(_payload(play=True, data="probe_ok"))["response"],
                    self.probe.decide(_payload(play=True)),
                )
            self.assertEqual(len(calls), 1)
            request, timeout = calls[0]
            body = json.loads(request.data.decode("utf-8"))
            self.assertEqual((request.full_url, request.get_method(), timeout), (self.probe.PROBE_URL, "POST", 3))
            self.assertEqual((body["model"], body["stream"], body["max_tokens"]), ("deepseek-v4-flash", False, 1))
            self.assertEqual(body["messages"], [{"role": "user", "content": "probe"}])
            self.assertTrue(request.get_header("Authorization").startswith("Bearer "))
            self.assertTrue(response.closed)

    def test_fixed_failure_categories_ignore_error_and_model_bodies(self):
        with TemporaryDirectory() as root:
            credential = self._credential(root, "credential.json", json.dumps({"api_key": "synthetic-test-credential"}))
            cases = (
                (socket.timeout(), "probe_timeout"),
                (urllib.error.URLError(socket.gaierror()), "probe_dns_or_connect_failed"),
                (urllib.error.URLError(ssl.SSLError()), "probe_tls_failed"),
                (urllib.error.HTTPError(self.probe.PROBE_URL, 401, "private", None, None), "probe_http_4xx"),
                (urllib.error.HTTPError(self.probe.PROBE_URL, 503, "private", None, None), "probe_http_5xx"),
                (_Response(b"not-json"), "probe_response_invalid"),
                (RuntimeError("private"), "probe_unexpected_failure"),
            )
            for result, expected in cases:
                with self.subTest(expected=expected):
                    with patch.object(self.probe, "PROBE_CREDENTIAL_PATH", str(credential)), patch.object(
                        self.probe, "_open_url", side_effect=result if isinstance(result, BaseException) else None, return_value=result if isinstance(result, _Response) else None
                    ):
                        actual = self.probe._probe_once({})
                    self.assertEqual(actual, expected)
                    self.assertNotIn("private", actual)

    def test_probe_response_never_changes_rule_response(self):
        payload = _payload(play=True)
        with TemporaryDirectory() as root:
            encoded = json.dumps(payload, separators=(",", ":")) + "\n"
            baseline = subprocess.run([sys.executable, str(BASELINE)], input=encoded, text=True, capture_output=True, cwd=root, timeout=5, check=True)
            probe = subprocess.run([sys.executable, str(SOURCE)], input=encoded, text=True, capture_output=True, cwd=root, timeout=5, check=True)
        baseline_output = json.loads(baseline.stdout)
        probe_output = json.loads(probe.stdout)
        self.assertEqual(probe_output["response"], baseline_output["response"])
        self.assertEqual(probe_output["debug"], "credential_unavailable")
        self.assertEqual(probe.stderr, "")


if __name__ == "__main__":
    unittest.main()
