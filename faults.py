
import pandas as pd, numpy as np

def evaluate_thresholds(df, signals, th, current_sign=1):
    events=[]
    def add(signal, subsystem, value, warn, crit, direction, ts):
        if value is None or pd.isna(value): return
        if direction=="high":
            sev = "Critical" if crit is not None and value>=crit else ("Warning" if warn is not None and value>=warn else None)
            dev = value-(crit if sev=="Critical" and crit is not None else warn)
        else:
            sev = "Critical" if crit is not None and value<=crit else ("Warning" if warn is not None and value<=warn else None)
            dev = (crit if sev=="Critical" and crit is not None else warn)-value
        if sev:
            events.append({"Subsystem":subsystem,"Signal":signal,"First Timestamp":str(ts),
                           "Measured":round(float(value),4),"Warning Limit":warn,"Critical Limit":crit,
                           "Deviation":round(float(dev),4),"Severity":sev,"Samples":1,
                           "Classification":"Configured threshold violation","Status":"Active"})
    checks = [
        ("cell_v_min","BMS","cell_v_min_low_warning","cell_v_min_low_critical","low"),
        ("cell_v_max","BMS","cell_v_max_high_warning","cell_v_max_high_critical","high"),
        ("pack_voltage","BMS","pack_v_min_low_warning","pack_v_min_low_critical","low"),
        ("temp_max","BMS","temp_high_warning","temp_high_critical","high"),
        ("temp_min","BMS","temp_low_warning","temp_low_critical","low"),
        ("charger_temp","Charger","charger_temp_high_warning","charger_temp_high_critical","high"),
    ]
    for sig,sub,wk,ck,direction in checks:
        if sig in signals:
            s=pd.to_numeric(df[signals[sig]],errors="coerce").dropna()
            if len(s):
                extreme = s.max() if direction=="high" else s.min()
                ts = df.loc[s.idxmax() if direction=="high" else s.idxmin(), "_timestamp"] if "_timestamp" in df else None
                add(sig,sub,extreme,th[wk],th[ck],direction,ts)
    if "pack_current" in signals:
        i=pd.to_numeric(df[signals["pack_current"]],errors="coerce")*current_sign
        if i.notna().any():
            add("discharge_current","BMS",-i.min(),th["discharge_current_warning"],th["discharge_current_critical"],"high",df.loc[i.idxmin(),"_timestamp"] if "_timestamp" in df else None)
            add("charge_current","BMS",i.max(),th["charge_current_warning"],th["charge_current_critical"],"high",df.loc[i.idxmax(),"_timestamp"] if "_timestamp" in df else None)
    if {"cell_v_min","cell_v_max"} <= signals.keys():
        spread=pd.to_numeric(df[signals["cell_v_max"]],errors="coerce")-pd.to_numeric(df[signals["cell_v_min"]],errors="coerce")
        if spread.notna().any():
            add("cell_voltage_spread","BMS",spread.max(),th["cell_v_spread_warning"],th["cell_v_spread_critical"],"high",df.loc[spread.idxmax(),"_timestamp"] if "_timestamp" in df else None)
    if "charger_cmd_current" in signals and "charger_out_current" in signals:
        cmd=pd.to_numeric(df[signals["charger_cmd_current"]],errors="coerce")
        act=pd.to_numeric(df[signals["charger_out_current"]],errors="coerce")
        err=(act-cmd).abs()
        if err.notna().any():
            add("charger_current_tracking_error","Charger",err.max(),th["charger_current_error_warning"],th["charger_current_error_critical"],"high",df.loc[err.idxmax(),"_timestamp"] if "_timestamp" in df else None)
    for n,e in enumerate(events,1): e["Event ID"]=f"EVT-{n:04d}"
    return pd.DataFrame(events)

def overall_assessment(faults, data_available):
    if not data_available: return "Not Evaluated"
    if faults.empty: return "Inconclusive"
    if (faults["Severity"]=="Critical").any(): return "Fail"
    return "Inconclusive"
