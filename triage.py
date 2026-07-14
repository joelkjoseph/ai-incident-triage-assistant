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
import chromadb
from anthropic import AnthropicBedrock

# Reads AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION from environment
client = AnthropicBedrock()

# Bedrock requires an "inference profile" ID rather than a bare model name.
# The region prefix here (us.) should match the AWS_REGION you're using.
BEDROCK_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# Connect to the vector index built by build_index.py
chroma_client = chromadb.PersistentClient(path="./chroma_db")
resolution_notes = chroma_client.get_collection("resolution_notes")

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

You will be given a list of similar past resolved cases retrieved from a
knowledge base. If one is genuinely relevant, base your suggested_first_step
on it and reference it by its bracketed category label. If none of the
retrieved cases are actually relevant to this ticket, ignore them and rely on
general IT support knowledge instead - do not force a false connection.

Respond with ONLY valid JSON in this exact shape, no other text:
{{
  "is_valid_ticket": true,
  "category": "...",
  "priority": "...",
  "confidence": 0.0,
  "suggested_first_step": "one concise sentence",
  "referenced_past_case": "brief note on which past case informed this, or null if none applied",
  "reasoning": "one short sentence explaining the classification"
}}"""


def retrieve_similar_notes(description: str, n_results: int = 3) -> list[dict]:
    """Search the resolution notes index for the most similar past cases."""
    results = resolution_notes.query(query_texts=[description], n_results=n_results)

    # results["metadatas"][0] is a list of the metadata dicts for each match,
    # in order from most to least similar
    return results["metadatas"][0] if results["metadatas"] else []


def format_notes_for_prompt(notes: list[dict]) -> str:
    if not notes:
        return "No similar past cases found."

    formatted = []
    for i, note in enumerate(notes, 1):
        formatted.append(
            f"{i}. [{note['category']}] {note['issue_summary']}\n"
            f"   Resolution: {note['resolution']}"
        )
    return "\n".join(formatted)


def triage_ticket(description: str) -> dict:
    """Send a single ticket description to Claude, along with similar past
    cases retrieved from the resolution notes index, and return the parsed
    triage result."""
    similar_notes = retrieve_similar_notes(description)
    notes_context = format_notes_for_prompt(similar_notes)

    user_message = (
        f"Ticket description:\n{description}\n\n"
        f"Similar past resolved cases (most similar first):\n{notes_context}\n\n"
        f"Use these past cases as reference where genuinely relevant, but don't "
        f"force a connection if none of them actually apply."
    )

    response = client.messages.create(
        model=BEDROCK_MODEL_ID,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
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
            print(f"  Referenced past case: {result.get('referenced_past_case')}")
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
