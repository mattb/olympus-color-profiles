"""One ICC conversion path for scoring and all display artifacts."""

import io
import struct
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageCms, ImageOps, ImageDraw


def _stable_srgb_profile():
    # LCMS writes wall-clock creation time into generated ICC headers. A valid
    # fixed date and unassigned profile ID make exported artifacts reproducible
    # without changing the color transform or embedding a stale checksum.
    data = bytearray(ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    struct.pack_into(">6H", data, 24, 2000, 1, 1, 0, 0, 0)
    data[84:100] = bytes(16)
    return bytes(data)


SRGB = _stable_srgb_profile()


def rgb(path):
    with Image.open(path) as original:
        icc = original.info.get("icc_profile")
        if not icc:
            raise ValueError(f"ICC profile required: {path}")
        im = ImageOps.exif_transpose(original).convert("RGB")
        converted = ImageCms.profileToProfile(
            im,
            ImageCms.ImageCmsProfile(io.BytesIO(icc)),
            ImageCms.createProfile("sRGB"),
            outputMode="RGB",
            renderingIntent=1,
        )
        return np.asarray(converted)


def contact_sheet(paths, output):
    canvas = Image.new("RGB", (400 * len(paths), 440), "white")
    draw = ImageDraw.Draw(canvas)
    for j, (path, label) in enumerate(paths):
        if isinstance(path, np.ndarray):
            # Arrays must already be canonical ICC-managed sRGB (e.g. frozen
            # registration output from Scorer.comparison_rgb).
            if path.dtype != np.uint8 or path.ndim != 3 or path.shape[2] != 3:
                raise ValueError("Comparison arrays must be uint8 canonical sRGB")
            values = path
        else:
            values = rgb(path)
        im = Image.fromarray(values)
        im.thumbnail((400, 400))
        canvas.paste(im, (j * 400 + (400 - im.width) // 2, 30 + (400 - im.height) // 2))
        draw.text((j * 400 + 10, 10), label, fill="black")
    canvas.save(output, quality=95, icc_profile=SRGB)


def align(source, target):
    cv2.setNumThreads(1)
    cv2.setRNGSeed(0)
    sift = cv2.SIFT_create()
    a, da = sift.detectAndCompute(cv2.cvtColor(source, cv2.COLOR_RGB2GRAY), None)
    b, db = sift.detectAndCompute(cv2.cvtColor(target, cv2.COLOR_RGB2GRAY), None)
    if da is None or db is None:
        raise ValueError("Insufficient registration features")
    matches = [
        m
        for pair in cv2.BFMatcher().knnMatch(da, db, k=2)
        if len(pair) == 2
        for m, n in [pair]
        if m.distance < 0.75 * n.distance
    ]
    if len(matches) < 20:
        raise ValueError("Insufficient registration matches")
    M, inliers = cv2.estimateAffinePartial2D(
        np.float32([a[m.queryIdx].pt for m in matches]),
        np.float32([b[m.trainIdx].pt for m in matches]),
        method=cv2.RANSAC,
        ransacReprojThreshold=2,
        maxIters=2000,
        confidence=0.99,
    )
    if M is None or inliers.sum() < 20 or inliers.mean() < 0.25:
        raise ValueError("Unreliable registration")
    angle = abs(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
    if angle > 2 or not 0.2 < np.hypot(M[0, 0], M[1, 0]) < 5:
        raise ValueError("Unexpected registration rotation/scale")
    valid = cv2.warpAffine(
        np.ones(source.shape[:2], np.uint8), M, (target.shape[1], target.shape[0])
    )
    if valid[10:-10, 10:-10].mean() < 0.85:
        raise ValueError("Registration coverage below 85%")
    return (
        M,
        valid,
        dict(
            matrix=M.tolist(),
            inliers=int(inliers.sum()),
            matches=len(matches),
            coverage=float(valid.mean()),
        ),
    )
