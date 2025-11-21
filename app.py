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

# --- CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)


# --- HELPER FUNCTIONS ---

def fetch_master():
    """Fetches the Master list."""
    try:
        df = conn.read(worksheet="Master", ttl=0)
        # Ensure necessary columns exist
        expected_cols = ["ID", "Task", "Status", "Deadline", "Notes", "Done", "SheetName"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = ""
        return df
    except Exception:
        # Initialize Master if it fails/is empty
        return pd.DataFrame(columns=["ID", "Task", "Status", "Deadline", "Notes", "Done", "SheetName"])


def save_master(df):
    conn.update(worksheet="Master", data=df)
    st.cache_data.clear()


def fetch_task_details(sheet_name):
    """Fetches the specific tab for a task."""
    try:
        return conn.read(worksheet=sheet_name, ttl=0)
    except:
        # If sheet doesn't exist yet (rare), return default template
        return pd.DataFrame(columns=["Item", "Cost", "Status", "Notes"])


def save_task_details(sheet_name, df):
    """Saves to the specific task tab."""
    conn.update(worksheet=sheet_name, data=df)
    st.cache_data.clear()


# --- INITIALIZATION ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = fetch_master()

# --- SIDEBAR ---
with st.sidebar:
    st.title("📅 Planner")

    # Navigation
    # We map Task Names to their SheetNames for easy lookup
    task_map = dict(zip(st.session_state.master_df['Task'], st.session_state.master_df['SheetName']))

    options = ["Dashboard"] + list(st.session_state.master_df['Task'])
    selected_page = st.radio("Go to:", options)

    st.divider()

    # Add Task Logic
    with st.expander("Add New Task"):
        new_task_name = st.text_input("Task Name")
        if st.button("Create Task"):
            if new_task_name:
                with st.spinner("Creating new tab in Google Sheets..."):
                    # 1. Generate ID and unique Sheet Name
                    current_ids = pd.to_numeric(st.session_state.master_df['ID'], errors='coerce').fillna(0)
                    next_id = int(current_ids.max()) + 1
                    new_sheet_name = f"Task_{next_id}"

                    # 2. Add to Master DataFrame
                    new_row = pd.DataFrame([{
                        "ID": next_id,
                        "Task": new_task_name,
                        "Status": "Not Started",
                        "Deadline": datetime.date.today().strftime("%Y-%m-%d"),
                        "Notes": "",
                        "Done": False,
                        "SheetName": new_sheet_name
                    }])
                    updated_master = pd.concat([st.session_state.master_df, new_row], ignore_index=True)
                    save_master(updated_master)
                    st.session_state.master_df = updated_master

                    # 3. Create the ACTUAL new tab in Google Sheets
                    # We do this by 'updating' a non-existent sheet, which forces creation
                    empty_template = pd.DataFrame(columns=["Item", "Cost", "Status", "Notes"])
                    save_task_details(new_sheet_name, empty_template)

                    st.success(f"Created task and tab '{new_sheet_name}'!")
                    st.rerun()

# --- DASHBOARD PAGE ---
if selected_page == "Dashboard":
    st.title("Project Overview")

    df = st.session_state.master_df

    # Metrics
    total = len(df)
    done_count = len(df[df['Done'] == True])
    progress = done_count / total if total > 0 else 0
    st.progress(progress)

    # Master Grid
    display_cols = ["ID", "Done", "Task", "Status", "Deadline", "Notes"]
    edited_df = st.data_editor(
        df[display_cols],
        column_config={
            "ID": None,
            "Done": st.column_config.CheckboxColumn("Done"),
            "Status": st.column_config.SelectboxColumn("Status", options=["Not Started", "In Progress", "Done"]),
            "Deadline": st.column_config.DateColumn("Deadline"),
            "Notes": st.column_config.TextColumn("Notes", width="large")
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key="master_grid"
    )

    if st.button("Save Dashboard"):
        # Merge changes back to master (preserving SheetName hidden col)
        df.update(edited_df)
        save_master(df)
        st.session_state.master_df = df
        st.success("Saved!")

# --- TASK DETAIL PAGE ---
else:
    task_name = selected_page
    # Lookup the specific sheet name (e.g., 'Task_5') for this task
    try:
        row = st.session_state.master_df[st.session_state.master_df['Task'] == task_name].iloc[0]
        sheet_name = row['SheetName']
    except IndexError:
        st.error("Task not found in Master list.")
        st.stop()

    st.header(f"📂 {task_name}")
    st.caption(f"Data stored in tab: {sheet_name}")

    # Fetch the specific tab data
    detail_df = fetch_task_details(sheet_name)

    # Column Adder
    with st.expander("Add Column"):
        new_col = st.text_input("Column Name")
        if st.button("Add"):
            if new_col and new_col not in detail_df.columns:
                detail_df[new_col] = ""
                save_task_details(sheet_name, detail_df)
                st.rerun()

    # The Editor for the specific tab
    edited_detail = st.data_editor(
        detail_df,
        num_rows="dynamic",
        use_container_width=True,
        key=f"editor_{sheet_name}"
    )

    if st.button(f"Save '{task_name}'"):
        save_task_details(sheet_name, edited_detail)
        st.success(f"Saved to tab {sheet_name}!")