#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${1:-${repo_root}/.env.production}"
default_username="info@helveticlens.ch"

if [[ ! -f "${env_file}" ]]; then
  printf 'Environment file not found: %s\n' "${env_file}" >&2
  exit 1
fi

printf 'SMTP username [%s]: ' "${default_username}" >&2
IFS= read -r smtp_username
smtp_username="${smtp_username:-${default_username}}"

printf 'SMTP device password (input hidden): ' >&2
IFS= read -r -s smtp_password
printf '\nRepeat SMTP device password: ' >&2
IFS= read -r -s smtp_password_confirmation
printf '\n' >&2

if [[ -z "${smtp_password}" ]]; then
  printf 'The password was empty; nothing was changed.\n' >&2
  exit 1
fi

if [[ "${smtp_password}" != "${smtp_password_confirmation}" ]]; then
  printf 'The passwords did not match; nothing was changed.\n' >&2
  exit 1
fi

# Compose treats single-quoted .env values literally. Escape only a literal
# single quote so characters such as $, #, %, &, and backslashes stay intact.
quoted_username="${smtp_username//\'/\\\'}"
quoted_password="${smtp_password//\'/\\\'}"

umask 077
temporary_file="$(mktemp "${env_file}.tmp.XXXXXX")"
trap 'rm -f "${temporary_file}"' EXIT

found_username=false
found_password=false
while IFS= read -r line || [[ -n "${line}" ]]; do
  case "${line}" in
    AUTH_SMTP_USERNAME=*)
      printf "AUTH_SMTP_USERNAME='%s'\n" "${quoted_username}" >> "${temporary_file}"
      found_username=true
      ;;
    AUTH_SMTP_PASSWORD=*)
      printf "AUTH_SMTP_PASSWORD='%s'\n" "${quoted_password}" >> "${temporary_file}"
      found_password=true
      ;;
    *)
      printf '%s\n' "${line}" >> "${temporary_file}"
      ;;
  esac
done < "${env_file}"

if [[ "${found_username}" != true || "${found_password}" != true ]]; then
  printf 'SMTP fields are missing from %s; nothing was changed.\n' "${env_file}" >&2
  exit 1
fi

chmod 600 "${temporary_file}"
mv -f "${temporary_file}" "${env_file}"
trap - EXIT

unset smtp_password smtp_password_confirmation quoted_password
printf 'SMTP credentials saved securely in %s.\n' "${env_file}"
