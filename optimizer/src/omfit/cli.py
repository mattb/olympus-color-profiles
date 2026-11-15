"""Deterministic stock/HSL/MONO fitting with persistent native GPU batches."""

import argparse
import importlib.metadata
import json
import re
import subprocess
from pathlib import Path
import numpy as np
from .color import rgb, align, contact_sheet
from .core import search, regularizer, BudgetExhausted
from .model import Layout, NATURAL
from .mono_model import MonoLayout
from .mono import search as mono_search
from .observability import analyze_jacobian
from .renderer import Renderer, canonical, digest, save
from .scoring import Scorer


def load_pairs(manifest):
    config = json.loads(manifest.read_text())
    pairs = config["pairs"]
    if not pairs or len({p["id"] for p in pairs}) != len(pairs):
        raise ValueError("Pairs need unique IDs")
    for p in pairs:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", p["id"]) or not re.fullmatch(
            r"[A-Za-z0-9_-]+", p.get("group", "default")
        ):
            raise ValueError("IDs and groups must be safe filename components")
        p.setdefault("role", "train")
        p.setdefault("group", "default")
        p.setdefault("initial", [53, 0, 0, 0])
        if p["role"] not in ("train", "validation"):
            raise ValueError("Unknown role")
        x = p["initial"]
        if (
            not isinstance(x, list)
            or len(x) != 4
            or any(type(v) != int for v in x)
            or not (
                20 <= x[0] <= 140
                and abs(x[1]) <= 7
                and abs(x[2]) <= 7
                and abs(x[3]) <= 3
            )
        ):
            raise ValueError(
                "initial must be [Kelvin/100, AB, GM, EV thirds] within bounds"
            )
        for field in ("raw", "target"):
            p[field] = str((manifest.parent / Path(p[field]).expanduser()).resolve())
            p[field + "_hash"] = digest(p[field])
        md = json.loads(
            subprocess.check_output(
                [
                    "exiftool",
                    "-j",
                    "-n",
                    "-Orientation",
                    "-Model",
                    "-CropWidth",
                    "-CropHeight",
                    p["raw"],
                ]
            )
        )[0]
        p["rotate"] = {1: 0, 3: 180, 6: 90, 8: 270}[md.get("Orientation", 1)]
        p["camera_model"] = md.get("Model", "unknown")
        w, h = md["CropWidth"], md["CropHeight"]
        if p["rotate"] in (90, 270):
            w, h = h, w
        p["developed_size"] = [w, h]
        p["resize"] = [round(w * 800 / max(w, h)), round(h * 800 / max(w, h))]
    return pairs


class Evaluator:
    """Prefetch reserves the same ordered request prefix on cold and warm caches."""

    def __init__(self, renderer, layout, train, scorers, backend, budget):
        self.renderer = renderer
        self.layout = layout
        self.train = train
        self.scorers = scorers
        self.backend = backend
        self.budget = budget
        self.requested = set()
        self.residuals = {}
        self.paths = {}

    def requests(self, vector):
        return [
            (p, self.layout.settings(p, self.layout.local(vector, i), self.backend))
            for i, p in enumerate(self.train)
        ]

    def reserve(self, p, s):
        key = canonical([p["raw_hash"], s])
        if key not in self.requested:
            if len(self.requested) >= self.budget:
                return False
            self.requested.add(key)
        return True

    def prefetch(self, vectors):
        requests = []
        for vector in vectors:
            for p, s in self.requests(vector):
                if not self.reserve(p, s):
                    self.render_phase(requests)
                    return
                requests.append((p, s))
        self.render_phase(requests)

    def render_phase(self, requests):
        paths = self.renderer.render_many(requests)
        for (p, s), path in zip(requests, paths):
            self.paths[canonical([p["raw_hash"], s])] = path

    def __call__(self, vector):
        key = tuple(map(int, vector))
        if key not in self.residuals:
            requests = self.requests(vector)
            if not all(self.reserve(p, s) for p, s in requests):
                raise BudgetExhausted()
            if any(
                canonical([p["raw_hash"], s]) not in self.paths for p, s in requests
            ):
                self.render_phase(requests)
            paths = [self.paths[canonical([p["raw_hash"], s])] for p, s in requests]
            self.residuals[key] = np.concatenate(
                [
                    self.scorers[p["id"]].small(path)[0].ravel()
                    / np.sqrt(len(self.train))
                    for (p, _), path in zip(requests, paths)
                ]
            )
        return self.residuals[key]


def request_budget(args, training_images):
    if training_images < 1:
        raise ValueError("A group needs training images")
    budget = (
        args.max_renders
        if args.max_renders is not None
        else args.render_budget_per_photo * training_images
    )
    if budget < training_images:
        raise ValueError("Budget cannot afford initial training evaluation")
    return budget


def run(args):
    sources = {p.name: digest(p) for p in Path(__file__).parent.glob("*.py")}
    manifest = Path(args.manifest).expanduser().resolve()
    pairs = load_pairs(manifest)
    layout = MonoLayout() if args.mode == "mono" else Layout(args.mode)
    for group in {p["group"] for p in pairs}:
        n = sum(p["role"] == "train" for p in pairs if p["group"] == group)
        if n == 0 or request_budget(args, n) < n:
            raise ValueError(
                "Each group needs training images and enough budget for the initial evaluation"
            )
    out = Path(args.output).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=False)
    for d in (
        "profiles",
        "adjustments",
        "settings",
        "comparisons",
        "registrations",
        "diagnostics",
    ):
        (out / d).mkdir()
    renderer = Renderer(
        args.renderer,
        args.cache,
        out,
        build_dir=args.build_dir,
        max_rss_mb=args.max_rss_mb,
        batch_size=args.batch_size,
    )
    save(out / "manifest-resolved.json", dict(pairs=pairs))
    results = {}
    # All initial registration renders share one native process/context.
    baseline_requests = [
        (p, layout.settings(p, layout.start(p["initial"]), args.backend)) for p in pairs
    ]
    baselines = renderer.render_many(baseline_requests)
    scorers = {}
    for p, path in zip(pairs, baselines):
        if args.identity_geometry:
            from .scoring_experiments import ExperimentalScorer

            scorers[p["id"]] = ExperimentalScorer(
                path, p["target"], registration="identity"
            )
        else:
            scorers[p["id"]] = Scorer(path, p["target"])
        save(out / "registrations" / f"{p['id']}.json", scorers[p["id"]].registration)
    for group in sorted({p["group"] for p in pairs}):
        members = [p for p in pairs if p["group"] == group]
        train = [p for p in members if p["role"] == "train"]
        initial = np.array(
            [0] * layout.shared + sum([p["initial"] for p in train], []), dtype=int
        )
        lower, upper, trust = layout.bounds(len(train))
        if args.freeze_scene:
            lower[layout.shared :] = initial[layout.shared :]
            upper[layout.shared :] = initial[layout.shared :]
        evaluator = Evaluator(
            renderer,
            layout,
            train,
            scorers,
            args.backend,
            request_budget(args, len(train)),
        )
        R, z = (
            layout.regularizer(len(train), initial)
            if args.mode == "mono"
            else regularizer(
                len(train),
                initial,
                0.01,
                0.03,
                0.01,
                0.01,
                wheel_channels=layout.wheel // 12,
            )
        )
        diagnostics = []
        channels = (
            ["saturation"]
            if args.mode == "stock"
            else ["saturation", "hue", "luminance"]
        )
        labels = [f"{channel}_{i:02d}" for channel in channels for i in range(12)] + [
            "highlight",
            "shadow",
        ]
        if args.mode == "mono":
            labels = ["filter_state", "contrast", "highlight", "shadow"]
        labels += [
            f"{p['id']}.{control}"
            for p in train
            for control in ("kelvin_100K", "ab", "gm", "exposure_thirds")
        ]

        def inspect(vector, matrix):
            d = analyze_jacobian(matrix, labels)
            d["vector"] = vector.tolist()
            diagnostics.append(d)

        fit = (mono_search if args.mode == "mono" else search)(
            initial,
            lower,
            upper,
            trust,
            evaluator,
            R,
            z,
            max_iterations=args.iterations,
            prefetch=evaluator.prefetch,
            inspect_jacobian=inspect,
        )
        save(
            out / "diagnostics" / f"{group}.json",
            dict(policy="report_only_no_automatic_freezing", iterations=diagnostics),
        )
        recipe = layout.recipe(fit.vector)
        recipe["source_camera_models"] = sorted({p["camera_model"] for p in train})
        recipe_path = out / "profiles" / f"{group}-{args.mode}.json"
        save(recipe_path, recipe)
        layout.oes(fit.vector, out / "profiles" / f"{group}-{args.mode}.oes")
        ablation_name = "zero_filter" if args.mode == "mono" else "zero_wheel"
        vectors = {}
        requests = []
        keys = []
        for p in members:
            start = layout.start(p["initial"])
            final = (
                layout.local(fit.vector, train.index(p))
                if p in train
                else np.r_[fit.vector[: layout.shared], p["initial"]]
            )
            style_only = np.r_[fit.vector[: layout.shared], p["initial"]]
            ablation = final.copy()
            ablation[: layout.wheel] = 0
            if args.mode == "mono":
                ablation[0] = 0
            vectors[p["id"]] = dict(
                baseline=start,
                fitted=final,
                profile_only=style_only,
            )
            vectors[p["id"]][ablation_name] = ablation
            for kind, v in vectors[p["id"]].items():
                requests.append((p, layout.settings(p, v, args.backend)))
                keys.append((p["id"], kind))
            adjustment = layout.adjustments(final, p)
            adjustment.update(
                photo=p["id"],
                role=p["role"],
                source="fitted_training_scene"
                if p["role"] == "train"
                else "declared_held_out_scene_unchanged",
            )
            save(out / "adjustments" / f"{p['id']}.json", adjustment)
            save(
                out / "settings" / f"{p['id']}.json",
                layout.settings(p, final, args.backend),
            )
        paths = renderer.render_many(requests)
        path_map = dict(zip(keys, paths))
        metrics = {}
        for p in members:
            mm = {
                kind: scorers[p["id"]].small(path_map[(p["id"], kind)])[1]
                for kind in vectors[p["id"]]
            }
            metrics[p["id"]] = dict(
                role=p["role"],
                preview=mm,
                **{
                    (
                        "filter_delta_e00_gain"
                        if args.mode == "mono"
                        else "wheel_delta_e00_gain"
                    ): mm[ablation_name]["delta_e00"] - mm["fitted"]["delta_e00"]
                },
                profile_only_delta_e00_gain=mm["baseline"]["delta_e00"]
                - mm["profile_only"]["delta_e00"],
            )
        # Only held-out candidates get full-resolution validation. Their reference
        # pixels are used for reporting, never for training or model selection.
        held = [p for p in members if p["role"] == "validation"]
        if held and not args.skip_full_validation:
            full_requests = []
            full_keys = []
            for p in held:
                for kind in ("baseline", "fitted", ablation_name):
                    full_requests.append(
                        (
                            p,
                            layout.settings(
                                p, vectors[p["id"]][kind], args.backend, full=True
                            ),
                        )
                    )
                    full_keys.append((p["id"], kind))
                save(
                    out / "settings" / f"{p['id']}-full.json",
                    layout.settings(
                        p, vectors[p["id"]]["fitted"], args.backend, full=True
                    ),
                )
            full_paths = dict(zip(full_keys, renderer.render_many(full_requests)))
            for p in held:
                cand = {
                    kind: full_paths[(p["id"], kind)]
                    for kind in ("baseline", "fitted", ablation_name)
                }
                full = scorers[p["id"]].full(cand["baseline"], cand)
                fm = full["metrics"]
                full["profile_delta_e00_gain"] = (
                    fm["baseline"]["delta_e00"] - fm["fitted"]["delta_e00"]
                )
                full[
                    "filter_delta_e00_gain"
                    if args.mode == "mono"
                    else "wheel_delta_e00_gain"
                ] = fm[ablation_name]["delta_e00"] - fm["fitted"]["delta_e00"]
                metrics[p["id"]]["full_resolution"] = full
        for p in members:
            mm = (
                metrics[p["id"]]
                .get("full_resolution", {})
                .get("metrics", metrics[p["id"]]["preview"])
            )
            contact_sheet(
                [
                    (scorers[p["id"]].target_small, "Reference target"),
                    (
                        scorers[p["id"]].comparison_rgb(mm["baseline"]["render"]),
                        "Initial / declared WB + EV",
                    ),
                    (
                        scorers[p["id"]].comparison_rgb(mm["fitted"]["render"]),
                        "Fitted style"
                        if p["role"] == "validation"
                        else "Style + fitted scene",
                    ),
                ],
                out / "comparisons" / f"{p['id']}.jpg",
            )
        full = [
            metrics[p["id"]]["full_resolution"]
            for p in held
            if "full_resolution" in metrics[p["id"]]
        ]
        status = (
            "not_tested"
            if not full
            else (
                "improved"
                if np.mean([x["profile_delta_e00_gain"] for x in full]) > 0
                else "did_not_improve"
            )
        )
        results[group] = dict(
            profile=recipe,
            profile_file=str(recipe_path),
            adjustment_files={
                p["id"]: str(out / "adjustments" / f"{p['id']}.json") for p in members
            },
            optimization=dict(
                vector_layout=(
                    "filter state, contrast, highlight, shadow, 4 per training photo"
                    if args.mode == "mono"
                    else f"{layout.wheel} wheel, 2 shared tone, 4 per training photo"
                ),
                vector=fit.vector.tolist(),
                objective=fit.objective,
                stop=fit.stop,
                history=fit.history,
                search_unique_renders=len(evaluator.requested),
            ),
            metrics=metrics,
            held_out_status=status,
            provisional=True,
            validation_policy="held-out scene fixed; no profile selection or refitting on validation references",
        )
    for p in pairs:
        for field in ("raw", "target"):
            if digest(p[field]) != p[field + "_hash"]:
                raise ValueError("Input changed during run")
    report = dict(
        schema="omfit/2",
        mode=args.mode,
        groups=results,
        engine=renderer.identity,
        inputs=pairs,
        renderer_versions=renderer.identities,
        mixed_renderer_versions=len(renderer.identities) > 1,
        invocation=renderer.invocation,
        actual_backends=sorted(renderer.used_backends),
        policy=dict(
            iterations=args.iterations,
            max_renders_override=args.max_renders,
            render_budget_per_training_photo=args.render_budget_per_photo,
            effective_group_budgets={
                g: request_budget(
                    args, sum(p["role"] == "train" for p in pairs if p["group"] == g)
                )
                for g in results
            },
            stopping="actual_no_improvement_or_request_budget",
            backend=args.backend,
            batch_size=args.batch_size,
            freeze_scene=args.freeze_scene,
            registration="identity" if args.identity_geometry else "features",
            mono_shading=0 if args.mode == "mono" else None,
            full_resolution_held_out=not args.skip_full_validation,
        ),
        cache_hits=renderer.hits,
        native_renders=renderer.calls,
        native_processes=renderer.native_processes,
        batches=renderer.batches,
        software=dict(
            sources=sources,
            lock_sha256=digest(Path(__file__).resolve().parents[2] / "uv.lock"),
            versions={
                n: importlib.metadata.version(n)
                for n in (
                    "numpy",
                    "scipy",
                    "Pillow",
                    "scikit-image",
                    "opencv-python-headless",
                )
            },
        ),
    )
    save(out / "result.json", report)
    print(
        canonical(
            dict(
                result=str(out / "result.json"),
                native_renders=renderer.calls,
                native_processes=renderer.native_processes,
                actual_backends=sorted(renderer.used_backends),
            )
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--output", required=True)
    parser.add_argument("--cache", required=True)
    parser.add_argument("--mode", choices=["stock", "hsl", "mono"], required=True)
    parser.add_argument("--renderer", default="omrender")
    parser.add_argument(
        "--build-dir", help="Resolved through omrender inspect when omitted"
    )
    parser.add_argument("--backend", choices=["auto", "cpu", "gpu"], default="gpu")
    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Safety cap; request budget and measured convergence govern stopping",
    )
    parser.add_argument(
        "--max-renders",
        type=int,
        default=None,
        help="Absolute per-group request cap, overriding the per-photo budget",
    )
    parser.add_argument("--render-budget-per-photo", type=int, default=200)
    parser.add_argument("--max-rss-mb", type=int, default=4096)
    parser.add_argument("--skip-full-validation", action="store_true")
    parser.add_argument(
        "--identity-geometry",
        action="store_true",
        help="Declare known pixel alignment for synthetic paired targets",
    )
    parser.add_argument(
        "--freeze-scene",
        action="store_true",
        help="Freeze declared per-photo WB/exposure for reusable-style qualification",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Maximum native jobs per GPU process (1..50)",
    )
    args = parser.parse_args()
    if (
        args.iterations < 0
        or (args.max_renders is not None and args.max_renders < 1)
        or args.render_budget_per_photo < 1
        or args.max_rss_mb < 256
        or not 1 <= args.batch_size <= 50
    ):
        parser.error("Invalid resource/search limits")
    run(args)


if __name__ == "__main__":
    main()
