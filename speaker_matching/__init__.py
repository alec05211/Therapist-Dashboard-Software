"""Provider-independent, conservative speaker matching."""

from collections import defaultdict
from math import isfinite, sqrt
from statistics import median


def _unit(vector):
    values = tuple(float(value) for value in vector)
    length = sqrt(sum(value * value for value in values))
    if not isfinite(length) or not length:
        raise ValueError("Invalid speaker embedding")
    return tuple(value / length for value in values)


def suggest_assignments(clips, references, *, threshold, margin, minimum_clips=3):
    """Score (source label, embedding) pairs against eligible profile embeddings."""
    if minimum_clips < 2 or not -1 <= threshold <= 1 or not 0 < margin <= 2:
        raise ValueError("Invalid speaker matching configuration")
    profiles = {key: _unit(vector) for key, vector in references.items()}
    votes = defaultdict(list)
    for label, embedding in clips:
        sample = _unit(embedding)
        scores = []
        for profile_id, reference in profiles.items():
            if len(sample) != len(reference):
                raise ValueError('Speaker embedding dimensions do not match')
            score = sum(a * b for a, b in zip(sample, reference))
            scores.append((profile_id, score))
        scores.sort(key=lambda item: item[1], reverse=True)
        if not scores:
            continue
        profile_id, score = scores[0]
        separated = len(scores) == 1 or score - scores[1][1] >= margin
        votes[label].append((profile_id, score) if score >= threshold and separated else None)

    assignments = {}
    for label, results in votes.items():
        matches = [result for result in results if result is not None]
        candidates = {profile_id for profile_id, _ in matches}
        if len(matches) >= minimum_clips and len(matches) > len(results) / 2 and len(candidates) == 1:
            assignments[label] = {
                "profile_id": next(iter(candidates)),
                "score": median(score for _, score in matches),
            }
    return assignments

