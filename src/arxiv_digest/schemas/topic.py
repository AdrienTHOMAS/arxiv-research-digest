"""Topic schema and configuration loader.

Reads research topic definitions from a YAML file and returns validated
Pydantic models.
"""

from pathlib import Path

import structlog
import yaml
from pydantic import BaseModel, Field

from arxiv_digest.config import get_settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class TopicSchema(BaseModel):
    """A research topic definition loaded from ``config/topics.yaml``.

    Attributes:
        id: Unique topic identifier (e.g. ``machine_learning``).
        name: Human-readable topic name.
        description: Detailed description of the topic scope.
        arxiv_categories: ArXiv category codes to query.
        keywords: Keywords used for relevance matching.
        max_papers: Maximum papers to include per digest run.
    """

    id: str = Field(description="Unique topic identifier.")
    name: str = Field(description="Human-readable topic name.")
    description: str = Field(description="Detailed topic description.")
    arxiv_categories: list[str] = Field(description="ArXiv category codes to query.")
    keywords: list[str] = Field(description="Keywords for relevance matching.")
    max_papers: int = Field(ge=1, description="Maximum papers per digest run.")


def load_topics(path: Path | None = None) -> list[TopicSchema]:
    """Load and validate research topics from the YAML configuration file.

    Args:
        path: Optional override for the YAML file path.  When ``None`` the
            path is read from application settings.

    Returns:
        A list of validated :class:`TopicSchema` instances.

    Raises:
        FileNotFoundError: If the topics file does not exist.
        yaml.YAMLError: If the YAML file cannot be parsed.
        pydantic.ValidationError: If topic data fails schema validation.
    """
    file_path = path or get_settings().TOPICS_FILE

    logger.info("topics.loading", path=str(file_path))

    raw_text = Path(file_path).read_text(encoding="utf-8")
    data: dict[str, list[dict[str, object]]] = yaml.safe_load(raw_text)

    topics = [TopicSchema.model_validate(t) for t in data["topics"]]

    logger.info("topics.loaded", count=len(topics))

    return topics
