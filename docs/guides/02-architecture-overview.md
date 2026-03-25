# Architecture Overview

A deep-dive into how the **FoundryIQ and Agent Framework Demo** works — from user query to grounded response.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER                                           │
│                          (Browser / curl)                                   │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ HTTP
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     FRONTEND (React + TypeScript)                           │
│               Vite dev server @ localhost:5173                              │
│         Chat UI  ·  Agent route display  ·  Trace visualization            │
│                    Proxies /api/* → Backend                                 │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ HTTP (Vite proxy in dev / direct in prod)
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI + Uvicorn)                              │
│              Container App @ port 8000                                      │
│                                                                             │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │                    ORCHESTRATOR                                    │     │
│   │                                                                    │     │
│   │   ┌──────────────┐    route     ┌────────────────────────────┐    │     │
│   │   │ Router Agent  │───────────►│  Specialist Agent Dispatch  │    │     │
│   │   │  (no KB)      │  "hr" /     │                            │    │     │
│   │   │  gpt-4.1      │  "products" │  ┌──────────────────────┐  │    │     │
│   │   └──────────────┘  "marketing" │  │     HR Agent         │  │    │     │
│   │                                  │  │  + kb1-hr KB         │  │    │     │
│   │                                  │  ├──────────────────────┤  │    │     │
│   │                                  │  │   Products Agent     │  │    │     │
│   │                                  │  │  + kb3-products KB   │  │    │     │
│   │                                  │  ├──────────────────────┤  │    │     │
│   │                                  │  │  Marketing Agent     │  │    │     │
│   │                                  │  │  + kb2-marketing KB  │  │    │     │
│   │                                  │  └──────────────────────┘  │    │     │
│   │                                  └────────────────────────────┘    │     │
│   └───────────────────────────────────────────────────────────────────┘     │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │ SDK calls (DefaultAzureCredential)
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AZURE CLOUD                                         │
│                                                                             │
│   ┌───────────────────────────────────────────────────────────────────┐     │
│   │              Azure AI Services (kind: AIServices)                  │     │
│   │                                                                    │     │
│   │   ┌──────────────────────────────────────────────────────────┐    │     │
│   │   │           Azure AI Services Project                       │    │     │
│   │   │                                                           │    │     │
│   │   │   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │    │     │
│   │   │   │  kb1-hr      │  │kb2-marketing│  │kb3-products  │    │    │     │
│   │   │   │  (KB)        │  │  (KB)       │  │  (KB)        │    │    │     │
│   │   │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │    │     │
│   │   │          │                 │                 │           │    │     │
│   │   │   ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐    │    │     │
│   │   │   │ Knowledge   │  │ Knowledge   │  │ Knowledge   │    │    │     │
│   │   │   │ Source (HR) │  │Source (Mktg)│  │Source (Prod)│    │    │     │
│   │   │   └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │    │     │
│   │   │          │                 │                 │           │    │     │
│   │   └──────────┼─────────────────┼─────────────────┼──────────┘    │     │
│   └──────────────┼─────────────────┼─────────────────┼──────────────┘     │
│                  │                 │                 │                     │
│   ┌──────────────▼─────────────────▼─────────────────▼──────────────┐     │
│   │                  Azure AI Search                                 │     │
│   │                                                                  │     │
│   │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │     │
│   │   │  index-hr     │  │index-marketing│ │index-products │         │     │
│   │   │  (semantic)   │  │  (semantic)   │ │  (semantic)   │         │     │
│   │   └──────────────┘  └──────────────┘  └──────────────┘         │     │
│   └──────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │            gpt-4.1 Model Deployment                               │     │
│   └──────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The New Foundry Model (AIServices)

This demo uses the **new Microsoft Foundry resource model**, which replaces the legacy Azure Machine Learning hub + project pattern.

### Old Pattern (Deprecated)
```
Azure ML Hub
  └── Azure ML Project
        └── Connections, Deployments, etc.
```

### New Pattern (This Demo)
```
Azure AI Services (kind: AIServices)
  └── Azure AI Services Project (child resource)
        └── Agent definitions, Knowledge Bases, Model deployments
```

### Key Differences

| Aspect | Old (ML Hub) | New (AIServices) |
|--------|-------------|------------------|
| **Resource type** | `Microsoft.MachineLearningServices/workspaces` | `Microsoft.CognitiveServices/accounts` (kind: `AIServices`) |
| **Project type** | ML Workspace (kind: Hub/Project) | `Microsoft.CognitiveServices/accounts/projects` |
| **Endpoint format** | `https://<region>.api.azureml.ms/...` | `https://<ais-name>.services.ai.azure.com/api/projects/<project-name>` |
| **Authentication** | API keys or managed identity | **RBAC-only** (DefaultAzureCredential, no API keys) |
| **Agent SDK** | Azure ML SDK v2 | `agent-framework-azure-ai` |

### Project Endpoint Format

The SDK connects to agents via the project endpoint:

```
https://<aiservices-account-name>.services.ai.azure.com/api/projects/<project-name>
```

For example, if your AIServices account is `myais-eastus2` and your project is `agent-project`:

```
https://myais-eastus2.services.ai.azure.com/api/projects/agent-project
```

This endpoint is set via the `PROJECT_ENDPOINT` environment variable and used by `AzureAIAgentClient` to communicate with the Foundry project.

---

## How the Orchestrator Works

The orchestrator follows a **route-then-dispatch** pattern with strict client isolation.

### Step 1: Router Agent Classifies the Query

The Router Agent receives the user's query and determines which specialist should handle it.

```python
ROUTER_INSTRUCTIONS = """
You are a routing agent. Analyze the user's query and respond with
exactly one word — the name of the specialist agent best suited to
answer:

- "hr" — for employee policies, benefits, PTO, hiring, onboarding
- "products" — for product specs, features, comparisons, pricing
- "marketing" — for campaigns, brand strategy, social media, analytics

Respond with ONLY the agent name. No explanation.
"""
```

The Router Agent:
- Uses `gpt-4.1` for classification
- Has **no Knowledge Base** attached (it doesn't need retrieval)
- Returns a single word: `hr`, `products`, or `marketing`

### Step 2: Orchestrator Dispatches to Specialist

```python
async def route_query(message: str) -> dict:
    # 1. Create a SEPARATE client for the router
    router_client = AzureAIAgentClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )
    
    # Route the query
    route = await router_client.run(
        agent=router_agent,
        message=message
    )
    
    # 2. Create a SEPARATE client for the specialist
    specialist_client = AzureAIAgentClient(
        endpoint=PROJECT_ENDPOINT,
        credential=DefaultAzureCredential()
    )
    
    # 3. Dispatch to the correct specialist
    specialist = agents[route.strip().lower()]
    response = await specialist_client.run(
        agent=specialist,
        message=message
    )
    
    return {"agent": route, "response": response}
```

> **⚠️ Critical: Separate Client Instances**
>
> The router and each specialist agent **must** use separate `AzureAIAgentClient` instances. Sharing a single client across agents causes a shared-state bug where conversation threads from the router bleed into specialist agent sessions, producing incorrect or garbled responses. Always instantiate a new client for each logical agent interaction.

### Step 3: Specialist Agent Generates Grounded Response

Each specialist agent:
1. Receives the user's original query
2. Uses its `AzureAISearchContextProvider` to query the relevant Knowledge Base
3. The KB performs **agentic retrieval** against the Azure AI Search index
4. The agent generates a response grounded in the retrieved documents

```python
# Example: HR Agent setup
hr_context_provider = AzureAISearchContextProvider(
    knowledge_base_name="kb1-hr",
    search_endpoint=SEARCH_ENDPOINT,
    index_name="index-hr"
)

hr_agent = Agent(
    name="HR Specialist",
    instructions=HR_INSTRUCTIONS,
    context_providers=[hr_context_provider],
    model="gpt-4.1"
)
```

---

## How FoundryIQ Knowledge Bases Work

FoundryIQ Knowledge Bases provide a managed abstraction over Azure AI Search, enabling **agentic retrieval** for grounded agent responses.

### The Knowledge Base Stack

```
┌─────────────────────────────────────────────┐
│           FoundryIQ Knowledge Base            │
│           (e.g., kb1-hr)                      │
│                                               │
│   Orchestrates retrieval, manages context     │
│   window, handles citation tracking           │
├─────────────────────────────────────────────┤
│           Knowledge Source                    │
│                                               │
│   Maps to a specific Azure AI Search index    │
│   Defines retrieval parameters                │
├─────────────────────────────────────────────┤
│           Azure AI Search Index               │
│           (e.g., index-hr)                    │
│                                               │
│   Stores documents with semantic config       │
│   Supports vector, keyword, and hybrid search │
└─────────────────────────────────────────────┘
```

### Layer Descriptions

| Layer | Purpose |
|-------|---------|
| **Azure AI Search Index** | Stores your documents with fields like `id`, `title`, `content`, `category`. Has a semantic configuration for ranking. |
| **Knowledge Source** | A pointer from the Foundry project to a specific search index. Defines the connection string and retrieval parameters. |
| **Knowledge Base** | A high-level container that groups one or more Knowledge Sources. This is what the agent SDK references by name. |

### In the SDK

The `AzureAISearchContextProvider` connects an agent to a Knowledge Base:

```python
from agent_framework_azure_ai_search import AzureAISearchContextProvider

context_provider = AzureAISearchContextProvider(
    knowledge_base_name="kb1-hr",
    search_endpoint=SEARCH_ENDPOINT,
    index_name="index-hr"
)
```

At runtime, when the agent processes a query:
1. The context provider sends the query to the Knowledge Base
2. The KB uses agentic retrieval to fetch relevant documents
3. Retrieved content is injected into the agent's context window
4. The agent generates a response grounded in the retrieved documents

---

## Agentic Retrieval vs Standard Search

Traditional vector search sends a single query to the index and returns top-K results. **Agentic retrieval** is fundamentally different.

### Standard Vector Search
```
User Query → Embed → Vector Search → Top-K Results → LLM
```

### Agentic Retrieval (FoundryIQ)
```
User Query → LLM analyzes intent
           → Generates multiple sub-queries
           → Executes each sub-query against the index
           → Aggregates and re-ranks results
           → Selects most relevant passages
           → Returns enriched context to the agent
```

### Key Advantages

| Feature | Standard Search | Agentic Retrieval |
|---------|----------------|-------------------|
| **Query understanding** | Literal embedding | Model-driven intent analysis |
| **Sub-query generation** | None | Automatic decomposition of complex queries |
| **Multi-hop reasoning** | Not supported | Follows chains of related documents |
| **Result quality** | Depends on embedding similarity | Model re-ranks for relevance |
| **Ambiguity handling** | Poor | Generates clarifying sub-queries |

For example, the query *"How does the PTO policy differ for part-time vs full-time employees?"* might generate:
1. Sub-query: "PTO policy full-time employees"
2. Sub-query: "PTO policy part-time employees"
3. Sub-query: "employee classification part-time full-time"

Each sub-query retrieves relevant chunks, which are then aggregated and ranked for the final agent context.

---

## RBAC Chain (Identity and Access Management)

This demo uses **RBAC-only authentication** — no API keys anywhere. Every service-to-service call uses managed identities.

### Identity Map

```
┌───────────────────────┐     ┌──────────────────────────────────────┐
│   Your User Account   │────►│  Cognitive Services User              │
│   (az login)          │     │  on AIServices account               │
└───────────────────────┘     └──────────────────────────────────────┘

┌───────────────────────┐     ┌──────────────────────────────────────┐
│  Container App MI     │────►│  Cognitive Services User              │
│  (backend identity)   │     │  on AIServices account               │
│                       │────►│  Search Index Data Reader             │
│                       │     │  on Azure AI Search                   │
└───────────────────────┘     └──────────────────────────────────────┘

┌───────────────────────┐     ┌──────────────────────────────────────┐
│  AIServices MI        │────►│  Search Index Data Reader             │
│  (system-assigned)    │     │  on Azure AI Search                   │
│                       │────►│  Search Service Contributor           │
│                       │     │  on Azure AI Search                   │
└───────────────────────┘     └──────────────────────────────────────┘

┌───────────────────────┐     ┌──────────────────────────────────────┐
│  Project MI           │────►│  Search Index Data Reader             │
│  (system-assigned)    │     │  on Azure AI Search                   │
│                       │────►│  Cognitive Services User              │
│                       │     │  on parent AIServices account         │
└───────────────────────┘     └──────────────────────────────────────┘

┌───────────────────────┐     ┌──────────────────────────────────────┐
│  Azure AI Search MI   │────►│  (outbound to data sources if using   │
│  (system-assigned)    │     │   indexers with blob/SQL/etc.)        │
└───────────────────────┘     └──────────────────────────────────────┘
```

### Required Role Assignments

| Principal | Role | Scope | Why |
|-----------|------|-------|-----|
| Your user account | `Cognitive Services User` | AIServices account | Local development with `az login` |
| Container App MI | `Cognitive Services User` | AIServices account | Backend calls agent APIs |
| Container App MI | `Search Index Data Reader` | Azure AI Search | Backend reads search indexes |
| AIServices MI | `Search Index Data Reader` | Azure AI Search | Foundry reads indexes for KBs |
| AIServices MI | `Search Service Contributor` | Azure AI Search | Foundry manages index configurations |
| Project MI | `Search Index Data Reader` | Azure AI Search | Project-level index access |
| Project MI | `Cognitive Services User` | AIServices account | Project calls parent model deployments |

> **Note:** RBAC role assignments can take **up to 10 minutes** to propagate. If you see 401/403 errors immediately after `azd up`, wait and retry.

---

## Frontend Architecture

The frontend is a **React + TypeScript** single-page application built with **Vite**.

### Key Components

```
app/frontend/
├── src/
│   ├── components/
│   │   ├── ChatInterface.tsx    # Main chat UI
│   │   ├── MessageBubble.tsx    # Individual message display
│   │   ├── AgentBadge.tsx       # Shows which agent handled the query
│   │   └── TraceViewer.tsx      # Visualizes the routing + retrieval trace
│   ├── api/
│   │   └── client.ts            # API client for backend calls
│   ├── App.tsx                  # Root component
│   └── main.tsx                 # Entry point
├── vite.config.ts               # Vite config with proxy settings
├── package.json
└── tsconfig.json
```

### Dev Proxy Configuration

In development, Vite proxies API requests to the local backend:

```typescript
// vite.config.ts
export default defineConfig({
  server: {
    proxy: {
      '/chat': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/agents': 'http://localhost:8000',
    }
  }
});
```

This means:
- Frontend serves at `http://localhost:5173`
- API calls to `/chat`, `/health`, `/agents` are proxied to `http://localhost:8000`
- No CORS configuration needed in development

### Trace Visualization

The frontend includes a trace viewer that shows:
1. The original user query
2. The Router Agent's classification decision
3. Which specialist agent was dispatched
4. The Knowledge Base retrieval results (documents found)
5. The final grounded response with source citations

---

## Infrastructure as Code (Bicep)

All Azure resources are defined in Bicep templates under `infra/`.

### Bicep Structure

```
infra/
├── main.bicep                    # Entry point — orchestrates all modules
├── main.parameters.json          # Default parameter values
├── modules/
│   ├── ai-services.bicep         # AIServices account + project
│   ├── ai-search.bicep           # Azure AI Search service
│   ├── container-app.bicep       # Container App + Environment
│   ├── managed-identity.bicep    # User-assigned managed identities
│   └── role-assignments.bicep    # All RBAC role assignments
└── scripts/
    └── postprovision.sh          # Post-provision setup script
```

### Key Resources Created

| Resource | Bicep Module | Purpose |
|----------|-------------|---------|
| `Microsoft.CognitiveServices/accounts` (kind: AIServices) | `ai-services.bicep` | Foundry resource hosting model deployments and project |
| `Microsoft.CognitiveServices/accounts/projects` | `ai-services.bicep` | Child project for agent management and KBs |
| `Microsoft.Search/searchServices` | `ai-search.bicep` | Hosts search indexes for each knowledge domain |
| `Microsoft.App/containerApps` | `container-app.bicep` | Runs the FastAPI backend |
| `Microsoft.App/managedEnvironments` | `container-app.bicep` | Container App execution environment |
| `Microsoft.Authorization/roleAssignments` | `role-assignments.bicep` | RBAC grants for all managed identities |

### Post-Provision Script

After Bicep creates the infrastructure, the post-provision script (`infra/scripts/postprovision.sh`) handles the data plane setup that can't be done in Bicep:

1. **Creates search indexes** with semantic configurations
2. **Uploads sample documents** (Zava Corp HR policies, product catalogs, marketing plans)
3. **Creates Knowledge Sources** in the Foundry project, pointing to each index
4. **Creates Knowledge Bases** (`kb1-hr`, `kb2-marketing`, `kb3-products`) referencing the sources
5. **Verifies** all resources are accessible

---

## Request Flow (End-to-End)

Here's what happens when a user asks *"What is the PTO policy?"*:

```
1. User types "What is the PTO policy?" in the React chat UI

2. Frontend POSTs to /chat with {"message": "What is the PTO policy?"}

3. FastAPI backend receives the request in the /chat endpoint

4. Orchestrator creates a Router Agent client (new AzureAIAgentClient instance)

5. Router Agent (gpt-4.1) analyzes the query:
   → Input:  "What is the PTO policy?"
   → Output: "hr"

6. Orchestrator creates a Specialist Agent client (NEW AzureAIAgentClient instance)

7. HR Specialist Agent receives the query with its AzureAISearchContextProvider:
   a. Context provider sends query to kb1-hr Knowledge Base
   b. KB performs agentic retrieval:
      - Generates sub-queries: "PTO policy", "paid time off", "vacation days"
      - Searches index-hr with each sub-query
      - Aggregates and re-ranks results
   c. Retrieved document chunks are injected into agent context
   d. Agent generates grounded response using gpt-4.1

8. Response returned to FastAPI: {agent: "hr", response: "...", sources: [...]}

9. Frontend displays the response with agent badge and source citations
```

---

## Next Steps

- 🚀 [Quick Start](./01-quick-start.md) — deploy the demo from scratch
- 🤖 [Add a New Agent](./03-add-new-agent.md) — extend the system with a 4th specialist
- 📚 [Customize Knowledge Bases](./04-customize-knowledge-bases.md) — use your own data
