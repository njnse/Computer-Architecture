#define _GNU_SOURCE
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <errno.h>

typedef struct { _Alignas(64) _Atomic uint64_t value; char padding[56]; } Padded;
_Static_assert(sizeof(Padded)==64,"padded stride");
static _Alignas(64) _Atomic uint64_t packed[2];
static Padded padded[2];
static _Alignas(64) _Atomic uint64_t shared;
static pthread_barrier_t ready, start, finish;
typedef struct {
    int id,cpu,mode,work,batch,pin_error;
    uint64_t iterations,checksum,flushes;
    double cpu_seconds;
} Args;

static double now(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC_RAW,&ts);
    return ts.tv_sec + ts.tv_nsec*1e-9;
}

static void *worker(void *arg) {
    Args *a=arg;
    cpu_set_t set; CPU_ZERO(&set); CPU_SET(a->cpu,&set);
    a->pin_error=pthread_setaffinity_np(pthread_self(),sizeof(set),&set);
    _Atomic uint64_t *target=a->mode==1 ? &padded[a->id].value :
        a->mode==2 ? &shared : &packed[a->id];
    uint64_t x=(uint64_t)a->id+1,delta=0,flushes=0;
    pthread_barrier_wait(&ready);
    pthread_barrier_wait(&start);
    struct timespec cb,ce;
    clock_gettime(CLOCK_THREAD_CPUTIME_ID,&cb);
    for(uint64_t i=0;i<a->iterations;i++) {
        for(int j=0;j<a->work;j++) x=x*UINT64_C(6364136223846793005)+UINT64_C(1442695040888963407);
        delta++;
        if(delta==(uint64_t)a->batch) {
            atomic_fetch_add_explicit(target,delta,memory_order_relaxed);
            delta=0;flushes++;
        }
    }
    if(delta) { atomic_fetch_add_explicit(target,delta,memory_order_relaxed);flushes++; }
    clock_gettime(CLOCK_THREAD_CPUTIME_ID,&ce);
    a->cpu_seconds=(ce.tv_sec-cb.tv_sec)+(ce.tv_nsec-cb.tv_nsec)*1e-9;
    a->checksum=x;a->flushes=flushes;
    pthread_barrier_wait(&finish);
    return NULL;
}

int main(int argc,char **argv) {
    if(argc!=6) return 2;
    const char *name=argv[1];
    int threads=atoi(argv[2]), work=atoi(argv[4]),batch=atoi(argv[5]);
    uint64_t n=strtoull(argv[3],NULL,10);
    int mode=!strcmp(name,"padded")?1:!strcmp(name,"shared")?2:!strcmp(name,"packed")?0:-1;
    if(mode<0 || threads<1 || threads>2 || work<0 || batch<1) return 2;
    cpu_set_t allowed;CPU_ZERO(&allowed);
    if(sched_getaffinity(0,sizeof(allowed),&allowed)) return 3;
    int cpus[CPU_SETSIZE],count=0;
    for(int c=0;c<CPU_SETSIZE;c++) if(CPU_ISSET(c,&allowed)) cpus[count++]=c;
    if(count<threads+1) return 4;
    cpu_set_t main_set;CPU_ZERO(&main_set);CPU_SET(cpus[0],&main_set);
    if(sched_setaffinity(0,sizeof(main_set),&main_set)) return 5;
    if(!atomic_is_lock_free(&packed[0])) return 6;
    pthread_barrier_init(&ready,NULL,threads+1);
    pthread_barrier_init(&start,NULL,threads+1);
    pthread_barrier_init(&finish,NULL,threads+1);
    pthread_t handles[2];Args args[2];
    for(int t=0;t<threads;t++) {
        args[t]=(Args){.id=t,.cpu=cpus[t+1],.mode=mode,.work=work,.batch=batch,.iterations=n};
        int err=pthread_create(&handles[t],NULL,worker,&args[t]);
        if(err) { fprintf(stderr,"pthread_create: %s\n",strerror(err));return 7; }
    }
    pthread_barrier_wait(&ready);
    double begin=now();
    pthread_barrier_wait(&start);
    pthread_barrier_wait(&finish);
    double elapsed=now()-begin;
    uint64_t total=0,checksum=0,flushes=0;
    double cpu_seconds=0;
    for(int t=0;t<threads;t++) {
        pthread_join(handles[t],NULL);
        if(args[t].pin_error) return 8;
        total+=mode==1?atomic_load(&padded[t].value):mode==2?0:atomic_load(&packed[t]);
        checksum+=args[t].checksum;flushes+=args[t].flushes;
        cpu_seconds+=args[t].cpu_seconds;
    }
    if(mode==2) total=atomic_load(&shared);
    if(total!=n*(uint64_t)threads) return 9;
    printf("{\"seconds\":%.9f,\"total\":%llu,\"checksum\":%llu,\"flushes\":%llu,\"counter_stride\":%zu,\"lock_free\":true,\"worker_cpu_seconds\":%.9f,\"packed_alignment_mod64\":%zu,\"padded_alignment_mod64\":%zu}\n",
        elapsed,(unsigned long long)total,(unsigned long long)checksum,
        (unsigned long long)flushes,mode==1?sizeof(Padded):sizeof(packed[0]),
        cpu_seconds,(size_t)((uintptr_t)&packed[0]%64),(size_t)((uintptr_t)&padded[0]%64));
    return 0;
}
