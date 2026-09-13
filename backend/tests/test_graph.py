import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
import json
from app.services.graph import build_relationship_graph

@pytest.mark.asyncio
async def test_build_relationship_graph():
    user_id = str(uuid.uuid4())
    chat_id = str(uuid.uuid4())
    p1 = str(uuid.uuid4())
    p2 = str(uuid.uuid4())
    p3 = str(uuid.uuid4())
    
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    
    # Mock people records
    mock_conn.fetch.side_effect = [
        [
            {"id": p1, "canonical_name": "Alice", "profile": json.dumps({"roles": ["leader"]})},
            {"id": p2, "canonical_name": "Bob", "profile": None},
            {"id": p3, "canonical_name": "Charlie", "profile": None},
        ],
        # Mock co-occurrence records
        [
            {"p1": p1, "p2": p2, "weight": 2},
            {"p1": p2, "p2": p3, "weight": 1},
        ]
    ]
    
    graph = await build_relationship_graph(mock_pool, user_id, chat_id)
    
    assert len(graph["nodes"]) == 3
    alice_node = next(n for n in graph["nodes"] if n["label"] == "Alice")
    assert alice_node["profile"] == {"roles": ["leader"]}
    
    assert len(graph["edges"]) == 2
    
    assert any(e["source"] == p1 and e["target"] == p2 for e in graph["edges"]) or any(e["source"] == p2 and e["target"] == p1 for e in graph["edges"])
    assert any(e["source"] == p2 and e["target"] == p3 for e in graph["edges"]) or any(e["source"] == p3 and e["target"] == p2 for e in graph["edges"])
    assert not (any(e["source"] == p1 and e["target"] == p3 for e in graph["edges"]) or any(e["source"] == p3 and e["target"] == p1 for e in graph["edges"]))
