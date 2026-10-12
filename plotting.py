
import plotly.graph_objects as go
import plotly.express as px

def _fig(y, title, ytitle):
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=y.index,y=y.values,mode="lines",name=title))
    fig.update_layout(title=title,xaxis_title="Timestamp",yaxis_title=ytitle,template="plotly_white",height=380)
    return fig

def time_series(df, signals, key, title, ytitle):
    if key not in signals or "_timestamp" not in df: return None
    y=pd.to_numeric(df[signals[key]],errors="coerce")
    y.index=df["_timestamp"]
    return _fig(y.dropna(),title,ytitle)

def power_chart(df):
    if not {"pack_voltage","pack_current"} <= signals_keys(df) or "_timestamp" not in df: return None
    return None

def signals_keys(df):
    return set(df.columns)

def fault_timeline(faults):
    if faults is None or faults.empty: return None
    fig=px.scatter(faults,x="First Timestamp",y="Signal",color="Severity",
                   color_discrete_map={"Warning":"#F9A825","Critical":"#C62828"},
                   hover_data=["Measured","Deviation","Event ID"],title="Fault Timeline")
    fig.update_layout(template="plotly_white",height=380)
    return fig
