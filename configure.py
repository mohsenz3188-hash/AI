#!/usr/bin/env python3
"""Interactive configuration; credentials are never echoed or committed."""
import getpass
import ipaddress
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.security import hash_password  # noqa: E402


def address(value):
    value = value.strip().rstrip("/")
    value = re.sub(r"^https?://", "", value)
    try:
        ip = ipaddress.ip_address(value.strip("[]"))
        host = f"[{ip}]" if ip.version == 6 else str(ip)
        return "http://:80", f"http://{host}", "false"
    except ValueError:
        if value == "localhost":
            return "http://:80", "http://localhost", "false"
        host = value.encode("idna").decode("ascii").lower()
        if len(host) > 253 or "." not in host or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part) for part in host.split(".")):
            raise ValueError("Enter a valid IP or domain without a path or port.")
        return host, f"https://{host}", "true"


def env_value(value):
    if any(c in value for c in "\r\n\x00"):
        raise ValueError("Multiline settings are not accepted.")
    # Compose single quotes keep dollar signs literal.
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main():
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else ".env")
    if destination.exists():
        raise SystemExit("Configuration already exists; edit it to preserve your settings.")
    print("Nava AI setup / راه‌اندازی نوا")
    while True:
        try:
            site, origin, secure = address(input("Server IP or domain / آدرس سرور یا دامنه: "))
            break
        except (ValueError, UnicodeError) as exc:
            print(str(exc))
    username = input("Admin username [admin]: ").strip() or "admin"
    if len(username) > 100:
        raise SystemExit("Username is too long.")
    while True:
        password = getpass.getpass("Admin password (12+ characters): ")
        if not 12 <= len(password) <= 256:
            print("Use 12 to 256 characters.")
            continue
        if password == getpass.getpass("Repeat password: "):
            break
        print("Passwords do not match.")
    api_key = getpass.getpass("Text API key (hidden; blank configures it later): ").strip()
    api_base = input("Text API base [https://api.openai.com/v1]: ").strip() or "https://api.openai.com/v1"
    models = input("Chat models, comma separated [gpt-4.1-mini,gpt-4.1]: ").strip() or "gpt-4.1-mini,gpt-4.1"
    image_key = getpass.getpass("Image API key (hidden; blank uses text key): ").strip()
    image_base = input("Image API base [https://api.openai.com/v1]: ").strip() or "https://api.openai.com/v1"
    image_model = input("Image model [gpt-image-1]: ").strip() or "gpt-image-1"
    values = {"ADMIN_USERNAME": username, "ADMIN_PASSWORD_HASH": hash_password(password), "SITE_ADDRESS": site, "APP_ORIGINS": origin, "COOKIE_SECURE": secure, "OPENAI_BASE_URL": api_base, "OPENAI_API_KEY": api_key, "CHAT_MODELS": models, "IMAGE_BASE_URL": image_base, "IMAGE_API_KEY": image_key, "IMAGE_MODEL": image_model, "MAX_OUTPUT_TOKENS": "4096"}
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write("# Private server configuration. Never commit this file.\n")
        out.writelines(f"{key}={env_value(value)}\n" for key, value in values.items())
    print(f"Configuration saved. Public address: {origin}")
    if secure == "false":
        print("IP mode uses HTTP. Configure a domain for encrypted HTTPS access.")


if __name__ == "__main__":
    main()
