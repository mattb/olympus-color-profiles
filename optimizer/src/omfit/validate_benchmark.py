"""Full-resolution held-out comparison of already selected benchmark candidates."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import numpy as np
from PIL import Image
from .model import Layout
from .renderer import Renderer, save, digest, canonical
from .scoring_experiments import ExperimentalScorer
from .color import contact_sheet
from .dataset_integrity import input_checksums, verify_checksums


def decoded_equal(a, b):
    with Image.open(a) as x, Image.open(b) as y:
        return (
            x.size == y.size
            and x.mode == y.mode
            and x.tobytes() == y.tobytes()
            and x.info.get("icc_profile") == y.info.get("icc_profile")
        )


def run(args):
    data = json.loads(Path(args.dataset).read_text())
    dataset_sha256 = digest(args.dataset)
    records = [json.loads(Path(p).read_text()) for p in args.results]
    if any(r.get("source_data_hash") != dataset_sha256 for r in records):
        raise ValueError("Candidate source_data_hash differs from supplied dataset")
    scope = {(r["camera"], r["look"], r["mode"]) for r in records}
    if len(scope) != 1:
        raise ValueError("Full comparison requires same camera/look/mode")
    camera, look_id, mode = next(iter(scope))
    layout = Layout(mode)
    look = next(l for l in data["looks"] if l["id"] == look_id)
    ids = set(records[0]["metrics"])
    if any(set(r["metrics"]) != ids for r in records):
        raise ValueError("Candidate evaluation sets differ")
    pairs = [
        dict(p, target=look["targets"][p["id"]])
        for p in data["pairs"]
        if p["id"] in ids
    ]
    checksums = input_checksums(pairs, [look])
    checksums[str(Path(args.dataset).resolve())] = dataset_sha256
    verify_checksums(checksums)
    eligibility = (
        json.loads(Path(args.eligibility).read_text()) if args.eligibility else {}
    )
    primary = set(eligibility.get("primary_independent_test_ids", ids))
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    renderer = Renderer(args.renderer, args.cache, out, max_rss_mb=4096)
    requests = []
    keys = []
    for p in pairs:
        requests.append(
            (p, layout.settings(p, layout.start(p["initial"]), "gpu", full=True))
        )
        keys.append((p["id"], "baseline"))
        for r in records:
            name = r["policy"]["name"]
            v = np.r_[r["vector"][: layout.shared], p["initial"]]
            requests.append((p, layout.settings(p, v, "gpu", full=True)))
            keys.append((p["id"], name))
    paths = dict(zip(keys, renderer.render_many(requests)))
    metrics = {}
    for p in pairs:
        scorer = ExperimentalScorer(
            p["baseline_preview"], p["target"], size=192, blur=0
        )
        candidates = {
            name: paths[(p["id"], name)] for id, name in keys if id == p["id"]
        }
        full = scorer.full(candidates["baseline"], candidates)
        full["primary_independent"] = p["id"] in primary
        full["scene_group"] = p["scene_group"]
        full["original_baseline_pixels_and_icc_equal"] = decoded_equal(
            candidates["baseline"], p["baseline_full"]
        )
        metrics[p["id"]] = full
        contact_sheet(
            [(p["target"], look["reference"] + " target")]
            + [(candidates[r["policy"]["name"]], r["policy"]["name"]) for r in records],
            out / (p["id"] + ".jpg"),
        )
    summary = {}
    for r in records:
        name = r["policy"]["name"]
        groups = defaultdict(list)
        for id, m in metrics.items():
            if m["primary_independent"]:
                groups[m["scene_group"]].append(m["metrics"][name]["delta_e00"])
        summary[name] = dict(
            primary_image_mean_delta_e00=float(
                np.mean(
                    [
                        m["metrics"][name]["delta_e00"]
                        for m in metrics.values()
                        if m["primary_independent"]
                    ]
                )
            ),
            primary_scene_mean_delta_e00=float(
                np.mean([np.mean(v) for v in groups.values()])
            ),
            primary_frames=sum(len(v) for v in groups.values()),
            primary_groups=len(groups),
        )
    names = [r["policy"]["name"] for r in records]
    decision = {}
    if len(names) == 2:
        a, b = names
        pa = summary[a]["primary_scene_mean_delta_e00"]
        pb = summary[b]["primary_scene_mean_delta_e00"]
        ratios = [
            m["metrics"][b]["delta_e00"] / max(m["metrics"][a]["delta_e00"], 1e-12) - 1
            for m in metrics.values()
            if m["primary_independent"]
        ]
        improvement = 1 - pb / max(pa, 1e-12)
        worst = max(ratios)
        decision = dict(
            baseline_policy=a,
            candidate_policy=b,
            relative_scene_mean_improvement=improvement,
            worst_primary_frame_relative_regression=worst,
            passes_predeclared_quality_gate=improvement >= 0.01 and worst <= 0.05,
            original_baselines_unchanged=all(
                m["original_baseline_pixels_and_icc_equal"] for m in metrics.values()
            ),
        )
    report = dict(
        schema="omfit-full-benchmark/1",
        camera=camera,
        look=look_id,
        mode=mode,
        metrics=metrics,
        summary=summary,
        decision=decision,
        native_renders=renderer.calls,
        native_processes=renderer.native_processes,
        renderer_versions=renderer.identities,
        candidate_results=[str(Path(p).resolve()) for p in args.results],
        source_manifest_sha256=dataset_sha256,
        eligibility=eligibility,
    )
    verify_checksums(checksums)
    save(out / "result.json", report)
    print(
        canonical(
            dict(result=str(out / "result.json"), summary=summary, decision=decision)
        )
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("dataset")
    p.add_argument("results", nargs="+")
    p.add_argument("--output", required=True)
    p.add_argument("--cache", required=True)
    p.add_argument("--eligibility")
    p.add_argument("--renderer", default="omrender")
    run(p.parse_args())


if __name__ == "__main__":
    main()
