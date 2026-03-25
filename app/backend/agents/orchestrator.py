import asyncio
import os
from azure.identity.aio import DefaultAzureCredential

from agent_framework import Agent, Message, Content
from agent_framework.azure import AzureAIAgentClient, AzureAISearchContextProvider

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "")
MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")

HR_KB_NAME = "kb1-hr"
MKT_KB_NAME = "kb2-marketing"
PRD_KB_NAME = "kb3-products"

# ✅ IMPORTANT: provide source_id (prefer env vars)
HR_SOURCE_ID = os.getenv("KB1_HR_SOURCE_ID", HR_KB_NAME)
MKT_SOURCE_ID = os.getenv("KB2_MARKETING_SOURCE_ID", MKT_KB_NAME)
PRD_SOURCE_ID = os.getenv("KB3_PRODUCTS_SOURCE_ID", PRD_KB_NAME)

HR_INSTRUCTIONS = """You are an HR Specialist Agent for Zava Corporation.
Answer questions about HR policies, PTO, benefits, and employee handbook using the knowledge base.
Be specific and cite sources when possible."""

MARKETING_INSTRUCTIONS = """You are a Marketing Specialist Agent for Zava Corporation.
Answer questions about marketing campaigns, brand guidelines, and marketing strategies using the knowledge base.
Be specific and cite sources when possible."""

PRODUCTS_INSTRUCTIONS = """You are a Products Specialist Agent for Zava Corporation.
Answer questions about products, catalog, specifications, and pricing using the knowledge base.
Be specific and cite sources when possible."""

ROUTER_INSTRUCTIONS = """You are a routing agent. Analyze the user query and determine which specialist should handle it.

Respond with ONLY one of these agent names:
- "hr"
- "marketing"
- "products"

Just respond with the agent name, nothing else."""


def user_message(text: str) -> Message:
    return Message(role="user", contents=[Content.from_text(text)])


async def route_query(router: Agent, query: str) -> str:
    resp = await router.run(user_message(query))
    route = (resp.text or "").strip().lower()
    if "hr" in route:
        return "hr"
    if "marketing" in route or "brand" in route or "campaign" in route:
        return "marketing"
    if "product" in route:
        return "products"
    return "hr"


def _make_client(credential):
    return AzureAIAgentClient(
        project_endpoint=PROJECT_ENDPOINT,
        model_deployment_name=MODEL,
        credential=credential,
    )


def _make_kb(source_id, kb_name, credential):
    return AzureAISearchContextProvider(
        source_id,
        endpoint=SEARCH_ENDPOINT,
        knowledge_base_name=kb_name,
        credential=credential,
        mode="agentic",
        knowledge_base_output_mode="answer_synthesis",
    )


async def run_orchestrator():
    async with DefaultAzureCredential() as credential:
        # Use separate clients for router and specialists to avoid shared state
        async with (
            _make_client(credential) as router_client,
            _make_client(credential) as specialist_client,
            _make_kb(HR_SOURCE_ID, HR_KB_NAME, credential) as hr_kb,
            _make_kb(MKT_SOURCE_ID, MKT_KB_NAME, credential) as marketing_kb,
            _make_kb(PRD_SOURCE_ID, PRD_KB_NAME, credential) as products_kb,
        ):
            router = Agent(client=router_client, instructions=ROUTER_INSTRUCTIONS)

            specialists = {
                "hr": Agent(client=specialist_client, context_provider=hr_kb, instructions=HR_INSTRUCTIONS),
                "marketing": Agent(client=specialist_client, context_provider=marketing_kb, instructions=MARKETING_INSTRUCTIONS),
                "products": Agent(client=specialist_client, context_provider=products_kb, instructions=PRODUCTS_INSTRUCTIONS),
            }

            print("\n🤖 Multi-Agent Orchestrator with KB Grounding")
            print("=" * 55)
            print("Type 'quit' to exit\n")

            while True:
                query = input("❓ Question: ").strip()
                if not query:
                    continue
                if query.lower() in ["quit", "exit", "q"]:
                    print("\n👋 Goodbye!")
                    return

                route = await route_query(router, query)
                print(f"📍 Routing to: {route.upper()} agent")

                resp = await specialists[route].run(user_message(query))
                print(f"\n💬 Response:\n{resp.text}\n")
                print("-" * 55)


async def run_single_query(query: str) -> tuple[str, str, list[dict]]:
    """Run a single query through the orchestrator and return (route, response_text, sources).

    Used by the FastAPI backend for non-interactive requests.
    """
    async with DefaultAzureCredential() as credential:
        async with (
            _make_client(credential) as router_client,
            _make_client(credential) as specialist_client,
            _make_kb(HR_SOURCE_ID, HR_KB_NAME, credential) as hr_kb,
            _make_kb(MKT_SOURCE_ID, MKT_KB_NAME, credential) as marketing_kb,
            _make_kb(PRD_SOURCE_ID, PRD_KB_NAME, credential) as products_kb,
        ):
            router = Agent(client=router_client, instructions=ROUTER_INSTRUCTIONS)

            specialists = {
                "hr": Agent(client=specialist_client, context_provider=hr_kb, instructions=HR_INSTRUCTIONS),
                "marketing": Agent(client=specialist_client, context_provider=marketing_kb, instructions=MARKETING_INSTRUCTIONS),
                "products": Agent(client=specialist_client, context_provider=products_kb, instructions=PRODUCTS_INSTRUCTIONS),
            }

            route = await route_query(router, query)
            resp = await specialists[route].run(user_message(query))
            return route, resp.text or "", []


if __name__ == "__main__":
    asyncio.run(run_orchestrator())
