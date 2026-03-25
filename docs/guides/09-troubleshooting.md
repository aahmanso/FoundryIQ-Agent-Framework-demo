# Troubleshooting Guide

This guide documents real issues encountered during the development and deployment of the FoundryIQ and Agent Framework Demo, along with their solutions. If you hit a problem, chances are it's listed here.

---

## Deployment Issues

### `azd up` Fails at Provisioning

**Symptoms**: Bicep deployment error during `azd up`, often with "DeploymentFailed" or resource-specific errors.

**Solutions**:

1. **Check region availability**: Not all regions support Azure AI Services with project management. Try `eastus2`, `swedencentral`, or `westus3`.
   ```bash
   # See which resources failed
   az deployment group list --resource-group <rg> --output table
   
   # Check specific deployment errors
   az deployment group show --resource-group <rg> --name <deployment-name> --query properties.error
   ```

2. **Clean up and retry**: If a partial deployment left resources in a bad state:
   ```bash
   azd down --force --purge
   azd up
   ```

3. **Quota limits**: Some regions have limited capacity for certain SKUs:
   ```bash
   az cognitiveservices usage list --location eastus2 --output table
   ```

---

### Model Deployment Fails

**Symptoms**: "InsufficientQuota" or "ModelNotAvailable" error when deploying gpt-4.1.

**Solutions**:

1. **Check current quota usage**:
   ```bash
   az cognitiveservices account deployment list \
     --name <ais-name> \
     --resource-group <rg> \
     --output table
   ```

2. **Request a quota increase**: Go to Azure Portal → Azure AI Services → Quotas → Request increase.

3. **Try a different region**: gpt-4.1 availability varies by region. Check [Azure AI model availability](https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models) for current regions.

4. **Reduce TPM (Tokens Per Minute)**: Lower the capacity in your Bicep deployment:
   ```bicep
   resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
     name: 'gpt-4.1'
     sku: {
       name: 'GlobalStandard'
       capacity: 50  // Reduce from default if hitting quota
     }
   }
   ```

---

### Container App Won't Start

**Symptoms**: CrashLoopBackOff, container keeps restarting.

**Solutions**:

1. **Check logs**:
   ```bash
   az containerapp logs show \
     --name <app-name> \
     --resource-group <rg> \
     --type console \
     --follow
   ```

2. **Common causes**:
   - Missing environment variables (check all required vars are set)
   - Package import errors (missing dependencies in container image)
   - Port mismatch (Container App expects the port defined in `targetPort`)

3. **Verify environment variables are set**:
   ```bash
   az containerapp show \
     --name <app-name> \
     --resource-group <rg> \
     --query "properties.template.containers[0].env" \
     --output table
   ```

---

## Authentication & RBAC Issues

### 403 Forbidden on OpenAI / Model Calls

**Symptoms**: `AuthorizationFailed` or `403 Forbidden` when calling gpt-4.1.

**Root Cause**: The calling identity does not have the correct RBAC role on the Azure AI Services resource.

**Solution**: Assign the "Cognitive Services OpenAI User" role:

```bash
# For your user principal (local development)
az role assignment create \
  --assignee <your-user-object-id> \
  --role "Cognitive Services OpenAI User" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<ais-name>

# For Container App managed identity (production)
az role assignment create \
  --assignee <container-app-mi-principal-id> \
  --role "Cognitive Services OpenAI User" \
  --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<ais-name>
```

> **Important**: Role assignments can take 5-10 minutes to propagate. Be patient after assigning.

---

### 403 Forbidden on Search Operations

**Symptoms**: `Forbidden` when the agent tries to query Azure AI Search.

**Solutions**:

1. **Ensure Search uses RBAC authentication** (not just API keys):
   ```bash
   az search service update \
     --name <search-name> \
     --resource-group <rg> \
     --auth-options aadOrApiKey
   ```

2. **Assign the correct roles**:
   ```bash
   # Reader role for querying indexes
   az role assignment create \
     --assignee <principal-id> \
     --role "Search Index Data Reader" \
     --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Search/searchServices/<search-name>
   
   # Contributor role for managing indexes
   az role assignment create \
     --assignee <principal-id> \
     --role "Search Index Data Contributor" \
     --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Search/searchServices/<search-name>
   
   # Service-level contributor for creating/deleting indexes
   az role assignment create \
     --assignee <principal-id> \
     --role "Search Service Contributor" \
     --scope /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Search/searchServices/<search-name>
   ```

---

### Knowledge Base Returns Empty Results (No Grounding)

**Symptoms**: Agents return generic, ungrounded responses. The LLM answers from its training data instead of your documents.

**Root Cause**: The identity chain between AIServices, Search, and the Knowledge Base is broken. Multiple RBAC roles must be correctly assigned across services.

**Solution**: Verify the full RBAC chain:

```bash
# AIServices managed identity → needs "Search Index Data Reader" on Search
az role assignment create \
  --assignee <ais-mi-principal-id> \
  --role "Search Index Data Reader" \
  --scope <search-resource-id>

# Search managed identity → needs "Cognitive Services OpenAI User" on AIServices
az role assignment create \
  --assignee <search-mi-principal-id> \
  --role "Cognitive Services OpenAI User" \
  --scope <ais-resource-id>

# Project managed identity → needs "Search Index Data Reader" on Search
az role assignment create \
  --assignee <project-mi-principal-id> \
  --role "Search Index Data Reader" \
  --scope <search-resource-id>
```

Also check:
- Search has system-assigned managed identity **enabled**
- The Knowledge Base references the correct search index name
- Documents actually exist in the search index (see [Knowledge Base Issues](#knowledge-base-issues) below)

---

### DefaultAzureCredential Fails

**Symptoms**: `azure.identity.CredentialUnavailableError: No credential in this chain provided a token`

**Solutions**:

1. **Ensure you're logged in**:
   ```bash
   az login
   az account show  # Verify correct subscription
   az account set --subscription <sub-id>  # Switch if needed
   ```

2. **Set the correct tenant** (if multi-tenant):
   ```bash
   az login --tenant <tenant-id>
   ```

3. **For VS Code**: Ensure the Azure Account extension is installed and you're signed in.

4. **For Container Apps**: Ensure system-assigned managed identity is enabled:
   ```bash
   az containerapp identity assign \
     --name <app-name> \
     --resource-group <rg> \
     --system-assigned
   ```

---

### Foundry Portal Access Denied

**Symptoms**: "Unauthorized network location" or "restricted resource" when accessing ai.azure.com.

**Root Cause**: You likely have an **old ML Hub workspace** with `publicNetworkAccess: Disabled` that is blocking access. This setting often cannot be changed even via REST API.

**Solution**: Delete the legacy ML Hub and Project resources:

```bash
# Delete the ML Project first (it's a child of the Hub)
az ml workspace delete --name <project-workspace-name> --resource-group <rg> --yes

# Then delete the ML Hub
az ml workspace delete --name <hub-workspace-name> --resource-group <rg> --yes

# Purge soft-deleted resources
az ml workspace delete --name <hub-workspace-name> --resource-group <rg> --permanently-delete --yes
```

> **Note**: New Foundry (AIServices + Projects) does not need ML Hub resources at all. See [New Foundry vs Legacy](10-new-foundry-vs-legacy.md) for details.

---

## Agent Runtime Issues

### Orchestrator Returns 2-Character Responses

**Symptoms**: Instead of a full answer, the orchestrator returns just `"hr"`, `"products"`, or `"marketing"` — the agent name, not the agent's response.

**Root Cause**: This is a **shared client state bug**. The router agent and specialist agents are sharing the same `AzureAIAgentClient` instance. The router's conversation thread pollutes the specialist's thread, causing the specialist to return the routing label instead of processing the query.

**Solution**: Use separate client instances for the router and each specialist agent:

```python
# ❌ BAD: Shared client
client = AzureAIAgentClient(endpoint=endpoint, credential=credential)
router = Agent(client=client, ...)
hr_agent = Agent(client=client, ...)  # Shares state with router!

# ✅ GOOD: Separate clients via helper function
def _make_client():
    return AzureAIAgentClient(
        endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT"),
        credential=DefaultAzureCredential(),
    )

router_client = _make_client()
hr_client = _make_client()
router = Agent(client=router_client, ...)
hr_agent = Agent(client=hr_client, ...)
```

---

### Agents Return Generic (Ungrounded) Responses

**Symptoms**: Agents answer questions but don't reference your documents. Responses are generic LLM knowledge.

**Solutions**:

1. **Verify `context_provider` is passed to the Agent constructor**:
   ```python
   # ❌ Missing context_provider
   agent = Agent(name="hr_agent", instructions="...", client=client)
   
   # ✅ With context_provider for KB grounding
   agent = Agent(
       name="hr_agent",
       instructions="...",
       client=client,
       context_provider=hr_knowledge_base,  # Must be set!
   )
   ```

2. **Verify the Knowledge Base exists and is connected**:
   - Open Foundry portal → your project → Knowledge Bases
   - Ensure the KB is listed and connected to your Azure AI Search index

3. **Check the search index has documents**:
   ```bash
   az search query \
     --service-name <search-name> \
     --index-name index-hr \
     --search-text "*" \
     --select "title" \
     --top 5
   ```

---

### Import Errors on Startup

**Symptoms**: `ModuleNotFoundError: No module named 'agent_framework_azure_ai_search'`

**Solutions**:

1. **Install all required packages**:
   ```bash
   pip install agent-framework-core agent-framework-azure-ai agent-framework-azure-ai-search
   ```

2. **Verify installation**:
   ```bash
   pip list | grep agent-framework
   ```

3. **Check your working directory**: Some import paths are relative. Make sure you're running from the project root:
   ```bash
   cd /path/to/FoundryIQ-Agent-Framework-demo
   python -m src.main  # Run as module, not script
   ```

---

### Frontend White Screen

**Symptoms**: The React frontend loads briefly, then goes white or shows nothing.

**Solutions**:

1. **Check browser developer console** (F12 → Console tab) for JavaScript errors

2. **Verify the backend is running** and the `/chat` endpoint responds:
   ```bash
   curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "hello"}'
   ```

3. **Check CORS configuration**: If the frontend and backend are on different ports, ensure CORS is enabled:
   ```python
   from fastapi.middleware.cors import CORSMiddleware
   
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["http://localhost:3000"],
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

4. **Check backend logs** for 500 errors on the `/chat` endpoint

---

### Slow Responses (>30 seconds)

**Symptoms**: Queries take 30+ seconds, causing timeouts on the frontend.

**Solutions**:

1. **Agentic retrieval mode is slower** than standard retrieval. Consider switching:
   ```python
   # Agentic (slower, better quality)
   retrieval_mode = "agentic"
   
   # Standard (faster, still good)
   retrieval_mode = "standard"
   ```

2. **Reduce retrieval reasoning effort** (for agentic mode):
   ```python
   retrieval_reasoning_effort = "low"  # Options: low, medium, high
   ```

3. **Check model TPM (Tokens Per Minute) capacity**:
   ```bash
   az cognitiveservices account deployment list \
     --name <ais-name> \
     --resource-group <rg> \
     --output table
   ```
   If capacity is low (e.g., 10 TPM), increase it in your Bicep or via the portal.

4. **Implement streaming** to give users partial responses while the full answer generates.

---

## Knowledge Base Issues

### KB Creation Fails

**Symptoms**: REST API returns 400 Bad Request when creating a Knowledge Base.

**Solutions**:

1. **Use the correct API version**:
   ```
   api-version=2025-11-01-preview
   ```
   Older API versions do not support Knowledge Base operations.

2. **Verify the knowledge source (search index) exists first**:
   ```bash
   az search index list --service-name <search-name> --output table
   ```

3. **Check the request body format**:
   ```json
   {
     "name": "kb-hr",
     "description": "HR Knowledge Base",
     "indexReference": {
       "indexId": "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Search/searchServices/<search>/indexes/index-hr",
       "indexConnectionId": "<connection-id>"
     }
   }
   ```

---

### Index Not Found

**Symptoms**: `"Index 'index-hr' not found"` when KB tries to query.

**Solutions**:

1. **Verify the index exists**:
   ```bash
   az search index list --service-name <search-name> --output table
   ```

2. **Check the index name matches exactly** (case-sensitive):
   ```bash
   az search index show --service-name <search-name> --index-name index-hr
   ```

3. **Ensure semantic configuration is enabled** on the index:
   ```json
   {
     "name": "index-hr",
     "semanticConfiguration": {
       "name": "my-semantic-config",
       "prioritizedFields": {
         "contentFields": [{ "fieldName": "content" }],
         "titleField": { "fieldName": "title" }
       }
     }
   }
   ```

---

### No Search Results

**Symptoms**: Knowledge Base queries return empty results.

**Solutions**:

1. **Verify documents exist in the index**:
   ```bash
   az search query \
     --service-name <search-name> \
     --index-name index-hr \
     --search-text "*" \
     --count true
   ```

2. **Check the content field is populated** (not empty strings or null):
   ```bash
   az search query \
     --service-name <search-name> \
     --index-name index-hr \
     --search-text "*" \
     --select "title,content" \
     --top 3
   ```

3. **Verify semantic config name** matches what the KB expects. A mismatch will silently return no results.

4. **Test a direct search query** to isolate whether the issue is in Search or in the KB layer:
   ```bash
   curl -X POST "https://<search-name>.search.windows.net/indexes/index-hr/docs/search?api-version=2024-07-01" \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <token>" \
     -d '{"search": "parental leave", "queryType": "semantic", "semanticConfiguration": "my-semantic-config"}'
   ```

---

## Foundry Portal Issues

### Can't Access ai.azure.com

**Symptoms**: "Restricted resource" or access denied when opening the Foundry portal for your project.

**Root Cause**: Legacy ML Hub resources in the same resource group may have network restrictions that interfere with Foundry portal access.

**Solution**: Delete legacy ML Hub/Project resources. See [Foundry Portal Access Denied](#foundry-portal-access-denied) above.

---

### No Agents Visible in Portal

**Symptoms**: The Foundry portal shows an empty agents list, even though you created agents via the API.

**Solutions**:

1. **Agents must be created with the correct project endpoint**:
   ```
   https://<ais-name>.services.ai.azure.com/api/projects/<project-name>
   ```

2. **Use the correct API version**: `2025-11-01-preview` or later.

3. **Check you're viewing the right project** in the portal.

---

### FoundryIQ Not Connecting to Search

**Symptoms**: Portal shows "Connect your agent to Foundry IQ" even though Search is deployed.

**Solutions**:

1. **Connect Azure AI Search via the Foundry portal**:
   - Open your project in ai.azure.com
   - Go to **Management → Connected resources**
   - Click **+ New connection** → Azure AI Search
   - Use **Managed Identity** authentication (not API key)

2. **Ensure Search has system-assigned managed identity enabled**:
   ```bash
   az search service update \
     --name <search-name> \
     --resource-group <rg> \
     --identity-type SystemAssigned
   ```

3. **Assign cross-service RBAC roles** (see [Knowledge Base Returns Empty Results](#knowledge-base-returns-empty-results-no-grounding) above).

---

## Quick Reference: Essential RBAC Roles

| Identity | Role | Target Resource | Purpose |
|----------|------|-----------------|---------|
| Your user principal | Cognitive Services OpenAI User | AIServices | Call models locally |
| Your user principal | Azure AI Developer | AIServices | Manage agents & KBs |
| Container App MI | Cognitive Services OpenAI User | AIServices | Call models in production |
| Container App MI | Cognitive Services User | AIServices | General service access |
| AIServices MI | Search Index Data Reader | Search | KB retrieval |
| Project MI | Search Index Data Reader | Search | KB retrieval |
| Search MI | Cognitive Services OpenAI User | AIServices | Embedding during indexing |
| AIServices MI | Storage Blob Data Reader | Storage | Access uploaded documents |

---

## Useful Commands Cheat Sheet

```bash
# Check deployed resources in your resource group
az resource list --resource-group <rg> --output table

# Check RBAC assignments on a resource
az role assignment list --scope <resource-id> --output table

# Test Search index directly
az search query --service-name <search> --index-name index-hr --search-text "*"

# List model deployments
az cognitiveservices account deployment list --name <ais> --resource-group <rg> --output table

# View Container App logs (live)
az containerapp logs show --name <app> --resource-group <rg> --type console --follow

# Load azd environment variables locally
azd env get-values > .env

# Check AI Services properties
az cognitiveservices account show --name <ais> --resource-group <rg>

# Check project properties
az rest --method GET \
  --url "https://management.azure.com/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<ais>/projects/<proj>?api-version=2024-10-01"

# List all role assignments for a specific principal
az role assignment list --assignee <principal-id> --all --output table

# Force refresh DefaultAzureCredential
az account get-access-token --resource https://cognitiveservices.azure.com
```

---

[← Tracing & Observability](08-tracing-observability.md) | [New Foundry vs Legacy →](10-new-foundry-vs-legacy.md)
