# endpoint_check.py
import sys
import requests

def test_endpoint(base_url: str):
    base_url = base_url.rstrip("/")
    print(f"Verifying deployed endpoints at: {base_url}")
    
    # 1. GET /
    print("\nTesting GET / ...")
    try:
        r = requests.get(base_url, timeout=10)
        print(f"Status: {r.status_code}")
        print(r.json())
        assert r.status_code == 200, "GET / failed"
    except Exception as e:
        print(f"Error GET /: {e}")
        return False

    # 2. GET /v1/healthz
    print("\nTesting GET /v1/healthz ...")
    try:
        r = requests.get(f"{base_url}/v1/healthz", timeout=10)
        print(f"Status: {r.status_code}")
        print(r.json())
        assert r.status_code == 200, "GET /v1/healthz failed"
    except Exception as e:
        print(f"Error GET /v1/healthz: {e}")
        return False

    # 3. GET /v1/metadata
    print("\nTesting GET /v1/metadata ...")
    try:
        r = requests.get(f"{base_url}/v1/metadata", timeout=10)
        print(f"Status: {r.status_code}")
        print(r.json())
        assert r.status_code == 200, "GET /v1/metadata failed"
    except Exception as e:
        print(f"Error GET /v1/metadata: {e}")
        return False

    # Mock context payloads for validation
    category_payload = {
        "slug": "dentists",
        "display_name": "Dentists",
        "voice": {"tone": "peer_clinical"},
        "offer_catalog": [{"id": "den_001", "title": "Dental Cleaning @ ₹299"}]
    }
    
    merchant_payload = {
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "category_slug": "dentists",
        "identity": {"name": "Dr. Meera's Dental Clinic", "owner_first_name": "Meera"}
    }
    
    trigger_payload = {
        "id": "trg_001_research_digest_dentists",
        "scope": "merchant",
        "kind": "research_digest",
        "merchant_id": "m_001_drmeera_dentist_delhi",
        "customer_id": None,
        "payload": {"top_item_id": "d_001"},
        "suppression_key": "research:dentists:2026-W17"
    }

    # 4. POST /v1/context (category)
    print("\nTesting POST /v1/context (category) ...")
    try:
        r = requests.post(f"{base_url}/v1/context", json={
            "scope": "category",
            "context_id": "dentists",
            "version": 100,  # Use high version to avoid 409 conflict
            "payload": category_payload,
            "delivered_at": "2026-04-26T10:00:00Z"
        }, timeout=10)
        print(f"Status: {r.status_code}")
        print(r.json())
        assert r.status_code == 200, "POST context category failed"
    except Exception as e:
        print(f"Error POST category context: {e}")
        return False

    # 5. POST /v1/context (merchant)
    print("\nTesting POST /v1/context (merchant) ...")
    try:
        r = requests.post(f"{base_url}/v1/context", json={
            "scope": "merchant",
            "context_id": "m_001_drmeera_dentist_delhi",
            "version": 100,
            "payload": merchant_payload,
            "delivered_at": "2026-04-26T10:00:00Z"
        }, timeout=10)
        print(f"Status: {r.status_code}")
        print(r.json())
        assert r.status_code == 200, "POST context merchant failed"
    except Exception as e:
        print(f"Error POST merchant context: {e}")
        return False

    # 6. POST /v1/context (trigger)
    print("\nTesting POST /v1/context (trigger) ...")
    try:
        r = requests.post(f"{base_url}/v1/context", json={
            "scope": "trigger",
            "context_id": "trg_001_research_digest_dentists",
            "version": 100,
            "payload": trigger_payload,
            "delivered_at": "2026-04-26T10:00:00Z"
        }, timeout=10)
        print(f"Status: {r.status_code}")
        print(r.json())
        assert r.status_code == 200, "POST context trigger failed"
    except Exception as e:
        print(f"Error POST trigger context: {e}")
        return False

    # 7. POST /v1/tick
    print("\nTesting POST /v1/tick ...")
    try:
        r = requests.post(f"{base_url}/v1/tick", json={
            "now": "2026-04-26T10:05:00Z",
            "available_triggers": ["trg_001_research_digest_dentists"]
        }, timeout=10)
        print(f"Status: {r.status_code}")
        print(r.json())
        assert r.status_code == 200, "POST /v1/tick failed"
        actions = r.json().get("actions", [])
        assert len(actions) > 0, "No actions returned"
        conv_id = actions[0]["conversation_id"]
    except Exception as e:
        print(f"Error POST /v1/tick: {e}")
        return False

    # 8. POST /v1/reply with "ok let's do it"
    print("\nTesting POST /v1/reply with 'ok let's do it' ...")
    try:
        r = requests.post(f"{base_url}/v1/reply", json={
            "conversation_id": conv_id,
            "merchant_id": "m_001_drmeera_dentist_delhi",
            "customer_id": None,
            "from_role": "merchant",
            "message": "ok let's do it",
            "received_at": "2026-04-26T10:10:00Z",
            "turn_number": 2
        }, timeout=10)
        print(f"Status: {r.status_code}")
        print(r.json())
        assert r.status_code == 200, "POST /v1/reply failed"
    except Exception as e:
        print(f"Error POST /v1/reply: {e}")
        return False

    print("\nEndpoint check passed. Submit base URL:", base_url)
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python endpoint_check.py <base_url>")
        sys.exit(1)
    
    base_url = sys.argv[1]
    success = test_endpoint(base_url)
    sys.exit(0 if success else 1)
