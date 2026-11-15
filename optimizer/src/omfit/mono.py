"""Deterministic native MONO filter enumeration followed by measured tone fitting.

Filter indices are categorical native states. They are never differentiated,
regularized, or treated as distances. The caller supplies a MonoLayout evaluator;
this module neither renders nor implements an approximate monochrome transform.
"""

import numpy as np

from .core import BudgetExhausted, SearchResult, search as continuous_search


FILTER_STATES = 25


def regularizer(n_images, initial, tone_l2=0.01, nuisance_l2=0.01, contrast_l2=0.01):
    """Neutral style and initial-scene priors, without an ordinal filter prior."""
    initial = np.asarray(initial)
    if n_images < 1 or len(initial) != 4 + 4 * n_images:
        raise ValueError(
            "MONO regularizer requires four shared and four scene controls/photo"
        )
    if any(not np.isfinite(v) or v < 0 for v in (tone_l2, nuisance_l2, contrast_l2)):
        raise ValueError("MONO regularization weights must be finite and nonnegative")
    rows, targets = [], []
    for j, weight in ((1, contrast_l2), (2, tone_l2 / 2), (3, tone_l2 / 2)):
        row = np.zeros(len(initial))
        row[j] = np.sqrt(weight)
        rows.append(row)
        targets.append(0.0)
    for i in range(n_images):
        for k, scale in enumerate((5.0, 1.0, 1.0, 1.0)):
            j = 4 + 4 * i + k
            row = np.zeros(len(initial))
            row[j] = np.sqrt(nuisance_l2 / (4 * n_images)) / scale
            rows.append(row)
            targets.append(row[j] * initial[j])
    return np.asarray(rows), np.asarray(targets)


def candidate_key(objective, vector):
    """Prefer simpler continuous controls, then the canonical filter ordering."""
    continuous = vector[1:]
    return (
        round(float(objective), 12),
        int(np.dot(continuous, continuous)),
        tuple(map(int, continuous)),
        int(vector[0]),
    )


def search(
    initial,
    lower,
    upper,
    trust,
    data_residual,
    penalty_matrix,
    penalty_target,
    *,
    max_iterations=3,
    min_improvement=1e-4,
    coordinate_trials=4,
    event=lambda _: None,
    prefetch=lambda _: None,
    inspect_jacobian=lambda vector, matrix: None,
):
    """Score all 25 native filters at neutral tones, then lock the best filter.

    Scene WB/exposure starts at the supplied anchor for enumeration. It remains
    frozen during tone fitting if lower/upper scene bounds are equal. All stages
    share the caller's evaluator/request budget; cache hits do not grant an
    additional budget. Only fully measured settings can be returned. This is a
    deterministic staged search, not a global filter/tone optimum.
    """
    x = np.asarray(initial, dtype=np.int64).copy()
    lower, upper, trust = (np.asarray(v).copy() for v in (lower, upper, trust))
    R = np.asarray(penalty_matrix, dtype=float)
    z = np.asarray(penalty_target, dtype=float)
    if len(x) < 8 or (len(x) - 4) % 4:
        raise ValueError(
            "MONO vector requires four shared and four scene controls/photo"
        )
    if any(v.shape != x.shape for v in (lower, upper, trust)):
        raise ValueError("MONO bounds/trust shape mismatch")
    if lower[0] != 0 or upper[0] != FILTER_STATES - 1:
        raise ValueError("MONO search enumerates all 25 canonical filter states")
    if R.ndim != 2 or R.shape[1] != len(x) or z.shape != (R.shape[0],):
        raise ValueError("MONO penalty dimensions mismatch")
    if np.any(R[:, 0] != 0):
        raise ValueError("Categorical MONO filters cannot have numeric penalties")
    if np.any(lower > upper):
        raise ValueError("MONO lower bounds exceed upper bounds")
    cache = {}
    best_x = None
    best_f = float("inf")
    history = []

    def evaluate(v):
        nonlocal best_x, best_f
        key = tuple(map(int, v))
        if key not in cache:
            residual = np.asarray(data_residual(v), dtype=float)
            if not np.isfinite(residual).all():
                raise ValueError("non-finite data residual")
            penalty = R @ v - z
            objective = float(residual @ residual + penalty @ penalty)
            cache[key] = residual, objective
            if best_x is None or candidate_key(objective, v) < candidate_key(
                best_f, best_x
            ):
                best_x, best_f = v.copy(), objective
        return cache[key]

    neutral = np.clip(x, lower, upper)
    neutral[1:4] = np.clip(np.zeros(3, dtype=int), lower[1:4], upper[1:4])
    candidates = []
    for state in range(FILTER_STATES):
        vector = neutral.copy()
        vector[0] = state
        candidates.append(vector)
    try:
        # Establish a fully measured incumbent before a possibly partial batch.
        for i, vector in enumerate(candidates):
            if i == 1:
                prefetch(candidates[1:])
            _, objective = evaluate(vector)
            row = dict(
                stage="filter_enumeration",
                filter_index=int(vector[0]),
                objective=objective,
                vector=vector.tolist(),
                accepted=np.array_equal(vector, best_x),
            )
            history.append(row)
            event(row)
    except BudgetExhausted:
        if best_x is None:
            raise
        return SearchResult(best_x, best_f, "evaluation_budget", history)

    locked_lower, locked_upper = lower.copy(), upper.copy()
    locked_lower[0] = locked_upper[0] = best_x[0]
    result = continuous_search(
        best_x,
        locked_lower,
        locked_upper,
        trust,
        lambda v: evaluate(v)[0],
        R,
        z,
        max_iterations=max_iterations,
        min_improvement=min_improvement,
        coordinate_trials=coordinate_trials,
        event=lambda row: event(dict(row, stage="continuous")),
        prefetch=prefetch,
        inspect_jacobian=inspect_jacobian,
    )
    history.extend(dict(row, stage="continuous") for row in result.history)
    # The core search tracks every measured probe, including interrupted phases.
    return SearchResult(result.vector, result.objective, result.stop, history)
