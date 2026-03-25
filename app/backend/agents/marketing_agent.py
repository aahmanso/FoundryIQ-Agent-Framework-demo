"""Marketing Agent - Connected to kb2-marketing Knowledge Base."""

import asyncio
import os
from azure.identity.aio import DefaultAzureCredential

from agent_framework import Agent, Message, Content
from agent_framework.azure import AzureAIAgentClient, AzureAISearchContextProvider

SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "")
PROJECT_ENDPOINT = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "")
MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")

MARKETING_INSTRUCTIONS = """You are a Marketing Specialist Agent for Zava Corporation.
Answer questions about marketing campaigns, brand guidelines, and marketing strategies using the knowledge base.
Be specific and cite sources when possible."""


async def run_marketing_agent(query: str) -> str:
    """Run the Marketing agent with a query."""
    async with DefaultAzureCredential() as credential:
        async with (
            AzureAIAgentClient(
                project_endpoint=PROJECT_ENDPOINT,
                model_deployment_name=MODEL,
                credential=credential,
            ) as client,
            AzureAISearchContextProvider(
                endpoint=SEARCH_ENDPOINT,
                knowledge_base_name="kb2-marketing",
                credential=credential,
                mode="agentic",
                knowledge_base_output_mode="answer_synthesis",
            ) as kb_context,
        ):
            agent = Agent(
                client=client,
                context_provider=kb_context,
                instructions=MARKETING_INSTRUCTIONS,
            )

            # ✅ Compatible with your installed agent-framework build
            message = Message(role="user", contents=[Content.from_text(query)])

            response = await agent.run(message)
            return response.text


async def main():
    print("\n📣 Marketing Agent (kb2-marketing)")
    print("=" * 50)

    query = "What are our current marketing campaigns?"
    print(f"\n❓ Query: {query}")

    response = await run_marketing_agent(query)
    print(f"\n💬 Response:\n{response}")


if __name__ == "__main__":
    asyncio.run(main())
