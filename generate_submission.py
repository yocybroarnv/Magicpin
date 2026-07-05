# generate_submission.py
import json
import argparse
from pathlib import Path
import compose_engine

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".", help="Root directory of the challenge workspace")
    parser.add_argument("--data", default="expanded", help="Path to the expanded dataset directory")
    parser.add_argument("--out", default="submission.jsonl", help="Output submission.jsonl path")
    args = parser.parse_args()

    root_dir = Path(args.root).resolve()
    data_dir = Path(args.data).resolve()
    out_path = Path(args.out).resolve()

    print(f"Generating submission from {data_dir} to {out_path}...")

    # Load test pairs
    test_pairs_path = data_dir / "test_pairs.json"
    if not test_pairs_path.exists():
        print(f"Error: test_pairs.json not found in {data_dir}")
        return

    with open(test_pairs_path, encoding="utf-8") as f:
        test_pairs = json.load(f)["pairs"]

    lines = []
    for pair in test_pairs:
        test_id = pair["test_id"]
        trigger_id = pair["trigger_id"]
        merchant_id = pair["merchant_id"]
        customer_id = pair.get("customer_id")

        # Load trigger
        trigger_path = data_dir / "triggers" / f"{trigger_id}.json"
        with open(trigger_path, encoding="utf-8") as f:
            trigger = json.load(f)

        # Load merchant
        merchant_path = data_dir / "merchants" / f"{merchant_id}.json"
        with open(merchant_path, encoding="utf-8") as f:
            merchant = json.load(f)

        # Load category
        cat_slug = merchant["category_slug"]
        category_path = data_dir / "categories" / f"{cat_slug}.json"
        with open(category_path, encoding="utf-8") as f:
            category = json.load(f)

        # Load optional customer
        customer = None
        if customer_id:
            customer_path = data_dir / "customers" / f"{customer_id}.json"
            with open(customer_path, encoding="utf-8") as f:
                customer = json.load(f)

        # Compose message
        composed = compose_engine.compose(
            category=category,
            merchant=merchant,
            trigger=trigger,
            customer=customer
        )

        lines.append({
            "test_id": test_id,
            "body": composed.get("body", ""),
            "cta": composed.get("cta", "YES/STOP"),
            "send_as": composed.get("send_as", "vera"),
            "suppression_key": composed.get("suppression_key", ""),
            "rationale": composed.get("rationale", "")
        })

    # Write submission.jsonl
    with open(out_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")

    print(f"Generated submission file with {len(lines)} lines successfully.")

if __name__ == "__main__":
    main()
