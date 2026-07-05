# magicpin AI Challenge — Vera Bot Submission

## Deployed URL
https://vera-ai-32wv.onrender.com

## Approach & Design
This solution implements a fully deterministic, rule-based FastAPI bot for magicpin's WhatsApp Merchant Assistant ("Vera"). It is designed for deterministic scoring under injected metric shifts, digest updates, and reply replay tests.

### Core Highlights
*   **Trigger Prioritization**: When multiple triggers are available in `/v1/tick`, they are scored (e.g., customer safety/recall: +30, performance dips/recovery: +25, etc.) and sorted. Only the highest-scoring actions (up to the tick cap of 20) are processed.
*   **Grounded Specificity Extraction**: Personalizes messages using merchant/owner name, locality, cities, metric/delta/windows, and active offers. It checks merchant active offers before proposing discounts, ensuring zero hallucinated prices or offers.
*   **Strict Category Adaption**: Incorporates specific guidelines for all 5 business verticals:
    *   *Dentists*: Peer-clinical tone with "Dr." prefixing and JIDA citations. Banned medical claims or statistics (e.g. "cut cavities by 38%") are prevented.
    *   *Salons*: Warm, practical, and slot-oriented messaging.
    *   *Restaurants*: Fast-paced, operator-to-operator language targeting delivery optimizations (e.g., IPL matches).
    *   *Gyms*: Coach-like, motivational, and cohort/slot occupancy focused.
    *   *Pharmacies*: Trustworthy, precise, with no medication dosage or prescription advice.
*   **Robust Multi-Turn Support**: 
    *   *Auto-reply loop filter*: Detects automated WhatsApp business replies, warns on the first, and ends conversation on the second.
    *   *Intent Routing*: Switches from qualifying/nudge to action draft (e.g. Google/WhatsApp post templates) immediately when the merchant commits ("yes", "ok", "do it").
    *   *GST and Out-of-Scope Redirects*: Gracefully redirects tax/GST queries to their CA.
    *   *Hostility Defense*: Ends the conversation gracefully if abusive/hostile keywords are detected.
    *   *STOP Opt-out*: Customer outreach always includes clear YES/STOP options and STOP instructions.

---

## Testing and Verification

To verify the bot locally, run the following commands in sequence:

```bash
# Install dependencies
pip install -r requirements.txt

# Generate expanded dataset (100 triggers, 50 merchants, 200 customers)
python dataset/generate_dataset.py --seed-dir dataset --out expanded

# Run local smoke tests (fast API validations)
python local_smoke_test.py

# Run API contract validation tests (schemas & responses)
python api_contract_test.py

# Run local quality audit (30 test pairs quality & safety check)
python quality_audit.py

# Generate final submission file
python generate_submission.py --root . --data expanded --out submission.jsonl
```

All verification scripts must pass with `exit code 0`.
