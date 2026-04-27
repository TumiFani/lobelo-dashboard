import streamlit as st
import pandas as pd


def _options(df: pd.DataFrame, column: str) -> list[str]:
    if df.empty or column not in df.columns:
        return []
    return sorted(df[column].dropna().astype(str).unique().tolist())


def render_sidebar(athletes: pd.DataFrame) -> dict:
    with st.sidebar:

        st.markdown("""
        <style>
        section[data-testid="stSidebar"] div[role="radiogroup"] label {
            font-size:14px !important;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown("""
        <style>

        /* Navigation radio items (Executive Overview, etc.) */
        section[data-testid="stSidebar"] div[role="radiogroup"] label div {
            font-size: 13px !important;
        }

        /* "Navigation" title above the radio group */
        section[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] {
        font-size: 13px !important;
        }

        /* Filters section headers */
        section[data-testid="stSidebar"] h3 {
        font-size: 13px !important;
        }

        </style>
        """, unsafe_allow_html=True)

        page = st.radio(
            "Navigation",
           [
                "Executive Overview",
                "Performance Analytics",
                "Athlete Explorer",
                "Ask Lobelo",
                "Data Editor",
           ],
           index=[
                "Executive Overview",
                "Performance Analytics",
                "Athlete Explorer",
                "Ask Lobelo",
                "Data Editor",
           ].index(st.session_state.get("page", "Executive Overview")),
           key="navigation_radio_main"
        )
        st.session_state.page = page


        st.markdown("---")
        st.markdown("### Filters")

        if athletes.empty:
            st.warning("Athletes data not found.")
            filters = {
                "search_text": "",
                "classification": [],
                "gender": [],
                "primary_event": [],
                "development_stage": [],
                "availability_status": [],
                "coach": [],
                "region": [],
            }
        else:
            filters = {
                "search_text": st.text_input("Search athlete", placeholder="type name or ID"),
                "classification": st.multiselect("Classification", _options(athletes, "classification")),
                "gender": st.multiselect("Gender", _options(athletes, "gender")),
                "primary_event": st.multiselect("Primary event", _options(athletes, "primary_event")),
                "development_stage": st.multiselect("Development stage", _options(athletes, "development_stage")),
                "availability_status": st.multiselect("Availability", _options(athletes, "availability_status")),
                "coach": st.multiselect("Coach", _options(athletes, "coach")),
                "region": st.multiselect("Region", _options(athletes, "region")),
            }

            st.markdown("---")
            st.markdown("### Selection summary")

            filtered = athletes.copy()
            text = filters["search_text"].strip()

            if text:
                name_mask = filtered["name"].astype(str).str.contains(text, case=False, na=False)
                id_mask = filtered["athlete_id"].astype(str).str.contains(text, case=False, na=False)
                filtered = filtered[name_mask | id_mask]

            for key, column in [
                ("classification", "classification"),
                ("gender", "gender"),
                ("primary_event", "primary_event"),
                ("development_stage", "development_stage"),
                ("availability_status", "availability_status"),
                ("coach", "coach"),
                ("region", "region"),
            ]:
                if filters[key]:
                    filtered = filtered[filtered[column].isin(filters[key])]

            st.markdown(f"**Athletes in scope:** `{len(filtered):,}`")

            if not filtered.empty:
                st.markdown(f"**Events covered:** `{filtered['primary_event'].nunique()}`")
                st.markdown(f"**Classes covered:** `{filtered['classification'].nunique()}`")

    return {"page": page, "filters": filters}