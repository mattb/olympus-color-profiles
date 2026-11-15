"""Diagnostics for a *measured data* Jacobian, excluding regularization rows.

A nonzero response is evidence of a local effect, not proof that a control was
uniquely learned or that a reusable style generalizes. Control units affect raw
column norms. Column-normalized rank/cosines expose directional degeneracy
without treating a 100K WB step as comparable to a wheel step.

Only exactly zero columns are eligible for default freezing, and only for the
current local solve. Reprobe them after moving the operating point. Numerical
rank/cosine tolerances below are floating-point diagnostics, not empirically
validated camera noise thresholds. Optional weak-response thresholds are
reporting-only and never enlarge the default freeze mask.
"""

import numpy as np


def _column_norms(jacobian):
    """Stable norms: retain a real tiny response rather than squaring it to zero."""
    scale = np.max(np.abs(jacobian), axis=0)
    normalized = np.divide(
        jacobian,
        scale,
        out=np.zeros_like(jacobian),
        where=scale != 0,
    )
    norms = scale * np.sqrt(np.sum(normalized * normalized, axis=0))
    if not np.isfinite(norms).all():
        raise ValueError("Jacobian column norms overflowed")
    return norms


def analyze_jacobian(jacobian, names=None, *, weak_relative_threshold=None):
    """Return JSON-safe, deterministic local identifiability diagnostics.

    Parameters
    ----------
    jacobian : array, shape (residual_samples, controls)
        Actual finite differences of the fixed weighted data residual. Do not
        append penalty rows: they could make unsupported controls appear observed.
    names : sequence[str], optional
        Labels in the same order as the vector. Defaults to ``control_0`` etc.
    weak_relative_threshold : float in (0, 1], optional
        Report columns with norm/max_column_norm below this configured ratio.
        This is a user policy, not a measured noise floor, and never freezes a
        nonzero column. No weak-response classification is made by default.

    ``default_local_freeze_mask`` contains true only for exact data zeros. The
    caller retains responsibility for remeasurement and for fixing those
    coordinates at their current values rather than claiming they were fitted.
    """
    matrix = np.asarray(jacobian, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        raise ValueError("Jacobian must be a 2D array with at least one residual")
    if not np.isfinite(matrix).all():
        raise ValueError("Jacobian must contain finite measured values")
    rows, columns = matrix.shape
    if names is None:
        names = [f"control_{i}" for i in range(columns)]
    else:
        names = list(names)
    if len(names) != columns or any(not isinstance(x, str) or not x for x in names):
        raise ValueError("One nonempty control name is required per Jacobian column")
    if len(set(names)) != columns:
        raise ValueError("Control names must be unique")
    if weak_relative_threshold is not None:
        if isinstance(weak_relative_threshold, (bool, np.bool_)):
            raise ValueError("Weak relative threshold must be a number in (0, 1]")
        weak_relative_threshold = float(weak_relative_threshold)
        if not np.isfinite(weak_relative_threshold) or not 0 < weak_relative_threshold <= 1:
            raise ValueError("Weak relative threshold must be a number in (0, 1]")

    counts = np.count_nonzero(matrix, axis=0)
    zero = counts == 0
    norms = _column_norms(matrix) if columns else np.empty(0)
    largest = float(norms.max()) if columns else 0.0
    relative = norms / largest if largest else np.zeros(columns)
    active = np.flatnonzero(~zero)
    numeric_rtol = float(np.finfo(np.float64).eps * max(rows, columns))

    if active.size:
        raw_singular = np.linalg.svd(matrix[:, active], compute_uv=False)
        raw_tolerance = float(raw_singular[0] * numeric_rtol)
        raw_rank = int(np.count_nonzero(raw_singular > raw_tolerance))
        normalized = matrix[:, active] / norms[active]
        # Reduced SVD provides the row-space basis even for an underdetermined J.
        _, unit_singular, vt = np.linalg.svd(normalized, full_matrices=False)
        unit_tolerance = float(unit_singular[0] * numeric_rtol)
        unit_rank = int(np.count_nonzero(unit_singular > unit_tolerance))
        basis = vt[:unit_rank]
        null_fraction = np.clip(1 - np.sum(basis * basis, axis=0), 0, 1)
        gram = np.clip(normalized.T @ normalized, -1, 1)
    else:
        raw_singular = unit_singular = np.empty(0)
        raw_tolerance = unit_tolerance = 0.0
        raw_rank = unit_rank = 0
        null_fraction = np.empty(0)
        gram = np.empty((0, 0))

    fractions = np.ones(columns)
    fractions[active] = null_fraction
    controls = []
    for i, name in enumerate(names):
        controls.append(
            dict(
                index=i,
                name=name,
                norm=float(norms[i]),
                rms=float(norms[i] / np.sqrt(rows)),
                nonzero_residual_samples=int(counts[i]),
                nonzero_sample_fraction=float(counts[i] / rows),
                relative_norm=float(relative[i]),
                exactly_zero_measured_effect=bool(zero[i]),
                weak_response_by_configured_ratio=(
                    bool(not zero[i] and relative[i] < weak_relative_threshold)
                    if weak_relative_threshold is not None else None
                ),
                measured_response_supported=bool(not zero[i]),
                identifiable_from_data_numerically=bool(not zero[i] and fractions[i] <= numeric_rtol),
                normalized_nullspace_fraction=float(fractions[i]),
                default_local_freeze=bool(zero[i]),
                learned_value_claim_permitted=bool(not zero[i] and fractions[i] <= numeric_rtol),
            )
        )

    pairs = []
    strongest = None
    for ai, i in enumerate(active):
        for aj in range(ai + 1, len(active)):
            j = int(active[aj])
            cosine = float(gram[ai, aj])
            item = dict(indices=[int(i), j], names=[names[i], names[j]], cosine=cosine)
            if strongest is None or abs(cosine) > abs(strongest["cosine"]):
                strongest = item
            if 1 - abs(cosine) <= numeric_rtol:
                pairs.append(item)

    raw_deficient = raw_rank < len(active)
    normalized_deficient = unit_rank < len(active)
    return dict(
        schema="omfit-observability/1",
        scope="local_measured_data_jacobian_only",
        residual_samples=rows,
        controls=controls,
        exact_zero_indices=np.flatnonzero(zero).tolist(),
        default_local_freeze_mask=zero.tolist(),
        weak_relative_threshold=weak_relative_threshold,
        weak_threshold_is_empirically_validated=False,
        numerical_rank=raw_rank,
        active_controls=len(active),
        rank_deficient=raw_deficient,
        singular_values=raw_singular.tolist(),
        singular_value_tolerance=raw_tolerance,
        condition_number=(float(raw_singular[0] / raw_singular[-1]) if len(active) and not raw_deficient else None),
        normalized_numerical_rank=unit_rank,
        normalized_rank_deficient=normalized_deficient,
        normalized_singular_values=unit_singular.tolist(),
        normalized_singular_value_tolerance=unit_tolerance,
        normalized_condition_number=(float(unit_singular[0] / unit_singular[-1]) if len(active) and not normalized_deficient else None),
        cosine_numerical_tolerance=numeric_rtol,
        numerically_collinear_pairs=pairs,
        strongest_response_direction_pair=strongest,
        remeasure_zero_controls_after_move=True,
        regularization_is_not_observational_evidence=True,
        generalization_established=False,
    )
