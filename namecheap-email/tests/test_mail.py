import asyncio
import contextlib
import io
import json
from pathlib import Path
import ssl
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mail_core as core
import server
import setup_email

CONFIG = {"host": core.HOST, "port": 993, "username": "test@example.com",
          "password": "synthetic-test-secret", "folders": ["INBOX", "Folder With Spaces"]}
RAW = b"From: sender@example.com\r\nTo: test@example.com\r\nSubject: Test\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nHello world"


class FakeIMAP:
    def __init__(self):
        self.calls = []
        self.literal = None
        self.size = len(RAW)
        self.validity = b"123"

    def login(self, user, password):
        return "OK", [b"logged in"]

    def select(self, folder, readonly=False):
        assert readonly is True
        self.calls.append(("EXAMINE", folder))
        return "OK", [b"3"]

    def response(self, name):
        return name, [self.validity]

    def uid(self, command, *args):
        assert command in ("SEARCH", "FETCH"), command
        self.calls.append((command, args, self.literal))
        if command == "SEARCH":
            self.literal = None
            return "OK", [b"1 4 9"]
        if args[1] == "(RFC822.SIZE)":
            return "OK", [f"1 (UID {args[0]} RFC822.SIZE {self.size})".encode()]
        assert "BODY.PEEK[" in args[1]
        return "OK", [(b"1 (UID 9 BODY[] {120}", RAW), b")"]

    def logout(self):
        self.calls.append(("LOGOUT",))
        return "BYE", []


class MailTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeIMAP()
        self.config = patch.object(core, "load_config", return_value=CONFIG.copy())
        self.network = patch.object(core.imaplib, "IMAP4_SSL", return_value=self.fake)
        self.config.start()
        self.factory = self.network.start()
        self.addCleanup(self.config.stop)
        self.addCleanup(self.network.stop)

    def test_tls_and_allowlist(self):
        self.assertTrue(core.check_connection()["read_only"])
        context = self.factory.call_args.kwargs["ssl_context"]
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertGreaterEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        self.assertEqual(self.factory.call_args.args, (core.HOST, 993))
        self.assertIn(("EXAMINE", '"Folder With Spaces"'), self.fake.calls)

    def test_pages_are_uid_based(self):
        page = core.list_messages(limit=2)
        self.assertEqual([m["uid"] for m in page["messages"]], ["9", "4"])
        self.assertEqual(page["next_before_uid"], 4)
        self.assertEqual(core.list_messages(before_uid=4)["messages"][0]["uid"], "1")

    def test_folder_scope(self):
        with self.assertRaises(core.MailError):
            core.list_messages(folder="Sent")
        self.assertFalse(any(call[0] == "EXAMINE" for call in self.fake.calls))

    def test_unicode_and_quoted_search_are_literals(self):
        term = 'café " OR ALL'
        core.list_messages(subject=term, unread_only=True, since="2026-09-01")
        searches = [call for call in self.fake.calls if call[0] == "SEARCH"]
        self.assertEqual(searches[0][1], ("UNSEEN", "SINCE", "01-Sep-2026"))
        self.assertEqual(searches[1][1], ("CHARSET", "UTF-8", "SUBJECT"))
        self.assertEqual(searches[1][2], term.encode("utf-8"))

    def test_control_injection_rejected_before_connect(self):
        with self.assertRaises(core.MailError):
            core.list_messages(subject="hello\r\nA1 STORE 1 +FLAGS \\Deleted")
        self.factory.assert_not_called()

    def test_read_only_and_logout(self):
        result = core.read_message("9", "123")
        self.assertEqual(result["body"], "Hello world")
        self.assertTrue(result["untrusted_email_data"])
        self.assertEqual(self.fake.calls[-1], ("LOGOUT",))

    def test_stale_uidvalidity_blocks_fetch(self):
        with self.assertRaises(core.MailError):
            core.read_message("9", "999")
        self.assertFalse(any(call[0] == "FETCH" for call in self.fake.calls))

    def test_invalid_uid_and_limits(self):
        for uid in ("1:*", "0", "1,2", "1 STORE", "1\r\n"):
            with self.assertRaises(core.MailError):
                core.read_message(uid, "123")
        for limit in (0, 51, True):
            with self.assertRaises(core.MailError):
                core.list_messages(limit=limit)
        self.factory.assert_not_called()

    def test_oversized_message_not_downloaded(self):
        self.fake.size = core.MAX_MESSAGE + 1
        with self.assertRaises(core.MailError):
            core.read_message("9", "123")
        self.assertEqual(len([c for c in self.fake.calls if c[0] == "FETCH"]), 1)

    def test_missing_message(self):
        with patch.object(self.fake, "uid", return_value=("OK", [None])):
            with self.assertRaises(core.MailError):
                core.read_message("9", "123")

    def test_multipart_html_no_active_content(self):
        raw = (b'MIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=x\r\n\r\n'
               b'--x\r\nContent-Type: text/html\r\n\r\n<p>Hello</p><script>danger</script><img src="https://example.com/pixel">'
               b'\r\n--x\r\nContent-Type: application/octet-stream\r\nContent-Disposition: attachment; filename="test.bin"\r\n\r\nattachment-data'
               b'\r\n--x--\r\n')
        result = core.parse_message(raw, 100)
        self.assertIn("Hello", result["body"])
        self.assertNotIn("danger", result["body"])
        self.assertNotIn("https", result["body"])
        self.assertNotIn("attachment-data", result["body"])
        self.assertEqual(result["attachments"][0]["filename"], "test.bin")

    def test_unknown_charset_and_truncation(self):
        raw = RAW.replace(b"charset=utf-8", b"charset=not-a-real-charset")
        result = core.parse_message(raw, 5)
        self.assertEqual(result["body"], "Hello")
        self.assertTrue(result["body_truncated"])

    def test_auth_error_is_redacted(self):
        with patch.object(self.fake, "login", side_effect=core.imaplib.IMAP4.error("synthetic-test-secret")):
            result = server.check_connection()
        self.assertFalse(result["ok"])
        self.assertNotIn("synthetic-test-secret", json.dumps(result))

    def test_unexpected_error_and_logs_are_redacted(self):
        output = io.StringIO()
        with patch.object(core, "check_connection", side_effect=RuntimeError("synthetic-test-secret")):
            with contextlib.redirect_stderr(output), contextlib.redirect_stdout(output):
                result = server.check_connection()
        self.assertNotIn("synthetic-test-secret", json.dumps(result) + output.getvalue())

    def test_host_cannot_be_redirected(self):
        with self.assertRaises(core.MailError):
            core.validate_config({**CONFIG, "host": "example.com"})

    def test_vault_failure_has_no_plaintext_fallback(self):
        with patch.object(core, "vault", side_effect=RuntimeError("synthetic-test-secret")):
            with self.assertRaisesRegex(core.MailError, "No plaintext fallback"):
                core.save_config(CONFIG)

    def test_mcp_tools_are_only_read_operations(self):
        tools = asyncio.run(server.mcp.list_tools())
        self.assertEqual({t.name for t in tools}, {"check_connection", "list_messages", "search_messages", "read_message"})
        for tool in tools:
            self.assertTrue(tool.annotations.readOnlyHint)
            self.assertFalse(tool.annotations.destructiveHint)
            self.assertNotIn("password", tool.inputSchema.get("properties", {}))

    def test_setup_refuses_noninteractive_password_input(self):
        with patch.object(sys.stdin, "isatty", return_value=False), patch.object(setup_email.getpass, "getpass") as password:
            with contextlib.redirect_stdout(io.StringIO()):
                setup_email.console_setup()
            password.assert_not_called()

    def test_setup_saves_only_after_verification(self):
        with patch.object(sys.stdin, "isatty", return_value=True), patch("builtins.input", side_effect=["", "test@example.com", "INBOX"]):
            with patch.object(setup_email.getpass, "getpass", return_value="synthetic-test-secret"):
                with patch.object(core, "check_connection", side_effect=core.MailError("Invalid login")), patch.object(core, "save_config") as save:
                    with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(core.MailError):
                        setup_email.console_setup()
                    save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
