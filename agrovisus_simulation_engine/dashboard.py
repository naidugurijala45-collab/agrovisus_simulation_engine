"""
AgroVisus Simulation Dashboard

Interactive Streamlit app to visualize simulation results with
Plotly charts, KPIs, and a crop template selector.

Usage:
    streamlit run dashboard.py
"""
import os
import sys
import json
import subprocess
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Page Config ──────────────────────────────────────────────

st.set_page_config(
    page_title="AgroVisus Dashboard",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Paths ────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "outputs")
CSV_PATH = os.path.join(OUTPUT_DIR, "simulation_output.csv")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")
TEMPLATES_PATH = os.path.join(PROJECT_ROOT, "app", "data", "crop_templates.json")
HISTORY_DIR = os.path.join(OUTPUT_DIR, "history")

# ── Custom CSS ───────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    .main .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    
    .kpi-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 1.2rem 1rem;
        text-align: center;
        transition: transform 0.2s;
    }
    .kpi-card:hover { transform: translateY(-2px); }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #00d2ff, #3a7bd5);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0.2rem 0;
    }
    .kpi-label {
        font-size: 0.8rem;
        color: #8899aa;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .kpi-delta { font-size: 0.75rem; color: #4ade80; }
    
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        margin: 1.2rem 0 0.6rem 0;
        padding-bottom: 0.3rem;
        border-bottom: 2px solid rgba(58, 123, 213, 0.3);
    }
</style>
""", unsafe_allow_html=True)


# ── Helper Functions ─────────────────────────────────────────

def load_csv(path):
    return pd.read_csv(path, parse_dates=["date"])


def load_templates():
    with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def kpi_card(label, value, delta=""):
    delta_html = f'<div class="kpi-delta">{delta}</div>' if delta else ""
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        {delta_html}
    </div>
    """

DARK_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
)


def save_run_history(crop_name):
    """Save current CSV to history folder with crop name + timestamp."""
    if not os.path.exists(CSV_PATH):
        return
    os.makedirs(HISTORY_DIR, exist_ok=True)
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(HISTORY_DIR, f"{crop_name}_{ts}.csv")
    import shutil
    shutil.copy2(CSV_PATH, dest)
    return dest


def load_history_runs():
    """Load all history run CSVs and return {label: df} dict."""
    runs = {}
    if not os.path.exists(HISTORY_DIR):
        return runs
    for f in sorted(os.listdir(HISTORY_DIR)):
        if f.endswith(".csv"):
            label = f.replace(".csv", "").replace("_", " ", 1)
            # Make label friendlier: "corn 20260216 210000" → "Corn (2026-02-16)"
            parts = f.replace(".csv", "").split("_")
            if len(parts) >= 3:
                crop = parts[0].capitalize()
                date_part = parts[1]
                label = f"{crop} ({date_part[:4]}-{date_part[4:6]}-{date_part[6:]})"
            try:
                df = pd.read_csv(os.path.join(HISTORY_DIR, f), parse_dates=["date"])
                runs[label] = df
            except Exception:
                pass
    return runs


def create_growth_chart(df):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        subplot_titles=("Biomass Accumulation (kg/ha)", "Leaf Area Index & GDD"),
        row_heights=[0.55, 0.45],
    )
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["total_biomass_kg_ha"], name="Total Biomass",
        fill="tozeroy", line=dict(color="#4ade80", width=2),
        fillcolor="rgba(74, 222, 128, 0.15)",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["leaf_area_index"], name="LAI",
        line=dict(color="#38bdf8", width=2),
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["gdd_accumulated"], name="Accumulated GDD",
        line=dict(color="#fbbf24", width=2, dash="dot"),
    ), row=2, col=1)

    # Stage transition lines
    prev_stage = df["crop_growth_stage"].iloc[0]
    for _, row in df.iterrows():
        if row["crop_growth_stage"] != prev_stage:
            fig.add_vline(x=row["date"], line_dash="dash",
                          line_color="rgba(255,255,255,0.2)", row=1, col=1)
            fig.add_annotation(
                x=row["date"], y=df["total_biomass_kg_ha"].max() * 0.95,
                text=row["crop_growth_stage"], showarrow=False,
                font=dict(size=10, color="#a78bfa"), row=1, col=1,
            )
            prev_stage = row["crop_growth_stage"]

    fig.update_layout(height=500, **DARK_LAYOUT,
                      margin=dict(l=60, r=60, t=40, b=20),
                      legend=dict(orientation="h", y=-0.08))
    fig.update_yaxes(title_text="Biomass (kg/ha)", row=1, col=1)
    fig.update_yaxes(title_text="LAI / GDD", row=2, col=1)
    return fig


def create_weather_chart(df):
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        subplot_titles=("Temperature (°C)", "Precipitation & Solar Radiation"),
        row_heights=[0.5, 0.5],
    )
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["daily_max_temp_c"], name="Max Temp",
        line=dict(color="rgba(239, 68, 68, 0.5)", width=1),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["daily_min_temp_c"], name="Min Temp",
        fill="tonexty", fillcolor="rgba(239, 68, 68, 0.1)",
        line=dict(color="rgba(59, 130, 246, 0.5)", width=1),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["daily_avg_temp_c"], name="Avg Temp",
        line=dict(color="#fbbf24", width=2),
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=df["date"], y=df["daily_precipitation_mm"], name="Precipitation",
        marker_color="rgba(56, 189, 248, 0.6)",
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["daily_solar_radiation_mj_m2"], name="Solar Rad",
        line=dict(color="#fb923c", width=2),
    ), row=2, col=1)

    fig.update_layout(height=450, **DARK_LAYOUT,
                      margin=dict(l=60, r=60, t=40, b=20),
                      legend=dict(orientation="h", y=-0.08))
    fig.update_yaxes(title_text="°C", row=1, col=1)
    fig.update_yaxes(title_text="mm / MJ/m²", row=2, col=1)
    return fig


def create_stress_chart(df):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["water_stress_factor"], name="Water Stress",
        fill="tozeroy", line=dict(color="#38bdf8", width=2),
        fillcolor="rgba(56, 189, 248, 0.1)",
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["nitrogen_stress_factor"], name="Nitrogen Stress",
        fill="tozeroy", line=dict(color="#4ade80", width=2),
        fillcolor="rgba(74, 222, 128, 0.1)",
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["disease_stress_factor"], name="Disease Stress",
        line=dict(color="#f472b6", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["overall_stress_factor"], name="Overall",
        line=dict(color="#fbbf24", width=3),
    ))
    fig.update_layout(height=350, **DARK_LAYOUT,
                      yaxis=dict(title="Stress Factor (1.0 = no stress)", range=[0, 1.1]),
                      margin=dict(l=60, r=60, t=20, b=20),
                      legend=dict(orientation="h", y=-0.12))
    return fig


def create_water_n_chart(df):
    fig = make_subplots(
        rows=1, cols=2, horizontal_spacing=0.1,
        subplot_titles=("Soil Water Balance", "Nitrogen Dynamics"),
    )
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["fraction_awc"], name="Fraction AWC",
        fill="tozeroy", line=dict(color="#38bdf8", width=2),
        fillcolor="rgba(56, 189, 248, 0.15)",
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=df["date"], y=df["daily_irrigation_mm"], name="Irrigation",
        marker_color="rgba(74, 222, 128, 0.6)",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["soil_nitrate_kg_ha"], name="Soil NO3",
        line=dict(color="#4ade80", width=2),
    ), row=1, col=2)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["soil_ammonium_kg_ha"], name="Soil NH4",
        line=dict(color="#fbbf24", width=2),
    ), row=1, col=2)
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["crop_nitrogen_uptake_kg_ha"], name="N Uptake",
        line=dict(color="#f472b6", width=2),
    ), row=1, col=2)
    fig.update_layout(height=350, **DARK_LAYOUT,
                      margin=dict(l=60, r=60, t=40, b=20),
                      legend=dict(orientation="h", y=-0.12))
    return fig


# ── Sidebar ──────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🌾 AgroVisus")
    st.markdown("**Simulation Dashboard**")
    st.markdown("---")

    templates = load_templates()
    template_names = list(templates.keys())
    config = load_config()
    current = config.get("crop_model_config", {}).get("crop_template", "corn")
    idx = template_names.index(current) if current in template_names else 0

    selected_crop = st.selectbox(
        "🌱 Crop Template", template_names, index=idx,
        format_func=lambda x: templates[x]["crop_name"],
    )
    sim_days = st.slider("📅 Simulation Days", 30, 180, 90, step=10)

    st.markdown("---")
    t = templates[selected_crop]
    st.markdown(f"**{t['crop_name']}**")
    st.markdown(f"- Base Temp: {t['t_base_c']}°C")
    st.markdown(f"- RUE: {t['radiation_use_efficiency_g_mj']} g/MJ")
    st.markdown(f"- Harvest Index: {t['harvest_index']}")
    st.markdown(f"- Root Depth: {t.get('max_root_depth_mm', 1200)}mm")
    st.markdown(f"- Stages: {len(t['gdd_thresholds'])}")
    st.markdown("---")

    if st.button("▶️ Run Simulation", type="primary", use_container_width=True):
        config["crop_model_config"]["crop_template"] = selected_crop
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        with st.spinner(f"Running {t['crop_name']} for {sim_days} days..."):
            python_exe = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
            if not os.path.exists(python_exe):
                python_exe = sys.executable
            result = subprocess.run(
                [python_exe, "run.py", "-d", str(sim_days)],
                cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=120,
            )
            if result.returncode == 0:
                save_run_history(selected_crop)
                st.success("Simulation complete! Saved to history.")
                st.rerun()
            else:
                st.error("Simulation failed!")
                with st.expander("Error details"):
                    st.code(result.stderr or result.stdout)

# ── Main Content ─────────────────────────────────────────────

st.markdown("# 🌾 AgroVisus Simulation Results")

if not os.path.exists(CSV_PATH):
    st.warning("No simulation results found. Click **Run Simulation** in the sidebar.")
    st.stop()

df = load_csv(CSV_PATH)
final = df.iloc[-1]

# ── KPI Row ──────────────────────────────────────────────────

total_biomass = final["total_biomass_kg_ha"]
total_precip = df["daily_precipitation_mm"].sum()
total_irrig = df["daily_irrigation_mm"].sum()
avg_stress = df["overall_stress_factor"].mean()

# Get harvest index for yield estimate
cfg = load_config()
hi = float(cfg.get("crop_model_config", {}).get("harvest_index", 0.5))
est_yield = total_biomass * hi

cols = st.columns(5)
cols[0].markdown(kpi_card(
    "Total Biomass", f"{total_biomass:,.0f} kg/ha",
    f"LAI: {final['leaf_area_index']:.1f}"
), unsafe_allow_html=True)
cols[1].markdown(kpi_card(
    "Est. Yield", f"{est_yield:,.0f} kg/ha",
    f"HI: {hi}"
), unsafe_allow_html=True)
cols[2].markdown(kpi_card(
    "Growth Stage", final["crop_growth_stage"],
    f"GDD: {final['gdd_accumulated']:.0f}°C·d"
), unsafe_allow_html=True)
cols[3].markdown(kpi_card(
    "Water Input", f"{total_precip + total_irrig:.0f} mm",
    f"Rain: {total_precip:.0f} | Irrig: {total_irrig:.0f}"
), unsafe_allow_html=True)
cols[4].markdown(kpi_card(
    "Avg Stress", f"{avg_stress:.2f}",
    f"Disease max: {df['disease_severity_percent'].max():.1f}%"
), unsafe_allow_html=True)

st.markdown("")

# ── Tabs ─────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🌱 Crop Growth", "🌤️ Weather", "💧 Water & Nutrients",
    "⚠️ Stress", "🔄 Crop Comparison", "📊 Raw Data"
])

with tab1:
    st.plotly_chart(create_growth_chart(df), use_container_width=True)

    st.markdown('<div class="section-header">Growth Stage Timeline</div>',
                unsafe_allow_html=True)
    stages = []
    prev = df["crop_growth_stage"].iloc[0]
    stages.append({"Stage": prev, "Start": df["date"].iloc[0], "GDD": 0})
    for _, r in df.iterrows():
        if r["crop_growth_stage"] != prev:
            stages[-1]["End"] = r["date"]
            stages[-1]["Days"] = (r["date"] - stages[-1]["Start"]).days
            stages.append({"Stage": r["crop_growth_stage"],
                           "Start": r["date"], "GDD": r["gdd_accumulated"]})
            prev = r["crop_growth_stage"]
    stages[-1]["End"] = df["date"].iloc[-1]
    stages[-1]["Days"] = (df["date"].iloc[-1] - stages[-1]["Start"]).days
    sdf = pd.DataFrame(stages)
    sdf["Start"] = sdf["Start"].dt.strftime("%Y-%m-%d")
    sdf["End"] = sdf["End"].dt.strftime("%Y-%m-%d")
    sdf["GDD"] = sdf["GDD"].round(0).astype(int)
    st.dataframe(sdf, use_container_width=True, hide_index=True)

with tab2:
    st.plotly_chart(create_weather_chart(df), use_container_width=True)
    wcols = st.columns(4)
    wcols[0].metric("Avg Temp", f"{df['daily_avg_temp_c'].mean():.1f}°C")
    wcols[1].metric("Total Precip", f"{total_precip:.1f} mm")
    wcols[2].metric("Avg Solar Rad", f"{df['daily_solar_radiation_mj_m2'].mean():.1f} MJ/m²")
    wcols[3].metric("Avg Humidity", f"{df['daily_avg_humidity_percent'].mean():.1f}%")

with tab3:
    st.plotly_chart(create_water_n_chart(df), use_container_width=True)
    st.markdown('<div class="section-header">Management Events</div>',
                unsafe_allow_html=True)
    events = df[(df["daily_irrigation_mm"] > 0) | (df["daily_fertilization_kg_ha"] > 0)]
    events = events[["date", "daily_irrigation_mm", "daily_fertilization_kg_ha"]].copy()
    events.columns = ["Date", "Irrigation (mm)", "Fertilizer (kg/ha)"]
    events["Date"] = events["Date"].dt.strftime("%Y-%m-%d")
    if not events.empty:
        st.dataframe(events, use_container_width=True, hide_index=True)
    else:
        st.info("No management events.")

with tab4:
    st.plotly_chart(create_stress_chart(df), use_container_width=True)
    scols = st.columns(4)
    scols[0].metric("Water Stress Days", int((df["water_stress_factor"] < 0.8).sum()))
    scols[1].metric("N Stress Days", int((df["nitrogen_stress_factor"] < 0.8).sum()))
    scols[2].metric("Peak Disease", f"{df['disease_severity_percent'].max():.1f}%")
    scols[3].metric("Severe Stress Days", int((df["overall_stress_factor"] < 0.5).sum()))

with tab5:
    st.markdown('<div class="section-header">Crop Comparison</div>',
                unsafe_allow_html=True)
    st.caption("Run simulations with different crops, then compare them here.")

    history = load_history_runs()
    if len(history) < 1:
        st.info("No history yet. Run a simulation to start comparing crops!")
    else:
        selected_runs = st.multiselect(
            "Select runs to compare", list(history.keys()),
            default=list(history.keys())[:min(3, len(history))],
        )

        if selected_runs:
            # Biomass comparison
            fig_comp = go.Figure()
            comp_data = []
            colors = ["#4ade80", "#38bdf8", "#fbbf24", "#f472b6", "#a78bfa"]
            for i, name in enumerate(selected_runs):
                rdf = history[name]
                c = colors[i % len(colors)]
                fig_comp.add_trace(go.Scatter(
                    x=rdf["date"], y=rdf["total_biomass_kg_ha"],
                    name=name, line=dict(color=c, width=2),
                ))
                final_row = rdf.iloc[-1]
                comp_data.append({
                    "Run": name,
                    "Final Biomass (kg/ha)": f"{final_row['total_biomass_kg_ha']:,.0f}",
                    "Final Stage": final_row["crop_growth_stage"],
                    "GDD": f"{final_row['gdd_accumulated']:.0f}",
                    "Avg Stress": f"{rdf['overall_stress_factor'].mean():.2f}",
                })

            fig_comp.update_layout(
                title="Biomass Comparison", height=400, **DARK_LAYOUT,
                yaxis_title="Biomass (kg/ha)",
                margin=dict(l=60, r=60, t=40, b=20),
                legend=dict(orientation="h", y=-0.12),
            )
            st.plotly_chart(fig_comp, use_container_width=True)

            # Stress comparison
            fig_stress = go.Figure()
            for i, name in enumerate(selected_runs):
                rdf = history[name]
                c = colors[i % len(colors)]
                fig_stress.add_trace(go.Scatter(
                    x=rdf["date"], y=rdf["overall_stress_factor"],
                    name=name, line=dict(color=c, width=2),
                ))
            fig_stress.update_layout(
                title="Overall Stress Comparison", height=350, **DARK_LAYOUT,
                yaxis=dict(title="Stress (1.0 = none)", range=[0, 1.1]),
                margin=dict(l=60, r=60, t=40, b=20),
                legend=dict(orientation="h", y=-0.12),
            )
            st.plotly_chart(fig_stress, use_container_width=True)

            # Summary table
            st.dataframe(pd.DataFrame(comp_data), use_container_width=True,
                         hide_index=True)

with tab6:
    all_cols = df.columns.tolist()
    defaults = ["date", "crop_growth_stage", "total_biomass_kg_ha",
                "leaf_area_index", "gdd_accumulated", "overall_stress_factor"]
    selected = st.multiselect("Select columns", all_cols, default=defaults)
    if selected:
        show = df[selected].copy()
        if "date" in show.columns:
            show["date"] = show["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(show, use_container_width=True, hide_index=True)
    st.download_button("📥 Download CSV", df.to_csv(index=False),
                       "simulation_results.csv", "text/csv")

# ── Footer ───────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#6b7280;font-size:0.8rem;">'
    'AgroVisus Simulation Engine v4.0</div>',
    unsafe_allow_html=True,
)
