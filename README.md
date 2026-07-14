# AI-Powered IT Incident Triage Assistant

An AI service desk triage tool that classifies incoming IT support tickets by category and priority, and suggests a first troubleshooting step — built to explore applying LLMs to real IT support workflows.

Given a raw ticket description, it returns a structured response:

```json
{
  "is_valid_ticket": true,
  "category": "Access Management",
  "priority": "High",
  "confidence": 0.92,
  "suggested_first_step": "Verify the user's VPN account is active and not locked, then have them clear cached credentials and attempt reconnection.",
  "reasoning": "Authentication failure blocking remote access ahead of a meeting."
}
```

## Why I built this

Coming from an IT support background (application support, incident resolution, root-cause troubleshooting), I wanted to explore how far an LLM could go in automating the first, most time-consuming step of the process: reading a raw ticket and deciding what it is and how urgent it is. This project tests that directly against a set of realistic support tickets and measures how well it performs.

## Tech stack

- **Python**
- **Claude (Haiku 4.5)** via **AWS Bedrock** — inference is authenticated through IAM credentials rather than a direct API key, keeping usage inside the AWS security boundary
- **Anthropic Python SDK** (`AnthropicBedrock` client)
- **ChromaDB** — local vector store for retrieval-augmented generation (RAG) over past resolution notes
- **FastAPI** — exposes triage as an HTTP endpoint with auto-generated interactive docs

## How it works

1. A small knowledge base of past resolution notes (`resolution_notes.csv`) is embedded and indexed locally using ChromaDB (`build_index.py`)
2. When a new ticket comes in, the script searches that index for the 3 most similar past resolved cases
3. Those cases are passed to Claude alongside the ticket, with instructions to use them if genuinely relevant and ignore them otherwise
4. The model returns structured JSON: category, priority, a confidence score, a suggested first step grounded in the retrieved cases, which past case (if any) it drew from, and a one-line rationale
5. A small sample dataset (`tickets.csv`) of realistic IT tickets is used to sanity-check the model's output against expected labels

### RAG in action

Before adding retrieval, a "printer offline" ticket produced a generic suggestion: *"Check if the printer is powered on and connected to the network."*

After adding retrieval, the same ticket correctly matched a past resolution note and produced: *"Check the printer's network connection status directly on its display panel and verify its current IP address matches what the print server has on file"* — because a near-identical past case in the knowledge base had traced the same symptom to a DHCP-reassigned IP address. The suggestion became specific and evidence-backed instead of generic.

## A finding worth mentioning

Early testing surfaced a real failure mode: when given input that wasn't a genuine IT ticket (e.g. an unrelated personal comment or a general knowledge question), the model didn't recognise this — it forced the input into a plausible-sounding IT category with **high confidence** rather than flagging it as invalid. That's a dangerous failure mode for any tool that's meant to be trusted: confidently wrong is worse than visibly uncertain.

The fix was adding an explicit `is_valid_ticket` field to the output schema, with instructions for the model to keep confidence low and flag the item for human review when the input doesn't resemble a genuine support request. After the fix, the same off-topic input was correctly flagged as invalid with confidence dropping from 0.95 to 0.2.

This is the kind of gap that only shows up once you actively try to break your own system — which is exactly what happened here.

## Setup

```bash
pip install "anthropic[bedrock]" chromadb

export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_REGION="us-east-1"

python3 build_index.py    # builds the local vector index (run once, or after editing resolution_notes.csv)
python3 triage.py         # run as a CLI tool
```

To run as an HTTP API instead:

```bash
pip install fastapi "uvicorn[standard]"
uvicorn api:app --reload
```

Then visit `http://127.0.0.1:8000/docs` for interactive API documentation, or send a POST request to `/triage`:

```bash
curl -X POST http://127.0.0.1:8000/triage \
  -H "Content-Type: application/json" \
  -d '{"description": "VPN authentication fails even though my password is correct"}'
```

Requires an AWS account with model access granted for Claude Haiku 4.5 in Amazon Bedrock, and an IAM user with Bedrock permissions.

## Sample results

Tested against 5 tickets from `tickets.csv`, the model classified all 5 categories correctly and, with retrieval enabled, correctly matched each ticket to its most relevant past resolution note. Priority classification showed a mild tendency to over-escalate (e.g. rating a Medium ticket as High) rather than under-escalate — arguably a reasonable bias for a support tool, though it's a tuning point for future iteration.

## Roadmap

- [x] Retrieval-augmented generation (RAG) over past resolution notes
- [x] Wrap in a lightweight FastAPI service
- [ ] Cloud deployment (AWS Lambda + API Gateway)
- [ ] Infrastructure as code (Terraform)
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Simple frontend for submitting and reviewing tickets
- [ ] Expand and formalise the evaluation dataset beyond the initial 25 sample tickets

## Author

Joel Joseph — [github.com/joelkjoseph](https://github.com/joelkjoseph) — [linkedin.com/in/joeljosephk](https://linkedin.com/in/joeljosephk)
