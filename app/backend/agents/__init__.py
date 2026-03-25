"""
Agents module for FoundryIQ + Agent Framework demo.

CONFIGURATION (set via environment variables, auto-populated by ``azd up``):
- AZURE_SEARCH_ENDPOINT: Azure AI Search endpoint
- AZURE_AI_PROJECT_ENDPOINT: Foundry project endpoint
- AZURE_OPENAI_DEPLOYMENT: Model deployment name (default: gpt-4.1)
- KBs: kb1-hr, kb2-marketing, kb3-products
"""

# KB-grounded agents
from .hr_agent import run_hr_agent, HR_INSTRUCTIONS
from .marketing_agent import run_marketing_agent, MARKETING_INSTRUCTIONS
from .products_agent import run_products_agent, PRODUCTS_INSTRUCTIONS

# Orchestrator
from .orchestrator import run_orchestrator, run_single_query

__all__ = [
    # KB agents
    "run_hr_agent",
    "run_marketing_agent", 
    "run_products_agent",
    "HR_INSTRUCTIONS",
    "MARKETING_INSTRUCTIONS",
    "PRODUCTS_INSTRUCTIONS",
    # Orchestrator
    "run_orchestrator",
    "run_single_query",
]
