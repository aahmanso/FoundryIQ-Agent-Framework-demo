# Evaluate and Optimize Agents

A practical guide for systematically measuring and improving agent quality in the FoundryIQ and Agent Framework multi-agent system. Covers manual testing, Foundry batch evaluation, programmatic SDK evaluation, and prompt optimization.

---

## Why Evaluate?

Even with grounded retrieval from FoundryIQ Knowledge Bases, your agents can still produce responses that are:

- **Wrong** — the model misinterprets the KB context or hallucinates facts
- **Incomplete** — relevant KB content exists but the model ignores it
- **Poorly formatted** — the response is a wall of text when the user asked for a table
- **Mis-routed** — the router sent the query to the wrong specialist

Evaluation transforms "it seems to work" into measurable, trackable quality metrics. Optimization uses those metrics to systematically improve prompts.

```
┌─────────┐     ┌──────────┐     ┌──────────┐     ┌──────────────┐
│  Author  │────▶│ Evaluate │────▶│ Analyze  │────▶│   Optimize   │
│  Prompts │     │  (batch) │     │ Results  │     │ (iterate)    │
└─────────┘     └──────────┘     └──────────┘     └──────┬───────┘
      ▲                                                    │
      └────────────────────────────────────────────────────┘
```

---

## Setting Up Evaluation

### Option 1: Manual Test Suite

The fastest way to get started. Create a test file and a runner script.

#### 1A — Create Test Cases

```json
// tests/eval_dataset.json
[
  {
    "id": "hr-001",
    "query": "What is the vacation policy for full-time employees?",
    "expected_route": "hr",
    "expected_phrases": ["vacation", "paid time off", "PTO", "days"],
    "difficulty": "easy"
  },
  {
    "id": "hr-002",
    "query": "How does parental leave work for adoptive parents?",
    "expected_route": "hr",
    "expected_phrases": ["parental leave", "adoption", "weeks"],
    "difficulty": "medium"
  },
  {
    "id": "prod-001",
    "query": "What API rate limits apply to the enterprise tier?",
    "expected_route": "products",
    "expected_phrases": ["rate limit", "enterprise", "requests"],
    "difficulty": "easy"
  },
  {
    "id": "mktg-001",
    "query": "What channels did we use for the Q3 product launch?",
    "expected_route": "marketing",
    "expected_phrases": ["channels", "launch", "campaign"],
    "difficulty": "easy"
  },
  {
    "id": "edge-001",
    "query": "Compare our product pricing with industry HR compensation benchmarks",
    "expected_route": "products",
    "expected_phrases": ["pricing"],
    "difficulty": "hard"
  },
  {
    "id": "edge-002",
    "query": "",
    "expected_route": "general",
    "expected_phrases": [],
    "difficulty": "edge"
  }
]
```

#### 1B — Build a Test Runner

```python
# tests/eval_runner.py
"""
Manual evaluation runner. Executes test cases against the live orchestrator
and reports routing accuracy + response quality.
"""

import asyncio
import json
import time
from app.backend.orchestrator import run_single_query

async def run_evaluation(dataset_path: str = "tests/eval_dataset.json"):
    with open(dataset_path) as f:
        test_cases = json.load(f)

    results = []
    routing_correct = 0
    total = len(test_cases)

    for tc in test_cases:
        print(f"Running: {tc['id']} — {tc['query'][:60]}...")
        start = time.time()

        try:
            response = await run_single_query(tc["query"])
            elapsed = time.time() - start

            # Check routing accuracy
            actual_route = response.get("route", "unknown")
            route_correct = actual_route == tc["expected_route"]
            if route_correct:
                routing_correct += 1

            # Check expected phrases in response
            message = response.get("message", "").lower()
            phrases_found = [
                phrase for phrase in tc["expected_phrases"]
                if phrase.lower() in message
            ]
            phrase_coverage = (
                len(phrases_found) / len(tc["expected_phrases"])
                if tc["expected_phrases"]
                else 1.0
            )

            results.append({
                "id": tc["id"],
                "route_correct": route_correct,
                "expected_route": tc["expected_route"],
                "actual_route": actual_route,
                "phrase_coverage": phrase_coverage,
                "phrases_found": phrases_found,
                "phrases_missing": [
                    p for p in tc["expected_phrases"] if p not in phrases_found
                ],
                "latency_s": round(elapsed, 2),
                "response_length": len(message),
                "difficulty": tc["difficulty"],
                "passed": route_correct and phrase_coverage >= 0.5,
            })
        except Exception as e:
            results.append({
                "id": tc["id"],
                "error": str(e),
                "passed": False,
            })

    # --- Summary Report ---
    passed = sum(1 for r in results if r.get("passed"))
    print("\n" + "=" * 70)
    print(f"EVALUATION RESULTS")
    print(f"=" * 70)
    print(f"Total test cases:   {total}")
    print(f"Passed:             {passed}/{total} ({passed/total*100:.1f}%)")
    print(f"Routing accuracy:   {routing_correct}/{total} ({routing_correct/total*100:.1f}%)")
    avg_latency = sum(r.get("latency_s", 0) for r in results) / total
    print(f"Avg latency:        {avg_latency:.2f}s")

    print(f"\n--- Failures ---")
    for r in results:
        if not r.get("passed"):
            print(f"  [{r['id']}] Route: {r.get('actual_route')} "
                  f"(expected {r.get('expected_route')}), "
                  f"Phrases missing: {r.get('phrases_missing', 'N/A')}")

    # Save detailed results
    with open("tests/eval_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed results saved to tests/eval_results.json")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
```

Run it:

```bash
python -m tests.eval_runner
```

---

### Option 2: Foundry Batch Evaluation

Azure AI Foundry provides built-in evaluation with standardized metrics. This is ideal for repeatable, production-grade evaluation.

#### 2A — Prepare the Dataset

Create a JSONL file that Foundry can ingest:

```jsonl
{"query": "What is the vacation policy?", "ground_truth": "Full-time employees receive 20 days PTO per year.", "context": "hr", "expected_route": "hr"}
{"query": "What API rate limits apply?", "ground_truth": "Enterprise tier: 10,000 requests/minute.", "context": "products", "expected_route": "products"}
{"query": "What channels for Q3 launch?", "ground_truth": "Social media, email, and paid search.", "context": "marketing", "expected_route": "marketing"}
```

#### 2B — Upload to Foundry

```bash
# Using the az CLI with the AI extension
az ai project data upload \
  --name "agent-eval-dataset-v1" \
  --file tests/eval_dataset.jsonl \
  --project-name <your-project-name> \
  --resource-group <rg-name>
```

Or upload via the Foundry portal:

1. Go to **Azure AI Foundry** → your project → **Data**
2. Click **+ Upload** → select your JSONL file
3. Name it `agent-eval-dataset-v1`

#### 2C — Create an Evaluation Run

In the Foundry portal:

1. Navigate to **Evaluation** → **+ New evaluation**
2. Select your dataset (`agent-eval-dataset-v1`)
3. Choose evaluators:

| Evaluator | What It Measures | When to Use |
|---|---|---|
| **Groundedness** | Is the response supported by provided context? | Always — your agents are KB-grounded |
| **Relevance** | Does the response address the question? | Always |
| **Coherence** | Is the response logically structured? | After prompt format changes |
| **Fluency** | Is the language natural and grammatical? | After persona changes |
| **Similarity** | How close is the response to the expected answer? | When you have reference answers |

4. Configure the mapping:
   - `query` → input column
   - `ground_truth` → reference answer column
   - `context` → context column (optional)
5. Run the evaluation

#### 2D — Interpret Scores

Foundry evaluators return scores from 1–5:

| Score | Meaning |
|---|---|
| 5 | Excellent — fully meets criteria |
| 4 | Good — minor issues |
| 3 | Acceptable — noticeable issues but usable |
| 2 | Poor — significant issues |
| 1 | Failing — does not meet criteria |

**Target scores for production:**
- Groundedness: ≥ 4.0 (critical — prevents hallucination)
- Relevance: ≥ 4.0 (critical — ensures answers match questions)
- Coherence: ≥ 3.5 (important for user experience)
- Fluency: ≥ 3.5 (important for user experience)

---

### Option 3: Programmatic Evaluation with SDK

Use the `azure-ai-evaluation` SDK for CI/CD integration.

#### 3A — Install the SDK

```bash
pip install azure-ai-evaluation
```

#### 3B — Run Evaluators Programmatically

```python
# tests/eval_foundry_sdk.py
"""
Programmatic evaluation using the azure-ai-evaluation SDK.
Runs evaluators against the orchestrator output and returns scores.
"""

import asyncio
import json
from azure.identity import DefaultAzureCredential
from azure.ai.evaluation import (
    GroundednessEvaluator,
    RelevanceEvaluator,
    CoherenceEvaluator,
    FluencyEvaluator,
)
from app.backend.orchestrator import run_single_query

# Initialize evaluators with your Foundry project
credential = DefaultAzureCredential()
PROJECT_ENDPOINT = "https://<ais-name>.services.ai.azure.com/api/projects/<project-name>"

groundedness_eval = GroundednessEvaluator(
    credential=credential,
    azure_ai_project=PROJECT_ENDPOINT,
)
relevance_eval = RelevanceEvaluator(
    credential=credential,
    azure_ai_project=PROJECT_ENDPOINT,
)
coherence_eval = CoherenceEvaluator(
    credential=credential,
    azure_ai_project=PROJECT_ENDPOINT,
)
fluency_eval = FluencyEvaluator(
    credential=credential,
    azure_ai_project=PROJECT_ENDPOINT,
)


async def evaluate_single(query: str, ground_truth: str, context: str = ""):
    """Run a single query through the orchestrator and evaluate the response."""
    response = await run_single_query(query)
    answer = response.get("message", "")

    # Run all evaluators
    scores = {}
    scores["groundedness"] = groundedness_eval(
        query=query, response=answer, context=context
    )
    scores["relevance"] = relevance_eval(
        query=query, response=answer
    )
    scores["coherence"] = coherence_eval(
        query=query, response=answer
    )
    scores["fluency"] = fluency_eval(
        query=query, response=answer
    )

    return {
        "query": query,
        "response": answer,
        "route": response.get("route"),
        "scores": scores,
    }


async def evaluate_batch(dataset_path: str):
    """Evaluate all test cases and produce a summary report."""
    with open(dataset_path) as f:
        test_cases = json.load(f)

    all_results = []
    for tc in test_cases:
        print(f"Evaluating: {tc['id']}...")
        result = await evaluate_single(
            query=tc["query"],
            ground_truth=tc.get("ground_truth", ""),
            context=tc.get("context", ""),
        )
        result["id"] = tc["id"]
        all_results.append(result)

    # Aggregate scores
    metrics = ["groundedness", "relevance", "coherence", "fluency"]
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    for metric in metrics:
        values = [
            r["scores"][metric].get("score", 0)
            for r in all_results
            if metric in r["scores"]
        ]
        if values:
            avg = sum(values) / len(values)
            print(f"  {metric:<20} avg: {avg:.2f}  min: {min(values)}  max: {max(values)}")

    # Save results
    with open("tests/eval_sdk_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to tests/eval_sdk_results.json")


if __name__ == "__main__":
    asyncio.run(evaluate_batch("tests/eval_dataset.json"))
```

#### 3C — CI/CD Integration

Add evaluation as a GitHub Actions step:

```yaml
# .github/workflows/eval.yml
name: Agent Evaluation
on:
  pull_request:
    paths:
      - "app/backend/orchestrator.py"
      - "app/backend/prompt_registry.py"

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r app/backend/requirements.txt azure-ai-evaluation

      - name: Azure Login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Run evaluation
        run: python -m tests.eval_foundry_sdk
        env:
          AZURE_PROJECT_ENDPOINT: ${{ vars.AZURE_PROJECT_ENDPOINT }}

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: tests/eval_sdk_results.json
```

---

## Creating Good Test Datasets

Quality evaluation data is the foundation of quality measurement.

### Coverage Matrix

Aim for balanced coverage across domains and difficulty levels:

| Domain | Easy | Medium | Hard | Edge | Total |
|---|---|---|---|---|---|
| HR | 5 | 5 | 3 | 2 | 15 |
| Products | 5 | 5 | 3 | 2 | 15 |
| Marketing | 5 | 5 | 3 | 2 | 15 |
| Cross-domain | — | — | 3 | 2 | 5 |
| **Total** | 15 | 15 | 12 | 8 | **50** |

### What Each Difficulty Level Tests

| Level | Description | Example |
|---|---|---|
| **Easy** | Single-hop, clearly one domain | "What is the vacation policy?" |
| **Medium** | Requires synthesizing 2+ KB documents | "How do parental leave and FMLA interact?" |
| **Hard** | Requires inference or multi-hop reasoning | "If I join mid-year, how is my PTO prorated given the new policy changes?" |
| **Edge** | Boundary conditions and adversarial inputs | Empty query, prompt injection, multi-domain query |

### Multi-Hop Questions

These test whether the agent can synthesize across multiple documents:

```json
{
  "id": "hr-multi-001",
  "query": "I'm a part-time employee in the London office — what benefits am I eligible for and how does the remote work policy apply to me?",
  "expected_route": "hr",
  "expected_phrases": ["part-time", "benefits", "remote", "London"],
  "difficulty": "hard",
  "notes": "Requires combining: benefits policy + part-time eligibility + remote work policy + UK-specific rules"
}
```

---

## Analyzing Results

### Common Failure Patterns

After running evaluations, look for these patterns:

| Pattern | Symptom | Root Cause | Fix |
|---|---|---|---|
| **Wrong routing** | Router sends HR query to Products | Ambiguous query or missing few-shot examples | Add few-shot examples to router prompt |
| **Missing citations** | Response doesn't reference KB sources | Specialist prompt doesn't require citations | Add citation instructions to specialist prompt |
| **Hallucination** | Response contains facts not in KB | Model fills gaps with training data | Add "only use provided context" guardrail |
| **Incomplete answers** | Response answers part of the question | Model stops after addressing first aspect | Add "address all parts of the question" instruction |
| **Format mismatch** | User asks for a list, gets a paragraph | No output format instructions | Add format instructions to specialist prompt |

### Building an Analysis Script

```python
# tests/analyze_results.py
import json

def analyze(results_path: str = "tests/eval_results.json"):
    with open(results_path) as f:
        results = json.load(f)

    # Routing analysis
    route_failures = [r for r in results if not r.get("route_correct", True)]
    print(f"Routing failures: {len(route_failures)}/{len(results)}")
    for r in route_failures:
        print(f"  [{r['id']}] Expected: {r['expected_route']}, Got: {r['actual_route']}")

    # Response quality by domain
    domains = {}
    for r in results:
        domain = r.get("expected_route", "unknown")
        if domain not in domains:
            domains[domain] = {"total": 0, "passed": 0, "avg_coverage": []}
        domains[domain]["total"] += 1
        if r.get("passed"):
            domains[domain]["passed"] += 1
        if "phrase_coverage" in r:
            domains[domain]["avg_coverage"].append(r["phrase_coverage"])

    print(f"\nDomain breakdown:")
    for domain, stats in domains.items():
        avg_cov = (
            sum(stats["avg_coverage"]) / len(stats["avg_coverage"])
            if stats["avg_coverage"]
            else 0
        )
        print(f"  {domain}: {stats['passed']}/{stats['total']} passed, "
              f"avg phrase coverage: {avg_cov:.1%}")

    # Latency analysis
    latencies = [r["latency_s"] for r in results if "latency_s" in r]
    if latencies:
        print(f"\nLatency: avg={sum(latencies)/len(latencies):.2f}s, "
              f"p50={sorted(latencies)[len(latencies)//2]:.2f}s, "
              f"max={max(latencies):.2f}s")

if __name__ == "__main__":
    analyze()
```

---

## Prompt Optimization with Foundry

Azure AI Foundry includes a **prompt optimizer** that uses evaluation results to suggest improved prompts automatically.

### How It Works

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│  Current      │      │  Evaluation  │      │   Prompt     │
│  Prompt       │─────▶│  Results     │─────▶│  Optimizer   │
│  (v1.0)       │      │  (scores)    │      │              │
└──────────────┘      └──────────────┘      └──────┬───────┘
                                                     │
                                                     ▼
                                             ┌──────────────┐
                                             │  Suggested   │
                                             │  Prompt      │
                                             │  (v1.1)      │
                                             └──────────────┘
```

### Using the Prompt Optimizer

#### Step 1: Prepare Inputs

The optimizer needs:
- **Current system prompt** (e.g., your `HR_INSTRUCTIONS`)
- **Evaluation dataset** with queries, expected answers, and quality scores
- **Target metric** to optimize (e.g., groundedness, relevance)

#### Step 2: Run Optimization via Foundry Portal

1. Navigate to **Azure AI Foundry** → your project → **Prompt Optimizer**
2. Paste your current system prompt
3. Upload or select your evaluation dataset
4. Choose the target metric(s)
5. Click **Optimize**

The optimizer will:
- Analyze failure patterns in your evaluation results
- Identify which prompt weaknesses correlate with low scores
- Generate candidate improved prompts
- Score each candidate against your evaluation set
- Return the best-performing prompt variant

#### Step 3: Review and Adopt

```python
# After optimization — compare old vs new prompt
OLD_HR_INSTRUCTIONS = "You are an HR Specialist Agent..."  # v1.0
NEW_HR_INSTRUCTIONS = "..."  # v1.1 (from optimizer)

# Run evaluation on both and compare
# See tests/eval_runner.py for comparison approach
```

### Iterative Optimization Loop

Don't stop after one round. The best results come from iterating:

```
Round 1: Baseline prompt → Evaluate → Score: 3.2 groundedness
Round 2: Optimized prompt → Evaluate → Score: 3.8 groundedness
Round 3: Manual tweaks + optimize → Evaluate → Score: 4.2 groundedness
Round 4: Fine-tune edge cases → Evaluate → Score: 4.4 groundedness ✓
```

**When to stop:** When your scores hit the target thresholds (groundedness ≥ 4.0, relevance ≥ 4.0) and additional optimization rounds show diminishing returns (< 0.1 improvement).

---

## Continuous Monitoring

### Set Up Recurring Evaluation

Run evaluations on a schedule to catch regressions:

```yaml
# .github/workflows/eval-scheduled.yml
name: Scheduled Agent Evaluation
on:
  schedule:
    - cron: "0 6 * * 1"  # Every Monday at 6 AM UTC

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r app/backend/requirements.txt azure-ai-evaluation

      - name: Azure Login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Run evaluation
        run: python -m tests.eval_foundry_sdk

      - name: Check thresholds
        run: |
          python -c "
          import json, sys
          results = json.load(open('tests/eval_sdk_results.json'))
          metrics = ['groundedness', 'relevance']
          for m in metrics:
              vals = [r['scores'][m].get('score', 0) for r in results if m in r['scores']]
              avg = sum(vals) / len(vals) if vals else 0
              if avg < 4.0:
                  print(f'FAIL: {m} avg score {avg:.2f} is below threshold 4.0')
                  sys.exit(1)
          print('All quality thresholds passed')
          "
```

### Track Metrics Over Time

Store evaluation results with timestamps for trend analysis:

```python
# tests/eval_history.py
"""
Append evaluation results to a history file for trend tracking.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

HISTORY_FILE = Path("tests/eval_history.jsonl")

def append_to_history(results: list, prompt_versions: dict):
    """Append a timestamped evaluation run to the history file."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_versions": prompt_versions,
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.get("passed")),
        },
        "scores": {},
    }

    # Aggregate metric averages
    for metric in ["groundedness", "relevance", "coherence", "fluency"]:
        values = [
            r["scores"][metric].get("score", 0)
            for r in results
            if metric in r.get("scores", {})
        ]
        if values:
            entry["scores"][metric] = round(sum(values) / len(values), 2)

    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"Appended evaluation run to {HISTORY_FILE}")
```

### Alert on Regressions

```python
# tests/check_regression.py
"""
Compare the latest evaluation run against the previous one.
Exit with error code if any metric regressed by more than 0.3 points.
"""

import json
from pathlib import Path

HISTORY_FILE = Path("tests/eval_history.jsonl")
REGRESSION_THRESHOLD = 0.3

def check():
    lines = HISTORY_FILE.read_text().strip().split("\n")
    if len(lines) < 2:
        print("Not enough history to detect regressions.")
        return

    prev = json.loads(lines[-2])
    curr = json.loads(lines[-1])

    regressions = []
    for metric in ["groundedness", "relevance", "coherence", "fluency"]:
        prev_score = prev["scores"].get(metric, 0)
        curr_score = curr["scores"].get(metric, 0)
        delta = curr_score - prev_score
        if delta < -REGRESSION_THRESHOLD:
            regressions.append(f"{metric}: {prev_score:.2f} → {curr_score:.2f} (Δ{delta:+.2f})")

    if regressions:
        print("⚠️  REGRESSIONS DETECTED:")
        for r in regressions:
            print(f"  {r}")
        exit(1)
    else:
        print("✅ No regressions detected.")

if __name__ == "__main__":
    check()
```

---

## Summary

| Evaluation Method | Best For | Effort | Precision |
|---|---|---|---|
| Manual test suite | Quick iteration during development | Low | Medium |
| Foundry batch eval | Standardized quality metrics | Medium | High |
| SDK programmatic eval | CI/CD integration | Medium | High |
| Prompt optimizer | Automated prompt improvement | Low | Medium–High |

**Recommended workflow:**

1. Start with the manual test suite (Option 1) for rapid experimentation
2. Graduate to SDK-based evaluation (Option 3) for CI/CD
3. Use Foundry batch evaluation (Option 2) for milestone quality gates
4. Apply prompt optimization when scores plateau

---

## Next Steps

- Apply the prompt experiments from [05 — Prompt Engineering Lab](05-prompt-engineering-lab.md) and measure their impact using the evaluation approach above
- Once your agents meet quality thresholds, proceed to [07 — Deploy as Hosted Agents](07-deploy-hosted-agents.md) for production deployment
