# ArXiv Research Digest

[![CI](https://github.com/AdrienTHOMAS/arxiv-research-digest/actions/workflows/ci.yml/badge.svg)](https://github.com/AdrienTHOMAS/arxiv-research-digest/actions/workflows/ci.yml)
[![Docker](https://github.com/AdrienTHOMAS/arxiv-research-digest/actions/workflows/docker.yml/badge.svg)](https://github.com/AdrienTHOMAS/arxiv-research-digest/pkgs/container/arxiv-research-digest)
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Agentic ArXiv research monitor powered by Claude — automatically fetches, scores, and summarizes the latest papers for your topics.

## Architecture

```
                          ArXiv Research Digest

  topics.yaml ──► Scheduler ──► ArXiv API ──► Scorer (Claude) ──► PostgreSQL
                    (cron)        fetch          agent loop          store
                                                    │
                                                    ▼
                                              ┌─────────────┐
                                              │  Database    │
                                              └──┬──────┬───┘
                                                 │      │
                                            ┌────▼──┐ ┌─▼──────────┐
                                            │ REST  │ │  Web UI    │
                                            │ API   │ │  Dashboard │
                                            └───┬───┘ └────────────┘
                                                │
                                           ┌────▼──────┐
                                           │ Webhooks  │
                                           │ Slack /   │
                                           │ Discord   │
                                           └───────────┘
```

## Quick Start

```bash
# Clone the repository
git clone https://github.com/AdrienTHOMAS/arxiv-research-digest.git
cd arxiv-research-digest

# Copy environment config
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY, API_KEY, and webhook URLs

# Start with Docker Compose
docker compose up -d
```

The dashboard is available at `http://localhost:8000` and the API at `http://localhost:8000/api/v1`.

## Configuration

### Topics (config/topics.yaml)

```yaml
topics:
  - id: machine_learning
    name: Machine Learning
    description: Core ML research
    arxiv_categories:
      - cs.LG
      - stat.ML
    keywords:
      - deep learning
      - neural network
    max_papers: 25
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://arxiv:arxiv@localhost:5432/arxiv_digest` |
| `API_KEY` | API key for protected endpoints | (required) |
| `ANTHROPIC_API_KEY` | Claude API key for the agent | (required) |
| `WEBHOOK_URLS` | Comma-separated webhook URLs | `[]` |
| `TOPICS_FILE` | Path to topics YAML | `config/topics.yaml` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `CORS_ORIGINS` | Allowed CORS origins | `["*"]` |
| `CACHE_DIR` | Cache directory path | `.cache` |

## API Reference

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

```json
{"status": "healthy", "version": "1.0.0", "database": "connected"}
```

### List Papers

```bash
# All papers
curl http://localhost:8000/api/v1/papers

# Filter by topic and minimum score
curl "http://localhost:8000/api/v1/papers?topic_id=machine_learning&min_score=0.7&page=1&page_size=20"
```

### List Digests

```bash
# All digests
curl http://localhost:8000/api/v1/digests

# Filter by topic and status
curl "http://localhost:8000/api/v1/digests?topic_id=nlp&status=complete"
```

### Create a Digest

```bash
curl -X POST http://localhost:8000/api/v1/digests \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"topic_id": "machine_learning", "run_date": "2024-01-15"}'
```

### Get Topics

```bash
curl http://localhost:8000/api/v1/topics
```

## Web UI

The dashboard provides a dark-mode interface at the root URL (`/`):

- **Home** — Latest digests per topic as cards
- **Papers** — Filterable, sortable table of all scored papers
- **Digest detail** — Rendered markdown summary with paper list

<!-- Screenshots placeholder -->

## CLI Usage

Run a standalone digest without starting the server:

```bash
# Basic usage
python scripts/run_digest.py --topic machine_learning --days 7

# With format and output file
python scripts/run_digest.py --topic 'NLP' --days 3 --format technical --output digest.md

# Executive summary to stdout
python scripts/run_digest.py --topic reinforcement_learning --format executive
```

## Project Structure

```
arxiv-research-digest/
├── src/arxiv_digest/
│   ├── main.py                 # FastAPI app factory
│   ├── config.py               # Pydantic settings
│   ├── database.py             # SQLAlchemy async engine
│   ├── agent/                  # Claude agent loop & tools
│   │   ├── loop.py             # Main agent loop
│   │   ├── prompts.py          # System prompts
│   │   └── tools_def.py        # Tool definitions
│   ├── api/v1/                 # REST API endpoints
│   │   ├── health.py
│   │   ├── topics.py
│   │   ├── digests.py
│   │   └── papers.py
│   ├── models/                 # SQLAlchemy ORM models
│   ├── schemas/                # Pydantic v2 schemas
│   ├── services/               # Business logic
│   │   ├── digest_service.py
│   │   ├── webhook_service.py
│   │   └── cache_service.py
│   ├── tools/                  # Agent tool implementations
│   ├── scheduler/              # APScheduler jobs
│   ├── templates/              # Digest Jinja2 templates
│   └── ui/                     # Web dashboard
│       ├── templates/          # HTML templates
│       └── static/             # CSS + JS
├── config/
│   ├── topics.yaml
│   └── schedule.yaml
├── scripts/
│   └── run_digest.py           # CLI entry point
├── tests/
├── migrations/                 # Alembic migrations
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Development

```bash
# Install dependencies
pip install -r requirements-dev.txt
pip install -e .

# Run linter
ruff check src/ tests/

# Run type checker
mypy --strict src/

# Run tests with coverage
pytest --cov=arxiv_digest --cov-fail-under=60

# Start dev server
uvicorn arxiv_digest.main:create_app --factory --reload
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Write tests for your changes
4. Ensure `ruff check` and `mypy --strict` pass
5. Run the full test suite
6. Submit a pull request

## License

MIT
