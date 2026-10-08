#!/usr/bin/env python3
"""
Exploratory check: do HomeFit catalog pillar scores predict CDC PLACES ZIP-level outcomes?

Joins ~366 catalog places (NYC, LA, SF metros) to PLACES ZCTA crude prevalence of frequent mental
distress, depression and short sleep (dataset qnzd-25i4, the only ZIP-level release; age-adjusted
rates are not published at ZIP level). Each pillar is fitted one at a time with the status-signal
wealth, education, home-cost and occupation scores as controls plus metro fixed effects. A pillar
counts as supported only if its sign is the same when each metro is dropped in turn and its
ZIP-clustered bootstrap 95% interval (500 resamples) excludes zero.

Results and caveats: docs/HAPPINESS_EVIDENCE_NOTES.md. Needs data.cdc.gov. Run from the project root.
"""
import json, requests, numpy as np, pandas as pd
M={"MHLTH":"Frequent mental distress among adults","DEPRESSION":"Depression among adults","SLEEP":"Short sleep duration among adults"}
rows=[]
for o,m in M.items():
    r=requests.get("https://data.cdc.gov/resource/qnzd-25i4.json",params={"$select":"locationname,data_value","$where":f"measure='{m}' AND data_value_type='Crude prevalence'","$limit":50000},timeout=120).json()
    for x in r: rows.append((x["locationname"].zfill(5),o,float(x["data_value"])))
P=pd.DataFrame(rows,columns=["zip","o","y"]).pivot_table(index="zip",columns="o",values="y").reset_index()
PIL=["active_outdoors","neighborhood_amenities","air_travel_access","public_transit_access","healthcare_access","quality_education","housing_value","climate_risk","social_fabric","diversity","community_safety","natural_beauty","economic_opportunity"]
recs=[]
for metro,f in [("nyc","nyc_metro_place_catalog_scores_merged"),("la","la_metro_place_catalog_scores_merged"),("sf","sf_metro_place_catalog_scores_merged")]:
    for l in open(f"data/{f}.jsonl"):
        r=json.loads(l)
        if not r.get("success"): continue
        s=r["score"]; z=(s.get("location_info") or {}).get("zip")
        if not z: continue
        d={"metro":metro,"zip":str(z).zfill(5),"area":(s.get("data_quality_summary") or {}).get("area_classification",{}).get("area_type")}
        for p in PIL: d[p]=((s.get("livability_pillars") or {}).get(p) or {}).get("score")
        sb=s.get("status_signal_breakdown") or {}
        for k in ["wealth","education","home_cost","occupation"]: d["ss_"+k]=sb.get(k)
        recs.append(d)
D=pd.DataFrame(recs).merge(P,on="zip")
print(len(D),"places",D.zip.nunique(),"zips"); print(D.metro.value_counts().to_dict())
CTRL=["ss_wealth","ss_education","ss_home_cost","ss_occupation"]
def fit(d,xs,y):
    X=np.column_stack([np.ones(len(d))]+[d[c] for c in xs]+[(d.metro==m).astype(float) for m in sorted(d.metro.unique())[1:]]); 
    b=np.linalg.lstsq(X,d[y].values,rcond=None)[0]; return b
rng=np.random.default_rng(1)
out=[]
for y in M:
    for p in PIL:
        d=D.dropna(subset=[p,y]+CTRL).copy()
        if len(d)<80: continue
        for c in [p]+CTRL: d[c]=(d[c]-d[c].mean())/d[c].std()
        b=fit(d,[p]+CTRL,y)[1]
        lo=[ ]; 
        signs=[np.sign(fit(d[d.metro!=m],[p]+CTRL,y)[1]) for m in d.metro.unique()]
        zips=d.zip.unique(); g={z:np.flatnonzero(d.zip.values==z) for z in zips}
        bs=[]
        for _ in range(500):
            idx=np.concatenate([g[z] for z in rng.choice(zips,len(zips))]); bs.append(fit(d.iloc[idx],[p]+CTRL,y)[1])
        ci=np.percentile(bs,[2.5,97.5])
        ok=all(s==np.sign(b) for s in signs) and (ci[0]>0 or ci[1]<0)
        out.append((y,p,len(d),b,ci[0],ci[1],ok))
R=pd.DataFrame(out,columns=["outcome","pillar","n","coef_pp_per_sd","lo","hi","supported"])
pd.set_option("display.width",200); print(R.round(2).to_string())
print(R.groupby("pillar").agg(sup=("supported","sum"),meancoef=("coef_pp_per_sd","mean")).round(2))
