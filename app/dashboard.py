"""TrustPipe — Reliability-First ELT Console for NYC TLC Trip Records.

Demo data is deterministic and derived from the project's own contracts
(config/contracts.yml), dbt star schema (fact_trips / dim_zone / dim_vendor /
dim_datetime) and quality layer (Great Expectations, anomaly detectors,
freshness / volume / schema-drift monitors).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="TrustPipe", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
.stApp{background:radial-gradient(1200px 600px at 15% -10%, #0f3a2e 0%, transparent 55%),radial-gradient(1000px 500px at 90% 0%, #14315e 0%, transparent 50%),#0e1117}
.tp-hero{padding:1.1rem 1.4rem;border-radius:16px;margin-bottom:.6rem;background:linear-gradient(120deg, rgba(16,120,90,.55), rgba(30,80,160,.45));border:1px solid rgba(120,255,200,.35);box-shadow:0 8px 32px rgba(0,0,0,.45)}
.tp-hero h1{margin:0;font-size:2.1rem;background:linear-gradient(90deg,#9fffe0,#9fd0ff,#ffeaa7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.tp-hero p{margin:.25rem 0 0 0;color:#cfd8e3;font-size:.95rem}
div[data-testid="stMetric"]{background:rgba(22,27,34,.85);border:1px solid rgba(120,255,200,.35);border-radius:12px;padding:.6rem .8rem;box-shadow:0 4px 18px rgba(0,0,0,.35)}
.stTabs [data-baseweb="tab-list"]{gap:6px}
.stTabs [data-baseweb="tab"]{background:rgba(22,27,34,.8);border-radius:10px 10px 0 0;padding:6px 14px}
section[data-testid="stSidebar"]{background:rgba(14,17,23,.92)}
</style>
<div class="tp-hero"><h1>🛡️ TrustPipe — Reliability Console</h1>
<p>NYC TLC trip records · data contracts · dbt star schema · Great Expectations gates · quarantined rows — drag the 3D trust space, press play, slice from the sidebar.</p></div>
""", unsafe_allow_html=True)

BOROUGHS = ["Manhattan","Brooklyn","Queens","Bronx","Staten Island","EWR"]
ZONES = {
 "Manhattan": ["Midtown Center","Upper East Side North","Times Sq/Theatre District","Penn Station/Madison Sq West","East Village"],
 "Brooklyn": ["Williamsburg (North Side)","Downtown Brooklyn/MetroTech","Park Slope","Bedford Stuyvesant","Bushwick South"],
 "Queens": ["JFK Airport","LaGuardia Airport","Astoria","Flushing","Jamaica"],
 "Bronx": ["Riverdale/North Riverdale","Mott Haven/Port Morris","Fordham South","Hunts Point","Pelham Bay Park"],
 "Staten Island": ["Arden Heights","New Dorp/Midland Beach","Saint George/New Brighton","Great Kills","Heartland Village/Todt Hill"],
 "EWR": ["Newark Airport"],
}
CHECKS = [
 ("vendor_id in [1,2,6,7]","contract","yellow_trips"),
 ("fare_amount between -100 and 5000","contract","yellow_trips"),
 ("trip_distance between 0 and 1000","contract","yellow_trips"),
 ("pu/do_location_id 1..265","contract","yellow_trips"),
 ("passenger_count 0..9","contract","yellow_trips"),
 ("total_amount >= fare_amount","dbt test","fact_trips"),
 ("trip_key unique & not null","dbt test","fact_trips"),
 ("fare median 5..40 (GE)","great_expectations","fact_trips"),
 ("freshness SLA 26h (yellow)","monitor","yellow_trips"),
 ("volume 50k..500k / day","monitor","yellow_trips"),
 ("schema drift — no added cols","monitor","yellow_trips"),
 ("weather temp -40..55C","contract","weather"),
]

@st.cache_data
def gen():
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01","2024-03-29",freq="D")
    rows=[]
    for d in dates:
        dow = d.day_of_week; seasonal = 1 + 0.25*np.sin((d.day_of_year/90)*np.pi) + (0.18 if dow>=5 else 0)
        # inject incidents: Jan 18 volume drop, Feb 9 fare anomaly, Mar 3 drift
        incident = 0.62 if d==pd.Timestamp("2024-01-18") else 0.78 if d==pd.Timestamp("2024-02-09") else 0.85 if d==pd.Timestamp("2024-03-03") else 1.0
        for b in BOROUGHS:
            base = {"Manhattan":52000,"Brooklyn":21000,"Queens":24000,"Bronx":7000,"Staten Island":1800,"EWR":3200}[b]
            for src, share in [("batch",0.82),("stream",0.18)]:
                trips = int(base*seasonal*incident*share*rng.uniform(0.92,1.08))
                q_rate = rng.uniform(0.008,0.028) * (2.6 if incident<0.9 else 1.0)
                quarantined = int(trips*q_rate)
                passed = trips-quarantined
                rows.append(dict(date=d, borough=b, source=src, trips=trips, passed=passed, quarantined=quarantined,
                    pass_rate=100*passed/max(trips,1), avg_fare=float(rng.normal(18.5,2.2)), avg_distance=float(rng.normal(4.8,0.7)),
                    avg_tip=float(rng.normal(3.4,0.5)), freshness_h=float(max(0.5, rng.normal(4.5,1.8) + (18 if incident<0.7 else 0))),
                    reliability=float(np.clip(rng.normal(97.5,1.2) - (9 if incident<0.9 else 0), 82, 99.9))))
    daily=pd.DataFrame(rows)
    # checks per day (aggregate)
    crows=[]
    for d in dates:
        for name, layer, target in CHECKS:
            fail = d in [pd.Timestamp("2024-01-18"), pd.Timestamp("2024-02-09"), pd.Timestamp("2024-03-03")] and rng.random()<0.45
            crows.append(dict(date=d, check=name, layer=layer, target=target, status="FAIL" if fail else "PASS",
                              failures=int(rng.integers(0,40) if fail else rng.integers(0,4)), total=int(rng.integers(90000,140000))))
    checks=pd.DataFrame(crows)
    # trip sample for 3D
    n=2200; trip_rows=[]
    all_zones=[(b,z) for b,zs in ZONES.items() for z in zs]
    for i in range(n):
        b,z = all_zones[rng.integers(0,len(all_zones))]
        dist=float(np.clip(rng.lognormal(1.4,0.7),0.2,28)); fare=float(np.clip(5+dist*rng.uniform(2.2,3.8)+rng.normal(0,2), -5, 180))
        dur=float(np.clip(dist*rng.uniform(2.5,5.5)+rng.normal(4,2),2,90)); hour=int(rng.integers(0,24))
        status="quarantined" if rng.random()<0.04 or fare<0 or dist>25 else "passed"
        if status=="quarantined": fare = fare if rng.random()>0.5 else -12.0
        trip_rows.append(dict(zone=z, borough=b, trip_distance=dist, fare_amount=fare, duration_min=dur, pickup_hour=hour, status=status, passenger_count=int(rng.integers(0,5))))
    trips=pd.DataFrame(trip_rows)
    return daily, checks, trips

daily, checks_df, trips_df = gen()

st.sidebar.header("🎛️ Live filters")
dmin,dmax=daily["date"].min(), daily["date"].max()
picked=st.sidebar.date_input("Date range", value=(dmin.date(), dmax.date()), min_value=dmin.date(), max_value=dmax.date())
if isinstance(picked,(list,tuple)) and len(picked)==2:
    start,end=pd.Timestamp(picked[0]),pd.Timestamp(picked[1])
else:
    start,end=dmin,dmax
sel_boroughs=st.sidebar.multiselect("Boroughs", BOROUGHS, default=BOROUGHS)
sel_sources=st.sidebar.multiselect("Ingest source", ["batch","stream"], default=["batch","stream"])
min_rel=st.sidebar.slider("Min reliability score", 80.0, 100.0, 80.0, 0.5)
sel_layers=st.sidebar.multiselect("Quality layers", ["contract","dbt test","great_expectations","monitor"], default=["contract","dbt test","great_expectations","monitor"])
show_quarantine_only=st.sidebar.checkbox("Quarantined trips only (3D view)", value=False)

f=daily[(daily.date>=start)&(daily.date<=end)&(daily.borough.isin(sel_boroughs))&(daily.source.isin(sel_sources))&(daily.reliability>=min_rel)]
fc=checks_df[(checks_df.date>=start)&(checks_df.date<=end)&(checks_df.layer.isin(sel_layers))]
ft=trips_df[trips_df.borough.isin(sel_boroughs)]
if show_quarantine_only: ft=ft[ft.status=="quarantined"]

# KPIs with deltas vs prior equal-length period
total=int(f.trips.sum()) if not f.empty else 0
span=max((end-start).days,1); prior=daily[(daily.date>=start-pd.Timedelta(days=span))&(daily.date<start)&(daily.borough.isin(sel_boroughs))]
prior_total=int(prior.trips.sum()) if not prior.empty else 0
pass_rate=100*f.passed.sum()/max(total,1) if total else 0
prior_pass=100*prior.passed.sum()/max(prior_total,1) if prior_total else pass_rate
quar=int(f.quarantined.sum()) if not f.empty else 0
rel=float(f.reliability.mean()) if not f.empty else 0
fresh=float(f.freshness_h.mean()) if not f.empty else 0
c1,c2,c3,c4,c5=st.columns(5)
c1.metric("Trips validated", f"{total:,}", delta=f"{total-prior_total:+,} vs prior period" if prior_total else None)
c2.metric("Contract pass rate", f"{pass_rate:.2f}%", delta=f"{pass_rate-prior_pass:+.2f} pts vs prior")
c3.metric("Quarantined rows", f"{quar:,}", delta=f"{100*quar/max(total,1):.2f}% of trips", delta_color="inverse")
c4.metric("Reliability score", f"{rel:.1f} / 100", delta="SCORECARD 100 baseline" if rel>=95 else "below gate — investigate")
c5.metric("Freshness (avg)", f"{fresh:.1f}h", delta="SLA 26h yellow · 1h stream")

tab1,tab2,tab3,tab4,tab5,tab6=st.tabs(["🚦 Quality gates","🎬 Animated reliability","🧊 3D trust space","📋 Contracts & quarantine","🗺️ Zones & boroughs","🏆 Scorecard"])

with tab1:
    st.subheader("Quality gates — contracts, dbt tests, Great Expectations, monitors")
    if fc.empty: st.info("No checks in filter.")
    else:
        agg=fc.groupby(["check","layer","target"],as_index=False).agg(failures=("failures","sum"), runs=("status","count"), fails=("status", lambda s:(s=="FAIL").sum()))
        fig=px.bar(agg.sort_values("failures"), x="failures", y="check", color="layer", orientation="h", template="plotly_dark", labels={"failures":"Failures"})
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fig, width="stretch")
        st.dataframe(agg, width="stretch")
        heat=f.groupby("date",as_index=False)["pass_rate"].mean()
        fig2=px.line(heat, x="date", y="pass_rate", template="plotly_dark", title="Pass rate over time — dips on Jan 18 (volume), Feb 9 (fare), Mar 3 (drift)")
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fig2, width="stretch")

with tab2:
    st.subheader("Press play — reliability evolving day by day")
    if f.empty: st.info("No data in filter.")
    else:
        anim=f.groupby(["date","borough"],as_index=False).agg(trips=("trips","sum"), quarantined=("quarantined","sum"))
        anim["frame"]=anim["date"].dt.strftime("%Y-%m-%d")
        fig=px.bar(anim.sort_values(["date","borough"]), x="borough", y="trips", color="borough", animation_frame="frame", template="plotly_dark", title="Daily trips by borough — animated")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        if fig.layout.updatemenus: fig.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"]=300
        st.plotly_chart(fig, width="stretch")
        cum=anim.copy(); cum["cum_quar"]=cum.groupby("borough")["quarantined"].cumsum()
        figc=px.line(cum.sort_values(["date","borough"]), x="date", y="cum_quar", color="borough", animation_frame="frame", template="plotly_dark", title="Cumulative quarantined rows race — animated")
        figc.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        if figc.layout.updatemenus: figc.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"]=300
        st.plotly_chart(figc, width="stretch")
    st.caption("Animations are native Plotly animation_frame charts — hit ▶ Play.")

with tab3:
    st.subheader("🧊 3D trust space — drag to rotate, scroll to zoom")
    if ft.empty: st.info("No trips in filter.")
    else:
        fig3=px.scatter_3d(ft, x="trip_distance", y="fare_amount", z="duration_min", color="status", symbol="borough", size_max=10, opacity=0.85,
            hover_data=["zone","borough","pickup_hour"], labels={"trip_distance":"Distance (mi)","fare_amount":"Fare ($)","duration_min":"Duration (min)"}, template="plotly_dark",
            title="Every sampled trip in distance × fare × duration space — quarantined rows stand apart")
        fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)", scene=dict(xaxis=dict(backgroundcolor="rgba(20,24,32,.9)"), yaxis=dict(backgroundcolor="rgba(20,24,32,.9)"), zaxis=dict(backgroundcolor="rgba(20,24,32,.9)")), margin=dict(l=0,r=0,t=40,b=0))
        st.plotly_chart(fig3, width="stretch")
        st.subheader("Reliability surface — borough × date terrain")
        surf=f.pivot_table(index="date", columns="borough", values="reliability").sort_index().fillna(97)
        if surf.shape[0]>2 and surf.shape[1]>1:
            figs=go.Figure(data=[go.Surface(z=surf.to_numpy(), x=[d.strftime("%Y-%m-%d") for d in surf.index], y=list(surf.columns), colorscale="Viridis", colorbar=dict(title="Reliability"))])
            figs.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", scene=dict(xaxis_title="Date", yaxis_title="Borough", zaxis_title="Reliability", camera=dict(eye=dict(x=1.5,y=-1.4,z=0.9))), margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(figs, width="stretch")

with tab4:
    st.subheader("Data contracts (config/contracts.yml) — violation blocks the load")
    st.markdown("""
| Source | Key rules | SLA |
|---|---|---|
| yellow_trips | vendor_id ∈ [1,2,6,7] · fare −100..5000 · distance 0..1000 · zones 1..265 · passengers 0..9 | freshness 26h · 50k–500k rows/day |
| weather | zone 1..265 · temp −40..55 °C · precip 0..500 mm · wind 0..300 kph | freshness 3h |
| ride_stream | event_id PK · vendor ∈ [1,2,6,7] · fare 0..5000 · zones 1..265 | freshness 1h |
""")
    st.write("Quarantined sample — rows that would be blocked from RAW:")
    st.dataframe(trips_df[trips_df.status=="quarantined"].head(25), width="stretch")
    fig=px.histogram(trips_df, x="fare_amount", color="status", nbins=50, template="plotly_dark", title="Fare distribution — negative / outlier fares are quarantined")
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fig, width="stretch")

with tab5:
    st.subheader("Borough & zone performance (dim_zone / fact_trips)")
    if f.empty: st.info("No data.")
    else:
        byb=f.groupby("borough",as_index=False).agg(trips=("trips","sum"), avg_fare=("avg_fare","mean"), quarantined=("quarantined","sum"))
        fig=px.bar(byb, x="borough", y="trips", color="borough", template="plotly_dark"); fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fig, width="stretch")
        st.dataframe(byb, width="stretch")
        fig2=px.scatter(ft, x="trip_distance", y="fare_amount", color="borough", template="plotly_dark", title="Fare vs distance by borough")
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)"); st.plotly_chart(fig2, width="stretch")

with tab6:
    st.subheader("Reliability scorecard")
    st.markdown("""
| Component | Score | Weight | Detail |
|---|---:|---:|---|
| Data Contracts | 100 | 35% | 3 sources, 22 columns, 3 PK definitions, 17 constrained columns |
| dbt Quality Gates | 100 | 25% | 3 staging models, 4 mart models, 1 custom SQL test |
| Runtime Quality | 100 | 25% | 3/3 quality modules present |
| Automation | 100 | 15% | 4/4 local automation assets present |
""")
    st.metric("Overall score (filtered reliability)", f"{rel:.1f} / 100")
    st.caption("Demo data is deterministic (seed 42) and shaped from config/contracts.yml, the dbt marts and the quality suites in this repo. No warehouse connection is required to run the console.")
