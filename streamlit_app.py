import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="HTA Price–Uncertainty Tool",
    layout="wide"
)

st.title("HTA Price–Uncertainty Headroom Tool")

st.markdown("""
This tool illustrates:
- Break-even rebate needed for cost-effectiveness
- WTP adjustment/headroom
- Residual uncertainty interpretation
- Diminishing marginal value of additional rebate
""")

# =========================
# INPUTS
# =========================

st.sidebar.header("Inputs")

aup = st.sidebar.number_input(
    "AUP / List Price (NOK)",
    value=1000000,
    step=50000
)

wtp = st.sidebar.number_input(
    "WTP Threshold (NOK/QALY)",
    value=500000,
    step=50000
)

qaly = st.sidebar.number_input(
    "Incremental QALYs",
    value=1.0,
    step=0.1
)

non_drug_cost = st.sidebar.number_input(
    "Non-drug Incremental Cost (NOK)",
    value=100000,
    step=10000
)

wtp_adjustment = st.sidebar.slider(
    "WTP Adjustment / Headroom (%)",
    min_value=0,
    max_value=20,
    value=10
)

scenario_reduction = st.sidebar.slider(
    "Scenario Reduction (%)",
    min_value=0,
    max_value=20,
    value=5
)

# =========================
# CORE CALCULATIONS
# =========================

# Break-even Pmax
pmax_be = (wtp * qaly) - non_drug_cost

# Adjusted WTP
adjusted_wtp = wtp * (1 - wtp_adjustment / 100)

# Pmax after WTP adjustment
pmax_adjusted = (
    adjusted_wtp * qaly
) - non_drug_cost

# Conservative scenario Pmax
pmax_scenario = (
    pmax_adjusted *
    (1 - scenario_reduction / 100)
)

# Rebates
rebate_be = (
    1 - (pmax_be / aup)
)

rebate_adjusted = (
    1 - (pmax_adjusted / aup)
)

rebate_scenario = (
    1 - (pmax_scenario / aup)
)

extra_headroom = (
    rebate_adjusted - rebate_be
)

# =========================
# RESULTS
# =========================

st.header("Results")

col1, col2, col3 = st.columns(3)

col1.metric(
    "Break-even Pmax",
    f"{pmax_be:,.0f} NOK"
)

col2.metric(
    "Adjusted Pmax",
    f"{pmax_adjusted:,.0f} NOK"
)

col3.metric(
    "Scenario Pmax",
    f"{pmax_scenario:,.0f} NOK"
)

col1.metric(
    "Minimum rebate needed",
    f"{rebate_be*100:.1f}%"
)

col2.metric(
    "Rebate with WTP adjustment",
    f"{rebate_adjusted*100:.1f}%"
)

col3.metric(
    "Scenario rebate",
    f"{rebate_scenario*100:.1f}%"
)

st.metric(
    "Extra rebate/headroom",
    f"{extra_headroom*100:.1f} percentage points"
)

# =========================
# ICER CURVE
# =========================

st.header("ICER vs Discount from AUP")

discounts = list(range(0, 95, 5))

icers = []

for d in discounts:

    price = aup * (1 - d/100)

    icer = (
        price + non_drug_cost
    ) / qaly

    icers.append(icer)

df = pd.DataFrame({
    "Discount (%)": discounts,
    "ICER": icers
})

fig = px.line(
    df,
    x="Discount (%)",
    y="ICER",
    markers=True,
    title="ICER Curve"
)

fig.add_hline(
    y=wtp,
    line_dash="dash",
    annotation_text="Base WTP"
)

fig.add_hline(
    y=adjusted_wtp,
    line_dash="dot",
    annotation_text="Adjusted WTP"
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# =========================
# HEADROOM CURVE
# =========================

st.header("Diminishing Value of Additional WTP Adjustment")

adjustments = list(range(0, 21, 1))

headroom_values = []

for adj in adjustments:

    adj_wtp = wtp * (
        1 - adj / 100
    )

    pmax_adj = (
        adj_wtp * qaly
    ) - non_drug_cost

    rebate_adj = (
        1 - (pmax_adj / aup)
    )

    extra = (
        rebate_adj - rebate_be
    ) * 100

    headroom_values.append(extra)

headroom_df = pd.DataFrame({
    "WTP Adjustment (%)": adjustments,
    "Extra Headroom (%)": headroom_values
})

fig2 = px.line(
    headroom_df,
    x="WTP Adjustment (%)",
    y="Extra Headroom (%)",
    markers=True,
    title="Headroom Curve"
)

st.plotly_chart(
    fig2,
    use_container_width=True
)

# =========================
# INTERPRETATION
# =========================

st.header("Interpretation")

if rebate_be < 0.25:

    st.success("""
    Low rebate need:
    Additional WTP adjustment may create meaningful headroom.
    """)

elif rebate_be < 0.50:

    st.warning("""
    Moderate rebate need:
    WTP adjustment may still provide useful payer protection.
    """)

elif rebate_be < 0.80:

    st.warning("""
    High rebate need:
    The rebate already internalizes substantial risk.
    Additional WTP adjustment has diminishing marginal value.
    """)

else:

    st.error("""
    Very high rebate need:
    Additional WTP adjustment provides limited practical gain.
    Risk of double penalization increases.
    """)

# =========================
# FORMULA SECTION
# =========================

st.header("Framework Formula")

st.latex(r'''
R_{total}
=
1 - \frac{Pmax_{final}}{AUP}
''')

st.latex(r'''
Pmax_{final}
=
\min(
Pmax_{BE},
Pmax_{WTP-adjusted},
Pmax_{scenario}
)
''')

st.markdown("""
### Interpretation

- **Pmax_BE** = break-even value-based price
- **Pmax_WTP-adjusted** = price after headroom adjustment
- **Pmax_scenario** = conservative scenario price
- The framework avoids automatic stacking of penalties.
""")
