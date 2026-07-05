# bot.py
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field
import compose_engine

app = FastAPI(title="magicpin AI Challenge — Vera Bot")

# In-memory stores
# Key: (scope, context_id) -> {"version": int, "payload": dict}
contexts: Dict[tuple, dict] = {}

# Key: conversation_id -> dict
conversations: Dict[str, dict] = {}

# Track suppressed triggers to prevent duplicate proactive messages
# Key: trigger_id -> bool
suppressed_triggers: Dict[str, bool] = {}

START_TIME = time.time()

class ContextPush(BaseModel):
    scope: str
    context_id: str
    version: int
    payload: Dict[str, Any]
    delivered_at: str

class TickRequest(BaseModel):
    now: str
    available_triggers: List[str]

class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int

@app.get("/")
def home():
    return {
        "status": "ok",
        "message": "magicpin AI Challenge Vera Bot is running.",
        "endpoints": {
            "GET /": "Welcome page showing available routes",
            "GET /v1/healthz": "Liveness probe returning loaded context counts",
            "GET /v1/metadata": "Candidate bot metadata details",
            "POST /v1/context": "Context push endpoint",
            "POST /v1/tick": "Trigger execution tick endpoint",
            "POST /v1/reply": "Conversation turn handler"
        }
    }

@app.get("/v1/healthz")
def healthz():
    counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
    for (scope, _), _ in contexts.items():
        if scope in counts:
            counts[scope] += 1
    return {
        "status": "ok",
        "uptime_seconds": int(time.time() - START_TIME),
        "contexts_loaded": counts
    }

@app.get("/v1/metadata")
def metadata():
    return {
        "team_name": "Team Antigravity",
        "team_members": ["Antigravity"],
        "model": "Deterministic Rule Engine (No-LLM)",
        "approach": "Fully rule-based & template-driven composition engine for 26 trigger families.",
        "contact_email": "antigravity@google.com",
        "version": "1.0.0",
        "submitted_at": datetime.utcnow().isoformat() + "Z"
    }

@app.post("/v1/context")
def post_context(body: ContextPush):
    scope = body.scope.strip().lower()
    if scope not in ["category", "merchant", "customer", "trigger"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"accepted": False, "reason": "invalid_scope"}
        )
    
    key = (scope, body.context_id)
    existing = contexts.get(key)
    
    if existing and existing["version"] >= body.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"accepted": False, "reason": "stale_version", "current_version": existing["version"]}
        )
        
    contexts[key] = {
        "version": body.version,
        "payload": body.payload
    }
    
    return {
        "accepted": True,
        "ack_id": f"ack_{body.context_id}_v{body.version}",
        "stored_at": datetime.utcnow().isoformat() + "Z"
    }

@app.post("/v1/tick")
def tick(body: TickRequest):
    actions = []
    
    for trg_id in body.available_triggers:
        # Check if already suppressed
        if trg_id in suppressed_triggers:
            continue
            
        trg_ctx = contexts.get(("trigger", trg_id))
        if not trg_ctx:
            continue
            
        trigger = trg_ctx["payload"]
        merchant_id = trigger.get("merchant_id")
        customer_id = trigger.get("customer_id")
        
        # Load merchant
        m_ctx = contexts.get(("merchant", merchant_id))
        if not m_ctx:
            continue
        merchant = m_ctx["payload"]
        
        # Load category
        cat_slug = merchant.get("category_slug")
        cat_ctx = contexts.get(("category", cat_slug))
        if not cat_ctx:
            continue
        category = cat_ctx["payload"]
        
        # Load optional customer
        customer = None
        if customer_id:
            c_ctx = contexts.get(("customer", customer_id))
            if c_ctx:
                customer = c_ctx["payload"]
                
        # Compose message
        try:
            composed = compose_engine.compose(category, merchant, trigger, customer)
            body_text = composed.get("body", "")
            
            # Skip if body is empty
            if not body_text:
                continue
                
            conv_id = f"conv_{merchant_id}_{trg_id}"
            
            # Store conversation context
            conversations[conv_id] = {
                "merchant_id": merchant_id,
                "customer_id": customer_id,
                "trigger_id": trg_id,
                "turns": [{"role": "vera", "message": body_text}],
                "auto_reply_count": 0,
                "proactive_action": composed
            }
            
            # Suppress this trigger to avoid repeats
            suppressed_triggers[trg_id] = True
            
            actions.append({
                "conversation_id": conv_id,
                "merchant_id": merchant_id,
                "customer_id": customer_id,
                "send_as": composed.get("send_as", "vera"),
                "trigger_id": trg_id,
                "template_name": f"vera_{trigger.get('kind', 'generic')}_v1",
                "template_params": [
                    merchant.get("identity", {}).get("name", "Merchant"),
                    body_text[:50]
                ],
                "body": body_text,
                "cta": composed.get("cta", "YES/STOP"),
                "suppression_key": composed.get("suppression_key", trg_id),
                "rationale": composed.get("rationale", "Composed proactive action.")
            })
        except Exception as e:
            # Prevent crashing, return empty actions
            continue
            
    return {"actions": actions}

@app.post("/v1/reply")
def reply(body: ReplyRequest):
    conv_id = body.conversation_id
    conv = conversations.get(conv_id)
    
    # If no conversation context found, initialize a dummy one to avoid crashing
    if not conv:
        conv = {
            "merchant_id": body.merchant_id,
            "customer_id": body.customer_id,
            "trigger_id": "dummy_trigger",
            "turns": [],
            "auto_reply_count": 0,
            "proactive_action": {}
        }
        conversations[conv_id] = conv
        
    conv["turns"].append({"role": body.from_role, "message": body.message})
    
    # Resolve trigger context
    trg_id = conv["trigger_id"]
    trg_ctx = contexts.get(("trigger", trg_id))
    trigger = trg_ctx["payload"] if trg_ctx else {"kind": "generic", "suppression_key": "dummy"}
    
    # Resolve merchant
    merchant_id = conv["merchant_id"]
    m_ctx = contexts.get(("merchant", merchant_id))
    merchant = m_ctx["payload"] if m_ctx else {"identity": {"name": "Merchant", "owner_first_name": "Owner"}}
    
    # Resolve category
    cat_slug = merchant.get("category_slug", "generic")
    cat_ctx = contexts.get(("category", cat_slug))
    category = cat_ctx["payload"] if cat_ctx else {"slug": cat_slug, "offer_catalog": []}
    
    # Resolve customer
    customer_id = conv["customer_id"]
    customer = None
    if customer_id:
        c_ctx = contexts.get(("customer", customer_id))
        if c_ctx:
            customer = c_ctx["payload"]
            
    try:
        reply_composed = compose_engine.compose_reply(
            conversation=conv,
            category=category,
            merchant=merchant,
            trigger=trigger,
            customer=customer,
            received_message=body.message,
            turn_number=body.turn_number
        )
        
        # Save response in turns
        if reply_composed.get("action") == "send" and reply_composed.get("body"):
            conv["turns"].append({"role": "vera", "message": reply_composed["body"]})
            
        return reply_composed
    except Exception as e:
        # Graceful fallback on exception
        return {
            "action": "end",
            "rationale": f"Internal exception occurred: {str(e)}. Ending conversation gracefully."
        }
