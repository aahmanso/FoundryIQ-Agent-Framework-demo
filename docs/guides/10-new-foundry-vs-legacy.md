# New Foundry vs Legacy Architecture

If you've worked with Azure AI before 2025, you're familiar with the ML Hub and ML Workspace model. Microsoft Foundry is a fundamentally different architecture, and this guide explains what changed, why it matters, and how to migrate.

This guide is based on real migration experience — we deleted our legacy ML Hub resources entirely when building this demo because the new Foundry architecture doesn't need them.

---

## The Old Way (Pre-2025): ML Hub + ML Project

The legacy Azure AI architecture was built on **Azure Machine Learning Services**:

```
Resource Group
├── ML Hub Workspace (Microsoft.MachineLearningServices/workspaces, kind: Hub)
│   ├── Managed VNet / Private Endpoints
│   ├── Storage Account (associated)
│   ├── Key Vault (associated)
│   ├── Container Registry (associated)
│   └── Application Insights (associated)
│
├── ML Project Workspace (Microsoft.MachineLearningServices/workspaces, kind: Project)
│   ├── Linked to Hub (parent)
│   ├── Model Deployments (via Online Endpoints)
│   └── Connections (to OpenAI, Search, etc.)
│
├── Azure OpenAI Resource (separate)
│   └── Model Deployments (gpt-4, etc.)
│
└── Azure AI Search (separate)
    └── Indexes
```

### Characteristics

- **Hub was the parent**: It managed networking, storage connections, and compute. Projects were child workspaces under the Hub.
- **Portal**: `ml.azure.com` (separate from the later AI Studio portal)
- **Resource provider**: `Microsoft.MachineLearningServices`
- **Heavy footprint**: A Hub deployment created 5+ associated resources (Storage, Key Vault, ACR, App Insights, the workspace itself)
- **Complex networking**: Hubs had `publicNetworkAccess` settings, managed VNets, and Private Endpoints. Once set to `Disabled`, this often **could not be changed back** — not even via REST API PUT/PATCH operations.
- **Slow provisioning**: Creating a Hub + Project took 10-15 minutes
- **Limited agent support**: No native agent hosting. You had to build your own orchestration layer.

---

## The New Way (2025+): Microsoft Foundry

The new architecture is built on **Azure Cognitive Services** with project management enabled:

```
Resource Group
├── Azure AI Services (Microsoft.CognitiveServices/accounts, kind: AIServices)
│   ├── allowProjectManagement: true
│   ├── Model Deployments (gpt-4.1, etc.) — built in
│   ├── System-Assigned Managed Identity
│   │
│   └── Project (Microsoft.CognitiveServices/accounts/projects)
│       ├── System-Assigned Managed Identity
│       ├── Agents (hosted & prompt agents) — native
│       ├── Knowledge Bases (FoundryIQ) — native
│       ├── Evaluation — native
│       └── Tracing — native
│
├── Azure AI Search
│   ├── System-Assigned Managed Identity
│   └── Indexes (index-hr, index-products, index-marketing)
│
└── Storage Account (for documents)
```

### Characteristics

- **AIServices is the parent**: It hosts models directly, manages identities, and enables project management via a single property.
- **Projects are sub-resources**: Not full workspaces — they're lightweight child resources under the AIServices account.
- **Portal**: `ai.azure.com` (unified Foundry portal)
- **Resource provider**: `Microsoft.CognitiveServices`
- **Minimal footprint**: AIServices + Project = 2 resources (plus Search and Storage as needed)
- **Simple networking**: Standard `publicNetworkAccess` on the AIServices resource, no managed VNet complexity
- **Fast provisioning**: Projects provision in seconds
- **Native agent support**: Hosted agents, prompt agents, FoundryIQ Knowledge Bases, evaluation, and tracing — all built in

### Key Property: `allowProjectManagement`

The AIServices resource must have this property set to `true` to enable the Foundry project model:

```json
{
  "type": "Microsoft.CognitiveServices/accounts",
  "kind": "AIServices",
  "properties": {
    "allowProjectManagement": true,
    "publicNetworkAccess": "Enabled"
  }
}
```

In Bicep:

```bicep
resource aiServices 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: aiServicesName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
    customSubDomainName: aiServicesName
  }
}
```

---

## Side-by-Side Comparison

| Aspect | Legacy (ML Hub) | New Foundry (AIServices) |
|--------|-----------------|--------------------------|
| **Parent resource** | ML Hub Workspace | AIServices (CognitiveServices) |
| **Project resource** | ML Project Workspace | CognitiveServices/accounts/projects |
| **Resource provider** | MachineLearningServices | CognitiveServices |
| **Portal** | ml.azure.com | ai.azure.com |
| **Networking** | Complex VNet/PE on Hub | Simple publicNetworkAccess on AIServices |
| **Model hosting** | Separate Azure OpenAI + endpoints | Direct model deployments on AIServices |
| **Identity** | Hub MI + Project MI (complex chain) | AIServices MI + Project MI (simpler chain) |
| **Provisioning time** | 10-15 minutes | 2-3 minutes |
| **IaC complexity** | ~200 lines Bicep (Hub + deps) | ~50 lines Bicep |
| **Agent support** | None (build your own) | Native (hosted and prompt agents) |
| **Knowledge bases** | Not integrated (manual RAG) | FoundryIQ built-in |
| **Evaluation** | Separate tooling | Built-in evaluation framework |
| **Tracing** | Application Insights only | Built-in + Application Insights |
| **Associated resources** | Storage, Key Vault, ACR, App Insights | None required (optional connections) |
| **Project endpoint** | `https://<region>.api.azureml.ms/...` | `https://<ais>.services.ai.azure.com/api/projects/<proj>` |

---

## Migration Steps

If you have existing ML Hub resources and want to move to the new Foundry architecture:

### Step 1: Inventory Your Existing Resources

```bash
# List all ML resources
az ml workspace list --resource-group <rg> --output table

# Check workspace kinds (Hub vs Project)
az ml workspace show --name <workspace> --resource-group <rg> --query "kind"
```

### Step 2: Export Data and Models

Before deleting anything, export what you need:

```bash
# List registered models
az ml model list --workspace-name <project> --resource-group <rg> --output table

# List datasets
az ml data list --workspace-name <project> --resource-group <rg> --output table

# Download model artifacts
az ml model download --name <model> --version <ver> --workspace-name <project> --resource-group <rg>
```

### Step 3: Delete the ML Project Workspace

Projects must be deleted **before** their parent Hub:

```bash
az ml workspace delete \
  --name <project-workspace-name> \
  --resource-group <rg> \
  --yes

# If the workspace was soft-deleted, permanently delete it
az ml workspace delete \
  --name <project-workspace-name> \
  --resource-group <rg> \
  --permanently-delete \
  --yes
```

### Step 4: Delete the ML Hub Workspace

```bash
az ml workspace delete \
  --name <hub-workspace-name> \
  --resource-group <rg> \
  --yes

# Permanently delete to free the name and clear network restrictions
az ml workspace delete \
  --name <hub-workspace-name> \
  --resource-group <rg> \
  --permanently-delete \
  --yes
```

### Step 5: Clean Up Associated Resources (Optional)

The Hub may have created associated resources. Check if they're still needed:

```bash
az resource list --resource-group <rg> --output table
```

Remove orphaned resources:
- Storage accounts created by ML Hub
- Key Vaults with ML-specific names
- Container Registries used only for ML
- Application Insights instances

### Step 6: Create New AIServices with Project Management

```bash
# Create AIServices resource
az rest --method PUT \
  --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<ais-name>?api-version=2024-10-01" \
  --body '{
    "location": "eastus2",
    "kind": "AIServices",
    "sku": { "name": "S0" },
    "identity": { "type": "SystemAssigned" },
    "properties": {
      "allowProjectManagement": true,
      "publicNetworkAccess": "Enabled",
      "customSubDomainName": "<ais-name>"
    }
  }'
```

### Step 7: Create a Project Under AIServices

```bash
az rest --method PUT \
  --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<ais-name>/projects/<project-name>?api-version=2024-10-01" \
  --body '{
    "location": "eastus2",
    "identity": { "type": "SystemAssigned" },
    "properties": {}
  }'
```

### Step 8: Deploy Models to AIServices

```bash
az cognitiveservices account deployment create \
  --name <ais-name> \
  --resource-group <rg> \
  --deployment-name "gpt-4.1" \
  --model-name "gpt-4.1" \
  --model-version "2025-04-14" \
  --model-format "OpenAI" \
  --sku-name "GlobalStandard" \
  --sku-capacity 80
```

### Step 9: Update Your Code

Replace old endpoints with the new Foundry project endpoint:

```python
# ❌ Old ML-based endpoint
endpoint = "https://<region>.api.azureml.ms/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.MachineLearningServices/workspaces/<project>"

# ✅ New Foundry endpoint
endpoint = "https://<ais-name>.services.ai.azure.com/api/projects/<project-name>"
```

### Step 10: Reassign RBAC Roles

The new resources have new managed identities. Reassign all roles:

```bash
# Get the new AIServices MI principal ID
ais_mi=$(az cognitiveservices account show --name <ais> --resource-group <rg> --query identity.principalId -o tsv)

# Get the new Project MI principal ID
proj_mi=$(az rest --method GET \
  --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<ais>/projects/<proj>?api-version=2024-10-01" \
  --query identity.principalId -o tsv)

# Assign roles (see Troubleshooting guide for full list)
az role assignment create --assignee $ais_mi --role "Search Index Data Reader" --scope <search-resource-id>
az role assignment create --assignee $proj_mi --role "Search Index Data Reader" --scope <search-resource-id>
```

---

## Key Gotchas We Discovered

These are hard-won lessons from our migration experience:

### 1. Old ML Hub Network Settings Are Immutable

If your old ML Hub had `publicNetworkAccess: Disabled`, you **cannot change it back**. We tried:

- Azure Portal: Setting greyed out
- Azure CLI: `az ml workspace update --public-network-access Enabled` → rejected
- REST API PUT: Returns 200 but doesn't actually change the value
- REST API PATCH: Same result

**The only fix is deletion.** Delete the Hub and Project workspaces entirely.

### 2. New Foundry Projects Require SystemAssigned Identity

When creating a project, you **must** include `identity.type: SystemAssigned` in the request body:

```json
{
  "location": "eastus2",
  "identity": {
    "type": "SystemAssigned"  // Required!
  },
  "properties": {}
}
```

Without this, the project cannot perform RBAC-authenticated operations.

### 3. allowProjectManagement Requires REST API

Not all CLI commands support setting `allowProjectManagement: true`. Use `az rest` with a direct PUT:

```bash
az rest --method PUT \
  --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<ais-name>?api-version=2024-10-01" \
  --body '{ "properties": { "allowProjectManagement": true } }'
```

Or better yet, use Bicep (which handles this natively).

### 4. Token Audience Changed

The agent API uses a different token audience than the Cognitive Services REST API:

```python
# ❌ Old audience for Cognitive Services
credential = DefaultAzureCredential()
token = credential.get_token("https://cognitiveservices.azure.com/.default")

# ✅ New audience for Foundry agent APIs
# The SDK handles this automatically when you use:
from azure.ai.agents import AzureAIAgentClient
client = AzureAIAgentClient(endpoint=endpoint, credential=credential)
# The SDK internally uses https://ai.azure.com as the audience
```

### 5. Knowledge Base API Version Matters

Knowledge Base (FoundryIQ) operations require API version `2025-11-01-preview` or later:

```bash
# ❌ This will 404 on KB endpoints
api-version=2024-10-01

# ✅ This works
api-version=2025-11-01-preview
```

---

## Benefits of the New Architecture

### Simplicity

| Metric | Legacy | New Foundry |
|--------|--------|-------------|
| Resources to deploy | 7-10 | 3-4 |
| Bicep lines | ~200 | ~50 |
| RBAC assignments | 15+ | 7-8 |
| Time to provision | 10-15 min | 2-3 min |
| Portal logins needed | 2 (ml.azure.com + portal.azure.com) | 1 (ai.azure.com) |

### Speed

- Projects provision in **seconds**, not minutes
- Model deployments are immediate (no endpoint provisioning)
- Knowledge Base creation is a single API call (no complex indexer pipelines)

### Unified Experience

Everything lives in one portal (ai.azure.com):

- **Models**: Deploy, test, and manage — all in one place
- **Agents**: Create hosted and prompt agents with built-in tools
- **Knowledge Bases**: FoundryIQ connects Search indexes directly
- **Evaluation**: Built-in evaluation framework with metrics
- **Tracing**: Agent conversation traces without external tooling
- **Playground**: Test agents interactively

### Better RBAC

The role hierarchy is flatter and clearer:

```
User Principal
  → "Azure AI Developer" on AIServices (manage agents, KBs)
  → "Cognitive Services OpenAI User" on AIServices (call models)

AIServices Managed Identity
  → "Search Index Data Reader" on Search (KB retrieval)
  → "Storage Blob Data Reader" on Storage (document access)

Search Managed Identity
  → "Cognitive Services OpenAI User" on AIServices (embedding during indexing)
```

No more Hub MI → Project MI → Connection → Endpoint identity chains.

### Native Agent Support

The old architecture had no concept of agents. You had to:

1. Deploy a model to an Online Endpoint
2. Build your own orchestration logic
3. Implement RAG manually
4. Handle conversation management yourself

With Foundry, agents are first-class resources:

```python
from azure.ai.agents import AzureAIAgentClient

client = AzureAIAgentClient(endpoint=project_endpoint, credential=credential)
agent = client.agents.create(
    name="hr-agent",
    model="gpt-4.1",
    instructions="You are an HR assistant...",
)
```

---

## Decision Matrix: When to Use What

| Scenario | Recommendation |
|----------|---------------|
| New project, no existing resources | Use New Foundry (AIServices + Projects) |
| Existing ML Hub, can delete | Migrate to New Foundry |
| Existing ML Hub, can't delete (compliance) | Keep legacy, but use AIServices for new agent work |
| Need agents/KBs | Must use New Foundry (not available in legacy) |
| Need ML training/compute | Keep ML Hub for training, use Foundry for inference/agents |
| Multi-region deployment | New Foundry is simpler to replicate |

---

[← Troubleshooting](09-troubleshooting.md) | [Back to Guides](README.md)
