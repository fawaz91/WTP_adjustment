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
import numpy as np
import pandas as pd

def calculate_icer(delta_cost, delta_qaly):
    if delta_qaly <= 0:
        return np.inf
    return delta_cost / delta_qaly


def run_scenario_curves(
    list_intervention_cost,
    comparator_cost,
    scenarios,
    wtp,
    discounts=np.arange(0, 0.96, 0.01)
):
    rows = []

    for d in discounts:
        net_intervention_cost = list_intervention_cost * (1 - d)

        for scenario_name, values in scenarios.items():
            non_drug_cost = values["non_drug_cost"]
            delta_qaly = values["delta_qaly"]

            total_intervention_cost = net_intervention_cost + non_drug_cost
            delta_cost = total_intervention_cost - comparator_cost
            icer = calculate_icer(delta_cost, delta_qaly)

            rows.append({
                "discount": d,
                "discount_percent": d * 100,
                "scenario": scenario_name,
                "net_intervention_cost": net_intervention_cost,
                
                "delta_cost": delta_cost,
                "delta_qaly": delta_qaly,
                "icer": icer,
                "cost_effective": icer <= wtp
            })

    return pd.DataFrame(rows)
    wtp = 500_000

list_intervention_cost = 1_000_000
comparator_cost = 100_000

scenarios = {
    "Base case": {
        "delta_qaly": 1.80,
        "non_drug_cost": 0
    },
    "Conservative no-cure scenario": {
        "delta_qaly": 1.20,
        "non_drug_cost": 0
    },
    "Treatment waning scenario": {
        "delta_qaly": 1.00,
        "non_drug_cost": 0
    },
    "Optimistic cure scenario": {
        "delta_qaly": 2.40,
        "non_drug_cost": 0
    }
}

df = run_scenario_curves(
    list_intervention_cost=list_intervention_cost,
    comparator_cost=comparator_cost,
    scenarios=scenarios,
    wtp=wtp
)

df.head()

def classify_residual_uncertainty(df, wtp, headroom_required=0.10):
    summary = []

    for d, group in df.groupby("discount"):
        min_icer = group["icer"].min()
        max_icer = group["icer"].max()
        base_icer = group.loc[group["scenario"] == "Base case", "icer"].iloc[0]

        any_ce = group["cost_effective"].any()
        all_ce = group["cost_effective"].all()
        decision_flip = any_ce and not all_ce

        headroom = (wtp - base_icer) / wtp

        if base_icer > wtp:
            status = "Not cost-effective"
        elif decision_flip and headroom < headroom_required:
            status = "Residual uncertainty remains"
        elif decision_flip and headroom >= headroom_required:
            status = "Partly covered by price headroom"
        elif all_ce and headroom >= headroom_required:
            status = "Uncertainty likely internalised by price"
        elif all_ce and headroom < headroom_required:
            status = "Cost-effective but limited headroom"
        else:
            status = "Unclear"

        summary.append({
            "discount": d,
            "discount_percent": d * 100,
            "base_icer": base_icer,
            "min_scenario_icer": min_icer,
            "max_scenario_icer": max_icer,
            "decision_flip": decision_flip,
            "headroom_percent": headroom * 100,
            "status": status
        })

    return pd.DataFrame(summary)


summary_df = classify_residual_uncertainty(df, wtp, headroom_required=0.10)

summary_df.head()

def find_discount_anchor(summary_df, status_condition):
    eligible = summary_df[status_condition(summary_df)]
    if eligible.empty:
        return None
    return eligible.sort_values("discount").iloc[0]


ordinary_threshold = find_discount_anchor(
    summary_df,
    lambda x: x["base_icer"] <= wtp
)

all_scenarios_threshold = find_discount_anchor(
    summary_df,
    lambda x: x["max_scenario_icer"] <= wtp
)

headroom_threshold = find_discount_anchor(
    summary_df,
    lambda x: (x["base_icer"] <= wtp * 0.90)
)

robust_threshold = find_discount_anchor(
    summary_df,
    lambda x: (x["max_scenario_icer"] <= wtp) & (x["headroom_percent"] >= 10)
)

anchors = {
    "Ordinary base-case threshold": ordinary_threshold,
    "All scenarios below WTP": all_scenarios_threshold,
    "Base case with 10% headroom": headroom_threshold,
    "Robust threshold": robust_threshold
}

for name, row in anchors.items():
    if row is not None:
        print(name, round(row["discount_percent"], 1), "%")
    else:
        print(name, "not reached")


import matplotlib.pyplot as plt

def plot_scenario_icer_curves(df, wtp):
    plt.figure(figsize=(10, 6))

    for scenario in df["scenario"].unique():
        subset = df[df["scenario"] == scenario]
        plt.plot(
            subset["discount_percent"],
            subset["icer"],
            label=scenario
        )

    plt.axhline(wtp, linestyle="--", label=f"WTP = {wtp:,.0f}")
    plt.xlabel("Discount from list price (%)")
    plt.ylabel("ICER")
    plt.title("Scenario ICER curves across discount levels")
    plt.ylim(0, wtp * 3)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()


plot_scenario_icer_curves(df, wtp)
