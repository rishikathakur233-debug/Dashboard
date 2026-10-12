
import pandas as pd

SIGNAL_ALIASES = {
    "timestamp": ["timestamp","time","date time","datetime","date_time","utc time","record time","t"],
    "elapsed_time": ["elapsed time","elapsed_time","time_s","test time","relative time"],
    "vehicle_id": ["vehicle id","vehicle_id","vehicle no","vehicle number","vin","vehicle"],
    "test_id": ["test id","test_id","test no","test number","run id","run_id"],
    "soc": ["soc","state of charge","battery soc","soc %","soc_percent"],
    "soh": ["soh","state of health","battery soh"],
    "pack_voltage": ["pack voltage","battery voltage","batt voltage","voltage","dc voltage","total voltage"],
    "pack_current": ["pack current","battery current","batt current","current","dc current"],
    "cell_v_min": ["min cell voltage","minimum cell voltage","cell voltage min","vmin"],
    "cell_v_max": ["max cell voltage","maximum cell voltage","cell voltage max","vmax"],
    "cell_v_diff": ["cell voltage difference","delta cell voltage","cell delta","voltage difference"],
    "temp_min": ["min temperature","minimum battery temperature","battery temp min","tmin"],
    "temp_max": ["max temperature","maximum battery temperature","battery temp max","tmax"],
    "temp_avg": ["avg temperature","average battery temperature","battery temp avg"],
    "mosfet_temp": ["mosfet temperature","mosfet temp","bms mosfet temperature"],
    "bms_fault": ["bms fault","bms fault code","fault code","bms state","protection flag"],
    "contactor": ["contactor","contactor status","main contactor"],
    "precharge": ["precharge","precharge status"],
    "charger_ac_voltage": ["ac input voltage","charger input voltage","ac voltage","input voltage"],
    "charger_ac_current": ["ac input current","charger input current","ac current","input current"],
    "charger_out_voltage": ["charger output voltage","output voltage","dc output voltage"],
    "charger_out_current": ["charger output current","output current","dc output current","charging current"],
    "charger_cmd_current": ["commanded current","charge current command","current command","requested current"],
    "charger_temp": ["charger temperature","charger temp","converter temperature"],
    "charger_fault": ["charger fault","charger fault code","charger error"],
    "charger_state": ["charger state","charger status","charging status"],
    "odometer": ["odometer","odometer reading","distance","total distance","km"],
    "can_id": ["can id","can_id","message id","arb id"],
    "can_dlc": ["dlc","data length"],
    "can_payload": ["payload","data","data bytes","can data"],
}

DEFAULT_THRESHOLDS = {
    "cell_v_min_low_warning": 3.00, "cell_v_min_low_critical": 2.80,
    "cell_v_max_high_warning": 4.20, "cell_v_max_high_critical": 4.25,
    "pack_v_min_low_warning": 48.0, "pack_v_min_low_critical": 44.0,
    "pack_v_max_high_warning": 84.0, "pack_v_max_high_critical": 88.0,
    "discharge_current_warning": 150.0, "discharge_current_critical": 180.0,
    "charge_current_warning": 100.0, "charge_current_critical": 120.0,
    "temp_high_warning": 55.0, "temp_high_critical": 60.0,
    "temp_low_warning": 0.0, "temp_low_critical": -10.0,
    "cell_v_spread_warning": 0.05, "cell_v_spread_critical": 0.10,
    "temp_spread_warning": 8.0, "temp_spread_critical": 12.0,
    "charger_current_error_warning": 2.0, "charger_current_error_critical": 5.0,
    "charger_temp_high_warning": 70.0, "charger_temp_high_critical": 80.0,
    "max_integration_gap_s": 30.0, "debounce_s": 1.0,
}

COLORS = {"pass":"#2E7D32","warning":"#F9A825","investigate":"#EF6C00",
          "critical":"#C62828","na":"#757575","info":"#1565C0"}

def normalize_header(s):
    return str(s).strip().lower().replace("\n"," ").replace("_"," ").strip()

def detect_signals(columns):
    norm = {c: normalize_header(c) for c in columns}
    found = {}
    for std, aliases in SIGNAL_ALIASES.items():
        for col, n in norm.items():
            if n == std or n in [normalize_header(a) for a in aliases]:
                found[std] = col; break
        if std not in found:
            for col, n in norm.items():
                if any(a.lower() in n for a in aliases):
                    found[std] = col; break
    return found

def detect_metadata(df, columns):
    text = " ".join(str(c) for c in columns)
    meta = {"vehicle_id": None, "test_id": None, "variant": None, "date": None}
    for c in columns:
        n = normalize_header(c)
        if meta["vehicle_id"] is None and ("vehicle" in n or n == "vin"):
            vals = df[c].dropna().astype(str)
            if len(vals): meta["vehicle_id"] = vals.mode().iloc[0]
        if meta["test_id"] is None and ("test" in n or "run" in n):
            vals = df[c].dropna().astype(str)
            if len(vals): meta["test_id"] = vals.mode().iloc[0]
        if meta["variant"] is None and ("variant" in n or "power" in n or "rating" in n):
            vals = df[c].dropna().astype(str)
            if len(vals): meta["variant"] = vals.mode().iloc[0]
    return meta
