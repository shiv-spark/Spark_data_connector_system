import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

st.set_page_config(
    page_title="Universal Data Connector",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# LIGHT THEME CSS
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Base */
.stApp { background:#f1f5f9; }
#MainMenu, footer, header { visibility:hidden; }
section[data-testid="stSidebar"] {
    background:#ffffff;
    border-right:2px solid #e2e8f0;
}
section[data-testid="stSidebar"] .stMarkdown p { color:#374151; }
section[data-testid="stSidebar"] h3 { color:#1e293b !important; }

/* Typography */
h1,h2,h3,h4 { color:#1e293b !important; font-weight:700 !important; }
p { color:#475569; }
label { color:#374151 !important; }
.stRadio label { color:#374151 !important; font-weight:500 !important; }
small, .stCaption { color:#94a3b8 !important; }

/* KPI cards */
.kpi {
    background:#fff; border:1px solid #e2e8f0; border-radius:12px;
    padding:14px 16px; text-align:center;
    box-shadow:0 1px 4px rgba(0,0,0,.05); margin-bottom:8px;
}
.kpi-v { font-size:1.75rem; font-weight:800; line-height:1.15; margin:0; }
.kpi-l { font-size:.6rem; color:#94a3b8; letter-spacing:.07em;
          text-transform:uppercase; margin-top:3px; }

/* Section heading */
.shd {
    font-size:1.2rem; font-weight:800; color:#1e293b;
    border-left:4px solid #6366f1; padding-left:12px;
    margin:0 0 1.2rem 0; line-height:1.3;
}

/* Alert boxes */
.bi { background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px;
      padding:10px 14px; color:#1d4ed8; font-size:.82rem; margin:6px 0; }
.bw { background:#fffbeb; border:1px solid #fde68a; border-radius:8px;
      padding:10px 14px; color:#92400e; font-size:.82rem; margin:6px 0; }
.bo { background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px;
      padding:10px 14px; color:#166534; font-size:.82rem; margin:6px 0; }
.be { background:#fef2f2; border:1px solid #fecaca; border-radius:8px;
      padding:10px 14px; color:#991b1b; font-size:.82rem; margin:6px 0; }

/* Status badges */
.bdg {
    display:inline-block; padding:3px 11px; border-radius:20px;
    font-size:.68rem; font-weight:700; letter-spacing:.05em;
}
.b-active   { background:#dcfce7; color:#15803d; }
.b-paused   { background:#fef9c3; color:#854d0e; }
.b-failed   { background:#fee2e2; color:#991b1b; }
.b-success  { background:#dcfce7; color:#15803d; }
.b-running  { background:#dbeafe; color:#1d4ed8; }
.b-skipped  { background:#fef9c3; color:#854d0e; }
.b-unknown  { background:#f1f5f9; color:#64748b; }
.b-healthy  { background:#dcfce7; color:#15803d; }
.b-degraded { background:#fee2e2; color:#991b1b; }
.b-warning  { background:#fef9c3; color:#854d0e; }
.b-created  { background:#dbeafe; color:#1d4ed8; }

/* Pipeline row card */
.prow {
    background:#fff; border:1px solid #e2e8f0; border-radius:10px;
    padding:12px 16px; margin-bottom:6px;
    box-shadow:0 1px 3px rgba(0,0,0,.04);
}
.pname { font-weight:700; color:#1e293b; font-size:.95rem; }
.pmeta { font-size:.73rem; color:#94a3b8; margin-top:3px; }

/* Chat bubbles */
.muser { display:flex; justify-content:flex-end; margin:6px 0; }
.mbot  { display:flex; gap:8px; align-items:flex-start; margin:6px 0; }
.bubu {
    background:#6366f1; color:#fff;
    padding:10px 16px; border-radius:18px 18px 4px 18px;
    max-width:72%; font-size:.84rem; line-height:1.6; word-wrap:break-word;
}
.bubb {
    background:#fff; color:#334155;
    padding:12px 16px; border-radius:18px 18px 18px 4px;
    max-width:76%; font-size:.84rem; line-height:1.7; word-wrap:break-word;
    border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,.05);
}
.bav {
    width:32px; height:32px; border-radius:8px; flex-shrink:0;
    background:linear-gradient(135deg,#6366f1,#06b6d4);
    display:flex; align-items:center; justify-content:center;
    font-size:.9rem; margin-top:2px;
}

/* Inputs */
.stTextInput input, .stTextArea textarea, .stNumberInput input {
    background:#fff !important; border:1px solid #d1d5db !important;
    color:#111827 !important; border-radius:8px !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color:#6366f1 !important;
    box-shadow:0 0 0 3px rgba(99,102,241,.15) !important;
}

/* Selectbox */
div[data-baseweb="select"] > div {
    background:#fff !important; border:1px solid #d1d5db !important;
    border-radius:8px !important; color:#111827 !important;
}
div[data-baseweb="select"] span { color:#111827 !important; }

/* Buttons */
.stButton > button {
    background:#fff !important; color:#374151 !important;
    border:1px solid #d1d5db !important; border-radius:8px !important;
    font-weight:600 !important; transition:all .15s !important;
    padding:6px 14px !important;
}
.stButton > button:hover {
    border-color:#6366f1 !important; color:#6366f1 !important;
    background:#f5f3ff !important;
}

/* Form submit button */
.stFormSubmitButton > button {
    background:#6366f1 !important; color:#fff !important;
    border:1px solid #6366f1 !important; border-radius:8px !important;
    font-weight:600 !important; width:100% !important;
}
.stFormSubmitButton > button:hover { background:#4f46e5 !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { border-bottom:2px solid #e2e8f0; }
.stTabs [data-baseweb="tab"]      { color:#64748b; font-weight:500; }
.stTabs [aria-selected="true"]    { color:#6366f1 !important;
                                    font-weight:700 !important;
                                    border-bottom:2px solid #6366f1 !important; }

/* Expander */
details summary { background:#f8fafc !important; border-radius:8px !important;
                  border:1px solid #e2e8f0 !important; padding:8px 12px !important; }

/* Dataframe */
.stDataFrame { border-radius:10px; overflow:hidden; }

/* Divider */
hr { border-color:#e2e8f0 !important; }

/* Metric widget */
[data-testid="stMetric"] { background:#fff; border:1px solid #e2e8f0;
    border-radius:10px; padding:10px 14px;
    box-shadow:0 1px 3px rgba(0,0,0,.04); }
[data-testid="stMetricLabel"] { color:#64748b !important; font-size:.75rem !important; }
[data-testid="stMetricValue"] { color:#1e293b !important; font-weight:700 !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
DEFAULTS = {
    "api_base":     "http://localhost:8000",
    "or_key":       "",
    "or_model":     "openai/gpt-oss-120b:free",
    "chat_history": [],
    "tbl_offset":   0,
    "ingest_type":  "csv",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def api(method, endpoint, **kwargs):
    try:
        r = getattr(requests, method)(
            f"{st.session_state.api_base}{endpoint}", timeout=15, **kwargs)
        if r.content:
            try:    return r.status_code, r.json()
            except: return r.status_code, {"raw": r.text}
        return r.status_code, {}
    except requests.exceptions.ConnectionError:
        return 0, {"error": "Cannot connect to API. Is the container running?"}
    except Exception as e:
        return 0, {"error": str(e)}

def fdt(dt):
    if not dt: return "—"
    try:    return datetime.fromisoformat(str(dt)).strftime("%d %b %Y  %H:%M")
    except: return str(dt)[:16]

def kpi(val, lbl, color="#6366f1"):
    return (f'<div class="kpi"><p class="kpi-v" style="color:{color}">{val}</p>'
            f'<p class="kpi-l">{lbl}</p></div>')

def bdg(status):
    s   = str(status).lower().strip()
    cls = {"active":"b-active","paused":"b-paused","failed":"b-failed",
           "success":"b-success","running":"b-running","skipped":"b-skipped",
           "healthy":"b-healthy","degraded":"b-degraded","warning":"b-warning",
           "created":"b-created"}.get(s, "b-unknown")
    return f'<span class="bdg {cls}">{status.upper()}</span>'

PLOT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#475569", size=12),
    margin=dict(l=0, r=0, t=32, b=0), height=270,
)
CLR = ["#6366f1","#06b6d4","#10b981","#f59e0b","#ef4444","#8b5cf6","#ec4899"]

# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚡ Data Connector")
    st.markdown("---")

    new_url = st.text_input("API Base URL", value=st.session_state.api_base)
    if new_url != st.session_state.api_base:
        st.session_state.api_base = new_url

    hc, _ = api("get", "/health")
    if hc == 200:
        st.markdown('<div class="bo">🟢 API Connected</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="be">🔴 API Unreachable</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**Navigation**")
    page = st.radio("nav", [
        "📊 Dashboard",
        "➕ Create Pipeline",
        "📋 Manage Pipelines",
        "📥 Direct Ingest",
        "🗄️ Data Preview",
        "📈 Metrics",
        "📜 Logs",
        "🔗 Multi-Source Pipeline",
        "🤖 AI Assistant",
    ], label_visibility="collapsed")

    st.markdown("---")
    st.caption("SparkBrains · Universal Data Connector · v1.7")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 1 — DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════
if page == "📊 Dashboard":
    st.markdown('<div class="shd">📊 Dashboard</div>', unsafe_allow_html=True)

    code, data = api("get", "/dashboard/summary")
    if code != 200:
        st.error(f"Failed to load dashboard: {data.get('error', data)}")
        st.stop()

    m      = data.get("metrics", {})         or {}
    ph     = data.get("pipeline_health", []) or []
    daily  = data.get("daily", [])           or []
    h      = data.get("system_health", "UNKNOWN")
    hc2    = {"HEALTHY":"#10b981","WARNING":"#f59e0b","DEGRADED":"#ef4444"}.get(h,"#64748b")

    # KPI values — metrics window is 7 days, fallback to pipeline_health aggregates
    total_runs = m.get("total_runs") or sum(p.get("total_runs", 0) for p in ph)
    success    = m.get("success")    or sum(p.get("success", 0)    for p in ph)
    failed     = m.get("failed")     or sum(p.get("failed", 0)     for p in ph)
    total_rows = m.get("total_rows") or sum(d.get("rows", 0) for d in daily)
    rate       = m.get("success_rate_pct")
    if not rate and total_runs:
        rate = round(success / total_runs * 100, 1)
    rate = rate or 0

    # KPI row
    c0,c1,c2,c3,c4,c5 = st.columns(6)
    c0.markdown(kpi(h,                    "HEALTH",     hc2),       unsafe_allow_html=True)
    c1.markdown(kpi(total_runs,           "TOTAL RUNS", "#6366f1"), unsafe_allow_html=True)
    c2.markdown(kpi(success,              "SUCCESS",    "#10b981"), unsafe_allow_html=True)
    c3.markdown(kpi(failed,               "FAILED",     "#ef4444"), unsafe_allow_html=True)
    c4.markdown(kpi(f"{rate}%",           "RATE",       "#6366f1"), unsafe_allow_html=True)
    c5.markdown(kpi(f"{int(total_rows):,}","ROWS",      "#06b6d4"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts row 1
    r1a, r1b = st.columns(2)
    with r1a:
        st.markdown("**📅 Last 7 Days**")
        if daily:
            df_d = pd.DataFrame(daily)
            df_d["day"] = pd.to_datetime(df_d["day"]).dt.strftime("%d %b")
            fig = go.Figure()
            for col, col_color in [("success","#10b981"),("failed","#ef4444"),("skipped","#f59e0b")]:
                if col in df_d.columns:
                    fig.add_bar(x=df_d["day"], y=df_d[col], name=col.title(), marker_color=col_color)
            fig.update_layout(**PLOT, barmode="stack", legend=dict(orientation="h", y=-0.3))
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(gridcolor="#e2e8f0")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available yet.")

    with r1b:
        st.markdown("**🔌 Connector Breakdown**")
        conns = data.get("connectors", [])
        if conns:
            df_c = pd.DataFrame(conns)
            fig = px.pie(df_c, names="connector_type", values="runs",
                         color_discrete_sequence=CLR, hole=0.4)
            fig.update_layout(**PLOT, legend=dict(orientation="h", y=-0.25))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available yet.")

    # Charts row 2
    r2a, r2b = st.columns(2)
    with r2a:
        st.markdown("**📈 30-Day Row Volume**")
        vt = data.get("volume_trend", [])
        if vt:
            df_v = pd.DataFrame(vt)
            df_v["day"] = pd.to_datetime(df_v["day"]).dt.strftime("%d %b")
            fig = px.area(df_v, x="day", y="total_rows", color_discrete_sequence=["#6366f1"])
            fig.update_layout(**PLOT)
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(gridcolor="#e2e8f0")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available yet.")

    with r2b:
        st.markdown("**⏱️ Hourly Activity (Last 24h)**")
        hourly = data.get("hourly", [])
        if hourly:
            df_h = pd.DataFrame(hourly)
            df_h["hour"] = pd.to_datetime(df_h["hour"]).dt.strftime("%H:%M")
            fig = go.Figure()
            fig.add_scatter(x=df_h["hour"], y=df_h.get("success", [0]*len(df_h)),
                            name="Success", line=dict(color="#10b981"),
                            fill="tozeroy", fillcolor="rgba(16,185,129,.12)")
            fig.add_scatter(x=df_h["hour"], y=df_h.get("failed", [0]*len(df_h)),
                            name="Failed",  line=dict(color="#ef4444"),
                            fill="tozeroy", fillcolor="rgba(239,68,68,.10)")
            fig.update_layout(**PLOT, legend=dict(orientation="h", y=-0.3))
            fig.update_xaxes(showgrid=False)
            fig.update_yaxes(gridcolor="#e2e8f0")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data available yet.")

    # Pipeline health table
    st.markdown("---")
    st.markdown("**🏥 Pipeline Health**")
    if ph:
        df_ph = pd.DataFrame(ph)
        if "last_run_at" in df_ph.columns:
            df_ph["last_run_at"] = df_ph["last_run_at"].apply(fdt)
        if "success_rate" in df_ph.columns:
            df_ph["success_rate"] = df_ph["success_rate"].apply(
                lambda x: f"{x}%" if x is not None else "—")
        show = [c for c in ["pipeline_id","connector_type","total_runs","success",
                             "failed","success_rate","avg_duration","last_status","last_run_at"]
                if c in df_ph.columns]
        st.dataframe(df_ph[show], use_container_width=True, hide_index=True)
    else:
        st.info("No pipeline metrics found. Run a pipeline first.")

    # Top failing
    tf = data.get("top_failing", [])
    if tf:
        st.markdown("---")
        st.markdown("**⚠️ Top Failing Pipelines (Last 7 Days)**")
        df_tf = pd.DataFrame(tf)
        if "last_failed_at" in df_tf.columns:
            df_tf["last_failed_at"] = df_tf["last_failed_at"].apply(fdt)
        st.dataframe(df_tf, use_container_width=True, hide_index=True)

    # Recent runs
    recent = data.get("recent_runs", [])
    if recent:
        st.markdown("---")
        st.markdown("**🕐 Recent Runs**")
        df_r = pd.DataFrame(recent)
        if "logged_at" in df_r.columns:
            df_r["logged_at"] = df_r["logged_at"].apply(fdt)
        show = [c for c in ["pipeline_id","connector_type","status",
                             "rows_inserted","duration_sec","error_message","logged_at"]
                if c in df_r.columns]
        st.dataframe(df_r[show], use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 2 — CREATE PIPELINE
# ═════════════════════════════════════════════════════════════════════════════
elif page == "➕ Create Pipeline":
    st.markdown('<div class="shd">➕ Create Pipeline</div>', unsafe_allow_html=True)

    # Connector type, Load Option, After First Run — all OUTSIDE form
    # so they update reactively without needing form submission
    col_pre1, col_pre2, col_pre3 = st.columns(3)
    with col_pre1:
        ctype = st.selectbox("Connector Type *",
                             ["csv","excel","google_sheets","api","postgres","s3"],
                             key="cp_ctype")
    with col_pre2:
        opt = st.selectbox("Load Option *",
                           ["1 — Append","2 — Overwrite","3 — Create Only"],
                           key="cp_opt")
    with col_pre3:
        afr = None
        if opt.startswith("3"):
            afr_raw = st.selectbox("After First Run *",
                                   ["1 — Switch to Append","2 — Switch to Overwrite"],
                                   key="cp_afr",
                                   help="Switch to this option after the first successful run")
            afr = afr_raw.split(" ")[0]
        else:
            st.empty()

    with st.form("create_pipeline_form"):
        st.markdown("#### Basic Config")
        col1, col2 = st.columns(2)
        with col1:
            pname = st.text_input("Pipeline Name *", placeholder="sales_data",
                                  help="Only letters, numbers, and underscores")
            tname = st.text_input("Table Name *",    placeholder="tbl_sales")
        with col2:
            sched = st.text_input("Cron Schedule *", value="*/5 * * * *")
            sync  = st.selectbox("Sync Mode", ["full","incremental"])

        inc_col = st.text_input("Incremental Column",
                                placeholder="updated_at",
                                help="Required when Sync Mode = incremental")

        st.markdown("---")
        st.markdown(f"#### Source Config  —  `{ctype}`")

        fp = file_p = su = au = None
        pg_host = pg_db = pg_user = pg_pw = pg_port = pg_q = None
        s3b = s3k = s3ft = None

        if ctype in ("csv", "excel"):
            fa, fb = st.columns(2)
            with fa:
                fp     = st.text_input("Folder Path",
                                       placeholder="/opt/airflow/dataset_win/sales",
                                       help="All CSV/Excel files in this folder will be processed")
            with fb:
                file_p = st.text_input("OR Single File Path",
                                       placeholder="/opt/airflow/dataset_win/sales/data.csv")
            st.markdown('<div class="bi">💡 Provide either Folder Path or Single File Path. '
                        'Folder mode processes all matching files.</div>',
                        unsafe_allow_html=True)

        elif ctype == "google_sheets":
            su = st.text_input("Google Sheet URL *",
                               placeholder="https://docs.google.com/spreadsheets/d/...")
            st.markdown('<div class="bi">💡 Sheet must be public: '
                        'Share → Anyone with link → Viewer</div>', unsafe_allow_html=True)

        elif ctype == "api":
            au = st.text_input("API URL *",
                               placeholder="https://api.example.com/data")

        elif ctype == "postgres":
            pa, pb, pc = st.columns(3)
            with pa:
                pg_host = st.text_input("Host *",     placeholder="db.example.com")
                pg_db   = st.text_input("Database *", placeholder="mydb")
            with pb:
                pg_user = st.text_input("User *",     placeholder="reader")
                pg_pw   = st.text_input("Password *", type="password")
            with pc:
                pg_port = st.text_input("Port", value="5432")
            pg_q = st.text_area("SQL Query *",
                                placeholder="SELECT * FROM employees WHERE active = true",
                                height=100)

        elif ctype == "s3":
            sa, sb, sc = st.columns(3)
            with sa: s3b  = st.text_input("Bucket Name *",  placeholder="my-data-bucket")
            with sb: s3k  = st.text_input("Key / Prefix *", placeholder="folder/data.csv")
            with sc: s3ft = st.selectbox("File Type", ["csv","xlsx","parquet","json"])

        submitted = st.form_submit_button("🚀 Create Pipeline", use_container_width=True)

    if submitted:
        errs = []
        if not pname: errs.append("Pipeline Name is required")
        if not tname: errs.append("Table Name is required")
        if sync == "incremental" and not inc_col:
            errs.append("Incremental Column is required when Sync Mode = incremental")
        if opt.startswith("3") and not afr:
            errs.append("After First Run is required when Load Option = Create Only")
        if ctype in ("csv","excel") and not fp and not file_p:
            errs.append("Folder Path or File Path is required for CSV/Excel")
        if ctype == "google_sheets" and not su:
            errs.append("Google Sheet URL is required")
        if ctype == "api" and not au:
            errs.append("API URL is required")
        if ctype == "postgres" and not pg_q:
            errs.append("SQL Query is required for Postgres connector")
        if ctype == "s3" and (not s3b or not s3k):
            errs.append("Bucket and Key are required for S3")

        if errs:
            for e in errs:
                st.warning(e)
        else:
            payload = {
                "pipeline_name":    pname,
                "connector_type":   ctype,
                "table_name":       tname,
                "option":           opt.split(" ")[0],
                "schedule":         sched,
                "sync_mode":        sync,
                "incremental_column": inc_col or None,
                "after_first_run":  afr,
                "folder_path":      fp     or None,
                "file_path":        file_p or None,
                "sheet_url":        su     or None,
                "api_url":          au     or None,
                "src_pg_host":      pg_host,
                "src_pg_db":        pg_db,
                "src_pg_user":      pg_user,
                "src_pg_password":  pg_pw,
                "src_pg_port":      pg_port,
                "pg_query":         pg_q,
                "s3_bucket":        s3b,
                "s3_key":           s3k,
                "s3_file_type":     s3ft,
            }
            with st.spinner("Creating pipeline..."):
                code, res = api("post", "/create_pipeline", json=payload)
            if code == 200 and res.get("status") == "SUCCESS":
                st.markdown(
                    f'<div class="bo">✅ Pipeline created: <b>{res.get("dag_id")}</b>'
                    f'<br>Airflow will pick it up in ~30 seconds.</div>',
                    unsafe_allow_html=True)
                st.json(res)
            else:
                err = res.get("detail", res.get("error", str(res)))
                st.markdown(f'<div class="be">❌ Failed: {err}</div>',
                            unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 3 — MANAGE PIPELINES
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📋 Manage Pipelines":
    st.markdown('<div class="shd">📋 Manage Pipelines</div>', unsafe_allow_html=True)

    top_a, top_b = st.columns([1, 4])
    with top_a:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()
    with top_b:
        search = st.text_input("Search pipeline", placeholder="Type pipeline name...",
                               label_visibility="collapsed")

    code, data = api("get", "/pipelines")
    pipes = data.get("pipelines", []) if code == 200 else []

    if not pipes:
        st.markdown('<div class="bw">No pipelines found. '
                    'Create one using the "Create Pipeline" page.</div>',
                    unsafe_allow_html=True)
    else:
        rows = []
        status_bar = st.progress(0, text="Fetching pipeline statuses...")
        for i, p in enumerate(pipes):
            name   = p["dag_id"].replace("pipeline_", "")
            sc, sd = api("get", f"/pipeline/{name}/status")
            rows.append({
                "dag_id":   p["dag_id"],
                "name":     name,
                "status":   sd.get("status", "UNKNOWN") if sc == 200 else "UNKNOWN",
                "next_run": fdt(sd.get("next_run")) if sc == 200 else "—",
                "size_kb":  p.get("size_kb", "—"),
            })
            status_bar.progress((i+1)/len(pipes),
                                text=f"Fetching {i+1} of {len(pipes)}...")
        status_bar.empty()

        m1, m2, m3 = st.columns(3)
        m1.metric("Total Pipelines", len(rows))
        m2.metric("Active",  sum(1 for r in rows if r["status"] == "ACTIVE"))
        m3.metric("Paused",  sum(1 for r in rows if r["status"] == "PAUSED"))
        st.markdown("---")

        filtered = [r for r in rows
                    if not search or search.lower() in r["dag_id"].lower()]

        if not filtered:
            st.info("No pipelines match your search.")

        for row in filtered:
            st.markdown(
                f'<div class="prow">'
                f'<span class="pname">{row["dag_id"]}</span>&nbsp;&nbsp;'
                f'{bdg(row["status"])}'
                f'<div class="pmeta">Next run: {row["next_run"]} &nbsp;·&nbsp; '
                f'Size: {row["size_kb"]} KB</div></div>',
                unsafe_allow_html=True)

            ba, bb, bc, bd = st.columns([3, 1, 1, 1])
            with bb:
                if row["status"] == "ACTIVE":
                    if st.button("⏸ Pause", key=f"pa_{row['name']}",
                                 use_container_width=True):
                        c2, d2 = api("patch", f"/pipeline/{row['name']}/pause")
                        if c2 == 200:
                            st.success("Paused ✓")
                            st.rerun()
                        else:
                            st.error(str(d2))
                else:
                    if st.button("▶ Resume", key=f"re_{row['name']}",
                                 use_container_width=True):
                        c2, d2 = api("patch", f"/pipeline/{row['name']}/unpause")
                        if c2 == 200:
                            st.success("Resumed ✓")
                            st.rerun()
                        else:
                            st.error(str(d2))
            with bc:
                if st.button("🗑 Delete", key=f"de_{row['name']}",
                             use_container_width=True):
                    c2, d2 = api("delete", f"/delete_pipeline/{row['name']}")
                    if c2 == 200:
                        st.success("Deleted ✓")
                        st.rerun()
                    else:
                        st.error(str(d2))
            with bd:
                pass

            with st.expander("✏️ Edit  /  📜 Run History"):
                etab, htab = st.tabs(["✏️ Edit", "📜 Run History"])

                with etab:
                    with st.form(f"edit_{row['name']}"):
                        ea, eb = st.columns(2)
                        with ea:
                            new_sched = st.text_input("New Schedule",
                                                      placeholder="0 */6 * * *",
                                                      key=f"ns_{row['name']}")
                            new_opt   = st.selectbox("New Load Option",
                                                     ["(no change)","1 — Append",
                                                      "2 — Overwrite"],
                                                     key=f"no_{row['name']}")
                        with eb:
                            new_fold  = st.text_input("New Folder Path",
                                                      key=f"nf_{row['name']}")
                            new_sync  = st.selectbox("New Sync Mode",
                                                     ["(no change)","full","incremental"],
                                                     key=f"nsync_{row['name']}")
                        new_inc = st.text_input("New Incremental Column",
                                               key=f"ni_{row['name']}")
                        if st.form_submit_button("💾 Save Changes",
                                                 use_container_width=True):
                            pl = {}
                            if new_sched:                 pl["schedule"]           = new_sched
                            if new_opt != "(no change)":  pl["option"]             = new_opt.split(" ")[0]
                            if new_fold:                  pl["folder_path"]        = new_fold
                            if new_sync != "(no change)": pl["sync_mode"]          = new_sync
                            if new_inc:                   pl["incremental_column"] = new_inc
                            if pl:
                                c2, d2 = api("patch", f"/edit_pipeline/{row['name']}",
                                             json=pl)
                                if c2 == 200:
                                    st.success(f"Updated: {d2.get('changed', pl)}")
                                else:
                                    st.error(str(d2))
                            else:
                                st.warning("No changes provided.")

                with htab:
                    hc2, hd2 = api("get", f"/pipeline/{row['name']}/runs",
                                   params={"limit": 15})
                    if hc2 == 200:
                        stats = hd2.get("stats", {})
                        s1, s2, s3, s4 = st.columns(4)
                        s1.metric("Total Runs",  stats.get("total_runs", 0))
                        s2.metric("Success",     stats.get("success_count", 0))
                        s3.metric("Failed",      stats.get("failed_count", 0))
                        s4.metric("Last Run",    fdt(stats.get("last_run_at")))
                        runs = hd2.get("runs", [])
                        if runs:
                            df_r = pd.DataFrame(runs)
                            show_c = [c for c in ["dag_run_id","status","operation",
                                                   "created_at"] if c in df_r.columns]
                            if "created_at" in df_r.columns:
                                df_r["created_at"] = df_r["created_at"].apply(fdt)
                            st.dataframe(df_r[show_c], use_container_width=True,
                                         hide_index=True)
                        else:
                            st.info("No runs found for this pipeline.")
                    else:
                        st.error(str(hd2))

            st.markdown("---")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 4 — DIRECT INGEST
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📥 Direct Ingest":
    st.markdown('<div class="shd">📥 Direct Ingest</div>', unsafe_allow_html=True)
    st.markdown('<div class="bi">💡 Ingest data directly without creating a scheduled pipeline. '
                'Useful for one-time loads.</div>', unsafe_allow_html=True)

    # Connector outside form — changing it re-renders source fields
    connector = st.selectbox("Connector Type",
                             ["csv","excel","google_sheets","api","postgres","s3"],
                             key="di_connector")

    with st.form("direct_ingest_form"):
        col1, col2 = st.columns(2)
        with col1:
            di_table = st.text_input("Table Name *", placeholder="tbl_sales")
            di_opt   = st.selectbox("Load Option",
                                    ["1 — Append","2 — Overwrite","3 — Create Only"])
        with col2:
            di_sync  = st.selectbox("Sync Mode", ["full","incremental"])
            di_inc   = st.text_input("Incremental Column", placeholder="updated_at")

        st.markdown("---")
        st.markdown(f"**{connector.upper()} — Source Details**")

        di_payload  = {}
        di_endpoint = None

        if connector == "csv":
            di_payload["file_path"] = st.text_input(
                "File Path *", placeholder="/opt/airflow/dataset_win/data.csv")
            di_endpoint = "/ingest_csv"

        elif connector == "excel":
            di_payload["file_path"] = st.text_input(
                "File Path *", placeholder="/opt/airflow/dataset_win/data.xlsx")
            di_endpoint = "/ingest_excel"

        elif connector == "google_sheets":
            di_payload["sheet_url"] = st.text_input(
                "Google Sheet URL *",
                placeholder="https://docs.google.com/spreadsheets/d/...")
            di_endpoint = "/ingest_google_sheet"

        elif connector == "api":
            di_payload["url"] = st.text_input(
                "API URL *", placeholder="https://api.example.com/data")
            di_endpoint = "/ingest_api"

        elif connector == "postgres":
            pa, pb, pc = st.columns(3)
            with pa:
                di_payload["host"]     = st.text_input("Host *")
                di_payload["database"] = st.text_input("Database *")
            with pb:
                di_payload["user"]     = st.text_input("User *")
                di_payload["password"] = st.text_input("Password *", type="password")
            with pc:
                di_payload["port"] = st.text_input("Port", value="5432")
            di_payload["query"] = st.text_area("SQL Query *",
                                               placeholder="SELECT * FROM table")
            di_endpoint = "/ingest_postgres"

        elif connector == "s3":
            sa, sb, sc2 = st.columns(3)
            with sa: di_payload["bucket"]    = st.text_input("Bucket *")
            with sb: di_payload["key"]       = st.text_input("Key / Prefix *")
            with sc2:di_payload["file_type"] = st.selectbox("File Type",
                                                            ["csv","xlsx","parquet","json"])
            di_endpoint = "/ingest_s3"

        go = st.form_submit_button("⚡ Run Ingest Now", use_container_width=True)

    if go:
        if not di_table:
            st.warning("Table Name is required.")
        elif not di_endpoint:
            st.error("Connector is not properly configured.")
        else:
            di_payload["option"]             = di_opt.split(" ")[0]
            di_payload["table_name"]         = di_table
            di_payload["sync_mode"]          = di_sync
            di_payload["incremental_column"] = di_inc or None

            with st.spinner(f"Ingesting via {connector}..."):
                code, res = api("post", di_endpoint, json=di_payload)
            if code == 200 and res.get("status") == "SUCCESS":
                st.markdown(
                    f'<div class="bo">✅ Success! <b>{res.get("rows","—")}</b> rows ingested.'
                    f'<br>Run ID: {res.get("run_id","—")}</div>',
                    unsafe_allow_html=True)
            else:
                err = res.get("error", res.get("detail", str(res)))
                st.markdown(f'<div class="be">❌ Failed: {err}</div>',
                            unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 5 — DATA PREVIEW
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🗄️ Data Preview":
    st.markdown('<div class="shd">🗄️ Data Preview</div>', unsafe_allow_html=True)

    pv_a, pv_b = st.columns([3, 1])
    with pv_a:
        pv_table = st.text_input("Table Name", placeholder="tbl_sales")
    with pv_b:
        pv_limit = st.number_input("Rows / page", min_value=10, max_value=1000, value=50)

    if not pv_table:
        st.markdown('<div class="bi">👆 Enter a table name above to preview data.</div>',
                    unsafe_allow_html=True)
    else:
        with st.expander("🔍 Filter & Sort", expanded=False):
            fa, fb, fc, fd = st.columns(4)
            with fa: pv_fc  = st.text_input("Filter Column",  placeholder="status")
            with fb: pv_fv  = st.text_input("Filter Value",   placeholder="active")
            with fc: pv_sb  = st.text_input("Sort By Column", placeholder="created_at")
            with fd: pv_ord = st.selectbox("Order", ["asc", "desc"])

        params = {
            "limit":  pv_limit,
            "offset": st.session_state.tbl_offset,
            "order":  pv_ord,
        }
        if pv_fc: params["filter_col"] = pv_fc
        if pv_fv: params["filter_val"] = pv_fv
        if pv_sb: params["sort_by"]    = pv_sb

        code, data = api("get", f"/table/{pv_table}", params=params)

        if code == 404:
            st.markdown(f'<div class="bw">Table "{pv_table}" not found. '
                        f'Check the table name.</div>', unsafe_allow_html=True)
        elif code != 200:
            st.markdown(f'<div class="be">Error: {data}</div>', unsafe_allow_html=True)
        else:
            pg  = data.get("pagination", {})
            tot = pg.get("total", 0)

            pm1, pm2, pm3, pm4 = st.columns(4)
            pm1.metric("Total Rows",   f"{tot:,}")
            pm2.metric("Columns",      len(data.get("columns", [])))
            pm3.metric("Current Page", pg.get("page", 1))
            pm4.metric("Total Pages",  pg.get("pages", 1))

            rows = data.get("data", [])
            if rows:
                df_pv = pd.DataFrame(rows)
                st.dataframe(df_pv, use_container_width=True, hide_index=True)
                st.download_button(
                    label="⬇️ Download this page as CSV",
                    data=df_pv.to_csv(index=False),
                    file_name=f"{pv_table}_page{pg.get('page',1)}.csv",
                    mime="text/csv",
                )
            else:
                st.info("No rows match the current filter.")

            # Pagination controls
            pp1, pp2, pp3 = st.columns([1, 2, 1])
            with pp1:
                if st.button("◀ Previous", use_container_width=True):
                    if st.session_state.tbl_offset >= pv_limit:
                        st.session_state.tbl_offset -= pv_limit
                        st.rerun()
            with pp2:
                st.markdown(
                    f"<p style='text-align:center;color:#94a3b8;padding-top:8px;'>"
                    f"Page {pg.get('page',1)} of {pg.get('pages',1)} &nbsp;·&nbsp; "
                    f"{tot:,} total rows</p>",
                    unsafe_allow_html=True)
            with pp3:
                if st.button("Next ▶", use_container_width=True):
                    if pg.get("has_more"):
                        st.session_state.tbl_offset += pv_limit
                        st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 6 — METRICS
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📈 Metrics":
    st.markdown('<div class="shd">📈 Metrics</div>', unsafe_allow_html=True)

    mt1, mt2 = st.tabs(["All Pipelines Summary", "Single Pipeline Deep Dive"])

    with mt1:
        code, data = api("get", "/metrics/summary/all")
        if code == 200:
            summary = data.get("summary", [])
            if summary:
                df_s = pd.DataFrame(summary)
                if "success_count" in df_s.columns and "total_runs" in df_s.columns:
                    df_s["success_rate_%"] = (
                        df_s["success_count"] /
                        df_s["total_runs"].replace(0, 1) * 100
                    ).round(1)
                    fig = px.bar(df_s, x="pipeline_id", y="success_rate_%",
                                 color="connector_type",
                                 title="Success Rate % by Pipeline",
                                 color_discrete_sequence=CLR)
                    fig.update_layout(**PLOT)
                    fig.update_yaxes(range=[0, 100], gridcolor="#e2e8f0")
                    fig.update_xaxes(showgrid=False)
                    st.plotly_chart(fig, use_container_width=True)

                if "last_run_at" in df_s.columns:
                    df_s["last_run_at"] = df_s["last_run_at"].apply(fdt)
                st.dataframe(df_s, use_container_width=True, hide_index=True)
            else:
                st.info("No metrics available. Run some pipelines first.")
        else:
            st.error(f"Failed to load metrics: {data}")

    with mt2:
        m_pid  = st.text_input("Pipeline ID", placeholder="pipeline_sales_data",
                               help="Full pipeline ID including 'pipeline_' prefix")
        m_runs = st.slider("Last N runs", 5, 50, 20)

        if m_pid:
            code, data = api("get", f"/metrics/{m_pid}", params={"limit": m_runs})
            if code == 200:
                runs = data.get("runs", [])
                if runs:
                    df_m = pd.DataFrame(runs)
                    df_m["run_no"] = range(1, len(df_m) + 1)

                    if "duration_sec" in df_m.columns:
                        fig = px.line(df_m, x="run_no", y="duration_sec",
                                      title="Duration per Run (seconds)",
                                      color_discrete_sequence=["#6366f1"],
                                      markers=True)
                        fig.update_layout(**PLOT)
                        fig.update_xaxes(showgrid=False, title="Run #")
                        fig.update_yaxes(gridcolor="#e2e8f0", title="Seconds")
                        st.plotly_chart(fig, use_container_width=True)

                    if "rows_inserted" in df_m.columns:
                        cmap = {"SUCCESS":"#10b981","FAILED":"#ef4444","SKIPPED":"#f59e0b"}
                        color_col = "status" if "status" in df_m.columns else None
                        fig2 = px.bar(df_m, x="run_no", y="rows_inserted",
                                      color=color_col,
                                      title="Rows Inserted per Run",
                                      color_discrete_map=cmap)
                        fig2.update_layout(**PLOT)
                        fig2.update_xaxes(showgrid=False, title="Run #")
                        fig2.update_yaxes(gridcolor="#e2e8f0", title="Rows")
                        st.plotly_chart(fig2, use_container_width=True)

                    show_c = [c for c in ["status","rows_inserted","duration_sec",
                                          "match_pct","error_message","logged_at"]
                              if c in df_m.columns]
                    if "logged_at" in df_m.columns:
                        df_m["logged_at"] = df_m["logged_at"].apply(fdt)
                    st.dataframe(df_m[show_c], use_container_width=True, hide_index=True)
                else:
                    st.info("No runs found for this pipeline.")
            else:
                st.error(f"Could not load metrics: {data}")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 7 — LOGS
# ═════════════════════════════════════════════════════════════════════════════
elif page == "📜 Logs":
    st.markdown('<div class="shd">📜 Logs</div>', unsafe_allow_html=True)

    la, lb = st.columns(2)
    with la:
        log_pipe = st.text_input("Pipeline Name", placeholder="spark1",
                                 help="Without the 'pipeline_' prefix")
    with lb:
        log_rid  = st.text_input("DAG Run ID (optional — blank = latest run)",
                                 placeholder="run__pipeline_spark1__20260413...")

    if log_pipe:
        ep = f"/pipeline/{log_pipe}/logs"
        if log_rid.strip():
            ep += f"/{log_rid.strip()}"

        code, data = api("get", ep)

        if code == 200:
            la2, lb2, lc2 = st.columns(3)
            la2.markdown(f"**Source:** `{data.get('source','—')}`")
            lb2.markdown(bdg(data.get("status","UNKNOWN")), unsafe_allow_html=True)
            lc2.markdown(f"**Logged at:** {fdt(data.get('logged_at'))}")
            if data.get("log_file"):
                st.caption(f"File: `{data['log_file']}`")
            log_content = data.get("log", "No log content found.")
            st.text_area("Log Output", value=log_content, height=450)
            st.download_button("⬇️ Download Log", log_content,
                               f"{log_pipe}_{log_rid or 'latest'}.log",
                               "text/plain")
        elif code == 404:
            st.markdown('<div class="bw">Log not found. '
                        'Has this pipeline run yet?</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="be">Error: {data}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="bi">👆 Enter a pipeline name above to view logs.</div>',
                    unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("**All Pipeline Runs (from DB)**")
    code, data = api("get", "/runs")
    if code == 200 and data:
        df_lr = pd.DataFrame(data)
        for col in ["start_time", "end_time"]:
            if col in df_lr.columns:
                df_lr[col] = df_lr[col].apply(fdt)
        st.dataframe(df_lr, use_container_width=True, hide_index=True)
    else:
        st.info("No runs found in the database.")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 8 — MULTI-SOURCE PIPELINE
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🔗 Multi-Source Pipeline":
    st.markdown('<div class="shd">🔗 Multi-Source Pipeline</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="bi">💡 Merge data from multiple sources into a single table. '
        'The first source uses your selected option. '
        'All subsequent sources automatically use <b>append</b>.</div>',
        unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### Pipeline Config")
    msa, msb, msc = st.columns(3)
    with msa:
        ms_name  = st.text_input("Pipeline Name *", placeholder="sales_combined")
        ms_table = st.text_input("Target Table *",  placeholder="tbl_all_sales")
    with msb:
        ms_opt   = st.selectbox("First Source Option",
                                ["1 — Append","2 — Overwrite"])
        ms_sched = st.text_input("Schedule", value="*/5 * * * *")
    with msc:
        ms_sync  = st.selectbox("Sync Mode", ["full","incremental"])
        ms_inc   = st.text_input("Incremental Column") if ms_sync == "incremental" else None

    st.markdown("---")
    st.markdown("#### Sources")

    if "ms_sources" not in st.session_state:
        st.session_state.ms_sources = [{}]

    if st.button("➕ Add Source", key="ms_add"):
        st.session_state.ms_sources.append({})
        st.rerun()

    to_remove = None
    sources_payload = []

    for i in range(len(st.session_state.ms_sources)):
        with st.expander(f"Source {i+1}", expanded=True):
            ms_ct = st.selectbox(
                "Connector Type", ["csv","excel","google_sheets","api","postgres","s3"],
                key=f"ms_ct_{i}")
            src = {"connector_type": ms_ct}

            if ms_ct in ("csv","excel"):
                src["folder_path"] = st.text_input(
                    "Folder / File Path", key=f"ms_fp_{i}",
                    placeholder="/opt/airflow/dataset_win/...")

            elif ms_ct == "google_sheets":
                src["sheet_url"] = st.text_input(
                    "Sheet URL", key=f"ms_su_{i}",
                    placeholder="https://docs.google.com/...")

            elif ms_ct == "api":
                src["api_url"] = st.text_input("API URL", key=f"ms_au_{i}")

            elif ms_ct == "s3":
                sa, sb, sc2 = st.columns(3)
                with sa: src["s3_bucket"]    = st.text_input("Bucket", key=f"ms_sb_{i}")
                with sb: src["s3_key"]       = st.text_input("Key",    key=f"ms_sk_{i}")
                with sc2:src["s3_file_type"] = st.selectbox("Type",
                                               ["csv","xlsx","parquet","json"],
                                               key=f"ms_sft_{i}")

            elif ms_ct == "postgres":
                pa, pb = st.columns(2)
                with pa:
                    src["src_pg_host"] = st.text_input("Host",     key=f"ms_ph_{i}")
                    src["src_pg_db"]   = st.text_input("Database", key=f"ms_pd_{i}")
                with pb:
                    src["src_pg_user"]     = st.text_input("User",    key=f"ms_pu_{i}")
                    src["src_pg_password"] = st.text_input("Password",key=f"ms_pp_{i}",
                                                          type="password")
                src["pg_query"] = st.text_area("SQL Query", key=f"ms_pq_{i}")

            if i > 0:
                if st.button(f"🗑 Remove Source {i+1}", key=f"ms_rm_{i}"):
                    to_remove = i

            sources_payload.append(src)

    if to_remove is not None:
        st.session_state.ms_sources.pop(to_remove)
        st.rerun()

    st.markdown("---")
    if st.button("🚀 Create Multi-Source Pipeline", type="primary",
                 use_container_width=True):
        errs = []
        if not ms_name:  errs.append("Pipeline Name is required")
        if not ms_table: errs.append("Target Table is required")
        if not sources_payload: errs.append("At least one source is required")

        if errs:
            for e in errs:
                st.warning(e)
        else:
            payload = {
                "pipeline_name":      ms_name,
                "table_name":         ms_table,
                "option":             ms_opt.split(" ")[0],
                "schedule":           ms_sched,
                "sync_mode":          ms_sync,
                "incremental_column": ms_inc,
                "sources":            sources_payload,
            }
            with st.spinner("Creating multi-source pipeline..."):
                code, res = api("post", "/create_multi_pipeline", json=payload)
            if code == 200 and res.get("status") == "SUCCESS":
                st.markdown(
                    f'<div class="bo">✅ Created: <b>{res.get("dag_id")}</b><br>'
                    f'{res.get("sources_count", len(sources_payload))} sources → '
                    f'table "<b>{ms_table}</b>"</div>',
                    unsafe_allow_html=True)
                st.json(res)
            else:
                err = res.get("detail", res.get("error", str(res)))
                st.markdown(f'<div class="be">❌ {err}</div>', unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 9 — AI ASSISTANT
# ═════════════════════════════════════════════════════════════════════════════
elif page == "🤖 AI Assistant":
    st.markdown('<div class="shd">🤖 AI Assistant</div>', unsafe_allow_html=True)

    # Config row
    aica, aicb, aicc = st.columns([2, 2, 1])
    with aica:
        new_key = st.text_input(
            "OpenRouter API Key",
            value=st.session_state.or_key,
            type="password",
            placeholder="sk-or-v1-...",
            help="Get a free key at openrouter.ai")
        if new_key != st.session_state.or_key:
            st.session_state.or_key = new_key

    with aicb:
        new_model = st.selectbox("Model", [
            "openai/gpt-oss-120b:free",
            "meta-llama/llama-3-8b-instruct:free",
            "google/gemma-2-9b-it:free",
            "mistralai/mistral-7b-instruct:free",
            "mistralai/mixtral-8x7b-instruct",
            "meta-llama/llama-3-70b-instruct",
            "anthropic/claude-3-haiku",
            "openai/gpt-4o-mini",
        ])
        if new_model != st.session_state.or_model:
            st.session_state.or_model = new_model

    with aicc:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑 Clear", use_container_width=True):
            st.session_state.chat_history = []
            st.rerun()

    if not st.session_state.or_key:
        st.markdown(
            '<div class="bw">⚠️ Enter your OpenRouter API key above. '
            'Get a free key at <a href="https://openrouter.ai" target="_blank">'
            '<b>openrouter.ai</b></a>.</div>',
            unsafe_allow_html=True)

    st.markdown("---")

    # Quick question chips
    st.markdown("**Quick Questions:**")
    CHIPS = [
        "How many runs today?",
        "Which pipeline is failing?",
        "Which is the slowest pipeline?",
        "What was the last error?",
        "How many rows have been ingested?",
        "What is the success rate?",
        "When did schema changes occur?",
        "What is the Airflow DAG status?",
    ]
    chip_clicked = None
    r1_cols = st.columns(4)
    r2_cols = st.columns(4)
    for i, chip in enumerate(CHIPS):
        col = r1_cols[i] if i < 4 else r2_cols[i-4]
        with col:
            if st.button(chip, key=f"qchip_{i}", use_container_width=True):
                chip_clicked = chip

    st.markdown("---")

    # Welcome message
    if not st.session_state.chat_history:
        st.markdown("""
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;
            padding:1.2rem 1.4rem;margin:.5rem 0;box-shadow:0 1px 3px rgba(0,0,0,.05)">
    <b>👋 Hello! I am the Pipeline Assistant.</b><br><br>
    I can query your pipeline's <b>live data</b> from these tables:<br>
    &nbsp;&nbsp;📊 <b>pipeline_runs</b> — status, duration, and row count per run<br>
    &nbsp;&nbsp;📋 <b>pipeline_metrics</b> — performance, schema changes, match %<br>
    &nbsp;&nbsp;✈️ <b>airflow_pipeline_runs</b> — DAG runs, schedules, triggers<br>
    &nbsp;&nbsp;📜 <b>pipeline_logs</b> — INFO/ERROR log messages<br>
    &nbsp;&nbsp;📁 <b>pipeline_dag_logs</b> — full task log content<br><br>
    Use the quick questions above or ask anything! 🚀
</div>
""", unsafe_allow_html=True)

    # Chat history display
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(
                f'<div class="muser"><div class="bubu">{msg["content"]}</div></div>',
                unsafe_allow_html=True)
        else:
            with st.chat_message("assistant"):
                st.markdown(msg["content"])

    # Chat input
    user_input = st.chat_input("Ask about pipeline status, errors, metrics, or logs...")
    final_q    = chip_clicked or user_input

    if final_q:
        st.session_state.chat_history.append({"role":"user","content": final_q})
        st.markdown(
            f'<div class="muser"><div class="bubu">{final_q}</div></div>',
            unsafe_allow_html=True)

        # Fetch live DB context
        with st.spinner("Fetching live data..."):
            parts = []
            try:
                c, d = api("get", "/dashboard/summary")
                if c == 200:
                    m2 = d.get("metrics", {}) or {}
                    h2 = d.get("system_health", "UNKNOWN")
                    ph2 = d.get("pipeline_health", []) or []
                    daily2 = d.get("daily", []) or []

                    # Use fallback totals same as dashboard KPIs
                    t_runs = m2.get("total_runs") or sum(p.get("total_runs",0) for p in ph2)
                    t_succ = m2.get("success")    or sum(p.get("success",0)    for p in ph2)
                    t_fail = m2.get("failed")      or sum(p.get("failed",0)     for p in ph2)
                    t_rows = m2.get("total_rows")  or sum(x.get("rows",0) for x in daily2)
                    t_rate = m2.get("success_rate_pct")
                    if not t_rate and t_runs:
                        t_rate = round(t_succ / t_runs * 100, 1)

                    parts.append(
                        f"=== SYSTEM STATUS ===\n"
                        f"Health       : {h2}\n"
                        f"Total Runs   : {t_runs}\n"
                        f"Success      : {t_succ}\n"
                        f"Failed       : {t_fail}\n"
                        f"Success Rate : {t_rate or 0}%\n"
                        f"Total Rows   : {int(t_rows or 0):,}\n"
                        f"Avg Duration : {m2.get('avg_duration',0)}s"
                    )

                    recent = d.get("recent_runs", [])[:8]
                    if recent:
                        lines = ["=== RECENT RUNS ==="]
                        for r in recent:
                            lines.append(
                                f"pipeline={r.get('pipeline_id')} | "
                                f"status={r.get('status')} | "
                                f"rows={r.get('rows_inserted',0)} | "
                                f"duration={r.get('duration_sec',0)}s | "
                                f"error={str(r.get('error_message',''))[:60]} | "
                                f"time={r.get('logged_at','')}")
                        parts.append("\n".join(lines))

                    tf2 = d.get("top_failing", [])
                    if tf2:
                        lines = ["=== TOP FAILING PIPELINES ==="]
                        for f2 in tf2:
                            lines.append(
                                f"pipeline={f2.get('pipeline_id')} | "
                                f"failures={f2.get('fail_count',0)} | "
                                f"last_error={str(f2.get('last_error',''))[:80]}")
                        parts.append("\n".join(lines))

                    if ph2:
                        lines = ["=== PIPELINE HEALTH ==="]
                        for p2 in ph2:
                            lines.append(
                                f"pipeline={p2.get('pipeline_id')} | "
                                f"connector={p2.get('connector_type')} | "
                                f"total_runs={p2.get('total_runs',0)} | "
                                f"success_rate={p2.get('success_rate',0)}% | "
                                f"last_status={p2.get('last_status')} | "
                                f"avg_duration={p2.get('avg_duration',0)}s")
                        parts.append("\n".join(lines))

                c2, d2 = api("get", "/metrics/summary/all")
                if c2 == 200:
                    summ = d2.get("summary", [])
                    if summ:
                        lines = ["=== METRICS SUMMARY (All Pipelines) ==="]
                        for s in summ:
                            lines.append(
                                f"pipeline={s.get('pipeline_id')} | "
                                f"connector={s.get('connector_type')} | "
                                f"runs={s.get('total_runs',0)} | "
                                f"total_rows={s.get('total_rows',0)} | "
                                f"avg_duration={s.get('avg_duration_sec',0)}s | "
                                f"success={s.get('success_count',0)} | "
                                f"failed={s.get('failed_count',0)}")
                        parts.append("\n".join(lines))

                c3, d3 = api("get", "/all_pipelines")
                if c3 == 200 and isinstance(d3, list) and d3:
                    lines = ["=== AIRFLOW PIPELINE RUNS (Last 10) ==="]
                    for r in d3[:10]:
                        if isinstance(r, dict):
                            lines.append(
                                f"dag={r.get('dag_id')} | "
                                f"status={r.get('status')} | "
                                f"connector={r.get('connector_type')} | "
                                f"schedule={r.get('schedule')} | "
                                f"triggered_by={r.get('triggered_by')} | "
                                f"error={str(r.get('error_message',''))[:60]}")
                    parts.append("\n".join(lines))

                c4, d4 = api("get", "/runs")
                if c4 == 200 and isinstance(d4, list):
                    failed_r = [r for r in d4
                                if str(r.get("status","")).upper() == "FAILED"][:5]
                    if failed_r:
                        lines = ["=== FAILED RUNS (pipeline_runs table) ==="]
                        for r in failed_r:
                            lines.append(
                                f"run_id={r.get('run_id')} | "
                                f"connector={r.get('connector_name')} | "
                                f"error={str(r.get('error',''))[:100]} | "
                                f"time={r.get('start_time')}")
                        parts.append("\n".join(lines))

            except Exception as ex:
                parts.append(f"Context fetch error: {ex}")

            db_context = "\n\n".join(parts) if parts else "No data available from API."

        # Build LLM messages
        SYSTEM_MSG = """
        You are the Pipeline Assistant for SparkBrains Universal Data Connector.

        Your role:
        Help users understand, debug, and monitor their data pipelines using the live database context.

        Tone:
        - Conversational, friendly, and clear (like a helpful teammate)
        - Avoid robotic or overly formal responses
        - Keep it concise but natural

        Context:
        You have access to:
        - pipeline_runs: run_id, connector_name, status, records_count, error, start_time, end_time
        - pipeline_logs: level (INFO/ERROR), message, timestamp, run_id
        - pipeline_metrics: rows_inserted, duration_sec, match_pct, evolved_columns, connector_type, status, error_message
        - airflow_pipeline_runs: dag_id, connector_type, schedule, status, triggered_by, error_message
        - pipeline_dag_logs: pipeline_id, log_content, log_file_path, status, created_at

        Guidelines:
        - Always base answers strictly on the DB context — don’t assume missing data
        - If no data is available, say clearly:
        → "I couldn’t find any data for this — try running the pipeline first."

        Response Style:
        - Start with a short, natural explanation (1–2 lines)
        - Then provide structured insights if needed:
        - ✅ Status summary
        - ⚠️ Issues (if any)
        - 💡 Suggested fix (practical and actionable)
        - Use bullet points, not long paragraphs
        - Avoid sounding like logs or raw SQL output

        Error Handling:
        - Clearly explain the root cause in simple terms
        - Suggest a fix like you would to a teammate (practical, not generic)

        Formatting:
        - Use Markdown (bold, bullets, small tables)
        - Format numbers cleanly (e.g., 10,000 rows, 25 sec)

        Length:
        - Keep responses short and useful (100–250 words preferred)

        Goal:
        Make the user feel like they are chatting with a smart engineer, not reading a system report.
        """

        llm_msgs = [{"role":"system","content": SYSTEM_MSG}]
        for h2 in st.session_state.chat_history[-6:]:
            llm_msgs.append({"role": h2["role"], "content": h2["content"]})
        llm_msgs[-1] = {
            "role": "user",
            "content": (
                f"Question: {final_q}\n\n"
                f"=== LIVE DATABASE CONTEXT ===\n"
                f"{db_context}\n"
                f"=== END CONTEXT ===\n\n"
                f"Answer based on the live data above."
            )
        }

        if not st.session_state.or_key:
            reply = "❌ OpenRouter API key is not set. Please enter it above."
        else:
            with st.spinner("Generating answer..."):
                try:
                    resp = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {st.session_state.or_key}",
                            "Content-Type":  "application/json",
                            "HTTP-Referer":  "http://localhost:8501",
                            "X-Title":       "SparkBrains Pipeline Assistant",
                        },
                        json={
                            "model":       st.session_state.or_model,
                            "messages":    llm_msgs,
                            "max_tokens":  1200,
                            "temperature": 0.3,
                        },
                        timeout=30,
                    )
                    if resp.status_code == 200:
                        reply = resp.json()["choices"][0]["message"]["content"]
                    elif resp.status_code == 401:
                        reply = "❌ Invalid API key. Please check your OpenRouter account."
                    elif resp.status_code == 402:
                        reply = "❌ Credits exhausted. Please top up your OpenRouter account."
                    elif resp.status_code == 429:
                        reply = "⚠️ Rate limit reached. Please wait a moment and try again."
                    elif resp.status_code == 503:
                        reply = ("⚠️ The selected model provider is temporarily unavailable (503). "
                                 "Please switch to a different model in the dropdown above, "
                                 "such as **meta-llama/llama-3-8b-instruct:free**.")
                    else:
                        reply = (f"❌ OpenRouter error {resp.status_code}: "
                                 f"{resp.text[:200]}")
                except requests.exceptions.Timeout:
                    reply = "⚠️ Request timed out. Please try again."
                except Exception as ex:
                    reply = f"❌ Unexpected error: {ex}"

        st.session_state.chat_history.append({"role":"assistant","content": reply})

        with st.chat_message("assistant"):
            st.markdown(reply)
