
import pandas as pd
import plotly.express as px
import streamlit as st


def metric_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _chart_style(fig, title: str, height: int = 310):
    fig.update_layout(
        title=dict(text=title, x=0.04, xanchor="left"),
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=45, b=20),
        legend_title_text="",
    )
    fig.update_yaxes(gridcolor="#D9E1EA")
    fig.update_xaxes(showgrid=False)
    return fig


def _filter_by_ids(df: pd.DataFrame, athlete_ids: list[str]) -> pd.DataFrame:
    if df.empty or "athlete_id" not in df.columns:
        return df.copy()
    if not athlete_ids:
        return df.iloc[0:0].copy()
    return df[df["athlete_id"].isin(athlete_ids)].copy()


def render_team_overview(data: dict, filtered_athletes: pd.DataFrame) -> None:
    athletes = filtered_athletes.copy()
    sessions = _filter_by_ids(data["training_sessions"], athletes["athlete_id"].tolist() if not athletes.empty else [])
    performance = _filter_by_ids(data["performance_tests"], athletes["athlete_id"].tolist() if not athletes.empty else [])
    competitions = _filter_by_ids(data["competition_results"], athletes["athlete_id"].tolist() if not athletes.empty else [])
    injuries = _filter_by_ids(data["injuries"], athletes["athlete_id"].tolist() if not athletes.empty else [])
    readiness = _filter_by_ids(data["readiness_scores"], athletes["athlete_id"].tolist() if not athletes.empty else [])

    st.markdown('<div style="font-size:22px;font-weight:700;color:#111827;margin-bottom:0.35rem;">Executive Overview</div>', unsafe_allow_html=True)

    if athletes.empty:
        st.info("No athletes match the selected filters.")
        return

    active_athletes = len(athletes)
    competition_ready_pct = round((readiness["status"].eq("Ready").mean() * 100), 1) if not readiness.empty else 0.0
    podium_track = athletes["development_stage"].eq("Podium Track").sum() if "development_stage" in athletes.columns else 0
    injury_risk_index = round(readiness["injury_risk"].mean(), 2) if not readiness.empty else 0.0
    session_completion_rate = round((sessions["completion_status"].eq("Completed").mean() * 100), 1) if not sessions.empty else 0.0
    recent_pbs = int(performance["is_pb"].fillna(False).sum()) if "is_pb" in performance.columns else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        metric_card("Active Athletes", f"{active_athletes:,}")
    with c2:
        metric_card("Competition Ready %", f"{competition_ready_pct}%")
    with c3:
        metric_card("Podium Track Athletes", f"{podium_track:,}")
    with c4:
        metric_card("Injury Risk Index", f"{injury_risk_index:.2f}")
    with c5:
        metric_card("Session Completion %", f"{session_completion_rate}%")
    with c6:
        metric_card("PB Improvements", f"{recent_pbs:,}")

    st.markdown("<hr class='section-separator'>", unsafe_allow_html=True)

    row1_col1, row1_col2 = st.columns(2)

    with row1_col1:
        depth_df = (
            athletes.groupby(["primary_event", "classification"])
            .size()
            .reset_index(name="count")
            .sort_values(["primary_event", "classification"])
        )
        fig_depth = px.bar(
            depth_df,
            x="primary_event",
            y="count",
            color="classification",
            barmode="stack",
            color_discrete_sequence=["#324B73", "#6B87B3", "#A7B9D6"],
        )
        st.plotly_chart(_chart_style(fig_depth, "Classification Depth by Event"), use_container_width=True)

    with row1_col2:
        dev_counts = athletes["development_stage"].value_counts().reset_index()
        dev_counts.columns = ["development_stage", "count"]
        fig_dev = px.pie(
            dev_counts,
            names="development_stage",
            values="count",
            hole=0.55,
            color_discrete_sequence=["#1D66C2", "#6CB1EA", "#B9D2EA", "#D9E7F3"],
        )
        fig_dev.update_traces(textinfo="label+percent")
        st.plotly_chart(_chart_style(fig_dev, "Development Stage Distribution"), use_container_width=True)

    row2_col1, row2_col2 = st.columns(2)

    with row2_col1:
        medal_counts = (
            competitions.loc[competitions["position"] <= 3, "competition_level"]
            .value_counts()
            .reset_index()
        )
        medal_counts.columns = ["competition_level", "medals"]
        if medal_counts.empty:
            st.info("No podium finishes available for the current selection.")
        else:
            fig_medals = px.bar(
                medal_counts,
                x="competition_level",
                y="medals",
                color="competition_level",
                color_discrete_sequence=["#1D4FA8", "#2C7CCF", "#74B4EA", "#A8C2DD", "#D9E7F3"],
            )
            st.plotly_chart(_chart_style(fig_medals, "Podium Finishes by Competition Level"), use_container_width=True)

    with row2_col2:
        if injuries.empty or "start_date" not in injuries.columns:
            st.info("No injury records available for the current selection.")
        else:
            injuries = injuries.copy()
            injuries["injury_month"] = injuries["start_date"].dt.to_period("M").astype(str)
            injury_trend = injuries.groupby("injury_month").size().reset_index(name="count")
            fig_injury = px.line(
                injury_trend,
                x="injury_month",
                y="count",
                markers=True,
            )
            st.plotly_chart(_chart_style(fig_injury, "Injury Burden Timeline"), use_container_width=True)

    row3_col1, row3_col2 = st.columns(2)

    with row3_col1:
        readiness_dist = readiness["status"].value_counts().reset_index()
        readiness_dist.columns = ["status", "count"]
        fig_readiness = px.bar(
            readiness_dist,
            x="status",
            y="count",
            color="status",
            color_discrete_map={
                "Ready": "#1D66C2",
                "Monitor": "#6CB1EA",
                "Build Phase": "#B9D2EA",
                "Restricted": "#324B73",
            },
        )
        st.plotly_chart(_chart_style(fig_readiness, "Readiness Status Distribution"), use_container_width=True)

    with row3_col2:
        participation = (
            competitions.groupby("competition_name")["athlete_id"]
            .nunique()
            .reset_index(name="athletes")
            .sort_values("athletes", ascending=False)
            .head(12)
        )
        if participation.empty:
            st.info("No competition participation data available.")
        else:
            fig_participation = px.bar(
                participation,
                x="competition_name",
                y="athletes",
                color="athletes",
                color_continuous_scale="Blues",
            )
            st.plotly_chart(_chart_style(fig_participation, "Competition Participation"), use_container_width=True)


def render_performance_analytics(data: dict, filtered_athletes: pd.DataFrame) -> None:
    athletes = filtered_athletes.copy()
    performance = _filter_by_ids(data["performance_tests"], athletes["athlete_id"].tolist() if not athletes.empty else [])
    sessions = _filter_by_ids(data["training_sessions"], athletes["athlete_id"].tolist() if not athletes.empty else [])
    readiness = _filter_by_ids(data["readiness_scores"], athletes["athlete_id"].tolist() if not athletes.empty else [])
    competitions = _filter_by_ids(data["competition_results"], athletes["athlete_id"].tolist() if not athletes.empty else [])

    st.markdown('<div style="font-size:22px;font-weight:700;color:#111827;margin-bottom:0.35rem;">Performance Analytics</div>', unsafe_allow_html=True)

    if athletes.empty:
        st.info("No athletes match the selected filters.")
        return

    tab1, tab2, tab3 = st.tabs(["Performance Trends", "Training Load", "Competition Signals"])

    with tab1:
        if performance.empty:
            st.info("No performance test data available.")
        else:
            performance = performance.copy()
            performance["month"] = performance["date"].dt.to_period("M").astype(str)

            event_options = sorted(performance["event"].dropna().unique().tolist())
            selected_event = st.selectbox("Event", event_options, key="perf_event")

            perf_event = performance[performance["event"] == selected_event]
            month_trend = perf_event.groupby("month")["time_seconds"].median().reset_index()
            pb_counts = perf_event.groupby("month")["is_pb"].sum().reset_index()

            col1, col2 = st.columns(2)

            with col1:
                fig_time = px.line(month_trend, x="month", y="time_seconds", markers=True)
                st.plotly_chart(_chart_style(fig_time, f"Median Time Trend — {selected_event}"), use_container_width=True)

            with col2:
                fig_pb = px.bar(pb_counts, x="month", y="is_pb", color="is_pb", color_continuous_scale="Blues")
                st.plotly_chart(_chart_style(fig_pb, f"PB Count by Month — {selected_event}"), use_container_width=True)

    with tab2:
        if sessions.empty:
            st.info("No training session data available.")
        else:
            sessions = sessions.copy()
            sessions["month"] = sessions["date"].dt.to_period("M").astype(str)
            load_trend = sessions.groupby("month")["duration_minutes"].sum().reset_index()
            completion_split = sessions["completion_status"].value_counts().reset_index()
            completion_split.columns = ["completion_status", "count"]

            col1, col2 = st.columns(2)
            with col1:
                fig_load = px.line(load_trend, x="month", y="duration_minutes", markers=True)
                st.plotly_chart(_chart_style(fig_load, "Training Load by Month"), use_container_width=True)
            with col2:
                fig_completion = px.pie(
                    completion_split,
                    names="completion_status",
                    values="count",
                    hole=0.55,
                    color_discrete_sequence=["#1D66C2", "#6CB1EA", "#D9E7F3"],
                )
                fig_completion.update_traces(textinfo="label+percent")
                st.plotly_chart(_chart_style(fig_completion, "Session Completion Split"), use_container_width=True)

    with tab3:
        if competitions.empty and readiness.empty:
            st.info("No competition or readiness data available.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                if competitions.empty:
                    st.info("No competition results available.")
                else:
                    event_success = competitions.assign(podium=competitions["position"] <= 3)
                    event_success = event_success.groupby("event")["podium"].mean().reset_index()
                    event_success["podium"] = (event_success["podium"] * 100).round(1)
                    fig_success = px.bar(
                        event_success,
                        x="event",
                        y="podium",
                        color="podium",
                        color_continuous_scale="Blues",
                    )
                    st.plotly_chart(_chart_style(fig_success, "Podium Rate by Event"), use_container_width=True)
            with col2:
                if readiness.empty:
                    st.info("No readiness score data available.")
                else:
                    score_dist = readiness.copy()
                    fig_scores = px.histogram(score_dist, x="overall_readiness_score", nbins=20)
                    st.plotly_chart(_chart_style(fig_scores, "Readiness Score Distribution"), use_container_width=True)
