#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
trap 'printf "Installation failed. Review the message above; your existing data was retained.\n" >&2' ERR
if [[ ${EUID} -ne 0 ]]; then
  printf 'Run this installer with sudo or as root.\n' >&2
  exit 1
fi
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
install_dir="${NAVA_INSTALL_DIR:-/opt/nava-ai}"
if [[ "$install_dir" != /* || "$install_dir" == / ]]; then
  printf 'NAVA_INSTALL_DIR must be an absolute project directory.\n' >&2
  exit 1
fi
if [[ ! -f /etc/os-release ]]; then
  printf 'This installer supports Ubuntu and Debian. Use Docker Compose manually on other systems.\n' >&2
  exit 1
fi
. /etc/os-release
if [[ "$ID" != ubuntu && "$ID" != debian ]]; then
  printf 'This installer supports Ubuntu and Debian.\n' >&2
  exit 1
fi
if ! command -v python3 >/dev/null || ! command -v curl >/dev/null; then
  apt-get update
  apt-get install -y python3 curl ca-certificates
fi
if ! command -v docker >/dev/null; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL "https://download.docker.com/linux/${ID}/gpg" -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  arch="$(dpkg --print-architecture)"
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/%s %s stable\n' "$arch" "$ID" "$VERSION_CODENAME" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi
if ! docker compose version >/dev/null 2>&1; then
  printf 'Docker exists but the Compose v2 plugin is missing. Install docker-compose-plugin, then rerun.\n' >&2
  exit 1
fi
docker info >/dev/null
install -d -m 0750 "$install_dir"
if [[ "$source_dir" != "$install_dir" ]]; then
  tar -C "$source_dir" -cf - app scripts compose.yaml Dockerfile Caddyfile requirements.txt .dockerignore .env.example README.fa.md LICENSE | tar -C "$install_dir" -xf -
fi
cd "$install_dir"
if [[ ! -f .env ]]; then
  if [[ ! -r /dev/tty ]]; then
    printf 'An interactive terminal is required for first setup.\n' >&2
    exit 1
  fi
  python3 scripts/configure.py .env </dev/tty
else
  printf 'Existing configuration retained.\n'
fi
chmod 600 .env
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 240
printf '\nNava is running. See README.fa.md for DNS, backups and updates.\n'
printf 'The app uses the address entered during setup. Allow inbound TCP 80 and 443 for domain HTTPS.\n'
