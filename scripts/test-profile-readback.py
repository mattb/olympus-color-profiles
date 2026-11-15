#!/usr/bin/env python3
"""Exercise camera payload and unrelated-setting verification without device I/O."""
import json
import pathlib
import runpy

api=runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1]/'omrender'))
def csv(fields,bank='Current'):
    return ('1,a,b,c,'+bank+',d\n'+''.join('2,'+k+','+v+'\n' for k,v in fields.items())+'3\n').encode()
payload=csv({'MONO1_FILTER':'RED','MONO1_LEVEL':'3'})
before=csv({'MONO1_FILTER':'OFF','MONO1_LEVEL':'0','COLOR1_SECTOR':'-2','MONO2_FILTER':'GREEN'})
after=csv({'MONO1_FILTER':'RED','MONO1_LEVEL':'3','COLOR1_SECTOR':'-2','MONO2_FILTER':'GREEN'})
verify=api['verify_camera_readback'];preserve=api['verify_camera_preservation']
tests={
 'exact_payload':verify(payload,after)['verified'],
 'wrong_payload_rejected':not verify(payload,before)['verified'],
 'unrelated_fields_preserved':preserve(payload,before,after)['verified'],
 'color_change_rejected':not preserve(payload,before,after.replace(b'COLOR1_SECTOR,-2',b'COLOR1_SECTOR,0'))['verified'],
 'other_mono_change_rejected':not preserve(payload,before,after.replace(b'MONO2_FILTER,GREEN',b'MONO2_FILTER,RED'))['verified'],
 'missing_bank_rejected':not preserve(payload,csv({},'Myset1'),after)['verified'],
 'opaque_readback_rejected':not verify(payload,b'not native CSV')['verified'],
}
print(json.dumps({'ok':all(tests.values()),'hardware_operations':False,'tests':tests},indent=2))
raise SystemExit(0 if all(tests.values()) else 1)
