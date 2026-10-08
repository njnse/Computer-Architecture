"""Public-data fixed-mask training, quantization, and held-out RTL stimuli."""
import hashlib,json
from pathlib import Path
import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from threadpoolctl import threadpool_limits
from reference import encode

POLICIES=['dense','index','pair','fixed']

def choose_mask(weights,policy):
    mask=np.zeros_like(weights,dtype=bool)
    groups=weights.reshape(10,16,4)
    m=mask.reshape(10,16,4)
    if policy=='dense':mask[:]=True
    elif policy=='index':
        order=np.argsort(-np.abs(groups),axis=-1,kind='stable')[:,:,:2]
        np.put_along_axis(m,order,True,axis=-1)
    elif policy=='pair':
        for start in [0,2]:
            order=np.argmax(np.abs(groups[:,:,start:start+2]),axis=-1)+start
            np.put_along_axis(m,order[:,:,None],True,axis=-1)
    else:m[:,:,0]=True;m[:,:,2]=True
    return mask

def loss(x,y,w,b):
    logits=x@w.T+b
    logits-=logits.max(axis=1,keepdims=True)
    return float(np.mean(np.log(np.exp(logits).sum(axis=1))-logits[np.arange(len(y)),y]))

def train(x,y,vx,vy,w,b,mask,epochs,seed,stage,history):
    w=w.copy()*mask;b=b.copy()
    best=(loss(vx,vy,w,b),w.copy(),b.copy(),0)
    hot=np.eye(10)[y]
    for epoch in range(1,epochs+1):
        logits=x@w.T+b;logits-=logits.max(axis=1,keepdims=True)
        probs=np.exp(logits);probs/=probs.sum(axis=1,keepdims=True)
        delta=(probs-hot)/len(y)
        w-=0.5*((delta.T@x)+0.0001*w)*mask
        b-=0.5*delta.sum(axis=0)
        if epoch%10==0:
            vl=loss(vx,vy,w,b)
            history.append({'seed':seed,'stage':stage,'epoch':epoch,'train_loss':loss(x,y,w,b),'validation_loss':vl})
            if vl<best[0]:best=(vl,w.copy(),b.copy(),epoch)
    return best[1],best[2],best[3],best[0]

def quantize(w,width):
    qmax=(1<<(width-1))-1
    scale=np.max(np.abs(w),axis=1)/qmax
    scale=np.where(scale==0,1.0,scale)
    return np.rint(w/scale[:,None]).clip(-qmax,qmax).astype(np.int64),scale

def logits_integer(x,w,b,width):
    qmax=(1<<(width-1))-1
    qx=np.rint(x*qmax).astype(np.int64)
    qw,scale=quantize(w,width)
    sums=qx@qw.T
    return sums*scale[None,:]/qmax+b,qx,qw,scale,sums

def train_workload(results):
    digits=load_digits()
    pixels=digits.data.astype(np.uint8);y=digits.target.astype(np.int64)
    ids=np.arange(len(y))
    tv,test=train_test_split(ids,test_size=0.2,random_state=1729,stratify=y)
    training,validation=train_test_split(tv,test_size=0.25,random_state=2718,stratify=y[tv])
    x=pixels.astype(np.float64)/16
    manifest={'loader':'sklearn.datasets.load_digits','dataset_doi':'10.24432/C50P49','license':'CC-BY-4.0','license_url':'https://archive.ics.uci.edu/dataset/80/optical+recognition+of+handwritten+digits','original_split_warning':'This is a new split of the original UCI test subset, not the official writer-independent benchmark.','images':len(y),'features':64,'classes':10,'pixels_u8_sha256':hashlib.sha256(pixels.tobytes()).hexdigest(),'labels_i64le_sha256':hashlib.sha256(y.astype('<i8').tobytes()).hexdigest(),'training':training.tolist(),'validation':validation.tolist(),'test':test.tolist(),'split_seeds':[1729,2718],'training_seeds':[7,31,97]}
    (results/'workload_provenance.json').write_text(json.dumps(manifest,indent=2)+'\n')
    models={};metrics=[];history=[];predictions={}
    with threadpool_limits(limits=1):
        for seed in [7,31,97]:
            rng=np.random.default_rng(seed)
            initial=rng.normal(0,0.01,(10,64))
            dense,bias,ep,vl=train(x[training],y[training],x[validation],y[validation],initial,np.zeros(10),np.ones_like(initial,dtype=bool),600,seed,'dense_initial',history)
            for policy in POLICIES:
                mask=choose_mask(dense,policy)
                dropped=float(np.square(dense*(~mask)).sum())
                pair_conflicts=sum(1 for group in choose_mask(dense,'index').reshape(-1,4) if group[:2].sum()==2 or group[2:].sum()==2)
                pruned=dense*mask
                recovered,rb,rep,rvl=train(x[training],y[training],x[validation],y[validation],pruned,bias,mask,300,seed,policy+'_recovery',history)
                for stage,w,b,epoch,val_loss in [('immediate',pruned,bias,ep,loss(x[validation],y[validation],pruned,bias)),('recovered',recovered,rb,rep,rvl)]:
                    key=f'{seed}_{policy}_{stage}'
                    models[key]={'weights':w.tolist(),'bias':b.tolist(),'mask':mask.astype(int).tolist(),'selected_epoch':epoch}
                    for width in [0,4,8]:
                        if width==0:logits=x[test]@w.T+b;nonzero=int(np.count_nonzero(w));qerror=0.0
                        else:
                            logits,_,qw,scale,_=logits_integer(x[test],w,b,width)
                            nonzero=int(np.count_nonzero(qw));qerror=float(np.square(w-qw*scale[:,None]).sum())
                        pred=logits.argmax(axis=1)
                        predictions[f'{key}_{width}']=pred.tolist()
                        metrics.append({'seed':seed,'policy':policy,'stage':stage,'width':width,'test_samples':len(test),'test_correct':int((pred==y[test]).sum()),'test_accuracy':float((pred==y[test]).mean()),'validation_loss':val_loss,'selected_epoch':epoch,'dropped_weight_energy':dropped,'weight_quantization_squared_error':qerror,'numerical_nonzeros':nonzero,'retained_slots':int(mask.sum()),'unrestricted_mask_pair_conflicts':int(pair_conflicts)})
    (results/'models.json').write_text(json.dumps(models,separators=(',',':'))+'\n')
    (results/'test_predictions.json').write_text(json.dumps({'test_labels':y[test].tolist(),'predictions':predictions},separators=(',',':'))+'\n')
    return x[test],y[test],models,metrics,history,predictions

def replay_transactions(x,model,width,mode):
    w=np.asarray(model['weights']);b=np.asarray(model['bias'])
    mask=np.asarray(model['mask'],dtype=bool)
    logits,qx,qw,scale,sums=logits_integer(x,w,b,width)
    def stream():
        for image in qx:
            for output in range(10):
                for group in range(16):
                    start=4*group
                    positions=np.flatnonzero(mask[output,start:start+4]).tolist()
                    yield encode(image[start:start+4].tolist(),qw[output,start:start+4].tolist(),positions,mode)
    return stream(),sums,scale,b,logits.argmax(axis=1)
