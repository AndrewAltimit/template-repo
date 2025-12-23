"""
Semantic Search Engine for Reaction Images

Uses sentence-transformers for embedding-based similarity search.
Embeddings are computed lazily on first query.
"""

from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Model configuration
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L12-v2"

# Base URL for reaction images
REACTION_BASE_URL = "https://raw.githubusercontent.com/AndrewAltimit/Media/refs/heads/main/reaction"


@dataclass
class ReactionResult:
    """A reaction search result."""

    id: str
    url: str
    markdown: str
    description: str
    similarity: float
    tags: List[str]
    usage_scenarios: List[str]
    character_appearance: str


class ReactionSearchEngine:
    """
    Semantic search engine for reaction images.

    Uses sentence-transformers to compute embeddings and cosine similarity
    for natural language search over reaction metadata.

    Attributes:
        model_name: HuggingFace model identifier
        reactions: List of reaction dictionaries
        embeddings: Numpy array of reaction embeddings
        initialized: Whether the engine has been initialized
    """

    def __init__(self, model_name: str = DEFAULT_MODEL):
        """
        Initialize the search engine.

        Args:
            model_name: HuggingFace model identifier for embeddings
        """
        self.model_name = model_name
        self._model = None
        self._reactions: List[Dict[str, Any]] = []
        self._embeddings: Optional[np.ndarray] = None
        self._id_to_index: Dict[str, int] = {}
        self._all_tags: Dict[str, int] = {}  # tag -> count
        self._initialized = False

    @property
    def initialized(self) -> bool:
        """Check if the engine is initialized."""
        return self._initialized

    @property
    def reaction_count(self) -> int:
        """Number of indexed reactions."""
        return len(self._reactions)

    def _get_model(self):
        """Lazy-load the sentence transformer model."""
        if self._model is None:
            logger.info("Loading sentence-transformers model: %s", self.model_name)
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
                logger.info("Model loaded successfully")
            except ImportError as e:
                logger.error("sentence-transformers not installed: %s", e)
                raise RuntimeError("sentence-transformers is required. Install with: pip install sentence-transformers") from e
        return self._model

    def _build_searchable_text(self, reaction: Dict[str, Any]) -> str:
        """
        Build a searchable text representation of a reaction.

        Combines description, usage scenarios, tags, and character appearance
        into a single text for embedding.

        Args:
            reaction: Reaction dictionary

        Returns:
            Combined searchable text
        """
        parts = []

        # Primary description
        if desc := reaction.get("description"):
            parts.append(desc)

        # Usage scenarios (very important for context matching)
        scenarios = reaction.get("usage_scenarios", [])
        if scenarios:
            parts.append(" ".join(scenarios))

        # Tags
        tags = reaction.get("tags", [])
        if tags:
            parts.append(" ".join(tags))

        # Character appearance (can help with visual queries)
        if appearance := reaction.get("character_appearance"):
            parts.append(appearance)

        return " ".join(parts)

    def initialize(self, reactions: List[Dict[str, Any]]) -> None:
        """
        Initialize the search engine with reaction data.

        Computes embeddings for all reactions.

        Args:
            reactions: List of reaction dictionaries from config
        """
        if not reactions:
            raise ValueError("No reactions provided")

        logger.info("Initializing search engine with %d reactions", len(reactions))

        self._reactions = reactions

        # Build ID index and tag counts
        self._id_to_index = {}
        self._all_tags = {}
        for i, reaction in enumerate(reactions):
            reaction_id = reaction.get("id", f"reaction_{i}")
            self._id_to_index[reaction_id] = i

            for tag in reaction.get("tags", []):
                self._all_tags[tag] = self._all_tags.get(tag, 0) + 1

        # Build searchable texts
        texts = [self._build_searchable_text(r) for r in reactions]

        # Compute embeddings
        model = self._get_model()
        logger.info("Computing embeddings for %d reactions...", len(texts))
        self._embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        logger.info("Embeddings computed: shape %s", self._embeddings.shape)

        self._initialized = True

    def _cosine_similarity(self, query_embedding: np.ndarray) -> np.ndarray:
        """
        Compute cosine similarity between query and all reactions.

        Args:
            query_embedding: Query embedding vector

        Returns:
            Array of similarity scores
        """
        # Normalize vectors
        query_norm = query_embedding / (np.linalg.norm(query_embedding) + 1e-8)
        embeddings_norm = self._embeddings / (np.linalg.norm(self._embeddings, axis=1, keepdims=True) + 1e-8)

        # Compute cosine similarity
        return np.dot(embeddings_norm, query_norm)

    def _reaction_to_result(self, reaction: Dict[str, Any], similarity: float) -> ReactionResult:
        """Convert a reaction dict to a ReactionResult."""
        reaction_id = reaction.get("id", "unknown")

        # Use source_url if available, otherwise construct from base URL
        url = reaction.get("source_url", "")
        if not url:
            # Try to construct from id (fallback)
            # This assumes filename matches id, which may not always be true
            url = f"{REACTION_BASE_URL}/{reaction_id}.webp"

        return ReactionResult(
            id=reaction_id,
            url=url,
            markdown=f"![Reaction]({url})",
            description=reaction.get("description", ""),
            similarity=round(similarity, 4),
            tags=reaction.get("tags", []),
            usage_scenarios=reaction.get("usage_scenarios", []),
            character_appearance=reaction.get("character_appearance", ""),
        )

    def search(
        self,
        query: str,
        limit: int = 5,
        tags: Optional[List[str]] = None,
        min_similarity: float = 0.0,
    ) -> List[ReactionResult]:
        """
        Search for reactions matching a natural language query.

        Args:
            query: Natural language search query
            limit: Maximum number of results
            tags: Optional tag filter (reactions must have at least one of these tags)
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of ReactionResult objects sorted by similarity

        Raises:
            RuntimeError: If the engine is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Search engine not initialized. Call initialize() first.")

        # Compute query embedding
        model = self._get_model()
        query_embedding = model.encode([query], convert_to_numpy=True)[0]

        # Compute similarities
        similarities = self._cosine_similarity(query_embedding)

        # Build results with filtering
        results = []
        for i, (reaction, similarity) in enumerate(zip(self._reactions, similarities)):
            # Apply minimum similarity threshold
            if similarity < min_similarity:
                continue

            # Apply tag filter
            if tags:
                reaction_tags = set(reaction.get("tags", []))
                if not reaction_tags.intersection(tags):
                    continue

            results.append((reaction, float(similarity)))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)

        # Convert to ReactionResult objects
        return [self._reaction_to_result(reaction, similarity) for reaction, similarity in results[:limit]]

    def get_by_id(self, reaction_id: str) -> Optional[ReactionResult]:
        """
        Get a specific reaction by ID.

        Args:
            reaction_id: Reaction identifier

        Returns:
            ReactionResult or None if not found
        """
        if not self._initialized:
            raise RuntimeError("Search engine not initialized. Call initialize() first.")

        index = self._id_to_index.get(reaction_id)
        if index is None:
            return None

        reaction = self._reactions[index]
        return self._reaction_to_result(reaction, 1.0)

    def list_tags(self) -> Dict[str, int]:
        """
        Get all available tags with their counts.

        Returns:
            Dict mapping tag name to occurrence count
        """
        if not self._initialized:
            raise RuntimeError("Search engine not initialized. Call initialize() first.")

        return dict(sorted(self._all_tags.items(), key=lambda x: (-x[1], x[0])))

    def list_all_reactions(self) -> List[ReactionResult]:
        """
        Get all reactions.

        Returns:
            List of all ReactionResult objects
        """
        if not self._initialized:
            raise RuntimeError("Search engine not initialized. Call initialize() first.")

        return [self._reaction_to_result(r, 1.0) for r in self._reactions]

    def get_status(self) -> Dict[str, Any]:
        """
        Get engine status information.

        Returns:
            Dict with status information
        """
        return {
            "initialized": self._initialized,
            "model_name": self.model_name,
            "reaction_count": len(self._reactions),
            "unique_tags": len(self._all_tags),
            "embeddings_shape": (list(self._embeddings.shape) if self._embeddings is not None else None),
        }
