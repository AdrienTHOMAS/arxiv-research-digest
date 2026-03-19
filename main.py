"""CLI entry point for the ArXiv Research Digest.

Provides a rich command-line interface with progress display,
summary tables, and digest preview after completion.
"""

import argparse
import logging
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent.loop import run

load_dotenv()

console = Console()
logger = logging.getLogger("arxiv_digest")


def main() -> None:
    """Parse CLI arguments and run the research digest agent."""
    parser = argparse.ArgumentParser(
        description="Claude ArXiv Research Digest — AI-powered weekly paper summaries",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "topic",
        type=str,
        help="Research topic to search for (e.g., 'large language models')",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=30,
        help="Maximum papers to fetch (default: 30)",
    )
    parser.add_argument(
        "--format",
        choices=["newsletter", "technical", "executive"],
        default="newsletter",
        help="Output format (default: newsletter)",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        default=["cs.AI", "cs.LG", "cs.CL"],
        help="ArXiv categories to filter (default: cs.AI cs.LG cs.CL)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Custom output file path (optional)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging output",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    console.print(
        Panel(
            f"[bold blue]ArXiv Research Digest[/bold blue]\n"
            f"Topic: [green]{args.topic}[/green] | "
            f"Days: {args.days} | "
            f"Max papers: {args.max_papers} | "
            f"Format: {args.format}",
            title="🤖 Claude ArXiv Digest",
            border_style="blue",
        )
    )

    with console.status("[bold green]Running research digest agent...", spinner="dots"):
        try:
            result = run(
                topic=args.topic,
                days_back=args.days,
                max_papers=args.max_papers,
                output_format=args.format,
                categories=args.categories,
            )
        except Exception as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            logger.exception("Agent loop failed")
            sys.exit(1)

    # Summary table
    table = Table(title="Digest Summary", border_style="blue")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Papers Found", str(result["papers_found"]))
    table.add_row("Top Papers", str(result["top_papers_count"]))
    table.add_row("Output Path", result["digest_path"] or "N/A")
    console.print(table)

    # Preview
    if result["final_report"]:
        preview = result["final_report"][:1500]
        if len(result["final_report"]) > 1500:
            preview += "\n\n... [truncated — see full digest at output path]"
        console.print(
            Panel(
                preview,
                title="📄 Digest Preview",
                border_style="green",
            )
        )

    console.print("[bold green]Done![/bold green]")


if __name__ == "__main__":
    main()
