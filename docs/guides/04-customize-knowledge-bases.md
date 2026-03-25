# Customize Knowledge Bases

This guide explains how to replace the sample Zava Corp data with your own documents, so the specialist agents answer questions grounded in **your** organization's knowledge.

---

## Understanding the Data Pipeline

Every piece of knowledge flows through a four-layer pipeline before an agent can use it:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         YOUR DOCUMENTS                                    │
│        PDFs, Word docs, Markdown, CSVs, database exports                 │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │  Upload / Index
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   AZURE AI SEARCH INDEX                                   │
│                                                                           │
│   Stores documents as searchable records with fields:                    │
│   id, title, content, category                                           │
│   Semantic configuration enables meaning-based ranking                   │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │  Referenced by
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE SOURCE                                       │
│                                                                           │
│   A Foundry project resource that points to a specific search index.     │
│   Defines connection details and authentication method.                  │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │  Grouped into
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE BASE                                         │
│                                                                           │
│   A named container of one or more Knowledge Sources.                    │
│   Referenced by name in the agent SDK:                                   │
│   AzureAISearchContextProvider(knowledge_base_name="kb1-hr")             │
│   Supports agentic retrieval (model-driven sub-query generation).        │
└──────────────────────────────┬───────────────────────────────────────────┘
                               │  Used by
                               ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                    SPECIALIST AGENT                                        │
│                                                                           │
│   Receives user query → context provider queries KB →                    │
│   retrieved documents injected into context → grounded response          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | What It Does | When You Change It |
|-------|-------------|-------------------|
| **Search Index** | Stores and retrieves your documents | When you update your content |
| **Knowledge Source** | Points to the correct index | When you change index names or connection details |
| **Knowledge Base** | Groups sources for an agent | When you add/remove data sources for an agent |
| **Agent** | Generates answers from retrieved context | When you change agent behavior or instructions |

---

## Option A: Replace Index Documents (Simplest)

The fastest way to use your own data — replace the sample documents in the existing indexes while keeping the same index schema, knowledge sources, and knowledge bases.

### A1. Format Your Documents

Each document needs these fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | String | ✅ (key) | Unique identifier for the document |
| `title` | String | ✅ | Document title (used in semantic ranking) |
| `content` | String | ✅ | The document text (main searchable content) |
| `category` | String | Optional | Category for filtering and faceting |

Example JSON:

```json
[
  {
    "id": "hr-001",
    "title": "Remote Work Policy",
    "content": "All employees may work remotely up to 3 days per week...",
    "category": "policy"
  },
  {
    "id": "hr-002",
    "title": "Annual Performance Review Process",
    "content": "Performance reviews are conducted annually in Q4...",
    "category": "process"
  }
]
```

### A2. Upload via REST API

```bash
SEARCH_ENDPOINT=$(azd env get-value AZURE_SEARCH_ENDPOINT)
INDEX_NAME="index-hr"  # Change to target index
SEARCH_ADMIN_KEY=$(az search admin-key show \
  --resource-group $(azd env get-value AZURE_RESOURCE_GROUP) \
  --service-name $(azd env get-value AZURE_SEARCH_SERVICE_NAME) \
  --query primaryKey -o tsv)

# Delete existing documents (optional — start fresh)
# Note: Easiest way is to delete and recreate the index, or upload
# with @search.action: "mergeOrUpload" to overwrite by ID.

# Upload new documents
curl -X POST "$SEARCH_ENDPOINT/indexes/$INDEX_NAME/docs/index?api-version=2024-07-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -d '{
    "value": [
      {
        "@search.action": "upload",
        "id": "hr-001",
        "title": "Remote Work Policy",
        "content": "All employees may work remotely up to 3 days per week...",
        "category": "policy"
      },
      {
        "@search.action": "upload",
        "id": "hr-002",
        "title": "Annual Performance Review Process",
        "content": "Performance reviews are conducted annually in Q4...",
        "category": "process"
      }
    ]
  }'
```

### A3. Python Script for Batch Upload

For larger document sets, use this script to upload from a JSON file:

```python
"""
batch_upload.py — Upload documents to Azure AI Search from a JSON or CSV file.

Usage:
  python batch_upload.py --index index-hr --file documents.json
  python batch_upload.py --index index-hr --file documents.csv
"""

import argparse
import csv
import json
import os
import uuid

import requests


def load_documents(file_path: str) -> list[dict]:
    """Load documents from JSON or CSV file."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            docs = json.load(f)
    elif ext == ".csv":
        docs = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "id" not in row or not row["id"]:
                    row["id"] = str(uuid.uuid4())
                docs.append(row)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use .json or .csv")

    return docs


def upload_batch(
    search_endpoint: str,
    index_name: str,
    api_key: str,
    documents: list[dict],
    batch_size: int = 100,
) -> None:
    """Upload documents in batches to Azure AI Search."""
    url = f"{search_endpoint}/indexes/{index_name}/docs/index?api-version=2024-07-01"
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key,
    }

    total = len(documents)
    uploaded = 0

    for i in range(0, total, batch_size):
        batch = documents[i : i + batch_size]

        # Add upload action to each document
        payload = {
            "value": [
                {"@search.action": "upload", **doc} for doc in batch
            ]
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()
        succeeded = sum(1 for r in result["value"] if r["status"])
        failed = sum(1 for r in result["value"] if not r["status"])
        uploaded += succeeded

        print(f"  Batch {i // batch_size + 1}: {succeeded} uploaded, {failed} failed")

    print(f"\n✅ Total: {uploaded}/{total} documents uploaded to '{index_name}'")


def main():
    parser = argparse.ArgumentParser(description="Upload documents to Azure AI Search")
    parser.add_argument("--index", required=True, help="Target index name")
    parser.add_argument("--file", required=True, help="Path to JSON or CSV file")
    parser.add_argument("--batch-size", type=int, default=100, help="Upload batch size")
    args = parser.parse_args()

    search_endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    api_key = os.environ.get("AZURE_SEARCH_ADMIN_KEY")

    if not api_key:
        print("⚠️  AZURE_SEARCH_ADMIN_KEY not set. Fetching via Azure CLI...")
        import subprocess
        result = subprocess.run(
            ["az", "search", "admin-key", "show",
             "--resource-group", os.environ["AZURE_RESOURCE_GROUP"],
             "--service-name", os.environ["AZURE_SEARCH_SERVICE_NAME"],
             "--query", "primaryKey", "-o", "tsv"],
            capture_output=True, text=True, check=True,
        )
        api_key = result.stdout.strip()

    documents = load_documents(args.file)
    print(f"📄 Loaded {len(documents)} documents from {args.file}")
    print(f"📤 Uploading to index '{args.index}'...\n")

    upload_batch(search_endpoint, args.index, api_key, documents, args.batch_size)


if __name__ == "__main__":
    main()
```

Example usage:

```bash
# From a JSON file
python batch_upload.py --index index-hr --file my_hr_docs.json

# From a CSV file (must have columns: id, title, content, category)
python batch_upload.py --index index-hr --file my_hr_docs.csv
```

### A4. Verify via Search Explorer

1. Open the [Azure Portal](https://portal.azure.com)
2. Navigate to your **Azure AI Search** resource
3. Click **Search explorer**
4. Select your index (e.g., `index-hr`)
5. Run a blank search (`*`) to see all documents
6. Run a semantic search to test retrieval quality

---

## Option B: Use Azure Blob Storage + Indexer

For document-heavy workflows (PDFs, Word docs, HTML), use an indexer to automatically extract, chunk, and index content.

### B1. Upload Documents to Blob Storage

```bash
STORAGE_ACCOUNT=$(azd env get-value AZURE_STORAGE_ACCOUNT)
CONTAINER_NAME="documents"

# Create the container if it doesn't exist
az storage container create \
  --account-name $STORAGE_ACCOUNT \
  --name $CONTAINER_NAME \
  --auth-mode login

# Upload documents
az storage blob upload-batch \
  --account-name $STORAGE_ACCOUNT \
  --destination $CONTAINER_NAME \
  --source ./my-documents/ \
  --auth-mode login \
  --pattern "*.pdf"
```

### B2. Create a Data Source Connection

```bash
curl -X PUT "$SEARCH_ENDPOINT/datasources/ds-blob-docs?api-version=2024-07-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -d '{
    "name": "ds-blob-docs",
    "type": "azureblob",
    "credentials": {
      "connectionString": "ResourceId=/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<account>;"
    },
    "container": {
      "name": "documents"
    }
  }'
```

> **Tip:** Use the `ResourceId` connection string format with managed identity instead of account keys for better security.

### B3. Create a Skillset for Document Cracking and Chunking

```bash
curl -X PUT "$SEARCH_ENDPOINT/skillsets/ss-doc-chunking?api-version=2024-07-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -d '{
    "name": "ss-doc-chunking",
    "description": "Extract text and chunk documents for search",
    "skills": [
      {
        "@odata.type": "#Microsoft.Skills.Text.SplitSkill",
        "name": "chunk-text",
        "description": "Split documents into chunks",
        "context": "/document",
        "inputs": [
          {"name": "text", "source": "/document/content"}
        ],
        "outputs": [
          {"name": "textItems", "targetName": "chunks"}
        ],
        "textSplitMode": "pages",
        "maximumPageLength": 2000,
        "pageOverlapLength": 200
      }
    ]
  }'
```

### B4. Create an Indexer

```bash
curl -X PUT "$SEARCH_ENDPOINT/indexers/idx-blob-docs?api-version=2024-07-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -d '{
    "name": "idx-blob-docs",
    "dataSourceName": "ds-blob-docs",
    "targetIndexName": "index-hr",
    "skillsetName": "ss-doc-chunking",
    "schedule": {
      "interval": "PT1H"
    },
    "fieldMappings": [
      {"sourceFieldName": "metadata_storage_name", "targetFieldName": "title"},
      {"sourceFieldName": "metadata_storage_path", "targetFieldName": "id", "mappingFunction": {"name": "base64Encode"}}
    ],
    "outputFieldMappings": [
      {"sourceFieldName": "/document/chunks/*", "targetFieldName": "content"}
    ],
    "parameters": {
      "configuration": {
        "dataToExtract": "contentAndMetadata",
        "parsingMode": "default"
      }
    }
  }'
```

### B5. Monitor Indexer Status

```bash
# Check indexer status
curl "$SEARCH_ENDPOINT/indexers/idx-blob-docs/status?api-version=2024-07-01" \
  -H "api-key: $SEARCH_ADMIN_KEY" | python -m json.tool

# Manually trigger a run (don't wait for schedule)
curl -X POST "$SEARCH_ENDPOINT/indexers/idx-blob-docs/run?api-version=2024-07-01" \
  -H "api-key: $SEARCH_ADMIN_KEY"
```

The indexer will:
1. Detect new/modified blobs in the container
2. Extract text content (PDF, Word, HTML, etc.)
3. Split into chunks using the skillset
4. Upload chunks to the target search index
5. Run on schedule (every hour in the example above)

---

## Option C: Use SharePoint / OneLake / Other Data Sources

Azure AI Search supports many data source types beyond blob storage:

| Data Source | Type Value | Use Case |
|-------------|-----------|----------|
| Azure Blob Storage | `azureblob` | PDFs, Word docs, images |
| Azure SQL Database | `azuresql` | Structured data, records |
| Azure Cosmos DB | `cosmosdb` | NoSQL documents |
| Azure Table Storage | `azuretable` | Key-value data |
| SharePoint Online | `sharepoint` | Enterprise documents |
| OneLake (Fabric) | `onelake` | Lakehouse data |
| ADLS Gen2 | `adlsgen2` | Data lake files |

For SharePoint specifically:

```bash
curl -X PUT "$SEARCH_ENDPOINT/datasources/ds-sharepoint?api-version=2024-07-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -d '{
    "name": "ds-sharepoint",
    "type": "sharepoint",
    "credentials": {
      "connectionString": "SharePointOnlineEndpoint=https://contoso.sharepoint.com/sites/hr;ApplicationId=<app-id>;TenantId=<tenant-id>"
    },
    "container": {
      "name": "defaultSiteLibrary"
    }
  }'
```

> **Reference:** See the [Azure AI Search data source documentation](https://learn.microsoft.com/azure/search/search-data-sources-gallery) for detailed setup instructions for each connector.

---

## Updating Knowledge Bases After Index Changes

### Documents Are Picked Up Automatically

When you add, update, or delete documents in a search index, the Knowledge Base **automatically reflects these changes** at query time. This is because:

- Agentic retrieval queries the index **live** at runtime
- There is no static snapshot or cache to invalidate
- New documents are available as soon as they're indexed

**No action needed** — just update the index and the agent will use the new data.

### When You Do Need to Update the KB Configuration

You only need to modify the Knowledge Base or Knowledge Source if:

| Scenario | What to Update |
|----------|---------------|
| Changed the index name | Update the Knowledge Source's `indexName` |
| Changed the semantic configuration name | Update the Knowledge Source's `semanticConfiguration` |
| Changed the search endpoint | Update the Knowledge Source's `endpoint` |
| Adding a second index to the same KB | Add a new Knowledge Source to the KB |
| Changing retrieval mode | Update the Knowledge Base's `retrievalMode` |

Example — update a Knowledge Source:

```bash
ACCESS_TOKEN=$(az account get-access-token \
  --resource "https://cognitiveservices.azure.com" \
  --query accessToken -o tsv)

curl -X PUT "$PROJECT_ENDPOINT/knowledge/sources/ks-hr?api-version=2025-11-01-preview" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -d '{
    "type": "AzureAISearch",
    "properties": {
      "endpoint": "'$SEARCH_ENDPOINT'",
      "indexName": "index-hr-v2",
      "authenticationType": "SystemAssignedManagedIdentity",
      "semanticConfiguration": "my-custom-config"
    }
  }'
```

---

## Best Practices

### 1. Document Chunking Strategy

How you chunk documents significantly impacts retrieval quality.

| Strategy | Chunk Size | Overlap | Best For |
|----------|-----------|---------|----------|
| **Small chunks** | 500–1000 chars | 100 chars | FAQ-style, specific facts |
| **Medium chunks** | 1000–2000 chars | 200 chars | Policy documents, guides (recommended default) |
| **Large chunks** | 2000–4000 chars | 400 chars | Long-form narratives, complex procedures |
| **Whole documents** | Full text | N/A | Short documents (< 2000 chars) |

**Recommendations:**
- Start with **medium chunks (1000–2000 chars)** for most use cases
- Use **overlap (10–20% of chunk size)** to avoid losing context at chunk boundaries
- Keep each chunk **self-contained** — it should make sense when read in isolation
- Include the document **title** in each chunk to provide context

Example chunking with overlap:

```python
def chunk_document(text: str, chunk_size: int = 1500, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at a sentence boundary
        if end < len(text):
            last_period = chunk.rfind(". ")
            if last_period > chunk_size * 0.5:
                end = start + last_period + 2
                chunk = text[start:end]

        chunks.append(chunk.strip())
        start = end - overlap

    return chunks
```

### 2. Semantic Configuration Tuning

The semantic configuration tells Azure AI Search which fields matter most for ranking.

```json
{
  "semantic": {
    "configurations": [
      {
        "name": "default",
        "prioritizedFields": {
          "titleField": {"fieldName": "title"},
          "contentFields": [
            {"fieldName": "content"}
          ],
          "keywordsFields": [
            {"fieldName": "category"}
          ]
        }
      }
    ]
  }
}
```

**Tuning tips:**
- The `titleField` is heavily weighted — make sure it's descriptive
- `contentFields` are used for passage extraction — put your main text here
- `keywordsFields` help with filtering and faceting — use for categories/tags
- You can have multiple `contentFields` ranked by priority

### 3. Testing Retrieval Quality

Before deploying changes, test retrieval quality directly against the search index:

```bash
# Test with semantic ranking
curl -X POST "$SEARCH_ENDPOINT/indexes/index-hr/docs/search?api-version=2024-07-01" \
  -H "Content-Type: application/json" \
  -H "api-key: $SEARCH_ADMIN_KEY" \
  -d '{
    "search": "How many vacation days do I get?",
    "queryType": "semantic",
    "semanticConfiguration": "default",
    "top": 5,
    "select": "title, content, category",
    "captions": "extractive",
    "answers": "extractive|count-3"
  }'
```

**What to look for:**
- Are the top 3 results relevant to the query?
- Do the extracted captions contain the answer?
- Are irrelevant documents being returned?

**Comparing before and after:**

```python
"""
test_retrieval.py — Compare retrieval quality before and after index changes.

Usage:
  python test_retrieval.py --index index-hr --queries test_queries.json
"""

import json
import os
import requests


def search(endpoint, index, api_key, query, top=5):
    url = f"{endpoint}/indexes/{index}/docs/search?api-version=2024-07-01"
    payload = {
        "search": query,
        "queryType": "semantic",
        "semanticConfiguration": "default",
        "top": top,
        "select": "id, title",
    }
    resp = requests.post(url, headers={"api-key": api_key, "Content-Type": "application/json"}, json=payload)
    resp.raise_for_status()
    return [doc["title"] for doc in resp.json()["value"]]


def main():
    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    api_key = os.environ["AZURE_SEARCH_ADMIN_KEY"]
    index = "index-hr"

    test_queries = [
        {"query": "What is the PTO policy?", "expected_top": "PTO Policy"},
        {"query": "How do I request parental leave?", "expected_top": "Parental Leave"},
        {"query": "What health insurance plans are offered?", "expected_top": "Health Insurance"},
    ]

    print(f"Testing retrieval quality for '{index}':\n")

    for tc in test_queries:
        results = search(endpoint, index, api_key, tc["query"])
        top_result = results[0] if results else "NO RESULTS"
        match = "✅" if tc["expected_top"].lower() in top_result.lower() else "❌"

        print(f"  {match} Query: {tc['query']}")
        print(f"     Expected: {tc['expected_top']}")
        print(f"     Got:      {top_result}")
        print()


if __name__ == "__main__":
    main()
```

### 4. Naming Conventions

Keep index and KB names consistent across the system:

| Domain | Index Name | Knowledge Source | Knowledge Base |
|--------|-----------|-----------------|----------------|
| HR | `index-hr` | `ks-hr` | `kb1-hr` |
| Marketing | `index-marketing` | `ks-marketing` | `kb2-marketing` |
| Products | `index-products` | `ks-products` | `kb3-products` |
| Finance | `index-finance` | `ks-finance` | `kb4-finance` |

**Convention:**
- Indexes: `index-<domain>`
- Knowledge Sources: `ks-<domain>`
- Knowledge Bases: `kb<number>-<domain>`
- Agent files: `app/backend/agents/<domain>_agent.py`

### 5. Document Quality Checklist

Before uploading documents, ensure they meet these standards:

- [ ] **No empty content** — every document has meaningful text in the `content` field
- [ ] **Unique IDs** — no duplicate `id` values within an index
- [ ] **Descriptive titles** — titles clearly describe the document's content
- [ ] **Consistent categories** — use a controlled vocabulary for the `category` field
- [ ] **Reasonable length** — chunks between 500–4000 characters (not too short, not too long)
- [ ] **Clean text** — remove HTML tags, excessive whitespace, boilerplate headers/footers
- [ ] **Up to date** — documents reflect current policies, products, or information

---

## Troubleshooting

### Agent returns generic answers, ignoring my documents

**Cause:** The Knowledge Base isn't retrieving your documents. Common reasons:
1. Documents weren't uploaded successfully
2. Semantic configuration doesn't match the index
3. RBAC roles not assigned (AIServices MI can't read the index)

**Fix:** Test the index directly with a search query (see Section A4). If results are correct there but not from the agent, check RBAC role assignments.

### "Index not found" errors

**Cause:** The Knowledge Source points to a non-existent index name.

**Fix:** Verify the index exists:
```bash
curl "$SEARCH_ENDPOINT/indexes?api-version=2024-07-01" \
  -H "api-key: $SEARCH_ADMIN_KEY" | python -m json.tool
```

### Documents appear in search but agent can't find them

**Cause:** Usually a semantic configuration mismatch. The KB uses semantic ranking, so the configuration must be present and match.

**Fix:** Verify the semantic config exists on the index:
```bash
curl "$SEARCH_ENDPOINT/indexes/index-hr?api-version=2024-07-01" \
  -H "api-key: $SEARCH_ADMIN_KEY" | python -c "
import json, sys
idx = json.load(sys.stdin)
print(json.dumps(idx.get('semantic', {}), indent=2))
"
```

### Indexer fails with "access denied"

**Cause:** The search service's managed identity doesn't have read access to the data source (blob storage, SQL, etc.).

**Fix:** Assign the appropriate role:
```bash
az role assignment create \
  --assignee $(az search service show --name <search-name> --resource-group <rg> --query identity.principalId -o tsv) \
  --role "Storage Blob Data Reader" \
  --scope "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Storage/storageAccounts/<account>"
```

---

## Next Steps

- 🚀 [Quick Start](./01-quick-start.md) — deploy the demo from scratch
- 📐 [Architecture Overview](./02-architecture-overview.md) — understand the full system
- 🤖 [Add a New Agent](./03-add-new-agent.md) — extend with more specialist agents
