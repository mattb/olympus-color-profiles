"""Reproducible native experiments on seeded RAW -> known-film-LUT pairs."""

import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import os

for _thread_variable in (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ.setdefault(_thread_variable, "1")
import time
import numpy as np
from PIL import Image
from .cli import Evaluator
from .color import rgb, SRGB
from .dataset_integrity import input_checksums, verify_checksums
from .experimental import screen_policies, run_strategy
from .model import Layout
from .observability import analyze_jacobian
from .renderer import Renderer, save, digest, canonical
from .scoring import resize_long
from .scoring_experiments import ExperimentalScorer


def controlled_bounds(layout, n_images, hsl_saturation_limit=None):
    """Experimental HSL S-range control; leave H/L, tone and scene bounds intact."""
    if hsl_saturation_limit not in (None, 5, 7):
        raise ValueError("HSL saturation limit must be 5 or 7")
    lower, upper, trust = layout.bounds(n_images)
    if layout.mode == "hsl" and hsl_saturation_limit is not None:
        lower[:12] = -hsl_saturation_limit
        upper[:12] = hsl_saturation_limit
    return lower, upper, trust


def controlled_policy(policy, layout, match_stock_wheel_penalty=False):
    """Match each HSL wheel coefficient to stock's per-control regularization."""
    if layout.mode == "hsl" and match_stock_wheel_penalty:
        channels = layout.wheel // 12
        return replace(policy, wheel_l2=policy.wheel_l2 * channels,
                       wheel_smooth=policy.wheel_smooth * channels)
    return policy


def preview(target, path):
    if not path.exists():
        Image.fromarray(resize_long(rgb(target))).save(path, icc_profile=SRGB)
    return str(path)


def completed_case(path, expected):
    """Resume only an identical experiment, independently of renderer updates."""
    record = json.loads(Path(path).read_text())
    # Legacy records predate the optional controls and used full HSL bounds and
    # the standard prior. Compare those effective defaults too: omitting a flag
    # must not silently resume a completed constrained experiment.
    legacy_defaults = dict(hsl_saturation_limit=7, match_stock_wheel_penalty=False)
    mismatches = [
        k for k, value in expected.items()
        if record.get(k, legacy_defaults.get(k)) != value
    ]
    if mismatches:
        raise ValueError(
            f"Completed experiment differs ({', '.join(mismatches)}): {path}. "
            "Use a new output directory."
        )
    return record


def run(args):
    dataset = Path(args.dataset).resolve()
    data = json.loads(dataset.read_text())
    dataset_sha256 = digest(dataset)
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    previous_plan = out / "predeclared-policy.json"
    if previous_plan.exists():
        completed_case(previous_plan, {"dataset_sha256": dataset_sha256})
    previews = out / "target-previews"
    previews.mkdir(exist_ok=True)
    start = time.monotonic()
    looks = [
        x
        for x in data["looks"]
        if x["ready"] and (not args.looks or x["id"] in args.looks.split(","))
    ]
    if not looks:
        raise ValueError("No requested complete look is available")
    selected_pairs = [
        p
        for p in data["pairs"]
        if not args.cameras or p["camera"] in args.cameras.split(",")
    ]
    checksums = input_checksums(selected_pairs, looks)
    checksums[str(dataset)] = dataset_sha256
    verify_checksums(checksums)
    save(
        out / "predeclared-policy.json",
        dict(
            dataset=str(dataset),
            dataset_sha256=dataset_sha256,
            phase="final_test" if args.evaluate_test else "development_only",
            cameras=args.cameras,
            modes=args.modes,
            policies=args.policies,
            stock_budget_per_image=args.stock_budget,
            hsl_budget_per_image=args.hsl_budget,
            hsl_saturation_limit=getattr(args, "hsl_saturation_limit", None),
            match_stock_wheel_penalty=getattr(args, "match_stock_wheel_penalty", False),
            decision_rule="Dev mean DeltaE00, equal camera/look weighting; promote only after independent full-resolution test. Test is not read during screen.",
            primary_train="first randomly drawn representative per whole training scene_group",
            scene="known WB/EV frozen unless explicit ablation",
            geometry="known identity; target full-native baseline -> LUT -> full PNG -> preview",
            reference_metric="192x192 unblurred spatial DeltaE00 independent of fitting loss/grid",
            minimum_relative_improvement=0.01,
            maximum_per_case_regression=0.05,
        ),
    )
    results = []
    for look in looks:
        for camera in sorted({p["camera"] for p in data["pairs"]}):
            if args.cameras and camera not in args.cameras.split(","):
                continue
            members = [
                dict(p, target=look["targets"][p["id"]])
                for p in data["pairs"]
                if p["camera"] == camera
            ]
            representatives = {}
            for p in sorted(members, key=lambda p: p["draw_order"]):
                if p["role"] in ("train", "dev"):
                    representatives.setdefault(p["scene_group"], p)
            cv_group = None
            if args.cv_fold is not None:
                groups = list(representatives)
                if not 0 <= args.cv_fold < len(groups):
                    continue
                cv_group = groups[args.cv_fold]
                train = [p for g, p in representatives.items() if g != cv_group]
                held = [
                    p
                    for p in members
                    if p["role"] in ("train", "dev") and p["scene_group"] == cv_group
                ]
            elif args.evaluate_test:
                train = list(representatives.values())
                held = [p for p in members if p["role"] == "test"]
            else:
                train = [p for p in members if p["primary_train"]]
                held = [p for p in members if p["role"] == "dev"]
            if not train or not held:
                raise ValueError(
                    "Each camera needs independent training and evaluation data"
                )
            # Preview files derive from FULL LUT targets, never LUT(resize(input)).
            for p in train + held:
                p["target_preview"] = preview(
                    p["target"], previews / f"{look['id']}--{p['id']}.png"
                )
            for mode in args.modes.split(","):
                layout = Layout(mode)
                budget = args.stock_budget if mode == "stock" else args.hsl_budget
                policies = screen_policies(render_budget_per_image=budget)
                if args.policies:
                    policies = [
                        p for p in policies if p.name in args.policies.split(",")
                    ]
                for policy in policies:
                    policy = controlled_policy(policy, layout, getattr(args, "match_stock_wheel_penalty", False))
                    if args.one_iteration_screen and policy.strategy == "original":
                        policy = replace(policy, coarse_iterations=1)
                    case = out / f"{look['id']}--{camera}--{mode}--{policy.name}"
                    expected = dict(
                        source_data_hash=dataset_sha256,
                        policy=asdict(policy),
                        camera=camera,
                        look=look["id"],
                        mode=mode,
                        training_ids=[p["id"] for p in train],
                        evaluation_split="test" if args.evaluate_test else "dev",
                        cross_validation_group=cv_group,
                    )
                    if mode == "hsl":
                        expected["hsl_saturation_limit"] = getattr(args, "hsl_saturation_limit", None) or 7
                        expected["match_stock_wheel_penalty"] = getattr(args, "match_stock_wheel_penalty", False)
                    if (case / "result.json").exists():
                        record = completed_case(case / "result.json", expected)
                        if set(record["metrics"]) != {p["id"] for p in held}:
                            raise ValueError(
                                f"Completed evaluation set differs: {case}"
                            )
                        results.append(record)
                        continue
                    case.mkdir()
                    renderer = Renderer(
                        args.renderer, args.cache, case, max_rss_mb=4096
                    )
                    scorers = {
                        p["id"]: ExperimentalScorer(
                            p["baseline_preview"],
                            p["target_preview"],
                            **policy.score_options(),
                        )
                        for p in train
                    }
                    initial = np.array(
                        [0] * layout.shared + sum([p["initial"] for p in train], []),
                        dtype=int,
                    )
                    lower, upper, trust = controlled_bounds(
                        layout, len(train), getattr(args, "hsl_saturation_limit", None)
                    )
                    R, z = policy.make_regularizer(
                        len(train), initial, wheel_channels=layout.wheel // 12
                    )
                    evaluator = Evaluator(
                        renderer, layout, train, scorers, "gpu", len(train) * budget
                    )
                    diagnostics = []

                    def inspect(vector, matrix):
                        d = analyze_jacobian(matrix)
                        d["vector"] = vector.tolist()
                        d["fixed_scene_indices"] = (
                            list(range(layout.shared, len(vector)))
                            if policy.scene_mode == "frozen"
                            else []
                        )
                        diagnostics.append(d)

                    evaluator.inspect_jacobian = inspect
                    fit = run_strategy(
                        policy, initial, lower, upper, trust, evaluator, R, z
                    )
                    save(case / "profile.json", layout.recipe(fit.vector))
                    layout.oes(fit.vector, case / "profile.oes")
                    adjdir = case / "adjustments"
                    adjdir.mkdir()
                    for i, p in enumerate(train):
                        save(
                            adjdir / f"{p['id']}.json",
                            layout.adjustments(layout.local(fit.vector, i), p),
                        )
                    requests = [
                        (
                            p,
                            layout.settings(
                                p,
                                np.r_[fit.vector[: layout.shared], p["initial"]],
                                "gpu",
                            ),
                        )
                        for p in held
                    ]
                    paths = renderer.render_many(requests)
                    metrics = {}
                    for p, path in zip(held, paths):
                        scorer = ExperimentalScorer(
                            p["baseline_preview"],
                            p["target_preview"],
                            size=192,
                            blur=0,
                            loss="lab",
                        )
                        _, base = scorer.small(p["baseline_preview"])
                        _, fitted = scorer.small(path)
                        metrics[p["id"]] = dict(
                            baseline=base,
                            fitted=fitted,
                            role=p["role"],
                            scene_group=p["scene_group"],
                        )
                    record = dict(
                        schema="omfit-experiment/1",
                        look=look["id"],
                        look_reference=look["reference"],
                        camera=camera,
                        mode=mode,
                        policy=asdict(policy),
                        training_ids=[p["id"] for p in train],
                        training_scene_count=len({p["scene_group"] for p in train}),
                        evaluation_split="test" if args.evaluate_test else "dev",
                        cross_validation_group=cv_group,
                        metrics=metrics,
                        mean_delta_e00=float(
                            np.mean(
                                [m["fitted"]["delta_e00"] for m in metrics.values()]
                            )
                        ),
                        mean_baseline_delta_e00=float(
                            np.mean(
                                [m["baseline"]["delta_e00"] for m in metrics.values()]
                            )
                        ),
                        vector=fit.vector.tolist(),
                        objective=fit.objective,
                        stop=fit.stop,
                        stages=fit.stages,
                        cost=fit.cost,
                        observability=diagnostics,
                        native_renders=renderer.calls,
                        native_processes=renderer.native_processes,
                        renderer_versions=renderer.identities,
                        batches=renderer.batches,
                        profile=str(case / "profile.json"),
                        source_data_hash=dataset_sha256,
                    )
                    for constraint in ("hsl_saturation_limit", "match_stock_wheel_penalty"):
                        if constraint in expected:
                            record[constraint] = expected[constraint]
                    verify_checksums(checksums)
                    save(case / "result.json", record)
                    results.append(record)
                    save(
                        out / "progress.json",
                        dict(
                            completed_cases=len(results),
                            last_case=case.name,
                            last_dev_delta_e00=record["mean_delta_e00"],
                            elapsed_seconds=time.monotonic() - start,
                        ),
                    )
                    print(
                        canonical(
                            dict(
                                case=case.name,
                                delta_e00=record["mean_delta_e00"],
                                native_renders=renderer.calls,
                                requests=fit.cost,
                            )
                        ),
                        flush=True,
                    )
    verify_checksums(checksums)
    save(
        out / "results.json",
        dict(cases=results, elapsed_seconds=time.monotonic() - start),
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dataset")
    p.add_argument("--output", required=True)
    p.add_argument("--cache", required=True)
    p.add_argument("--looks")
    p.add_argument("--cameras")
    p.add_argument("--modes", default="stock,hsl")
    p.add_argument("--policies")
    p.add_argument("--renderer", default="omrender")
    p.add_argument("--stock-budget", type=int, default=64)
    p.add_argument("--hsl-budget", type=int, default=160)
    p.add_argument("--match-stock-wheel-penalty", action="store_true",
                   help="Experimental HSL wheel penalties×3 so each control matches stock regularization")
    p.add_argument("--hsl-saturation-limit", type=int, choices=(5, 7),
                   help="Experimental HSL saturation bound; H/L stay ±7, default unchanged ±7")
    p.add_argument(
        "--cv-fold",
        type=int,
        help="Leave one whole train/dev scene out; final test remains untouched",
    )
    p.add_argument("--one-iteration-screen", action="store_true")
    p.add_argument("--evaluate-test", action="store_true")
    run(p.parse_args())


if __name__ == "__main__":
    main()
