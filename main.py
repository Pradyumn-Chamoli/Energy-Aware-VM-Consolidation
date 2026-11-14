
import os
import sys
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config import DEFAULT_CONFIG
from simulation.engine import run_simulation


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Energy-Aware VM Consolidation",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Energy-Aware VM Consolidation")
st.caption(
    "Energy-efficient virtual machine placement, migration "
    "and physical server management."
)


# --------------------------------------------------
# SIDEBAR CONFIGURATION
# --------------------------------------------------

with st.sidebar:

    st.header("Simulation Configuration")

    num_hosts = st.slider(
        "Physical hosts",
        3, 20,
        DEFAULT_CONFIG["num_hosts"]
    )

    num_vms = st.slider(
        "Virtual machines",
        5, 80,
        DEFAULT_CONFIG["num_vms"]
    )

    host_capacity = st.number_input(
        "CPU capacity per host",
        50.0, 500.0,
        float(DEFAULT_CONFIG["host_capacity"]),
        10.0
    )

    steps = st.slider(
        "Simulation time steps",
        12, 144,
        DEFAULT_CONFIG["simulation_steps"],
        4
    )

    step_minutes = st.selectbox(
        "Minutes per step",
        [5, 10, 15, 30, 60],
        index=2
    )

    underload_pct = st.slider(
        "Underload threshold (%)",
        10, 60,
        int(DEFAULT_CONFIG["underload_threshold"] * 100)
    )

    safety_pct = st.slider(
        "Safe maximum utilization (%)",
        70, 100,
        int(DEFAULT_CONFIG["safety_threshold"] * 100)
    )

    idle_power = st.number_input(
        "Idle power (W)",
        50.0, 300.0,
        float(DEFAULT_CONFIG["idle_power_w"]),
        5.0
    )

    max_power = st.number_input(
        "Maximum power (W)",
        100.0, 500.0,
        float(DEFAULT_CONFIG["max_power_w"]),
        5.0
    )

    migration_cost = st.number_input(
        "Migration energy cost (Wh)",
        0.0, 100.0,
        float(DEFAULT_CONFIG["migration_energy_wh"]),
        1.0
    )

    vm_selection = st.selectbox(
        "VM selection strategy",
        [
            "Minimum CPU first",
            "Maximum CPU first",
            "Minimum migration time"
        ]
    )

    seed = st.number_input(
        "Random seed",
        0, 100000,
        DEFAULT_CONFIG["seed"]
    )

    run_button = st.button(
        "▶ Run simulation",
        type="primary",
        use_container_width=True
    )


# --------------------------------------------------
# SIMULATION CONFIGURATION
# --------------------------------------------------

if num_vms < num_hosts:
    st.warning(
        "For meaningful consolidation, use at least "
        "as many VMs as physical hosts."
    )

config = {
    "num_hosts": num_hosts,
    "num_vms": num_vms,
    "host_capacity": float(host_capacity),
    "simulation_steps": steps,
    "step_minutes": step_minutes,
    "underload_threshold": underload_pct / 100.0,
    "overload_threshold": DEFAULT_CONFIG["overload_threshold"],
    "safety_threshold": safety_pct / 100.0,
    "idle_power_w": float(idle_power),
    "max_power_w": float(max(max_power, idle_power)),
    "migration_energy_wh": float(migration_cost),
    "migration_overhead": DEFAULT_CONFIG["migration_overhead"],
    "seed": int(seed)
}


# --------------------------------------------------
# RUN SIMULATION
# --------------------------------------------------

if run_button:

    if num_vms < 1 or num_hosts < 1:
        st.error("Configure at least one host and one VM.")
        st.stop()

    with st.spinner("Simulating data centre operations..."):

        results = run_simulation(config, vm_selection)

    st.session_state["results"] = results
    st.session_state["config"] = config


# --------------------------------------------------
# CHECK RESULTS
# --------------------------------------------------

if "results" not in st.session_state:

    st.info(
        "Configure the data centre in the sidebar "
        "and click Run simulation."
    )

    st.markdown("""
    ### Project features

    - Physical host and virtual machine simulation
    - Dynamic CPU workload generation
    - VM migration and consolidation
    - Automatic host shutdown and activation
    - Energy consumption calculation
    - Migration cost analysis
    - SLA and CPU capacity monitoring
    - Consolidation policy comparison
    """)

    st.stop()


results = st.session_state["results"]
saved_config = st.session_state["config"]

safety_limit = saved_config["safety_threshold"] * 100
simulation_steps = saved_config["simulation_steps"]


# --------------------------------------------------
# PREPARE POLICY RESULTS
# --------------------------------------------------

summary = []
host_data = {}
migration_data = {}

baseline = results["No Consolidation"].total_energy_wh

for name, result in results.items():

    host_df = pd.DataFrame(result.host_rows)
    migration_df = pd.DataFrame(result.migration_rows)

    host_data[name] = host_df
    migration_data[name] = migration_df

    # Count actual capacity violations independently.
    capacity_violations = int(
        (
            (host_df["active"] == True)
            & (host_df["utilization_pct"] > 100)
        ).sum()
    )

    # SLA violations use the configured safety threshold.
    safety_violations = result.sla_violations

    energy_savings = (
        (baseline - result.total_energy_wh) / baseline * 100
        if baseline > 0 else 0
    )

    max_utilization = (
        host_df.loc[host_df["active"], "utilization_pct"].max()
        if host_df["active"].any()
        else 0
    )

    final_active_hosts = int(
        host_df[host_df["step"] == simulation_steps]["active"].sum()
    )

    summary.append({

        "Policy": name,

        "Total energy (Wh)": round(
            result.total_energy_wh, 2
        ),

        "Energy saved (%)": round(
            energy_savings, 2
        ),

        "Operational energy (Wh)": round(
            result.operational_energy_wh, 2
        ),

        "Migration energy (Wh)": round(
            result.migration_energy_wh, 2
        ),

        "Migrations": result.migrations,

        "Hosts switched off": result.hosts_shutdown,

        "Active hosts at end": final_active_hosts,

        "Safety violations (> threshold)": safety_violations,

        "Capacity violations (>100%)": capacity_violations,

        "Maximum CPU utilization (%)": round(
            max_utilization, 2
        )
    })


summary_df = pd.DataFrame(summary)


# --------------------------------------------------
# FIND BEST POLICY
# --------------------------------------------------

best_policy = min(
    results.values(),
    key=lambda r: r.total_energy_wh
)

best_energy = best_policy.total_energy_wh

best_savings = (
    (baseline - best_energy) / baseline * 100
    if baseline > 0 else 0
)


# --------------------------------------------------
# MAIN METRICS
# --------------------------------------------------

st.subheader("Simulation Overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Baseline Energy",
    f"{baseline:,.2f} Wh"
)

c2.metric(
    "Best Policy Energy",
    f"{best_energy:,.2f} Wh"
)

c3.metric(
    "Energy Reduction",
    f"{best_savings:.2f}%"
)

c4.metric(
    "Best Algorithm",
    best_policy.name
)


# --------------------------------------------------
# POLICY COMPARISON
# --------------------------------------------------

st.subheader("Consolidation Policy Comparison")

st.dataframe(
    summary_df,
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Safety violations count active-host intervals above the "
    "configured safety threshold. Capacity violations count "
    "active-host intervals exceeding 100% CPU capacity."
)


# --------------------------------------------------
# NAVIGATION TABS
# --------------------------------------------------

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Energy Analysis",
    "Host Utilization",
    "VM Migrations",
    "SLA Monitoring",
    "Raw Data",
    "Break-even Analysis"
])


# ==================================================
# TAB 1: ENERGY ANALYSIS
# ==================================================

with tab1:

    st.subheader("Energy Consumption Comparison")

    fig1 = px.bar(
        summary_df,
        x="Policy",
        y="Total energy (Wh)",
        color="Policy",
        text="Total energy (Wh)",
        title="Total Energy Including Migration Cost"
    )

    fig1.update_layout(
        yaxis_title="Energy (Wh)",
        xaxis_title="Consolidation Policy",
        showlegend=False
    )

    st.plotly_chart(
        fig1,
        use_container_width=True
    )

    # Operational energy over simulation time.
    energy_df = pd.concat([
        pd.DataFrame(result.step_rows).assign(Policy=name)
        for name, result in results.items()
    ], ignore_index=True)

    fig2 = px.line(
        energy_df,
        x="time_minutes",
        y="operational_energy_wh",
        color="Policy",
        markers=True,
        title="Operational Energy Per Simulation Interval"
    )

    fig2.update_layout(
        xaxis_title="Simulation Time (minutes)",
        yaxis_title="Energy per interval (Wh)"
    )

    st.plotly_chart(
        fig2,
        use_container_width=True
    )

    # Migration energy comparison.
    fig3 = px.bar(
        summary_df,
        x="Policy",
        y="Migration energy (Wh)",
        color="Policy",
        title="Energy Cost of VM Migrations"
    )

    fig3.update_layout(showlegend=False)

    st.plotly_chart(
        fig3,
        use_container_width=True
    )

    st.success(
        f"{best_policy.name} achieved the lowest estimated "
        f"total energy consumption: {best_energy:,.2f} Wh."
    )


# ==================================================
# TAB 2: HOST UTILIZATION
# ==================================================

with tab2:

    st.subheader("Physical Host Monitoring")

    selected_policy = st.selectbox(
        "Select consolidation policy",
        list(results.keys()),
        key="host_policy"
    )

    host_df = host_data[selected_policy].copy()

    selected_step = st.slider(
        "Inspect simulation time step",
        1,
        simulation_steps,
        simulation_steps,
        key="host_step"
    )

    snapshot = host_df[
        host_df["step"] == selected_step
    ].copy()

    # Give every host a readable status.
    def get_host_status(row):

        if not row["active"]:
            return "Powered Off"

        if row["utilization_pct"] > 100:
            return "Overloaded"

        if row["utilization_pct"] > safety_limit:
            return "Above Safety Limit"

        return "Active"

    snapshot["Status"] = snapshot.apply(
        get_host_status,
        axis=1
    )

    active_count = int(snapshot["active"].sum())
    inactive_count = len(snapshot) - active_count

    a, b, c = st.columns(3)

    a.metric("Active Hosts", active_count)
    b.metric("Powered-Off Hosts", inactive_count)

    c.metric(
        "Highest CPU Utilization",
        f"{snapshot['utilization_pct'].max():.2f}%"
    )

    fig4 = px.bar(
        snapshot,
        x="host_id",
        y="utilization_pct",
        color="Status",
        text="utilization_pct",
        hover_data=[
            "cpu_demand",
            "vm_count",
            "power_w"
        ],
        color_discrete_map={
            "Active": "#16A34A",
            "Powered Off": "#808080",
            "Above Safety Limit": "#F59E0B",
            "Overloaded": "#DC2626"
        },
        title=f"Host CPU Utilization at Step {selected_step}"
    )

    fig4.add_hline(
        y=safety_limit,
        line_dash="dash",
        line_color="orange",
        annotation_text="Safety Threshold"
    )

    fig4.add_hline(
        y=100,
        line_dash="dot",
        line_color="red",
        annotation_text="Maximum CPU Capacity"
    )

    fig4.update_layout(
        xaxis_title="Physical Host",
        yaxis_title="CPU Utilization (%)"
    )

    st.plotly_chart(
        fig4,
        use_container_width=True
    )

    st.subheader("Host Details")

    st.dataframe(
        snapshot,
        use_container_width=True,
        hide_index=True
    )


# ==================================================
# TAB 3: VM MIGRATIONS
# ==================================================

with tab3:

    st.subheader("Virtual Machine Migration History")

    migration_policy = st.selectbox(
        "Select policy",
        list(results.keys()),
        key="migration_policy"
    )

    migration_df = migration_data[migration_policy]

    result = results[migration_policy]

    m1, m2, m3 = st.columns(3)

    m1.metric(
        "Total Migrations",
        result.migrations
    )

    m2.metric(
        "Migration Energy",
        f"{result.migration_energy_wh:.2f} Wh"
    )

    m3.metric(
        "Hosts Switched Off",
        result.hosts_shutdown
    )

    if migration_df.empty:

        st.info(
            "No VM migrations were performed under this policy."
        )

    else:

        st.dataframe(
            migration_df,
            use_container_width=True,
            hide_index=True
        )

        migration_counts = (
            migration_df.groupby("step")
            .size()
            .reset_index(name="migrations")
        )

        fig5 = px.bar(
            migration_counts,
            x="step",
            y="migrations",
            title="VM Migrations Per Simulation Step"
        )

        st.plotly_chart(
            fig5,
            use_container_width=True
        )


# ==================================================
# TAB 4: SLA MONITORING
# ==================================================

with tab4:

    st.subheader("Service Level Agreement Monitoring")

    st.write(
        f"Configured safe CPU utilization threshold: "
        f"**{safety_limit:.0f}%**"
    )

    sla_policy = st.selectbox(
        "Select policy for SLA monitoring",
        list(results.keys()),
        key="sla_policy"
    )

    sla_result = results[sla_policy]
    sla_hosts = host_data[sla_policy]

    safety_violations = sla_result.sla_violations

    capacity_violations = int(
        (
            (sla_hosts["active"] == True)
            & (sla_hosts["utilization_pct"] > 100)
        ).sum()
    )

    s1, s2, s3 = st.columns(3)

    s1.metric(
        "Safety Threshold Violations",
        safety_violations
    )

    s2.metric(
        "Actual Capacity Violations",
        capacity_violations
    )

    s3.metric(
        "SLA Violation Rate",
        f"{safety_violations / (len(sla_hosts) or 1) * 100:.2f}%"
    )

    # Identify every host-time interval that violates the safety threshold.
    violations_df = sla_hosts[
        (sla_hosts["active"] == True)
        & (sla_hosts["utilization_pct"] > safety_limit)
    ].copy()

    if violations_df.empty:

        st.success(
            "No active host exceeded the configured safety threshold "
            "during this simulation."
        )

    else:

        st.warning(
            "Some hosts exceeded the configured safety threshold."
        )

        st.dataframe(
            violations_df,
            use_container_width=True,
            hide_index=True
        )

    # Show CPU capacity violations separately.
    overload_df = sla_hosts[
        (sla_hosts["active"] == True)
        & (sla_hosts["utilization_pct"] > 100)
    ]

    if overload_df.empty:

        st.success(
            "No physical host exceeded 100% CPU capacity."
        )

    else:

        st.error(
            f"{len(overload_df)} host-time capacity violations detected."
        )

        st.dataframe(
            overload_df,
            use_container_width=True,
            hide_index=True
        )


# ==================================================
# TAB 5: RAW DATA AND EXPORT
# ==================================================

with tab5:

    st.subheader("Simulation Data Export")

    detail_policy = st.selectbox(
        "Select policy",
        list(results.keys()),
        key="detail_policy"
    )

    detail_result = results[detail_policy]

    detail_df = pd.DataFrame(
        detail_result.step_rows
    )

    host_export = host_data[detail_policy]

    migration_export = migration_data[detail_policy]

    st.write("Time-step simulation records")

    st.dataframe(
        detail_df,
        use_container_width=True,
        hide_index=True
    )

    st.download_button(
        "Download Time-Step Results CSV",
        detail_df.to_csv(index=False).encode("utf-8"),
        file_name="time_step_results.csv",
        mime="text/csv"
    )

    st.write("Host performance records")

    st.download_button(
        "Download Host Metrics CSV",
        host_export.to_csv(index=False).encode("utf-8"),
        file_name="host_metrics.csv",
        mime="text/csv"
    )

    st.write("Migration records")

    st.download_button(
        "Download Migration History CSV",
        migration_export.to_csv(index=False).encode("utf-8"),
        file_name="migration_history.csv",
        mime="text/csv"
    )

    st.write("Policy comparison")

    st.download_button(
        "Download Policy Comparison CSV",
        summary_df.to_csv(index=False).encode("utf-8"),
        file_name="policy_comparison.csv",
        mime="text/csv"
    )


# ==================================================
# TAB 6: BREAK-EVEN ANALYSIS
# ==================================================

with tab6:

    st.subheader("VM Migration Break-even Analysis")

    st.markdown("""
    This analysis determines whether consolidating an
    underutilized host is energy-efficient.

    A migration is approved when the expected operational
    energy savings exceed the migration energy cost, while
    maintaining the configured CPU safety threshold.
    """)

    break_even_policy = st.selectbox(
        "Select consolidation policy",
        list(results.keys()),
        key="break_even_policy"
    )

    be_result = results[break_even_policy]

    be_rows = getattr(be_result, "break_even_rows", [])

    skipped = getattr(
        be_result,
        "migrations_skipped_not_worthwhile",
        0
    )

    if break_even_policy == "No Consolidation":

        st.info(
            "No Consolidation does not perform VM consolidation. "
            "Therefore, break-even analysis is not applicable."
        )

    elif not be_rows:

        st.info(
            "No underloaded hosts were considered for consolidation "
            "in this simulation."
        )

    else:

        be_df = pd.DataFrame(be_rows)

        approved_df = be_df[
            be_df["worthwhile"] == True
        ]

        rejected_df = be_df[
            be_df["worthwhile"] == False
        ]

        total_expected_savings = (
            be_df["expected_operational_savings_wh"].sum()
        )

        total_migration_cost = (
            be_df["migration_cost_wh"].sum()
        )

        total_net_savings = (
            be_df["net_energy_savings_wh"].sum()
        )

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Consolidation Evaluations",
            len(be_df)
        )

        col2.metric(
            "Approved Decisions",
            len(approved_df)
        )

        col3.metric(
            "Rejected Decisions",
            len(rejected_df)
        )

        col4.metric(
            "Skipped Decisions",
            skipped
        )

        st.divider()

        st.subheader("Energy Break-even Summary")

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Expected Operational Savings",
            f"{total_expected_savings:,.2f} Wh"
        )

        c2.metric(
            "Migration Energy Cost",
            f"{total_migration_cost:,.2f} Wh"
        )

        c3.metric(
            "Net Expected Savings",
            f"{total_net_savings:,.2f} Wh"
        )

        st.caption(
            "These totals represent consolidation evaluations. "
            "Multiple evaluations can overlap in their forecast "
            "horizons, so they must not be interpreted as additive "
            "realized energy savings."
        )

        st.divider()

        st.subheader("Consolidation Decision History")

        display_columns = [
            "step",
            "source_host",
            "vms_to_migrate",
            "expected_operational_savings_wh",
            "migration_cost_wh",
            "net_energy_savings_wh",
            "estimated_payback_steps",
            "future_placement_safe",
            "worthwhile",
            "decision"
        ]

        st.dataframe(
            be_df[display_columns],
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.subheader("Expected Savings vs Migration Cost")

        chart_df = be_df.melt(
            id_vars=["step", "source_host"],
            value_vars=[
                "expected_operational_savings_wh",
                "migration_cost_wh"
            ],
            var_name="Energy Metric",
            value_name="Energy (Wh)"
        )

        fig6 = px.bar(
            chart_df,
            x="source_host",
            y="Energy (Wh)",
            color="Energy Metric",
            barmode="group",
            hover_data=["step"],
            title="Expected Operational Savings vs Migration Cost"
        )

        st.plotly_chart(
            fig6,
            use_container_width=True
        )

        st.divider()

        st.subheader("Decision Explanation")

        for index, row in be_df.iterrows():

            with st.expander(
                f"Step {row['step']} | {row['source_host']} | "
                f"{'Approved' if row['worthwhile'] else 'Rejected'}"
            ):

                st.write(
                    f"**VMs to migrate:** {row['vms_to_migrate']}"
                )

                st.write(
                    f"**Expected operational savings:** "
                    f"{row['expected_operational_savings_wh']} Wh"
                )

                st.write(
                    f"**Migration cost:** "
                    f"{row['migration_cost_wh']} Wh"
                )

                st.write(
                    f"**Net expected savings:** "
                    f"{row['net_energy_savings_wh']} Wh"
                )

                st.write(
                    f"**Estimated payback:** "
                    f"{row['estimated_payback_steps']} steps"
                )

                st.write(
                    f"**Future placement safe:** "
                    f"{row['future_placement_safe']}"
                )

                st.write(
                    f"**Decision:** {row['decision']}"
                )

        st.download_button(
            "Download Break-even Analysis CSV",
            be_df.to_csv(index=False).encode("utf-8"),
            file_name="break_even_analysis.csv",
            mime="text/csv"
        )


# --------------------------------------------------
# FINAL INTERPRETATION
# --------------------------------------------------

st.divider()

st.subheader("Simulation Conclusion")

st.markdown(
    f"""
    **Best-performing policy:** {best_policy.name}

    - Baseline energy: {baseline:,.2f} Wh
    - Energy with best policy: {best_energy:,.2f} Wh
    - Estimated energy reduction: {best_savings:.2f}%
    - Total VM migrations: {best_policy.migrations}
    - Physical hosts switched off: {best_policy.hosts_shutdown}
    - Safety-threshold violations: {best_policy.sla_violations}

    The simulator compares different VM consolidation strategies
    and evaluates their energy consumption, migration costs and
    resource utilization.
    """
)

st.caption(
    "Note: This is a mathematical data-centre simulation. "
    "Energy and migration values are model-based estimates, "
    "not physical electricity meter measurements."
)
