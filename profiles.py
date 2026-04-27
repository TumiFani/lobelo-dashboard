import pandas as pd
import plotly.express as px
import streamlit as st


# =========================================================
# CHART STYLE
# =========================================================

def style_chart(fig, title):
    fig.update_layout(
        title=dict(
            text=title,
            x=0.01,
            xanchor="left",
            font=dict(size=16, color="#0f172a"),
        ),
        height=320,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=42, b=20),
        font=dict(color="#334155"),
        legend_title_text=""
    )

    fig.update_yaxes(gridcolor="#E2E8F0")
    fig.update_xaxes(showgrid=False)

    return fig


def draw(fig):
    st.plotly_chart(
        fig,
        use_container_width=True,
        config={"displayModeBar": False}
    )


# =========================================================
# ATHLETE HEADER (PROFESSIONAL TYPOGRAPHY SYSTEM)
# =========================================================

def render_header(athlete, readiness, injuries):

    latest = readiness.sort_values("date").iloc[-1] if not readiness.empty else None
    previous = readiness.sort_values("date").iloc[-2] if len(readiness) > 1 else None
    injury = injuries.sort_values("start_date").iloc[-1] if not injuries.empty else None

    score = round(latest["overall_readiness_score"] * 100) if latest is not None else "—"
    consistency = round(latest["training_consistency"], 2) if latest is not None else "—"
    comp_ready = round(latest["competition_readiness"], 2) if latest is not None else "—"

    trend = ""
    if latest is not None and previous is not None:
        delta = latest["overall_readiness_score"] - previous["overall_readiness_score"]
        trend = f"{'▲' if delta>0 else '▼'} {round(delta*100,1)}%" if delta != 0 else "—"

    injury_line = athlete["injury_status"]
    if injury is not None:
        injury_line += f" · {injury['injury_type']}"

    coach = str(athlete["coach"]).replace("Coach ", "")

    gender = athlete.get("gender", "—")
    impairment = athlete.get("impairment", "Visually Impaired")

    st.markdown(f"""

<div style="
padding:4px 0 18px 0;
border-bottom:1px solid #e2e8f0;
margin-bottom:16px">

<div style="
display:grid;
grid-template-columns:1.4fr 1fr 1fr;
gap:28px;
align-items:center">

<!-- COLUMN 1 -->
<div>

<div style="font-size:28px;font-weight:700;color:#0f172a">
{athlete["classification"]} · {gender}
</div>

<div style="font-size:22px;font-weight:600;color:#0f172a">
{athlete["name"]}
</div>

<div style="font-size:13px;color:#64748b">
{athlete["development_stage"]} Squad · Coach {coach}
</div>

<div style="font-size:13px;color:#64748b">
Impairment: {impairment}
</div>

</div>


<!-- COLUMN 2 -->
<div>

<div style="font-size:12px;letter-spacing:1.2px;color:#64748b">
PRIMARY EVENT
</div>

<div style="font-size:24px;font-weight:700;color:#0f172a">
{athlete["primary_event"]}
</div>

<div style="font-size:13px;color:#64748b">
Secondary: {athlete["secondary_event"]}
</div>


<div style="margin-top:10px;font-size:12px;letter-spacing:1.2px;color:#64748b">
SELECTION STATUS
</div>

<div style="font-size:18px;font-weight:600;color:#0f172a">
{athlete["availability_status"]}
</div>

<div style="font-size:13px;color:#64748b">
{injury_line}
</div>

</div>


<!-- COLUMN 3 -->
<div style="text-align:right">

<div style="font-size:12px;letter-spacing:1.2px;color:#64748b">
READINESS
</div>

<div style="font-size:36px;font-weight:700;color:#0f172a">
{score}%
</div>

<div style="font-size:13px;color:#64748b">
Consistency {consistency} · Competition {comp_ready}
</div>

<div style="font-size:13px;color:#64748b">
Trend {trend}
</div>

</div>

</div>

</div>

""", unsafe_allow_html=True)


# =========================================================
# MAIN PAGE
# =========================================================

def render_profiles(data, filtered_athletes):

    st.markdown("## Athlete Explorer")

    if filtered_athletes.empty:
        st.info("No athletes available.")
        return

    athlete_name = st.selectbox(
        "Select athlete",
        sorted(filtered_athletes["name"].tolist())
    )

    athlete = filtered_athletes[
        filtered_athletes["name"] == athlete_name
    ].iloc[0]

    athlete_id = athlete["athlete_id"]

    sessions = data["training_sessions"]
    performance = data["performance_tests"]
    competitions = data["competition_results"]
    injuries = data["injuries"]
    readiness = data["readiness_scores"]
    notes = data["coach_notes"]

    athlete_sessions = sessions[sessions.athlete_id == athlete_id]
    athlete_perf = performance[performance.athlete_id == athlete_id]
    athlete_comp = competitions[competitions.athlete_id == athlete_id]
    athlete_inj = injuries[injuries.athlete_id == athlete_id]
    athlete_ready = readiness[readiness.athlete_id == athlete_id]
    athlete_notes = notes[notes.athlete_id == athlete_id]

    render_header(athlete, athlete_ready, athlete_inj)

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Performance", "Competitions", "Medical", "Coach Notes"]
    )

    # PERFORMANCE
    with tab1:

        col1, col2 = st.columns(2)

        with col1:
            if athlete_perf.empty:
                st.info("No performance tests recorded.")
            else:
                fig = px.line(
                    athlete_perf.sort_values("date"),
                    x="date",
                    y="time_seconds",
                    color="event",
                    markers=True
                )
                draw(style_chart(fig, "Performance Test Trend"))

        with col2:
            if athlete_sessions.empty:
                st.info("No training sessions recorded.")
            else:
                mix = athlete_sessions["session_type"].value_counts().reset_index()
                mix.columns = ["session_type", "count"]

                fig = px.bar(mix, x="session_type", y="count")
                draw(style_chart(fig, "Session Type Mix"))

        if not athlete_sessions.empty:
            st.subheader("Training Session Log")
            st.dataframe(
                athlete_sessions.sort_values("date", ascending=False),
                use_container_width=True,
                hide_index=True
            )

    # COMPETITIONS
    with tab2:

        col1, col2 = st.columns(2)

        with col1:
            if athlete_comp.empty:
                st.info("No competition results recorded.")
            else:
                fig = px.line(
                    athlete_comp.sort_values("date"),
                    x="date",
                    y="position",
                    color="event",
                    markers=True
                )
                fig.update_yaxes(autorange="reversed")
                draw(style_chart(fig, "Finishing Position Trend"))

        with col2:
            if athlete_comp.empty:
                st.info("No qualification history recorded.")
            else:
                qual = athlete_comp["qualification_status"].value_counts().reset_index()
                qual.columns = ["status", "count"]

                fig = px.pie(qual, names="status", values="count", hole=0.55)
                draw(style_chart(fig, "Qualification Split"))

        if not athlete_comp.empty:
            st.subheader("Competition Log")
            st.dataframe(
                athlete_comp.sort_values("date", ascending=False),
                use_container_width=True,
                hide_index=True
            )

    # MEDICAL
    with tab3:

        col1, col2 = st.columns(2)

        with col1:
            if athlete_inj.empty:
                st.info("No injury history recorded.")
            else:
                sev = athlete_inj["severity"].value_counts().reset_index()
                sev.columns = ["severity", "count"]

                fig = px.bar(sev, x="severity", y="count")
                draw(style_chart(fig, "Injury Severity Profile"))

        with col2:
            if athlete_inj.empty:
                st.info("No lost-time injury data available.")
            else:
                fig = px.bar(
                    athlete_inj.sort_values("days_lost"),
                    x="injury_type",
                    y="days_lost",
                    color="body_area"
                )
                draw(style_chart(fig, "Days Lost by Injury"))

        if not athlete_inj.empty:
            st.subheader("Medical Log")
            st.dataframe(
                athlete_inj.sort_values("start_date", ascending=False),
                use_container_width=True,
                hide_index=True
            )

    # COACH NOTES
    with tab4:

        if athlete_notes.empty:
            st.info("No notes recorded.")
        else:
            types = st.multiselect(
                "Note type",
                athlete_notes["note_type"].unique(),
                default=athlete_notes["note_type"].unique()
            )

            filtered = athlete_notes[
                athlete_notes.note_type.isin(types)
            ]

            for _, row in filtered.iterrows():

                st.markdown(f"""
<div style="
padding:14px 18px;
border-radius:12px;
background:#f8fafc;
border:1px solid #e2e8f0;
margin-bottom:10px">

<div style="
font-size:12px;
color:#64748b;
margin-bottom:6px">

{row["date"].strftime("%Y-%m-%d")} · {row["note_type"].upper()}

</div>

<div style="font-size:15px;color:#0f172a">
{row["note_text"]}
</div>

</div>
""", unsafe_allow_html=True)