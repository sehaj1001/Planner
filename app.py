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
    .stButton>button { width: 100%; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)


# --- HELPER FUNCTIONS ---

def fetch_master():
    """Fetches the Master list with strict type handling."""
    try:
        df = conn.read(worksheet="Master", ttl=0)

        # Ensure all required columns exist
        required_cols = ["ID", "Task", "Status", "Deadline", "Notes", "Done", "SheetName"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""

        # Force ID to be numeric, turning errors (like empty strings) into NaN
        df['ID'] = pd.to_numeric(df['ID'], errors='coerce')

        # Remove any rows where Task is completely empty (cleanup)
        df = df[df['Task'].str.strip() != ""]

        return df
    except Exception:
        # Return clean empty dataframe if reading fails
        return pd.DataFrame(columns=["ID", "Task", "Status", "Deadline", "Notes", "Done", "SheetName"])


def save_master(df):
    conn.update(worksheet="Master", data=df)
    st.cache_data.clear()


def fetch_task_details(sheet_name):
    try:
        return conn.read(worksheet=sheet_name, ttl=0)
    except:
        return pd.DataFrame(columns=["Item", "Cost", "Status", "Notes"])


def save_task_details(sheet_name, df):
    conn.update(worksheet=sheet_name, data=df)
    st.cache_data.clear()


def create_new_sheet_if_needed(df):
    """Scans the dataframe for new rows (missing IDs) and creates sheets for them."""

    # 1. Find the next available ID
    if df['ID'].dropna().empty:
        next_id = 1
    else:
        next_id = int(df['ID'].max()) + 1

    changes_made = False

    # 2. Iterate through rows that have no ID (New Rows)
    for index, row in df.iterrows():
        if pd.isna(row['ID']) or row['ID'] == "":

            # Generate Metadata
            current_id = next_id
            sheet_name = f"Task_{current_id}"

            # Update the DataFrame row in memory
            df.at[index, 'ID'] = current_id
            df.at[index, 'SheetName'] = sheet_name
            # Set defaults if user didn't fill them
            if pd.isna(row['Deadline']) or row['Deadline'] == "":
                df.at[index, 'Deadline'] = datetime.date.today().strftime("%Y-%m-%d")
            if pd.isna(row['Status']) or row['Status'] == "":
                df.at[index, 'Status'] = "Not Started"

            # Create the actual Google Sheet Tab
            try:
                empty_template = pd.DataFrame(columns=["Item", "Cost", "Status", "Notes"])
                save_task_details(sheet_name, empty_template)
                st.toast(f"✨ Created new workspace: {sheet_name}")
            except Exception as e:
                st.error(f"Could not create tab for {row['Task']}: {e}")

            next_id += 1
            changes_made = True

    return df, changes_made


# --- INITIALIZATION ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = fetch_master()

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.title("📅 Planner")

    # Refresh logic to ensure sidebar names update
    task_list = st.session_state.master_df.dropna(subset=['Task'])
    options = ["Dashboard"] + task_list['Task'].tolist()

    selected_page = st.radio("Go to:", options)

    st.markdown("---")
    if st.button("🔄 Refresh Data"):
        st.session_state.master_df = fetch_master()
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

    # --- THE MAIN EDITOR ---
    # We allow adding rows here. ID and SheetName are hidden.
    edited_df = st.data_editor(
        df,
        column_config={
            "ID": None,  # Hidden
            "SheetName": None,  # Hidden
            "Done": st.column_config.CheckboxColumn("Done"),
            "Status": st.column_config.SelectboxColumn("Status",
                                                       options=["Not Started", "In Progress", "Blocked", "Done"],
                                                       required=True),
            "Deadline": st.column_config.DateColumn("Deadline"),
            "Notes": st.column_config.TextColumn("Notes", width="large"),
            "Task": st.column_config.TextColumn("Task", required=True)
        },
        num_rows="dynamic",  # <--- This enables the 'Add Row' button in the table
        use_container_width=True,
        hide_index=True,
        key="master_editor"
    )

    # --- SAVE & PROCESS BUTTON ---
    # We use a button to trigger the "Creation" logic.
    # This prevents the app from crashing while you are halfway through typing a task name.
    if st.button("Sync & Save Changes", type="primary"):
        # 1. Process new rows (assign IDs, create sheets)
        processed_df, new_sheets_created = create_new_sheet_if_needed(edited_df)

        # 2. Save to Google Sheets
        save_master(processed_df)

        # 3. Update Session State
        st.session_state.master_df = processed_df

        if new_sheets_created:
            st.success("Saved changes and created new task tabs!")
            st.rerun()  # Rerun to update the sidebar list
        else:
            st.success("Saved successfully!")

# --- TASK DETAIL PAGE ---
else:
    task_name = selected_page
    # Find the row corresponding to this task name
    # We assume unique task names for simplicity in finding the ID
    row = st.session_state.master_df[st.session_state.master_df['Task'] == task_name]

    if row.empty:
        st.error("Task not found.")
    else:
        row = row.iloc[0]
        sheet_name = row['SheetName']

        col1, col2 = st.columns([6, 1])
        with col1:
            st.header(f"📂 {task_name}")
            st.caption(f"Linked to Sheet: {sheet_name}")
        with col2:
            if st.button("Delete Task", type="primary"):
                # Drop from master
                st.session_state.master_df = st.session_state.master_df[st.session_state.master_df['ID'] != row['ID']]
                save_master(st.session_state.master_df)
                st.rerun()

        # Fetch Details
        detail_df = fetch_task_details(sheet_name)

        # Quick Column Adder
        with st.expander("Add Column"):
            new_col = st.text_input("New Column Name")
            if st.button("Add"):
                if new_col and new_col not in detail_df.columns:
                    detail_df[new_col] = ""
                    save_task_details(sheet_name, detail_df)
                    st.rerun()

        # Detail Editor
        edited_detail = st.data_editor(
            detail_df,
            num_rows="dynamic",
            use_container_width=True,
            key=f"editor_{sheet_name}"
        )

        if st.button(f"Save '{task_name}' Details"):
            save_task_details(sheet_name, edited_detail)
            st.success("Saved!")