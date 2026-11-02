"""Public demo: narrow input contract and atomic, shared model-attempt quotas.

No browser credential, no stored conversations, no access to protected responses.
The single quota document stores counters only; failed attempts are not refunded.
"""
import time
from threading import Lock

from .shared_store import StoreUnavailable


class DemoLimit(Exception):
    def __init__(self, retry_after):
        self.retry_after = retry_after


def reserve(data, now, daily_limit, minute_limit):
    day, minute = int(now // 86400), int(now // 60)
    daily = data.get('daily', 0) if data.get('day') == day else 0
    recent = data.get('recent', 0) if data.get('minute') == minute else 0
    if daily >= daily_limit:
        raise DemoLimit(max(1, int((day + 1) * 86400 - now)))
    if recent >= minute_limit:
        raise DemoLimit(max(1, int((minute + 1) * 60 - now)))
    return dict(day=day, minute=minute, daily=daily + 1, recent=recent + 1)


class DemoQuota:
    def __init__(self, daily, minute, client=None):
        self.daily, self.minute, self.client = daily, minute, client
        self.data = {}
        self.lock = Lock()

    def consume(self):
        now = time.time()
        if self.client is None:
            # Development only. Production uses the named Firestore database.
            with self.lock:
                self.data = reserve(self.data, now, self.daily, self.minute)
            return
        from google.cloud import firestore
        ref = self.client.collection('cv_demo_control').document('quota')

        @firestore.transactional
        def consume_shared(transaction):
            snapshot = ref.get(transaction=transaction, timeout=5, retry=None)
            data = snapshot.to_dict() if snapshot.exists else {}
            updated = reserve(data, now, self.daily, self.minute)
            transaction.set(ref, updated)

        try:
            consume_shared(self.client.transaction(max_attempts=3))
        except DemoLimit:
            raise
        except Exception:
            # Never fall back to per-instance counters on a database failure.
            raise StoreUnavailable('demo_quota_unavailable') from None


def demo_body(payload):
    if not isinstance(payload, dict) or set(payload) - {'message', 'history'}:
        raise ValueError('Envía únicamente message e history.')
    message, history = payload.get('message'), payload.get('history', [])
    if not isinstance(message, str) or not message.strip() or len(message) > 1500:
        raise ValueError('Escribe una pregunta de 1 a 1500 caracteres.')
    if not isinstance(history, list) or len(history) > 8 or len(history) % 2:
        raise ValueError('El historial admite hasta cuatro intercambios completos.')
    for i, turn in enumerate(history):
        if (not isinstance(turn, dict) or set(turn) != {'role', 'content'}
                or turn['role'] != ('user' if i % 2 == 0 else 'assistant')
                or not isinstance(turn['content'], str) or not turn['content'].strip()):
            raise ValueError('Historial inválido.')
    if sum(len(t['content']) for t in history) > 8000:
        raise ValueError('El historial es demasiado largo. Inicia otra conversación.')
    return {'input': history + [{'role': 'user', 'content': message}], 'store': False,
            'stream': False, 'max_output_tokens': 450, 'temperature': 0.2,
            'metadata': {'citations': 'inline'}}
