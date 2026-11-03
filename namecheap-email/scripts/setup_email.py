"""Interactive local setup. Never accepts passwords on the command line."""
import threading
import tkinter as tk
from tkinter import messagebox
import getpass
import sys
import warnings
import mail_core as core


def main():
    root = tk.Tk()
    root.title("Namecheap Email — secure local setup")
    root.geometry("620x470")
    root.resizable(False, False)
    frame = tk.Frame(root, padx=24, pady=20)
    frame.pack(fill="both", expand=True)
    tk.Label(frame, text="Read your Namecheap Private Email", font=("Segoe UI", 15, "bold")).pack(anchor="w")
    tk.Label(frame, text="Connects only to mail.privateemail.com:993 with verified TLS.\n"
             "Saved in Windows Credential Manager for this Windows account.", justify="left").pack(anchor="w", pady=8)
    entries = {}
    for key, label, initial in (("username", "Full mailbox email address", ""),
                                ("password", "Dedicated app password (hidden)", ""),
                                ("folders", "Allowed folders, separated by commas", "INBOX")):
        tk.Label(frame, text=label).pack(anchor="w")
        entry = tk.Entry(frame, width=75, show="*" if key == "password" else "")
        entry.insert(0, initial)
        entry.pack(anchor="w", pady=(0, 8))
        entries[key] = entry
    status = tk.StringVar(value="The connection test reads no message bodies and changes no message flags.")
    tk.Label(frame, textvariable=status, wraplength=560, justify="left").pack(anchor="w", pady=8)
    buttons = tk.Frame(frame)
    buttons.pack(anchor="w")

    def finish(error):
        save_button.config(state="normal")
        forget_button.config(state="normal")
        if error:
            status.set(error)
        else:
            entries["password"].delete(0, tk.END)
            status.set("Connected and saved. You may close this window and use the plugin.")

    def save():
        config = {"host": core.HOST, "port": core.PORT,
                  "username": entries["username"].get().strip(),
                  "password": entries["password"].get(),
                  "folders": list(dict.fromkeys(s.strip() for s in entries["folders"].get().split(",") if s.strip()))}
        try:
            core.validate_config(config)
        except core.MailError as exc:
            status.set(str(exc))
            return
        save_button.config(state="disabled")
        forget_button.config(state="disabled")
        status.set("Testing the secure connection…")

        def worker():
            error = None
            try:
                core.check_connection(config)
                core.save_config(config)
            except core.MailError as exc:
                error = str(exc)
            except Exception:
                error = "Setup failed safely. Verify the account details and try again."
            finally:
                config["password"] = ""
            try:
                root.after(0, finish, error)
            except RuntimeError:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def forget():
        if messagebox.askyesno("Forget local login", "Remove this plugin's saved login from Windows Credential Manager?"):
            try:
                core.forget_config()
                entries["password"].delete(0, tk.END)
                status.set("Local login removed. Revoke the app password in Namecheap to invalidate it there too.")
            except core.MailError as exc:
                status.set(str(exc))

    save_button = tk.Button(buttons, text="Test and save securely", command=save)
    save_button.pack(side="left", padx=(0, 12))
    forget_button = tk.Button(buttons, text="Forget saved login", command=forget)
    forget_button.pack(side="left")
    root.mainloop()


def console_setup():
    # Some bundled Python distributions contain unusable Tcl runtimes. Use a
    # real local terminal and fail closed if getpass cannot suppress echo.
    if not sys.stdin.isatty():
        print("Open Setup Email.ps1 in a local PowerShell window to configure the login.")
        return
    print("Namecheap Private Email — local secure setup")
    print("The password will not be displayed or written to a file.")
    choice = input("Press Enter to connect, or type FORGET to remove the saved login: ").strip()
    if choice == "FORGET":
        core.forget_config()
        print("Local login removed. Revoke the app password in Namecheap to invalidate it there too.")
        return
    username = input("Full mailbox email address: ").strip()
    folders = input("Allowed folders, comma separated [INBOX]: ").strip() or "INBOX"
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        password = getpass.getpass("Dedicated app password (hidden): ")
    config = {"host": core.HOST, "port": core.PORT, "username": username,
              "password": password, "folders": list(dict.fromkeys(s.strip() for s in folders.split(",") if s.strip()))}
    try:
        core.check_connection(config)
        core.save_config(config)
        print("Connected and saved securely in Windows Credential Manager.")
    finally:
        config["password"] = ""
        password = ""


if __name__ == "__main__":
    try:
        try:
            main()
        except tk.TclError:
            console_setup()
    except core.MailError as exc:
        print(str(exc))
    except (KeyboardInterrupt, EOFError):
        print("Setup cancelled.")
    except Exception:
        print("Local setup could not complete safely. No plaintext fallback was used.")
