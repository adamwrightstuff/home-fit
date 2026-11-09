import gzip,csv,glob,json,sys,math,collections
import numpy as np
raw=sys.argv[1]; repo=sys.argv[2]
jobs={}
for f in glob.glob(raw+'/*_wac_*.csv.gz'):
    with gzip.open(f,'rt') as fh:
        r=csv.DictReader(fh)
        for x in r: jobs[x['w_geocode']]=int(x['CNS07'])+int(x['CNS18'])
la=[];lo=[];jb=[]
for f in glob.glob(raw+'/*_xwalk.csv.gz'):
    with gzip.open(f,'rt') as fh:
        r=csv.DictReader(fh)
        for x in r:
            j=jobs.get(x['tabblk2020'])
            if j: la.append(float(x['blklatdd']));lo.append(float(x['blklondd']));jb.append(j)
la=np.array(la);lo=np.array(lo);jb=np.array(jb)
print('blocks with retail+food jobs',len(jb),'total jobs',jb.sum())
def jobs_within(lat,lon,R=800):
    k=111320.0;m=(abs(la-lat)*k<R)&(abs(lo-lon)*k*math.cos(math.radians(lat))<R)
    d=np.hypot((la[m]-lat)*k,(lo[m]-lon)*k*math.cos(math.radians(lat)));return jb[m][d<=R].sum()
rows=[]
for f in sorted(glob.glob(repo+'/data/*composites_recomputed.jsonl')):
    metro=f.split('/')[-1].split('_')[0]
    for l in open(f):
        r=json.loads(l);s=r['score'];p=s['livability_pillars']['neighborhood_amenities'];c=s['coordinates']
        rows.append((metro,r['catalog']['name'],r['catalog']['state_abbr'],p.get('score'),(p.get('breakdown') or {}).get('home_walkability',{}).get('score'),int(jobs_within(c["lat"],c["lon"]))))
print('places',len(rows))
def rk(a): 
    o=np.argsort(a,kind='stable');r=np.empty(len(a));r[o]=np.arange(len(a))
    # average ties
    u,inv,cnt=np.unique(a,return_inverse=True,return_counts=True);s=np.bincount(inv,weights=r);return (s/cnt)[inv]
def sp(x,y): return float(np.corrcoef(rk(np.array(x,float)),rk(np.array(y,float)))[0,1])
sc=[r for r in rows if r[4] is not None]
print('scored with home score',len(sc),'; coverage (has LODES value, incl zero):',len(rows),'of 1476; zero-job places:',sum(1 for r in rows if r[5]==0))
print('OVERALL Spearman home vs jobs800: %.3f ; total score vs jobs: %.3f'%(sp([r[4] for r in sc],[r[5] for r in sc]),sp([r[3] for r in sc],[r[5] for r in sc])))
by=collections.defaultdict(list)
for r in sc: by[r[0]].append(r)
ms=[]
for k,v in sorted(by.items()):
    c=sp([r[4] for r in v],[r[5] for r in v]);ms.append(c);print('  %-10s n=%3d rho %.3f'%(k,len(v),c))
print('median within-metro %.3f min %.3f'%(np.median(ms),min(ms)))
# 20 largest rank disagreements
rh=rk(np.array([r[4] for r in sc]));rj=rk(np.array([r[5] for r in sc]));d=(rh-rj)/len(sc)
o=np.argsort(d)
print('home rank far BELOW jobs rank:',[(sc[i][1],sc[i][2],round(sc[i][4]),sc[i][5]) for i in o[:10]])
print('home rank far ABOVE jobs rank:',[(sc[i][1],sc[i][2],round(sc[i][4]),sc[i][5]) for i in o[::-1][:10]])
json.dump(rows,open(sys.argv[3],'w'))
