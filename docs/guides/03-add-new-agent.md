# Add a New Specialist Agent — Finance

This tutorial walks you through adding a **Finance Agent** as a 4th specialist. You'll create it entirely through the **Microsoft Foundry portal UI** (no code required for the agent itself), then optionally wire it into the Python orchestrator.

> 🎯 **Who is this for?** Team members who want to learn how agents work by building one in the Foundry UI. No Python experience needed for Steps 1–5.

---

## Overview

| Step | What You'll Do | Where |
|------|---------------|-------|
| 1 | Create a search index for finance documents | Azure Portal |
| 2 | Upload sample finance documents | Azure Portal |
| 3 | Connect FoundryIQ and create a Knowledge Base | Foundry Portal |
| 4 | Create a Finance prompt agent with KB tool | Foundry Portal |
| 5 | Test the agent in the Foundry playground | Foundry Portal |
| 6 | *(Optional)* Wire into the Python orchestrator | Code |

---

## Prerequisites

- The demo is already deployed via `azd up` (see [Quick Start](./01-quick-start.md))
- Access to the [Azure Portal](https://portal.azure.com) and [Foundry Portal](https://ai.azure.com)
- Your user account has **Search Index Data Contributor** and **Azure AI Developer** roles (assigned automatically by `azd up`)

---

## Step 1: Create the Search Index (Azure Portal)

1. Go to **Azure Portal** → your resource group → click on the **Azure AI Search** resource
2. In the left menu, click **Indexes** → **+ Add index**
3. Set the index name to: `index-finance`
4. Add the following fields:

   | Field Name | Type | Key | Searchable | Retrievable | Filterable |
   |------------|------|-----|------------|-------------|------------|
   | `id` | Edm.String | ✅ | ❌ | ✅ | ✅ |
   | `title` | Edm.String | ❌ | ✅ | ✅ | ❌ |
   | `content` | Edm.String | ❌ | ✅ | ✅ | ❌ |
   | `category` | Edm.String | ❌ | ✅ | ✅ | ✅ |

5. Click the **Semantic configurations** tab → **+ Add**:
   - Configuration name: `default`
   - Title field: `title`
   - Content fields: `content`
   - Keyword fields: `category`
6. Click **Create**

---

## Step 2: Upload Sample Finance Documents (Azure Portal)

1. In the Azure AI Search resource, click **Indexes** → `index-finance`
2. Click the **Search explorer** tab at the top
3. Switch to **JSON view** and paste the following, then click **Upload**:

```json
{
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
}
```

4. Verify by running a search query in the explorer: type `budget` and click **Search**. You should see matching documents.

---

## Step 3: Create a Knowledge Base (Foundry Portal)

1. Go to [ai.azure.com](https://ai.azure.com) → select your **Foundry project**
2. In the left menu, click **Knowledge** (under the "Build" section)
3. If prompted to connect Azure AI Search:
   - Select your search resource
   - Choose **Managed Identity** (not API key)
   - Click **Connect**

### 3a. Create a Knowledge Source

4. Click **+ Add knowledge source**
5. Configure:
   - **Name**: `ks-finance`
   - **Type**: Azure AI Search
   - **Index**: Select `index-finance` from the dropdown
   - **Semantic configuration**: `default`
6. Click **Create**

### 3b. Create a Knowledge Base

7. Click **+ Create knowledge base**
8. Configure:
   - **Name**: `kb4-finance`
   - **Description**: "Finance knowledge base — budgets, expenses, financial policies, procurement, and accounting"
   - **Sources**: Select `ks-finance`
   - **Retrieval mode**: Agentic
9. Click **Create**

✅ You should now see `kb4-finance` alongside `kb1-hr`, `kb2-marketing`, and `kb3-products`.

---

## Step 4: Create the Finance Agent (Foundry Portal)

This is where the magic happens — you'll create a fully functional agent without writing any code.

1. In the Foundry portal, click **Agents** in the left menu
2. Click **+ New agent**
3. Configure the agent:

   | Setting | Value |
   |---------|-------|
   | **Name** | `finance-agent` |
   | **Type** | Prompt |
   | **Model** | `gpt-4.1` |

4. Set the **Instructions** (system prompt):

   ```
   You are a Finance Specialist Agent for Zava Corporation.

   Your role is to answer questions about budgets, expenses, financial
   policies, procurement, accounting standards, and financial planning.

   Guidelines:
   - Always ground your answers in the retrieved knowledge base documents.
     Do not fabricate financial figures or policies.
   - When citing specific numbers (budgets, thresholds, percentages),
     reference the source document title.
   - If the knowledge base does not contain information to answer the
     question, clearly state that and suggest contacting the Finance
     department directly.
   - Use clear, professional language appropriate for financial topics.
   - Include relevant thresholds, deadlines, and approval requirements
     when discussing policies.
   - Format your responses with bullet points for readability when listing
     multiple items.
   ```

5. Under **Tools**, click **+ Add tool** → **Azure AI Search**
6. In the search tool configuration:
   - Select your search resource
   - Under **Knowledge Base**, select `kb4-finance`
7. Click **Save**

---

## Step 5: Test in the Foundry Playground

1. After saving, click the **Test** tab (or the playground icon)
2. Try these sample queries:

   | Query | Expected Behavior |
   |-------|-------------------|
   | "What is the Q3 2024 budget?" | Returns $4.2M breakdown by department with percentages |
   | "What is the meal allowance for international travel?" | Returns $100/day from Expense Reimbursement Policy |
   | "How many bids do I need for a $15K purchase?" | Returns 3 competitive bids from Procurement policy |
   | "When are FY2025 budget proposals due?" | Returns November 15th from Financial Planning Guidelines |
   | "How does Zava Corp recognize SaaS revenue?" | Returns ASC 606 ratably over contract term |

3. Verify that responses:
   - ✅ Cite specific documents (grounded, not hallucinated)
   - ✅ Include actual numbers and dates from the uploaded documents
   - ✅ Are professional and well-formatted

> 💡 **Tip**: If responses seem generic (not citing your documents), go back to the Knowledge section and verify `kb4-finance` shows your knowledge source connected.

🎉 **Congratulations!** You've created a fully functional Finance agent using only the Foundry UI. Your team members can now test it directly in the playground.

---

## Understanding What You Built

Here's how the pieces fit together:

```
                     ┌─────────────────────────┐
                     │     Foundry Portal       │
                     │     (Playground)         │
                     └───────────┬─────────────┘
                                 │ User sends query
                                 ▼
                     ┌─────────────────────────┐
                     │    finance-agent         │
                     │    (Prompt Agent)        │
                     │                          │
                     │  Model: gpt-4.1          │
                     │  Tool: Azure AI Search   │
                     └───────────┬─────────────┘
                                 │ Retrieves context
                                 ▼
                     ┌─────────────────────────┐
                     │    kb4-finance           │
                     │    (Knowledge Base)      │
                     │                          │
                     │  Source: ks-finance       │
                     │  Mode: Agentic           │
                     └───────────┬─────────────┘
                                 │ Queries index
                                 ▼
                     ┌─────────────────────────┐
                     │    index-finance         │
                     │    (Search Index)        │
                     │                          │
                     │  5 finance documents     │
                     │  Semantic config enabled │
                     └─────────────────────────┘
```

**Key concepts:**
- **Prompt Agent**: An agent where Foundry manages the runtime — you just configure the instructions, model, and tools
- **Knowledge Base**: Wraps one or more search indexes with agentic retrieval (the model generates sub-queries to find the best documents)
- **Agentic Retrieval**: Unlike simple vector search, the model actively reasons about what to search for, resulting in higher-quality answers

---

## Step 6: (Optional, Advanced) Wire into the Python Orchestrator

> 🔧 **This step requires code changes.** Skip if you only need the standalone agent in the Foundry playground.

To make the orchestrator's frontend route "finance" queries to your new Foundry-hosted agent, you need to invoke it via the Foundry Agents API instead of running it locally.

### 6a. Update the Orchestrator

Edit `app/backend/agents/orchestrator.py`:

**Add the finance KB and agent constants at the top:**

```python
FIN_KB_NAME = "kb4-finance"
FIN_SOURCE_ID = os.getenv("KB4_FINANCE_SOURCE_ID", FIN_KB_NAME)

FINANCE_INSTRUCTIONS = """You are a Finance Specialist Agent for Zava Corporation.
Answer questions about budgets, expenses, financial policies, procurement, and accounting
using the knowledge base. Be specific and cite sources when possible."""
```

**Update `ROUTER_INSTRUCTIONS` to include finance:**

```python
ROUTER_INSTRUCTIONS = """You are a routing agent. Analyze the user query and determine which specialist should handle it.

Respond with ONLY one of these agent names:
- "hr"
- "marketing"
- "products"
- "finance"

Just respond with the agent name, nothing else."""
```

**Update the `route_query` function to detect finance keywords:**

```python
async def route_query(router: Agent, query: str) -> str:
    resp = await router.run(user_message(query))
    route = (resp.text or "").strip().lower()
    if "hr" in route:
        return "hr"
    if "marketing" in route or "brand" in route or "campaign" in route:
        return "marketing"
    if "product" in route:
        return "products"
    if "finance" in route or "budget" in route or "expense" in route:
        return "finance"
    return "hr"
```

**Add finance to the specialist agents in `run_orchestrator()` and `run_single_query()`:**

```python
async with (
    _make_client(credential) as router_client,
    _make_client(credential) as specialist_client,
    _make_kb(HR_SOURCE_ID, HR_KB_NAME, credential) as hr_kb,
    _make_kb(MKT_SOURCE_ID, MKT_KB_NAME, credential) as marketing_kb,
    _make_kb(PRD_SOURCE_ID, PRD_KB_NAME, credential) as products_kb,
    _make_kb(FIN_SOURCE_ID, FIN_KB_NAME, credential) as finance_kb,  # ← NEW
):
    router = Agent(client=router_client, instructions=ROUTER_INSTRUCTIONS)

    specialists = {
        "hr": Agent(client=specialist_client, context_provider=hr_kb, instructions=HR_INSTRUCTIONS),
        "marketing": Agent(client=specialist_client, context_provider=marketing_kb, instructions=MARKETING_INSTRUCTIONS),
        "products": Agent(client=specialist_client, context_provider=products_kb, instructions=PRODUCTS_INSTRUCTIONS),
        "finance": Agent(client=specialist_client, context_provider=finance_kb, instructions=FINANCE_INSTRUCTIONS),  # ← NEW
    }
```

### 6b. Update the Backend API Metadata

Edit `app/backend/main.py` — add the finance agent to the `/agents` endpoint:

```python
{
    "id": "finance",
    "name": "Finance Agent",
    "description": "Handles budgets, expenses, financial policies, procurement, and accounting",
    "kb": "kb4-finance",
    "color": "#F59E0B",
},
```

### 6c. Test the Full System

```bash
# Start backend
uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload

# Test finance routing
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the Q3 budget?"}' | python -m json.tool

# Verify other agents still work
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the PTO policy?"}' | python -m json.tool
```

---

## Two Approaches Compared

| | Foundry Portal Agent (Steps 1-5) | Orchestrator Integration (Step 6) |
|---|---|---|
| **Effort** | 15 minutes, no code | 30 minutes, Python changes |
| **Where it runs** | Foundry-managed runtime | Your Container App |
| **Accessible via** | Foundry playground UI | Frontend app + API |
| **Best for** | Testing, prototyping, non-technical users | Production multi-agent orchestration |
| **Scaling** | Foundry manages it | You manage Container App scaling |
| **Visible in Foundry portal** | ✅ Yes | ❌ Only the backend Container App |

> 💡 Both approaches use the **same** search index, knowledge base, and model. The difference is who runs the agent logic.

---

## Next Steps

- 🧪 [Prompt Engineering Lab](./05-prompt-engineering-lab.md) — experiment with your Finance agent's instructions
- 📚 [Customize Knowledge Bases](./04-customize-knowledge-bases.md) — replace sample data with real finance documents
- 📐 [Architecture Overview](./02-architecture-overview.md) — understand the full multi-agent system
