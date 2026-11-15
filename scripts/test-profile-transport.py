#!/usr/bin/env python3
"""Test installed native MySet code with fake handlers and hardware I/O denied."""
import argparse, json, pathlib, subprocess
R=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--jpeg',type=pathlib.Path,required=True);p.add_argument('--output-dir',type=pathlib.Path,required=True);a=p.parse_args()
a.output_dir=a.output_dir.expanduser().resolve();a.output_dir.mkdir(parents=True,exist_ok=False)
sb=a.output_dir/'read-only.sb';sb.write_text('(version 1)\n(allow default)\n(deny file-write*)\n(deny network*)\n(deny iokit-open)\n')
fw='/Applications/OM Workspace.app/Contents/Helpers/OM Digital Camera Updater.app/Contents/Frameworks:/Applications/OM Workspace.app/Contents/Frameworks'
results={}
for name in ('upload','download'):
    binary=a.output_dir/name
    subprocess.run(['clang++','-arch','arm64','-framework','Foundation',str(R/'tests'/f'native_profile_{name}_mock.mm'),'-o',str(binary)],check=True)
    cmd=['/usr/bin/sandbox-exec','-f',str(sb),'/usr/bin/env','DYLD_FRAMEWORK_PATH='+fw,'DYLD_LIBRARY_PATH='+fw,str(binary)]
    if name=='upload':cmd.append(str(a.jpeg.expanduser().resolve()))
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=60,check=True)
    (a.output_dir/f'{name}.json').write_text(r.stdout);(a.output_dir/f'{name}.log').write_text(r.stderr)
    results[name]=json.loads(r.stdout)
u=results['upload'];assert not u['hardware_operations']
for case in u['results']:
    expected=case['case'] in ('success','status2','status4')
    assert case['result']==expected,case
    events=case['events'];writes=[e for e in events if e['call']=='uploadMySet']
    assert all(e['bytes']<=0xf800 for e in writes)
    if expected:assert case['received_equals_input']
    if case['skip_cold_start']:assert not any(e['call']=='coldStart' for e in events)
    if case['case'] in ('reserve','upload'):assert not any(e['call']=='checkUploadMySet' for e in events)
    if case['case'] in ('reserve','upload','commit'):assert case['error_code']=={'reserve':901,'upload':902,'commit':903}[case['case']]
d=results['download'];assert not d['hardware_operations'] and d['byte_identical'] and d['input_size']==140003
assert [e['size'] for e in d['events'] if e['call']=='download']==[63488,63488,13027]
summary={'hardware_operations':False,'native_upload_mock_cases_passed':len(u['results']),'native_download_bytes_exact':d['input_size'],'physical_camera_validation':False}
(a.output_dir/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
