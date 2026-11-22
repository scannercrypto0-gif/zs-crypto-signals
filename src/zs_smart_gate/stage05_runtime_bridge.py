"""Durable scanner/Telegram bridge; never turns research into a signal.

The concrete upstream verifier currently admits real-source rejection records
only. Consequently the archive and read-only A/B interaction can be exercised,
while genuine signal delivery remains blocked by the missing qualified verifier.
"""
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from .stage05_contracts import ContractError, canonical, digest, parse_utc
from .stage05_custody import LocalOutbox, VerifiedUpstream
from .stage05_delivery import DeliveryCoordinator, plan
from .stage05_interactive import InteractiveService, respond_once
from .stage05_telegram_http import TelegramHTTP


class TelegramBridge:
    def __init__(self, *, root, config, upstream, references, clock_guard,
                 flags=None, permit=None, head_sha=None, clock=None,
                 transports=None, simulation=False, max_snapshot_age_seconds=120):
        config.validate()
        if type(upstream) is not VerifiedUpstream or not callable(clock_guard):
            raise ContractError('BRIDGE_VERIFIED_SOURCE_AND_CLOCK_REQUIRED')
        if type(max_snapshot_age_seconds) is not int or not 1 <= max_snapshot_age_seconds <= 120:
            raise ContractError('BRIDGE_SNAPSHOT_AGE_INVALID')
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.config, self.upstream = config, upstream
        self.references = dict(references)
        if not self.references:
            raise ContractError('BRIDGE_SOURCE_REFERENCES_REQUIRED')
        self.guard = clock_guard
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.age = max_snapshot_age_seconds
        self.store = LocalOutbox(self.root / 'outbox.sqlite')
        self.simulation = simulation
        self.opts = dict(flags=flags, permit=permit, head_sha=head_sha)
        self.transports = dict(transports or {})
        if not simulation and transports:
            raise ContractError('BRIDGE_LIVE_TRANSPORT_INJECTION_FORBIDDEN')
        if not simulation:
            for role, token in (('SIGNALS', config.signals_token), ('ANALYTICS', config.analytics_token),
                                ('INTERACTIVE', config.interactive_token)):
                self.transports[role] = TelegramHTTP(token, on_attempt=lambda _: self._guard())
        if 'INTERACTIVE' not in self.transports:
            raise ContractError('BRIDGE_INTERACTIVE_TRANSPORT_REQUIRED')
        self.delivery = DeliveryCoordinator(store=self.store, config=config, clock=self.clock,
            transports=self.transports, simulation=simulation, research_test=True, **self.opts)
        self.service = InteractiveService(config=config, supported_symbols=tuple(self.references),
                                          lookup=self._snapshot, clock=self.clock)
        self.cursor = self.root / 'ingress.sqlite'
        with closing(self._db()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS ingress(update_id INTEGER PRIMARY KEY, digest TEXT NOT NULL, disposition TEXT NOT NULL)')
            for action in ('UPDATE', 'DELETE'):
                db.execute(f"CREATE TRIGGER IF NOT EXISTS ingress_no_{action} BEFORE {action} ON ingress BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END")

    def _db(self):
        db = sqlite3.connect(self.cursor, timeout=5)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        return db

    def _guard(self):
        if (self.root / 'STOP_REQUESTED').exists() or self.guard() is not True:
            raise ContractError('BRIDGE_STOP_OR_CLOCK_HOLD')

    def _fresh(self, event):
        age = (self.clock() - parse_utc(event['timestamps']['decision_at'])).total_seconds()
        if not 0 <= age <= self.age:
            raise ContractError('BRIDGE_SOURCE_STALE_OR_FUTURE')

    def dispatch(self, symbol):
        """All destinations follow existing verified qualification, not a caller flag."""
        self._guard()
        ref = self.references[symbol]
        event = self.upstream.read(*ref)
        if event['symbol'] != symbol:
            raise ContractError('BRIDGE_SOURCE_SYMBOL_MISMATCH')
        self._fresh(event)
        outcomes = {}
        for job in plan(event):
            self._guard()
            outcomes[job.destination] = self.delivery.step_verified(self.upstream, *ref, job.destination)
        return dict(candidate_id=event['candidate_id'], signal_id=event['signal_id'],
                    qualification=event['qualification_status'], destinations=outcomes)

    def _snapshot(self, symbol):
        ref = self.references.get(symbol)
        if ref is None:
            return None
        event = self.upstream.read(*ref)
        self._fresh(event)
        return self.upstream.snapshot(*ref, symbol)

    def poll_once(self):
        """Advance acknowledgment only after a durable terminal per-update record.

        An uncertain send is terminal for automatic retry, not successful delivery.
        The existing outbox claim survives crashes before ingress commit.
        """
        self._guard()
        with closing(self._db()) as db:
            offset = db.execute('SELECT COALESCE(MAX(update_id)+1,0) FROM ingress').fetchone()[0]
        result = self.transports['INTERACTIVE'].get_updates(offset=offset, **self.opts)
        if result.status != 'ACCEPTED':
            return dict(status=result.status, processed=0, replies=[])
        if len(result.updates) > 20:
            raise ContractError('BRIDGE_UPDATE_BATCH_TOO_LARGE')
        rows = list(result.updates)
        if any(not isinstance(row, dict) or type(row.get('update_id')) is not int
               or row['update_id'] < 0 or row['update_id'] >= 2**63-1 for row in rows):
            raise ContractError('BRIDGE_UPDATE_ID_INVALID')
        replies = []
        for update in sorted(rows, key=lambda row: row['update_id']):
            self._guard()
            uid = update['update_id']
            pin = digest(canonical(update))
            with closing(self._db()) as db:
                old = db.execute('SELECT digest FROM ingress WHERE update_id=?', (uid,)).fetchone()
            if old:
                if old[0] != pin:
                    raise ContractError('BRIDGE_UPDATE_CONFLICT')
                continue
            state = 'IGNORED'
            message = update.get('message', {})
            if isinstance(message, dict):
                sender, chat = message.get('from', {}), message.get('chat', {})
                stamp = message.get('date')
                fresh_message = (type(stamp) is int and 0 <= self.clock().timestamp()-stamp <= 120)
                if (isinstance(sender, dict) and isinstance(chat, dict)
                        and fresh_message and not sender.get('is_bot') and chat.get('type') == 'private'):
                    # No account identifier is placed in public runtime summaries.
                    service = self.service
                    request = service.accept(text=message.get('text'), user_id=sender.get('id'),
                        chat_id=chat.get('id'), message_id=message.get('message_id'))
                    state = request['status']
                    if state == 'QUEUED':
                        response = service.process_one()
                        response['reply_text'] = 'TEST / RESEARCH ONLY / NOT A TRADING SIGNAL\n' + service.format_reply(response)
                        if len(response['reply_text']) > 3900:
                            raise ContractError('BRIDGE_REPLY_TOO_LONG')
                        self._guard()
                        receipt = respond_once(response=response, chat_id=chat['id'], user_id=sender['id'],
                            config=self.config, store=self.store, clock=self.clock, simulation=self.simulation,
                            transport=self.transports['INTERACTIVE'], reply_to=message['message_id'], **self.opts)
                        state = receipt['status']
                        replies.append(dict(status=state, delivery_id=receipt['delivery_id']))
            with closing(self._db()) as db, db:
                db.execute('INSERT INTO ingress VALUES(?,?,?)', (uid, pin, state))
        return dict(status='ACCEPTED', processed=len(rows), replies=replies)
