"""Claude ArXiv Research Digest - Agent Module.

Exports the main run function that orchestrates the agentic loop
for fetching, analyzing, and summarizing ArXiv papers.
"""

from agent.loop import run

__all__ = ["run"]
