# Add Tracing and Observability

Multi-agent systems are inherently complex. When a user asks a question, the orchestrator must route it to the right specialist agent, which then queries a FoundryIQ Knowledge Base, calls the LLM, and returns a grounded response. Without observability, debugging issues like "why did the HR agent answer a marketing question?" or "why is response latency spiking?" becomes guesswork.

This guide walks you through three complementary approaches to monitoring the FoundryIQ and Agent Framework Demo in production.

---

## Why Observability Matters

In this demo, a single user query passes through multiple stages:

```
User Query
  → Orchestrator (routing decision)
    → Specialist Agent (HR / Products / Marketing)
      → FoundryIQ Knowledge Base (retrieval from Azure AI Search)
        → gpt-4.1 (LLM generation with grounded context)
          → Response back to user
```

At each stage, things can go wrong:

- **Routing errors**: The orchestrator sends a product question to the HR agent
- **Retrieval failures**: The Knowledge Base returns no documents (empty grounding)
- **High latency**: One agent takes 30+ seconds due to agentic retrieval reasoning
- **Model errors**: Token limits exceeded, content filtered, or rate limited
- **Silent degradation**: Responses become generic because grounding stopped working

You need visibility into **which agent handled what**, **latency per step**, **retrieval quality**, and **error rates**.

---

## Option 1: Application Insights Integration

Application Insights provides the deepest level of tracing. The Agent Framework SDK emits OpenTelemetry-compatible traces that Application Insights can collect automatically.

### Step 1: Create or Locate Your Application Insights Resource

If you deployed with `azd up`, an Application Insights resource may already exist in your resource group:

```bash
az resource list --resource-group <rg> --resource-type Microsoft.Insights/components --output table
```

If not, create one:

```bash
az monitor app-insights component create \
  --app foundryiq-demo-insights \
  --location eastus2 \
  --resource-group <rg> \
  --application-type web
```

Retrieve the connection string:

```bash
az monitor app-insights component show \
  --app foundryiq-demo-insights \
  --resource-group <rg> \
  --query connectionString -o tsv
```

### Step 2: Set the Environment Variable

Add the connection string to your environment. For local development:

```bash
# Load all azd env vars
azd env get-values > .env

# Add the App Insights connection string
echo 'APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=xxx;IngestionEndpoint=https://..."' >> .env
```

For Container Apps, update the Bicep or set it directly:

```bash
az containerapp update \
  --name <app-name> \
  --resource-group <rg> \
  --set-env-vars "APPLICATIONINSIGHTS_CONNECTION_STRING=<connection-string>"
```

### Step 3: Install the OpenTelemetry Package

```bash
pip install azure-monitor-opentelemetry
```

Add it to your `requirements.txt`:

```
azure-monitor-opentelemetry>=1.6.0
```

### Step 4: Instrument Your Application

Add the following to the top of `main.py` (before any other Azure SDK imports):

```python
import os
from azure.monitor.opentelemetry import configure_azure_monitor

# Initialize Azure Monitor tracing — must be called before other Azure SDK imports
connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
if connection_string:
    configure_azure_monitor(
        connection_string=connection_string,
        enable_live_metrics=True,
    )
    print("✅ Azure Monitor tracing enabled")
else:
    print("⚠️  APPLICATIONINSIGHTS_CONNECTION_STRING not set — tracing disabled")
```

Once configured, the Azure SDKs automatically emit traces for:

- **Agent invocations**: Each call to a specialist agent
- **Knowledge Base queries**: FoundryIQ retrieval requests to Azure AI Search
- **Model calls**: gpt-4.1 completions via Azure AI Services
- **HTTP requests**: All outbound REST calls

### Step 5: Verify Traces Are Flowing

1. Run the application and send a few test queries
2. Wait 2-3 minutes for traces to propagate
3. Open **Azure Portal → Application Insights → Transaction search**
4. Filter by time range and look for dependency calls to `cognitiveservices` and `search.windows.net`

---

## Option 2: Foundry Tracing

The Foundry portal includes a built-in trace viewer specifically designed for agent conversations.

### Accessing Foundry Tracing

1. Open [ai.azure.com](https://ai.azure.com)
2. Navigate to your project
3. Click **Tracing** in the left sidebar

### What You Can See

The Foundry trace viewer shows:

- **Full conversation traces**: Each user message and the complete processing chain
- **Agent-level detail**: Which agent was invoked, what instructions it used
- **Retrieval context**: What documents the Knowledge Base returned
- **Token usage**: Input/output tokens per call
- **Latency breakdown**: Time spent in routing, retrieval, and generation

### Filtering and Searching

- Filter by **agent name** (e.g., show only HR agent traces)
- Filter by **time range** (last hour, last 24 hours, custom)
- Filter by **status** (success, failure)
- Search by **query text** to find specific user interactions

### Enabling Foundry Tracing

Foundry tracing is enabled automatically when you create agents via the Agent API. No additional configuration is needed if your agents are created with the correct project endpoint:

```
https://<ais-name>.services.ai.azure.com/api/projects/<project-name>
```

> **Note**: Foundry tracing captures agent-level traces. For infrastructure-level traces (HTTP latency, dependency failures), use Application Insights.

---

## Option 3: Custom Structured Logging

For maximum control, add structured logging directly to the orchestrator. This is especially useful for capturing business-level metrics that neither App Insights nor Foundry tracing provide automatically.

### Add a JSON Logger

Create a logging utility (`src/logging_config.py`):

```python
import logging
import json
import sys
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for agent observability."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include extra fields if present
        for key in ("agent_name", "query", "latency_ms", "sources_count",
                     "response_length", "routing_decision", "error_type"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)
        return json.dumps(log_entry)


def setup_logging():
    """Configure structured JSON logging."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("orchestrator")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger
```

### Instrument the Orchestrator

Add logging calls to your orchestrator (`orchestrator.py`):

```python
import time
from logging_config import setup_logging

logger = setup_logging()


async def handle_query(query: str) -> str:
    start_time = time.perf_counter()

    # Log incoming query
    logger.info(
        "Query received",
        extra={"query": query[:200]}  # Truncate for log safety
    )

    # Route to specialist agent
    routing_start = time.perf_counter()
    agent_name = await route_query(query)
    routing_latency = (time.perf_counter() - routing_start) * 1000

    logger.info(
        "Query routed",
        extra={
            "routing_decision": agent_name,
            "latency_ms": round(routing_latency, 2),
            "query": query[:200],
        }
    )

    # Execute specialist agent
    agent_start = time.perf_counter()
    response = await execute_agent(agent_name, query)
    agent_latency = (time.perf_counter() - agent_start) * 1000

    total_latency = (time.perf_counter() - start_time) * 1000

    logger.info(
        "Query completed",
        extra={
            "agent_name": agent_name,
            "latency_ms": round(total_latency, 2),
            "response_length": len(response),
            "query": query[:200],
        }
    )

    return response
```

### Example Log Output

```json
{"timestamp": "2025-06-27T14:30:00.123Z", "level": "INFO", "logger": "orchestrator", "message": "Query routed", "routing_decision": "hr_agent", "latency_ms": 245.67, "query": "What is the parental leave policy?"}
{"timestamp": "2025-06-27T14:30:02.456Z", "level": "INFO", "logger": "orchestrator", "message": "Query completed", "agent_name": "hr_agent", "latency_ms": 2578.34, "response_length": 1247, "query": "What is the parental leave policy?"}
```

---

## Building a Dashboard

Use KQL (Kusto Query Language) in Application Insights to build visualizations.

### Agent Routing Distribution (Pie Chart)

```kql
customEvents
| where name == "Query routed"
| extend agent = tostring(customDimensions["routing_decision"])
| summarize count() by agent
| render piechart
```

### Average Response Latency by Agent (Bar Chart)

```kql
customEvents
| where name == "Query completed"
| extend agent = tostring(customDimensions["agent_name"]),
         latency = todouble(customDimensions["latency_ms"])
| summarize avg(latency), percentile(latency, 95) by agent
| render barchart
```

### Error Rate Over Time (Line Chart)

```kql
requests
| where timestamp > ago(24h)
| summarize
    total = count(),
    errors = countif(resultCode >= 400)
    by bin(timestamp, 1h)
| extend error_rate = round(100.0 * errors / total, 2)
| project timestamp, error_rate
| render timechart
```

### Top Queries by Frequency

```kql
customEvents
| where name == "Query received"
| extend query = tostring(customDimensions["query"])
| summarize count() by query
| top 20 by count_
| render table
```

### Latency Percentiles Over Time

```kql
customEvents
| where name == "Query completed"
| extend latency = todouble(customDimensions["latency_ms"])
| summarize
    p50 = percentile(latency, 50),
    p90 = percentile(latency, 90),
    p99 = percentile(latency, 99)
    by bin(timestamp, 1h)
| render timechart
```

### Creating an Azure Dashboard

1. Open **Azure Portal → Dashboard**
2. Click **+ New dashboard → Blank dashboard**
3. Add tiles → **Logs** → select your Application Insights resource
4. Paste each KQL query above into a separate tile
5. Set the visualization type (pie chart, bar chart, etc.)
6. Save and pin the dashboard

Alternatively, create an **Azure Workbook** for a more interactive experience:

1. Open **Application Insights → Workbooks → + New**
2. Add query steps with the KQL above
3. Add parameters for time range and agent name filtering
4. Share the workbook with your team

---

## Alerting

Set up alerts to catch issues before users notice them.

### High Error Rate Alert

```bash
az monitor metrics alert create \
  --name "high-error-rate" \
  --resource-group <rg> \
  --scopes <app-insights-resource-id> \
  --condition "count requests/failed > 10" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action <action-group-id> \
  --description "More than 10 failed requests in 5 minutes"
```

### High Latency Alert

Create a log-based alert in the Azure Portal:

1. Open **Application Insights → Alerts → + New alert rule**
2. Condition → **Custom log search**
3. Query:
   ```kql
   customEvents
   | where name == "Query completed"
   | extend latency = todouble(customDimensions["latency_ms"])
   | where latency > 15000
   | summarize count() by bin(timestamp, 5m)
   | where count_ > 5
   ```
4. Set threshold: **Greater than 0**
5. Set evaluation period: **Every 5 minutes**

### Routing Failure Alert

```kql
customEvents
| where name == "Query routed"
| extend agent = tostring(customDimensions["routing_decision"])
| where isempty(agent) or agent == "unknown"
| summarize count() by bin(timestamp, 5m)
| where count_ > 3
```

### Action Groups

Create an action group for notifications:

```bash
az monitor action-group create \
  --name "agent-alerts" \
  --resource-group <rg> \
  --short-name "AgentAlerts" \
  --action email admin admin@contoso.com \
  --action webhook teams "https://outlook.office.com/webhook/..."
```

---

## Summary

| Approach | Best For | Setup Effort | Detail Level |
|----------|----------|-------------|--------------|
| Application Insights | Full-stack tracing, dashboards, alerting | Medium | High |
| Foundry Tracing | Agent conversation debugging | Low | Medium |
| Custom Logging | Business metrics, custom dimensions | Medium | Customizable |

**Recommendation**: Use all three in production. Foundry Tracing for day-to-day debugging, Application Insights for dashboards and alerting, and custom logging for business-specific metrics.

---

[← Deploy Hosted Agents](07-deploy-hosted-agents.md) | [Troubleshooting →](09-troubleshooting.md)
