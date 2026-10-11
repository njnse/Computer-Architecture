"""Audit evidence against formulas, executable inputs, and retained netlists."""
import base64
import csv
import gzip
import hashlib
import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parent
R=ROOT/'results'


def main():
    read=lambda name:json.loads((R/name).read_text())
    sim=read('simulation.json');resources=read('resources.json');application=read('application.json')
    assert len(sim)==484,(len(sim),'expected full predefined grid')
    assert len(resources)==33
    assert len(read('netlist_readback.json'))==33
    assert {x['configuration'] for x in read('netlist_readback.json')}=={x['configuration'] for x in resources}
    assert len(read('formal.json'))==6 and all(x['passed'] for x in read('formal.json'))
    assert len(read('mutations.json'))==3 and all(x['detected'] for x in read('mutations.json'))
    testlog=R/'python_tests.log'
    text=testlog.read_text() if testlog.exists() else gzip.decompress(base64.b64decode((R/'python_tests.log.gz.b64').read_text())).decode()
    assert 'Ran 10 tests' in text and '\nOK\n' in text
    for file,digest in read('measurement_sources.json').items():
        assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==digest
    assert read('python_pin_check.json')['passed'] and read('tool_pin_check.json')['passed']
    for x in sim:
        assert x['emitted']+x['canceled']==x['count']
        for kind,suffix in [('stimulus','.txt'),('output','.csv')]:
            path=ROOT/'build'/(x['run']+suffix)
            assert hashlib.sha256(path.read_bytes()).hexdigest()==x[kind+'_sha256']
    nets=json.loads(gzip.decompress(base64.b64decode((R/'netlists.json.gz.b64').read_text())))
    for x in resources:
        d=nets[x['configuration']]
        assert hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()==x['retained_design_sha256']
        types={}
        for cell in d['modules']['dot_engine']['cells'].values():types[cell['type']]=types.get(cell['type'],0)+1
        assert types==x['types']
        assert not any('LATCH' in kind.upper() or kind.startswith(('LDCE','LDPE')) for kind in types)
        if x['flow']!='generic':
            assert x['lut']==sum(v for k,v in types.items() if re.fullmatch(r'LUT[1-6]',k))
    assert len(application)==108
    for width,lanes in [(8,4),(4,4),(8,8)]:
        for policy in ['dense','index']:
            for seed in [7,31,97]:
                rows=[x for x in application if (x['width'],x['lanes'],x['policy'],x['model_seed'])==(width,lanes,policy,seed)]
                assert len(rows)==6
                assert len({x['raw_dots_sha256'] for x in rows})==1
                assert len({x['correct'] for x in rows})==1 and all(x['prediction_changes']==0 for x in rows)
    for policy in ['dense','index']:
        for seed in [7,31,97]:
            rows=[x for x in application if x['width']==8 and x['policy']==policy and x['model_seed']==seed]
            assert len(rows)==12 and len({x['raw_dots_sha256'] for x in rows})==1
    images=list(csv.DictReader((R/'image_cycles.csv').open()))
    assert len(images)==108*360
    for app in application:
        rows=[x for x in images if (int(x['width']),int(x['lanes']),x['policy'],int(x['model_seed']),x['variant'])==
              (app['width'],app['lanes'],app['policy'],app['model_seed'],app['variant'])]
        assert sum(int(x['service_cycles']) for x in rows)/app['block_outputs']==app['mean_cycles_per_block']
    raw=list(csv.DictReader((R/'application_blocks.csv').open()))
    assert len(raw)==57600
    candidate=next(x for x in sim if x['run']=='app_w8_n4_s7_index_qualified_bitmap')
    assert hashlib.sha256((R/'application_blocks.csv').read_bytes()).hexdigest()==candidate['output_sha256']
    summary=read('summary.json')
    assert all(summary['coverage'][x]>0 for x in ['busyreset','outputreset','outstalls','excluded_nonzero','qualified_zero','reduced_planes'])
    audit=dict(passed=True,rtl_and_netlist_runs=len(sim),python_tests=10,formal_checks=6,mutation_checks=3,
               retained_and_readback_netlists=len(resources),raw_public_blocks=len(raw),
               per_image_service_records=len(images),all_public_modes_bit_exact=True,
               scope='Bounded formal, finite RTL and generic-netlist tests, logical FPGA synthesis; no UVM/Vivado/physical timing/board execution')
    (R/'validation.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(audit,indent=2))


if __name__=='__main__':main()
