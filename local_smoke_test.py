# local_smoke_test.py
import json
from pathlib import Path
from fastapi.testclient import TestClient
from bot import app
import compose_engine

def run_tests():
    print("Running local smoke tests...")
    
    # 1. Test compose engine functionality
    data_dir = Path("expanded")
    if not data_dir.exists():
        print("expanded directory not found. Please run generate_dataset.py first.")
        return False
        
    print("Loading test data...")
    # Load sample categories, merchant, trigger
    with open(data_dir / "categories" / "dentists.json", encoding="utf-8") as f:
        category = json.load(f)
    with open(data_dir / "merchants" / "m_001_drmeera_dentist_delhi.json", encoding="utf-8") as f:
        merchant = json.load(f)
    with open(data_dir / "triggers" / "trg_001_research_digest_dentists.json", encoding="utf-8") as f:
        trigger = json.load(f)
    with open(data_dir / "customers" / "c_001_priya_for_m001.json", encoding="utf-8") as f:
        customer = json.load(f)

    print("Testing compose_engine.compose...")
    res = compose_engine.compose(category, merchant, trigger, None)
    assert res is not None
    assert "body" in res
    assert "cta" in res
    assert "JIDA" in res["body"]
    print("  compose success!")

    print("Testing compose_engine.compose_reply...")
    conv = {"auto_reply_count": 0, "turns": []}
    reply_res = compose_engine.compose_reply(conv, category, merchant, trigger, "Yes, please do it", 2, None)
    assert reply_res is not None
    assert reply_res["action"] == "send"
    assert "Draft ready" in reply_res["body"]
    print("  compose_reply success!")

    # 2. Test API endpoints using TestClient
    print("Testing API endpoints via TestClient...")
    client = TestClient(app)

    # Test GET /
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    print("  GET / success!")

    # Test GET /v1/healthz
    r = client.get("/v1/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    print("  GET /v1/healthz success!")

    # Test GET /v1/metadata
    r = client.get("/v1/metadata")
    assert r.status_code == 200
    assert "team_name" in r.json()
    print("  GET /v1/metadata success!")

    # Test POST /v1/context (Category)
    r = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": category,
        "delivered_at": "2026-04-26T10:00:00Z"
    })
    assert r.status_code == 200
    assert r.json()["accepted"] is True
    print("  POST /v1/context category success!")

    # Test POST /v1/context (Merchant)
    r = client.post("/v1/context", json={
        "scope": "merchant",
        "context_id": "m_001_drmeera_dentist_delhi",
        "version": 1,
        "payload": merchant,
        "delivered_at": "2026-04-26T10:00:00Z"
    })
    assert r.status_code == 200
    assert r.json()["accepted"] is True
    print("  POST /v1/context merchant success!")

    # Test POST /v1/context (Trigger)
    r = client.post("/v1/context", json={
        "scope": "trigger",
        "context_id": trigger["id"],
        "version": 1,
        "payload": trigger,
        "delivered_at": "2026-04-26T10:00:00Z"
    })
    assert r.status_code == 200
    assert r.json()["accepted"] is True
    print("  POST /v1/context trigger success!")

    # Test POST /v1/tick
    r = client.post("/v1/tick", json={
        "now": "2026-04-26T10:05:00Z",
        "available_triggers": [trigger["id"]]
    })
    assert r.status_code == 200
    actions = r.json().get("actions", [])
    assert len(actions) == 1
    assert actions[0]["merchant_id"] == "m_001_drmeera_dentist_delhi"
    print("  POST /v1/tick success!")

    # Test POST /v1/reply
    r = client.post("/v1/reply", json={
        "conversation_id": actions[0]["conversation_id"],
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": None,
        "from_role": "merchant",
        "message": "ok let's do it",
        "received_at": "2026-04-26T10:10:00Z",
        "turn_number": 2
    })
    assert r.status_code == 200
    assert r.json()["action"] == "send"
    print("  POST /v1/reply success!")

    # Test duplicate/stale version conflict
    r = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": category,
        "delivered_at": "2026-04-26T10:00:00Z"
    })
    assert r.status_code == 409
    print("  POST /v1/context version conflict validation success!")

    # Test invalid scope
    r = client.post("/v1/context", json={
        "scope": "invalid",
        "context_id": "dentists",
        "version": 1,
        "payload": category,
        "delivered_at": "2026-04-26T10:00:00Z"
    })
    assert r.status_code == 400
    print("  POST /v1/context invalid scope validation success!")

    print("All local smoke tests passed successfully!")
    return True

if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
