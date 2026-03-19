"""Agentic loop that drives the research digest pipeline via Claude tool-use.

Orchestrates paper fetching, scoring, citation enrichment, trend detection,
and digest generation through iterative Claude API calls.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any

import anthropic
import structlog
from sqlalchemy import select

from arxiv_digest.agent.prompts import SYSTEM_PROMPT
from arxiv_digest.agent.tools_def import TOOLS
from arxiv_digest.models import Paper
from arxiv_digest.schemas.topic import TopicSchema, load_topics
from arxiv_digest.tools.arxiv import fetch_arxiv_papers
from arxiv_digest.tools.digest_gen import generate_digest
from arxiv_digest.tools.history import compare_with_history
from arxiv_digest.tools.paper_details import fetch_paper_details
from arxiv_digest.tools.scorer import score_paper_impact
from arxiv_digest.tools.semantic_scholar import search_semantic_scholar

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

MODEL = "claude-opus-4-6"
MAX_TOKENS = 4096
MAX_ITERATIONS = 25


def _find_topic(topic_id: str) -> TopicSchema:
    """Resolve a topic_id to its TopicSchema from the YAML config."""
    topics = load_topics()
    for topic in topics:
        if topic.id == topic_id:
            return topic
    msg = f"Topic '{topic_id}' not found in topics.yaml."
    raise ValueError(msg)


def _paper_to_dict(paper: Paper) -> dict[str, object]:
    """Convert a Paper ORM instance to a plain dict for serialisation."""
    return {
        "arxiv_id": paper.arxiv_id,
        "title": paper.title,
        "authors": paper.authors,
        "abstract": paper.abstract,
        "published_date": paper.published_date.isoformat() if paper.published_date else None,
        "categories": paper.categories,
        "pdf_url": paper.pdf_url,
        "relevance_score": paper.relevance_score,
    }


async def _handle_fetch_arxiv(
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> object:
    topic = _find_topic(tool_input["topic_id"])
    days_back = tool_input.get("days_back", 3)
    papers = await fetch_arxiv_papers(topic, db, days_back=days_back)
    return [_paper_to_dict(p) for p in papers]


async def _handle_fetch_details(
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> object:
    return await fetch_paper_details(tool_input["arxiv_id"], db)


async def _handle_score(
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> object:
    stmt = select(Paper).where(Paper.arxiv_id == tool_input["arxiv_id"])
    result = await db.execute(stmt)
    paper = result.scalar_one_or_none()
    if paper is None:
        return {"error": f"Paper '{tool_input['arxiv_id']}' not found in database."}
    return score_paper_impact(paper)


async def _handle_semantic_scholar(
    tool_input: dict[str, Any],
    db: AsyncSession,  # noqa: ARG001
) -> object:
    return await search_semantic_scholar(tool_input["arxiv_id"])


async def _handle_compare_history(
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> object:
    lookback = tool_input.get("lookback_days", 30)
    return await compare_with_history(tool_input["topic_id"], db, lookback_days=lookback)


async def _handle_generate_digest(
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> object:
    return await generate_digest(
        topic_id=tool_input["topic_id"],
        papers=tool_input["papers"],
        format=tool_input["format"],
        db=db,
    )


_TOOL_HANDLERS: dict[
    str,
    Any,
] = {
    "fetch_arxiv_papers": _handle_fetch_arxiv,
    "fetch_paper_details": _handle_fetch_details,
    "score_paper_impact": _handle_score,
    "search_semantic_scholar": _handle_semantic_scholar,
    "compare_with_history": _handle_compare_history,
    "generate_digest": _handle_generate_digest,
}


async def _dispatch_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    db: AsyncSession,
) -> object:
    """Route a tool call to the corresponding implementation."""
    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        msg = f"Unknown tool: {tool_name}"
        raise ValueError(msg)
    return await handler(tool_input, db)


def _extract_text(response: anthropic.types.Message) -> str:
    """Extract concatenated text from a response's content blocks."""
    return "".join(block.text for block in response.content if block.type == "text")


async def _handle_tool_use(
    response: anthropic.types.Message,
    db: AsyncSession,
    messages: list[dict[str, Any]],
) -> int:
    """Process tool-use blocks, append results to messages, return call count."""
    messages.append({"role": "assistant", "content": response.content})
    tool_results: list[dict[str, Any]] = []
    call_count = 0

    for block in response.content:
        if block.type != "tool_use":
            continue

        call_count += 1
        tool_start = time.monotonic()

        logger.info(
            "agent.tool.call",
            tool=block.name,
            input_keys=list(block.input.keys()) if isinstance(block.input, dict) else [],
        )

        try:
            result = await _dispatch_tool(block.name, block.input, db)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, default=str),
            })
        except Exception as exc:
            logger.exception("agent.tool.error", tool=block.name, error=str(exc))
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps({"error": str(exc)}),
                "is_error": True,
            })

        logger.info(
            "agent.tool.done",
            tool=block.name,
            duration_s=round(time.monotonic() - tool_start, 2),
        )

    messages.append({"role": "user", "content": tool_results})
    return call_count


async def run_agent_loop(
    topic_id: str,
    digest_format: str,
    db: AsyncSession,
    *,
    days_back: int = 3,
) -> dict[str, object]:
    """Execute the full agentic research analysis loop.

    Args:
        topic_id: Research topic to analyse.
        digest_format: Output format (``newsletter``, ``technical``, ``executive``).
        db: Active async database session.
        days_back: How many days back to search for papers.

    Returns:
        Dict with ``content`` (final text), ``total_tool_calls``,
        ``duration_seconds``, and ``tokens_used``.
    """
    client = anthropic.AsyncAnthropic()
    start = time.monotonic()
    total_tool_calls = 0
    tokens_used: dict[str, int] = {"input": 0, "output": 0}
    final_text = ""

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                f"Analyse the recent papers for topic '{topic_id}' "
                f"(last {days_back} days) and generate a '{digest_format}' "
                f"format digest. Be thorough but opinionated — researchers "
                f"reading this digest want signal, not noise."
            ),
        },
    ]

    logger.info(
        "agent.loop.start",
        topic_id=topic_id,
        format=digest_format,
        days_back=days_back,
    )

    for iteration in range(MAX_ITERATIONS):
        try:
            response = await client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOLS,  # type: ignore[arg-type]
                messages=messages,
            )
        except anthropic.RateLimitError:
            logger.warning("agent.rate_limited", iteration=iteration)
            await asyncio.sleep(5)
            continue
        except anthropic.APITimeoutError:
            logger.exception("agent.timeout", iteration=iteration)
            break
        except anthropic.APIError:
            logger.exception("agent.api_error", iteration=iteration)
            break

        tokens_used["input"] += response.usage.input_tokens
        tokens_used["output"] += response.usage.output_tokens

        if response.stop_reason == "end_turn":
            final_text = _extract_text(response)
            logger.info(
                "agent.loop.complete",
                iterations=iteration + 1,
                tool_calls=total_tool_calls,
            )
            break

        if response.stop_reason == "tool_use":
            calls = await _handle_tool_use(response, db, messages)
            total_tool_calls += calls
            continue

        # Unexpected stop reason.
        logger.warning(
            "agent.unexpected_stop",
            stop_reason=response.stop_reason,
            iteration=iteration,
        )
        final_text = _extract_text(response)
        break
    else:
        logger.warning("agent.loop.max_iterations", max=MAX_ITERATIONS)
        final_text = "[Agent reached maximum iteration limit]"

    duration = round(time.monotonic() - start, 2)
    logger.info(
        "agent.loop.summary",
        duration_s=duration,
        tool_calls=total_tool_calls,
        tokens=tokens_used,
    )

    return {
        "content": final_text,
        "total_tool_calls": total_tool_calls,
        "duration_seconds": duration,
        "tokens_used": tokens_used,
    }
