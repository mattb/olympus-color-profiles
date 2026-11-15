"""Optional direction-aware local proposals; not wired into the default search.

Olympus controls need not have symmetric positive/negative response. Measure
both signed unit perturbations and keep their effects separate. Never average
them into a central difference. This module proposes candidate settings only;
its linear predictions are NOT measured results or an acceptance decision.
"""
from dataclasses import dataclass
import numpy as np
from scipy.optimize import lsq_linear
from .core import BudgetExhausted, quantize
from .polish import MeasuredObjective, legal_neighbors, validate_box


@dataclass
class DirectionalProposals:
    vectors: list
    sources: list
    predicted_objectives: list
    best_measured_vector: np.ndarray
    best_measured_objective: float
    evaluations: int
    complete: bool
    effects: dict


def directional_proposals(initial, lower, upper, trust, data_residual,
                          penalty_matrix, penalty_target, *,
                          max_evaluations=None, prefetch=lambda _: None):
    """Build at most six quantized proposals from separately measured +/- slopes.

    Three deterministic sign-consistent bounded models are considered: positive
    directions only, negative directions only, and a mixed model selecting each
    coordinate's best isolated predicted improvement. Each model has AT MOST one
    direction per coordinate: the nonphysical solution using simultaneous + and
    - movement on the same slider is prohibited. Full and half steps are rounded
    with core.quantize; duplicates and the unchanged initial vector are removed.

    ``effects[(j, sign)]`` is r(x + sign*e_j) - r(x), i.e. residual change per
    unit *magnitude* in that direction. Negative effects are NOT negated or
    averaged with positive effects. Linear regularization is modeled exactly.
    All measurements and callbacks obey polish.MeasuredObjective's budget rules.
    An incomplete probe neighborhood returns no proposals and the best fully
    measured candidate, because its partial derivative model is not usable.

    Caller must prefetch/render/score returned vectors with the exact actual
    objective before accepting any improvement using core.candidate_key and
    min_improvement. There is no claim of globally optimal sign selection: the
    mixed model is greedy and does not enumerate 2**dimensions combinations.
    """
    x, lower, upper = validate_box(initial, lower, upper)
    trust = np.asarray(trust, dtype=np.float64)
    if trust.shape != x.shape or not np.isfinite(trust).all() or np.any(trust < 0):
        raise ValueError("trust must be a finite nonnegative vector matching settings")
    measured = MeasuredObjective(data_residual, penalty_matrix, penalty_target,
                                 prefetch=prefetch, max_evaluations=max_evaluations)
    residual, _ = measured.evaluate(x)
    effects = {}
    neighbors = legal_neighbors(x, lower, upper)
    try:
        measured.prefetch(neighbors)
        for vector in neighbors:
            j = int(np.flatnonzero(vector != x)[0])
            sign = int(vector[j] - x[j])
            effects[j, sign] = measured.evaluate(vector)[0] - residual
    except BudgetExhausted:
        return DirectionalProposals([], [], [], measured.best_vector.copy(),
                                    measured.best_objective, measured.evaluations, False, effects)
    base = np.r_[residual, measured.R @ x - measured.z]
    options = {}
    for j, sign in effects:
        limit = min(trust[j], (upper[j]-x[j]) if sign > 0 else (x[j]-lower[j]))
        if limit <= 0:
            continue
        column = np.r_[effects[j, sign], sign * measured.R[:, j]]
        norm = float(column @ column)
        step = np.clip(-float(base @ column) / norm, 0., limit) if norm else 0.
        predicted = base + step * column
        options[j, sign] = column, limit, float(predicted @ predicted)
    mixed = {}
    for j in range(len(x)):
        available = [sign for sign in (-1, 1) if (j, sign) in options]
        if available:
            mixed[j] = min(available, key=lambda sign: (options[j, sign][2], sign))
    branches = [
        ("mixed", mixed),
        ("positive", {j: 1 for j in range(len(x)) if (j, 1) in options}),
        ("negative", {j: -1 for j in range(len(x)) if (j, -1) in options}),
    ]
    vectors, sources, predictions = [], [], []
    seen = {tuple(map(int, x))}
    for name, branch in branches:
        coordinates = sorted(branch)
        if not coordinates:
            continue
        A = np.column_stack([options[j, branch[j]][0] for j in coordinates])
        caps = np.array([options[j, branch[j]][1] for j in coordinates])
        fit = lsq_linear(A, -base, bounds=(np.zeros(len(caps)), caps),
                         method="bvls", tol=1e-10, max_iter=500)
        if not fit.success or not np.isfinite(fit.x).all():
            raise ValueError("directional bounded least-squares solve failed")
        delta = np.zeros(len(x))
        for j, magnitude in zip(coordinates, fit.x):
            delta[j] = branch[j] * magnitude
        for scale in (1., .5):
            vector = quantize(x + scale * delta, lower, upper)
            key = tuple(map(int, vector))
            if key in seen:
                continue
            seen.add(key)
            # Score the integer proposal with its chosen piecewise local model.
            # This is a prediction only, never an actual objective measurement.
            predicted = base.copy()
            for j in coordinates:
                predicted += abs(int(vector[j]-x[j])) * options[j, branch[j]][0]
            vectors.append(vector)
            sources.append(f"{name}:{scale:g}")
            predictions.append(float(predicted @ predicted))
    return DirectionalProposals(vectors, sources, predictions,
                                measured.best_vector.copy(), measured.best_objective,
                                measured.evaluations, True, effects)
