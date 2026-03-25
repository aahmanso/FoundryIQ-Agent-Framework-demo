# 📚 Learning Guides

Welcome to the **FoundryIQ and Agent Framework Demo** learning guides! These guides will help you understand, customize, and extend the multi-agent orchestration system built on Microsoft Foundry.

## About This Demo

This project demonstrates a multi-agent orchestration pattern where:

- An **Orchestrator** routes user queries to specialist agents
- **3 Specialist Agents** (HR, Products, Marketing) handle domain-specific questions
- **FoundryIQ Knowledge Bases** provide grounded retrieval from Azure AI Search
- Everything runs on the **new Microsoft Foundry** architecture (AIServices + Projects)
- Authentication is **RBAC-only** using `DefaultAzureCredential` — no API keys
- Infrastructure is deployed via **`azd up`** with Bicep IaC

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Agent SDK | `agent-framework-core`, `agent-framework-azure-ai`, `agent-framework-azure-ai-search` |
| LLM | gpt-4.1 on Azure AI Services |
| Search | Azure AI Search with semantic configuration |
| Auth | DefaultAzureCredential (RBAC) |
| IaC | Bicep via Azure Developer CLI (`azd`) |
| Runtime | Python (FastAPI backend) + React (frontend) |

---

## Getting Started

| # | Guide | Description | Level |
|---|-------|-------------|-------|
| 1 | [Quick Start](01-quick-start.md) | Deploy the demo end-to-end with `azd up` | 🟢 Beginner |
| 2 | [Architecture Overview](02-architecture-overview.md) | Deep-dive into how the system works | 🟢 Beginner |

> **New here?** Start with Guide 1 to get the demo running, then read Guide 2 to understand how all the pieces fit together.

---

## Hands-On Experiences

| # | Guide | Description | Level |
|---|-------|-------------|-------|
| 3 | [Add a New Agent](03-add-new-agent.md) | Extend the system with a Finance agent | 🔵 Intermediate |
| 4 | [Customize Knowledge Bases](04-customize-knowledge-bases.md) | Replace sample data with your own | 🔵 Intermediate |
| 5 | [Prompt Engineering Lab](05-prompt-engineering-lab.md) | Experiment with routing and specialist prompts | 🔵 Intermediate |

> **Want to customize?** Follow guides 4 → 5 to make the demo your own.

---

## Advanced Exploration

| # | Guide | Description | Level |
|---|-------|-------------|-------|
| 6 | [Evaluate & Optimize](06-evaluate-optimize-agents.md) | Measure and improve agent quality | 🟣 Advanced |
| 7 | [Deploy Hosted Agents](07-deploy-hosted-agents.md) | Containerize and deploy to Foundry runtime | 🟣 Advanced |
| 8 | [Tracing & Observability](08-tracing-observability.md) | Monitor agent behavior in production | 🟣 Advanced |

> **Going to production?** Read guides 6 → 8 → 9 for quality, monitoring, and troubleshooting.

---

## Reference

| # | Guide | Description | Level |
|---|-------|-------------|-------|
| 9 | [Troubleshooting](09-troubleshooting.md) | Solutions for common issues we actually hit | 🟠 Reference |
| 10 | [New Foundry vs Legacy](10-new-foundry-vs-legacy.md) | Comparison with old ML Hub architecture | 🟠 Reference |

> **Migrating from old Azure AI?** Read Guide 10 first — it explains everything that changed and how to migrate.

---

## Recommended Learning Paths

### 🚀 "I'm New to This Project"

```
Guide 1: Quick Start
  → Guide 2: Architecture Overview
    → Guide 3: Add a New Agent
```

Deploy the demo, understand the architecture, then extend it with your own agent.

### 🎨 "I Want to Customize It"

```
Guide 4: Customize Knowledge Bases
  → Guide 5: Prompt Engineering Lab
```

Replace sample data with your own documents and tune the prompts for your use case.

### 🏭 "I'm Going to Production"

```
Guide 6: Evaluate & Optimize
  → Guide 8: Tracing & Observability
    → Guide 9: Troubleshooting
```

Measure quality, set up monitoring, and know how to fix things when they break.

### 🔄 "I'm Migrating from Old Azure AI"

```
Guide 10: New Foundry vs Legacy
  → Guide 1: Quick Start
    → Guide 9: Troubleshooting
```

Understand the architectural differences, then deploy fresh with the new Foundry model.

---

## Level Legend

| Icon | Level | Description |
|------|-------|-------------|
| 🟢 | Beginner | No prior Azure AI experience needed |
| 🔵 | Intermediate | Familiarity with the demo architecture helpful |
| 🟣 | Advanced | Requires understanding of Azure services and agent patterns |
| 🟠 | Reference | Consult as needed — not a linear walkthrough |

---

## Prerequisites

Before starting any guide, ensure you have:

- **Azure subscription** with Contributor access
- **Azure CLI** (`az`) installed and logged in
- **Azure Developer CLI** (`azd`) installed
- **Python 3.11+** with pip
- **Node.js 18+** (for the frontend)
- **Git** for cloning the repository

### Quick Environment Check

```bash
az --version          # Azure CLI 2.60+
azd version           # Azure Developer CLI 1.9+
python --version      # Python 3.11+
node --version        # Node.js 18+
```

---

## Contributing

Found an issue in a guide? Want to add a new one? Please open a PR! Guides follow the naming convention `NN-descriptive-name.md` where `NN` is the guide number.
