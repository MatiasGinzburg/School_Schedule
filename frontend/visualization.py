import streamlit as st
import pandas as pd
from backend.control import find_swap_by_course, find_swap_by_professor
from backend.exporter import export_schedule_to_excel_bytes, export_professor_schedules_to_bytes

# --- DATA TRANSFORMATION ---

def build_course_dataframe(course: str, schedule: dict, data: dict) -> pd.DataFrame:
    """Builds the display dataframe for a selected course."""
    days = data['days']
    hours = data['hours']
    grid_data = {}
    
    for d in days:
        day_col = []
        for h in hours:
            prof_or_alias = schedule.get(course, {}).get(d, {}).get(h)
            if prof_or_alias:
                subj = data.get('subject_map', {}).get((course, prof_or_alias), prof_or_alias)
                day_col.append(str(subj))
            else:
                day_col.append("---")
        grid_data[d] = day_col
        
    return pd.DataFrame(grid_data, index=hours)

def build_professor_dataframe(prof: str, schedule: dict, data: dict) -> pd.DataFrame:
    """Builds the display dataframe for a selected professor."""
    days = data['days']
    hours = data['hours']
    grid_data = {}
    
    for d in days:
        day_col = []
        for h in hours:
            assigned_subjects = []
            for c in data['courses']:
                scheduled_entity = schedule.get(c, {}).get(d, {}).get(h)
                if scheduled_entity:
                    active_profs = [x.strip() for x in str(scheduled_entity).split(',')]
                    if str(prof) in active_profs:
                        subj = data.get('subject_map', {}).get((c, scheduled_entity), scheduled_entity)
                        if subj not in assigned_subjects:
                            assigned_subjects.append(str(subj))
                            
            cell_val = ", ".join(assigned_subjects) if assigned_subjects else "---"
            day_col.append(cell_val)
        grid_data[d] = day_col
        
    return pd.DataFrame(grid_data, index=hours)


# --- STATE & LOGIC ---

def init_swap_state(active_entity: str, edit_mode: bool):
    """Initializes and resets the Streamlit session state for the edit mode."""
    if 'prev_edit_mode' not in st.session_state:
        st.session_state.prev_edit_mode = False
        
    if edit_mode and not st.session_state.prev_edit_mode:
        st.session_state.swap_source = None
        st.session_state.swap_target = None
        st.session_state.valid_swaps = []
        st.session_state.active_box = "Box 1 (Subject to Move)"
        
    st.session_state.prev_edit_mode = edit_mode

    if 'swap_source' not in st.session_state: st.session_state.swap_source = None
    if 'swap_target' not in st.session_state: st.session_state.swap_target = None
    if 'valid_swaps' not in st.session_state: st.session_state.valid_swaps = []
    if 'active_box' not in st.session_state: st.session_state.active_box = "Box 1 (Subject to Move)"
    
    # Reset if the active course/professor changes
    if 'prev_entity' not in st.session_state or st.session_state.prev_entity != active_entity:
        st.session_state.swap_source = None
        st.session_state.swap_target = None
        st.session_state.valid_swaps = []
        st.session_state.active_box = "Box 1 (Subject to Move)"
        st.session_state.prev_entity = active_entity

def execute_schedule_swap(schedule: dict, data: dict):
    """Executes the swap for the active entity, updates exports, and resets the UI state."""
    day1, hour1 = st.session_state.swap_source
    day2, hour2 = st.session_state.swap_target
    entity = st.session_state.prev_entity
    
    if entity.startswith("COURSE_"):
        course = entity.replace("COURSE_", "")
        prof1 = schedule[course][day1][hour1]
        prof2 = schedule[course][day2][hour2]
        
        schedule[course][day1][hour1] = prof2
        schedule[course][day2][hour2] = prof1

    elif entity.startswith("PROF_"):
        prof = entity.replace("PROF_", "")
        
        def get_course_for_prof(p, d, h):
            for c in data['courses']:
                scheduled_entity = schedule.get(c, {}).get(d, {}).get(h)
                if scheduled_entity:
                    active_profs = [x.strip() for x in str(scheduled_entity).split(',')]
                    if str(p) in active_profs:
                        return c
            return None

        c_target = get_course_for_prof(prof, day1, hour1)
        c_candidate = get_course_for_prof(prof, day2, hour2)
        
        # A professor's swap might involve swapping classes for two entirely different courses.
        if c_target:
            p1 = schedule[c_target][day1][hour1]
            p2 = schedule[c_target][day2][hour2]
            schedule[c_target][day1][hour1] = p2
            schedule[c_target][day2][hour2] = p1
            
        if c_candidate and c_candidate != c_target:
            p1 = schedule[c_candidate][day1][hour1]
            p2 = schedule[c_candidate][day2][hour2]
            schedule[c_candidate][day1][hour1] = p2
            schedule[c_candidate][day2][hour2] = p1

    # Update session and re-export
    st.session_state.schedule = schedule
    st.session_state.master_bytes = export_schedule_to_excel_bytes(schedule, data)
    st.session_state.prof_bytes = export_professor_schedules_to_bytes(schedule, data)
    
    # Reset UI
    st.session_state.swap_source = None
    st.session_state.swap_target = None
    st.session_state.valid_swaps = []
    st.session_state.active_box = "Box 1 (Subject to Move)"
    st.rerun()


# --- UI COMPONENTS ---

def apply_emoji_highlights(df: pd.DataFrame) -> pd.DataFrame:
    """Injects emoji markers into the dataframe cells based on current state."""
    display_df = df.copy()
    
    if st.session_state.valid_swaps:
        for (d, h) in st.session_state.valid_swaps:
            display_df.at[h, d] = "🟢 " + str(display_df.at[h, d])
            
    if st.session_state.swap_source:
        d, h = st.session_state.swap_source
        display_df.at[h, d] = "🟠 " + str(df.at[h, d])
        
    if st.session_state.swap_target:
        d, h = st.session_state.swap_target
        display_df.at[h, d] = "🟡 " + str(df.at[h, d])
        
    return display_df

def render_edit_controls(schedule: dict, data: dict):
    """Renders the radio toggles, text boxes, and execution button."""
    st.info("👆 Use the toggle below to choose which box to fill, then click a cell in the table.")
    
    box_options = ["Box 1 (Subject to Move)", "Box 2 (Destination)"]
    current_idx = box_options.index(st.session_state.active_box) if st.session_state.active_box in box_options else 0
    
    selected_box = st.radio(
        "Currently Selecting For:", 
        options=box_options, 
        horizontal=True, 
        index=current_idx
    )
    
    if selected_box != st.session_state.active_box:
        st.session_state.active_box = selected_box
        st.rerun()

    box_col1, box_col2, box_col3 = st.columns([2, 2, 1])
    
    val1 = f"{st.session_state.swap_source[0]} {st.session_state.swap_source[1]}" if st.session_state.swap_source else ""
    val2 = f"{st.session_state.swap_target[0]} {st.session_state.swap_target[1]}" if st.session_state.swap_target else ""
    
    with box_col1:
        st.text_input("Swap (Box 1) 🟠:", value=val1, disabled=True)
    with box_col2:
        st.text_input("With (Box 2) 🟡:", value=val2, disabled=True)
    with box_col3:
        st.write(" ")
        st.write(" ")
        if st.button("Swap", type="primary", disabled=not (st.session_state.swap_source and st.session_state.swap_target)):
            execute_schedule_swap(schedule, data)

def handle_grid_interaction(event, df: pd.DataFrame, schedule: dict, data: dict, active_course: str = None, active_prof: str = None):
    """Processes dataframe clicks for both Course and Professor views."""
    selections = event.get("selection", {})
    selected_cells = selections.get("cells", [])
    
    if selected_cells and len(selected_cells) > 0:
        first_cell = selected_cells[0]
        row_idx = int(first_cell[0])
        clicked_day = str(first_cell[1])
        clicked_hour = df.index[row_idx]
        
        needs_rerun = False
        
        # Target BOX 1
        if "Box 1" in st.session_state.active_box:
            if st.session_state.swap_source != (clicked_day, clicked_hour):
                st.session_state.swap_source = (clicked_day, clicked_hour)
                st.session_state.swap_target = None 
                
                # Route to the correct backend function based on view
                if active_course:
                    st.session_state.valid_swaps = find_swap_by_course(active_course, clicked_day, clicked_hour, data, schedule)
                elif active_prof:
                    st.session_state.valid_swaps = find_swap_by_professor(active_prof, clicked_day, clicked_hour, data, schedule)
                
                if not st.session_state.valid_swaps:
                    st.warning("No easily swappable timeslots found for this assignment.")
                else:
                    st.session_state.active_box = "Box 2 (Destination)"
                    
                needs_rerun = True

        # Target BOX 2
        else:
            if st.session_state.swap_target != (clicked_day, clicked_hour):
                if (clicked_day, clicked_hour) in st.session_state.valid_swaps:
                    st.session_state.swap_target = (clicked_day, clicked_hour)
                    needs_rerun = True
                else:
                    if not st.session_state.swap_source:
                        st.warning("Please assign a subject to Box 1 first.")
                    else:
                        st.warning("That timeslot is not a valid swap. All constraints must be met.")
                
        if needs_rerun:
            st.rerun()


# --- MAIN EXPORT ---

def render_schedule_visualizer(schedule: dict, data: dict):
    """Main entry point for the UI visualizer."""
    st.divider()
    st.subheader("👀 Schedule Visualizer")
    
    view_type = st.radio("View schedule by:", options=["Course", "Professor"], horizontal=True)
    
    if view_type == "Course":
        courses = data['courses']
        
        col1, col2 = st.columns([3, 1])
        with col1:
            selected_course = st.selectbox("Select a Course:", options=courses)
        with col2:
            st.write(" ")
            st.write(" ")
            edit_mode = st.toggle("✏️ Edit Mode", help="Click a cell in the table to swap it.", key="edit_toggle_course")

        if selected_course:
            init_swap_state(f"COURSE_{selected_course}", edit_mode)
            df_course = build_course_dataframe(selected_course, schedule, data)
            
            if edit_mode:
                render_edit_controls(schedule, data)
                display_df = apply_emoji_highlights(df_course)
                
                event = st.dataframe(
                    display_df,
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode=["single-cell", "single-column"],
                    key="course_grid_select"
                )
                handle_grid_interaction(event, df_course, schedule, data, active_course=selected_course)
            else:
                st.dataframe(df_course, use_container_width=True, on_select="rerun", selection_mode="single-column")

    elif view_type == "Professor":
        real_profs = [p for p in data['professors'] if not str(p).startswith("free_hour_")]
        
        col1, col2 = st.columns([3, 1])
        with col1:
            selected_prof = st.selectbox("Select a Professor:", options=real_profs)
        with col2:
            st.write(" ")
            st.write(" ")
            edit_mode = st.toggle("✏️ Edit Mode", help="Click a cell in the table to swap it.", key="edit_toggle_prof")
        
        if selected_prof:
            init_swap_state(f"PROF_{selected_prof}", edit_mode)
            df_prof = build_professor_dataframe(selected_prof, schedule, data)
            
            if edit_mode:
                render_edit_controls(schedule, data)
                display_df = apply_emoji_highlights(df_prof)
                
                event = st.dataframe(
                    display_df,
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode=["single-cell", "single-column"],
                    key="prof_grid_select"
                )
                handle_grid_interaction(event, df_prof, schedule, data, active_prof=selected_prof)
            else:
                st.dataframe(df_prof, use_container_width=True, on_select="rerun", selection_mode="single-column")