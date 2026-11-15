"""Frozen registration/masks; low-resolution fitting and full-pixel validation."""

import cv2
import numpy as np
from skimage.color import rgb2lab, deltaE_ciede2000
from .color import rgb, align


def resize_long(a, edge=800):
    h, w = a.shape[:2]
    return cv2.resize(
        a,
        (round(w * edge / max(w, h)), round(h * edge / max(w, h))),
        interpolation=cv2.INTER_AREA,
    )


def lab_small(a):
    return rgb2lab(
        cv2.GaussianBlur(
            cv2.resize(a, (96, 96), interpolation=cv2.INTER_AREA), (0, 0), 0.7
        )
        / 255.0
    )


class Scorer:
    def __init__(self, baseline, target):
        base = rgb(baseline)
        self.target_path = target
        self.target_small = resize_long(rgb(target))
        self.baseline_small_shape = base.shape[:2]
        self.M, valid, self.registration = align(base, self.target_small)
        self.target_lab = lab_small(self.target_small)
        mask = cv2.resize(valid, (96, 96), interpolation=cv2.INTER_NEAREST).astype(
            float
        )
        mask[:4] = 0
        mask[-4:] = 0
        mask[:, :4] = 0
        mask[:, -4:] = 0
        if mask.sum() == 0:
            raise ValueError("Empty scoring mask")
        self.weight = mask / mask.sum()

    def small(self, path):
        a = rgb(path)
        h, w = self.target_small.shape[:2]
        ll = lab_small(cv2.warpAffine(a, self.M, (w, h)))
        diff = ll - self.target_lab
        return diff * np.sqrt(self.weight[..., None] / 3), dict(
            lab_rmse=float(np.sqrt(np.sum(self.weight[..., None] * diff**2) / 3)),
            delta_e00=float(
                np.sum(self.weight * deltaE_ciede2000(ll, self.target_lab))
            ),
            render=str(path),
            resolution="96x96_blurred",
            color_space="ICC_to_sRGB_to_Lab_D65",
        )

    def comparison_rgb(self, path):
        """ICC-managed display on the same frozen reference geometry as scoring."""
        a = rgb(path)
        h, w = self.baseline_small_shape
        if a.shape[:2] != (h, w):
            a = cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA)
        th, tw = self.target_small.shape[:2]
        return cv2.warpAffine(a, self.M, (tw, th))

    def full(self, baseline_path, candidates):
        """No registration or mask refit on candidates; row tiles bound Lab memory."""
        target = rgb(self.target_path)
        base = rgb(baseline_path)
        th, tw = target.shape[:2]
        bh, bw = base.shape[:2]
        sh, sw = self.baseline_small_shape
        sth, stw = self.target_small.shape[:2]
        M = (
            np.diag([tw / stw, th / sth, 1])
            @ np.vstack([self.M, [0, 0, 1]])
            @ np.diag([sw / bw, sh / bh, 1])
        )[:2]
        valid = cv2.warpAffine(np.ones((bh, bw), np.uint8), M, (tw, th)).astype(bool)
        border_x = int(np.ceil(tw * 4 / 96))
        border_y = int(np.ceil(th * 4 / 96))
        valid[:border_y] = False
        valid[-border_y:] = False
        valid[:, :border_x] = False
        valid[:, -border_x:] = False
        n = int(valid.sum())
        if not n:
            raise ValueError("Empty full-resolution scoring mask")
        metrics = {}
        for name, path in candidates.items():
            image = rgb(path)
            if image.shape != base.shape:
                raise ValueError("Full-resolution render dimensions differ")
            warped = cv2.warpAffine(image, M, (tw, th))
            sq = 0.0
            de = 0.0
            for y in range(0, th, 128):
                mask = valid[y : y + 128]
                left = rgb2lab(warped[y : y + 128] / 255.0)
                right = rgb2lab(target[y : y + 128] / 255.0)
                diff = (left - right)[mask]
                sq += float(np.sum(diff**2))
                de += float(np.sum(deltaE_ciede2000(left, right)[mask]))
            metrics[name] = dict(
                lab_rmse=float(np.sqrt(sq / (3 * n))),
                delta_e00=de / n,
                render=str(path),
                resolution="full_unsmoothed",
                render_dimensions=[bw, bh],
                target_dimensions=[tw, th],
                pixels_scored=n,
                color_space="ICC_to_sRGB_to_Lab_D65",
            )
        return dict(
            metrics=metrics,
            registration_matrix=M.tolist(),
            mask="baseline_valid_coverage_and_outer_4_over_96_border",
            registration_frozen=True,
        )
