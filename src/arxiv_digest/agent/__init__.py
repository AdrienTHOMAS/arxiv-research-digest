"""Agentic research analysis loop powered by Claude.

Provides the core agent loop that orchestrates ArXiv paper discovery,
scoring, citation enrichment, and digest generation through Claude's
tool-use capabilities.
"""

from arxiv_digest.agent.loop import run_agent_loop

__all__ = ["run_agent_loop"]
