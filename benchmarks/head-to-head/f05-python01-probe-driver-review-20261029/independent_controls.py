"""Bounded independent adapter checks; fake transport only, never probe/daemon."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile

HERE = Path(__file__).resolve().parent
REPLAY = HERE / 'replay'
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPLAY))
import controls as c
import driver as d


def main():
    p = d.load_plan()
    out = HERE / 'independent-fixtures'
    out.mkdir()
    cases = []
    for label in ['create', 'start']:
        class Fail(c.Fake):
            def command(self, folder, name, argv, **kwargs):
                r = super().command(folder, name, argv, **kwargs)
                if name == label:
                    r.update(exitCode=1, error='owned synthetic client failure')
                    (folder/'logs'/name/'receipt.json').write_text(json.dumps(r))
                return r
        f=Fail(p)
        r=d.run(None,out/label,out/(label+'-scratch'),backend=f,authorization_check=lambda *_:{'synthetic':True})
        assert r['state']=='incomplete' and r['containerCreateAttempted'] and r['containerAbsent']
        assert f.labels[-3:]==['cleanup','post-cleanup-inspect','post-cleanup-list']
        assert (out/label/'result.json').is_file() and (out/label/'trace.json').is_file()
        cases.append({'case':label+'-failure-cleanup','passed':True,'result':r})
    f=c.Fake(p)
    def badplan():
        raise ValueError('owned synthetic changed input')
    r=d.run(None,out/'preflight',out/'preflight-scratch',backend=f,plan_loader=badplan)
    assert not f.labels and r['daemonCalls']==0 and r['state']=='incomplete'
    assert (out/'preflight/result.json').is_file() and r['costUsd'] is None
    cases.append({'case':'preflight-failure-receipt-no-daemon','passed':True,'result':r})
    tick=[0]
    class Deadline(c.Fake):
        def command(self, folder, label, argv, **kwargs):
            r=super().command(folder,label,argv,**kwargs)
            if label=='uv-version': tick[0]=61
            return r
    f=Deadline(p)
    r=d.run(None,out/'sixty',out/'sixty-scratch',backend=f,clock=lambda:tick[0],authorization_check=lambda *_:{'synthetic':True})
    assert r['state']=='incomplete' and r['probeBudgetExceeded'] and not r['workBudgetExceeded']
    assert 'owned-probe' not in f.labels and r['containerAbsent']
    cases.append({'case':'sixty-second-whole-stage-not-renewed-for-probe','passed':True,'result':r})
    raw=d.owned_tar(p)
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:
        rows=t.getmembers(); assert len(rows)==1 and rows[0].name=='probe.py' and rows[0].isfile()
        assert hashlib.sha256(t.extractfile(rows[0]).read()).hexdigest()==p['probe']['sourceSha256']
    cases.append({'case':'only-owned-script-provisioned','passed':True,'tarBytes':len(raw),'tarSha256':hashlib.sha256(raw).hexdigest()})
    for label,raw in [('duplicate',b'{"schema":"x","schema":"x"}'),('nonfinite',b'{"x":NaN}')]:
        try: d.check_probe(raw)
        except ValueError: pass
        else: raise AssertionError(label)
        cases.append({'case':'metadata-'+label+'-refusal','passed':True})
    result={'state':'independent-bounded-fake-controls-pass','count':len(cases),'cases':cases,'probeExecuted':False,'actualDaemonCalls':0,'actualAdmission':False}
    (HERE/'independent-controls.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'state':result['state'],'count':len(cases)}))


if __name__=='__main__': main()
