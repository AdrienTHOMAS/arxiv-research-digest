"""Claude ArXiv Research Digest - Tools Module.

Provides tool implementations for ArXiv paper fetching, key findings
extraction, historical comparison, and digest generation.
"""

from tools.arxiv import fetch_arxiv_papers
from tools.extractor import extract_key_findings
from tools.comparator import compare_with_previous
from tools.digest import generate_digest

__all__ = [
    "fetch_arxiv_papers",
    "extract_key_findings",
    "compare_with_previous",
    "generate_digest",
]
