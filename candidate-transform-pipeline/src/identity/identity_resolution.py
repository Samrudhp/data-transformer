"""
IdentityResolutionService — determines whether normalized fragments from
different sources refer to the same real-world candidate.

Algorithm
---------
1. Blocking  — group fragments by exact email or phone to cut comparison space.
2. Similarity — compare name / email / phone / github with RapidFuzz.
3. Weighted matching — combine similarities with configurable field weights.
4. Threshold — fragments whose combined score ≥ threshold are merged into
               one cluster; the rest remain as separate candidates.

Default weights: email=0.45, phone=0.30, name=0.20, github=0.05
Default threshold: 0.80
"""

from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz

from src.models.candidate_fragment import CandidateFragment
from src.models.processing_context import ProcessingContext
from src.pipeline.stage import Stage
from src.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

_DEFAULT_WEIGHTS: Dict[str, float] = {
    "email": 0.45,
    "phone": 0.30,
    "full_name": 0.20,
    "github": 0.05,
}
_DEFAULT_THRESHOLD: float = 0.80


class IdentityResolutionService(Stage):
    """
    Pipeline stage that clusters normalized fragments belonging to the
    same candidate using blocking + weighted fuzzy similarity.

    Results are stored in ``context.identity_resolution_result`` as:
    {
        "clusters": [
            {
                "cluster_id": "cluster_0",
                "sources": ["csv", "ats"],
                "fragment_indices": [0, 1],
                "score": 0.92,
            },
            ...
        ]
    }
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        threshold: Optional[float] = None,
    ) -> None:
        """
        Args:
            weights: Per-field similarity weights. Defaults to
                     ``_DEFAULT_WEIGHTS``.
            threshold: Minimum combined score to merge two fragments.
                       Defaults to 0.80.
        """
        self.weights: Dict[str, float] = weights or _DEFAULT_WEIGHTS
        self.threshold: float = threshold if threshold is not None else _DEFAULT_THRESHOLD

    # ------------------------------------------------------------------
    # Stage entry point
    # ------------------------------------------------------------------

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Run identity resolution against normalized fragments.

        Args:
            context: Shared pipeline context with ``normalized_fragments``.

        Returns:
            Updated context with ``identity_resolution_result`` set.
        """
        fragments = context.normalized_fragments
        logger.info(
            "IdentityResolutionService: resolving %d fragment(s) (threshold=%.2f).",
            len(fragments),
            self.threshold,
        )
        result = self.resolve(fragments)
        context.identity_resolution_result = result
        logger.info(
            "IdentityResolutionService: produced %d cluster(s).",
            len(result.get("clusters", [])),
        )
        return context

    # ------------------------------------------------------------------
    # Core resolution logic
    # ------------------------------------------------------------------

    def resolve(self, fragments: List[CandidateFragment]) -> Dict[str, Any]:
        """
        Cluster a list of normalized fragments into identity groups.

        Args:
            fragments: Normalized candidate fragments.

        Returns:
            Resolution result dict containing a ``"clusters"`` list.
        """
        if not fragments:
            return {"clusters": [], "total_fragments": 0}

        n = len(fragments)
        # Union-Find for clustering.
        parent = list(range(n))
        scores: Dict[Tuple[int, int], float] = {}

        def _find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def _union(a: int, b: int) -> None:
            ra, rb = _find(a), _find(b)
            if ra != rb:
                parent[rb] = ra

        # --- Step 1: Blocking buckets (exact email / phone match) ---
        email_buckets: Dict[str, List[int]] = {}
        phone_buckets: Dict[str, List[int]] = {}
        for i, frag in enumerate(fragments):
            email = frag.extracted_fields.get("email")
            phone = frag.extracted_fields.get("phone")
            if email:
                email_buckets.setdefault(str(email).lower(), []).append(i)
            if phone:
                phone_buckets.setdefault(str(phone), []).append(i)

        candidate_pairs: set = set()
        for bucket in list(email_buckets.values()) + list(phone_buckets.values()):
            for i in range(len(bucket)):
                for j in range(i + 1, len(bucket)):
                    a, b = bucket[i], bucket[j]
                    candidate_pairs.add((min(a, b), max(a, b)))

        # Also check all pairs when there are few fragments (no bucket hit).
        if len(fragments) <= 10:
            for i in range(n):
                for j in range(i + 1, n):
                    candidate_pairs.add((i, j))

        # --- Step 2 & 3: Similarity + weighted matching ---
        for i, j in candidate_pairs:
            score = self._combined_score(fragments[i], fragments[j])
            scores[(i, j)] = score
            if score >= self.threshold:
                _union(i, j)

        # --- Build cluster objects ---
        cluster_map: Dict[int, List[int]] = {}
        for idx in range(n):
            root = _find(idx)
            cluster_map.setdefault(root, []).append(idx)

        clusters = []
        for cluster_id, (root, members) in enumerate(cluster_map.items()):
            # Average pairwise score for cluster quality metric.
            pair_scores = [
                scores.get((min(a, b), max(a, b)), 0.0)
                for a in members
                for b in members
                if a < b
            ]
            avg_score = sum(pair_scores) / len(pair_scores) if pair_scores else 1.0
            clusters.append(
                {
                    "cluster_id": f"cluster_{cluster_id}",
                    "sources": [fragments[m].source for m in members],
                    "fragment_indices": members,
                    "score": round(avg_score, 4),
                }
            )

        return {
            "clusters": clusters,
            "total_fragments": n,
            "threshold": self.threshold,
            "weights": self.weights,
        }

    # ------------------------------------------------------------------
    # Similarity helpers
    # ------------------------------------------------------------------

    def _combined_score(
        self,
        a: CandidateFragment,
        b: CandidateFragment,
    ) -> float:
        """
        Compute the weighted similarity score between two fragments.

        Uses token_set_ratio for names (handles word re-ordering),
        ratio for emails/phones/github.
        """
        fa = a.extracted_fields
        fb = b.extracted_fields
        total_weight = 0.0
        weighted_sum = 0.0

        def _ratio(x: Any, y: Any, use_token_set: bool = False) -> float:
            if not x or not y:
                return 0.0
            sx, sy = str(x).lower().strip(), str(y).lower().strip()
            if use_token_set:
                return fuzz.token_set_ratio(sx, sy) / 100.0
            return fuzz.ratio(sx, sy) / 100.0

        for field, weight in self.weights.items():
            val_a = fa.get(field)
            val_b = fb.get(field)
            if val_a is None and val_b is None:
                # Both absent: skip field (do not penalise).
                continue
            use_token = field in ("full_name",)
            sim = _ratio(val_a, val_b, use_token_set=use_token)
            weighted_sum += sim * weight
            total_weight += weight

        if total_weight == 0.0:
            return 0.0
        return weighted_sum / total_weight
