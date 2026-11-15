"""Declared sRGB 3D CUBE transforms, independent of camera/preset approximations.

CUBE rows change red fastest. Input samples outside DOMAIN_MIN/MAX clamp to the
nearest edge. Finite LUT outputs outside [0,1] are retained by apply_cube and
clipped only when generate_target encodes an 8-bit display image. This module
never guesses a log/gamut conversion: callers must supply an sRGB-in/sRGB-out LUT.
"""
from dataclasses import dataclass
import hashlib
from pathlib import Path
import shlex

import numpy as np
from PIL import Image
from .color import SRGB, rgb


@dataclass(frozen=True)
class Cube:
    size: int
    table: np.ndarray  # axes red, green, blue, output-channel
    domain_min: np.ndarray
    domain_max: np.ndarray
    title: str
    source_path: str
    source_sha256: str


def _hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):h.update(block)
    return h.hexdigest()


def load_cube(path):
    """Read one 3D CUBE; reject 1D/shaper combinations and unknown directives.

    Supported: TITLE, LUT_3D_SIZE, DOMAIN_MIN, DOMAIN_MAX, comments and RGB rows.
    Default domain is [0,1]^3. Exact row count, finite data, and strictly increasing
    per-channel domains are required. Unknown extensions fail rather than silently
    applying a transform in the wrong domain. No file-size-sized text array is kept.
    """
    path=Path(path).expanduser().resolve()
    size=None;title='';low=np.zeros(3);high=np.ones(3);seen=set();rows=[]
    with path.open(encoding='utf-8-sig') as f:
        for number,line in enumerate(f,1):
            tokens=shlex.split(line,comments=True,posix=True)
            if not tokens:continue
            key=tokens[0]
            if key in ('TITLE','LUT_3D_SIZE','DOMAIN_MIN','DOMAIN_MAX'):
                if rows:raise ValueError(f'CUBE header after data, line {number}')
                if key in seen:raise ValueError(f'Duplicate CUBE directive {key}')
                seen.add(key)
                if key=='TITLE':
                    if len(tokens)!=2:raise ValueError('TITLE must be one quoted string')
                    title=tokens[1]
                elif key=='LUT_3D_SIZE':
                    if len(tokens)!=2 or not tokens[1].isdigit():raise ValueError('Invalid LUT_3D_SIZE')
                    size=int(tokens[1])
                    if not 2<=size<=256:raise ValueError('LUT_3D_SIZE must be 2..256')
                else:
                    if len(tokens)!=4:raise ValueError(f'{key} needs three components')
                    v=np.array([float(x) for x in tokens[1:]],dtype=np.float64)
                    if not np.isfinite(v).all():raise ValueError('Nonfinite CUBE domain')
                    if key=='DOMAIN_MIN':low=v
                    else:high=v
            else:
                if size is None:raise ValueError(f'Unsupported directive or missing LUT_3D_SIZE, line {number}')
                if len(tokens)!=3:raise ValueError(f'CUBE RGB row requires three values, line {number}')
                try:v=tuple(float(x) for x in tokens)
                except ValueError:raise ValueError(f'Unsupported CUBE directive {key}') from None
                if not all(np.isfinite(v)):raise ValueError(f'Nonfinite CUBE value, line {number}')
                rows.append(v)
                if len(rows)>size**3:raise ValueError('Too many CUBE RGB rows')
    if size is None or len(rows)!=size**3:raise ValueError('Incomplete CUBE RGB table')
    if not np.all(high>low):raise ValueError('CUBE DOMAIN_MAX must exceed DOMAIN_MIN per channel')
    table=np.asarray(rows,dtype=np.float64).reshape(size,size,size,3).transpose(2,1,0,3).copy()
    table.setflags(write=False);low.setflags(write=False);high.setflags(write=False)
    return Cube(size,table,low,high,title,str(path),_hash(path))


def apply_cube(image,cube,*,chunk_rows=128):
    """Trilinear RGB interpolation; return float32 RGB without output clipping.

    Input is HxWx3 uint8/uint16 (normalized by its full dtype range) or floating
    RGB values in the declared domain. Finite inputs are required. Each row chunk
    bounds interpolation temporaries; the float32 output array is allocated once.
    One 20MP output needs about 240MB, plus at most chunk_rows of work arrays.
    """
    image=np.asarray(image)
    if image.ndim!=3 or image.shape[2]!=3:raise ValueError('Expected HxWx3 RGB image')
    if type(chunk_rows)!=int or chunk_rows<1:raise ValueError('chunk_rows must be a positive integer')
    if image.dtype not in (np.uint8,np.uint16) and not np.issubdtype(image.dtype,np.floating):
        raise ValueError('Expected uint8, uint16 or floating RGB samples')
    scale=float(np.iinfo(image.dtype).max) if np.issubdtype(image.dtype,np.unsignedinteger) else 1.
    out=np.empty(image.shape,dtype=np.float32)
    for y in range(0,image.shape[0],chunk_rows):
        a=image[y:y+chunk_rows].astype(np.float64)/scale
        if not np.isfinite(a).all():raise ValueError('Nonfinite input RGB samples')
        t=np.clip((a-cube.domain_min)/(cube.domain_max-cube.domain_min),0.,1.)*(cube.size-1)
        lower=np.minimum(np.floor(t).astype(np.intp),cube.size-2)
        fraction=t-lower
        result=np.zeros_like(a)
        for dr in (0,1):
            wr=fraction[...,0] if dr else 1.-fraction[...,0]
            for dg in (0,1):
                wg=fraction[...,1] if dg else 1.-fraction[...,1]
                for db in (0,1):
                    wb=fraction[...,2] if db else 1.-fraction[...,2]
                    result+=cube.table[lower[...,0]+dr,lower[...,1]+dg,lower[...,2]+db]*(wr*wg*wb)[...,None]
        if not np.isfinite(result).all():raise ValueError('Nonfinite interpolated CUBE result')
        if np.max(np.abs(result),initial=0.)>np.finfo(np.float32).max:
            raise ValueError('Interpolated CUBE output exceeds float32 range')
        out[y:y+chunk_rows]=result
    return out


def generate_target(sourceimage,path,cube,*,chunk_rows=128):
    """Apply a declared full sRGB LUT to ICC-converted source RGB; save tagged PNG/JPEG.

    Does not overwrite any file. No heuristic Lightroom control parsing, grain or
    spatial effects are involved. PNG is recommended for exact synthetic targets.
    JPEG uses quality=100, chroma subsampling disabled, explicit sRGB ICC. Returned
    hashes/provenance must accompany the upstream license/attribution manifest.
    """
    sourceimage=Path(sourceimage).expanduser().resolve();path=Path(path).expanduser().resolve()
    suffix=path.suffix.lower()
    if suffix not in ('.png','.jpg','.jpeg'):raise ValueError('Target output must be PNG or JPEG')
    if path.exists():raise FileExistsError(path)
    if not path.parent.is_dir():raise ValueError('Target parent directory must exist')
    if _hash(cube.source_path)!=cube.source_sha256:raise ValueError('LUT changed since loading')
    source_hash=_hash(sourceimage)
    transformed=apply_cube(rgb(sourceimage),cube,chunk_rows=chunk_rows)
    clipped=float(np.count_nonzero((transformed<0)|(transformed>1))/transformed.size)
    encoded=np.rint(np.clip(transformed,0,1)*255.).astype(np.uint8)
    kwargs=dict(icc_profile=SRGB)
    if suffix!='.png':kwargs.update(quality=100,subsampling=0)
    # Exclusive create prevents a race from overwriting another process's output.
    with path.open('xb') as f:Image.fromarray(encoded).save(f,format='PNG' if suffix=='.png' else 'JPEG',**kwargs)
    if _hash(sourceimage)!=source_hash:raise ValueError('Source changed while generating target')
    return dict(schema='omfit-lut-target/1',source=str(sourceimage),source_sha256=source_hash,
        lut=cube.source_path,lut_sha256=cube.source_sha256,output=str(path),output_sha256=_hash(path),
        title=cube.title,size=cube.size,domain_min=cube.domain_min.tolist(),domain_max=cube.domain_max.tolist(),
        input_encoding='sRGB ICC converted, gamma encoded',output_encoding='sRGB gamma encoded, tagged 8bit',
        interpolation='trilinear, domain clamped, red fastest',clipped_channel_fraction=clipped,
        license='Consult accompanying acquired LUT manifest; target provenance does not replace its attribution',
        synthetic=True,real_film_ground_truth=False)
