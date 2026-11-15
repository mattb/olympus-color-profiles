"""Explicit camera-control layout and disjoint style/scene exports."""

from dataclasses import dataclass
import numpy as np
import xml.etree.ElementTree as ET
from pathlib import Path

NATURAL = Path(__file__).with_name("natural.oes")


@dataclass(frozen=True)
class Layout:
    mode: str

    def __post_init__(self):
        if self.mode not in ("stock", "hsl"):
            raise ValueError("mode must be stock or hsl")

    @property
    def wheel(self):
        return 12 if self.mode == "stock" else 36

    @property
    def shared(self):
        return self.wheel + 2

    @property
    def limit(self):
        return 5 if self.mode == "stock" else 7

    def local(self, vector, i):
        return np.r_[
            vector[: self.shared], vector[self.shared + 4 * i : self.shared + 4 * i + 4]
        ]

    def start(self, scene):
        return np.array([0] * self.shared + list(scene), dtype=int)

    def bounds(self, n):
        return (
            np.array([-self.limit] * self.wheel + [-7] * 2 + [20, -7, -7, -3] * n),
            np.array([self.limit] * self.wheel + [7] * 2 + [140, 7, 7, 3] * n),
            np.array([2] * self.shared + [5, 2, 2, 2] * n),
        )

    def profile(self, vector):
        p = dict(
            kind="stock_pen_f" if self.mode == "stock" else "firmware_hsl_research",
            mode="manual",
            saturation=list(map(int, vector[:12])),
        )
        if self.mode == "hsl":
            p.update(
                hue=list(map(int, vector[12:24])),
                luminance=list(map(int, vector[24:36])),
            )
        return p

    def recipe(self, vector):
        return dict(
            schema="omfit-profile/2",
            fitting_mode=self.mode,
            scope="shared_reusable_style",
            profile=self.profile(vector),
            finishing="Natural",
            tone_control=[1, int(vector[self.wheel]), int(vector[self.wheel + 1])],
            camera_firmware="stock"
            if self.mode == "stock"
            else "unofficial_hsl_required",
            physical_camera_validated=False,
            validation_status="provisional",
        )

    def adjustments(self, vector, pair=None):
        scene = vector[self.shared :]
        result = dict(
            schema="omfit-adjustments/2",
            scope="per_photo_only",
            white_balance_mode=4,
            custom_wb2=[int(scene[0]) * 100, int(scene[1]), int(scene[2])],
            exposure_bias=[int(scene[3]), 3],
        )

        if pair and pair.get("scene_wb_anchor") == "as_shot":
            result.pop("white_balance_mode")
            result.pop("custom_wb2")
            result["white_balance_anchor"] = "inherited_ORF_as_shot"
        return result

    def settings(self, pair, vector, backend, full=False):
        a = self.adjustments(vector, pair)
        overrides = dict(
            exposure_bias=a["exposure_bias"],
            tone_control=self.recipe(vector)["tone_control"],
            color_space_mode=1,
        )
        if "custom_wb2" in a:
            overrides.update(white_balance_mode=4, custom_wb2=a["custom_wb2"])
        output = dict(bits=8, rotate=pair["rotate"])
        if not full:
            output["resize"] = pair["resize"]
        return dict(
            schema="omrender/1",
            backend=backend,
            inherit="orf_shooting_parameters",
            decode_instructions=0,
            oes_file=str(NATURAL),
            profile=self.profile(vector),
            raw_overrides=overrides,
            output=output,
        )

    def oes(self, vector, output):
        tree = ET.parse(NATURAL)
        params = tree.getroot().find("Parameters")
        p = self.profile(vector)
        ET.SubElement(
            params,
            "ColorCreater2",
            Apply="true",
            Mode="Manual",
            SatValue=",".join(map(str, p["saturation"])),
            HueValue=",".join(map(str, p.get("hue", [0] * 12))),
            LumValue=",".join(map(str, p.get("luminance", [0] * 12))),
        )
        ET.SubElement(
            params,
            "ToneControl",
            Apply="true",
            Mode="Manual",
            Bright=str(vector[self.wheel]),
            Dark=str(vector[self.wheel + 1]),
        )
        tree.write(output, encoding="UTF-8", xml_declaration=True)
