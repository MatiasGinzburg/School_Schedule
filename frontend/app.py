import streamlit as st
import sys
from pathlib import Path

# Add backend to path so we can import it
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.data_loader import load_and_validate_data
from backend.optimizer import solve_schedule
from backend.control import verify_schedule, pre_optimization_checks
from backend.exporter import export_schedule_to_excel_bytes, export_professor_schedules_to_bytes

st.set_page_config(page_title="School Scheduler V2", page_icon="📅", layout="wide")

st.title("📅 Automated School Scheduler (V2)")
st.write("Upload your consolidated `Horarios_SG.xlsx` file to generate an optimized, flexible schedule.")

# 1. Initialize session state to hold the generated files
if 'schedule_generated' not in st.session_state:
    st.session_state.schedule_generated = False
if 'master_bytes' not in st.session_state:
    st.session_state.master_bytes = None
if 'prof_bytes' not in st.session_state:
    st.session_state.prof_bytes = None

# --- UI: Configuration Sidebar ---
st.sidebar.header("⚙️ Solver Configuration")

cost_option = st.sidebar.radio(
    "Optimization Goal:",
    options=["pure_feasibility", "minimize_prof_days_and_gaps"],
    format_func=lambda x: "⚡ Fast Feasibility (Any valid schedule)" if x == "pure_feasibility" else "🎯 Minimize Days & Gaps (Optimal but slower)",
    index=0
)

force_contiguous = st.sidebar.checkbox(
    "Force Free Hours to End of Day", 
    value=True, 
    help="Pushes all unassigned optional slots (2) strictly to the end of the day."
)

# Build the active constraints list based on UI selections
selected_constraints = [
    "fulfill_req_hours", 
    "respect_course_availability", 
    "no_double_booking_and_prof_availability"
]
if force_contiguous:
    selected_constraints.append("force_free_hours_to_end")


# --- UI: Main Area ---
uploaded_file = st.file_uploader("Upload Schedule Data (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    st.success("File uploaded successfully!")
    
    if st.button("Generate Schedule", type="primary"):
        with st.spinner("Analyzing data and running optimization..."):
            try:
                # 1. Load Data
                data = load_and_validate_data(uploaded_file)
                st.info(f"Data loaded successfully: {len(data['courses'])} courses and {len(data['professors'])} professors detected.")

                # Run Pre-Optimization Checks
                is_feasible, errors, warnings = pre_optimization_checks(data, margin=1.3)
                
                # Display warnings in UI
                for w in warnings:
                    st.warning(w)
                    
                # Display errors in UI
                for e in errors:
                    st.error(e)
                
                # Stop execution if mathematically impossible
                if not is_feasible:
                    st.error("Pre-optimization checks failed. The schedule is mathematically impossible. Please fix the grid constraints above and try again.")
                    st.session_state.schedule_generated = False
                else:
                    st.success("Pre-checks passed. Inputs are theoretically feasible. Running solver...")
                    
                    # 2. Solve Schedule
                    schedule = solve_schedule(
                        data=data, 
                        cost_function=cost_option, 
                        active_constraints=selected_constraints
                    )

                # 2. Solve Schedule
                schedule = solve_schedule(
                    data=data, 
                    cost_function=cost_option, 
                    active_constraints=selected_constraints
                )
                
                if not schedule:
                    st.error("No mathematically valid schedule exists with the current constraints and availability grids.")
                    st.session_state.schedule_generated = False
                else:
                    # 3. Verify
                    is_valid = verify_schedule(schedule, data, active_constraints=selected_constraints)
                    
                    if is_valid:
                        st.success("✨ Optimal schedule generated and strictly verified!")
                        
                        # 4. Save the generated files into Streamlit's session state
                        st.session_state.master_bytes = export_schedule_to_excel_bytes(schedule, data)
                        st.session_state.prof_bytes = export_professor_schedules_to_bytes(schedule, data)
                        st.session_state.schedule_generated = True
                    else:
                        st.error("Schedule verification failed. Constraints were violated.")
                        st.session_state.schedule_generated = False
                        
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.session_state.schedule_generated = False

    # --- UI: Download Section ---
    # Display the download buttons OUTSIDE the Generate button's if-block
    if st.session_state.schedule_generated:
        st.write("### 📥 Download Your Schedules")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="Download Master Schedule",
                data=st.session_state.master_bytes,
                file_name="v2_master_schedule.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_master"
            )
        with col2:
            st.download_button(
                label="Download Professor Schedules",
                data=st.session_state.prof_bytes,
                file_name="v2_professor_schedules.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_prof"
            )
else:
    # Clear state if the user removes the uploaded file
    st.session_state.schedule_generated = False
    st.session_state.master_bytes = None
    st.session_state.prof_bytes = None