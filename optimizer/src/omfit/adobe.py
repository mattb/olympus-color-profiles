"""Fit Adobe Develop presets to JPEG references using DNG Converter previews."""

import argparse
import json
import re
from pathlib import Path
import numpy as np
from PIL import Image
from .adobe_xmp import base_settings, write_preset, write_sidecar, read_preset
from .color import rgb, SRGB, contact_sheet
from .core import search, BudgetExhausted
from .renderer import digest, save
from .scoring import Scorer, resize_long
from .scoring_experiments import ExperimentalScorer

TONES = ["Contrast2012", "Highlights2012", "Shadows2012", "Whites2012", "Blacks2012"]
MIXER = [
    "GrayMixer" + c
    for c in ("Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta")
]

COLOR = ["Vibrance", "Saturation"] + [
    prefix + c
    for prefix in ("HueAdjustment", "SaturationAdjustment", "LuminanceAdjustment")
    for c in ("Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta")
]


def controls_for(mode):
    if mode not in ("mono", "color"):
        raise ValueError("mode must be mono or color")
    return TONES + (MIXER if mode == "mono" else COLOR)


def initial_vector(path, mode):
    """Seed from supported shared controls only; frozen scene settings stay separate."""
    controls = controls_for(mode)
    if path is None:
        return np.zeros(len(controls), dtype=int)
    settings = read_preset(path)
    if bool(settings.get("ConvertToGrayscale", False)) != (mode == "mono"):
        raise ValueError("Initial preset treatment differs from fitting mode")
    values = np.array([float(settings.get(k, 0)) for k in controls])
    if not np.all(np.isfinite(values)) or np.any(np.abs(values) > 100):
        raise ValueError("Initial preset control outside finite [-100, 100] bounds")
    return np.rint(values / 5).astype(int)


def settings_for(vector, mode, scene):
    controls = controls_for(mode)
    if len(vector) != len(controls):
        raise ValueError("Vector length does not match fitting mode")
    settings = base_settings(mode)
    settings.update(
        dict(
            zip(
                controls,
                map(lambda v: int(v) * 5, vector),
            )
        )
    )
    settings.update(scene)
    return settings


def load_pairs(manifest):
    config = json.loads(Path(manifest).read_text())
    pairs = config["pairs"]
    seen = set()
    for p in pairs:
        if not re.fullmatch("[A-Za-z0-9_-]+", p["id"]) or p["id"] in seen:
            raise ValueError("Unsafe/duplicate photo ID")
        seen.add(p["id"])
        p.setdefault("role", "train")
        if p["role"] not in ("train", "validation"):
            raise ValueError("Unknown role")
        for key in ("raw", "target"):
            p[key] = str((Path(manifest).parent / Path(p[key]).expanduser()).resolve())
            p[key + "_hash"] = digest(p[key])
        scene = dict(WhiteBalance="As Shot", Exposure2012=0)
        supplied = p.get("scene", {})
        if set(supplied) - {"WhiteBalance", "Temperature", "Tint", "Exposure2012"}:
            raise ValueError("Scene must contain only WB/exposure")
        scene.update(supplied)
        if scene["WhiteBalance"] not in ("As Shot", "Custom"):
            raise ValueError("WhiteBalance must be As Shot or Custom")
        for key, limits in [
            ("Exposure2012", (-5, 5)),
            ("Temperature", (2000, 50000)),
            ("Tint", (-150, 150)),
        ]:
            if key in scene and (
                type(scene[key]) not in (int, float)
                or not np.isfinite(scene[key])
                or not limits[0] <= scene[key] <= limits[1]
            ):
                raise ValueError("Invalid scene value: " + key)
        if (
            scene["WhiteBalance"] == "Custom"
            and not {"Temperature", "Tint"} <= scene.keys()
        ):
            raise ValueError("Custom WB requires Temperature and Tint")
        p["scene"] = scene
    if not any(p["role"] == "train" for p in pairs):
        raise ValueError("Training photos required")
    training_hashes = {p["raw_hash"] for p in pairs if p["role"] == "train"}
    if any(
        p["raw_hash"] in training_hashes for p in pairs if p["role"] == "validation"
    ):
        raise ValueError("Training and validation RAW bytes overlap")
    return pairs


def run(args):
    from .adobe_renderer import AdobeRenderer

    camera_profile = getattr(args, "camera_profile", "Adobe Standard")
    if not isinstance(camera_profile, str) or not camera_profile.strip():
        raise ValueError("Camera profile must be a nonempty Adobe profile name")
    pairs = load_pairs(Path(args.manifest).resolve())
    train = [p for p in pairs if p["role"] == "train"]
    if args.max_renders < len(train):
        raise ValueError("Budget cannot evaluate initial candidate")
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    for d in ("previews", "settings", "adjustments", "comparisons"):
        (out / d).mkdir()
    kwargs = {} if not args.converter else {"converter": args.converter}
    renderer = AdobeRenderer(args.cache, out, **kwargs)
    dim = len(controls_for(args.mode))
    initial = initial_vector(getattr(args, "initial_preset", None), args.mode)
    neutral = np.zeros(dim, dtype=int)
    scorers = {}
    baselines = {}
    memo = {}
    requested = set()

    def preview(path):
        dst = out / "previews" / (digest(path) + ".png")
        if not dst.exists():
            Image.fromarray(resize_long(rgb(path))).save(dst, icc_profile=SRGB)
        return dst

    def render_settings(v, scene):
        s = settings_for(v, args.mode, scene)
        s["CameraProfile"] = camera_profile
        return s

    def render(p, v):
        s = render_settings(v, p["scene"])
        key = (p["id"], tuple(map(int, v)))
        if key not in memo:
            memo[key] = renderer.render(p["raw"], s)
        return memo[key]

    for p in pairs:
        baselines[p["id"]] = render(p, neutral)
        cls = ExperimentalScorer if args.identity_geometry else Scorer
        scorers[p["id"]] = cls(preview(baselines[p["id"]]), p["target"])

    def evaluate(v):
        residual = []
        for p in train:
            key = (p["id"], tuple(map(int, v)))
            if key not in requested:
                if len(requested) >= args.max_renders:
                    raise BudgetExhausted()
                requested.add(key)
            residual.append(
                scorers[p["id"]].small(preview(render(p, v)))[0].ravel()
                / np.sqrt(len(train))
            )
        return np.concatenate(residual)

    fit = search(
        initial,
        np.full(dim, -20),
        np.full(dim, 20),
        np.full(dim, 2 if args.mode == "mono" else 4),
        evaluate,
        np.eye(dim) * np.sqrt(0.01 / dim),
        np.zeros(dim),
        max_iterations=args.iterations,
    )
    style = render_settings(fit.vector, {})
    write_preset(out / "profile.xmp", style, args.name)
    save(
        out / "profile.json",
        dict(
            scope="fixed_adobe_baseline_plus_shared_style",
            settings=style,
            lightroom_import_validated=False,
            renderer="Adobe DNG Converter JPEG preview",
        ),
    )
    metrics = {}
    for p in pairs:
        path = render(p, fit.vector)
        scorer = scorers[p["id"]]
        m = dict(
            role=p["role"],
            baseline=scorer.small(preview(baselines[p["id"]]))[1],
            fitted=scorer.small(preview(path))[1],
        )
        if p["role"] == "validation" and not args.skip_full_validation:
            m["full_resolution"] = scorer.full(
                baselines[p["id"]], dict(baseline=baselines[p["id"]], fitted=path)
            )
        metrics[p["id"]] = m
        write_sidecar(
            out / "settings" / (p["id"] + ".xmp"),
            render_settings(fit.vector, p["scene"]),
        )
        save(
            out / "adjustments" / (p["id"] + ".json"),
            dict(scope="per_photo_only", settings=p["scene"], fitted=False),
        )
        contact_sheet(
            [
                (scorer.target_small, "Reference"),
                (scorer.comparison_rgb(baselines[p["id"]]), "Adobe baseline"),
                (scorer.comparison_rgb(path), "Adobe fitted"),
            ],
            out / "comparisons" / (p["id"] + ".jpg"),
        )
    for p in pairs:
        for key in ("raw", "target"):
            if digest(p[key]) != p[key + "_hash"]:
                raise ValueError("Input changed during fit")
    report = dict(
        schema="omfit-adobe/1",
        mode=args.mode,
        camera_profile=camera_profile,
        inputs=pairs,
        profile=str(out / "profile.xmp"),
        vector=fit.vector.tolist(),
        controls=controls_for(args.mode),
        initial_vector=initial.tolist(),
        initial_preset=str(Path(args.initial_preset).resolve())
        if getattr(args, "initial_preset", None) else None,
        control_step=5,
        trust_step=10 if args.mode == "mono" else 20,
        objective=fit.objective,
        history=fit.history,
        stop=fit.stop,
        logical_requests=len(requested),
        budget=args.max_renders,
        metrics=metrics,
        renderer_identity=getattr(renderer, "identity", {}),
        native_calls=getattr(renderer, "calls", None),
        cache_hits=getattr(renderer, "hits", None),
        policy=dict(
            scene="frozen",
            training_only_selection=True,
            preview_color_management="renderer canonical sRGB",
            lightroom_parity_validated=False,
            preset_import_validated=False,
            color_mode_scope="tone_global_color_and_eight_sector_hsl"
            if args.mode == "color"
            else "tone_and_bw_mixer",
            preset_scope="fixed baseline plus style; resets detail/lens settings included in base",
            limitations=[
                "DNG JPEG preview oracle, not Lightroom TIFF parity",
                "Five-unit controls; bounded local search",
            ],
        ),
    )
    save(out / "result.json", report)
    print(
        json.dumps(
            dict(
                result=str(out / "result.json"),
                stop=fit.stop,
                logical_requests=len(requested),
            )
        )
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest")
    p.add_argument("--output", required=True)
    p.add_argument("--cache", required=True)
    p.add_argument("--converter")
    p.add_argument("--mode", choices=["mono", "color"], default="mono")
    p.add_argument("--name", default="OM Fit Adobe")
    p.add_argument("--camera-profile", default="Adobe Standard",
                   help="Fixed Adobe base profile; actual availability verified by render readback")
    p.add_argument("--initial-preset", help="Seed shared controls from an existing XMP preset")
    p.add_argument("--max-renders", type=int, default=100)
    p.add_argument("--iterations", type=int, default=10)
    p.add_argument("--identity-geometry", action="store_true")
    p.add_argument("--skip-full-validation", action="store_true")
    a = p.parse_args()
    if a.max_renders < 1 or a.iterations < 0:
        p.error("Invalid budget/iterations")
    run(a)


if __name__ == "__main__":
    main()
