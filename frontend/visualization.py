# frontend/visualization.py

import streamlit as st
import pandas as pd
from backend.control import (
    find_simple_swaps_by_course, 
    find_simple_swaps_by_professor, 
    verify_schedule
)
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
        st.session_state.active_swap_course = None
        
    st.session_state.prev_edit_mode = edit_mode

    if 'swap_source' not in st.session_state: st.session_state.swap_source = None
    if 'swap_target' not in st.session_state: st.session_state.swap_target = None
    if 'valid_swaps' not in st.session_state: st.session_state.valid_swaps = []
    if 'active_box' not in st.session_state: st.session_state.active_box = "Box 1 (Subject to Move)"
    if 'active_swap_course' not in st.session_state: st.session_state.active_swap_course = None
    
    # Reset if the active course/professor changes
    if 'prev_entity' not in st.session_state or st.session_state.prev_entity != active_entity:
        st.session_state.swap_source = None
        st.session_state.swap_target = None
        st.session_state.valid_swaps = []
        st.session_state.active_box = "Box 1 (Subject to Move)"
        st.session_state.active_swap_course = None
        st.session_state.prev_entity = active_entity

def get_linked_courses(prof_str: str, day: str, hour: str, schedule: dict, data: dict) -> list:
    """Finds all courses that share this exact assignment (handles joint/alias classes)."""
    if not prof_str: 
        return []
    linked = []
    for c in data['courses']:
        if schedule.get(c, {}).get(day, {}).get(hour) == prof_str:
            linked.append(c)
    return linked

def get_swap_moves(day1: str, hour1: str, day2: str, hour2: str, entity: str, schedule: dict, data: dict) -> list:
    """
    Identifies all intertwined courses involved in a swap, including double swaps 
    where shared professors cross the diagonal of the exchange.
    """
    courses_to_swap = set()
    
    # 1. Identify the base courses initiating the swap
    if entity.startswith("COURSE_"):
        c = entity.replace("COURSE_", "")
        courses_to_swap.add(c)
    elif entity.startswith("PROF_"):
        p = entity.replace("PROF_", "")
        c1 = get_course_for_professor_slot(p, day1, hour1, schedule, data)
        c2 = get_course_for_professor_slot(p, day2, hour2, schedule, data)
        if c1: courses_to_swap.add(c1)
        if c2: courses_to_swap.add(c2)
        
    # 2. Expand mathematically to include joint-classes AND double-swaps
    expanded = True
    while expanded:
        expanded = False
        current_courses = list(courses_to_swap)
        for c in current_courses:
            p1_str = schedule.get(c, {}).get(day1, {}).get(hour1)
            p2_str = schedule.get(c, {}).get(day2, {}).get(hour2)
            
            # 2a. Joint Classes
            linked1 = get_linked_courses(p1_str, day1, hour1, schedule, data) if p1_str else []
            linked2 = get_linked_courses(p2_str, day2, hour2, schedule, data) if p2_str else []
            
            for lc in linked1 + linked2:
                if lc not in courses_to_swap:
                    courses_to_swap.add(lc)
                    expanded = True
                    
            # 2b. Double Swaps (Prof from Slot 1 is already busy in another course at Slot 2)
            if p1_str:
                profs1 = [p.strip() for p in p1_str.split(',')]
                for other_c in data['courses']:
                    other_p2_str = schedule.get(other_c, {}).get(day2, {}).get(hour2)
                    if other_p2_str:
                        other_profs2 = [p.strip() for p in other_p2_str.split(',')]
                        if any(p in other_profs2 for p in profs1):
                            if other_c not in courses_to_swap:
                                courses_to_swap.add(other_c)
                                expanded = True

            # 2c. Double Swaps (Prof from Slot 2 is already busy in another course at Slot 1)
            if p2_str:
                profs2 = [p.strip() for p in p2_str.split(',')]
                for other_c in data['courses']:
                    other_p1_str = schedule.get(other_c, {}).get(day1, {}).get(hour1)
                    if other_p1_str:
                        other_profs1 = [p.strip() for p in other_p1_str.split(',')]
                        if any(p in other_profs1 for p in profs2):
                            if other_c not in courses_to_swap:
                                courses_to_swap.add(other_c)
                                expanded = True

    moves = []
    # 3. Create the move blocks for Day 1 going to Day 2
    processed_c_d1 = set()
    for c in courses_to_swap:
        if c in processed_c_d1: continue
        p1 = schedule.get(c, {}).get(day1, {}).get(hour1)
        linked = get_linked_courses(p1, day1, hour1, schedule, data) if p1 else [c]
        moves.append((p1, linked, day1, hour1, day2, hour2))
        for lc in linked: processed_c_d1.add(lc)
        
    # 4. Create the move blocks for Day 2 going to Day 1
    processed_c_d2 = set()
    for c in courses_to_swap:
        if c in processed_c_d2: continue
        p2 = schedule.get(c, {}).get(day2, {}).get(hour2)
        linked = get_linked_courses(p2, day2, hour2, schedule, data) if p2 else [c]
        moves.append((p2, linked, day2, hour2, day1, hour1))
        for lc in linked: processed_c_d2.add(lc)
        
    return moves

def execute_schedule_swap(schedule: dict, data: dict, moves: list):
    """Executes the swap safely by gathering all new states before overwriting."""
    new_states = []
    for prof_str, linked, src_d, src_h, dst_d, dst_h in moves:
        for c in linked:
            new_states.append((c, dst_d, dst_h, prof_str))
            
    # Apply all simultaneous moves
    for c, d, h, prof_str in new_states:
        schedule[c][d][h] = prof_str

    # This guarantees the swap didn't violate constraints like double-booking or contiguous free hours
    if not verify_schedule(schedule, data):
        st.error("Fatal Logic Error: This swap broke the schedule constraints! Check the terminal logs.")
        st.stop()  # Halts execution so the corrupted schedule isn't saved

    # Update session and re-export
    st.session_state.schedule = schedule
    st.session_state.master_bytes = export_schedule_to_excel_bytes(schedule, data)
    st.session_state.prof_bytes = export_professor_schedules_to_bytes(schedule, data)
    
    # Reset UI
    st.session_state.swap_source = None
    st.session_state.swap_target = None
    st.session_state.valid_swaps = []
    st.session_state.active_box = "Box 1 (Subject to Move)"
    st.session_state.active_swap_course = None
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

def get_course_for_professor_slot(prof: str, day: str, hour: str, schedule: dict, data: dict):
    """Helper to figure out which course a professor is teaching at a given slot."""
    for c in data['courses']:
        scheduled_entity = schedule.get(c, {}).get(day, {}).get(hour)
        if scheduled_entity:
            active_profs = [x.strip() for x in str(scheduled_entity).split(',')]
            if str(prof) in active_profs:
                return c
    return None

@st.dialog("⚠️ Confirm Swap Details")
def confirm_swap_dialog(schedule: dict, data: dict):
    """A popup that details exactly what subjects are moving across all affected courses."""
    day1, hour1 = st.session_state.swap_source
    day2, hour2 = st.session_state.swap_target
    entity = st.session_state.prev_entity
    
    moves = get_swap_moves(day1, hour1, day2, hour2, entity, schedule, data)
    
    st.write("### You are about to make the following changes:")
    
    def format_move(prof_str, linked_courses, source_day, source_hour, dest_day, dest_hour):
        if not prof_str or not linked_courses:
            return f"- **Empty Slot** is moved from `{source_day} {source_hour}` to `{dest_day} {dest_hour}`"
        
        subj_list = []
        for c in linked_courses:
            subj = data.get('subject_map', {}).get((c, prof_str), prof_str)
            if str(subj) not in subj_list:
                subj_list.append(str(subj))
                
        subjects_str = ", ".join(subj_list)
        courses_str = ", ".join(linked_courses)
        
        return f"- **{subjects_str}** ({prof_str}, {courses_str}) is moved from `{source_day} {source_hour}` to `{dest_day} {dest_hour}`"

    for move in moves:
        st.markdown(format_move(*move))
            
    st.warning("Do you want to proceed and update the schedule?")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Yes, Execute Swap", type="primary", use_container_width=True):
            execute_schedule_swap(schedule, data, moves)
    with col2:
        if st.button("❌ Cancel", use_container_width=True):
            st.rerun()

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
            confirm_swap_dialog(schedule, data)

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
                course_to_swap = active_course
                if active_prof:
                    course_to_swap = get_course_for_professor_slot(active_prof, clicked_day, clicked_hour, schedule, data)
                
                if course_to_swap:
                    st.session_state.swap_source = (clicked_day, clicked_hour)
                    st.session_state.swap_target = None 
                    st.session_state.active_swap_course = course_to_swap
                    
                    if active_course:
                        st.session_state.valid_swaps = (
                            find_simple_swaps_by_course(course_to_swap, clicked_day, clicked_hour, data, schedule)
                        )
                    elif active_prof:
                        st.session_state.valid_swaps = (
                            find_simple_swaps_by_professor(active_prof, clicked_day, clicked_hour, data, schedule)
                        )
                    
                    if not st.session_state.valid_swaps:
                        st.warning("No easily swappable timeslots found for this assignment.")
                    else:
                        st.session_state.active_box = "Box 2 (Destination)"
                        
                    needs_rerun = True
                else:
                    st.warning("Selected slot is empty. Please click an assigned class for Box 1.")

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
                st.dataframe(
                    df_course, 
                    use_container_width=True, 
                    on_select="ignore", 
                    selection_mode="single-column"
                )

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
                st.dataframe(
                    df_prof, 
                    use_container_width=True, 
                    on_select="ignore",
                    selection_mode="single-column"
                )