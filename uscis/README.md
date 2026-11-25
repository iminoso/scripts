# USCIS status check

`check-uscis-status.sh` opens USCIS in your running Ardia browser, submits a receipt number, and prints the status text returned from the page. It performs a one-time check; it does not poll for changes.

## Requirements

- Ardia running with its CLI installed and accessible as `ardia`.
- `curl` (only needed for Telegram notifications; available by default on macOS).

## Run

From this directory:

```sh
sh check-uscis-status.sh IOE0939126117
```

The receipt number must contain three uppercase letters followed by ten digits.

## Optional Telegram notification

Set the bot token and destination chat ID in your environment to send each successful check's result to Telegram:

```sh
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
sh check-uscis-status.sh IOE0939126117
```

If neither variable is set, the script only prints the result. If only one is set, it exits with an error. Keep credentials out of the repository. The receipt number and returned status are included in the Telegram message when notifications are enabled.
