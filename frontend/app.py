import streamlit as st
import sys
from pathlib import Path

# Add backend to path so we can import it
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.data_loader import load_and_validate_data
from backend.optimizer import solve_schedule
from backend.control import verify_schedule, pre_optimization_checks
from backend.exporter import export_schedule_to_excel_bytes, export_professor_schedules_to_bytes
from frontend.visualization import render_schedule_visualizer

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
if 'data_info' not in st.session_state:
    st.session_state.data_info = None

# --- UI: Configuration Sidebar ---
st.sidebar.header("⚙️ Solver Configuration")

# Updated: Multiselect returns a list in the order items are clicked, handling the new prioritization logic
st.sidebar.subheader("🎯 Optimization Goals")
cost_options = st.sidebar.multiselect(
    "Select and prioritize goals (First selected = Highest Priority):",
    options=["minimize_prof_days", "minimize_prof_gaps"],
    format_func=lambda x: "📅 Minimize Professor Days" if x == "minimize_prof_days" else "⏱️ Minimize Empty Gaps",
    default=[]
)

# Fallback to feasibility if the list is empty
if not cost_options:
    cost_options = ["pure_feasibility"]
    st.sidebar.info("⚡ Fast Feasibility (Any valid schedule) is active.")

st.sidebar.subheader("🔒 Constraints")
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
    
    # --- UI Layout Magic --- 
    # Create structural placeholders to strictly control the UI rendering order. 
    data_info_placeholder = st.empty()     # 1. "Data loaded successfully..." 
    spinner_placeholder = st.empty()       # 2. "Analyzing data..." 
    results_container = st.container()     # 3. Visualizer and Downloads 
    logs_container = st.container()        # 4. Warnings, errors, and logs 
    
    if st.button("Generate Schedule", type="primary"):
        with spinner_placeholder:
            with st.spinner("Analyzing data and running optimization..."):
                try:
                    # 1. Load Data
                    data = load_and_validate_data(uploaded_file)
                    info_msg = f"Data loaded successfully: {len(data['courses'])} courses and {len(data['professors'])} professors detected."
                    
                    st.session_state.data_info = info_msg
                    data_info_placeholder.info(info_msg)

                    # Run Pre-Optimization Checks
                    is_feasible, errors, warnings = pre_optimization_checks(data, margin=1.3) 
                    
                    # Send warnings and errors to slot #4 
                    with logs_container:
                        for w in warnings:
                            st.warning(w)
                        for e in errors:
                            st.error(e)
                        
                        if not is_feasible:
                            st.error("Pre-optimization checks failed. The schedule is mathematically impossible. Please fix the grid constraints above and try again.")
                            st.session_state.schedule_generated = False
                        else:
                            st.success("Pre-checks passed. Inputs are theoretically feasible. Running solver...")
                            
                            # 2. Solve Schedule
                            schedule = solve_schedule(
                                data=data, 
                                cost_function=cost_options,  # Now passing the list of strings
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
                                    st.session_state.schedule = schedule
                                    st.session_state.data = data
                                else:
                                    st.error("Schedule verification failed. Constraints were violated.")
                                    st.session_state.schedule_generated = False
                                    
                except Exception as e:
                    with logs_container:
                        st.error(f"An error occurred: {e}")
                    st.session_state.schedule_generated = False

    # --- UI: Render Results ---
    if st.session_state.schedule_generated and st.session_state.data_info:
        data_info_placeholder.info(st.session_state.data_info)

    if st.session_state.schedule_generated:
        with results_container:
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
                
            if 'schedule' in st.session_state and 'data' in st.session_state:
                render_schedule_visualizer(st.session_state.schedule, st.session_state.data)

else:
    st.session_state.schedule_generated = False
    st.session_state.master_bytes = None
    st.session_state.prof_bytes = None
    st.session_state.data_info = None