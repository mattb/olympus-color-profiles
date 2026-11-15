"""Explicit benchmark scoring ablations; stable Scorer defaults stay unchanged."""

import cv2
import numpy as np
from skimage.color import rgb2lab, deltaE_ciede2000
from .color import rgb, align
from .scoring import Scorer, resize_long
from .relative import construct_relative_target


class ExperimentalScorer(Scorer):
    def __init__(
        self,
        baseline,
        target,
        *,
        size=96,
        blur=0.7,
        loss="lab",
        weighting="spatial",
        registration="identity",
        reset=None,
        relative=False,
    ):
        if (
            size < 24
            or blur < 0
            or loss not in ("lab", "delta_e00_squared")
            or weighting not in ("spatial", "hue_lightness")
        ):
            raise ValueError("Invalid scoring experiment policy")
        self.size = size
        self.blur = blur
        self.loss = loss
        self.weighting = weighting
        self.target_path = target
        self.target_small = resize_long(rgb(target))
        base = rgb(baseline)
        self.baseline_small_shape = base.shape[:2]
        if registration == "identity":
            if base.shape != self.target_small.shape:
                raise ValueError(
                    "Declared identity requires identical preview dimensions"
                )
            self.M = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
            valid = np.ones(base.shape[:2], np.uint8)
            self.registration = dict(
                matrix=self.M.tolist(),
                kind="known_generated_pixel_alignment",
                coverage=1.0,
            )
        elif registration == "features":
            self.M, valid, self.registration = align(base, self.target_small)
        else:
            raise ValueError("Unknown registration policy")
        h, w = self.target_small.shape[:2]
        base_grid = cv2.warpAffine(base, self.M, (w, h))
        self.absolute_target_lab = self.sample_lab(self.target_small)
        self.target_lab = self.absolute_target_lab
        self.relative_diagnostics = None
        if relative:
            if reset is None:
                raise ValueError("Relative experiment requires actual reset reference")
            reset_small = resize_long(rgb(reset))
            rM, rvalid, rinfo = align(reset_small, self.target_small)
            reset_grid = cv2.warpAffine(reset_small, rM, (w, h))
            valid = valid * rvalid
            values = construct_relative_target(
                self.sample_rgb(base_grid),
                self.sample_rgb(reset_grid),
                self.sample_rgb(self.target_small),
            )
            self.target_lab = values["target_lab"]
            self.absolute_target_lab = values["absolute_target_lab"]
            self.relative_diagnostics = values["diagnostics"]
            self.registration["reset_registration"] = rinfo
        mask = cv2.resize(valid, (size, size), interpolation=cv2.INTER_NEAREST).astype(
            float
        )
        border = max(1, round(size * 4 / 96))
        mask[:border] = 0
        mask[-border:] = 0
        mask[:, :border] = 0
        mask[:, -border:] = 0
        if not mask.sum():
            raise ValueError("Empty experimental scoring mask")
        self.weight = mask / mask.sum()
        self.weight_diagnostics = dict(policy=weighting)
        if weighting == "hue_lightness":
            lab = self.sample_lab(base_grid)
            chroma = np.hypot(lab[..., 1], lab[..., 2])
            hue = np.mod(np.arctan2(lab[..., 2], lab[..., 1]), 2 * np.pi)
            hue_bin = np.minimum((hue * 12 / (2 * np.pi)).astype(int), 11)
            hue_bin[chroma < 8] = 12
            light = np.digitize(lab[..., 0], [30, 70])
            bins = hue_bin * 3 + light
            counts = np.bincount(bins[mask > 0].ravel(), minlength=39)
            occupied = np.count_nonzero(counts)
            factors = np.sqrt(mask.sum() / (occupied * np.maximum(counts[bins], 1)))
            factors = np.clip(
                factors, 0.5, 2.0
            )  # fixed max:min=4, no target/candidate adaptation
            self.weight = mask * factors
            self.weight /= self.weight.sum()
            self.weight_diagnostics.update(
                bin_counts=counts.tolist(),
                factor_min=float(factors[mask > 0].min()),
                factor_max=float(factors[mask > 0].max()),
                neutral_chroma_threshold=8,
            )

    def sample_rgb(self, a):
        a = cv2.resize(a, (self.size, self.size), interpolation=cv2.INTER_AREA)
        if self.blur:
            a = cv2.GaussianBlur(a, (0, 0), self.blur)
        return a / 255.0

    def sample_lab(self, a):
        return rgb2lab(self.sample_rgb(a))

    def small(self, path):
        a = rgb(path)
        h, w = self.target_small.shape[:2]
        ll = self.sample_lab(cv2.warpAffine(a, self.M, (w, h)))
        diff = ll - self.target_lab
        de = deltaE_ciede2000(ll, self.target_lab)
        residual = (
            diff * np.sqrt(self.weight[..., None] / 3)
            if self.loss == "lab"
            else de * np.sqrt(self.weight)
        )
        metrics = dict(
            lab_rmse=float(np.sqrt(np.sum(self.weight[..., None] * diff**2) / 3)),
            delta_e00=float(np.sum(self.weight * de)),
            render=str(path),
            resolution=f"{self.size}x{self.size}_sigma_{self.blur}",
            color_space="ICC_to_sRGB_to_Lab_D65",
            objective_loss=self.loss,
            weighting=self.weighting,
            target_mode="relative_lab_delta"
            if self.relative_diagnostics
            else "absolute",
        )
        if self.relative_diagnostics:
            absolute = ll - self.absolute_target_lab
            metrics.update(
                absolute_lab_rmse=float(
                    np.sqrt(np.sum(self.weight[..., None] * absolute**2) / 3)
                ),
                absolute_delta_e00=float(
                    np.sum(self.weight * deltaE_ciede2000(ll, self.absolute_target_lab))
                ),
            )
        return residual, metrics
