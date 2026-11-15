"""Optional deterministic integer-coordinate polishing after the coarse search.

This stage never accepts a linear prediction. Each sweep measures the entire
legal +/-1 coordinate neighborhood, then accepts its best rendered improvement.
The caller may provide a *separate* rendering-budget callback and batched
prefetch hook, just as for ``core.search``. Budgeting is independent of cache
warmth; see ``polish`` for the partial-batch contract.
"""

import numpy as np
from .core import BudgetExhausted, SearchResult, candidate_key


def _integer_vector(value, name):
    a = np.asarray(value)
    if a.ndim != 1 or not np.issubdtype(a.dtype, np.number):
        raise ValueError(f"{name} must be a numeric one-dimensional vector")
    if not np.isfinite(a).all() or not np.equal(a, np.rint(a)).all():
        raise ValueError(f"{name} must contain finite integer settings")
    return a.astype(np.int64)


def validate_box(initial, lower, upper):
    x = _integer_vector(initial, "initial")
    lower = _integer_vector(lower, "lower")
    upper = _integer_vector(upper, "upper")
    if not len(x) or x.shape != lower.shape or x.shape != upper.shape:
        raise ValueError("initial/lower/upper must have equal nonzero dimensions")
    if np.any(lower > upper) or np.any(x < lower) or np.any(x > upper):
        raise ValueError("initial must lie within valid bounds")
    return x, lower, upper


def legal_neighbors(x, lower, upper):
    """Fixed order: coordinate ascending; negative before positive; no clipping."""
    out = []
    for j in range(len(x)):
        for step in (-1, 1):
            if lower[j] <= x[j] + step <= upper[j]:
                v = x.copy()
                v[j] += step
                out.append(v)
    return out


class MeasuredObjective:
    """Shared measured-loss/cache adapter for optional local search stages.

    ``max_evaluations`` is an optional count of distinct complete vectors, NOT a
    native-image request budget. A multi-photo caller should enforce image-cost
    accounting in its own residual/prefetch callbacks instead. Initial scoring
    counts as one vector. Existing disk cache hits count identically to misses.

    ``prefetch`` must render only the admissible deterministic request prefix and
    return without raising BudgetExhausted. ``data_residual`` then raises it at
    the first inadmissible vector. This lets the search score already-rendered
    admissible candidates before stopping. A callback that raises during
    prefetch is supported conservatively, but its unscored renders cannot win.
    """

    def __init__(self, data_residual, penalty_matrix, penalty_target, *,
                 prefetch=lambda _: None, max_evaluations=None):
        if max_evaluations is not None and (
            type(max_evaluations) is not int or max_evaluations < 1
        ):
            raise ValueError("max_evaluations must be a positive integer or None")
        self.data_residual = data_residual
        self.R = np.asarray(penalty_matrix, dtype=np.float64)
        self.z = np.asarray(penalty_target, dtype=np.float64)
        if self.R.ndim != 2 or self.z.shape != (self.R.shape[0],):
            raise ValueError("penalty dimensions are inconsistent")
        if not np.isfinite(self.R).all() or not np.isfinite(self.z).all():
            raise ValueError("non-finite regularizer")
        self.prefetch_callback = prefetch
        self.max_evaluations = max_evaluations
        self.cache = {}
        self.best_vector = None
        self.best_objective = float("inf")
        self.residual_shape = None

    @property
    def evaluations(self):
        return len(self.cache)

    def prefetch(self, vectors):
        missing = []
        seen = set(self.cache)
        for vector in vectors:
            key = tuple(map(int, vector))
            if key not in seen:
                missing.append(vector.copy())
                seen.add(key)
        if self.max_evaluations is not None:
            missing = missing[: max(0, self.max_evaluations - self.evaluations)]
        if missing:
            self.prefetch_callback(missing)

    def evaluate(self, vector):
        key = tuple(map(int, vector))
        if key not in self.cache:
            if self.max_evaluations is not None and self.evaluations >= self.max_evaluations:
                raise BudgetExhausted()
            if self.R.shape[1] != len(vector):
                raise ValueError("penalty dimension does not match settings")
            residual = np.asarray(self.data_residual(vector.copy()), dtype=np.float64)
            if residual.ndim != 1 or not np.isfinite(residual).all():
                raise ValueError("data residual must be a finite one-dimensional vector")
            if self.residual_shape is not None and residual.shape != self.residual_shape:
                raise ValueError("data residual shape changed during the search")
            self.residual_shape = residual.shape
            penalty = self.R @ vector - self.z
            objective = float(residual @ residual + penalty @ penalty)
            if not np.isfinite(objective):
                raise ValueError("non-finite measured objective")
            self.cache[key] = residual, objective
            if self.best_vector is None or candidate_key(objective, vector) < candidate_key(
                self.best_objective, self.best_vector
            ):
                self.best_vector = vector.copy()
                self.best_objective = objective
        return self.cache[key]


def polish(initial, lower, upper, data_residual, penalty_matrix, penalty_target, *,
           max_sweeps=3, min_improvement=1e-4, max_evaluations=None,
           prefetch=lambda _: None, event=lambda _: None):
    """Best-improvement coordinate sweeps with complete measured neighborhoods.

    Returns ``core.SearchResult`` with the same penalized squared-residual loss,
    ``candidate_key`` tie rules and strict min-improvement acceptance as coarse
    search. Stop values are ``sweep_limit``, ``no_measured_improvement``,
    ``quantized_stationary`` or ``evaluation_budget``. On interrupted sweeps,
    return the best fully scored setting, never an unrendered or partly scored
    candidate. Like core.search, the best measured result is returned even if a
    sub-threshold improvement was insufficient to start another sweep.

    A completed no-improvement sweep establishes only a legal +/-1 coordinate
    local optimum, not a joint/multi-coordinate/global optimum. A budget- or
    sweep-limited run makes no such claim. At least the initial vector must be
    affordable; BudgetExhausted on its first evaluation propagates to the caller.
    """
    if type(max_sweeps) is not int or max_sweeps < 0:
        raise ValueError("max_sweeps must be a nonnegative integer")
    if not np.isfinite(min_improvement) or min_improvement < 0:
        raise ValueError("min_improvement must be finite and nonnegative")
    x, lower, upper = validate_box(initial, lower, upper)
    measured = MeasuredObjective(data_residual, penalty_matrix, penalty_target,
                                 prefetch=prefetch, max_evaluations=max_evaluations)
    _, objective = measured.evaluate(x)
    history = [dict(iteration=0, objective=objective, vector=x.tolist(),
                    accepted=True, source="polish_initial", evaluations=measured.evaluations)]
    stop = "sweep_limit"
    try:
        for sweep in range(1, max_sweeps + 1):
            neighbors = legal_neighbors(x, lower, upper)
            if not neighbors:
                stop = "quantized_stationary"
                break
            measured.prefetch(neighbors)
            scored = [(measured.evaluate(v)[1], v) for v in neighbors]
            next_objective, next_x = min(scored, key=lambda item: candidate_key(item[0], item[1]))
            accepted = next_objective < objective - min_improvement
            row = dict(iteration=sweep, previous=objective, objective=next_objective,
                       vector=next_x.tolist(), accepted=accepted,
                       source="complete_coordinate_neighborhood", complete=True,
                       neighbors=len(neighbors), evaluations=measured.evaluations)
            history.append(row)
            event(row)
            if not accepted:
                stop = "no_measured_improvement"
                break
            x, objective = next_x.copy(), next_objective
    except BudgetExhausted:
        stop = "evaluation_budget"
        row = dict(iteration=sweep, previous=objective,
                   objective=measured.best_objective,
                   vector=measured.best_vector.tolist(),
                   accepted=measured.best_objective < objective - min_improvement,
                   source="partial_coordinate_neighborhood", complete=False,
                   evaluations=measured.evaluations)
        history.append(row)
        event(row)
    return SearchResult(measured.best_vector.copy(), measured.best_objective, stop, history)
