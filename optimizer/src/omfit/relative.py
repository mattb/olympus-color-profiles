"""Experimental relative-look targets; never silently replace absolute matching.

Inputs must already be registered onto ONE fixed grid and converted through the
same ICC-managed sRGB path. This module performs no registration, WB estimation,
mask selection, or candidate-dependent adjustment. It transfers an edit-minus-
reset Lab vector onto the neutral Olympus rendering. Unlike LCh subtraction this
has no undefined hue near neutral colors and no circular hue branch cut.

This changes the fitting question: preserving Olympus baseline plus a Lightroom
edit delta is NOT the same objective as reproducing the Lightroom edited image.
Always retain/report error against ``absolute_target_lab`` separately.
"""

import numpy as np
from skimage.color import rgb2lab

# IEC sRGB/D65 matrix used by the pinned scikit-image RGB→XYZ implementation.
_XYZ_FROM_LINEAR_SRGB = np.array(
    [[0.412453, 0.357580, 0.180423],
     [0.212671, 0.715160, 0.072169],
     [0.019334, 0.119193, 0.950227]], dtype=np.float64
)
_LINEAR_SRGB_FROM_XYZ = np.linalg.inv(_XYZ_FROM_LINEAR_SRGB)
_D65 = np.array([0.95047, 1.0, 1.08883])


def _srgb_float(value, name):
    array = np.asarray(value)
    if array.ndim < 2 or array.shape[-1] != 3 or array.size == 0:
        raise ValueError(f"{name} must be a nonempty (..., 3) sRGB image")
    if array.dtype == np.uint8:
        array = array.astype(np.float64) / 255.0
    elif np.issubdtype(array.dtype, np.floating):
        array = array.astype(np.float64, copy=False)
    else:
        raise ValueError(f"{name} must be uint8 or floating-point sRGB in [0, 1]")
    if not np.isfinite(array).all() or np.any(array < 0) or np.any(array > 1):
        raise ValueError(f"{name} must contain finite sRGB values in [0, 1]")
    return array


def _unclipped_linear_rgb(lab):
    """Lab→linear sRGB without the gamut clipping in ordinary display helpers."""
    fy = (lab[..., 0] + 16) / 116
    f = np.stack((fy + lab[..., 1] / 500, fy, fy - lab[..., 2] / 200), axis=-1)
    delta = 6 / 29
    xyz = np.where(f > delta, f**3, 3 * delta**2 * (f - 4 / 29)) * _D65
    return xyz @ _LINEAR_SRGB_FROM_XYZ.T


def construct_relative_target(
    baseline_rgb, reset_rgb, edited_rgb, *, gamut="preserve_lab", numerical_tolerance=1e-7
):
    """Construct an explicit experimental look-delta target.

    ``gamut='preserve_lab'`` retains the exact intended Lab delta, including
    colors outside display sRGB. The clipped ``display_rgb`` is then only a
    visualization; it is NOT the scoring target. ``gamut='clip_srgb'`` instead
    projects that target into display sRGB and recomputes the scoring Lab values.
    Both options report gamut/clipping fractions. Neither is proven to produce
    more reusable camera profiles; compare them on independent held-out scenes.

    Returns a dictionary with NumPy ``target_lab``, ``absolute_target_lab``,
    floating-point ``display_rgb`` in [0,1], boolean ``out_of_gamut_mask``, and
    JSON-safe ``diagnostics``. Inputs can be uint8 or floating sRGB in [0,1].
    uint16/ambiguous integer units are deliberately rejected.
    """
    if gamut not in ("preserve_lab", "clip_srgb"):
        raise ValueError("gamut must be preserve_lab or clip_srgb")
    if (isinstance(numerical_tolerance, (bool, np.bool_))
        or not np.isfinite(numerical_tolerance) or numerical_tolerance < 0):
        raise ValueError("Numerical gamut tolerance must be finite and nonnegative")
    baseline = _srgb_float(baseline_rgb, "baseline_rgb")
    reset = _srgb_float(reset_rgb, "reset_rgb")
    edited = _srgb_float(edited_rgb, "edited_rgb")
    if baseline.shape != reset.shape or baseline.shape != edited.shape:
        raise ValueError("Inputs must already be registered onto the same grid")
    baseline_lab = rgb2lab(baseline)
    reset_lab = rgb2lab(reset)
    absolute_lab = rgb2lab(edited)
    intended = baseline_lab + absolute_lab - reset_lab
    linear = _unclipped_linear_rgb(intended)
    outside = np.any(
        (linear < -numerical_tolerance) | (linear > 1 + numerical_tolerance), axis=-1
    )
    # The nonlinear branch only receives nonnegative values; negative channels
    # use the linear segment and are clipped solely for the display image.
    encoded = np.where(
        linear <= 0.0031308,
        12.92 * linear,
        1.055 * np.maximum(linear, 0) ** (1 / 2.4) - 0.055,
    )
    display = np.clip(encoded, 0, 1)
    target = intended if gamut == "preserve_lab" else rgb2lab(display)
    intended_delta = absolute_lab - reset_lab
    target_delta = target - baseline_lab
    projection_error = np.linalg.norm(target - intended, axis=-1)
    diagnostics = dict(
        schema="omfit-relative-target/1",
        experimental=True,
        objective="olympus_baseline_plus_lightroom_edit_minus_reset_lab",
        changes_absolute_matching_objective=True,
        input_space="ICC_managed_sRGB_D65",
        registration="caller_supplied_fixed_grid",
        gamut_policy=gamut,
        display_is_scoring_target=(gamut == "clip_srgb"),
        out_of_gamut_pixel_fraction=float(outside.mean()),
        out_of_gamut_pixels=int(outside.sum()),
        pixel_count=int(outside.size),
        intended_lightness_outside_0_100_fraction=float(
            np.mean((intended[..., 0] < 0) | (intended[..., 0] > 100))
        ),
        numerical_gamut_tolerance=float(numerical_tolerance),
        mean_intended_edit_delta_lab=float(np.linalg.norm(intended_delta, axis=-1).mean()),
        mean_applied_edit_delta_lab=float(np.linalg.norm(target_delta, axis=-1).mean()),
        mean_projection_error_lab=float(projection_error.mean()),
        max_projection_error_lab=float(projection_error.max()),
        absolute_edited_reference_must_be_reported_separately=True,
        physical_camera_validated=False,
    )
    return dict(target_lab=target, absolute_target_lab=absolute_lab,
                display_rgb=display, out_of_gamut_mask=outside, diagnostics=diagnostics)
