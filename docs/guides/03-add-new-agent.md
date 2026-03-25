# Add a New Specialist Agent

This tutorial walks you through adding a **Finance Agent** as a 4th specialist in the multi-agent orchestrator. By the end, your system will route finance-related questions to a dedicated agent backed by its own FoundryIQ Knowledge Base.

---

## Overview

Adding a new specialist requires six steps:

| Step | What You'll Do |
|------|---------------|
| 1 | Create an Azure AI Search index for finance documents |
| 2 | Create a FoundryIQ Knowledge Base (`kb4-finance`) |
| 3 | Write the Finance Agent code |
| 4 | Wire the agent into the Orchestrator |
| 5 | Update the Backend API metadata |
| 6 | Test end-to-end |

---

## Prerequisites

- The demo is already deployed via `azd up` (see [Quick Start](./01-quick-start.md))
- You have the Azure environment variables loaded locally:
  ```bash
  eval $(azd env get-values | sed 's/^/export /')
  ```
- You have the required CLI tools: `az`, `python`, `curl`

---

## Step 1: Create the Search Index

### 1a. Define the Index Schema

Create `index-finance` with the same field structure used by the other indexes:

```bash
SEARCH_ENDPOINT=$(azd env get-value AZURE_SEARCH_ENDPOINT)
SEARCH_ADMIN_KEY=$(az search admin-key show \
  --resource-group $(azd env get-value AZURE_RESOURCE_GROUP) \
  --service-name $(azd env get-value AZURE_SEARCH_SERVICE_NAME) \
  --query primaryKey -o tsv)

curl -X PUT "$SEARCH_ENDPOINT/indexes/index-finance?api-version=2024-07-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -d '{
    "name": "index-finance",
    "fields": [
      {"name": "id", "type": "Edm.String", "key": true, "filterable": true},
      {"name": "title", "type": "Edm.String", "searchable": true, "retrievable": true},
      {"name": "content", "type": "Edm.String", "searchable": true, "retrievable": true},
      {"name": "category", "type": "Edm.String", "filterable": true, "facetable": true, "retrievable": true}
    ],
    "semantic": {
      "configurations": [
        {
          "name": "default",
          "prioritizedFields": {
            "titleField": {"fieldName": "title"},
            "contentFields": [{"fieldName": "content"}],
            "keywordsFields": [{"fieldName": "category"}]
          }
        }
      ]
    }
  }'
```

### 1b. Upload Sample Finance Documents

```bash
curl -X POST "$SEARCH_ENDPOINT/indexes/index-finance/docs/index?api-version=2024-07-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -d '{
    "value": [
      {
        "@search.action": "upload",
        "id": "fin-001",
        "title": "Q3 2024 Budget Report",
        "content": "The Q3 2024 budget for Zava Corp totals $4.2M across all departments. Engineering received $1.8M (43%), Marketing $800K (19%), Sales $600K (14%), and Operations $1.0M (24%). Notable variances include a 12% overspend in cloud infrastructure costs offset by 8% savings in travel and events. The board has approved an additional $200K contingency fund for Q4 hiring initiatives.",
        "category": "budget"
      },
      {
        "@search.action": "upload",
        "id": "fin-002",
        "title": "Expense Reimbursement Policy",
        "content": "All employees must submit expense reports within 30 days of incurring the expense. Receipts are required for any expense over $25. Travel expenses must be pre-approved by the department manager for amounts exceeding $500. Meal allowances are capped at $75/day for domestic travel and $100/day for international travel. Mileage reimbursement is $0.67/mile. Expense reports are processed bi-weekly on the 1st and 15th of each month, with reimbursement appearing in the following pay period.",
        "category": "policy"
      },
      {
        "@search.action": "upload",
        "id": "fin-003",
        "title": "Financial Planning Guidelines",
        "content": "Department budget proposals for FY2025 are due by November 15th. Each department must submit a line-item budget with justifications for any increase exceeding 10% over the current fiscal year. Capital expenditure requests over $50K require CFO approval and board notification. All recurring SaaS subscriptions must be reviewed quarterly and reported to the Finance team. The company targets an operating margin of 18-22% and maintains a minimum cash reserve of 6 months operating expenses.",
        "category": "planning"
      },
      {
        "@search.action": "upload",
        "id": "fin-004",
        "title": "Procurement and Vendor Management",
        "content": "All purchases over $10K require three competitive bids. Preferred vendor contracts are negotiated annually by the Procurement team. Sole-source justifications require VP-level approval. Payment terms are Net-30 for all vendors unless otherwise negotiated. The approved vendor list is maintained in the Finance SharePoint site and updated quarterly. New vendor onboarding requires W-9 collection, credit check, and compliance verification.",
        "category": "procurement"
      },
      {
        "@search.action": "upload",
        "id": "fin-005",
        "title": "Revenue Recognition Policy",
        "content": "Zava Corp follows ASC 606 for revenue recognition. SaaS subscription revenue is recognized ratably over the contract term. Professional services revenue is recognized on a percentage-of-completion basis. Hardware revenue is recognized upon delivery and customer acceptance. Multi-element arrangements are allocated using standalone selling prices. Contract modifications are evaluated as either prospective or cumulative catch-up adjustments.",
        "category": "accounting"
      }
    ]
  }'
```

### 1c. Verify the Index

```bash
# Check document count
curl "$SEARCH_ENDPOINT/indexes/index-finance/docs/\$count?api-version=2024-07-01" \
  -H "api-key: $SEARCH_ADMIN_KEY"
# Expected: 5

# Test a search query
curl -X POST "$SEARCH_ENDPOINT/indexes/index-finance/docs/search?api-version=2024-07-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -d '{"search": "Q3 budget", "queryType": "semantic", "semanticConfiguration": "default", "top": 3}'
```

---

## Step 2: Create the Knowledge Base

### 2a. Create a Knowledge Source

The Knowledge Source connects the Foundry project to the `index-finance` search index.

```bash
PROJECT_ENDPOINT=$(azd env get-value PROJECT_ENDPOINT)
ACCESS_TOKEN=$(az account get-access-token \
  --resource "https://cognitiveservices.azure.com" \
  --query accessToken -o tsv)

curl -X PUT "$PROJECT_ENDPOINT/knowledge/sources/ks-finance?api-version=2025-11-01-preview" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "type": "AzureAISearch",
    "properties": {
      "endpoint": "'$SEARCH_ENDPOINT'",
      "indexName": "index-finance",
      "authenticationType": "SystemAssignedManagedIdentity",
      "semanticConfiguration": "default"
    }
  }'
```

### 2b. Create the Knowledge Base

The Knowledge Base groups the knowledge source and is referenced by name in the agent SDK.

```bash
curl -X PUT "$PROJECT_ENDPOINT/knowledge/bases/kb4-finance?api-version=2025-11-01-preview" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "description": "Finance knowledge base containing budget reports, expense policies, financial guidelines, and procurement procedures.",
    "sources": [
      {
        "sourceName": "ks-finance"
      }
    ],
    "retrievalMode": "agentic"
  }'
```

### 2c. Verify the Knowledge Base

```bash
# List all Knowledge Bases
curl "$PROJECT_ENDPOINT/knowledge/bases?api-version=2025-11-01-preview" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python -m json.tool

# Get the finance KB specifically
curl "$PROJECT_ENDPOINT/knowledge/bases/kb4-finance?api-version=2025-11-01-preview" \
  -H "Authorization: Bearer $ACCESS_TOKEN" | python -m json.tool
```

You should see `kb4-finance` listed alongside `kb1-hr`, `kb2-marketing`, and `kb3-products`.

---

## Step 3: Create the Agent Code

Create the file `app/backend/agents/finance_agent.py`:

```python
"""
Finance Specialist Agent

Handles finance-related queries using the kb4-finance FoundryIQ
Knowledge Base for grounded retrieval over budget reports, expense
policies, financial guidelines, and procurement procedures.
"""

import asyncio
import os

from agent_framework_core import Agent
from agent_framework_azure_ai import AzureAIAgentClient
from agent_framework_azure_ai_search import AzureAISearchContextProvider
from azure.identity import DefaultAzureCredential

# ── Configuration ──────────────────────────────────────────────────
PROJECT_ENDPOINT = os.environ["PROJECT_ENDPOINT"]
SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]

# ── System Prompt ──────────────────────────────────────────────────
FINANCE_INSTRUCTIONS = """
You are a Finance specialist agent for Zava Corp. Your role is to answer
questions about budgets, expenses, financial policies, procurement,
accounting standards, and financial planning.

Guidelines:
- Always ground your answers in the retrieved documents from the
  knowledge base. Do not fabricate financial figures or policies.
- When citing specific numbers (budgets, thresholds, percentages),
  reference the source document.
- If the knowledge base does not contain information to answer the
  question, clearly state that and suggest the user contact the
  Finance department directly.
- Use clear, professional language appropriate for financial topics.
- When discussing policies, include relevant thresholds, deadlines,
  and approval requirements.
"""

# ── Context Provider (FoundryIQ KB) ───────────────────────────────
finance_context_provider = AzureAISearchContextProvider(
    knowledge_base_name="kb4-finance",
    search_endpoint=SEARCH_ENDPOINT,
    index_name="index-finance",
)

# ── Agent Definition ──────────────────────────────────────────────
finance_agent = Agent(
    name="Finance Specialist",
    instructions=FINANCE_INSTRUCTIONS,
    context_providers=[finance_context_provider],
    model="gpt-4.1",
)


async def run_finance_agent(message: str) -> dict:
    """
    Run the Finance agent with the given message.

    Creates a dedicated AzureAIAgentClient instance to avoid shared
    state issues with other agents in the orchestrator.

    Args:
        message: The user's finance-related query.

    Returns:
        Dictionary with 'agent', 'response', and 'sources' keys.
    """
    client = AzureAIAgentClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
    )

    try:
        result = await client.run(
            agent=finance_agent,
            message=message,
        )

        return {
            "agent": "finance",
            "response": result.content,
            "sources": result.sources if hasattr(result, "sources") else [],
        }
    finally:
        await client.close()


# ── Standalone Testing ────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "What is the Q3 budget?"
    print(f"\n💰 Finance Agent — Query: {query}\n")

    result = asyncio.run(run_finance_agent(query))

    print(f"Agent:    {result['agent']}")
    print(f"Response: {result['response']}")
    if result["sources"]:
        print(f"Sources:  {result['sources']}")
```

### Code Structure Explained

| Component | Purpose |
|-----------|---------|
| `FINANCE_INSTRUCTIONS` | System prompt that defines the agent's persona and response guidelines |
| `AzureAISearchContextProvider` | Connects to `kb4-finance` for grounded retrieval |
| `Agent(...)` | Defines the agent with model, instructions, and context provider |
| `run_finance_agent()` | Creates a **dedicated** client instance and runs the agent |
| `__main__` block | Enables standalone testing from the command line |

---

## Step 4: Wire into the Orchestrator

Update `app/backend/orchestrator.py` to include the Finance agent.

### 4a. Update Router Instructions

Add `"finance"` as a routing option:

```python
ROUTER_INSTRUCTIONS = """
You are a routing agent. Analyze the user's query and respond with
exactly one word — the name of the specialist agent best suited to
answer:

- "hr" — for employee policies, benefits, PTO, hiring, onboarding
- "products" — for product specs, features, comparisons, pricing
- "marketing" — for campaigns, brand strategy, social media, analytics
- "finance" — for budgets, expenses, financial policies, procurement, accounting

Respond with ONLY the agent name. No explanation.
"""
```

### 4b. Import and Register the Finance Agent

Add the finance agent imports and configuration:

```python
# Add import at the top of orchestrator.py
from app.backend.agents.finance_agent import (
    finance_agent,
    finance_context_provider,
    run_finance_agent,
)

# Add to the agents dictionary (alongside existing entries)
agents = {
    "hr": run_hr_agent,
    "products": run_products_agent,
    "marketing": run_marketing_agent,
    "finance": run_finance_agent,  # ← NEW
}
```

### 4c. Update the Route Query Function

Ensure the `route_query` function handles the new route:

```python
async def route_query(message: str) -> dict:
    # Create router client
    router_client = AzureAIAgentClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential(),
    )

    try:
        route_result = await router_client.run(
            agent=router_agent,
            message=message,
        )
        route = route_result.content.strip().lower()
    finally:
        await router_client.close()

    # Validate route
    if route not in agents:
        return {
            "agent": "unknown",
            "response": f"I couldn't determine the right specialist for your question. "
                        f"Detected route: '{route}'. Try rephrasing your question.",
            "sources": [],
        }

    # Dispatch to specialist
    return await agents[route](message)
```

> **Note:** Because `agents` is a dictionary, adding a new entry automatically makes it available to `route_query` without additional conditional logic.

---

## Step 5: Update the Backend API

Update `app/backend/main.py` to include the Finance agent in the `/agents` metadata endpoint:

```python
@app.get("/agents")
async def list_agents():
    """Return metadata about available specialist agents."""
    return {
        "agents": [
            {
                "name": "hr",
                "description": "Employee policies, benefits, PTO, hiring, onboarding",
                "knowledge_base": "kb1-hr",
                "index": "index-hr",
            },
            {
                "name": "products",
                "description": "Product specs, features, comparisons, pricing",
                "knowledge_base": "kb3-products",
                "index": "index-products",
            },
            {
                "name": "marketing",
                "description": "Campaigns, brand strategy, social media, analytics",
                "knowledge_base": "kb2-marketing",
                "index": "index-marketing",
            },
            {
                "name": "finance",  # ← NEW
                "description": "Budgets, expenses, financial policies, procurement, accounting",
                "knowledge_base": "kb4-finance",
                "index": "index-finance",
            },
        ]
    }
```

---

## Step 6: Test

### 6a. Test the Agent Standalone

```bash
# Make sure environment variables are loaded
eval $(azd env get-values | sed 's/^/export /')

# Run the finance agent directly
python -m app.backend.agents.finance_agent "What is the Q3 budget?"
```

Expected output:

```
💰 Finance Agent — Query: What is the Q3 budget?

Agent:    finance
Response: The Q3 2024 budget for Zava Corp totals $4.2M across all
          departments. Engineering received $1.8M (43%), Marketing $800K
          (19%), Sales $600K (14%), and Operations $1.0M (24%)...
Sources:  [{'title': 'Q3 2024 Budget Report', 'id': 'fin-001'}]
```

### 6b. Test via the Orchestrator

```bash
# Start the backend
uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

In a separate terminal:

```bash
# Test routing to finance agent
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the Q3 budget?"}'
```

Expected response:

```json
{
  "agent": "finance",
  "response": "The Q3 2024 budget for Zava Corp totals $4.2M...",
  "sources": [{"title": "Q3 2024 Budget Report", "id": "fin-001"}]
}
```

### 6c. Test Multiple Finance Queries

```bash
# Expense policy
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the expense reimbursement limit for meals?"}' | python -m json.tool

# Procurement
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How many bids do I need for a $15K purchase?"}' | python -m json.tool

# Budget planning
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "When are FY2025 budget proposals due?"}' | python -m json.tool
```

### 6d. Verify Other Agents Still Work

Ensure the new agent doesn't break existing routing:

```bash
# Should route to HR
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the PTO policy?"}' | python -m json.tool

# Should route to Products
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me about the fitness watch"}' | python -m json.tool
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `app/backend/agents/finance_agent.py` | **New file** — Finance specialist agent |
| `app/backend/orchestrator.py` | Updated router instructions + registered finance agent |
| `app/backend/main.py` | Added finance to `/agents` endpoint metadata |
| Azure AI Search | New `index-finance` index with sample documents |
| Foundry Project | New `ks-finance` knowledge source + `kb4-finance` knowledge base |

---

## Optional: Automate with Infrastructure as Code

To make the Finance agent part of the standard `azd up` deployment, update:

1. **Post-provision script** (`infra/scripts/postprovision.sh`) — add index creation, document upload, knowledge source, and knowledge base creation for finance.

2. **Bicep parameters** — if you want to parameterize the index/KB names, add them to `infra/main.parameters.json`.

This ensures the finance agent is provisioned automatically for new deployments.

---

## Next Steps

- 📐 [Architecture Overview](./02-architecture-overview.md) — understand how routing and retrieval work
- 📚 [Customize Knowledge Bases](./04-customize-knowledge-bases.md) — replace sample finance data with real documents
