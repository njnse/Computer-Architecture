"""Audit executable provenance, numerical equivalence, and actual netlists."""
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
    sim=read('simulation.json');resources=read('resources.json');app=read('application.json')
    assert len(sim)==726,len(sim)
    assert len(resources)==45
    rb=read('netlist_readback.json')
    assert len(rb)==45 and all(x['passed'] for x in rb)
    assert {x['configuration'] for x in rb}=={x['configuration'] for x in resources}
    formal=read('formal.json');assert len(formal)==8 and all(x['passed'] for x in formal)
    faults=read('mutations.json');assert len(faults)==5 and all(x['detected'] for x in faults)
    path=R/'python_tests.log'
    text=path.read_text() if path.exists() else gzip.decompress(base64.b64decode((R/'python_tests.log.gz.b64').read_text())).decode()
    assert 'Ran 11 tests' in text and '\nOK\n' in text
    for file,h in read('measurement_sources.json').items():assert hashlib.sha256((ROOT/file).read_bytes()).hexdigest()==h
    assert read('python_pin_check.json')['passed'] and read('tool_pin_check.json')['passed']
    assert hashlib.sha256((R/'models.json').read_bytes()).hexdigest()==read('trained_models_sha256.json')['sha256']
    models=read('models.json');history=read('training_history.json')
    assert set(models)=={f'{a}_{seed}' for a in ['tanh','relu'] for seed in [7,31,97]}
    assert len(history)==6*120
    for key,m in models.items():
        rows=[x for x in history if x['activation']==m['activation'] and x['seed']==m['seed']]
        best=min(rows,key=lambda x:x['validation_ce'])
        assert best['epoch']==m['selected_epoch'] and best['validation_ce']==m['validation_ce']
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
        assert types==x['types'] and x['latches']==0
        assert not any('LATCH' in k.upper() or k.startswith(('LDCE','LDPE')) for k in types)
        if x['flow']!='generic':assert x['lut']==sum(v for k,v in types.items() if re.fullmatch(r'LUT[1-6]',k))
    assert len(app)==144
    for width,lanes in [(8,4),(4,4),(8,8)]:
        for activation in ['tanh','relu']:
            for seed in [7,31,97]:
                rows=[x for x in app if (x['width'],x['lanes'],x['activation'],x['model_seed'])==(width,lanes,activation,seed)]
                assert len(rows)==8 and len({x['raw_dots_sha256'] for x in rows})==1
                assert len({x['correct'] for x in rows})==1 and all(x['prediction_changes']==0 for x in rows)
                if activation=='relu':
                    costs={x['variant']:x['mean_cycles_per_block'] for x in rows}
                    assert costs['tc_bitmap']==costs['sm_bitmap'] and costs['tc_counter']==costs['sm_counter']
    for activation in ['tanh','relu']:
        for seed in [7,31,97]:
            rows=[x for x in app if x['width']==8 and x['activation']==activation and x['model_seed']==seed]
            assert len(rows)==16 and len({x['raw_dots_sha256'] for x in rows})==1
    images=list(csv.DictReader((R/'image_cycles.csv').open()))
    assert len(images)==144*360
    for a in app:
        rows=[x for x in images if (int(x['width']),int(x['lanes']),x['activation'],int(x['model_seed']),x['variant'])==
              (a['width'],a['lanes'],a['activation'],a['model_seed'],a['variant'])]
        assert sum(int(x['service_cycles']) for x in rows)/a['block_outputs']==a['mean_cycles_per_block']
    raw=list(csv.DictReader((R/'application_blocks.csv').open()));assert len(raw)==28800
    selected=next(x for x in sim if x['run']=='app_w8_n4_tanh_s7_sm_bitmap')
    assert hashlib.sha256((R/'application_blocks.csv').read_bytes()).hexdigest()==selected['output_sha256']
    summary=read('summary.json')
    assert all(summary['coverage'][k]>0 for k in ['busyreset','outputreset','outstalls','negative_groups','zero_weights'])
    check=dict(passed=True,rtl_and_netlist_runs=len(sim),python_tests=11,formal_checks=8,detected_mutations=5,
               retained_and_readback_netlists=45,generic_netlist_replays=22,raw_public_blocks=len(raw),per_image_records=len(images),
               trained_checkpoints=6,training_epochs_per_checkpoint=120,validation_selection_audited=True,
               bit_exact_all_public_variants=True,relu_tc_sm_identical_service_cycles=True,
               scope='Actual signed/relu MLP traces, RTL and logical synthesis; no UVM, physical timing, GPU training or board execution')
    (R/'validation.json').write_text(json.dumps(check,indent=2)+'\n');print(json.dumps(check,indent=2))


if __name__=='__main__':main()
