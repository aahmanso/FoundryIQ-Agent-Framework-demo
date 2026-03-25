# Quick Start Guide

Get the **FoundryIQ and Agent Framework Demo** running from scratch. This guide walks you through provisioning Azure resources, deploying the multi-agent orchestrator, and sending your first queries.

---

## Prerequisites

Before you begin, ensure you have the following installed and configured:

| Tool | Minimum Version | Install Link |
|------|----------------|--------------|
| **Azure Subscription** | Pay-as-you-go or higher | [azure.microsoft.com](https://azure.microsoft.com/free/) |
| **Azure CLI** (`az`) | 2.65+ | [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| **Azure Developer CLI** (`azd`) | 1.12+ | [Install azd](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd) |
| **Python** | 3.11+ | [python.org](https://www.python.org/downloads/) |
| **Node.js** | 20 LTS+ | [nodejs.org](https://nodejs.org/) |
| **Git** | Latest | [git-scm.com](https://git-scm.com/) |

### Azure Subscription Requirements

- You need **Owner** or **Contributor + User Access Administrator** on the subscription so that `azd up` can assign RBAC roles.
- The subscription must have quota for **gpt-4.1** model deployments in your target region.
- Azure AI Search (Basic tier or higher) must be available in your target region.

> **Tip:** Run `az account show` to verify you're on the correct subscription.

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/<your-org>/FoundryIQ-Agent-Framework-demo.git
cd FoundryIQ-Agent-Framework-demo
```

---

## Step 2: Create a Python Virtual Environment

```bash
# Create and activate virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

---

## Step 3: Install Dependencies

```bash
# Backend dependencies
pip install -r requirements.txt

# Frontend dependencies
cd app/frontend
npm install
cd ../..
```

The backend uses these key SDK packages:
- `agent-framework-core` — core orchestration primitives
- `agent-framework-azure-ai` — Azure AI Foundry agent client
- `agent-framework-azure-ai-search` — Azure AI Search context provider (FoundryIQ)

---

## Step 4: Authenticate with Azure

```bash
# Log in to Azure CLI (opens browser)
az login

# Log in to Azure Developer CLI
azd auth login
```

Verify your subscription:

```bash
az account show --query "{name:name, id:id, state:state}" -o table
```

If you need to switch subscriptions:

```bash
az account set --subscription "<subscription-id>"
```

---

## Step 5: Deploy with `azd up`

```bash
azd up
```

You will be prompted for:

| Prompt | What to Enter |
|--------|--------------|
| **Environment name** | A unique name (e.g., `foundryiq-demo-dev`) |
| **Azure subscription** | Select your subscription |
| **Azure location** | Choose a region with gpt-4.1 and AI Search support (e.g., `eastus2`) |

### What `azd up` Does Behind the Scenes

`azd up` is a single command that orchestrates the full deployment pipeline:

1. **`azd provision`** — Runs `infra/main.bicep` to create all Azure resources:
   - **Azure AI Services** (kind: `AIServices`) — the new Foundry resource (replaces the old ML hub pattern)
   - **Azure AI Services Project** — child resource of AIServices for agent management
   - **Azure AI Search** (Basic tier) — hosts the knowledge base indexes
   - **Container App Environment + Container App** — hosts the FastAPI backend on port 8000
   - **Managed Identities** — system-assigned identities for each resource
   - **RBAC Role Assignments** — grants identities the correct permissions across resources

2. **Model Deployment** — Deploys the **gpt-4.1** model to the AIServices resource.

3. **Post-Provision Scripts** — Runs automatically after infrastructure is created:
   - Creates Azure AI Search indexes (`index-hr`, `index-marketing`, `index-products`) with semantic configurations
   - Uploads sample Zava Corp documents to each index
   - Creates FoundryIQ Knowledge Sources pointing to each index
   - Creates FoundryIQ Knowledge Bases (`kb1-hr`, `kb2-marketing`, `kb3-products`)
   - Assigns any remaining RBAC roles

4. **`azd deploy`** — Builds the backend container image and deploys it to the Container App.

The entire process takes approximately **10–15 minutes**.

---

## Step 6: Verify the Deployment

### Check Azure Portal

Navigate to the [Azure Portal](https://portal.azure.com) and verify these resources exist in your resource group:

- ✅ Azure AI Services account (kind: AIServices)
- ✅ Azure AI Services Project (child resource)
- ✅ Azure AI Search service with 3 indexes
- ✅ Container App running the backend
- ✅ Container App Environment

### Test the Backend Health Endpoint

```bash
# Get the backend URL from azd
BACKEND_URL=$(azd env get-value BACKEND_URI)

# Test health endpoint
curl "$BACKEND_URL/health"
```

Expected response:

```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

### Test the Chat Endpoint

```bash
curl -X POST "$BACKEND_URL/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the PTO policy?"}'
```

Expected response:

```json
{
  "response": "According to Zava Corp's HR policy, employees receive...",
  "agent": "hr",
  "sources": [...]
}
```

---

## Step 7: Run Locally for Development

For faster iteration, run the backend and frontend locally.

### Load Environment Variables

Export the Azure resource configuration to your local shell:

```bash
# Bash / macOS / Linux
eval $(azd env get-values | sed 's/^/export /')

# PowerShell
azd env get-values | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2].Trim('"'))
    }
}
```

### Start the Backend

```bash
# From the repository root
uvicorn app.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend API will be available at `http://localhost:8000`.

### Start the Frontend

```bash
cd app/frontend
npm run dev
```

The frontend dev server starts at `http://localhost:5173` and proxies API requests to the backend on port 8000 via Vite's proxy configuration.

### Access the Application

Open your browser to **http://localhost:5173** to interact with the multi-agent chat interface.

---

## Step 8: Try Sample Queries

Test each specialist agent with these sample queries:

### HR Agent
```
What is the PTO policy?
How do I request parental leave?
What are the health insurance options?
```

### Products Agent
```
Tell me about the fitness watch.
What are the specs of the wireless earbuds?
Compare the smart home devices.
```

### Marketing Agent
```
What are the latest marketing campaigns?
Tell me about the social media strategy for Q3.
What was the ROI of the last product launch campaign?
```

### Expected Output Format

Each response includes:

1. **Agent Route** — which specialist handled the query (e.g., `hr`, `products`, `marketing`)
2. **Grounded Response** — the answer sourced from the agent's FoundryIQ Knowledge Base
3. **Sources** — references to the specific documents used to generate the response

Example:

```
[Route: hr]
According to Zava Corp's employee handbook, the PTO policy provides
full-time employees with 20 days of paid time off per year, accrued
at 1.67 days per month. New employees can begin using PTO after their
90-day probation period...

Sources:
  - employee-handbook.md (section: PTO Policy)
  - benefits-guide.md (section: Time Off)
```

---

## Troubleshooting Common First-Run Issues

### `azd up` fails with "quota exceeded"

**Cause:** Your subscription doesn't have enough quota for gpt-4.1 in the selected region.

**Fix:** Try a different region, or request a quota increase in the Azure Portal under **Subscriptions → Usage + quotas**.

### `azd up` fails with "role assignment" errors

**Cause:** Your account lacks permissions to create RBAC role assignments.

**Fix:** Ensure you have **Owner** or **Contributor + User Access Administrator** on the subscription.

### Backend returns 401/403 errors

**Cause:** Managed identity RBAC roles haven't fully propagated.

**Fix:** RBAC propagation can take up to 10 minutes. Wait and retry. If persistent, manually verify role assignments in the Azure Portal.

### `DefaultAzureCredential` fails locally

**Cause:** Your local Azure CLI session has expired or targets the wrong subscription.

**Fix:**
```bash
az login
az account set --subscription "<your-subscription-id>"
```

### Frontend shows "Network Error" or can't reach backend

**Cause:** The Vite dev proxy isn't configured or the backend isn't running.

**Fix:**
1. Ensure the backend is running on port 8000.
2. Check `app/frontend/vite.config.ts` has the proxy set to `http://localhost:8000`.

### Search indexes return empty results

**Cause:** The post-provision script didn't upload sample data.

**Fix:** Re-run the post-provision script:
```bash
azd hooks run postprovision
```

### "Model not found" errors

**Cause:** The gpt-4.1 model deployment didn't complete.

**Fix:** Check the model deployment in Azure Portal under your AIServices resource → **Model deployments**. Redeploy if necessary.

---

## Next Steps

- 📐 [Architecture Overview](./02-architecture-overview.md) — understand how the system works end-to-end
- 🤖 [Add a New Agent](./03-add-new-agent.md) — extend the system with a 4th specialist agent
- 📚 [Customize Knowledge Bases](./04-customize-knowledge-bases.md) — replace sample data with your own documents
