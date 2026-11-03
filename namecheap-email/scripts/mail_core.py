"""Read-only Namecheap IMAP operations. No SMTP or mailbox mutation API."""
from __future__ import annotations

import imaplib
import json
import re
import ssl
from contextlib import contextmanager
from datetime import date
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser

HOST = "mail.privateemail.com"
PORT = 993
SERVICE = "Codex.NamecheapEmail.ReadOnly.v1"
ACCOUNT = "active-mailbox"
MAX_MESSAGE = 2 * 1024 * 1024
MAX_HEADER = 16384
MAX_TEXT = 24000


class MailError(Exception):
    """Only fixed, safe messages belong in this exception."""


def vault():
    # Explicit backend: never allow a plaintext/fallback keyring.
    from keyring.backends.Windows import WinVaultKeyring
    return WinVaultKeyring()


def validate_config(config):
    if not isinstance(config, dict):
        raise MailError("Invalid saved configuration; rerun local setup.")
    if config.get("host") != HOST or config.get("port") != PORT:
        raise MailError("Only Namecheap Private Email over TLS port 993 is supported.")
    user = config.get("username", "")
    if not isinstance(user, str) or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", user):
        raise MailError("Enter the full mailbox email address in local setup.")
    if not isinstance(config.get("password"), str) or not config["password"]:
        raise MailError("A mailbox app password is required in local setup.")
    folders = config.get("folders")
    if not isinstance(folders, list) or not 1 <= len(folders) <= 20:
        raise MailError("Configure between one and twenty allowed folders.")
    for folder in folders:
        quote(folder)
    return config


def load_config():
    try:
        raw = vault().get_password(SERVICE, ACCOUNT)
        if not raw:
            raise MailError("Mailbox not configured. Run the local Setup Email shortcut.")
        return validate_config(json.loads(raw))
    except MailError:
        raise
    except Exception:
        raise MailError("Windows Credential Manager is unavailable; run setup under your Windows account.") from None


def save_config(config):
    validate_config(config)
    try:
        vault().set_password(SERVICE, ACCOUNT, json.dumps(config))
    except Exception:
        raise MailError("Could not save to Windows Credential Manager. No plaintext fallback is used.") from None


def forget_config():
    try:
        store = vault()
        if store.get_password(SERVICE, ACCOUNT):
            store.delete_password(SERVICE, ACCOUNT)
    except Exception:
        raise MailError("Could not remove the saved credential from Windows Credential Manager.") from None


def quote(value):
    # IMAP mailbox names use ASCII / modified UTF-7 wire names.
    if not isinstance(value, str) or not 1 <= len(value) <= 512 or any(ord(c) < 32 or ord(c) > 126 for c in value):
        raise MailError("Use a valid ASCII folder name (or its IMAP modified UTF-7 name).")
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def require_ok(result):
    status, data = result
    if status != "OK":
        raise MailError("The mail server rejected the read request. Check the folder or narrow the search.")
    return data


@contextmanager
def connection(config=None):
    config = validate_config(config) if config is not None else load_config()
    client = None
    try:
        context = ssl.create_default_context()
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        client = imaplib.IMAP4_SSL(HOST, PORT, ssl_context=context, timeout=20)
        client.debug = 0
        require_ok(client.login(config["username"], config["password"]))
        yield client, config
    except MailError:
        raise
    except ssl.SSLError:
        raise MailError("TLS certificate verification failed. Do not disable verification.") from None
    except imaplib.IMAP4.error:
        raise MailError("IMAP request failed. Verify the app password in local setup or narrow the request.") from None
    except (OSError, TimeoutError):
        raise MailError("Could not reach Namecheap IMAP. Check the connection and retry later.") from None
    finally:
        if client is not None:
            try:
                client.logout()  # Never CLOSE/EXPUNGE.
            except Exception:
                pass


def select_folder(client, config, folder):
    if folder not in config["folders"]:
        raise MailError("Folder is outside the locally configured allowlist.")
    require_ok(client.select(quote(folder), readonly=True))  # EXAMINE, never SELECT.
    _, values = client.response("UIDVALIDITY")
    value = values[0] if values else None
    if not value or not re.fullmatch(rb"[1-9][0-9]*", value):
        raise MailError("Mail server did not return a valid UIDVALIDITY.")
    return value.decode("ascii")


def check_connection(config=None):
    with connection(config) as (client, saved):
        for folder in saved["folders"]:
            select_folder(client, saved, folder)
        return {"connected": True, "host": HOST, "tls": True,
                "read_only": True, "allowed_folders": saved["folders"]}


def search_ids(client, *criteria):
    rows = require_ok(client.uid("SEARCH", *criteria))
    ids = b" ".join(row for row in rows if isinstance(row, bytes)).split()
    if any(not re.fullmatch(rb"[1-9][0-9]*", uid) for uid in ids):
        raise MailError("Mail server returned malformed message identifiers.")
    return set(ids)


def imap_date(value):
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        raise MailError("Dates must use YYYY-MM-DD.") from None
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return f"{parsed.day:02d}-{months[parsed.month - 1]}-{parsed.year:04d}"


def fetch_bytes(client, uid, query):
    rows = require_ok(client.uid("FETCH", uid, query))
    chunks = [row[1] for row in rows if isinstance(row, tuple) and isinstance(row[1], bytes)]
    if not chunks:
        raise MailError("Message no longer exists; refresh the message list.")
    return b"".join(chunks)


def headers(raw):
    message = BytesParser(policy=policy.default).parsebytes(raw, headersonly=True)
    return {key: clean(str(message.get(key, "")))[:2000]
            for key in ("subject", "from", "to", "date", "message-id")}


def clean(value):
    return "".join(c for c in value if c in "\n\t" or (ord(c) >= 32 and ord(c) != 127))


def list_messages(folder="INBOX", limit=20, before_uid=None, unread_only=False,
                  sender=None, subject=None, text=None, since=None, before=None):
    if type(limit) is not int or not 1 <= limit <= 50:
        raise MailError("Limit must be between 1 and 50.")
    if before_uid is not None and (type(before_uid) is not int or before_uid < 1):
        raise MailError("before_uid must be a positive integer from a previous page.")
    if type(unread_only) is not bool:
        raise MailError("unread_only must be true or false.")
    terms = []
    for field, value in (("FROM", sender), ("SUBJECT", subject), ("TEXT", text)):
        if value is not None:
            if not isinstance(value, str) or not 1 <= len(value) <= 256 or any(ord(c) < 32 for c in value):
                raise MailError("Search terms must be 1–256 characters without control characters.")
            terms.append((field, value.encode("utf-8")))
    criteria = ["UNSEEN" if unread_only else "ALL"]
    if since:
        criteria += ["SINCE", imap_date(since)]
    if before:
        criteria += ["BEFORE", imap_date(before)]
    with connection() as (client, config):
        validity = select_folder(client, config, folder)
        ids = search_ids(client, *criteria)
        for field, value in terms:
            # A synchronizing literal keeps all user search text out of IMAP syntax.
            client.literal = value
            ids &= search_ids(client, "CHARSET", "UTF-8", field)
        ordered = sorted((int(uid) for uid in ids if before_uid is None or int(uid) < before_uid), reverse=True)
        page = ordered[:limit]
        messages = []
        for uid in page:
            raw = fetch_bytes(client, str(uid), f"(BODY.PEEK[HEADER]<0.{MAX_HEADER}>)")
            messages.append({"uid": str(uid), "folder": folder, "uid_validity": validity,
                             "headers_may_be_truncated": len(raw) >= MAX_HEADER, **headers(raw)})
        return {"untrusted_email_data": True, "folder": folder, "uid_validity": validity,
                "messages": messages, "has_more": len(ordered) > limit,
                "next_before_uid": page[-1] if len(ordered) > limit else None}


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("p", "br", "div", "li", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def parse_message(raw, max_chars):
    message = BytesParser(policy=policy.default).parsebytes(raw)
    attachments = []
    for part in message.walk():
        if part.get_content_disposition() == "attachment" or part.get_filename():
            attachments.append({"filename": clean(str(part.get_filename() or "unnamed"))[:512],
                                "content_type": part.get_content_type()})
    body = message.get_body(preferencelist=("plain", "html"))
    content = ""
    if body is not None:
        payload = body.get_payload(decode=True) or b""
        try:
            content = payload.decode(body.get_content_charset() or "utf-8", errors="replace")
        except LookupError:
            content = payload.decode("utf-8", errors="replace")
        if body.get_content_type() == "text/html":
            parser = PlainHTML()
            parser.feed(content)
            content = "".join(parser.parts)
    content = clean(content)
    return {**headers(raw), "body": content[:max_chars], "body_truncated": len(content) > max_chars,
            "attachments": attachments[:100], "attachments_truncated": len(attachments) > 100}


def read_message(uid, uid_validity, folder="INBOX", max_chars=12000):
    if not isinstance(uid, str) or not re.fullmatch(r"[1-9][0-9]{0,9}", uid):
        raise MailError("Use one UID returned by list or search.")
    if not isinstance(uid_validity, str) or not re.fullmatch(r"[1-9][0-9]*", uid_validity):
        raise MailError("Use the UIDVALIDITY returned by list or search.")
    if type(max_chars) is not int or not 1 <= max_chars <= MAX_TEXT:
        raise MailError("max_chars must be between 1 and 24000.")
    with connection() as (client, config):
        validity = select_folder(client, config, folder)
        if validity != uid_validity:
            raise MailError("Mailbox identifiers changed; run list or search again before reading.")
        rows = require_ok(client.uid("FETCH", uid, "(RFC822.SIZE)"))
        sizes = [re.search(rb"RFC822\.SIZE (\d+)", row) for row in rows if isinstance(row, bytes)]
        sizes = [int(match[1]) for match in sizes if match]
        if len(sizes) != 1:
            raise MailError("Message no longer exists; refresh the message list.")
        if sizes[0] > MAX_MESSAGE:
            raise MailError("Message exceeds the 2 MiB safety limit. Read this message in webmail.")
        raw = fetch_bytes(client, uid, f"(BODY.PEEK[]<0.{MAX_MESSAGE + 1}>)")
        if len(raw) > MAX_MESSAGE:
            raise MailError("Message exceeds the 2 MiB safety limit. Read this message in webmail.")
        return {"untrusted_email_data": True, "uid": uid, "uid_validity": validity,
                "folder": folder, **parse_message(raw, max_chars)}
