import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(
    page_title="HTA Price–Uncertainty Headroom Tool",
    layout="wide"
)

st.title("HTA Price–Uncertainty Headroom Tool")

st.markdown("""
This tool illustrates how price negotiation, discount size, scenario uncertainty and headroom interact.

It distinguishes between:
- ordinary cost-effectiveness at the base-case threshold,
- whether conservative scenarios remain cost-effective,
- whether the offered discount creates enough headroom below WTP,
- whether residual uncertainty remains around the decision threshold.
""")

# =====================================================
# HELPER FUNCTIONS
# =====================================================

def calculate_icer(delta_cost: float, delta_qaly: float) -> float:
    """Calculate ICER. Returns infinity if incremental QALYs are non-positive."""
    if delta_qaly <= 0:
        return np.inf
    return delta_cost / delta_qaly


def run_scenario_curves(
    list_intervention_cost: float,
    comparator_cost: float,
    scenarios: dict,
    wtp: float,
    discounts: np.ndarray
) -> pd.DataFrame:
    """Run ICERs for all scenarios across discount levels."""
    rows = []

    for d in discounts:
        net_intervention_cost = list_intervention_cost * (1 - d)

        for scenario_name, values in scenarios.items():
            non_drug_cost = values["non_drug_cost"]
            delta_qaly = values["delta_qaly"]

            total_incremental_cost = (
                net_intervention_cost
                + non_drug_cost
                - comparator_cost
            )

            icer = calculate_icer(total_incremental_cost, delta_qaly)

            rows.append({
                "discount": d,
                "discount_percent": d * 100,
                "scenario": scenario_name,
                "net_intervention_cost": net_intervention_cost,
                "comparator_cost": comparator_cost,
                "non_drug_cost": non_drug_cost,
                "delta_cost": total_incremental_cost,
                "delta_qaly": delta_qaly,
                "icer": icer,
                "cost_effective": icer <= wtp,
            })

    return pd.DataFrame(rows)


def classify_residual_uncertainty(
    df: pd.DataFrame,
    wtp: float,
    headroom_required: float,
    base_case_name: str = "Base case"
) -> pd.DataFrame:
    """Classify decision status at each discount level."""
    summary = []

    for d, group in df.groupby("discount"):
        min_icer = group["icer"].min()
        max_icer = group["icer"].max()

        if base_case_name in group["scenario"].values:
            base_icer = group.loc[
                group["scenario"] == base_case_name,
                "icer"
            ].iloc[0]
        else:
            base_icer = group["icer"].iloc[0]

        any_ce = group["cost_effective"].any()
        all_ce = group["cost_effective"].all()
        decision_flip = any_ce and not all_ce

        headroom = (wtp - base_icer) / wtp

        if base_icer > wtp:
            status = "Not cost-effective"
        elif decision_flip and headroom < headroom_required:
            status = "Residual uncertainty remains around threshold"
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
            "all_scenarios_cost_effective": all_ce,
            "headroom_percent": headroom * 100,
            "status": status,
        })

    return pd.DataFrame(summary)


def first_discount_where(summary_df: pd.DataFrame, condition):
    eligible = summary_df[condition(summary_df)].copy()
    if eligible.empty:
        return None
    return eligible.sort_values("discount").iloc[0]


def fmt_pct(x):
    if x is None or pd.isna(x):
        return "Not reached"
    return f"{x:.1f}%"


def fmt_nok(x):
    if x is None or pd.isna(x) or np.isinf(x):
        return "Not applicable"
    return f"{x:,.0f} NOK"


# =====================================================
# SIDEBAR INPUTS
# =====================================================

st.sidebar.header("Core inputs")

aup = st.sidebar.number_input(
    "AUP / list price of intervention (NOK)",
    min_value=0.0,
    value=1_000_000.0,
    step=50_000.0,
)

comparator_cost = st.sidebar.number_input(
    "Comparator cost (NOK)",
    min_value=0.0,
    value=100_000.0,
    step=10_000.0,
    help="Cost of comparator treatment. This is subtracted from the intervention arm cost."
)

wtp = st.sidebar.number_input(
    "WTP threshold (NOK/QALY)",
    min_value=1.0,
    value=500_000.0,
    step=50_000.0,
)

base_qaly = st.sidebar.number_input(
    "Base-case incremental QALYs",
    min_value=0.01,
    value=1.80,
    step=0.10,
)

base_non_drug_cost = st.sidebar.number_input(
    "Base-case incremental non-drug cost (NOK)",
    value=0.0,
    step=10_000.0,
    help="Positive values increase intervention cost; negative values represent non-drug cost savings."
)

st.sidebar.header("Negotiation and headroom inputs")

offered_discount = st.sidebar.slider(
    "Offered / negotiated discount from AUP (%)",
    min_value=0,
    max_value=95,
    value=60,
    step=1,
)

headroom_required_pct = st.sidebar.slider(
    "Required headroom below WTP (%)",
    min_value=0,
    max_value=30,
    value=10,
    step=1,
    help="Example: 10% headroom means the base-case ICER should be at or below 90% of WTP."
)

wtp_adjustment_pct = st.sidebar.slider(
    "Optional WTP adjustment / policy headroom (%)",
    min_value=0,
    max_value=30,
    value=0,
    step=1,
    help="Use only when testing an explicit downward adjustment to effective WTP."
)

scenario_price_reduction_pct = st.sidebar.slider(
    "Additional conservative scenario Pmax reduction (%)",
    min_value=0,
    max_value=30,
    value=0,
    step=1,
    help="Optional extra reduction to scenario-based Pmax, separate from WTP headroom."
)

st.sidebar.header("Discount grid")

discount_grid_max = st.sidebar.slider(
    "Maximum discount shown in curves (%)",
    min_value=50,
    max_value=99,
    value=95,
    step=1,
)

discount_grid_step = st.sidebar.selectbox(
    "Discount grid step (%)",
    options=[1, 2, 5, 10],
    index=0,
)

headroom_required = headroom_required_pct / 100
adjusted_wtp = wtp * (1 - wtp_adjustment_pct / 100)
headroom_wtp = wtp * (1 - headroom_required)
offered_discount_decimal = offered_discount / 100


# =====================================================
# SCENARIO INPUT TABLE
# =====================================================

st.header("Scenario inputs")

st.markdown("""
Edit the scenarios below. The base case should be named **Base case** to be used as the anchor for headroom classification.
""")

default_scenarios = pd.DataFrame({
    "include": [True, True, True, True],
    "scenario": [
        "Base case",
        "Conservative no-cure scenario",
        "Treatment waning scenario",
        "Optimistic cure scenario",
    ],
    "delta_qaly": [base_qaly, 1.20, 1.00, 2.40],
    "non_drug_cost": [
        base_non_drug_cost,
        base_non_drug_cost,
        base_non_drug_cost,
        base_non_drug_cost,
    ],
})

scenario_input = st.data_editor(
    default_scenarios,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "include": st.column_config.CheckboxColumn("Include"),
        "scenario": st.column_config.TextColumn("Scenario name"),
        "delta_qaly": st.column_config.NumberColumn(
            "Incremental QALYs",
            min_value=0.001,
            step=0.1,
        ),
        "non_drug_cost": st.column_config.NumberColumn(
            "Incremental non-drug cost (NOK)",
            step=10_000.0,
        ),
    },
)

scenario_input = scenario_input[scenario_input["include"] == True].copy()
scenario_input = scenario_input.dropna(subset=["scenario", "delta_qaly"])

if scenario_input.empty:
    st.error("Please include at least one scenario.")
    st.stop()

scenarios = {
    row["scenario"]: {
        "delta_qaly": float(row["delta_qaly"]),
        "non_drug_cost": float(row["non_drug_cost"]),
    }
    for _, row in scenario_input.iterrows()
}


# =====================================================
# CORE CALCULATIONS
# =====================================================

discounts = np.arange(
    0,
    (discount_grid_max / 100) + 0.0001,
    discount_grid_step / 100,
)

df = run_scenario_curves(
    list_intervention_cost=aup,
    comparator_cost=comparator_cost,
    scenarios=scenarios,
    wtp=wtp,
    discounts=discounts,
)

summary_df = classify_residual_uncertainty(
    df=df,
    wtp=wtp,
    headroom_required=headroom_required,
    base_case_name="Base case",
)

# Use the edited base case if available
base_values = scenarios.get("Base case", next(iter(scenarios.values())))
base_delta_qaly = base_values["delta_qaly"]
base_non_drug_cost_used = base_values["non_drug_cost"]

pmax_be = (
    wtp * base_delta_qaly
    - base_non_drug_cost_used
    + comparator_cost
)

pmax_headroom = (
    headroom_wtp * base_delta_qaly
    - base_non_drug_cost_used
    + comparator_cost
)

pmax_adjusted_wtp = (
    adjusted_wtp * base_delta_qaly
    - base_non_drug_cost_used
    + comparator_cost
)

pmax_scenario = pmax_adjusted_wtp * (
    1 - scenario_price_reduction_pct / 100
)

rebate_be = 1 - (pmax_be / aup) if aup > 0 else np.nan
rebate_headroom = 1 - (pmax_headroom / aup) if aup > 0 else np.nan
rebate_adjusted = 1 - (pmax_adjusted_wtp / aup) if aup > 0 else np.nan
rebate_scenario = 1 - (pmax_scenario / aup) if aup > 0 else np.nan

net_price_offer = aup * (1 - offered_discount_decimal)

offer_rows = run_scenario_curves(
    list_intervention_cost=aup,
    comparator_cost=comparator_cost,
    scenarios=scenarios,
    wtp=wtp,
    discounts=np.array([offered_discount_decimal]),
)

offer_summary = classify_residual_uncertainty(
    df=offer_rows,
    wtp=wtp,
    headroom_required=headroom_required,
    base_case_name="Base case",
).iloc[0]

ordinary_threshold = first_discount_where(
    summary_df,
    lambda x: x["base_icer"] <= wtp,
)

all_scenarios_threshold = first_discount_where(
    summary_df,
    lambda x: x["max_scenario_icer"] <= wtp,
)

headroom_threshold = first_discount_where(
    summary_df,
    lambda x: x["base_icer"] <= headroom_wtp,
)

robust_threshold = first_discount_where(
    summary_df,
    lambda x: (
        (x["max_scenario_icer"] <= wtp)
        & (x["headroom_percent"] >= headroom_required_pct)
    ),
)


# =====================================================
# RESULTS
# =====================================================

st.header("Results at selected inputs")

col1, col2, col3, col4 = st.columns(4)

col1.metric("Break-even Pmax", fmt_nok(pmax_be))
col2.metric("Pmax with required headroom", fmt_nok(pmax_headroom))
col3.metric("Pmax with optional WTP adjustment", fmt_nok(pmax_adjusted_wtp))
col4.metric("Scenario Pmax", fmt_nok(pmax_scenario))

col1.metric("Base-case rebate needed", fmt_pct(rebate_be * 100))
col2.metric("Rebate for required headroom", fmt_pct(rebate_headroom * 100))
col3.metric("Rebate with WTP adjustment", fmt_pct(rebate_adjusted * 100))
col4.metric("Scenario rebate", fmt_pct(rebate_scenario * 100))

st.subheader("Offered / negotiated discount interpretation")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Offered discount", f"{offered_discount:.1f}%")
c2.metric("Net intervention price", fmt_nok(net_price_offer))
c3.metric("Base-case ICER at offer", fmt_nok(offer_summary["base_icer"]))
c4.metric("Headroom at offer", f"{offer_summary['headroom_percent']:.1f}%")

st.info(f"**Status at offered discount:** {offer_summary['status']}")


# =====================================================
# DISCOUNT ANCHORS
# =====================================================

st.header("Discount anchors")

anchor_df = pd.DataFrame({
    "Anchor": [
        "Base case reaches WTP",
        "All included scenarios below WTP",
        f"Base case reaches {headroom_required_pct}% headroom",
        "Robust threshold: all scenarios below WTP + base-case headroom",
    ],
    "Required discount (%)": [
        None if ordinary_threshold is None else ordinary_threshold["discount_percent"],
        None if all_scenarios_threshold is None else all_scenarios_threshold["discount_percent"],
        None if headroom_threshold is None else headroom_threshold["discount_percent"],
        None if robust_threshold is None else robust_threshold["discount_percent"],
    ],
})

st.dataframe(anchor_df, use_container_width=True)


# =====================================================
# PLOTS
# =====================================================

st.header("Scenario ICER curves across discount levels")

fig = px.line(
    df,
    x="discount_percent",
    y="icer",
    color="scenario",
    markers=True,
    title="ICER by scenario across discounts",
    labels={
        "discount_percent": "Discount from AUP (%)",
        "icer": "ICER (NOK/QALY)",
    },
)

fig.add_hline(
    y=wtp,
    line_dash="dash",
    annotation_text="Base WTP",
)

fig.add_hline(
    y=headroom_wtp,
    line_dash="dot",
    annotation_text=f"WTP with {headroom_required_pct}% headroom",
)

if wtp_adjustment_pct > 0:
    fig.add_hline(
        y=adjusted_wtp,
        line_dash="dashdot",
        annotation_text="Adjusted WTP",
    )

fig.update_yaxes(
    range=[
        0,
        max(
            wtp * 3,
            df["icer"].replace(np.inf, np.nan).quantile(0.95),
        ),
    ]
)

st.plotly_chart(fig, use_container_width=True)


st.header("Residual uncertainty classification across discounts")

fig2 = px.line(
    summary_df,
    x="discount_percent",
    y="headroom_percent",
    markers=True,
    title="Headroom created by price discount",
    labels={
        "discount_percent": "Discount from AUP (%)",
        "headroom_percent": "Base-case headroom below WTP (%)",
    },
)

fig2.add_hline(
    y=headroom_required_pct,
    line_dash="dash",
    annotation_text="Required headroom",
)

st.plotly_chart(fig2, use_container_width=True)

st.dataframe(
    summary_df[[
        "discount_percent",
        "base_icer",
        "max_scenario_icer",
        "decision_flip",
        "all_scenarios_cost_effective",
        "headroom_percent",
        "status",
    ]],
    use_container_width=True,
)


# =====================================================
# INTERPRETATION LOGIC
# =====================================================

st.header("Interpretation")

if offer_summary["base_icer"] > wtp:
    st.error(
        "The offered discount does not make the base case cost-effective. "
        "Further price reduction is needed before residual uncertainty is considered."
    )

elif offer_summary["decision_flip"] and offer_summary["headroom_percent"] < headroom_required_pct:
    st.warning(
        "The offer makes the base case cost-effective, but plausible scenarios still cross "
        "the WTP threshold and headroom is limited. Residual decision uncertainty remains."
    )

elif offer_summary["decision_flip"] and offer_summary["headroom_percent"] >= headroom_required_pct:
    st.warning(
        "The offer creates some price headroom, but not all scenarios are below WTP. "
        "The rebate partly internalises uncertainty, but residual structural uncertainty may remain."
    )

elif offer_summary["all_scenarios_cost_effective"] and offer_summary["headroom_percent"] >= headroom_required_pct:
    st.success(
        "The offered discount creates enough headroom and all included scenarios remain below WTP. "
        "Additional WTP reduction is likely unnecessary and may risk double penalisation."
    )

elif offer_summary["all_scenarios_cost_effective"] and offer_summary["headroom_percent"] < headroom_required_pct:
    st.info(
        "All scenarios are cost-effective, but the base case has limited headroom. "
        "Consider whether ordinary uncertainty handling is sufficient or whether extra headroom is needed."
    )

else:
    st.info(
        "The case requires qualitative interpretation. Review scenario stability, model structure "
        "and whether probabilities can be credibly assigned."
    )

st.markdown("""
### How to read this tool

A rebate can act as an uncertainty mechanism when it creates enough distance between the net ICER and the WTP threshold.

The practical question is not whether the discount is large, but whether the net price keeps the decision robust under conservative scenarios.

Suggested decision logic:

1. **Base-case threshold**: the price where the base-case ICER equals WTP.
2. **Scenario threshold**: the price where all key conservative scenarios remain below WTP.
3. **Headroom threshold**: the price where the base case sits below WTP by the required buffer.
4. **Robust threshold**: the price where both scenario stability and headroom are achieved.

If the offered discount reaches the robust threshold, uncertainty is more likely to be internalised by price.

If it only reaches the base-case threshold, residual decision uncertainty may remain.
""")


# =====================================================
# FORMULAS
# =====================================================

st.header("Framework formulas")

st.latex(r'''
ICER_{net} =
\frac{
Price_{net} + C_{non\text{-}drug} - C_{comparator}
}{
\Delta QALY
}
''')

st.latex(r'''
Headroom\% =
\frac{
WTP - ICER_{net}
}{
WTP
}
''')

st.latex(r'''
Pmax_{BE} =
WTP \times \Delta QALY
- C_{non\text{-}drug}
+ C_{comparator}
''')

st.latex(r'''
Pmax_{headroom} =
WTP \times (1-h) \times \Delta QALY
- C_{non\text{-}drug}
+ C_{comparator}
''')

st.latex(r'''
Required\ rebate =
1 - \frac{Pmax}{AUP}
''')
