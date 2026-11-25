import contextlib
from datetime import date, datetime
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import main as bot


class MonitorTests(unittest.TestCase):
    def test_filters_slots_and_converts_to_toronto(self):
        payload = {'2026-12-04': {'times': {'evening': [
            {'time': '2026-12-04T23:00:00Z', 'available': True},
            {'time': '2026-12-04T23:00:00Z', 'available': True},
            {'time': '2026-12-04T23:45:00Z', 'available': False},
        ]}}}
        slots = bot.collect_openings(payload, date(2026, 12, 4), date(2026, 12, 4),
                                     datetime(2026, 11, 16, tzinfo=bot.TORONTO))
        self.assertEqual(slots, {'2026-12-04T18:00:00-05:00'})

    def test_alert_history_and_failed_delivery(self):
        slots = {'2026-12-04T18:00:00-05:00'}
        with tempfile.TemporaryDirectory() as folder:
            state = Path(folder) / 'state.json'
            argv = ['main.py', '--once', '--start', '2026-11-27', '--end',
                    '2026-12-04', '--state', str(state)]
            with patch.dict(os.environ, TELEGRAM_BOT_TOKEN='fake', TELEGRAM_CHAT_ID='123'), \
                 patch('sys.argv', argv), patch.object(bot, 'fetch_openings', return_value={}), \
                 patch.object(bot, 'collect_openings', return_value=slots), \
                 patch.object(bot, 'send_alert') as send, \
                 patch.object(bot, 'send_message'), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                send.side_effect = RuntimeError('failed')
                self.assertEqual(bot.main(), 1)
                self.assertFalse(state.exists())
                send.side_effect = None
                self.assertEqual(bot.main(), 0)
                self.assertEqual(json.loads(state.read_text()), {'123': sorted(slots)})
                send.reset_mock()
                self.assertEqual(bot.main(), 0)
                send.assert_not_called()

    def test_telegram_alert_contains_booking_link(self):
        with patch.object(bot, 'send_message') as send:
            bot.send_alert({'2026-12-04T18:00:00-05:00'}, 'fake', '123')
            text = send.call_args.args[2]
            self.assertIn('06:00 PM', text)
            self.assertIn(bot.BOOKING, text)


if __name__ == '__main__':
    unittest.main()
