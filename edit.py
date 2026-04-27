
from pathlib import Path

import pandas as pd
import streamlit as st


def render_edit(data_path: Path) -> None:
    st.subheader("Data Editor")

    dataset_choice = st.selectbox(
        "Choose dataset to edit",
        [
            "athletes.csv",
            "training_sessions.csv",
            "performance_tests.csv",
            "competition_results.csv",
            "injuries.csv",
            "readiness_scores.csv",
            "coach_notes.csv",
        ],
    )

    selected_path = data_path / dataset_choice

    if not selected_path.exists():
        st.warning(f"Missing file: {selected_path.name}")
        return

    df = pd.read_csv(selected_path)
    edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

    if st.button("Save changes"):
        edited_df.to_csv(selected_path, index=False)
        st.success(f"{selected_path.name} saved successfully.")
