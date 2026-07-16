"""
Evaluation script - Step 3

Runs the full ticket dataset (original + extended) through the triage
pipeline and reports real accuracy metrics, rather than spot-checking a
handful of tickets by eye.

Run:
    python3 evaluate.py
"""

import csv
from triage import triage_ticket


def load_all_tickets():
    tickets = []
    for path in ("tickets.csv", "tickets_extended.csv"):
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["edge_case"] = row.get("edge_case", "false") == "true"
                tickets.append(row)
    return tickets


def run_evaluation():
    tickets = load_all_tickets()
    total = len(tickets)

    category_correct = 0
    priority_correct = 0
    edge_case_count = 0
    edge_case_flagged_low_confidence = 0

    results = []

    print(f"Running evaluation against {total} tickets...\n")

    for i, ticket in enumerate(tickets, 1):
        result = triage_ticket(ticket["description"])

        category_match = result.get("category") == ticket["category"]
        priority_match = result.get("priority") == ticket["priority"]

        if category_match:
            category_correct += 1
        if priority_match:
            priority_correct += 1

        if ticket["edge_case"]:
            edge_case_count += 1
            # For edge cases, we're specifically interested in whether the
            # model showed appropriate uncertainty (lower confidence) rather
            # than confidently misclassifying ambiguous or malformed input.
            if result.get("confidence", 1.0) < 0.7 or result.get("is_valid_ticket") is False:
                edge_case_flagged_low_confidence += 1

        results.append({
            "id": ticket["ticket_id"],
            "edge_case": ticket["edge_case"],
            "category_match": category_match,
            "priority_match": priority_match,
            "confidence": result.get("confidence"),
            "is_valid_ticket": result.get("is_valid_ticket"),
        })

        status = "✓" if category_match and priority_match else "✗"
        edge_tag = " [EDGE CASE]" if ticket["edge_case"] else ""
        print(f"{status} {ticket['ticket_id']}{edge_tag} — category:{'match' if category_match else 'MISS'} priority:{'match' if priority_match else 'MISS'} confidence:{result.get('confidence')}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total tickets evaluated: {total}")
    print(f"Category accuracy: {category_correct}/{total} ({100*category_correct/total:.1f}%)")
    print(f"Priority accuracy: {priority_correct}/{total} ({100*priority_correct/total:.1f}%)")
    print(f"\nEdge cases: {edge_case_count}")
    print(f"Edge cases handled with appropriate caution (low confidence or flagged invalid): "
          f"{edge_case_flagged_low_confidence}/{edge_case_count} "
          f"({100*edge_case_flagged_low_confidence/edge_case_count:.1f}%)" if edge_case_count else "")

    return results


if __name__ == "__main__":
    run_evaluation()
