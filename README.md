# 🤖 Claude ArXiv Research Digest

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)
![License MIT](https://img.shields.io/badge/License-MIT-green)
![ArXiv API](https://img.shields.io/badge/ArXiv-API-red)

**An AI-powered agentic system that fetches, analyzes, and summarizes the most impactful ArXiv papers each week.**

## Features

- **Smart Prioritization** — Claude scores papers on novelty, impact, methodology, and reproducibility, surfacing only what matters.
- **Trend Detection** — Compares weekly digests to identify emerging research directions and recurring themes.
- **Multiple Formats** — Choose from newsletter (accessible), technical (detailed), or executive (concise) output styles.
- **Weekly Scheduler** — Set-and-forget cron scheduling delivers digests to your output directory every Monday.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    main.py (CLI)                     │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│              agent/loop.py (Agentic Loop)            │
│                                                      │
│   User Prompt ──► Claude claude-opus-4-5 ──► Tool Calls ──► Results   │
│                      │           ▲                    │
│                      ▼           │                    │
│                 [Iterate until end_turn]              │
└──────┬──────────┬──────────┬──────────┬─────────────┘
       │          │          │          │
       ▼          ▼          ▼          ▼
┌──────────┐┌──────────┐┌──────────┐┌──────────┐
│  fetch   ││ extract  ││ compare  ││ generate │
│  arxiv   ││   key    ││   with   ││  digest  │
│  papers  ││ findings ││ previous ││          │
└──────────┘└──────────┘└──────────┘└──────────┘
  tools/       tools/      tools/      tools/
  arxiv.py   extractor.py comparator.py digest.py
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY=your_key_here

# Run a digest
python main.py "large language models" --days 7 --format newsletter
```

## Usage

```bash
# Basic usage
python main.py "reinforcement learning"

# Custom date range and paper limit
python main.py "diffusion models" --days 14 --max-papers 50

# Technical format with specific categories
python main.py "graph neural networks" --format technical --categories cs.LG cs.AI

# Executive summary
python main.py "AI safety" --format executive --days 3

# Scheduled weekly runs
python scheduler.py --topics "large language models" "AI safety" --run-now

# Schedule only (runs every Monday at 08:00 UTC)
python scheduler.py --topics "transformer architectures" "multimodal learning"
```

## Example Output

```markdown
# 🤖 AI Research Digest — Large Language Models

**Week 2025-W03** | 27 papers reviewed | Generated 2025-01-20

## 📊 This Week at a Glance
- **Papers Reviewed:** 27
- **Top Impact Score:** 9/10
- **Key Themes:** Reasoning chains, Efficient fine-tuning, Multilingual alignment

## 🔥 Top Papers This Week

### 1. Constitutional Reasoning: Teaching LLMs to Self-Correct via Structured Debate
**Authors:** Chen, W., Park, J., Liu, M., et al.
**Published:** 2025-01-18 | **Impact:** 🔴 9/10
**ArXiv:** [2501.10234](https://arxiv.org/abs/2501.10234)

Introduces a framework where multiple LLM instances debate each
other's reasoning steps before converging on an answer...

> **Why it matters:** This could fundamentally change how we approach
> LLM reliability — instead of training away mistakes, let models
> catch each other's errors in real time.
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Model | Claude claude-opus-4-5 (Anthropic) |
| Paper Source | ArXiv API |
| Feed Parsing | feedparser |
| CLI Interface | argparse + Rich |
| Templating | Jinja2 |
| Scheduling | schedule |
| HTTP Client | requests |

## Project Structure

```
arxiv-research-digest/
├── agent/
│   ├── __init__.py          # Module exports
│   ├── loop.py              # Agentic loop orchestration
│   ├── prompts.py           # System prompt
│   └── tools_def.py         # Tool definitions (Anthropic format)
├── tools/
│   ├── __init__.py          # Tool exports
│   ├── arxiv.py             # ArXiv API integration
│   ├── extractor.py         # Paper analysis scaffold
│   ├── comparator.py        # Week-over-week comparison
│   └── digest.py            # Digest generation & saving
├── templates/
│   └── digest.md.j2         # Jinja2 digest template
├── data/previous/           # Historical digest data
├── output/digests/          # Generated digests
├── main.py                  # CLI entry point
├── scheduler.py             # Weekly cron scheduler
├── requirements.txt         # Python dependencies
└── README.md
```

## License

MIT License — see [LICENSE](LICENSE) for details.

---

*Built with [Claude claude-opus-4-5](https://www.anthropic.com/claude) by Anthropic*
