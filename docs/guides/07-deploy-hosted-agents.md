# Deploy as Hosted Agents in Foundry

A step-by-step guide for containerizing your multi-agent orchestrator and deploying it to Azure AI Foundry's hosted agent runtime. Covers Dockerfile creation, ACR push, Foundry API calls, testing, and comparison with the existing Container Apps deployment.

---

## What Are Hosted Agents?

Azure AI Foundry offers two agent types:

| | Prompt Agents | Hosted Agents |
|---|---|---|
| **Code** | No custom code — LLM + tools only | Your code runs in a managed container |
| **Runtime** | Foundry-managed | Your container, Foundry-managed infra |
| **Customization** | System prompt + built-in tools | Full control — any framework, any logic |
| **Use cases** | Simple Q&A, tool-calling scenarios | Complex multi-step workflows, custom orchestration |

**Hosted agents** are the right choice for this demo because:

- The orchestrator has **custom routing logic** (Router → Specialist pattern)
- Each specialist uses `AzureAISearchContextProvider` with the Agent Framework SDK
- The FastAPI backend has custom endpoints and middleware
- You need full control over the request/response lifecycle

### Architecture After Deployment

```
┌───────────────────────────────────────────────┐
│  Azure AI Foundry — Hosted Agent Runtime       │
│                                                │
│  ┌───────────────────────────────────────┐    │
│  │  Your Container                        │    │
│  │  ┌──────────┐  ┌──────────────────┐   │    │
│  │  │ FastAPI   │  │  Orchestrator     │   │    │
│  │  │ (uvicorn) │──│  Router Agent     │   │    │
│  │  │ port 8000 │  │  HR Agent         │   │    │
│  │  │           │  │  Products Agent   │   │    │
│  │  │           │  │  Marketing Agent  │   │    │
│  │  └──────────┘  └──────────────────┘   │    │
│  └───────────────────────────────────────┘    │
│                                                │
│  Managed: scaling, networking, monitoring      │
└───────────────────────────────────────────────┘
         │
         ▼
  FoundryIQ Knowledge Bases (Azure AI Search)
  gpt-4.1 Model Deployment
```

---

## Prerequisites

Before starting, ensure you have:

| Prerequisite | How to Verify | Provisioned By |
|---|---|---|
| Azure Container Registry (ACR) | `az acr show --name <acr-name>` | `azd up` (Bicep templates) |
| Docker installed locally | `docker --version` | Manual install |
| Foundry project | Check in Azure AI Foundry portal | `azd up` (Bicep templates) |
| Azure AI Developer role on Foundry project | Portal → IAM → Role assignments | `azd up` or manual RBAC |
| Azure CLI with `ai` extension | `az extension show --name ai` | `az extension add --name ai` |
| `DefaultAzureCredential` working | `az account show` | `az login` |

---

## Step 1: Create a Dockerfile

### 1A — Production Dockerfile

Create a `Dockerfile` in the repository root:

```dockerfile
# Dockerfile
# Multi-stage build for the FoundryIQ Agent Framework backend

# --- Stage 1: Dependencies ---
FROM python:3.12-slim AS dependencies

WORKDIR /app

# Install system dependencies for potential native packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY app/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy installed packages from the dependencies stage
COPY --from=dependencies /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code
COPY app/backend/ ./app/backend/

# Create a non-root user for security
RUN useradd --create-home appuser
USER appuser

# Expose the FastAPI port
EXPOSE 8000

# Health check for Foundry liveness probes
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start uvicorn
CMD ["uvicorn", "app.backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### 1B — Add a Health Endpoint

If your `main.py` doesn't already have one, add a health check:

```python
# app/backend/main.py — add near the top, after app = FastAPI(...)

@app.get("/health")
async def health():
    return {"status": "healthy"}
```

### 1C — Create a `.dockerignore`

```text
# .dockerignore
.git
.github
.azure
.venv
__pycache__
*.pyc
node_modules
app/frontend/node_modules
docs/
tests/
*.md
.env
.env.*
```

### 1D — Build and Test Locally

```bash
# Build the image
docker build -t foundryiq-agents:latest .

# Run locally (pass Azure credentials via environment)
docker run -p 8000:8000 \
  -e AZURE_PROJECT_ENDPOINT="https://<ais-name>.services.ai.azure.com/api/projects/<project-name>" \
  -e AZURE_CLIENT_ID="<your-client-id>" \
  -e AZURE_TENANT_ID="<your-tenant-id>" \
  -e AZURE_CLIENT_SECRET="<your-client-secret>" \
  foundryiq-agents:latest

# Test the health endpoint
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# Test a query
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the vacation policy?"}'
```

> **Note on credentials:** In production, Foundry hosted agents use managed identity (no secrets needed). For local Docker testing, pass a service principal or use `az login` token forwarding.

---

## Step 2: Push to Azure Container Registry

### 2A — Log In to ACR

```bash
# Log in using Azure CLI (uses your az login credentials)
az acr login --name <acr-name>

# Verify login succeeded
docker info | grep "Registry"
```

### 2B — Tag the Image

Follow a consistent tagging convention:

```bash
# Tag with version and latest
ACR_NAME="<acr-name>"
IMAGE_TAG="v1.0.0"

docker tag foundryiq-agents:latest ${ACR_NAME}.azurecr.io/foundryiq-agents:${IMAGE_TAG}
docker tag foundryiq-agents:latest ${ACR_NAME}.azurecr.io/foundryiq-agents:latest
```

### 2C — Push to ACR

```bash
# Push both tags
docker push ${ACR_NAME}.azurecr.io/foundryiq-agents:${IMAGE_TAG}
docker push ${ACR_NAME}.azurecr.io/foundryiq-agents:latest

# Verify the image is in ACR
az acr repository show-tags --name ${ACR_NAME} --repository foundryiq-agents --output table
```

Expected output:

```
Result
--------
latest
v1.0.0
```

### 2D — Build Directly in ACR (Alternative)

Skip local Docker builds entirely by building in ACR:

```bash
az acr build \
  --registry ${ACR_NAME} \
  --image foundryiq-agents:${IMAGE_TAG} \
  --file Dockerfile \
  .
```

This uploads the build context to ACR and builds the image remotely — useful in CI/CD pipelines or when Docker is not installed locally.

---

## Step 3: Create a Hosted Agent in Foundry

### 3A — Required Information

Gather these values before making API calls:

```bash
# Your Foundry project endpoint
PROJECT_ENDPOINT="https://<ais-name>.services.ai.azure.com/api/projects/<project-name>"

# ACR image URL
IMAGE_URL="${ACR_NAME}.azurecr.io/foundryiq-agents:v1.0.0"

# API version for Foundry hosted agents
API_VERSION="2025-05-15-preview"
```

### 3B — Create the Hosted Agent via REST API

```bash
# Get an access token
ACCESS_TOKEN=$(az account get-access-token --resource https://ai.azure.com --query accessToken -o tsv)

# Create the hosted agent
curl -X PUT "${PROJECT_ENDPOINT}/agents/foundryiq-orchestrator?api-version=${API_VERSION}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "hosted",
    "displayName": "FoundryIQ Orchestrator",
    "description": "Multi-agent orchestrator with Router, HR, Products, and Marketing specialists",
    "properties": {
      "container": {
        "image": "'${IMAGE_URL}'",
        "ports": [
          {
            "port": 8000,
            "protocol": "tcp"
          }
        ],
        "environmentVariables": [
          {
            "name": "AZURE_PROJECT_ENDPOINT",
            "value": "'${PROJECT_ENDPOINT}'"
          }
        ],
        "readinessProbe": {
          "httpGet": {
            "path": "/health",
            "port": 8000
          },
          "initialDelaySeconds": 10,
          "periodSeconds": 30
        }
      },
      "authentication": {
        "type": "managedIdentity"
      }
    }
  }'
```

### 3C — Python SDK Alternative

```python
# scripts/create_hosted_agent.py
"""
Create a hosted agent in Azure AI Foundry using the REST API.
"""

import os
import requests
from azure.identity import DefaultAzureCredential

PROJECT_ENDPOINT = os.environ["AZURE_PROJECT_ENDPOINT"]
ACR_NAME = os.environ["ACR_NAME"]
IMAGE_TAG = os.environ.get("IMAGE_TAG", "v1.0.0")
API_VERSION = "2025-05-15-preview"

credential = DefaultAzureCredential()
token = credential.get_token("https://ai.azure.com/.default")

agent_name = "foundryiq-orchestrator"
url = f"{PROJECT_ENDPOINT}/agents/{agent_name}?api-version={API_VERSION}"

payload = {
    "kind": "hosted",
    "displayName": "FoundryIQ Orchestrator",
    "description": "Multi-agent orchestrator with Router, HR, Products, and Marketing specialists",
    "properties": {
        "container": {
            "image": f"{ACR_NAME}.azurecr.io/foundryiq-agents:{IMAGE_TAG}",
            "ports": [{"port": 8000, "protocol": "tcp"}],
            "environmentVariables": [
                {"name": "AZURE_PROJECT_ENDPOINT", "value": PROJECT_ENDPOINT},
            ],
            "readinessProbe": {
                "httpGet": {"path": "/health", "port": 8000},
                "initialDelaySeconds": 10,
                "periodSeconds": 30,
            },
        },
        "authentication": {"type": "managedIdentity"},
    },
}

response = requests.put(
    url,
    json=payload,
    headers={
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/json",
    },
)

if response.status_code in (200, 201):
    print(f"✅ Hosted agent created: {agent_name}")
    print(f"   Status: {response.json().get('properties', {}).get('provisioningState')}")
else:
    print(f"❌ Failed: {response.status_code}")
    print(response.json())
```

---

## Step 4: Start and Test

### 4A — Start the Agent Container

```bash
# Start the hosted agent
curl -X POST "${PROJECT_ENDPOINT}/agents/foundryiq-orchestrator:start?api-version=${API_VERSION}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json"
```

### 4B — Check Agent Status

```bash
# Poll until status is "Running"
curl -s "${PROJECT_ENDPOINT}/agents/foundryiq-orchestrator?api-version=${API_VERSION}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" | python -m json.tool
```

Expected response (truncated):

```json
{
  "name": "foundryiq-orchestrator",
  "kind": "hosted",
  "properties": {
    "provisioningState": "Succeeded",
    "runtimeState": "Running",
    "endpoint": "https://<assigned-endpoint>/api"
  }
}
```

### 4C — Test with the Invoke API

Once the agent is running, send a test query:

```bash
# Get the agent's endpoint from the status response
AGENT_ENDPOINT="https://<assigned-endpoint>/api"

# Send a test query
curl -X POST "${AGENT_ENDPOINT}/ask" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the vacation policy for full-time employees?"}'
```

Expected response:

```json
{
  "route": "hr",
  "message": "Full-time employees at Zava Corporation are entitled to..."
}
```

### 4D — View Logs in the Portal

1. Navigate to **Azure AI Foundry** → your project → **Agents**
2. Click on **foundryiq-orchestrator**
3. Go to the **Logs** tab to see container stdout/stderr
4. Check the **Metrics** tab for request count, latency, and error rate

### 4E — Automated Smoke Test Script

```python
# scripts/smoke_test.py
"""
Smoke test for the deployed hosted agent.
Verifies health, routing, and basic responses.
"""

import os
import requests
from azure.identity import DefaultAzureCredential

AGENT_ENDPOINT = os.environ["AGENT_ENDPOINT"]

credential = DefaultAzureCredential()
token = credential.get_token("https://ai.azure.com/.default")
headers = {
    "Authorization": f"Bearer {token.token}",
    "Content-Type": "application/json",
}

TEST_QUERIES = [
    {"query": "What is the vacation policy?", "expected_route": "hr"},
    {"query": "Tell me about enterprise features", "expected_route": "products"},
    {"query": "What was our Q3 campaign performance?", "expected_route": "marketing"},
]

print("Running smoke tests against deployed agent...\n")
all_passed = True

# Test health endpoint
health = requests.get(f"{AGENT_ENDPOINT}/health", headers=headers)
if health.status_code == 200:
    print("✅ Health check passed")
else:
    print(f"❌ Health check failed: {health.status_code}")
    all_passed = False

# Test queries
for tc in TEST_QUERIES:
    resp = requests.post(
        f"{AGENT_ENDPOINT}/ask",
        json={"query": tc["query"]},
        headers=headers,
    )
    if resp.status_code == 200:
        data = resp.json()
        route = data.get("route")
        if route == tc["expected_route"]:
            print(f"✅ '{tc['query'][:40]}...' → {route}")
        else:
            print(f"❌ '{tc['query'][:40]}...' → {route} (expected {tc['expected_route']})")
            all_passed = False
    else:
        print(f"❌ '{tc['query'][:40]}...' → HTTP {resp.status_code}")
        all_passed = False

print(f"\n{'All smoke tests passed!' if all_passed else 'Some tests failed.'}")
exit(0 if all_passed else 1)
```

---

## Step 5: Update and Redeploy

### 5A — Build and Push a New Version

```bash
# After making code changes
IMAGE_TAG="v1.1.0"

docker build -t foundryiq-agents:${IMAGE_TAG} .
docker tag foundryiq-agents:${IMAGE_TAG} ${ACR_NAME}.azurecr.io/foundryiq-agents:${IMAGE_TAG}
docker push ${ACR_NAME}.azurecr.io/foundryiq-agents:${IMAGE_TAG}
```

### 5B — Update the Agent to Use the New Image

```bash
# Update the hosted agent with the new image tag
curl -X PATCH "${PROJECT_ENDPOINT}/agents/foundryiq-orchestrator?api-version=${API_VERSION}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "properties": {
      "container": {
        "image": "'${ACR_NAME}'.azurecr.io/foundryiq-agents:'${IMAGE_TAG}'"
      }
    }
  }'
```

### 5C — Rolling Update with Zero Downtime

Foundry handles rolling updates when you update the image:

1. A new container is started with the new image
2. Foundry waits for the readiness probe (`/health`) to succeed
3. Traffic is shifted to the new container
4. The old container is stopped

```
Time ─────────────────────────────────────────────────▶

Old container (v1.0.0):  ████████████████████▓▓▓░░░░░
New container (v1.1.0):  ░░░░░░░░░░░▓▓▓████████████████

                         ▲           ▲           ▲
                    Update     New container   Old container
                    issued       healthy         stopped
```

### 5D — Rollback

If the new version has issues, revert to the previous image:

```bash
# Rollback to v1.0.0
curl -X PATCH "${PROJECT_ENDPOINT}/agents/foundryiq-orchestrator?api-version=${API_VERSION}" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "properties": {
      "container": {
        "image": "'${ACR_NAME}'.azurecr.io/foundryiq-agents:v1.0.0"
      }
    }
  }'
```

---

## vs Current Container App Deployment

This repo already deploys to **Azure Container Apps** via `azd up`. Here's how that compares to Foundry hosted agents:

### Feature Comparison

| Capability | Container Apps (current) | Foundry Hosted Agents |
|---|---|---|
| **Deployment method** | `azd up` (Bicep/IaC) | Foundry REST API / Portal |
| **Scaling** | Manual or KEDA-based autoscale | Foundry-managed autoscale |
| **Networking** | Full VNet integration, custom domains | Foundry-managed endpoint |
| **Monitoring** | Azure Monitor, Log Analytics | Foundry portal metrics + Azure Monitor |
| **Evaluation** | Manual — must build your own pipeline | Built-in evaluation in Foundry portal |
| **Prompt optimization** | Manual | Foundry prompt optimizer integration |
| **Multi-container** | Sidecar containers, Dapr integration | Single container per agent |
| **Cost** | Pay per vCPU/memory consumed | Pay per agent runtime (preview pricing) |
| **CI/CD** | GitHub Actions → `azd deploy` | GitHub Actions → ACR push → API update |
| **Portal visibility** | Container Apps blade in Azure Portal | Agents blade in Foundry portal |

### When to Use Each

**Use Container Apps when:**
- You need full infrastructure control (VNet, custom DNS, IP restrictions)
- You're running multiple services (frontend + backend + sidecars)
- You need Dapr for service-to-service communication
- You have existing Container Apps infrastructure
- Cost optimization is critical (granular resource control)

**Use Foundry Hosted Agents when:**
- You want integrated evaluation and prompt optimization
- You want agent visibility in the Foundry portal alongside your models and data
- You're using Foundry for the full AI lifecycle (data → model → agent → eval)
- You want managed scaling without configuring KEDA rules
- You plan to use Foundry's agent monitoring and tracing features

### Migration Path

You don't have to choose one exclusively. A common pattern:

```
Development:    Local Docker → Foundry Hosted Agent (easy deploy, built-in eval)
Staging:        Foundry Hosted Agent (evaluate with Foundry tooling)
Production:     Container Apps (full infra control, cost optimization)
```

Or run both in parallel:
- **Foundry Hosted Agent** for the evaluation/optimization loop during development
- **Container Apps** for the production workload serving real users

### Side-by-Side Deployment Example

```bash
# Deploy to Container Apps (existing flow)
azd up

# Deploy to Foundry Hosted Agents (new flow)
docker build -t foundryiq-agents:v1.0.0 .
az acr login --name ${ACR_NAME}
docker tag foundryiq-agents:v1.0.0 ${ACR_NAME}.azurecr.io/foundryiq-agents:v1.0.0
docker push ${ACR_NAME}.azurecr.io/foundryiq-agents:v1.0.0
python scripts/create_hosted_agent.py
python scripts/smoke_test.py
```

---

## Troubleshooting

| Issue | Possible Cause | Fix |
|---|---|---|
| Container fails to start | Missing environment variables | Check `environmentVariables` in the agent config |
| Health check fails | `/health` endpoint not exposed | Add `@app.get("/health")` to `main.py` |
| 401 Unauthorized | Managed identity not configured | Ensure the agent has `Azure AI Developer` role on the Foundry project |
| ACR pull fails | ACR access not granted | Grant `AcrPull` role to the Foundry project's managed identity on the ACR |
| Agent stuck in "Provisioning" | Image too large or slow startup | Optimize Dockerfile (multi-stage build), increase `initialDelaySeconds` |
| Timeout on queries | KB search is slow or model latency | Check Azure AI Search metrics; consider reducing `max_tokens` |

### Granting ACR Pull Access

```bash
# Get the Foundry project's managed identity principal ID
PRINCIPAL_ID=$(az ai project show \
  --name <project-name> \
  --resource-group <rg-name> \
  --query identity.principalId -o tsv)

# Grant AcrPull role
az role assignment create \
  --assignee ${PRINCIPAL_ID} \
  --role AcrPull \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg-name>/providers/Microsoft.ContainerRegistry/registries/<acr-name>
```

---

## Summary

| Step | Command / Action | Outcome |
|---|---|---|
| 1. Dockerfile | `docker build -t foundryiq-agents .` | Container image built |
| 2. Push to ACR | `docker push <acr>.azurecr.io/foundryiq-agents:v1` | Image in ACR |
| 3. Create agent | `curl -X PUT .../agents/foundryiq-orchestrator` | Agent registered in Foundry |
| 4. Start & test | `curl -X POST .../agents/foundryiq-orchestrator:start` | Agent running and serving queries |
| 5. Update | `curl -X PATCH ...` with new image tag | Zero-downtime rolling update |

---

## Next Steps

- Run the [evaluation suite](06-evaluate-optimize-agents.md) against the hosted agent to verify quality
- Set up CI/CD to automate the build → push → update cycle on every merge to `main`
- Explore Foundry's built-in agent tracing to monitor query patterns and response quality in production
