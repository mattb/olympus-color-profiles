"""Integer trust-region least squares with rendered acceptance and fixed tie rules."""

from dataclasses import dataclass
import numpy as np
from scipy.optimize import lsq_linear


class BudgetExhausted(RuntimeError):
    pass


@dataclass
class SearchResult:
    vector: np.ndarray
    objective: float
    stop: str
    history: list


def quantize(x, lower, upper):
    # IEEE round-to-even is intentional and is part of the algorithm contract.
    return np.clip(np.rint(x), lower, upper).astype(np.int64)


def regularizer(
    n_images, initial, wheel_l2, wheel_smooth, tone_l2, nuisance_l2, *, wheel_channels=1
):
    """Linear square-root penalty rows; circular neighboring color sectors."""
    d = len(initial)
    rows, offsets = [], []
    wheel_size = 12 * wheel_channels
    shared = wheel_size + 2
    for channel in range(wheel_channels):
        for sector in range(12):
            j = channel * 12 + sector
            r = np.zeros(d)
            r[j] = np.sqrt(wheel_l2 / wheel_size)
            rows.append(r)
            offsets.append(0.0)
            r = np.zeros(d)
            r[j] = np.sqrt(wheel_smooth / wheel_size)
            r[channel * 12 + (sector + 1) % 12] = -r[j]
            rows.append(r)
            offsets.append(0.0)
    for j in (wheel_size, wheel_size + 1):
        r = np.zeros(d)
        r[j] = np.sqrt(tone_l2 / 2)
        rows.append(r)
        offsets.append(0.0)
    # Scale Kelvin units (100K) so its prior is comparable to WB-axis steps.
    scales = [5.0, 1.0, 1.0, 1.0]
    for i in range(n_images):
        for k, scale in enumerate(scales):
            j = shared + i * 4 + k
            r = np.zeros(d)
            r[j] = np.sqrt(nuisance_l2 / (4 * n_images)) / scale
            rows.append(r)
            offsets.append(r[j] * initial[j])
    return np.asarray(rows), np.asarray(offsets)


def candidate_key(objective, vector):
    # Round objective only for resolving numerical ties, never for acceptance.
    return (
        round(float(objective), 12),
        int(np.dot(vector, vector)),
        tuple(map(int, vector)),
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
    """data_residual evaluates actual renders and returns fixed weighted Lab residuals.

    A complete new local Jacobian is measured after each accepted move. A render
    budget failure returns the best *fully evaluated* candidate, including a
    candidate discovered just before interruption. No partial Jacobian is used.
    """
    x = np.asarray(initial, dtype=np.int64).copy()
    lower, upper, trust = map(np.asarray, (lower, upper, trust))
    cache = {}
    best_x = x.copy()
    best_f = float("inf")

    def evaluate(v):
        nonlocal best_x, best_f
        key = tuple(map(int, v))
        if key not in cache:
            r = np.asarray(data_residual(v), dtype=np.float64)
            if not np.isfinite(r).all():
                raise ValueError("non-finite data residual")
            pr = penalty_matrix @ v - penalty_target
            f = float(r @ r + pr @ pr)
            cache[key] = r, f
            if candidate_key(f, v) < candidate_key(best_f, best_x):
                best_x, best_f = v.copy(), f
        return cache[key]

    r, f = evaluate(x)
    history = [dict(iteration=0, objective=f, vector=x.tolist(), accepted=True)]
    stop = "iteration_limit"
    try:
        for iteration in range(1, max_iterations + 1):
            jac = np.zeros((len(r), len(x)))
            # Prefetch a complete phase in one persistent native batch. Evaluation
            # order stays sequential so budget behavior and tie rules are unchanged.
            probes = []
            for j in range(len(x)):
                if lower[j] == upper[j]:
                    continue
                step = 1 if x[j] < upper[j] else -1
                probe = x.copy()
                probe[j] += step
                probes.append((j, step, probe))
            prefetch([p for _, _, p in probes])
            for j, step, probe in probes:
                rp, _ = evaluate(probe)
                jac[:, j] = (rp - r) / step
            inspect_jacobian(x.copy(), jac.copy())
            a = np.vstack([jac, penalty_matrix])
            b = -np.r_[r, penalty_matrix @ x - penalty_target]
            lo, hi = np.maximum(lower - x, -trust), np.minimum(upper - x, trust)
            free = lo < hi
            delta = np.zeros(len(x))
            if free.any():
                fit = lsq_linear(
                    a[:, free],
                    b,
                    bounds=(lo[free], hi[free]),
                    method="bvls",
                    tol=1e-10,
                    max_iter=500,
                )
                if not fit.success or not np.isfinite(fit.x).all():
                    raise ValueError("bounded least-squares solve failed")
                delta[free] = fit.x
            proposed = []
            for scale in (1.0, 0.5):
                v = quantize(x + scale * delta, lower, upper)
                if not np.array_equal(v, x) and not any(
                    np.array_equal(v, a) for a in proposed
                ):
                    proposed.append(v)
            candidates = []
            prefetch(proposed)
            for v in proposed:
                rv, fv = evaluate(v)
                candidates.append((fv, v, rv, "joint"))
            # Fixed fallback if the quantized joint model gives no real improvement.
            if not candidates or min(v[0] for v in candidates) >= f - min_improvement:
                grad = a.T @ (-b)
                order = sorted(range(len(x)), key=lambda j: (-abs(grad[j]), j))
                trials = 0
                fallback = []
                for j in order:
                    if trials >= coordinate_trials:
                        break
                    if lower[j] == upper[j]:
                        continue
                    step = -1 if grad[j] > 0 else 1
                    v = x.copy()
                    v[j] = np.clip(v[j] + step, lower[j], upper[j])
                    if np.array_equal(v, x):
                        continue
                    fallback.append(v)
                    trials += 1
                prefetch(fallback)
                for v in fallback:
                    rv, fv = evaluate(v)
                    candidates.append((fv, v, rv, "coordinate"))
            # Probes themselves are legitimate rendered candidates too.
            if best_f < f - min_improvement:
                rb, fb = evaluate(best_x)
                candidates.append((fb, best_x.copy(), rb, "best_measured"))
            if not candidates:
                stop = "quantized_stationary"
                break
            fv, v, rv, source = min(candidates, key=lambda t: candidate_key(t[0], t[1]))
            accepted = fv < f - min_improvement
            row = dict(
                iteration=iteration,
                objective=fv,
                previous=f,
                vector=v.tolist(),
                accepted=accepted,
                source=source,
            )
            history.append(row)
            event(row)
            if not accepted:
                stop = "no_measured_improvement"
                break
            x, r, f = v.copy(), rv, fv
    except BudgetExhausted:
        stop = "evaluation_budget"
    # Never publish an unrendered continuous solution.
    return SearchResult(best_x, best_f, stop, history)
