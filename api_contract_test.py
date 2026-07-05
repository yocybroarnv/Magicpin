# api_contract_test.py
import json
from pathlib import Path
from fastapi.testclient import TestClient
from bot import app

def run_contract_test():
    print("Running API contract validation test...")
    client = TestClient(app)
    
    # 1. Verify healthz response schema
    print("Checking /v1/healthz schema...")
    r = client.get("/v1/healthz")
    assert r.status_code == 200, "healthz status code must be 200"
    data = r.json()
    assert "status" in data and isinstance(data["status"], str), "healthz must contain status: str"
    assert "uptime_seconds" in data and isinstance(data["uptime_seconds"], int), "healthz must contain uptime_seconds: int"
    assert "contexts_loaded" in data and isinstance(data["contexts_loaded"], dict), "healthz must contain contexts_loaded: dict"
    loaded = data["contexts_loaded"]
    for key in ["category", "merchant", "customer", "trigger"]:
        assert key in loaded and isinstance(loaded[key], int), f"contexts_loaded must contain {key}: int"
    print("  healthz schema OK")

    # 2. Verify metadata response schema
    print("Checking /v1/metadata schema...")
    r = client.get("/v1/metadata")
    assert r.status_code == 200, "metadata status code must be 200"
    data = r.json()
    required_metadata = ["team_name", "team_members", "model", "approach", "contact_email", "version", "submitted_at"]
    for key in required_metadata:
        assert key in data, f"metadata must contain {key}"
        if key == "team_members":
            assert isinstance(data[key], list), "team_members must be a list"
        else:
            assert isinstance(data[key], str), f"{key} must be a string"
    print("  metadata schema OK")

    # 3. Verify context push schema & errors
    print("Checking /v1/context schema & responses...")
    dummy_payload = {"test": True}
    
    # Valid call
    r = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "test_cat",
        "version": 1,
        "payload": dummy_payload,
        "delivered_at": "2026-04-26T10:00:00Z"
    })
    assert r.status_code == 200
    data = r.json()
    assert data.get("accepted") is True
    assert "ack_id" in data
    assert "stored_at" in data
    
    # Conflict (stale version)
    r = client.post("/v1/context", json={
        "scope": "category",
        "context_id": "test_cat",
        "version": 1,
        "payload": dummy_payload,
        "delivered_at": "2026-04-26T10:00:00Z"
    })
    assert r.status_code == 409
    data = r.json()
    assert data.get("detail", {}).get("accepted") is False
    assert data.get("detail", {}).get("reason") == "stale_version"
    
    # Invalid scope (400)
    r = client.post("/v1/context", json={
        "scope": "invalid_scope_name",
        "context_id": "test_cat",
        "version": 2,
        "payload": dummy_payload,
        "delivered_at": "2026-04-26T10:00:00Z"
    })
    assert r.status_code == 400
    data = r.json()
    assert data.get("detail", {}).get("accepted") is False
    assert data.get("detail", {}).get("reason") == "invalid_scope"
    print("  context push schemas and errors OK")

    # 4. Verify tick output schema
    print("Checking /v1/tick schema...")
    # Load dentists data to make a valid tick resolve
    data_dir = Path("expanded")
    if data_dir.exists():
        with open(data_dir / "categories" / "dentists.json", encoding="utf-8") as f:
            cat = json.load(f)
        with open(data_dir / "merchants" / "m_001_drmeera_dentist_delhi.json", encoding="utf-8") as f:
            merch = json.load(f)
        with open(data_dir / "triggers" / "trg_001_research_digest_dentists.json", encoding="utf-8") as f:
            trg = json.load(f)
            
        client.post("/v1/context", json={"scope": "category", "context_id": "dentists", "version": 2, "payload": cat, "delivered_at": "2026-04-26T10:00:00Z"})
        client.post("/v1/context", json={"scope": "merchant", "context_id": "m_001_drmeera_dentist_delhi", "version": 2, "payload": merch, "delivered_at": "2026-04-26T10:00:00Z"})
        client.post("/v1/context", json={"scope": "trigger", "context_id": trg["id"], "version": 2, "payload": trg, "delivered_at": "2026-04-26T10:00:00Z"})
        
        r = client.post("/v1/tick", json={
            "now": "2026-04-26T10:05:00Z",
            "available_triggers": [trg["id"]]
        })
        assert r.status_code == 200
        data = r.json()
        assert "actions" in data and isinstance(data["actions"], list)
        actions = data["actions"]
        if actions:
            act = actions[0]
            required_keys = [
                "conversation_id", "merchant_id", "customer_id", "send_as", 
                "trigger_id", "template_name", "template_params", "body", 
                "cta", "suppression_key", "rationale"
            ]
            for rkey in required_keys:
                assert rkey in act, f"Action must contain key: {rkey}"
                
            assert isinstance(act["template_params"], list), "template_params must be a list"
            assert act["send_as"] in ["vera", "merchant_on_behalf"], "send_as must be either vera or merchant_on_behalf"
            assert isinstance(act["body"], str), "body must be a string"
            assert isinstance(act["cta"], str), "cta must be a string"
            
    print("  tick schema OK")

    # 5. Verify reply response schema
    print("Checking /v1/reply schema...")
    r = client.post("/v1/reply", json={
        "conversation_id": "test_conv",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": None,
        "from_role": "merchant",
        "message": "ok let's do it",
        "received_at": "2026-04-26T10:10:00Z",
        "turn_number": 2
    })
    assert r.status_code == 200
    data = r.json()
    assert "action" in data and data["action"] in ["send", "wait", "end"]
    assert "rationale" in data
    if data["action"] == "send":
        assert "body" in data and isinstance(data["body"], str)
        assert "cta" in data and isinstance(data["cta"], str)
    elif data["action"] == "wait":
        assert "wait_seconds" in data and isinstance(data["wait_seconds"], int)
    print("  reply schema OK")

    print("All API contract validation checks passed successfully!")
    return True

if __name__ == "__main__":
    import sys
    success = run_contract_test()
    sys.exit(0 if success else 1)
