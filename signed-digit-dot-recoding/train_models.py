"""Train fixed small MLP workloads; validation selects checkpoints and calibration."""
import hashlib
import json
import os
from pathlib import Path

for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[name]='1'
import numpy as np
from sklearn.datasets import load_digits

ROOT=Path(__file__).resolve().parent
CONFIG=dict(input_features=64,hidden=32,classes=10,epochs=120,batch_size=64,
            learning_rate=.003,weight_decay=.0001,beta1=.9,beta2=.999,epsilon=1e-8,
            seeds=[7,31,97],activations=['tanh','relu'],selection='minimum validation cross entropy')


def forward(x,p,activation):
    pre=x@p['w1']+p['b1']
    hidden=np.tanh(pre) if activation=='tanh' else np.maximum(pre,0)
    logits=hidden@p['w2']+p['b2']
    return pre,hidden,logits


def loss_and_grad(x,y,p,activation,decay=.0001):
    pre,h,logits=forward(x,p,activation)
    z=logits-logits.max(axis=1,keepdims=True)
    prob=np.exp(z);prob/=prob.sum(axis=1,keepdims=True)
    ce=float(-np.log(prob[np.arange(len(y)),y]).mean())
    loss=ce+.5*decay*float((p['w1']**2).sum()+(p['w2']**2).sum())
    dl=prob.copy();dl[np.arange(len(y)),y]-=1;dl/=len(y)
    dh=(dl@p['w2'].T)*((1-h*h) if activation=='tanh' else (pre>0))
    gradients={'w2':h.T@dl+decay*p['w2'],'b2':dl.sum(axis=0),
               'w1':x.T@dh+decay*p['w1'],'b1':dh.sum(axis=0)}
    return loss,gradients


def ce_accuracy(x,y,p,activation):
    logits=forward(x,p,activation)[2]
    z=logits-logits.max(axis=1,keepdims=True)
    logsum=np.log(np.exp(z).sum(axis=1))
    return float((logsum-z[np.arange(len(y)),y]).mean()),int((logits.argmax(axis=1)==y).sum())


def load_workload():
    provenance=json.loads((ROOT/'fixtures/provenance.json').read_text())
    data=load_digits();pixels=data.data.astype(np.uint8);labels=data.target.astype('<i8')
    d=provenance['dataset']
    assert hashlib.sha256(pixels.tobytes()).hexdigest()==d['pixels_u8_sha256']
    assert hashlib.sha256(labels.tobytes()).hexdigest()==d['labels_i64le_sha256']
    splits={k:np.asarray(d[k],dtype=np.int64) for k in ['training','validation','test']}
    assert all(not set(splits[a])&set(splits[b]) for a,b in [('training','validation'),('training','test'),('validation','test')])
    assert len(set(np.concatenate(list(splits.values()))))==1797
    return pixels.astype(np.float64)/16,labels,splits


def train():
    x,y,splits=load_workload();train_ids=splits['training'];val=splits['validation'];test=splits['test']
    models={};history=[]
    for activation in CONFIG['activations']:
        for seed in CONFIG['seeds']:
            rng=np.random.default_rng(seed)
            p={'w1':rng.normal(0,np.sqrt((2 if activation=='relu' else 1)/64),(64,32)),
               'b1':np.zeros(32),'w2':rng.normal(0,np.sqrt(1/32),(32,10)),'b2':np.zeros(10)}
            m={k:np.zeros_like(v) for k,v in p.items()};v={k:np.zeros_like(value) for k,value in p.items()}
            best=None;bestloss=float('inf');step=0;bestepoch=0
            for epoch in range(1,CONFIG['epochs']+1):
                order=rng.permutation(train_ids)
                for start in range(0,len(order),CONFIG['batch_size']):
                    ids=order[start:start+CONFIG['batch_size']]
                    _,grads=loss_and_grad(x[ids],y[ids],p,activation,CONFIG['weight_decay'])
                    step+=1
                    for k in p:
                        m[k]=CONFIG['beta1']*m[k]+(1-CONFIG['beta1'])*grads[k]
                        v[k]=CONFIG['beta2']*v[k]+(1-CONFIG['beta2'])*grads[k]**2
                        p[k]-=CONFIG['learning_rate']*(m[k]/(1-CONFIG['beta1']**step))/(np.sqrt(v[k]/(1-CONFIG['beta2']**step))+CONFIG['epsilon'])
                val_loss,val_correct=ce_accuracy(x[val],y[val],p,activation)
                train_loss,train_correct=ce_accuracy(x[train_ids],y[train_ids],p,activation)
                history.append(dict(activation=activation,seed=seed,epoch=epoch,training_ce=train_loss,
                                    training_correct=train_correct,validation_ce=val_loss,validation_correct=val_correct))
                if val_loss<bestloss:
                    bestloss=val_loss;bestepoch=epoch;best={k:value.copy() for k,value in p.items()}
            assert best is not None
            hidden=forward(x[val],best,activation)[1]
            bound=1.0 if activation=='tanh' else float(hidden.max())
            _,test_correct=ce_accuracy(x[test],y[test],best,activation)
            key=f'{activation}_{seed}'
            models[key]=dict(parameters={k:v.tolist() for k,v in best.items()},activation=activation,seed=seed,
                             selected_epoch=bestepoch,validation_ce=bestloss,activation_bound=bound,
                             calibration='fixed tanh mathematical bound' if activation=='tanh' else 'global maximum hidden activation on validation only',
                             floating_test_correct=test_correct,training_configuration=CONFIG)
            print('Trained',key,'selected epoch',bestepoch,'float correct',test_correct,'of',len(test),flush=True)
    results=ROOT/'results';results.mkdir(exist_ok=True)
    (results/'models.json').write_text(json.dumps(models,indent=2)+'\n')
    (results/'training_history.json').write_text(json.dumps(history,indent=2)+'\n')
    (results/'training_config.json').write_text(json.dumps(CONFIG,indent=2)+'\n')
    return models


if __name__=='__main__':train()
