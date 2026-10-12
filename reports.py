
import io, datetime
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
import plotly.io as pio

def fig_png(fig, width=700, height=380):
    if fig is None: return None
    try:
        return pio.to_image(fig, format="png", width=width, height=height, scale=2)
    except Exception:
        return None

def pdf_report(kpis, faults, charts, report_type="Complete", engineer=""):
    buf=io.BytesIO(); styles=getSampleStyleSheet(); story=[]
    story += [Paragraph("EV Electrical Diagnostics and Validation Report",styles["Title"]),
              Spacer(1,6*mm),
              Paragraph(f"Report ID: EVDR-{datetime.datetime.now():%Y%m%d-%H%M%S}",styles["Normal"]),
              Paragraph(f"Generated: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}",styles["Normal"]),
              Paragraph(f"Test Engineer: {engineer or 'Not specified'}",styles["Normal"]),
              Paragraph(f"Report Type: {report_type}",styles["Normal"]), Spacer(1,5*mm)]
    story.append(Paragraph("Executive Summary",styles["Heading2"]))
    story.append(Paragraph(f"Overall assessment: <b>{kpis.get('assessment','Not Evaluated')}</b>",styles["Normal"]))
    rows=[["Metric","Value"]]
    for k,v in kpis.items():
        if k!="assessment": rows.append([k, "N/A — Signal Not Available" if v is None else str(v)])
    t=Table(rows); t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.grey),
        ("BACKGROUND",(0,0),(-1,0),colors.lightgrey),("FONTSIZE",(0,0),(-1,-1),7)]))
    story += [t, Spacer(1,5*mm)]
    if report_type=="Complete" and faults is not None and not faults.empty:
        story.append(Paragraph("Fault Events",styles["Heading2"]))
        ft=faults.copy()
        cols=[c for c in ["Event ID","Subsystem","Signal","First Timestamp","Measured","Warning Limit","Critical Limit","Deviation","Severity","Status"] if c in ft]
        t=Table([cols]+ft[cols].astype(str).values.tolist()); t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.grey),("FONTSIZE",(0,0),(-1,-1),6)]))
        story += [t, Spacer(1,5*mm)]
    story.append(Paragraph("Graphs Generated From Uploaded Data",styles["Heading2"]))
    added=False
    for title,fig in charts.items():
        png=fig_png(fig)
        if png:
            story += [Paragraph(title,styles["Heading3"]), Image(io.BytesIO(png),width=170*mm,height=92*mm), Spacer(1,4*mm)]
            added=True
    if not added: story.append(Paragraph("No supported graphs were available.",styles["Normal"]))
    story += [Spacer(1,5*mm), Paragraph("Calculation Methods",styles["Heading2"]),
              Paragraph("Ah and kWh use trapezoidal integration over actual timestamps; configured maximum integration gaps are excluded. Battery power is voltage multiplied by current. Charger efficiency is calculated only when input and output power measurements are available.",styles["Normal"])]
    SimpleDocTemplate(buf,pagesize=A4,rightMargin=15*mm,leftMargin=15*mm,topMargin=15*mm,bottomMargin=15*mm).build(story)
    buf.seek(0); return buf

def excel_report(kpis, faults, intervals, thresholds, processed_df=None):
    buf=io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xl:
        pd.DataFrame([kpis]).T.rename(columns={0:"Value"}).to_excel(xl,sheet_name="Executive Summary")
        pd.DataFrame([{"Item":k,"Value":v} for k,v in kpis.items()]).to_excel(xl,sheet_name="Test Metadata",index=False)
        if faults is not None: faults.to_excel(xl,sheet_name="Fault Log",index=False)
        pd.DataFrame(intervals).to_excel(xl,sheet_name="Charging Discharging",index=False)
        pd.DataFrame([{"Threshold":k,"Value":v} for k,v in thresholds.items()]).to_excel(xl,sheet_name="Threshold Configuration",index=False)
        if processed_df is not None:
            processed_df.head(100000).to_excel(xl,sheet_name="Processed Data",index=False)
    buf.seek(0); return buf
