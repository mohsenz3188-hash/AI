#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
backup_dir="${NAVA_BACKUP_DIR:-$PWD/backups}"
mkdir -p "$backup_dir"
backup_file="$backup_dir/nava-$(date -u +%Y%m%d-%H%M%S).tar.gz"
# Pause writes so SQLite, its WAL and generated images represent one snapshot.
docker compose stop app >/dev/null
trap 'docker compose start app >/dev/null' EXIT
docker compose run --rm --no-deps -T --entrypoint python app -c 'import sys,tarfile; t=tarfile.open(fileobj=sys.stdout.buffer,mode="w|gz"); t.add("/data",arcname="data"); t.close()' > "$backup_file"
printf 'Backup saved: %s\n' "$backup_file"
