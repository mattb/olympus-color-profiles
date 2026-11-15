"""Deterministic Adobe Camera Raw sidecars and reusable Develop presets."""

import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

CRS = "http://ns.adobe.com/camera-raw-settings/1.0/"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
ET.register_namespace("x", "adobe:ns:meta/")
ET.register_namespace("rdf", RDF)
ET.register_namespace("crs", CRS)
SCENE_KEYS = {"WhiteBalance", "Temperature", "Tint", "Exposure2012"}


def base_settings(mode="mono"):
    if mode not in ("mono", "color"):
        raise ValueError("mode must be mono or color")
    settings = dict(
        Version="16.5",
        ProcessVersion="11.0",
        HasSettings=True,
        CameraProfile="Adobe Standard",
        ConvertToGrayscale=mode == "mono",
        Contrast2012=0,
        Highlights2012=0,
        Shadows2012=0,
        Whites2012=0,
        Blacks2012=0,
        Clarity2012=0,
        Texture=0,
        Dehaze=0,
        Sharpness=0,
        LuminanceSmoothing=0,
        ColorNoiseReduction=0,
        PostCropVignetteAmount=0,
        GrainAmount=0,
        LensProfileEnable=0,
        AutoLateralCA=0,
        ToneCurveName2012="Linear",
        ToneCurvePV2012=["0, 0", "255, 255"],
    )
    if mode == "mono":
        for c in (
            "Red",
            "Orange",
            "Yellow",
            "Green",
            "Aqua",
            "Blue",
            "Purple",
            "Magenta",
        ):
            settings["GrayMixer" + c] = 0
    else:
        settings.update(Vibrance=0, Saturation=0)
        for prefix in ("HueAdjustment", "SaturationAdjustment", "LuminanceAdjustment"):
            for c in ("Red", "Orange", "Yellow", "Green", "Aqua", "Blue", "Purple", "Magenta"):
                settings[prefix + c] = 0
    return settings


def _tree(settings):
    root = ET.Element("{adobe:ns:meta/}xmpmeta")
    rdf = ET.SubElement(root, "{" + RDF + "}RDF")
    desc = ET.SubElement(rdf, "{" + RDF + "}Description", {"{" + RDF + "}about": ""})
    for key, value in sorted(settings.items()):
        if not key.replace("_", "").isalnum():
            raise ValueError("Invalid CRS key")
        if isinstance(value, (list, tuple)):
            seq = ET.SubElement(
                ET.SubElement(desc, "{" + CRS + "}" + key), "{" + RDF + "}Seq"
            )
            for item in value:
                ET.SubElement(seq, "{" + RDF + "}li").text = str(item)
        else:
            desc.set(
                "{" + CRS + "}" + key,
                "True" if value is True else "False" if value is False else str(value),
            )
    return ET.ElementTree(root), desc


def write_sidecar(path, settings):
    tree, _ = _tree(settings)
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def write_preset(path, settings, name):
    shared = {k: v for k, v in settings.items() if k not in SCENE_KEYS}
    shared.update(
        PresetType="Normal",
        Cluster="",
        UUID=uuid.uuid5(
            uuid.NAMESPACE_URL, json.dumps(shared, sort_keys=True)
        ).hex.upper(),
        SupportsAmount=False,
        SupportsColor=True,
        SupportsMonochrome=True,
        SupportsHighDynamicRange=True,
        SupportsNormalDynamicRange=True,
        SupportsSceneReferred=True,
        SupportsOutputReferred=True,
    )
    tree, desc = _tree(shared)
    for key, value in [("Name", name), ("Group", "OM Fit")]:
        alt = ET.SubElement(
            ET.SubElement(desc, "{" + CRS + "}" + key), "{" + RDF + "}Alt"
        )
        ET.SubElement(
            alt,
            "{" + RDF + "}li",
            {"{http://www.w3.org/XML/1998/namespace}lang": "x-default"},
        ).text = value
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def read_settings(path):
    desc = ET.parse(path).find(".//{" + RDF + "}Description")
    if desc is None:
        raise ValueError("Missing XMP description")
    result = {
        k[len(CRS) + 2 :]: v
        for k, v in desc.attrib.items()
        if k.startswith("{" + CRS + "}")
    }
    for child in desc:
        seq = child.find("{" + RDF + "}Seq")
        if seq is not None:
            result[child.tag[len(CRS) + 2 :]] = [x.text for x in seq]
    return result


def read_preset(path):
    """Recover this feature's supported Develop values from an exported preset."""
    values = read_settings(path)
    known = base_settings(
        "mono" if values.get("ConvertToGrayscale") == "True" else "color"
    )
    result = {}
    for key, default in known.items():
        if key not in values:
            raise ValueError("Preset missing explicit base control: " + key)
        value = values[key]
        if isinstance(default, bool):
            if value not in ("True", "False"):
                raise ValueError("Invalid boolean " + key)
            value = value == "True"
        elif isinstance(default, int):
            value = int(value)
        result[key] = value
    if SCENE_KEYS & values.keys():
        raise ValueError("Reusable preset contains scene adjustments")
    return result
