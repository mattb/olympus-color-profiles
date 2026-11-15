"""Isolated Adobe DNG Converter rendering; generated previews, never camera thumbnails."""

import io
from functools import lru_cache
import json
import plistlib
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image, ImageCms
import numpy as np
from .color import SRGB
from .renderer import digest, canonical, save

DEFAULT_CONVERTER = (
    "/Applications/Adobe DNG Converter.app/Contents/MacOS/Adobe DNG Converter"
)


@lru_cache(maxsize=1)
def gray_profile_bytes():
    # Build exact gamma2.2/D50 gray ICC: macOS's similarly named profile is
    # effectively sRGB TRC on this machine and is not a pure gamma2.2 profile.
    import ctypes
    import ctypes.util

    library = ctypes.util.find_library("lcms2")
    if not library:
        raise RuntimeError("Adobe rendering requires LittleCMS2 (install with: brew install little-cms2); other fitting modes do not need this optional dependency")
    lib = ctypes.CDLL(library)

    class xyY(ctypes.Structure):
        _fields_ = [
            ("x", ctypes.c_double),
            ("y", ctypes.c_double),
            ("Y", ctypes.c_double),
        ]

    lib.cmsBuildGamma.argtypes = [ctypes.c_void_p, ctypes.c_double]
    lib.cmsBuildGamma.restype = ctypes.c_void_p
    lib.cmsCreateGrayProfile.argtypes = [ctypes.POINTER(xyY), ctypes.c_void_p]
    lib.cmsCreateGrayProfile.restype = ctypes.c_void_p
    lib.cmsSaveProfileToMem.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
    ]
    lib.cmsCloseProfile.argtypes = [ctypes.c_void_p]
    lib.cmsFreeToneCurve.argtypes = [ctypes.c_void_p]
    curve = lib.cmsBuildGamma(None, 2.2)
    if not curve:
        raise RuntimeError("Could not create gamma curve")
    profile = lib.cmsCreateGrayProfile(ctypes.byref(xyY(0.3457, 0.3585, 1)), curve)
    if not profile:
        lib.cmsFreeToneCurve(curve)
        raise RuntimeError("Could not create gray profile")
    try:
        size = ctypes.c_uint32()
        lib.cmsSaveProfileToMem(profile, None, ctypes.byref(size))
        buf = ctypes.create_string_buffer(size.value)
        if not lib.cmsSaveProfileToMem(profile, buf, ctypes.byref(size)):
            raise RuntimeError("Gray ICC creation failed")
        data = bytearray(buf.raw)
        data[24:36] = SRGB[24:36]
        data[84:100] = bytes(16)
        return bytes(data)
    finally:
        lib.cmsCloseProfile(profile)
        lib.cmsFreeToneCurve(curve)




def write_settings(path, settings):
    from .adobe_xmp import write_sidecar

    write_sidecar(path, settings)


def _equivalent(a, b):
    if isinstance(b, bool):
        return str(a).lower() in (("true", "1") if b else ("false", "0"))
    if isinstance(b, (int, float)):
        try:
            return abs(float(a) - b) < 1e-6
        except (ValueError, TypeError):
            return False
    if isinstance(b, list):
        values = a if isinstance(a, list) else [v.strip() for v in str(a).split(",")]
        return values == b
    return str(a) == str(b)


def orient_preview(image, metadata):
    orientation = metadata.get("IFD0:Orientation", 1)
    transforms = {
        2: Image.Transpose.FLIP_LEFT_RIGHT,
        3: Image.Transpose.ROTATE_180,
        4: Image.Transpose.FLIP_TOP_BOTTOM,
        5: Image.Transpose.TRANSPOSE,
        6: Image.Transpose.ROTATE_270,
        7: Image.Transpose.TRANSVERSE,
        8: Image.Transpose.ROTATE_90,
    }
    if orientation == 1:
        return image
    if orientation not in transforms:
        raise ValueError("Unsupported DNG orientation")
    return image.transpose(transforms[orientation])


def canonical_preview(jpeg, metadata):
    """Interpret the generated-preview color space before converting to sRGB."""
    with Image.open(io.BytesIO(jpeg)) as im:
        space = metadata["SubIFD2:PreviewColorSpace"]
        if metadata.get("SubIFD2:PreviewApplicationName") != "Adobe DNG Converter":
            raise ValueError("Not an Adobe-generated full preview")
        expected = (metadata["SubIFD2:ImageWidth"], metadata["SubIFD2:ImageHeight"])
        if im.size != expected:
            raise ValueError("Generated preview dimensions mismatch")
        if space == "sRGB":
            return orient_preview(im.convert("RGB").copy(), metadata)
        if space == "Gray Gamma 2.2":
            a = np.asarray(im.convert("RGB"))
            if not np.array_equal(a[..., 0], a[..., 1]) or not np.array_equal(
                a[..., 1], a[..., 2]
            ):
                raise ValueError("Gray preview contains chromatic samples")
            gray = Image.fromarray(a[..., 0], "L")
            return orient_preview(
                ImageCms.profileToProfile(
                    gray,
                    ImageCms.ImageCmsProfile(io.BytesIO(gray_profile_bytes())),
                    ImageCms.ImageCmsProfile(io.BytesIO(SRGB)),
                    outputMode="RGB",
                    renderingIntent=1,
                ),
                metadata,
            )
        raise ValueError("Unsupported Adobe preview color space: " + str(space))


class AdobeRenderer:
    def __init__(self, cache, output, converter=DEFAULT_CONVERTER, timeout=180):
        self.converter = Path(converter).expanduser().resolve()
        self.cache = Path(cache).resolve()
        self.cache.mkdir(parents=True, exist_ok=True)
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        info = self.converter.parent.parent / "Info.plist"
        app = plistlib.loads(info.read_bytes()) if info.exists() else {}
        self.identity = dict(
            converter=str(self.converter),
            sha256=digest(self.converter),
            version=app.get("CFBundleShortVersionString"),
            build=app.get("CFBundleVersion"),
            gray_profile_sha256=__import__("hashlib").sha256(gray_profile_bytes()).hexdigest(),
            policy="generated-JpgFromRaw-LCMS-sRGB-oriented/3",
            lcms_version=ImageCms.core.littlecms_version,
            srgb_sha256=__import__("hashlib").sha256(SRGB).hexdigest(),
        )
        self.calls = 0
        self.hits = 0
        self.records = []

    def render(self, raw, settings):
        if set(settings) & {"AutoTone", "AutoGray"}:
            raise ValueError(
                "Use explicit tone and GrayMixer values, not Auto commands"
            )
        raw = Path(raw).resolve()
        source_hash = digest(raw)
        import hashlib

        key = hashlib.sha256(
            canonical(
                dict(raw=source_hash, settings=settings, engine=self.identity)
            ).encode()
        ).hexdigest()
        dest = self.cache / key
        proof = dest / "complete.json"
        image = dest / "render.png"
        if proof.exists():
            record = json.loads(proof.read_text())
            if digest(image) != record["render_sha256"]:
                raise ValueError("Corrupt Adobe render cache: " + str(dest))
            self.hits += 1
            self.records.append(record)
            return image
        required = raw.stat().st_size * 4 + 64 * 1024 * 1024
        for location in (self.output, self.cache):
            available = shutil.disk_usage(location).free
            if available < required:
                raise RuntimeError(
                    f"Insufficient disk space for Adobe render at {location}: "
                    f"need at least {required} bytes, available {available}. "
                    "Free disposable intermediates before retrying."
                )
        dest.mkdir(exist_ok=False)
        save(dest / "requested.json", settings)
        with tempfile.TemporaryDirectory(prefix="adobe-", dir=self.output) as tmp:
            work = Path(tmp)
            scratch = work / raw.name
            shutil.copy2(raw, scratch)
            if digest(scratch) != source_hash:
                raise ValueError("RAW changed while copying")
            write_settings(scratch.with_suffix(".xmp"), settings)
            command = [
                str(self.converter),
                "-c",
                "-p2",
                "-d",
                str(work),
                "-o",
                "candidate.dng",
                str(scratch),
            ]
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=self.timeout
            )
            save(
                dest / "command.json",
                dict(
                    command=command,
                    returncode=result.returncode,
                    stdout=result.stdout,
                    stderr=result.stderr,
                ),
            )
            dng = work / "candidate.dng"
            if result.returncode or not dng.exists():
                raise RuntimeError(
                    "Adobe conversion failed: " + str(dest / "command.json")
                )
            md = json.loads(
                subprocess.check_output(
                    [
                        "exiftool",
                        "-j",
                        "-a",
                        "-G1",
                        "-s",
                        "-PreviewApplicationName",
                        "-PreviewApplicationVersion",
                        "-PreviewColorSpace",
                        "-Orientation#",
                        "-ImageWidth",
                        "-ImageHeight",
                        "-XMP-crs:all",
                        str(dng),
                    ],
                    timeout=30,
                )
            )[0]
            for name, value in settings.items():
                if name in ("HasSettings", "Version"):
                    continue
                actual = md.get("XMP-crs:" + name)
                if not _equivalent(actual, value):
                    raise ValueError(
                        f"Adobe XMP readback mismatch {name}: {actual!r} != {value!r}"
                    )
            jpeg = subprocess.check_output(
                ["exiftool", "-b", "-JpgFromRaw", str(dng)], timeout=30
            )
            rendered = canonical_preview(jpeg, md)
            rendered.save(image, icc_profile=SRGB)
            if digest(raw) != source_hash:
                raise ValueError("Source RAW changed during Adobe render")
            record = dict(
                schema="omfit-adobe-render/1",
                raw=str(raw),
                raw_sha256=source_hash,
                settings=settings,
                renderer=self.identity,
                metadata=md,
                render=str(image),
                render_sha256=digest(image),
                dimensions=list(rendered.size),
                orientation_applied=md.get("IFD0:Orientation", 1),
                color_space="ICC-managed sRGB",
                lightroom_parity_verified=False,
            )
            save(dest / "complete.json", record)
        self.calls += 1
        self.records.append(record)
        return image
