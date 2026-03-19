"""Agentic loop for the ArXiv Research Digest.

Orchestrates the Claude model through a multi-step workflow of fetching,
analyzing, comparing, and summarizing ArXiv papers using tool calls.
"""

import json
import logging
from typing import Any

import anthropic

from agent.prompts import SYSTEM_PROMPT
from agent.tools_def import TOOLS
from tools.arxiv import fetch_arxiv_papers
from tools.comparator import compare_with_previous
from tools.digest import generate_digest, save_digest
from tools.extractor import extract_key_findings

logger = logging.getLogger(__name__)

TOOL_HANDLERS: dict[str, Any] = {
    "fetch_arxiv_papers": fetch_arxiv_papers,
    "extract_key_findings": extract_key_findings,
    "compare_with_previous": compare_with_previous,
    "generate_digest": generate_digest,
}


def _execute_tool(name: str, input_data: dict[str, Any]) -> str:
    """Execute a tool by name and return the JSON-serialized result.

    Args:
        name: Tool name matching a key in TOOL_HANDLERS.
        input_data: Keyword arguments to pass to the tool function.

    Returns:
        JSON string of the tool's return value, or an error message.
    """
    handler = TOOL_HANDLERS.get(name)
    if handler is None:
        logger.error("Unknown tool requested: %s", name)
        return json.dumps({"error": f"Unknown tool: {name}"})

    try:
        result = handler(**input_data)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:
        logger.exception("Tool '%s' raised an exception", name)
        return json.dumps({"error": f"Tool '{name}' failed: {exc}"})


def run(
    topic: str,
    days_back: int = 7,
    max_papers: int = 30,
    output_format: str = "newsletter",
    categories: list[str] | None = None,
) -> dict[str, Any]:
    """Run the agentic loop to produce a research digest.

    Sends a prompt to Claude and iteratively handles tool calls until
    the model produces a final end_turn response with the completed digest.

    Args:
        topic: Research topic to search for (e.g., "large language models").
        days_back: Number of days to look back for papers.
        max_papers: Maximum number of papers to fetch.
        output_format: Digest format — "newsletter", "technical", or "executive".
        categories: ArXiv category filters. Defaults to ["cs.AI", "cs.LG", "cs.CL"].

    Returns:
        Dictionary with keys: digest_path, final_report, papers_found, top_papers_count.
    """
    if categories is None:
        categories = ["cs.AI", "cs.LG", "cs.CL"]

    client = anthropic.Anthropic()

    user_message = (
        f"Produce a weekly ArXiv research digest on the topic: '{topic}'.\n\n"
        f"Parameters:\n"
        f"- Look back: {days_back} days\n"
        f"- Max papers to fetch: {max_papers}\n"
        f"- Categories: {', '.join(categories)}\n"
        f"- Output format: {output_format}\n\n"
        f"Follow your workflow: fetch papers, triage, extract key findings from "
        f"the most promising ones, compare with previous weeks, then generate "
        f"the final digest."
    )

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]

    logger.info("Starting agentic loop for topic '%s'", topic)

    digest_path: str = ""
    papers_found: int = 0
    top_papers_count: int = 0

    while True:
        response = client.messages.create(
            model="claude-opus-4-5-20250514",
            max_tokens=16384,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        logger.debug("Response stop_reason: %s", response.stop_reason)

        if response.stop_reason == "end_turn":
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            # Save the final digest if generate_digest was called
            if digest_path and final_text:
                try:
                    saved_path = save_digest(final_text, digest_path)
                    digest_path = saved_path
                except OSError:
                    logger.error("Failed to save final digest")

            logger.info(
                "Agentic loop complete — papers_found=%d, top_papers=%d",
                papers_found,
                top_papers_count,
            )

            return {
                "digest_path": digest_path,
                "final_report": final_text,
                "papers_found": papers_found,
                "top_papers_count": top_papers_count,
            }

        if response.stop_reason == "tool_use":
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results: list[dict[str, Any]] = []

            for block in assistant_content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input

                logger.info("Executing tool: %s", tool_name)
                result_str = _execute_tool(tool_name, tool_input)

                # Track key metrics from tool results
                try:
                    result_data = json.loads(result_str)
                    if tool_name == "fetch_arxiv_papers":
                        papers_found = result_data.get("total_found", 0)
                    elif tool_name == "generate_digest":
                        digest_path = result_data.get("output_path", "")
                        top_papers_count = len(result_data.get("top_papers", []))
                except json.JSONDecodeError:
                    pass

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    }
                )

            messages.append({"role": "user", "content": tool_results})
        else:
            logger.warning("Unexpected stop_reason: %s", response.stop_reason)
            break

    return {
        "digest_path": digest_path,
        "final_report": "",
        "papers_found": papers_found,
        "top_papers_count": top_papers_count,
    }
