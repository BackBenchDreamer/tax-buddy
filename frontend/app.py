"""
AI Tax Filing Assistant — Streamlit Dashboard
Connects to FastAPI backend at http://localhost:8000/api/v1
"""

import json
import requests
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

API_BASE = "http://localhost:8000/api/v1"

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Tax Filing Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.main-header {
    background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
    padding: 2.5rem 2rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    color: white;
    text-align: center;
}
.main-header h1 { font-size: 2.4rem; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
.main-header p { font-size: 1.05rem; opacity: 0.85; margin: 0.5rem 0 0 0; font-weight: 300; }

.status-badge {
    display: inline-block; padding: 4px 14px; border-radius: 20px;
    font-size: 0.78rem; font-weight: 600; margin-top: 0.8rem;
}
.status-online { background: #00e676; color: #0a3d1e; }
.status-offline { background: #ff5252; color: #fff; }

.card {
    background: #ffffff; border: 1px solid #e8ecf1; border-radius: 14px;
    padding: 1.5rem; margin-bottom: 1rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.04);
}
.card-title {
    font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;
    color: #7b8794; font-weight: 600; margin-bottom: 0.8rem;
}

.metric-row { display: flex; gap: 1rem; flex-wrap: wrap; }
.metric-card {
    flex: 1; min-width: 140px; background: linear-gradient(135deg, #f8fafc, #eef2f7);
    border-radius: 12px; padding: 1.2rem; text-align: center;
    border: 1px solid #e2e8f0;
}
.metric-card .label { font-size: 0.75rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
.metric-card .value { font-size: 1.5rem; font-weight: 700; color: #1e293b; margin-top: 4px; }

.section-divider { border: none; border-top: 1px solid #e8ecf1; margin: 2rem 0; }

div[data-testid="stFileUploader"] {
    border: 2px dashed #94a3b8 !important; border-radius: 12px !important;
    background: #f8fafc !important;
}

.stButton > button {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    color: white !important; border: none !important;
    border-radius: 10px !important; padding: 0.6rem 2rem !important;
    font-weight: 600 !important; font-size: 0.95rem !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(37,99,235,0.35) !important;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_inr(val):
    """Format a number as ₹ Indian style."""
    try:
        v = float(val)
        if v >= 1_00_000:
            return f"₹{v:,.0f}"
        return f"₹{v:,.2f}"
    except (TypeError, ValueError):
        return str(val)


def check_api():
    try:
        r = requests.get(f"{API_BASE}/system/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def call_process(file_bytes, filename):
    """Call the /process endpoint."""
    files = {"file": (filename, file_bytes)}
    r = requests.post(f"{API_BASE}/process", files=files, timeout=120)
    r.raise_for_status()
    return r.json()


def call_validate(form16, form26as):
    r = requests.post(f"{API_BASE}/validate", json={"form16_data": form16, "form26as_data": form26as}, timeout=30)
    r.raise_for_status()
    return r.json()


def call_compute_tax(data, regime):
    r = requests.post(f"{API_BASE}/compute-tax", json={"data": data, "regime": regime}, timeout=30)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
for key in ("uploaded_file", "process_result", "entities_df", "validation", "tax", "raw_text"):
    if key not in st.session_state:
        st.session_state[key] = None


# ---------------------------------------------------------------------------
# 1. HEADER
# ---------------------------------------------------------------------------
api_online = check_api()
badge_cls = "status-online" if api_online else "status-offline"
badge_txt = "● API Connected" if api_online else "● API Offline"

st.markdown(f"""
<div class="main-header">
    <h1>📊 AI Tax Filing Assistant</h1>
    <p>OCR + NLP powered automation for Indian income tax</p>
    <span class="status-badge {badge_cls}">{badge_txt}</span>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# 2. FILE UPLOAD
# ---------------------------------------------------------------------------
st.markdown('<div class="card"><div class="card-title">📁 Upload Document</div>', unsafe_allow_html=True)

col_upload, col_preview = st.columns([2, 1])

with col_upload:
    uploaded = st.file_uploader(
        "Drop your Form 16 (PDF or image)",
        type=["pdf", "png", "jpg", "jpeg", "tiff", "bmp"],
        help="Supported: PDF, PNG, JPG, TIFF, BMP",
    )
    if uploaded:
        st.session_state.uploaded_file = uploaded
        st.success(f"**{uploaded.name}** — {uploaded.size / 1024:.1f} KB")

with col_preview:
    if st.session_state.uploaded_file:
        uf = st.session_state.uploaded_file
        if uf.name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
            st.image(uf, caption="Preview", use_container_width=True)
        else:
            st.info(f"📄 {uf.name}")

process_clicked = st.button("🚀 Process Document", disabled=(st.session_state.uploaded_file is None or not api_online), use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Processing logic
# ---------------------------------------------------------------------------
if process_clicked and st.session_state.uploaded_file:
    uf = st.session_state.uploaded_file
    with st.spinner("⏳ Running pipeline: OCR → NER → Validation → Tax …"):
        try:
            uf.seek(0)
            result = call_process(uf.read(), uf.name)

            st.session_state.process_result = result
            st.session_state.raw_text = result.get("text", "")

            # Build entities dataframe
            entities = result.get("entities", [])
            if entities:
                df = pd.DataFrame(entities)
                st.session_state.entities_df = df
            else:
                st.session_state.entities_df = pd.DataFrame(columns=["label", "value", "confidence"])

            st.session_state.validation = result.get("validation")
            st.session_state.tax = result.get("tax")

            st.success("✅ Document processed successfully!")
        except requests.exceptions.HTTPError as exc:
            st.error(f"❌ API error: {exc.response.text if exc.response else exc}")
        except Exception as exc:
            st.error(f"❌ Processing failed: {exc}")


# ---------------------------------------------------------------------------
# DEMO MODE — if backend isn't available, let users load sample data
# ---------------------------------------------------------------------------
if not api_online:
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    if st.button("📋 Load Demo Data (no backend needed)", use_container_width=True):
        demo_entities = [
            {"label": "PAN", "value": "BIGPP1846N", "confidence": 1.0},
            {"label": "TAN", "value": "MUMS15654C", "confidence": 1.0},
            {"label": "EmployerName", "value": "SIEMENS TECHNOLOGY AND SERVICES PVT LTD", "confidence": 0.92},
            {"label": "GrossSalary", "value": "873898", "confidence": 0.95},
            {"label": "TaxableIncome", "value": "604280", "confidence": 0.95},
            {"label": "TDS", "value": "34690", "confidence": 0.95},
            {"label": "Section80C", "value": "150000", "confidence": 0.90},
            {"label": "Section80D", "value": "25000", "confidence": 0.90},
            {"label": "AssessmentYear", "value": "2023-24", "confidence": 0.98},
        ]
        st.session_state.entities_df = pd.DataFrame(demo_entities)
        st.session_state.validation = {
            "status": "warning", "score": 75,
            "issues": [{"type": "TDS_MISMATCH", "message": "Form 16 TDS (34690) != Form 26AS TDS (34000). Difference: ₹690.", "severity": "high", "field": "TDS"}],
        }
        st.session_state.tax = {
            "regime": "old", "gross_income": 873898, "deductions": 269618,
            "taxable_income": 604280, "base_tax": 33356, "rebate": 0,
            "surcharge": 0, "cess": 1334.24, "total_tax": 34690.24,
            "tds_paid": 34690, "refund_or_payable": -0.24,
            "breakdown": [
                {"range": "0-2.5L", "taxable_amount": 250000, "rate": 0.0, "tax": 0},
                {"range": "2.5L-5L", "taxable_amount": 250000, "rate": 0.05, "tax": 12500},
                {"range": "5L-10L", "taxable_amount": 104280, "rate": 0.2, "tax": 20856},
            ],
        }
        st.session_state.raw_text = "FORM NO. 16 — SIEMENS TECHNOLOGY AND SERVICES PVT LTD …"
        st.rerun()


# ---------------------------------------------------------------------------
# 3. RESULTS DASHBOARD
# ---------------------------------------------------------------------------
if st.session_state.entities_df is not None and not st.session_state.entities_df.empty:
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown("## 📋 Results Dashboard")

    col_left, col_center, col_right = st.columns([1, 1, 1], gap="large")

    # ── LEFT: Extracted Data ──────────────────────────────────────────────
    with col_left:
        st.markdown('<div class="card"><div class="card-title">🔍 Extracted Entities</div>', unsafe_allow_html=True)
        df = st.session_state.entities_df.copy()

        personal = df[df["label"].isin(["PAN", "TAN", "EmployerName", "EmployeeName", "AssessmentYear"])]
        income = df[df["label"].isin(["GrossSalary", "NetSalary", "TaxableIncome"])]
        deductions = df[df["label"].isin(["Section80C", "Section80D", "TDS"])]

        if not personal.empty:
            st.markdown("**👤 Personal Info**")
            st.dataframe(personal[["label", "value", "confidence"]], use_container_width=True, hide_index=True)

        if not income.empty:
            st.markdown("**💰 Income**")
            st.dataframe(income[["label", "value", "confidence"]], use_container_width=True, hide_index=True)

        if not deductions.empty:
            st.markdown("**📑 Deductions & TDS**")
            st.dataframe(deductions[["label", "value", "confidence"]], use_container_width=True, hide_index=True)

        # Show any remaining entities
        shown_labels = set(personal["label"]) | set(income["label"]) | set(deductions["label"])
        other = df[~df["label"].isin(shown_labels)]
        if not other.empty:
            st.markdown("**📦 Other**")
            st.dataframe(other[["label", "value", "confidence"]], use_container_width=True, hide_index=True)

        st.markdown("</div>", unsafe_allow_html=True)

    # ── CENTER: Validation ────────────────────────────────────────────────
    with col_center:
        st.markdown('<div class="card"><div class="card-title">✅ Validation</div>', unsafe_allow_html=True)
        val = st.session_state.validation

        if val:
            status = val.get("status", "ok")
            score = val.get("score", 100)
            issues = val.get("issues", [])

            # Status indicator
            status_map = {"ok": ("✅ All Checks Passed", "success"), "warning": ("⚠️ Warnings Found", "warning"), "error": ("❌ Errors Detected", "error")}
            label, stype = status_map.get(status, ("ℹ️ Unknown", "info"))
            getattr(st, stype)(label)

            # Score gauge
            gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=score,
                title={"text": "Trust Score", "font": {"size": 16}},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#2563eb"},
                    "steps": [
                        {"range": [0, 50], "color": "#fee2e2"},
                        {"range": [50, 80], "color": "#fef3c7"},
                        {"range": [80, 100], "color": "#d1fae5"},
                    ],
                },
            ))
            gauge.update_layout(height=200, margin=dict(t=40, b=10, l=30, r=30))
            st.plotly_chart(gauge, use_container_width=True)

            # Issues list
            if issues:
                st.markdown("**Issues:**")
                for iss in issues:
                    sev = iss.get("severity", "low")
                    msg = iss.get("message", "")
                    if sev == "high":
                        st.error(f"🔴 {msg}")
                    elif sev == "medium":
                        st.warning(f"🟡 {msg}")
                    else:
                        st.info(f"🔵 {msg}")
            else:
                st.markdown("No issues detected. 🎉")
        else:
            st.info("No validation data available.")

        st.markdown("</div>", unsafe_allow_html=True)

    # ── RIGHT: Tax Summary ────────────────────────────────────────────────
    with col_right:
        st.markdown('<div class="card"><div class="card-title">💰 Tax Summary</div>', unsafe_allow_html=True)
        tax = st.session_state.tax

        if tax:
            regime_label = "Old Regime" if tax.get("regime") == "old" else "New Regime (115BAC)"
            st.markdown(f"**Regime:** `{regime_label}`")

            # Metric cards via HTML
            metrics = [
                ("Gross Income", fmt_inr(tax.get("gross_income", 0))),
                ("Taxable Income", fmt_inr(tax.get("taxable_income", 0))),
                ("Total Tax", fmt_inr(tax.get("total_tax", 0))),
            ]
            refund = tax.get("refund_or_payable", 0)
            if refund >= 0:
                metrics.append(("Refund", fmt_inr(abs(refund))))
            else:
                metrics.append(("Payable", fmt_inr(abs(refund))))

            html = '<div class="metric-row">'
            for lbl, val in metrics:
                html += f'<div class="metric-card"><div class="label">{lbl}</div><div class="value">{val}</div></div>'
            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)

            # Breakdown table
            breakdown = tax.get("breakdown", [])
            if breakdown:
                st.markdown("")
                st.markdown("**Slab Breakdown:**")
                bd_df = pd.DataFrame(breakdown)
                bd_df["rate"] = bd_df["rate"].apply(lambda r: f"{r*100:.0f}%")
                bd_df["tax"] = bd_df["tax"].apply(lambda t: fmt_inr(t))
                bd_df["taxable_amount"] = bd_df["taxable_amount"].apply(lambda t: fmt_inr(t))
                bd_df.columns = ["Slab", "Taxable", "Rate", "Tax"]
                st.dataframe(bd_df, use_container_width=True, hide_index=True)

            # Extra line items
            st.markdown(f"**Base Tax:** {fmt_inr(tax.get('base_tax', 0))}  |  "
                        f"**Rebate:** {fmt_inr(tax.get('rebate', 0))}  |  "
                        f"**Cess (4%):** {fmt_inr(tax.get('cess', 0))}")
        else:
            st.info("No tax data available.")

        st.markdown("</div>", unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────────
    # CHARTS SECTION
    # ──────────────────────────────────────────────────────────────────────
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown("## 📈 Visual Analysis")

    chart_left, chart_right = st.columns(2, gap="large")

    with chart_left:
        st.markdown('<div class="card"><div class="card-title">Income vs Deductions</div>', unsafe_allow_html=True)
        if st.session_state.tax:
            t = st.session_state.tax
            bar_data = pd.DataFrame({
                "Category": ["Gross Income", "Deductions", "Taxable Income", "Total Tax"],
                "Amount": [
                    t.get("gross_income", 0),
                    t.get("deductions", 0),
                    t.get("taxable_income", 0),
                    t.get("total_tax", 0),
                ],
            })
            colors = ["#2563eb", "#f59e0b", "#10b981", "#ef4444"]
            fig_bar = px.bar(
                bar_data, x="Category", y="Amount", color="Category",
                color_discrete_sequence=colors,
                text_auto=".2s",
            )
            fig_bar.update_layout(
                showlegend=False, height=350,
                margin=dict(t=20, b=40, l=40, r=20),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(gridcolor="#e8ecf1"),
            )
            fig_bar.update_traces(textposition="outside")
            st.plotly_chart(fig_bar, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with chart_right:
        st.markdown('<div class="card"><div class="card-title">Tax Slab Breakdown</div>', unsafe_allow_html=True)
        if st.session_state.tax and st.session_state.tax.get("breakdown"):
            bd = st.session_state.tax["breakdown"]
            # Only show slabs with tax > 0
            pie_data = [s for s in bd if s.get("tax", 0) > 0]
            if pie_data:
                pdf = pd.DataFrame(pie_data)
                fig_pie = px.pie(
                    pdf, values="tax", names="range",
                    color_discrete_sequence=px.colors.sequential.Blues_r,
                    hole=0.45,
                )
                fig_pie.update_traces(
                    textposition="inside", textinfo="label+percent",
                    textfont_size=12,
                )
                fig_pie.update_layout(
                    height=350, showlegend=True,
                    margin=dict(t=20, b=20, l=20, r=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", yanchor="bottom", y=-0.15),
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No tax liability — rebate covers entire tax.")
        st.markdown("</div>", unsafe_allow_html=True)

    # ──────────────────────────────────────────────────────────────────────
    # DOWNLOAD SECTION
    # ──────────────────────────────────────────────────────────────────────
    st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
    st.markdown("## 📥 Export")

    dl_left, dl_right, _ = st.columns([1, 1, 2])

    with dl_left:
        # Build ITR-like JSON
        itr_json = {
            "itr_form": "ITR-1 (Sahaj)",
            "entities": st.session_state.entities_df.to_dict(orient="records") if st.session_state.entities_df is not None else [],
            "validation": st.session_state.validation,
            "tax": st.session_state.tax,
        }
        st.download_button(
            label="📄 Download Tax Report (JSON)",
            data=json.dumps(itr_json, indent=2, default=str),
            file_name="tax_report.json",
            mime="application/json",
            use_container_width=True,
        )

    with dl_right:
        if st.session_state.raw_text:
            st.download_button(
                label="📝 Download OCR Text",
                data=st.session_state.raw_text,
                file_name="ocr_output.txt",
                mime="text/plain",
                use_container_width=True,
            )

    # ── Raw OCR text expander ─────────────────────────────────────────────
    if st.session_state.raw_text:
        with st.expander("🔎 View Raw OCR Text"):
            st.text(st.session_state.raw_text[:5000])


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("<hr class='section-divider'>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align:center; color:#94a3b8; font-size:0.8rem; padding:1rem 0;'>"
    "AI Tax Filing Assistant — Built with FastAPI + Streamlit + PaddleOCR + XLM-RoBERTa"
    "</div>",
    unsafe_allow_html=True,
)
