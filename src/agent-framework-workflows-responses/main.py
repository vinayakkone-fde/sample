# Copyright (c) Microsoft. All rights reserved.

import os

from agent_framework import Agent, AgentExecutor, WorkflowBuilder
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def main():
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
    )

    research_agent = Agent(
        client=client,
        instructions=(
            "You are a careful research assistant. Research the user's topic using Bing web search and build a factual, "
            "balanced brief. Cite sourced claims inline as Markdown links using the actual source title and URL returned "
            "by search. End with a Sources section listing the sources you relied on. Cover key concepts, background, "
            "relevant perspectives, and implications. Separate established facts from uncertainty; never invent facts, "
            "statistics, or citations."
        ),
        name="topic_researcher",
        tools=[client.get_web_search_tool(search_context_size="high")],
    )

    organization_agent = Agent(
        client=client,
        instructions=(
            "Turn the research brief into a clear, well-organized Markdown article. Use a descriptive title, an "
            "overview, meaningful sections, and relevant subsections. Arrange ideas in a logical order, use concise "
            "language, and preserve the research agent's qualifications, uncertainty, inline citations, and Sources "
            "section. Do not add unsupported claims or remove source URLs."
        ),
        name="content_organizer",
    )

    faq_agent = Agent(
        client=client,
        instructions=(
            "Return one complete Markdown document. Begin by reproducing the entire organized article from the "
            "input, preserving its title, sections, qualifications, and meaning. Then append a clearly titled "
            "Frequently Asked Questions section. Do not return only the FAQ. Include questions and "
            "answers about legal considerations, social impacts, and other relevant areas such as ethical, economic, "
            "environmental, safety, or technical concerns. Keep answers grounded in the article, distinguish facts "
            "from uncertainty, and do not invent details. Preserve the article's citations and Sources section. Use "
            "Bing web search to substantiate any additional factual claims, cite them inline as Markdown links using "
            "the actual source title and URL, and include any new sources in the Sources section. Legal answers must be "
            "general information, not legal advice; note when laws vary by jurisdiction and recommend consulting a "
            "qualified professional for specific cases."
        ),
        name="faq_writer",
        tools=[client.get_web_search_tool(search_context_size="high")],
    ) #Note - Tool response, and  Agent Response formating in between calls

    # Set the context mode to `last_agent` so that each agent only sees the output of the
    # previous agent instead of the full conversation history
    research_executor = AgentExecutor(research_agent, context_mode="last_agent")
    organization_executor = AgentExecutor(organization_agent, context_mode="last_agent")
    faq_executor = AgentExecutor(faq_agent, context_mode="last_agent")
# Note - Normal Executor
    workflow_agent = (
        WorkflowBuilder(
            start_executor=research_executor,
            # A single final snapshot keeps the Responses stream append-only.
            output_from=[faq_executor],
        )
        .add_edge(research_executor, organization_executor)
        .add_edge(organization_executor, faq_executor)
        .build()
        .as_agent()
    )

    server = ResponsesHostServer(workflow_agent)
    server.run()


if __name__ == "__main__":
    main()
