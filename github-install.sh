#!/usr/bin/env bash
# Optional private-repository bootstrap, distributed in the source ZIP.
# Usage: bash scripts/github-install.sh OWNER/REPO [BRANCH]
set -Eeuo pipefail
umask 077
repository="${1:?Pass OWNER/REPO}"
branch="${2:-main}"
[[ "$repository" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { printf 'Invalid repository.\n' >&2; exit 1; }
[[ "$branch" =~ ^[A-Za-z0-9_./-]+$ && "$branch" != -* ]] || { printf 'Invalid branch.\n' >&2; exit 1; }
command -v git >/dev/null || { printf 'Install git first.\n' >&2; exit 1; }
token_dir="$(mktemp -d)"
trap 'rm -rf -- "$token_dir"; unset GITHUB_TOKEN' EXIT
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  read -r -s -p 'GitHub token with read access to this repository: ' GITHUB_TOKEN </dev/tty
  printf '\n'
fi
[[ -n "$GITHUB_TOKEN" ]] || { printf 'A token is required for a private repository.\n' >&2; exit 1; }
export GITHUB_TOKEN
cat > "$token_dir/askpass" <<'ASKPASS'
#!/usr/bin/env bash
case "$1" in
  *Username*) printf '%s\n' 'x-access-token' ;;
  *Password*) printf '%s\n' "$GITHUB_TOKEN" ;;
  *) exit 1 ;;
esac
ASKPASS
chmod 700 "$token_dir/askpass"
GIT_ASKPASS="$token_dir/askpass" GIT_TERMINAL_PROMPT=0 git -c credential.helper= clone --depth 1 --branch "$branch" "https://github.com/${repository}.git" "$token_dir/source"
unset GITHUB_TOKEN
if [[ ${EUID} -eq 0 ]]; then
  bash "$token_dir/source/install.sh"
else
  sudo bash "$token_dir/source/install.sh"
fi
