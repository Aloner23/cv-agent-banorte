"""Almacén compartido opcional. ADC usa la identidad de Cloud Run, sin key JSON.

El TTL se comprueba al leer: la limpieza física de Firestore es asíncrona.
Los documentos guardan conversación y respuesta; store=false evita escribirlos.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from .agent import Turn


class StoreUnavailable(Exception):
    pass


class FirestoreResponseStore:
    def __init__(self, project: str, database: str, collection: str, ttl_s: int, client=None):
        if client is None:
            from google.cloud import firestore
            client = firestore.Client(project=project, database=database)
        self.collection = client.collection(collection)
        self.ttl = ttl_s

    def put(self, resp_id: str, turns: list[Turn], response: dict) -> None:
        # JSON evita índices sobre el contenido conversacional y arrays anidados.
        payload = json.dumps({'turns': [asdict(t) for t in turns], 'response': response}, ensure_ascii=False)
        if len(payload.encode()) > 800_000:
            raise StoreUnavailable('response_too_large')
        try:
            self.collection.document(resp_id).set({
                'payload': payload,
                'expires_at': datetime.now(timezone.utc) + timedelta(seconds=self.ttl),
            }, timeout=5, retry=None)
        except Exception:
            raise StoreUnavailable('store_unavailable') from None

    def get(self, resp_id: str) -> tuple[list[Turn], dict] | None:
        if not re.fullmatch(r'resp_[0-9a-f]{32}', resp_id):
            return None
        try:
            doc = self.collection.document(resp_id).get(timeout=5, retry=None)
            if not doc.exists:
                return None
            data = doc.to_dict()
            if data['expires_at'] <= datetime.now(timezone.utc):
                return None
            payload = json.loads(data['payload'])
            return [Turn(**t) for t in payload['turns']], payload['response']
        except Exception:
            raise StoreUnavailable('store_unavailable') from None
