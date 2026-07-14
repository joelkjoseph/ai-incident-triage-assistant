"""
IT Incident Triage Assistant - Core Loop (v1)

The smallest possible working version: take one ticket description,
send it to Claude, get back a structured triage result.

No RAG, no database, no API server yet. Just prove the core loop works
before adding anything else.

Setup:
    pip install anthropic
    export ANTHROPIC_API_KEY="your-key-here"

Run:
    python triage.py
"""

import os
import json
import csv
from anthropic import AnthropicBedrock

# Reads AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION from environment
client = AnthropicBedrock()

# Bedrock requires an "inference profile" ID rather than a bare model name.
# The region prefix here (us.) should match the AWS_REGION you're using.
BEDROCK_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

VALID_CATEGORIES = [
    "Access Management", "Hardware", "Software", "Network", "Email",
    "Database", "Infrastructure", "Security", "User Provisioning",
    "General Support",
]

VALID_PRIORITIES = ["Low", "Medium", "High", "Critical"]

SYSTEM_PROMPT = f"""You are an IT service desk triage assistant. Given a support
ticket description, first decide whether this is actually a legitimate IT support
request. Then classify it and suggest a first troubleshooting step.

Valid categories: {", ".join(VALID_CATEGORIES)}
Valid priorities: {", ".join(VALID_PRIORITIES)}

Priority guidance:
- Critical: full outage affecting multiple users or business-critical systems
- High: single user blocked from essential work, or security concern
- Medium: degraded experience, workaround likely exists
- Low: minor annoyance, no urgent business impact

If the input is NOT a real IT support request (small talk, unrelated personal
matters, general knowledge questions, spam, or anything with no genuine IT
component), set is_valid_ticket to false, set category to "General Support",
set priority to "Low", and keep confidence LOW (0.3 or below) to reflect that
this needs human review rather than automated routing.

Respond with ONLY valid JSON in this exact shape, no other text:
{{
  "is_valid_ticket": true,
  "category": "...",
  "priority": "...",
  "confidence": 0.0,
  "suggested_first_step": "one concise sentence",
  "reasoning": "one short sentence explaining the classification"
}}"""


def triage_ticket(description: str) -> dict:
    """Send a single ticket description to Claude and return the parsed triage result."""
    response = client.messages.create(
        model=BEDROCK_MODEL_ID,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Ticket description:\n{description}"}],
    )

    raw_text = response.content[0].text.strip()

    # Strip markdown code fences if the model adds them despite instructions
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json\n", "", 1)

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        return {"error": "Could not parse model response", "raw_response": raw_text}


def run_against_sample_dataset(csv_path: str, limit: int = 5):
    """Quick sanity check: run the triage function against a few real tickets
    and compare the model's output to the ground-truth labels already in the CSV."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    print(f"\nRunning triage against {limit} sample tickets from {csv_path}\n")
    print("-" * 70)

    for row in reader[:limit]:
        result = triage_ticket(row["description"])

        print(f"Ticket: {row['ticket_id']} - {row['title']}")
        print(f"  Actual   -> category: {row['category']:<20} priority: {row['priority']}")

        if "error" in result:
            print(f"  Model    -> ERROR: {result['error']}")
        else:
            print(f"  Model    -> category: {result['category']:<20} priority: {result['priority']}")
            print(f"  Confidence: {result.get('confidence')}")
            print(f"  Suggested step: {result.get('suggested_first_step')}")
        print("-" * 70)


def run_interactive():
    """Let you type a new ticket description and see the triage result live."""
    print("\nType a ticket description (or 'quit' to exit):\n")
    while True:
        description = input("> ").strip()
        if description.lower() in ("quit", "exit"):
            break
        if not description:
            continue

        result = triage_ticket(description)
        print(json.dumps(result, indent=2))
        print()


if __name__ == "__main__":
    missing = [
        var for var in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION")
        if not os.environ.get(var)
    ]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        print("Set them first, e.g.:")
        print('  export AWS_ACCESS_KEY_ID="..."')
        print('  export AWS_SECRET_ACCESS_KEY="..."')
        print('  export AWS_REGION="us-east-1"')
        raise SystemExit(1)

    run_against_sample_dataset("tickets.csv", limit=5)
    run_interactive()
