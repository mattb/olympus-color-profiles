"""Content-addressed native batches with identity/readback verification."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from PIL import Image
from .color import rgb
from .model import NATURAL


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(",", ":"))


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def verify_readback(settings, report):
    if report.get("renderer_protocol") != "omrender-native/2":
        raise ValueError("Native renderer protocol mismatch")
    used = report["backend"]["used"]
    requested = settings["backend"]
    if used not in ("cpu", "gpu") or requested != "auto" and used != requested:
        raise ValueError("Actual renderer backend mismatch")
    c = report["current_parameters"]
    p = settings["profile"]
    o = settings["raw_overrides"]
    mono = p["kind"] == "stock_pen_f_mono"
    if mono:
        from .mono_model import verify_mono_readback

        verify_mono_readback(settings, report)
    for channel in ("saturation", "hue", "luminance"):
        r = c[channel]
        if (
            r["status"] != 0
            or r["mode"] != (0 if mono else 2)
            or r["values"] != p.get(channel, [0] * 12)
        ):
            raise ValueError("Native profile readback mismatch: " + channel)
    wb = c["custom_wb2"]
    ev = c["exposure_bias"]
    tone = c["tone_control"]
    if (
        (
            "white_balance_mode" in o
            and c["white_balance_mode"]["value"] != o["white_balance_mode"]
        )
        or ("custom_wb2" in o and wb["status"] != 0)
        or c["color_space_mode"]["value"] != 1
        or (
            "custom_wb2" in o
            and [wb["kelvin"], wb["ab_adjust"], wb["gm_adjust"]] != o["custom_wb2"]
        )
        or ev["numerator"] * o["exposure_bias"][1]
        != o["exposure_bias"][0] * ev["denominator"]
        or [tone["mode"], tone["bright"], tone["dark"]] != o["tone_control"][:3]
        or (
            len(o["tone_control"]) == 4
            and "tone_control_with_mid" in c
            and (
                c["tone_control_with_mid"]["status"] != 0
                or c["tone_control_with_mid"]["mid"] != o["tone_control"][3]
            )
        )
        or any(
            c[k]["status"] != 0
            for k in (
                "exposure_bias",
                "tone_control",
                "white_balance_mode",
                "color_space_mode",
            )
        )
        or report["bits"] != settings["output"]["bits"]
    ):
        raise ValueError("Native scene/tone readback mismatch")
    return used


class Renderer:
    def __init__(
        self, cli, cache, output, *, build_dir=None, max_rss_mb=4096, batch_size=50
    ):
        if type(batch_size) is not int or not 1 <= batch_size <= 50:
            raise ValueError("Native batch size must be between 1 and 50")
        self.batch_size = batch_size
        self.command = str(cli)
        self.explicit_build = build_dir
        self.cache = Path(cache).resolve()
        self.cache.mkdir(parents=True, exist_ok=True)
        self.output = Path(output)
        self.events = self.output / "events.jsonl"
        self.batch_dir = self.output / "batches"
        self.batch_dir.mkdir()
        self.hits = 0
        self.calls = 0
        self.native_processes = 0
        self.batches = []
        self.used_backends = set()
        self.max_rss_mb = max_rss_mb
        self.identities = []
        self.refresh_provenance()

    def refresh_provenance(self):
        # Observation only. Follow PATH and current defaults; never snapshot or
        # reject an update. Each batch records the build actually requested.
        resolved = shutil.which(self.command)
        if resolved is None and self.command == "omrender":
            candidate = Path(__file__).resolve().parents[3] / "omrender"
            if candidate.is_file() and (candidate.parent / "scripts/build.sh").is_file():
                resolved = str(candidate)
            else:
                raise ValueError("omrender was not found on PATH. Install the companion renderer from the source checkout, add it to PATH, or pass --renderer /absolute/path/to/omrender.")
        self.cli = Path(resolved or self.command).expanduser().resolve()
        if not self.cli.is_file():
            raise ValueError(f"Renderer executable was not found: {self.cli}. Install omrender or supply --renderer /absolute/path/to/omrender.")
        cmd = [str(self.cli), "inspect"]
        if self.explicit_build:
            cmd += [
                "--build-dir",
                str(Path(self.explicit_build).expanduser().resolve()),
            ]
        info = json.loads(subprocess.check_output(cmd))
        self.build_dir = Path(info["build_dir"]).resolve()
        self.native = Path(info["native_binary"]).resolve()
        self.identity = dict(
            inspect=info,
            launcher=str(self.cli),
            launcher_sha256=digest(self.cli),
            native_sha256=info["native_sha256"],
            natural_oes_sha256=digest(NATURAL),
        )
        if self.identity not in self.identities:
            self.identities.append(self.identity)
        self.invocation = dict(
            launcher=str(self.cli),
            build_dir=str(self.build_dir),
            native_binary=str(self.native),
            native_sha256=info["native_sha256"],
        )

    def key(self, pair, settings):
        return hashlib.sha256(
            canonical(
                dict(
                    schema="omfit-cache/2",
                    raw=pair["raw_hash"],
                    settings=settings,
                    engine=self.identity,
                )
            ).encode()
        ).hexdigest()

    def cached(self, pair, settings):
        d = self.cache / self.key(pair, settings)
        proof = d / "complete.json"
        out = d / "render.tif"
        if not proof.exists():
            return None
        x = json.loads(proof.read_text())
        if (
            digest(out) != x["sha256"]
            or digest(str(out) + ".json") != x["sidecar_sha256"]
        ):
            raise ValueError("Corrupt render cache: " + str(d))
        report = json.loads(Path(str(out) + ".json").read_text())
        used = verify_readback(settings, report)
        self.used_backends.add(used)
        return out

    def render_many(self, requests):
        self.refresh_provenance()
        unique = {self.key(p, s): (p, s) for p, s in requests}
        resolved = {}
        pending = []
        for key, (pair, settings) in unique.items():
            out = self.cached(pair, settings)
            if out is not None:
                self.hits += 1
                resolved[key] = out
                continue
            d = self.cache / key
            try:
                d.mkdir()
            except FileExistsError:
                raise RuntimeError(
                    "Incomplete or concurrent cache entry; inspect before removing: "
                    + str(d)
                )
            save(d / "settings.json", settings)
            out = d / "render.tif"
            resolved[key] = out
            pending.append((key, pair, settings, out))
        all_pending = pending
        for start in range(0, len(all_pending), self.batch_size):
            pending = all_pending[start : start + self.batch_size]
            number = len(self.batches)
            manifest = self.batch_dir / f"{number:04d}-jobs.json"
            report_path = self.batch_dir / f"{number:04d}-report.json"
            save(
                manifest,
                [
                    dict(
                        input=p["raw"],
                        settings=str(out.parent / "settings.json"),
                        output=str(out),
                    )
                    for _, p, _, out in pending
                ],
            )
            timeout = max(120, len(pending) * 30 + 30)
            cmd = [
                str(self.cli),
                "batch",
                str(manifest),
                "--report",
                str(report_path),
                "--build-dir",
                str(self.build_dir),
                "--timeout",
                str(timeout),
                "--max-rss-mb",
                str(self.max_rss_mb),
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout + 30
            )
            save(
                self.batch_dir / f"{number:04d}-command.json",
                dict(
                    command=cmd,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                ),
            )
            self.native_processes += 1
            if result.returncode:
                raise RuntimeError(
                    "Native batch failed: "
                    + str(self.batch_dir / f"{number:04d}-command.json")
                )
            native_reports = []
            # Validate the entire phase before marking any entry complete.
            for key, pair, settings, out in pending:
                data = json.loads(Path(str(out) + ".json").read_text())
                used = verify_readback(settings, data)
                if data["input"] != pair["raw"]:
                    raise ValueError("Native input mismatch")
                expected = settings["output"].get("resize", pair["developed_size"])
                with Image.open(out) as im:
                    if list(im.size) != expected:
                        raise ValueError("Native output dimensions mismatch")
                rgb(out)
                self.used_backends.add(used)
                native_reports.append(data)
            pids = {r["process_id"] for r in native_reports}
            if len(pids) != 1:
                raise ValueError("Batch did not use one persistent native process")
            for key, pair, settings, out in pending:
                save(
                    out.parent / "complete.json",
                    dict(
                        sha256=digest(out),
                        sidecar_sha256=digest(str(out) + ".json"),
                        native_sha256=self.identity["native_sha256"],
                    ),
                )
            summary = dict(
                report=str(report_path),
                jobs=len(pending),
                process_id=next(iter(pids)),
                invocation=dict(self.invocation),
                backends=[r["backend"]["used"] for r in native_reports],
                context_initialization_seconds=[
                    r["backend"].get("device", {}).get("context_initialization_seconds")
                    for r in native_reports
                ],
            )
            self.batches.append(summary)
            self.calls += len(pending)
        with self.events.open("a") as f:
            for p, s in requests:
                key = self.key(p, s)
                data = json.loads(Path(str(resolved[key]) + ".json").read_text())
                f.write(
                    canonical(
                        dict(
                            key=key,
                            output=str(resolved[key]),
                            backend=data["backend"]["used"],
                            process_id=data["process_id"],
                        )
                    )
                    + "\n"
                )
        return [resolved[self.key(p, s)] for p, s in requests]

    def render(self, pair, settings):
        return self.render_many([(pair, settings)])[0]
