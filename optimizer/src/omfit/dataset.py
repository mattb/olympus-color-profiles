"""Generate a seeded, camera-stratified full-resolution synthetic LUT benchmark.

Run with: python -m omfit.dataset --sample RANDOM.json --luts ACQUISITION.json
--output NEW_DIRECTORY --cache CACHE_DIRECTORY. Native baseline jobs run in one
persistent GPU batch; CPU LUT jobs operate on full-resolution ICC-managed RGB.
"""
import argparse
import concurrent.futures
import datetime
import json
import os
import io

import numpy as np
from PIL import Image, ImageCms, ImageOps
from skimage.color import rgb2lab
from pathlib import Path
import shutil
import time

from .lut import generate_target, load_cube
from .model import Layout
from .renderer import Renderer, digest


def atomic_save(path, value):
    path=Path(path)
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w') as f:
        json.dump(value,f,indent=2,sort_keys=True);f.write('\n');f.flush();os.fsync(f.fileno())
    temporary.replace(path)


def source_pairs(sample, scene_wb_anchor="fixed_5300"):
    """Preserve the random sample/splits; pick first drawn train frame per burst."""
    if scene_wb_anchor not in ('fixed_5300','as_shot'):
        raise ValueError('Unknown scene WB anchor')
    pairs=[];seen_train=set();seen_ids=set()
    for row in sample['selected']:
        if row['id'] in seen_ids:raise ValueError('Duplicate sampled ID')
        seen_ids.add(row['id'])
        metadata=row['metadata'];orientation=metadata.get('Orientation',1)
        if orientation not in (1,3,6,8):raise ValueError('Mirrored or unsupported orientation')
        rotate={1:0,3:180,6:90,8:270}[orientation]
        w,h=metadata['CropWidth'],metadata['CropHeight']
        if rotate in (90,270):w,h=h,w
        group=(row['camera'],row['scene_group'])
        primary=row['role']=='train' and group not in seen_train
        if row['role']=='train':seen_train.add(group)
        pair=dict(row)
        pair.update(raw_hash=row['sha256'],rotate=rotate,developed_size=[w,h],
            resize=[round(w*800/max(w,h)),round(h*800/max(w,h))],primary_train=primary,
            diagnostic_only=row['role']=='train' and not primary)
        if scene_wb_anchor=='fixed_5300' and pair['initial']!=[53,0,0,0]:
            raise ValueError('Controlled fixed5300 dataset requires declared known5300K/zeroEV baseline')
        if scene_wb_anchor=='as_shot':
            if len(pair['initial'])!=4 or pair['initial'][3]!=0:
                raise ValueError('Controlled as-shot dataset requires explicit zero EV')
            pair['scene_wb_anchor']='as_shot'
            pair['initial_wb_policy']='WB inherited from camera ORF as-shot parameters. Numerical initial[0:3] are unused placeholders, not5300K/AB0/GM0. ExplicitEV0 retained. FreezeWB in primaryfit; freeWBablationrequires separatecustomWBanchor.'
            pair['free_wb_ablation_compatible']=False
        pairs.append(pair)
    return pairs


def anchor_coverage(pairs):
    """Training representatives only; exact192grid samples from full baselines."""
    cameras=[]
    for camera in sorted({p['camera']for p in pairs}):
        rows=[p for p in pairs if p['camera']==camera and p['primary_train']]
        samples=[]
        for pair in rows:
            with Image.open(pair['baseline_full'])as original:
                im=ImageOps.exif_transpose(original).convert('RGB');w,h=im.size
                xx=np.floor((np.arange(192)+.5)*w/192).astype(int);yy=np.floor((np.arange(192)+.5)*h/192).astype(int)
                values=np.asarray(im)[yy][:,xx]
                small=Image.fromarray(values)
                managed=ImageCms.profileToProfile(small,ImageCms.ImageCmsProfile(io.BytesIO(original.info['icc_profile'])),ImageCms.createProfile('sRGB'),outputMode='RGB',renderingIntent=1)
                samples.append(np.asarray(managed).reshape(-1,3)/255.)
        if not samples:continue
        rgb=np.concatenate(samples);lab=rgb2lab(rgb);C=np.hypot(lab[:,1],lab[:,2]);hue=np.degrees(np.arctan2(lab[:,2],lab[:,1]))%360
        chromatic=C>=10.;counts=np.histogram(hue[chromatic],bins=np.linspace(0,360,13))[0];hist=counts/max(1,counts.sum())
        stats=dict(neutral_C_below10_fraction=float((~chromatic).mean()),high_chroma_C_atleast40_fraction=float((C>=40).mean()),
            occupied_chromatic_hue_bins_atleast1pct=int((hist>=.01).sum()),chromatic_hue_fraction=hist.tolist(),
            endpoint_pixel_fraction=float(np.any((rgb<=0)|(rgb>=1),axis=1).mean()),L_mean=float(lab[:,0].mean()))
        cameras.append(dict(camera=camera,frames=len(rows),independent_scene_groups=len({p['scene_group']for p in rows}),distribution=stats))
    return dict(schema='omfit-wb-anchor-coverage/1',sampling='Fixed192pixel-center uniform grid onFULLbaseline; exactpixelsICCconverted, noresize.',
        scope='Only primary training representatives; no dev/test colors or fit outcomes used.',cameras=cameras,
        warning='As-shot cameraWB is metadata-inherited and may still be warm or inaccurate; wider descriptivecolorcoverage does not establish photometricneutrality or nativecontrolidentifiability.')


def _target_job(job):
    source,output,cube_path=job
    cube=load_cube(cube_path)
    return generate_target(source,output,cube,chunk_rows=128)


def generate(args):
    sample_path=Path(args.sample).expanduser().resolve();lut_path=Path(args.luts).expanduser().resolve()
    sample=json.loads(sample_path.read_text());assets=json.loads(lut_path.read_text())['assets']
    output=Path(args.output).expanduser().resolve();output.mkdir(parents=True,exist_ok=False)
    progress=output/'progress.json';manifest_path=output/'synthetic_manifest.json';start=time.monotonic()
    pairs=source_pairs(sample,args.scene_wb_anchor)
    for p in pairs:
        if digest(p['raw'])!=p['raw_hash']:raise ValueError('Sample RAW hash changed: '+p['raw'])
    for a in assets:
        if digest(a['cube_path'])!=a['cube_sha256']:raise ValueError('Acquired LUT hash changed: '+a['cube_path'])
    # This local license tree is necessary to interpret/share any derived LUT assets.
    license_dir=output/'licenses';license_dir.mkdir()
    upstream=lut_path.parent
    if (upstream/'LICENSES').exists():shutil.copytree(upstream/'LICENSES',license_dir/'upstream')
    shutil.copy2(lut_path,license_dir/'ACQUISITION.json')
    if (upstream/'README.md').exists():shutil.copy2(upstream/'README.md',license_dir/'UPSTREAM_README.md')
    policy=dict(seed=sample['seed'],selection_source=str(sample_path),selection_sha256=digest(sample_path),
        sampling=sample['sampling'],split_policy=sample['split_policy'],split_counts=sample['split_counts'],
        baseline=dict(backend='gpu_required',finishing='Natural',stock_wheel=[0]*12,highlight=0,shadow=0,
            scene_wb_anchor=args.scene_wb_anchor,wb_kelvin=5300 if args.scene_wb_anchor=='fixed_5300' else None,wb_ab=0 if args.scene_wb_anchor=='fixed_5300' else None,wb_gm=0 if args.scene_wb_anchor=='fixed_5300' else None,exposure_ev=0,output_bits=8,native_development_bits=16),
        target_pipeline='FULL native baseline -> embedded ICC to encoded sRGB -> full3D LUT -> tagged lossless full PNG',
        resize_policy='No resize before LUT. Native800 preview baseline is a separate rendering; no targetLUT is applied to it.',
        adjustments='Known WB/EV fixed in primary benchmark; free per-photo adjustment fitting is a separate ablation.' if args.scene_wb_anchor=='fixed_5300' else 'WB INHERITED from ORF camera as-shot metadata, not neutral photometricproof. Initial53 is unused placeholder. PrimaryWBfrozen; freeWBablationrequires distinctexplicitcustomanchor. EV0 explicit.',
        primary_train='First random-draw training representative of each (camera,scene_group); other sampled training frames diagnostic only. Original draw and split roles unchanged.',
        synthetic=True,real_film_ground_truth=False,source_edits=False,license_manifest=str(license_dir/'ACQUISITION.json'))
    report=dict(schema='omfit-synthetic-dataset/1',policy=policy,pairs=pairs,looks=[],baselines_ready=False,
        ready_look_ids=[],complete=False,created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    atomic_save(manifest_path,report)
    def status(stage,**extra):
        atomic_save(progress,dict(stage=stage,elapsed_seconds=round(time.monotonic()-start,3),ready_looks=report['ready_look_ids'],**extra))
    status('rendering_native_baselines',jobs=len(pairs)*2)
    native_dir=output/'native-baselines';native_dir.mkdir()
    renderer=Renderer(args.renderer,args.cache,native_dir,build_dir=args.build_dir,max_rss_mb=args.max_rss_mb)
    layout=Layout('stock');requests=[]
    for p in pairs:
        vector=layout.start(p['initial'])
        requests.extend([(p,layout.settings(p,vector,'gpu',full=True)),(p,layout.settings(p,vector,'gpu',full=False))])
    paths=renderer.render_many(requests)
    for i,p in enumerate(pairs):
        full,preview=paths[2*i:2*i+2];full_report=json.loads(Path(str(full)+'.json').read_text())
        if full_report.get('development_bits')!=16:raise ValueError('Native development was not16bit')
        p.update(baseline_full=str(full),baseline_preview=str(preview),baseline_full_sha256=digest(full),
            baseline_preview_sha256=digest(preview),baseline_backend=full_report['backend']['used'],
            baseline_process_id=full_report['process_id'],baseline_wb_mode_readback=full_report['current_parameters']['white_balance_mode'])
    report.update(baselines_ready=True,renderer_identities=renderer.identities,baseline_batches=renderer.batches,
        native_jobs=renderer.calls,native_processes=renderer.native_processes,cache_hits=renderer.hits)
    atomic_save(manifest_path,report);status('baselines_ready',pairs=len(pairs),native_processes=renderer.native_processes)
    print(json.dumps(dict(event='baselines_ready',manifest=str(manifest_path),pairs=len(pairs))),flush=True)
    if args.scene_wb_anchor=='as_shot':
        coverage=anchor_coverage(pairs)
        if args.coverage_reference:
            reference=json.loads(Path(args.coverage_reference).expanduser().read_text())
            old={r['camera']:r['distribution']for r in reference['grouped_baseline_coverage']if r['role']=='train_primary'}
            comparisons=[]
            for row in coverage['cameras']:
                previous=old[row['camera']];new=row['distribution']
                hue_gain=new['occupied_chromatic_hue_bins_atleast1pct']-previous['occupied_chromatic_hue_bins_atleast1pct']
                neutral_gain=new['neutral_C_below10_fraction']-previous['neutral_C_below10_fraction']
                endpoint_ratio=new['endpoint_pixel_fraction']/max(previous['endpoint_pixel_fraction'],1e-12)
                strong=(hue_gain>=2 or neutral_gain>=.20) and endpoint_ratio<=.75
                comparisons.append(dict(camera=row['camera'],old=previous,new=new,hue_bin_gain=hue_gain,neutral_fraction_gain=neutral_gain,endpoint_ratio=endpoint_ratio,strong_improvement=strong))
            coverage.update(reference=str(Path(args.coverage_reference).resolve()),comparisons=comparisons,
                gate_policy='Training-only descriptive gate, fixed before newWBbaseline evaluation: at least one camera gains>=2occupiedLab hue bins OR>=.20neutralfraction AND lowers displayendpointfraction>=25%. Does not use fit/dev/test outcomes.',
                proceed=any(r['strong_improvement']for r in comparisons))
        else:coverage.update(proceed=True,gate_policy='No reference supplied; explicit as-shot choice, descriptive coverage only.')
        atomic_save(output/'wb-anchor-coverage.json',coverage);report['wb_anchor_coverage']=coverage
        atomic_save(manifest_path,report)
        print(json.dumps(dict(event='wb_anchor_coverage',path=str(output/'wb-anchor-coverage.json'),proceed=coverage['proceed'])),flush=True)
        if not coverage['proceed']:
            status('coverage_gate_not_met',coverage=str(output/'wb-anchor-coverage.json'))
            return
    target_dir=output/'targets';target_dir.mkdir()
    total=len(pairs)*len(assets);completed=0
    # Finish one entire look before starting the next, publishing atomic ready flags
    # so the benchmark can begin with the first two looks while generation continues.
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        for asset in assets:
            look_id=asset['lut'];look_dir=target_dir/look_id;look_dir.mkdir()
            look=dict(id=look_id,reference=asset['reference'],source=asset['source'],
                sourceCubeSHA=asset['cube_sha256'],cube_path=asset['cube_path'],license=asset['license'],
                source_url=asset['url'],source_revision=asset['upstream_revision'],
                source_details=asset['source_details'],targets={},target_provenance={},ready=False)
            report['looks'].append(look);atomic_save(manifest_path,report)
            jobs=[(p['baseline_full'],str(look_dir/(p['id']+'.png')),asset['cube_path'])for p in pairs]
            # executor.map keeps manifest ordering deterministic despite completion order.
            for p,proof in zip(pairs,pool.map(_target_job,jobs)):
                look['targets'][p['id']]=proof['output'];look['target_provenance'][p['id']]=proof
                atomic_save(look_dir/(p['id']+'.provenance.json'),proof)
                completed+=1;status('generating_full_targets',current_look=look_id,completed=completed,total=total)
            look['ready']=True;report['ready_look_ids'].append(look_id)
            atomic_save(manifest_path,report);status('look_ready',current_look=look_id,completed=completed,total=total)
            print(json.dumps(dict(event='look_ready',look=look_id,manifest=str(manifest_path),completed=completed,total=total)),flush=True)
    for p in pairs:
        if digest(p['raw'])!=p['raw_hash']:raise ValueError('Source RAW changed during generation')
    report.update(complete=True,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        elapsed_seconds=round(time.monotonic()-start,3),target_files=total,
        target_bytes=sum(Path(path).stat().st_size for look in report['looks']for path in look['targets'].values()),
        baseline_bytes=sum(Path(p[k]).stat().st_size for p in pairs for k in ('baseline_full','baseline_preview')))
    atomic_save(manifest_path,report);status('complete',completed=total,total=total,target_bytes=report['target_bytes'])
    print(json.dumps(dict(event='complete',manifest=str(manifest_path),target_bytes=report['target_bytes'])),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample',required=True);parser.add_argument('--luts',required=True)
    parser.add_argument('--output',required=True);parser.add_argument('--cache',required=True)
    parser.add_argument('--renderer',default='omrender');parser.add_argument('--build-dir')
    parser.add_argument('--scene-wb-anchor',choices=['fixed_5300','as_shot'],default='fixed_5300');parser.add_argument('--coverage-reference',help='Old coverage.json; training-only gate before regenerating full targets')
    parser.add_argument('--workers',type=int,default=2);parser.add_argument('--max-rss-mb',type=int,default=4096)
    args=parser.parse_args()
    if not 1<=args.workers<=3:parser.error('Use1..3 memory-bounded CPU workers')
    generate(args)

if __name__=='__main__':main()
