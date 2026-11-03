# Namecheap Email — private, read-only Codex plugin

Search, list, and read your Namecheap Private Email mailbox from Codex on this Windows computer. The service was confirmed by the user as Namecheap's IMAP Private Email. This is a personal local plugin, not a Namecheap product or a public ChatGPT app.

## Connect it

1. Right-click **Install Plugin.ps1** and choose **Run with PowerShell**. This installs pinned Python dependencies, creates `~/plugins/namecheap-email`, registers it in the default personal marketplace, and activates it in Codex. It requires Python 3.11+ and the Codex command. It detects this computer's bundled Python automatically. If Windows prevents scripts from running, use the one-process command below; it does not change your saved execution policy.
2. Create a dedicated app password in [Private Email webmail](https://privateemail.com/): **Settings → Launch Security Center → App passwords → Create new password**. Name it “Codex read-only email”. Use an app password valid for IMAP. See [Namecheap's current app-password instructions](https://www.namecheap.com/support/knowledgebase/article.aspx/10816/2178/how-to-use-app-passwords-for-private-email/). If your legacy interface differs, consult its account security settings or Namecheap support; do not turn off two-factor authentication.
3. Right-click **Setup Email.ps1** and choose **Run with PowerShell**. Enter the full mailbox email address and app password locally. Where Python's graphical runtime works, the password field is masked; otherwise setup uses the local terminal with password echo disabled (no characters appear as you type). This computer uses the terminal fallback. Leave allowed folders as `INBOX`, or enter specific additional folder names separated by commas. Follow the prompts or click **Test and save securely**. Setup tests TLS, authentication, and each allowed folder before saving. You do not need to give these values to Codex chat.
4. Start a new Codex task so it loads the installed tools. Ask: “Use Namecheap Email to list my 10 newest emails” or “Search my Namecheap inbox for invoices received since September 1.” Read a selected message after searching.

If you need the one-process installer command, open PowerShell in this plugin's folder and run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\Install Plugin.ps1'
```

For the local credential window:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\Setup Email.ps1'
```

The installer preserves an existing plugin and directs you to setup when its runtime is already present. Setup checks both normal LocalAppData and the physical Windows Codex app storage folder, so it works from ordinary PowerShell after an in-app installation. If registration succeeds but activation fails, open the personal plugin page in Codex and install **namecheap-email**. The connection configuration is generated with absolute paths to this computer's runtime and installed source; regenerate it when moving to another computer. The archive contains no mailbox login.

## Connection and permissions

The server is fixed to `mail.privateemail.com`, TCP port `993`, with certificate-verified implicit TLS and TLS 1.2 minimum. The username is the full mailbox email address. This follows [Namecheap's IMAP settings](https://www.namecheap.com/support/knowledgebase/article.aspx/1179/2175/general-private-email-configuration-for-mail-clients-and-mobile-devices/). Namecheap has [legacy Open-Xchange and newer webmail interfaces](https://www.namecheap.com/support/knowledgebase/article.aspx/10818/2178/new-private-email-webmail-heres-what-to-expect/); this plugin uses IMAP rather than depending on either webmail API. cPanel hosting mail is outside this plugin's configuration.

Use a dedicated password for this mailbox, never the Namecheap account administrator password or domain API key. An app password is revocable, but it may authorize additional protocols and mailbox writes at the provider. This plugin cannot reduce those provider permissions. It enforces read-only behavior through `EXAMINE` (read-only folder selection), `BODY.PEEK` (preserves unread status), and an explicit local folder allowlist. There are no send, delete, move, flag-edit, SMTP, or arbitrary IMAP-command tools.

The full configuration is held in **Windows Credential Manager**, using the Windows vault backend directly. It uses the service `Codex.NamecheapEmail.ReadOnly.v1` and account `active-mailbox`. There is one active mailbox. Setup replaces that entry only after successful verification. The plugin does not read other saved credentials. Passwords never go in environment variables, command arguments, `.mcp.json`, source files, email output, or logs. If the vault is unavailable, setup fails without a plaintext fallback. Processes running as your Windows account can access that account's vault; protect your Windows login.

The plugin connects directly from this computer to Namecheap. It does not run a public web server or use a relay. Email content explicitly returned by the tools enters the Codex conversation and is subject to the account's data settings. The plugin does not itself archive messages or create email logs. In-memory message and credential data are not guaranteed to be zeroized by Python.

## Available tools

- `check_connection`: verifies authentication and allowed folders without fetching messages.
- `list_messages`: returns up to 50 message headers, newest UID first, with optional unread filtering and pagination.
- `search_messages`: combines sender, subject, whole-message text, unread, and received-date filters. Text is literal; Unicode is supported using IMAP literals. `since` includes the date and `before` excludes it. Both use `YYYY-MM-DD`. Date filtering uses the server's internal received date.
- `read_message`: requires the UID, UIDVALIDITY and folder returned by list/search. Returns plain text and attachment names. It refuses stale IDs and does not mark messages read.

Limits: 16 KiB headers; 2 MiB complete-message size, including attachments; at most 24,000 returned body characters and 100 attachment entries. Truncation is reported. For larger messages use webmail. HTML is converted to text without loading scripts or remote images. Attachments are not opened, downloaded to disk, or executed, although the bounded raw message fetched into memory can contain attachment bytes. Signed/encrypted messages may require webmail. Folder names must be ASCII or IMAP modified UTF-7 wire names; the setup comma separator cannot represent a folder containing a comma. Broad searches on very large mailboxes may hit server or response limits; narrow the date range.

## Revoke access or update

Run **Setup Email.ps1 → Forget saved login**, or type `FORGET` at the terminal's first prompt, to remove the local entry. Revoke the dedicated app password in Namecheap's Security Center to invalidate it at the provider. Uninstalling or disabling the plugin alone does not revoke that password. The runtime remains under `%LOCALAPPDATA%\NamecheapEmail\runtime` and the source remains under `~/plugins/namecheap-email`.

For code updates, follow the installed Codex plugin-creator skill's update workflow: validate the personal marketplace name, edit the installed source, run its `update_plugin_cachebuster.py` helper, validate the plugin, and reinstall with `codex plugin add namecheap-email@<validated-marketplace-name>`. Start a new task afterward. Do not hand-edit the marketplace during updates.

This package targets local Codex. Using it from a cloud-only ChatGPT session would require a separately deployed, authenticated HTTPS MCP service; this package does not deploy one. Local plugin packaging is documented by [OpenAI](https://developers.openai.com/plugins/build/plugins).

## Verification

See **TEST-RESULTS.md** for the checks completed when this package was built. No real mailbox login was used during development. The setup window performs the remaining live authenticated connection test.

For developers, create a Python environment, install `requirements.txt`, then run:

```powershell
python -B -m unittest discover -s tests -v
python -B tests/smoke_mcp.py
python installer/validate_plugin.py .
```

The `installer` directory includes the original Codex plugin-creator scaffold and validation helpers used to create and register this plugin.
