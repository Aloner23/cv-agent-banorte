from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.agent import Turn
from app.shared_store import FirestoreResponseStore, StoreUnavailable

ID = 'resp_' + 'a' * 32


def test_two_instances_share_conversation_and_enforce_expiry():
    data = {}
    class Doc:
        def set(self, value, **kwargs):
            assert kwargs == {'timeout': 5, 'retry': None}
            data.update(value)
        def get(self, **kwargs):
            return SimpleNamespace(exists=bool(data), to_dict=lambda: data)
    client = Mock()
    client.collection.return_value.document.return_value = Doc()
    a = FirestoreResponseStore('p', 'db', 'c', 3600, client)
    b = FirestoreResponseStore('p', 'db', 'c', 3600, client)
    turns = [Turn('user', 'Hola'), Turn('assistant', 'Hola Carlos')]
    response = {'output': [{'content': [{'text': 'Hola Carlos'}]}]}
    a.put(ID, turns, response)
    assert b.get(ID) == (turns, response)
    data['expires_at'] = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert b.get(ID) is None  # Firestore todavía no ha eliminado físicamente el documento.


def test_invalid_id_never_reaches_database():
    client = Mock()
    store = FirestoreResponseStore('p', 'db', 'c', 60, client)
    assert store.get('../other/document') is None
    client.collection.return_value.document.assert_not_called()


def test_failure_hides_database_details():
    client = Mock()
    client.collection.return_value.document.return_value.get.side_effect = RuntimeError('sensitive detail')
    store = FirestoreResponseStore('p', 'db', 'c', 60, client)
    with pytest.raises(StoreUnavailable, match='store_unavailable') as exc:
        store.get(ID)
    assert 'sensitive' not in str(exc.value)
