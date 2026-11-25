#!/usr/bin/env python3
"""Check Mark Feolino every five minutes and send Telegram alerts for new openings."""
import argparse
import atexit
import json
import os
from pathlib import Path
import requests
import signal
import sys
import time
from datetime import date, datetime, timedelta
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

BARBER_ID = '1dbb97ce-4671-40f7-874c-0225cec547f1'
TORONTO = ZoneInfo('America/Toronto')
BOOKING = ('https://getsquire.com/booking/book/downtown-duncan-2nd-floor-toronto/'
           'barber/mark-feolino?brandRoute=manstop-barbershop')
CHECK_INTERVAL = 300


def fetch_openings(start, end):
    days = {}
    while start <= end:
        chunk_end = min(start + timedelta(days=27), end)
        url = (f'https://api.getsquire.com/v1/barber/{BARBER_ID}/'
               f'schedule-time-range/{start}/{chunk_end}/45')
        with urlopen(Request(url, headers={
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0',
                'Origin': 'https://getsquire.com',
                'Referer': 'https://getsquire.com/',
                'x-client-app': 'squire-mobile-flagship',
                'x-client-platform': 'web',
                'x-client-surface': 'mobile_web',
                'x-client-version': '3.22.0',
        }), timeout=30) as response:
            payload = json.load(response)
        if not isinstance(payload, list):
            raise ValueError('Unexpected API response: expected a list of days')
        for day in payload:
            days[day['day']] = day
        start = chunk_end + timedelta(days=1)
    return days


def collect_openings(days, start, end, now):
    openings = set()
    current = start
    while current <= end:
        day = days.get(current.isoformat())
        if day is None:
            raise ValueError(f'API omitted {current}; availability is unknown')
        for group in day['times'].values():
            for slot in group:
                if slot.get('available') is True:
                    instant = datetime.fromisoformat(slot['time'].replace('Z', '+00:00'))
                    if instant > now:
                        openings.add(instant.astimezone(TORONTO).isoformat())
        current += timedelta(days=1)
    return openings


def describe(slots):
    return '\n'.join(datetime.fromisoformat(slot).strftime('%a, %b %d, %Y at %I:%M %p')
                     for slot in sorted(slots))


API_URL = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(token: str, chat_id: str, text: str) -> None:
    """Send *text* to a Telegram chat and raise for an unsuccessful response."""
    response = requests.get(
        API_URL.format(token=token),
        params={"chat_id": chat_id, "text": text},
        timeout=10,
    )
    response.raise_for_status()

    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError("Telegram rejected the message")



def send_alert(slots, token, chat_id):
    # Stay below Telegram's message size limit. Record delivery only after all
    # chunks succeed; a partial failure may repeat earlier chunks on retry.
    lines = sorted(slots)
    for offset in range(0, len(lines), 40):
        text = ('New 45-minute haircut openings with Mark Feolino at Manstop '
                '(Downtown Duncan 2nd Floor).\n\nAll times Toronto:\n'
                + describe(lines[offset:offset + 40]) + '\n\nBook here: ' + BOOKING)
        send_message(token, chat_id, text)


def check_availability(args, token, chat_id, saved, notified):
    """Check for openings, notify about new slots, and persist sent alerts."""
    now = datetime.now(TORONTO)
    slots = collect_openings(fetch_openings(args.start, args.end), args.start, args.end, now)
    new = slots - notified
    print(f'[{now.isoformat(timespec="seconds")}] {len(slots)} openings; {len(new)} new.', flush=True)

    if new:
        print(describe(new), flush=True)
        if not args.dry_run:
            send_alert(new, token, chat_id)
            notified.update(new)
            saved[chat_id] = sorted(notified)
            temporary = args.state.with_suffix('.tmp')
            temporary.write_text(json.dumps(saved, indent=2) + '\n')
            temporary.replace(args.state)
            print('Telegram alert sent.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=date.fromisoformat, required=True,
                        help='First date to check (YYYY-MM-DD)')
    parser.add_argument('--end', type=date.fromisoformat, required=True,
                        help='Last date to check (YYYY-MM-DD)')
    parser.add_argument('text', nargs='?', help='Send this Telegram message and exit')
    parser.add_argument('--test-message', action='store_true',
                        help='Send one Telegram test message and exit')
    parser.add_argument('--once', action='store_true', help='Check once and exit')
    parser.add_argument('--dry-run', action='store_true', help='Print openings without sending or saving alerts')
    parser.add_argument('--state', type=Path, default=Path(__file__).with_name('barber_alerts.json'))
    args = parser.parse_args()
    if args.test_message and args.dry_run:
        parser.error('--test-message cannot be combined with --dry-run')
    if args.start > args.end:
        parser.error('--start must be on or before --end')
    token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    if args.text and args.dry_run:
        parser.error('text cannot be combined with --dry-run')
    if not args.dry_run and not (token and chat_id):
        parser.error('Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID before running')
    if args.test_message or args.text:
        try:
            send_message(token, chat_id, args.text or 'Barber alerts: Telegram notifications are working.')
        except (OSError, ValueError, requests.RequestException, RuntimeError) as exc:
            print(f'Telegram message failed ({type(exc).__name__}). Check credentials and connectivity.', file=sys.stderr)
            return 1
        print('Telegram message sent.')
        return 0
    # Only record a slot after successful Telegram delivery. Preserve history across restarts.
    try:
        saved = json.loads(args.state.read_text()) if args.state.exists() else {}
        if not isinstance(saved, dict) or not all(isinstance(v, list) for v in saved.values()):
            raise ValueError('invalid alert state')
        notified = set(saved.get(chat_id, []))
    except (OSError, ValueError, TypeError) as exc:
        parser.error(f'Cannot read alert history: {exc}')
    pid = os.getpid()
    if not args.dry_run:
        send_message(token, chat_id, f'Haircut availability monitor started. PID: {pid}.')
        atexit.register(
            send_message, token, chat_id,
            f'Haircut availability monitor is not running. PID: {pid}.'
        )
        for sig in (signal.SIGTERM,):
            signal.signal(sig, lambda signum, frame: sys.exit(128 + signum))
    print(f'Watching Mark Feolino, {args.start} through {args.end}; every 5 minutes. PID: {pid}', flush=True)
    try:
        while True:
            started = time.monotonic()
            try:
                check_availability(args, token, chat_id, saved, notified)
            except (OSError, ValueError, KeyError, TypeError, requests.RequestException, RuntimeError) as exc:
                suffix = '' if args.once else '; will retry in five minutes'
                detail = type(exc).__name__ if isinstance(exc, requests.RequestException) else str(exc)
                print(f'Check failed{suffix}: {detail}', file=sys.stderr, flush=True)
                if args.once:
                    return 1

            if args.once:
                return 0
            remaining = CHECK_INTERVAL - (time.monotonic() - started)
            time.sleep(max(0, remaining))
    except KeyboardInterrupt:
        print('\nStopped.', flush=True)
        return 0


if __name__ == '__main__':
    sys.exit(main())
