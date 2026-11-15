"""Predeclared experimental policies and equal-budget measured strategy runner.

This module does not alter the production CLI, scorer or core search. The
caller constructs its scorer from ``policy.score_options()`` and its ORIGINAL
regularizer from ``policy.make_regularizer`` before invoking ``run_strategy``.
One evaluator request ledger is shared across all stages. Native image requests,
including disk-cache hits, count against the same fixed cap.
"""

from dataclasses import asdict, dataclass, replace
import math
import numpy as np
from skimage.color import deltaE_ciede2000
from .core import BudgetExhausted, SearchResult, candidate_key, regularizer, search
from .directional import directional_proposals
from .polish import polish, validate_box


@dataclass(frozen=True)
class TuningPolicy:
    name: str = "original"
    strategy: str = "original"
    coarse_iterations: int = 3
    polish_sweeps: int = 8
    directional_rounds: int = 1
    wheel_l2: float = 0.01
    wheel_smooth: float = 0.03
    tone_l2: float = 0.01
    nuisance_l2: float = 0.01
    trust_steps: int = 2
    grid_size: int = 96
    blur_sigma: float = 0.7
    loss: str = "lab"
    weighting: str = "spatial"
    scene_mode: str = "frozen"
    render_budget_per_image: int = 64
    min_improvement: float = 1e-4

    def __post_init__(self):
        if self.strategy not in (
            "original",
            "coarse1_polish",
            "coarse_then_polish",
            "directional_polish",
        ):
            raise ValueError("unknown strategy")
        if self.scene_mode not in ("frozen", "free"):
            raise ValueError("scene_mode must be frozen or free")
        if self.weighting not in ("spatial", "hue_lightness"):
            raise ValueError("unknown weighting policy")
        if self.loss not in ("lab", "delta_e00_squared"):
            raise ValueError("unknown scoring loss")
        if self.trust_steps not in (1, 2) or self.grid_size not in (96, 192):
            raise ValueError("screen trust_steps must be 1/2 and grid_size 96/192")
        if not self.name:
            raise ValueError("policy must have a name")
        for k in (
            "coarse_iterations",
            "polish_sweeps",
            "directional_rounds",
            "render_budget_per_image",
        ):
            v = getattr(self, k)
            if type(v) is not int or v < 1:
                raise ValueError(f"{k} must be a positive integer")
        for k in (
            "wheel_l2",
            "wheel_smooth",
            "tone_l2",
            "nuisance_l2",
            "blur_sigma",
            "min_improvement",
        ):
            if not math.isfinite(getattr(self, k)) or getattr(self, k) < 0:
                raise ValueError(f"{k} must be finite and nonnegative")

    def score_options(self):
        # Keep the excluded BORDER FRACTION fixed when changing sampling grids:
        # 4 pixels at 96 correspond to 8 at 192, not 4 at both sizes.
        return dict(
            size=self.grid_size,
            blur=self.blur_sigma,
            loss=self.loss,
            weighting=self.weighting,
        )

    def make_regularizer(self, n_images, original_initial, *, wheel_channels=1):
        return regularizer(
            n_images,
            original_initial,
            self.wheel_l2,
            self.wheel_smooth,
            self.tone_l2,
            self.nuisance_l2,
            wheel_channels=wheel_channels,
        )


@dataclass
class StrategyResult:
    result: SearchResult
    stages: list
    cost: dict
    policy: dict

    @property
    def vector(self):
        return self.result.vector

    @property
    def objective(self):
        return self.result.objective

    @property
    def stop(self):
        return self.result.stop

    @property
    def history(self):
        return self.result.history


def screen_policies(*, render_budget_per_image=64):
    """Thirteen fixed screen policies; no full factorial or adaptive test peeking.

    Eleven are baseline/numeric/scoring contrasts; two change search strategy.
    Sampling has individual grid-only and blur-only contrasts plus one declared
    combined 192/no-blur check, permitting attribution without silently bundling
    both changes. All policies share the same native request cap.
    """
    base = TuningPolicy(render_budget_per_image=render_budget_per_image)
    changes = [
        ("original", {}),
        ("wheel_l2_0.1", dict(wheel_l2=0.1)),
        ("smooth_none", dict(wheel_smooth=0.0)),
        ("smooth_0.1", dict(wheel_smooth=0.1)),
        ("tone_l2_0.1", dict(tone_l2=0.1)),
        ("trust_1", dict(trust_steps=1)),
        ("delta_e00_squared", dict(loss="delta_e00_squared")),
        ("hue_lightness", dict(weighting="hue_lightness")),
        ("grid_192", dict(grid_size=192)),
        ("blur_none", dict(blur_sigma=0.0)),
        ("grid_192_blur_none", dict(grid_size=192, blur_sigma=0.0)),
        ("coarse1_polish", dict(strategy="coarse1_polish")),
        ("directional_polish", dict(strategy="directional_polish")),
    ]
    # Additional predeclared allocation controls: keep the complete original
    # coarse stage before polishing, and let the original use the full budget.
    changes += [
        ("original_budget", dict(coarse_iterations=100)),
        ("original3_polish", dict(strategy="coarse_then_polish")),
    ]
    return [replace(base, name=name, **change) for name, change in changes]


def scene_ablation(policy):
    """Separate nuisance-freeing ablation; never smuggle it into the main screen."""
    return replace(policy, name=policy.name + "__free_scene", scene_mode="free")


def scoring_residual(candidate_lab, target_lab, weights, *, loss="lab"):
    """Pure scorer hook: r@r is weighted Lab channel MSE or mean(DeltaE00**2).

    Each image's nonnegative weights are normalized to one. The existing
    Evaluator then divides each image residual by sqrt(number_of_training_images)
    to weight images equally. Delta-E is not squared *after* averaging, and its
    scalar residual is not an arbitrary signed Lab vector. It is a nonlinear
    loss; finite differences must be remeasured under this same residual.
    """
    candidate = np.asarray(candidate_lab, dtype=np.float64)
    target = np.asarray(target_lab, dtype=np.float64)
    weights = np.asarray(weights, dtype=np.float64)
    if (
        candidate.shape != target.shape
        or candidate.ndim < 2
        or candidate.shape[-1] != 3
    ):
        raise ValueError("Lab arrays must have equal (..., 3) shape")
    if (
        weights.shape != candidate.shape[:-1]
        or not np.isfinite(weights).all()
        or np.any(weights < 0)
    ):
        raise ValueError("weights must be finite, nonnegative, and match Lab pixels")
    total = weights.sum()
    if total <= 0 or not np.isfinite(candidate).all() or not np.isfinite(target).all():
        raise ValueError("empty weights or non-finite Lab samples")
    weights = weights / total
    if loss == "lab":
        return ((candidate - target) * np.sqrt(weights[..., None] / 3)).ravel()
    if loss == "delta_e00_squared":
        return (deltaE_ciede2000(candidate, target) * np.sqrt(weights)).ravel()
    raise ValueError("unknown scoring loss")


class _Tracked:
    """Measure every candidate under the same original objective across stages."""

    def __init__(self, evaluator, R, z):
        self.evaluator = evaluator
        self.R = np.asarray(R, dtype=float)
        self.z = np.asarray(z, dtype=float)
        self.best_vector = None
        self.best_objective = float("inf")
        self.objectives = {}

    def __call__(self, vector):
        residual = np.asarray(self.evaluator(vector), dtype=np.float64)
        if residual.ndim != 1 or not np.isfinite(residual).all():
            raise ValueError("invalid measured residual")
        penalty = self.R @ vector - self.z
        objective = float(residual @ residual + penalty @ penalty)
        if not np.isfinite(objective):
            raise ValueError("non-finite measured objective")
        self.objectives[tuple(map(int, vector))] = objective
        if self.best_vector is None or candidate_key(objective, vector) < candidate_key(
            self.best_objective, self.best_vector
        ):
            self.best_vector, self.best_objective = vector.copy(), objective
        return residual

    def prefetch(self, vectors):
        self.evaluator.prefetch(vectors)


def _counter(renderer, name):
    return getattr(renderer, name, 0) if renderer is not None else 0


def _directional_stage(policy, x, lower, upper, trust, measured, R, z):
    """Actual acceptance wrapper: no predicted objective can select a winner."""
    measured(x)
    start = measured.objectives[tuple(map(int, x))]
    history = [
        dict(
            iteration=0,
            objective=start,
            vector=x.tolist(),
            accepted=True,
            source="directional_initial",
        )
    ]
    stop = "iteration_limit"
    for iteration in range(1, policy.directional_rounds + 1):
        before = measured.objectives[tuple(map(int, x))]
        proposals = directional_proposals(
            x, lower, upper, trust, measured, R, z, prefetch=measured.prefetch
        )
        budget = not proposals.complete
        # Probes themselves are fully measured candidates, including a prefix
        # scored before budget exhaustion. The global tracker already saw them.
        if not budget:
            try:
                measured.prefetch(proposals.vectors)
                for vector in proposals.vectors:
                    measured(vector)
            except BudgetExhausted:
                budget = True
        accepted = measured.best_objective < before - policy.min_improvement
        row = dict(
            iteration=iteration,
            previous=before,
            objective=measured.best_objective,
            vector=measured.best_vector.tolist(),
            accepted=accepted,
            source="directional_measured",
            complete=not budget,
            proposed=[v.tolist() for v in proposals.vectors],
            model_predictions=proposals.predicted_objectives,
        )
        history.append(row)
        if budget:
            stop = "evaluation_budget"
            break
        if not accepted:
            stop = "no_measured_improvement"
            break
        x = measured.best_vector.copy()
    return SearchResult(
        measured.best_vector.copy(), measured.best_objective, stop, history
    )


def run_strategy(policy, initial, lower, upper, trust, evaluator, R, z):
    """Run a predeclared strategy with one actual-native-request budget ledger.

    ``evaluator`` is the existing CLI Evaluator contract: callable residual,
    ``prefetch(vectors)``, mutable ``budget``, ``requested`` unique request set,
    and ``train`` / ``layout.shared`` for native multi-photo control layouts.
    Synthetic evaluators may instead supply ``training_image_count`` and
    ``shared_size``; absent layout metadata, all coordinates are shared.

    Caller builds scorer/registration from policy.score_options() BEFORE this
    function, and passes the original R,z (not recomputed at stage boundaries).
    The effective absolute cap is min(caller budget, per-image policy cap * N).
    An already-populated logical ledger remains counted; use a fresh evaluator
    per experimental policy for an unbiased comparison. Prior disk cache warmth
    is irrelevant. This function restores the caller's budget on exit.

    In primary frozen-scene mode, WB/EV bounds are set equal to the original
    initial values; only shared wheel/tone may move. Free-scene mode deliberately
    retains caller scene bounds and is a separately labeled ablation.
    """
    if not isinstance(policy, TuningPolicy):
        raise TypeError("policy must be a TuningPolicy")
    x, lower, upper = validate_box(initial, lower, upper)
    trust = np.asarray(trust, dtype=float).copy()
    if trust.shape != x.shape or not np.isfinite(trust).all() or np.any(trust < 0):
        raise ValueError("invalid trust vector")
    R, z = np.asarray(R, dtype=float), np.asarray(z, dtype=float)
    if R.ndim != 2 or R.shape[1] != len(x) or z.shape != (R.shape[0],):
        raise ValueError("regularizer dimensions differ from settings")
    if not np.isfinite(R).all() or not np.isfinite(z).all():
        raise ValueError("non-finite regularizer")
    shared = getattr(
        getattr(evaluator, "layout", None),
        "shared",
        getattr(evaluator, "shared_size", len(x)),
    )
    if type(shared) is not int or not 0 <= shared <= len(x):
        raise ValueError("invalid shared control count")
    trust[:shared] = policy.trust_steps
    if policy.scene_mode == "frozen":
        lower[shared:] = x[shared:]
        upper[shared:] = x[shared:]
        trust[shared:] = 0.0
    n = (
        len(evaluator.train)
        if hasattr(evaluator, "train")
        else getattr(evaluator, "training_image_count", 1)
    )
    if type(n) is not int or n < 1:
        raise ValueError("at least one training image is required")
    original_budget = evaluator.budget
    cap = min(original_budget, policy.render_budget_per_image * n)
    if type(cap) is not int or cap < n:
        raise ValueError("budget must afford the initial complete training evaluation")
    before_requests = len(evaluator.requested)
    renderer = getattr(evaluator, "renderer", None)
    before_calls = _counter(renderer, "calls")
    before_processes = _counter(renderer, "native_processes")
    stages, history = [], []
    measured = _Tracked(evaluator, R, z)
    evaluator.budget = cap
    try:
        measured(x)  # At least one complete scored candidate must be affordable.

        def record(name, result, start_requests, start_objective):
            stages.append(
                dict(
                    name=name,
                    stop=result.stop,
                    start_objective=start_objective,
                    objective=result.objective,
                    vector=result.vector.tolist(),
                    requests_before=start_requests,
                    requests_after=len(evaluator.requested),
                    new_requests=len(evaluator.requested) - start_requests,
                    request_cap=cap,
                    history=result.history,
                )
            )
            history.extend(dict(row, stage=name) for row in result.history)

        if policy.strategy in ("original", "coarse1_polish", "coarse_then_polish"):
            stage_start = len(evaluator.requested)
            start_objective = measured.best_objective
            coarse = search(
                x,
                lower,
                upper,
                trust,
                measured,
                R,
                z,
                max_iterations=1
                if policy.strategy == "coarse1_polish"
                else policy.coarse_iterations,
                min_improvement=policy.min_improvement,
                prefetch=measured.prefetch,
                inspect_jacobian=getattr(
                    evaluator, "inspect_jacobian", lambda vector, matrix: None
                ),
            )
            record("coarse", coarse, stage_start, start_objective)
        else:
            stage_start = len(evaluator.requested)
            start_objective = measured.best_objective
            directed = _directional_stage(
                policy, x, lower, upper, trust, measured, R, z
            )
            record("directional", directed, stage_start, start_objective)
        if policy.strategy != "original" and len(evaluator.requested) < cap:
            stage_start = len(evaluator.requested)
            start_objective = measured.best_objective
            fine = polish(
                measured.best_vector,
                lower,
                upper,
                measured,
                R,
                z,
                max_sweeps=policy.polish_sweeps,
                min_improvement=policy.min_improvement,
                prefetch=measured.prefetch,
            )
            record("polish", fine, stage_start, start_objective)
        stop = stages[-1]["stop"]
        if len(evaluator.requested) >= cap and stop in (
            "iteration_limit",
            "sweep_limit",
        ):
            stop = "evaluation_budget"
        cost = dict(
            requests_before=before_requests,
            requests_total=len(evaluator.requested),
            new_requests=len(evaluator.requested) - before_requests,
            request_cap=cap,
            training_images=n,
            native_calls=_counter(renderer, "calls") - before_calls,
            native_processes=_counter(renderer, "native_processes") - before_processes,
            cache_hits_consume_budget=True,
        )
        return StrategyResult(
            SearchResult(
                measured.best_vector.copy(), measured.best_objective, stop, history
            ),
            stages,
            cost,
            asdict(policy),
        )
    finally:
        evaluator.budget = original_budget
