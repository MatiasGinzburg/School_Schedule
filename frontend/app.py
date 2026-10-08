import streamlit as st
import sys
from pathlib import Path

# Add backend to path so we can import it
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.data_loader import load_and_validate_data
from backend.optimizer import solve_schedule
from backend.control import verify_schedule
from backend.exporter import export_schedule_to_excel_bytes, export_professor_schedules_to_bytes

st.set_page_config(page_title="School Scheduler", page_icon="📅")

st.title("📅 Automated School Scheduler")
st.write("Upload your Excel spreadsheet containing professor availability and course requirements to generate an optimized schedule.")

# 1. Initialize session state to hold the generated files
if 'schedule_generated' not in st.session_state:
    st.session_state.schedule_generated = False
if 'master_bytes' not in st.session_state:
    st.session_state.master_bytes = None
if 'prof_bytes' not in st.session_state:
    st.session_state.prof_bytes = None

# File Uploader
uploaded_file = st.file_uploader("Upload Schedule Data (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    st.success("File uploaded successfully!")
    
    if st.button("Generate Schedule", type="primary"):
        with st.spinner("Analyzing data and running optimization..."):
            try:
                # Load Data
                data = load_and_validate_data(uploaded_file)
                st.info("Data validated successfully. Constraints look good.")
                
                # Solve Schedule
                schedule = solve_schedule(data)
                
                if not schedule:
                    st.error("No mathematically valid schedule exists with the current constraints.")
                    st.session_state.schedule_generated = False
                else:
                    # Verify
                    is_valid = verify_schedule(schedule, data)
                    
                    if is_valid:
                        st.success("✨ Optimal schedule generated and verified!")
                        
                        # Save the generated files into Streamlit's session state
                        st.session_state.master_bytes = export_schedule_to_excel_bytes(schedule, data)
                        st.session_state.prof_bytes = export_professor_schedules_to_bytes(schedule, data)
                        st.session_state.schedule_generated = True
                    else:
                        st.error("Schedule verification failed. Please check the logs.")
                        st.session_state.schedule_generated = False
                        
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.session_state.schedule_generated = False

    # 2. Display the download buttons OUTSIDE the Generate button's if-block
    if st.session_state.schedule_generated:
        st.write("### Download Your Schedules")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="📥 Download Master Schedule",
                data=st.session_state.master_bytes,
                file_name="master_schedule.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_master"
            )
        with col2:
            st.download_button(
                label="📥 Download Professor Schedules",
                data=st.session_state.prof_bytes,
                file_name="professor_schedules.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_prof"
            )
else:
    # Clear state if the user removes the uploaded file
    st.session_state.schedule_generated = False
    st.session_state.master_bytes = None
    st.session_state.prof_bytes = None