#!/usr/bin/env python3
import json
import sys
from pathlib import Path
import compose_engine

def main():
    root = Path(__file__).parent.resolve()
    data_dir = root / "expanded"
    test_pairs_file = data_dir / "test_pairs.json"
    
    if not test_pairs_file.exists():
        print(f"Error: {test_pairs_file} not found. Generate the dataset first.")
        sys.exit(1)
        
    with open(test_pairs_file, "r", encoding="utf-8") as f:
        test_pairs = json.load(f)["pairs"]
        
    passed_count = 0
    failed_count = 0
    failures = []
    
    print(f"Running quality audit on {len(test_pairs)} test pairs...")
    print("-" * 80)
    
    for pair in test_pairs:
        test_id = pair["test_id"]
        trg_id = pair["trigger_id"]
        merchant_id = pair["merchant_id"]
        customer_id = pair.get("customer_id")
        
        # Load trigger
        with open(data_dir / "triggers" / f"{trg_id}.json", "r", encoding="utf-8") as f:
            trigger = json.load(f)
            
        # Load merchant
        with open(data_dir / "merchants" / f"{merchant_id}.json", "r", encoding="utf-8") as f:
            merchant = json.load(f)
            
        # Load category
        cat_slug = merchant["category_slug"]
        with open(data_dir / "categories" / f"{cat_slug}.json", "r", encoding="utf-8") as f:
            category = json.load(f)
            
        # Load customer
        customer = None
        if customer_id:
            with open(data_dir / "customers" / f"{customer_id}.json", "r", encoding="utf-8") as f:
                customer = json.load(f)
                
        # Run compose
        try:
            res = compose_engine.compose(category, merchant, trigger, customer)
        except Exception as e:
            failed_count += 1
            failures.append((test_id, f"compose crashed: {e}"))
            print(f"[{test_id}] FAIL: compose crashed: {e}")
            continue
            
        # Assertions
        body = res.get("body", "")
        cta = res.get("cta", "")
        send_as = res.get("send_as", "")
        suppression_key = res.get("suppression_key", "")
        rationale = res.get("rationale", "")
        
        errors = []
        
        # 1. Non-empty fields
        if not body:
            errors.append("body is empty")
        if not cta:
            errors.append("cta is empty")
        if not send_as:
            errors.append("send_as is empty")
        if not suppression_key:
            errors.append("suppression_key is empty")
        if not rationale:
            errors.append("rationale is empty")
            
        # 2. No unsafe banned phrases
        banned_phrases = ["cut cavities by", "38%"]
        for p in banned_phrases:
            if p in body.lower():
                errors.append(f"body contains banned phrase '{p}'")
                
        # Word boundaries for exact words
        import re
        exact_banned = ["guaranteed", "cure", "heal", "best in city"]
        for p in exact_banned:
            if re.search(r"\b" + re.escape(p) + r"\b", body.lower()):
                errors.append(f"body contains banned word '{p}'")
                
        # 3. calls dip in non-perf triggers
        trigger_kind = trigger.get("kind", "")
        if "calls dip" in body.lower() and trigger_kind not in ["perf_dip", "seasonal_perf_dip"]:
            errors.append("body mentions 'calls dip' for a non-performance trigger")
            
        # 4. discount when no offer exists
        m_offer = compose_engine.get_merchant_active_offer(merchant)
        if "discount" in body.lower() and not m_offer and "discount" not in str(trigger.get("payload", {})):
            errors.append("body mentions 'discount' but merchant has no active offer")
            
        # 5. one CTA only
        if not cta or len(cta.split(",")) > 1 or len(cta.split("/")) > 2:
            # YES/STOP is fine
            if cta not in ["YES/STOP", "open_ended", "none"]:
                errors.append(f"invalid or multiple CTA options: {cta}")
                
        # 6. merchant/owner name included when merchant-facing
        scope = trigger.get("scope", "merchant")
        if scope == "merchant":
            owner = compose_engine.get_owner_name(merchant)
            biz = compose_engine.get_biz_name(merchant)
            # Salutation could contain Dr. Owner
            salutation = f"Dr. {owner}" if (cat_slug == "dentists" and owner != "there") else owner
            owner_clean = owner.replace("Dr. ", "")
            salutation_clean = salutation.replace("Dr. ", "")
            
            # Check if owner name or business name exists in body
            # We allow lowercase/case-insensitive checks, and allow owner being "there"
            has_owner = owner_clean.lower() in body.lower() or salutation_clean.lower() in body.lower() or "there" in body.lower()
            has_biz = biz.lower() in body.lower() or merchant["identity"]["name"].lower() in body.lower()
            if not (has_owner or has_biz):
                errors.append(f"merchant-facing trigger does not mention owner name ('{owner}') or business name ('{biz}')")
                
        # 7. customer name included when customer-facing
        if scope == "customer" and customer:
            c_name = compose_engine.get_customer_name(customer)
            if c_name.lower() not in body.lower():
                errors.append(f"customer-facing trigger does not mention customer name ('{c_name}')")
                
        # 8. performance metric included for perf triggers
        if trigger_kind in ["perf_dip", "seasonal_perf_dip", "perf_spike"]:
            payload = trigger.get("payload", {})
            default_metric = "views" if trigger_kind == "perf_spike" else "calls"
            metric = payload.get("metric", default_metric)
            if metric.lower() not in body.lower():
                errors.append(f"performance trigger does not mention metric '{metric}'")
                
        # 9. STOP included for customer outreach
        if scope == "customer":
            if "STOP" not in body:
                errors.append("customer outreach message does not contain 'STOP' opt-out instruction")
                
        # 10. no hallucinated price if offer missing
        if not m_offer:
            # Check if there is any price symbol like ₹ followed by numbers, or Rs followed by numbers that isn't from the payload/catalog
            import re
            prices_found = re.findall(r"₹\d+|Rs\.?\s*\d+", body)
            # Filter out any prices present in category catalog or trigger payload
            payload_str = str(trigger.get("payload", {}))
            cat_str = str(category.get("offer_catalog", []))
            for pf in prices_found:
                # extract digit
                digit = re.search(r"\d+", pf).group()
                if digit not in payload_str and digit not in cat_str:
                    errors.append(f"hallucinated price '{pf}' found in message body when merchant has no active offer")
                    
        # 11. research_digest does not mention perf dip
        if trigger_kind == "research_digest":
            if "dip" in body.lower() or "drop" in body.lower() or "performance" in body.lower():
                errors.append("research_digest trigger mentions performance dips or drops")
                
        if errors:
            failed_count += 1
            failures.append((test_id, "; ".join(errors)))
            print(f"[{test_id}] FAIL: {'; '.join(errors)}")
        else:
            passed_count += 1
            print(f"[{test_id}] PASS")
            
    print("-" * 80)
    print(f"Audit completed: {passed_count} PASSED, {failed_count} FAILED.")
    
    if failed_count > 0:
        print("\nFailed Tests Summary:")
        for fid, msg in failures:
            print(f"  - {fid}: {msg}")
        sys.exit(1)
    else:
        print("\nAll quality audit checks passed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    main()
