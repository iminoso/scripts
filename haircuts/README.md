# Haircut Availability Monitor

Checks Mark Feolino's 45-minute haircut availability at [Manstop Downtown Duncan, 2nd Floor, Toronto](https://getsquire.com/booking/book/downtown-duncan-2nd-floor-toronto/barber/mark-feolino?brandRoute=manstop-barbershop), every five minutes and sends new openings to your verified Telegram chat.

Browse [Manstop on Squire](https://getsquire.com/booking/book/downtown-duncan-2nd-floor-toronto/barber/mark-feolino?brandRoute=manstop-barbershop) to book a haircut.

## Setup

This directory is a standalone `uv` project. From `scripts/haircuts/`, run:

```sh
uv sync
export TELEGRAM_BOT_TOKEN="your-bot-token"
export TELEGRAM_CHAT_ID="your-chat-id"
```

Keep credentials in your environment; do not commit them. The alert-history file (`barber_alerts.json`) is created locally and is ignored by Git.

## Run the monitor

```sh
uv run main.py --start <start-date> --end <end-date>
```

Replace the placeholders with dates in `YYYY-MM-DD` format.

Pass the inclusive date range with `--start` and `--end` in `YYYY-MM-DD` format; both are required. The monitor checks immediately, then every 300 seconds until Ctrl+C. On startup, it sends a Telegram message with its PID. On normal exit, Ctrl+C, SIGTERM, or an unhandled Python exception, it sends a final “not running” message with the same PID. A forced kill (SIGKILL), power loss, or network outage can prevent the final message from being delivered. All alert times are Toronto time. Keep your computer awake and connected. No ChatGPT usage or email credentials are required.

```sh
uv run main.py --start <start-date> --end <end-date> --once --dry-run
uv run main.py --start <start-date> --end <end-date> --once
uv run main.py --start <start-date> --end <end-date> --test-message
uv run main.py --start <start-date> --end <end-date> "Hello from my bot!"
```

New openings are saved in `barber_alerts.json` after successful Telegram delivery. Restarting does not resend previously alerted slots; a slot that disappears and returns is not alerted again. Existing openings on the first run trigger an alert. Failed checks and sends retry on the next cycle. A partial send or crash before saving can produce duplicate alerts. Only run one monitor at a time.

Past times are excluded. The monitor continues until you stop it, even after the target date range has passed. It does not book appointments; follow the link in the Telegram alert to book.

The Squire request includes the booking page's client headers to avoid the 403 response produced by a plain request.

## Tests

Run the test suite from this directory:

```sh
uv run python -m unittest
```
