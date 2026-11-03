# Verification — September 11, 2026

Setup repair: the launcher now checks the physical Windows Codex app storage folder as well as normal LocalAppData. The original lookup caused normal PowerShell to report a missing runtime even though Codex had installed it. Verified the corrected launcher with Windows PowerShell's `-CheckOnly` option from the user's extracted copy, verified safe installer reruns, and refreshed the installed plugin. No credentials were read during these checks.

- 19 automated tests passed: verified TLS settings, folder allowlist, UID pagination, search literals and command-injection rejection, read-only fetches, logout, UIDVALIDITY mismatch, input limits, missing and oversized messages, MIME/HTML conversion, unknown charsets, output truncation, error redaction, fixed server host, credential-storage failure, read-only tool schemas, noninteractive setup refusal, and verification before credential storage.
- Real MCP client/server test passed: initialization, discovery of all four tools, and safe invocation of a tool with invalid input. This did not read credentials or connect to a mailbox.
- Codex plugin manifest validator passed.
- Codex skill validator passed.
- PowerShell installer and launch-script syntax checks passed.
- Live unauthenticated connection to `mail.privateemail.com:993` passed with certificate verification and TLS 1.3. The IMAP greeting and capabilities were received, then the connection was closed without logging in.
- The bundled Python Tk runtime failed to initialize. Setup includes a local-terminal fallback using Python's no-echo password prompt; noninteractive and verification-before-save behavior were tested. Passwords are never accepted through command-line arguments. Graphical setup remains available with a working Tk runtime.

Not yet verified: the user's mailbox login, actual message search/read against that mailbox, and Windows vault storage with the user's credential. These require the user's local setup. Automated mail tests use synthetic fixtures and mock IMAP responses, not the user's mail. Public endpoint connectivity alone does not establish mailbox authentication or folder availability.

Installation on this computer completed: `namecheap-email@personal`, version `0.1.0`, is installed and enabled. The first activation attempt encountered a transient Windows access-denied error; retrying the same activation command succeeded. A final MCP test using the installed copy's actual `.mcp.json` successfully launched its runtime, discovered all four tools, and invoked a safe invalid-input check without accessing credentials. No email password is included in this package.
