#!/bin/sh
set -eu

# Requires Ardia running with its CLI installed. No account or login needed.
# Usage: sh check-uscis-status.sh IOE0939126117
receipt=${1:?Usage: check-uscis-status.sh RECEIPT_NUMBER}
if ! printf '%s\n' "$receipt" | LC_ALL=C grep -Eq '^[A-Z]{3}[0-9]{10}$'; then
  printf '%s\n' 'Expected three uppercase letters followed by ten digits.' >&2
  exit 2
fi

ardia browse open https://egov.uscis.gov/ >/dev/null
result=$(ardia browse batch --bail <<EOF
find label "Enter a Receipt Number" fill "$receipt"
find role button click --name "Check Status"
read -s '#main-content-sec'
EOF
)
printf '%s\n' "$result"

# Telegram notifications are optional. Set both variables to enable them.
if [ "${TELEGRAM_BOT_TOKEN:-}" ] || [ "${TELEGRAM_CHAT_ID:-}" ]; then
  if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ]; then
    printf '%s\n' 'Set both TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to send notifications.' >&2
    exit 2
  fi
  message=$(printf 'USCIS status for %s:\n%s' "$receipt" "$result")
  curl --fail-with-body --silent --show-error \
    --request POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${message}" >/dev/null
fi
