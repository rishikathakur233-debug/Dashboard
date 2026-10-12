import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import tempfile
import os

# Optional Imports for DBC and BLF handling
try:
    import cantools
    HAS_CANTOOLS = True
except ImportError:
    HAS_CANTOOLS = False

try:
    import can
    HAS_PYTHON_CAN = True
except ImportError:
    HAS_PYTHON_CAN = False

st.set_page_config(
    page_title="EV Electrical Diagnostics Dashboard",
    page_icon="⚡",
    layout="wide"
)

# Signal Mapping Engine
STANDARD_SIGNALS = {
    "timestamp": ["timestamp", "time", "t", "datetime", "log_time"],
    "pack_voltage": ["pack_voltage", "battery_voltage", "v_pack", "v_batt", "pack_v"],
    "pack_current": ["pack_current", "battery_current", "i_pack", "i_batt", "pack_a"],
    "soc": ["soc", "state_of_charge", "battery_soc"],
    "max_cell_v": ["max_cell_voltage", "v_cell_max", "cell_v_max"],
    "min_cell_v": ["min_cell_voltage", "v_cell_min", "cell_v_min"],
}

def map_columns(df_cols):
    mapping = {}
    cols_lower = {str(c).lower().strip(): c for c in df_cols}
    for std_key, aliases in STANDARD_SIGNALS.items():
        found = None
        for alias in aliases:
            if alias in cols_lower:
                found = cols_lower[alias]
                break
        mapping[std_key] = found
    return mapping

def parse_blf(file_bytes, dbc_db=None):
    if not HAS_PYTHON_CAN:
        st.error("`python-can` package missing. Please ensure it is in requirements.txt.")
        return pd.DataFrame()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".blf") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        log = can.BLFReader(tmp_path)
        records = []
        for msg in log:
            rec = {
                "timestamp": msg.timestamp,
                "arbitration_id": hex(msg.arbitration_id),
                "dlc": msg.dlc,
                "data": msg.data.hex()
            }
            if dbc_db:
                try:
                    decoded = dbc_db.decode_message(msg.arbitration_id, msg.data)
                    rec.update(decoded)
                except Exception:
                    pass
            records.append(rec)
        df = pd.DataFrame(records)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return df

def process_telemetry(df, mapping, polarity_invert=False):
    pdf = df.copy()
    ts_col = mapping.get("timestamp")
    if ts_col and ts_col in pdf.columns:
        pdf["parsed_time"] = pd.to_datetime(pdf[ts_col], errors="coerce")
        pdf = pdf.sort_values("parsed_time").reset_index(drop=True)
        pdf["time_diff_s"] = pdf["parsed_time"].diff().dt.total_seconds().fillna(0)
    else:
        pdf["parsed_time"] = pd.date_range(start="2026-10-12 08:00:00", periods=len(pdf), freq="1S")
        pdf["time_diff_s"] = 1.0

    v_col = mapping.get("pack_voltage")
    i_col = mapping.get("pack_current")
    pdf["Voltage_V"] = pd.to_numeric(pdf[v_col], errors="coerce") if v_col else 0.0
    pdf["Current_A"] = pd.to_numeric(pdf[i_col], errors="coerce") if i_col else 0.0
    
    if polarity_invert:
        pdf["Current_A"] = -1.0 * pdf["Current_A"]
        
    pdf["Power_kW"] = (pdf["Voltage_V"] * pdf["Current_A"]) / 1000.0
    pdf["Discharge_Current_A"] = pdf["Current_A"].apply(lambda x: x if x > 0 else 0)
    pdf["Charge_Current_A"] = pdf["Current_A"].apply(lambda x: abs(x) if x < 0 else 0)
    
    dt_hours = pdf["time_diff_s"] / 3600.0
    pdf["Discharge_kWh"] = (pdf["Discharge_Current_A"] * pdf["Voltage_V"] / 1000.0) * dt_hours
    pdf["Charge_kWh"] = (pdf["Charge_Current_A"] * pdf["Voltage_V"] / 1000.0) * dt_hours
    
    pdf["Cum_Discharge_kWh"] = pdf["Discharge_kWh"].cumsum()
    pdf["Cum_Charge_kWh"] = pdf["Charge_kWh"].cumsum()

    max_v_col = mapping.get("max_cell_v")
    min_v_col = mapping.get("min_cell_v")
    if max_v_col and min_v_col:
        pdf["Cell_Delta_mV"] = (pd.to_numeric(pdf[max_v_col], errors="coerce") - pd.to_numeric(pdf[min_v_col], errors="coerce")) * 1000.0
    else:
        pdf["Cell_Delta_mV"] = 0.0

    soc_col = mapping.get("soc")
    pdf["SOC_%"] = pd.to_numeric(pdf[soc_col], errors="coerce") if soc_col else np.nan
    return pdf

def detect_faults(df, limits):
    faults = []
    if "Cell_Delta_mV" in df.columns:
        spread = df[df["Cell_Delta_mV"] > limits["max_cell_spread_mv"]]
        if not spread.empty:
            faults.append({
                "Event ID": "FLT-CELL-SPREAD",
                "Subsystem": "BMS",
                "Severity": "RED",
                "Description": f"Cell Delta Spread > {limits['max_cell_spread_mv']} mV",
                "Occurrences": len(spread),
                "Peak Value": f"{spread['Cell_Delta_mV'].max():.1f} mV"
            })
    if "Voltage_V" in df.columns:
        ov = df[df["Voltage_V"] > limits["over_voltage_v"]]
        if not ov.empty:
            faults.append({
                "Event ID": "FLT-PACK-OV",
                "Subsystem": "Battery Pack",
                "Severity": "RED",
                "Description": f"Pack Overvoltage > {limits['over_voltage_v']} V",
                "Occurrences": len(ov),
                "Peak Value": f"{ov['Voltage_V'].max():.1f} V"
            })
    return pd.DataFrame(faults)

# --- SIDEBAR CONTROLS ---
st.sidebar.title("⚡ Data Ingestion & Config")
uploaded_files = st.sidebar.file_uploader(
    "Upload Telemetry (.csv, .xlsx, .blf)",
    type=["csv", "xlsx", "xls", "blf"],
    accept_multiple_files=True
)

dbc_file = st.sidebar.file_uploader("Upload DBC Database (.dbc)", type=["dbc"])
dbc_db = None
if dbc_file and HAS_CANTOOLS:
    try:
        dbc_str = dbc_file.getvalue().decode("utf-8", errors="ignore")
        dbc_db = cantools.database.load_string(dbc_str, database_format="dbc")
        st.sidebar.success("DBC Loaded")
    except Exception as e:
        st.sidebar.error(f"DBC Error: {e}")

over_voltage = st.sidebar.number_input("Overvoltage Limit (V)", value=420.0)
under_voltage = st.sidebar.number_input("Undervoltage Limit (V)", value=300.0)
max_cell_spread = st.sidebar.number_input("Max Cell Delta (mV)", value=50.0)
invert_polarity = st.sidebar.checkbox("Invert Current Polarity", value=False)

threshold_limits = {
    "over_voltage_v": over_voltage,
    "under_voltage_v": under_voltage,
    "max_cell_spread_mv": max_cell_spread
}

# --- MAIN DASHBOARD LAYOUT ---
st.title("⚡ EV Electrical Diagnostics Dashboard")

raw_dfs = []
if uploaded_files:
    for f in uploaded_files:
        ext = f.name.split(".")[-1].lower()
        if ext == "blf":
            tdf = parse_blf(f.getvalue(), dbc_db)
        elif ext == "csv":
            tdf = pd.read_csv(f)
        else:
            tdf = pd.read_excel(f)
        raw_dfs.append(tdf)
    combined_raw = pd.concat(raw_dfs, ignore_index=True)
    st.success(f"Processed {len(uploaded_files)} log file(s).")
else:
    st.info("Upload your CSV, XLSX, or BLF file in the sidebar to perform automated diagnostics.")
    # Baseline demo frame
    t = pd.date_range(start="2026-10-12 09:00:00", periods=300, freq="1S")
    v = 380 - (np.arange(300) * 0.05)
    i = np.where((np.arange(300) > 50) & (np.arange(300) < 200), 100, -20)
    combined_raw = pd.DataFrame({
        "timestamp": t,
        "pack_voltage": v,
        "pack_current": i,
        "soc": 90 - (np.arange(300) * 0.02),
        "max_cell_voltage": (v / 108) + 0.02,
        "min_cell_voltage": (v / 108) - 0.01
    })

mapped_cols = map_columns(combined_raw.columns)
processed_df = process_telemetry(combined_raw, mapped_cols, polarity_invert=invert_polarity)
detected_faults = detect_faults(processed_df, threshold_limits)

# Metrics Cards
c1, c2, c3, c4 = st.columns(4)
c1.metric("Discharge Energy", f"{processed_df['Cum_Discharge_kWh'].max():.2f} kWh")
c2.metric("Charge Energy", f"{processed_df['Cum_Charge_kWh'].max():.2f} kWh")
c3.metric("Peak Power Demand", f"{processed_df['Power_kW'].max():.1f} kW")
c4.metric("Max Cell Delta", f"{processed_df['Cell_Delta_mV'].max():.1f} mV")

st.markdown("---")

fig = make_subplots(specs=[[{"secondary_y": True}]])
fig.add_trace(go.Scatter(x=processed_df["parsed_time"], y=processed_df["Power_kW"], name="Power (kW)", line=dict(color="#10B981")), secondary_y=False)
fig.add_trace(go.Scatter(x=processed_df["parsed_time"], y=processed_df["SOC_%"], name="SOC (%)", line=dict(color="#3B82F6", dash="dash")), secondary_y=True)
fig.update_layout(title="Power Profile & State of Charge", height=400)
st.plotly_chart(fig, use_container_width=True)

st.subheader("🚨 Automated Diagnostics & Fault Findings")
if not detected_faults.empty:
    st.dataframe(detected_faults, use_container_width=True)
else:
    st.success("No parameter threshold violations detected.")

csv_out = processed_df.to_csv(index=False).encode('utf-8')
st.download_button("📥 Export Diagnostic Report (CSV)", data=csv_out, file_name="EV_Diagnostics_Summary.csv", mime="text/csv")