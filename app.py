import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Planner App", page_icon="📅", layout="wide")

# --- STYLING ---
st.markdown("""
    <style>
    .main { background-color: #ffffff; }
    h1, h2, h3 { font-family: 'Helvetica Neue', sans-serif; font-weight: 300; }
    .stProgress > div > div > div > div { background-color: #4CAF50; }
    </style>
    """, unsafe_allow_html=True)

# --- GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)


def fetch_data():
    """Fetches data from Google Sheets."""
    try:
        # Reads from the worksheet named "Master"
        df = conn.read(worksheet="Master", ttl=0)
        return df
    except Exception:
        return pd.DataFrame(columns=["ID", "Task", "Status", "Deadline", "Notes", "Done"])


def save_data(df):
    """Writes the dataframe back to Google Sheets."""
    conn.update(worksheet="Master", data=df)
    st.cache_data.clear()


# --- INITIALIZE SESSION STATE ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = fetch_data()

# --- HELPER: ENSURE COLUMNS EXIST ---
required_cols = ["ID", "Task", "Status", "Deadline", "Notes", "Done"]
for col in required_cols:
    if col not in st.session_state.master_df.columns:
        st.session_state.master_df[col] = ""

# --- SIDEBAR ---
with st.sidebar:
    st.title("📅 Planner")
    page = st.radio("Navigation", ["Dashboard", "Raw Data View"])

    st.divider()
    with st.expander("Add New Task"):
        new_task = st.text_input("Task Name")
        if st.button("Add"):
            if new_task:
                # Create a new row
                new_row = pd.DataFrame([{
                    "ID": len(st.session_state.master_df) + 1,
                    "Task": new_task,
                    "Status": "Not Started",
                    "Deadline": datetime.date.today().strftime("%Y-%m-%d"),
                    "Notes": "",
                    "Done": False
                }])
                # Add to dataframe and save
                st.session_state.master_df = pd.concat([st.session_state.master_df, new_row], ignore_index=True)
                save_data(st.session_state.master_df)
                st.rerun()

# --- MAIN PAGE ---
if page == "Dashboard":
    st.title("Project Overview")

    # Metrics
    df = st.session_state.master_df
    total = len(df)
    done_count = len(df[df['Done'] == True])
    progress = done_count / total if total > 0 else 0

    # Progress Bar
    st.progress(progress)
    st.caption(f"{done_count} of {total} tasks completed")

    st.divider()

    # Interactive Grid
    edited_df = st.data_editor(
        df,
        column_config={
            "ID": None,  # Hide ID
            "Done": st.column_config.CheckboxColumn("Done"),
            "Status": st.column_config.SelectboxColumn("Status",
                                                       options=["Not Started", "In Progress", "Blocked", "Done"]),
            "Deadline": st.column_config.DateColumn("Deadline"),
            "Notes": st.column_config.TextColumn("Notes", width="large"),
        },
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True
    )

    # Save logic
    if st.button("Save Changes to Cloud", type="primary"):
        save_data(edited_df)
        st.success("✅ Saved to Google Sheets!")
        st.session_state.master_df = edited_df

elif page == "Raw Data View":
    st.write("Current Database View:")
    st.dataframe(st.session_state.master_df)