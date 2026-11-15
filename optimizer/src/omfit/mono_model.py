"""Native PEN-F MONO layout; categorical filters never imply a color distance."""

from dataclasses import dataclass
import xml.etree.ElementTree as ET
import numpy as np
from .model import Layout

FILTER_COLORS = (
    "red",
    "orange",
    "yellow",
    "yellow-green",
    "green",
    "cyan",
    "blue",
    "magenta",
)
FILTER_STATES = (("off", 0),) + tuple(
    (color, strength) for color in FILTER_COLORS for strength in (1, 2, 3)
)
FILTER_ROTATIONS = {
    "off": 0,
    "yellow": 1,
    "orange": 2,
    "red": 3,
    "magenta": 4,
    "blue": 5,
    "cyan": 6,
    "green": 7,
    "yellow-green": 8,
}


@dataclass(frozen=True)
class MonoLayout:
    """[filter_index, contrast, highlight, shadow] then each photo's scene4.

    Enumerate filter states explicitly, fixing the categorical coordinate's
    bound during continuous/local integer optimization. No finite differences
    or smoothing across neighboring filter indices are meaningful.
    """

    mode: str = "mono"
    shared: int = 4
    wheel: int = 0

    local = Layout.local
    adjustments = Layout.adjustments

    def start(self, scene):
        return np.array([0] * self.shared + list(scene), dtype=int)

    def bounds(self, n):
        return (
            np.array([0, -2, -7, -7] + [20, -7, -7, -3] * n),
            np.array([24, 2, 7, 7] + [140, 7, 7, 3] * n),
            np.array([1, 1, 2, 2] + [5, 2, 2, 2] * n),
        )

    def profile(self, vector):
        index = vector[0]
        if index != int(index) or not 0 <= index < len(FILTER_STATES):
            raise ValueError("MONO filter index must be an integer in0..24")
        color, strength = FILTER_STATES[int(index)]
        if vector[1] != int(vector[1]) or not -2 <= vector[1] <= 2:
            raise ValueError("MONO contrast must be an integer in-2..2")
        return dict(
            kind="stock_pen_f_mono",
            mode="manual",
            color_filter=dict(color=color, strength=strength),
            grain="off",
            toning="neutral",
            shading=0,
            contrast=int(vector[1]),
            sharpness=0,
        )

    def recipe(self, vector):
        return dict(
            schema="omfit-profile/2",
            fitting_mode="mono",
            scope="shared_reusable_style",
            profile=self.profile(vector),
            finishing="Natural",
            tone_control=[1, int(vector[2]), int(vector[3]), 0],
            camera_firmware="stock",
            physical_camera_validated=False,
            validation_status="provisional",
            shading_policy="fixed_zero",
        )

    def settings(self, pair, vector, backend, full=False):
        scene = self.adjustments(vector, pair)
        overrides = dict(
            exposure_bias=scene["exposure_bias"],
            tone_control=self.recipe(vector)["tone_control"],
            color_space_mode=1,
        )
        if "custom_wb2" in scene:
            overrides.update(white_balance_mode=4, custom_wb2=scene["custom_wb2"])
        output = dict(bits=8, rotate=pair["rotate"])
        if not full:
            output["resize"] = pair["resize"]
        return dict(
            schema="omrender/1",
            backend=backend,
            inherit="orf_shooting_parameters",
            decode_instructions=0,
            profile=self.profile(vector),
            raw_overrides=overrides,
            output=output,
        )

    def regularizer(self, n_images, initial):
        from .mono import regularizer

        return regularizer(n_images, initial)

    def oes(self, vector, output):
        root = ET.Element("ImageProcessing")
        ET.SubElement(
            root, "ParametersType", FormatID="65539", Platform="M", Version="2502"
        )
        params = ET.SubElement(root, "Parameters")
        ET.SubElement(params, "FinishingMode", Apply="true", Mode="Natural")
        ET.SubElement(params, "ColorCreater", Mode="Off")
        ET.SubElement(params, "ColorCreater2", Mode="Off")
        p = self.profile(vector)
        f = p["color_filter"]
        ET.SubElement(
            params,
            "MonochroCreater",
            Mode="Manual",
            SatValue=str(f["strength"]),
            HueValue=str(FILTER_ROTATIONS[f["color"]]),
            Graininess="0",
            ColorTone="1",
        )
        for tag, value in (("Contrast", p["contrast"]), ("Sharpness", 0)):
            ET.SubElement(
                params, tag, Apply="true", Mode="Manual", Value=str(value), Adjust="0"
            )
        ET.SubElement(params, "ShadingCreator", Apply="true", Mode="Manual", Value="0")
        ET.SubElement(
            params,
            "ToneControl",
            Apply="true",
            Mode="Manual",
            Bright=str(vector[2]),
            Dark=str(vector[3]),
            Mid="0",
        )
        ET.ElementTree(root).write(output, encoding="UTF-8", xml_declaration=True)


def verify_mono_readback(settings, report):
    """Check actual native family/filter/style, never requested-JSON echoes."""
    p = settings["profile"]
    if (
        p["shading"] != 0
        or p["grain"] != "off"
        or p["toning"] != "neutral"
        or p["sharpness"] != 0
    ):
        raise ValueError(
            "Optimizer MONO requires zero shading/sharpness, grain off and neutral toning"
        )
    m = report["mono_parameters"]
    if (
        report.get("profile_kind") != "stock_pen_f_mono"
        or m["active_processing_family"] != "native_monochrome_profile"
        or m["get_parameters_status"] != 0
        or m["finishing_mode"] != dict(status=0, value=2)
    ):
        raise ValueError("Native MONO processing family mismatch")
    f = p["color_filter"]
    actual = m["monochrome"]
    if (
        actual["status"] != 0
        or actual["mode"] != 2
        or actual["radial"] != f["strength"]
        or actual["rotation"] != FILTER_ROTATIONS[f["color"]]
        or actual["filter_color"] != f["color"]
        or actual["strength"] != f["strength"]
    ):
        raise ValueError("Native MONO filter readback mismatch")
    for key in ("contrast", "sharpness"):
        if m[key] != dict(status=0, mode=1, value=p[key], adjust=0):
            raise ValueError("Native MONO readback mismatch: " + key)
    for key, value in (
        ("grain", 0),
        ("toning", 2),
        ("creative_shading", 0),
        ("legacy_monochro_shading", 0),
    ):
        if m[key] != dict(status=0, mode=2, value=value):
            raise ValueError("Native MONO readback mismatch: " + key)
    stage = report["mono_creative_shading_stage"]
    if stage["applied"] or stage["value"] != 0:
        raise ValueError("Native MONO nonzero shading stage")
