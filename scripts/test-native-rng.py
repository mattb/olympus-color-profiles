#!/usr/bin/env python3
"""Build and exercise actual native RNG rollback/unwind behavior; no camera I/O."""
import argparse,json,os,pathlib,runpy,subprocess
root=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output-dir',required=True,type=pathlib.Path)
a=p.parse_args();out=a.output_dir.expanduser().resolve()
if (pathlib.Path.home()/'Documents').resolve() not in out.parents:p.error('output directory must be isolated under ~/Documents')
if out.exists():p.error('output directory must be new')
out.mkdir(parents=True)
binary=out/'native-rng-fault-test'
subprocess.run(['clang++','-std=c++17','-arch','arm64','-O2','-framework','Foundation','-framework','AppKit',str(root/'src/native_rng_fault_test.mm'),'-o',str(binary)],check=True,timeout=60)
api=runpy.run_path(str(root/'omrender'))
env=api['native_environment']()
log=out/'native.log';timing=api['bounded']([binary],log,30,1024,env)
result=json.loads(log.read_text());result.update(ok=True,invoked_binary=str(binary),**timing)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
