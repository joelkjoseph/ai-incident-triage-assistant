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
- **Docker** — containerized for consistent, portable deployment
- **AWS Lambda + Function URL** — serverless deployment, publicly reachable over HTTPS
- **Terraform** — infrastructure as code for a reproducible parallel deployment
- **GitHub Actions** — CI/CD: automated syntax checks and Docker build verification on every push, plus automatic build-push-deploy to Lambda on push to main
- **Vanilla HTML/CSS/JS frontend** — hosted free on GitHub Pages, calling the live API directly

## CI/CD

Every push to `main` triggers two independent GitHub Actions workflows:

- **CI** (`.github/workflows/ci.yml`) — checks out the code, verifies Python syntax, installs dependencies, and confirms the Docker image builds successfully. Runs on every push and pull request, no AWS access required.
- **Deploy** (`.github/workflows/deploy.yml`) — builds the Lambda-specific image, pushes it to Amazon ECR, updates the live Lambda function to use it, and waits for the update to complete. Authenticates using AWS credentials stored as encrypted GitHub Secrets, never committed to the repository.

In practice, this means pushing a code change is the only step required to update the live deployment — no manual Docker commands or console clicks.

## Live demo

**Try it yourself:** [https://joelkjoseph.github.io/ai-incident-triage-assistant/](https://joelkjoseph.github.io/ai-incident-triage-assistant/)

Or call the API directly:

```bash
curl -X POST https://fq3bycsnigljfqkd5dfg4sfski0djrpj.lambda-url.us-east-1.on.aws/triage \
  -H "Content-Type: application/json" \
  -d '{"description": "printer is showing offline for the whole floor"}'
```

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

## Deploying to serverless: three filesystem issues, one pattern

Getting this running on AWS Lambda surfaced a cluster of related issues, all stemming from the same root cause: Lambda's filesystem is read-only at runtime except for `/tmp`.

1. **ChromaDB's database itself** was baked into the image at a read-only path. Fixed by detecting the Lambda environment at startup and copying the pre-built index into `/tmp` before connecting to it.
2. **The embedding model's cache directory** defaulted to a path under the user's home folder, also unwritable in Lambda. Fixed by setting `HOME=/tmp` as an environment variable, redirecting where libraries look for a writable cache location.
3. **Cold start timing**: loading ChromaDB during Lambda's initialization phase came close to the platform's fixed 10-second init limit. Resolved by increasing the function's allocated memory, which proportionally increases available CPU during startup.

None of these were bugs in the application logic — they were all specific to how Lambda's execution environment differs from a normal server, and they only surfaced by actually deploying and reading the real error traces rather than assuming a container that works locally will behave identically in a serverless environment.

## Infrastructure as Code with Terraform

A second, parallel deployment of the same container image is defined entirely as code in `terraform/`, provisioning its own IAM role, Lambda function, and public Function URL from scratch with `terraform apply`. This is kept separate from the manually-built deployment above so the working version stays untouched during development.

Getting the Function URL to actually respond publicly surfaced another layered issue, this time in AWS's permission model rather than Lambda's filesystem:

1. A resource-based policy statement allowing `lambda:InvokeFunctionUrl` is required, but isn't enough on its own.
2. Since October 2025, AWS additionally requires a second permission, `lambda:InvokeFunction`, conditioned on the request being routed through a Function URL specifically. This uses a different mechanism (the CLI's `--invoked-via-function-url` flag) than the first permission, and isn't currently exposed as a clean, direct argument on this version of Terraform's AWS provider.
3. The console had added both automatically when the first (manually-built) Lambda function's URL was created; the Terraform-managed function needed the second one added explicitly via the AWS CLI, documented directly in `terraform/lambda.tf` as a known manual step alongside the code.

This is a realistic example of infrastructure-as-code not being perfectly self-contained in practice — provider support sometimes lags behind a cloud platform's own new requirements, and documenting the gap honestly is preferable to a `.tf` file that silently doesn't match deployed reality.

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

### Running with Docker

The project is fully containerized. To build and run it in Docker instead of a local Python environment:

```bash
docker build -t triage-app .

docker run -p 8000:8000 \
  -e AWS_ACCESS_KEY_ID="your-access-key-id" \
  -e AWS_SECRET_ACCESS_KEY="your-secret-access-key" \
  -e AWS_REGION="us-east-1" \
  triage-app
```

Then visit `http://127.0.0.1:8000/docs`, same as running locally. The vector index is built automatically inside the image at build time, so the container is ready to serve requests as soon as it starts.

Requires an AWS account with model access granted for Claude Haiku 4.5 in Amazon Bedrock, and an IAM user with Bedrock permissions.

## Evaluation results

Running `evaluate.py` against the full 65-ticket dataset (25 original tickets + 40 additional, including 15 deliberately difficult edge cases) gives a real, measured picture rather than a handful of spot-checks:

| Metric | Result |
|---|---|
| Category accuracy | 57/65 (87.7%) |
| Priority accuracy | 28/65 (43.1%) |
| Edge cases handled with appropriate caution | 11/15 (73.3%) |

**Category classification is strong.** At this scale, the model reliably identifies what kind of issue a ticket describes, including across terse, vague, and multi-issue inputs.

**Priority classification is a genuine weak point, not just noise.** This confirms a pattern first noticed in early manual testing (see below): the model tends to over-escalate rather than under-escalate priority, for example rating Medium-severity tickets as High. At 65 tickets, this shows up as a real, measurable gap rather than an isolated observation. A likely next step: adding a small number of explicit few-shot priority examples to the system prompt, calibrating what "High" versus "Medium" actually looks like, rather than relying on the model's own judgment of the four-level guidance alone.

**Edge case handling is decent but not solved.** 11 of 15 deliberately difficult inputs (very terse tickets, multi-issue tickets, off-topic messages, ALL-CAPS spam-style urgency) were handled with appropriate caution — either flagged as invalid or given visibly lower confidence. The remaining 4 were confidently misclassified, a concrete area for further guardrail tuning.

Reporting a real weakness alongside the strengths is intentional: a 65-ticket evaluation that only showed good news would be a less credible result than one that surfaces where the system actually struggles.

## Roadmap

- [x] Retrieval-augmented generation (RAG) over past resolution notes
- [x] Wrap in a lightweight FastAPI service
- [x] Containerize with Docker
- [x] Cloud deployment (AWS Lambda, public Function URL)
- [x] Infrastructure as code (Terraform)
- [x] CI/CD pipeline (GitHub Actions)
- [x] Simple frontend for submitting and reviewing tickets
- [x] Expand and formalise the evaluation dataset beyond the initial 25 sample tickets
- [ ] Add few-shot priority calibration examples to address the over-escalation pattern found during evaluation

## Author

Joel Joseph — [github.com/joelkjoseph](https://github.com/joelkjoseph) — [linkedin.com/in/joeljosephk](https://linkedin.com/in/joeljosephk)
