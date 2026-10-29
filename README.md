# Nava AI · نوا

A self-hosted, Persian-first AI workspace for a VPS: streaming conversations,
coding assistance, translation, summarization, text/code attachments, image
generation, private login, persistent history and a downloadable image gallery.

**[راهنمای کامل فارسی و نصب تک‌خطی](README.fa.md)**

Supports Debian/Ubuntu with Docker Compose, IP access over HTTP, or a domain with
automatic HTTPS through Caddy. Text and image providers are configurable. This
is an application that connects to AI models; it does not train or bundle a model.
Language and coding quality depend on your selected model. Generated code is
displayed for review and is not executed on the server.

For a **private GitHub repository**, first upload the source, then replace the
repository address below. Git prompts for your username and a token as the password:

```bash
git -c credential.helper= clone https://github.com/YOUR_USER/nava-ai.git && cd nava-ai && sudo bash install.sh
```

Requires Git, sudo/root, and Ubuntu/Debian. The installer installs Docker if absent,
asks for the public address, admin password and API keys, and starts the service.
Do not put a token in the command URL. `.env` is excluded from Git and Docker images.
An optional hidden-token bootstrap is in `scripts/github-install.sh`.

Tests: `python -m unittest discover -s tests -v`. Provider tests use fixtures and do
not consume API credits. See the Persian guide for limitations, backup/restore,
local models, manual configuration, updates and the API contract.
