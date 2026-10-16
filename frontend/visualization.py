import streamlit as st
import pandas as pd
import plotly.graph_objects as go

def create_timetable_figure(df: pd.DataFrame, title: str):
    """Generates an interactive Plotly table from a pandas DataFrame."""
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=["<b>Hours</b>"] + [f"<b>{col}</b>" for col in df.columns],
            fill_color='#4A90E2',
            font=dict(color='white', size=14),
            align='center'
        ),
        cells=dict(
            values=[df.index] + [df[col] for col in df.columns],
            fill_color='#F4F6F9',
            font=dict(color='#333333', size=12),
            align='center',
            height=35
        )
    )])
    
    fig.update_layout(
        title=dict(text=title, font=dict(size=20), x=0.5),
        margin=dict(l=0, r=0, t=50, b=0),
        height=400 + (len(df) * 35) # Dynamically scale height based on hours
    )
    return fig

def render_schedule_visualizer(schedule: dict, data: dict):
    """Renders the Streamlit UI for selecting and visualizing schedules."""
    st.divider()
    st.subheader("👀 Schedule Visualizer")
    
    # 1. Choose perspective
    view_type = st.radio("View schedule by:", options=["Course", "Professor"], horizontal=True)
    
    days = data['days']
    hours = data['hours']
    
    if view_type == "Course":
        courses = data['courses']
        selected_course = st.selectbox("Select a Course:", options=courses)
        
        if selected_course:
            # Build DataFrame for the selected course
            grid_data = {}
            for d in days:
                day_col = []
                for h in hours:
                    # Fetch professor, default to "---" if empty
                    prof = schedule.get(selected_course, {}).get(d, {}).get(h, "---")
                    day_col.append(prof)
                grid_data[d] = day_col
                
            df_course = pd.DataFrame(grid_data, index=hours)
            
            # Render Plotly Table
            fig = create_timetable_figure(df_course, f"Weekly Schedule: Course {selected_course}")
            # Note: For future click interactivity, Streamlit's st.plotly_chart supports on_select
            st.plotly_chart(fig, use_container_width=True)

    elif view_type == "Professor":
        # Filter out dummy professors (free_hour_*)
        real_profs = [p for p in data['professors'] if not str(p).startswith("free_hour_")]
        selected_prof = st.selectbox("Select a Professor:", options=real_profs)
        
        if selected_prof:
            # Build DataFrame for the selected professor
            grid_data = {}
            for d in days:
                day_col = []
                for h in hours:
                    assigned_courses_list = []
                    for c in data['courses']:
                        prof_at_slot = schedule.get(c, {}).get(d, {}).get(h)
                        if prof_at_slot:
                            # Handle joint aliases by splitting strings (e.g., "ING7, ING4")
                            active_profs = [x.strip() for x in str(prof_at_slot).split(',')]
                            if str(selected_prof) in active_profs:
                                assigned_courses_list.append(str(c))
                                
                    cell_val = ", ".join(assigned_courses_list) if assigned_courses_list else "---"
                    day_col.append(cell_val)
                grid_data[d] = day_col
                
            df_prof = pd.DataFrame(grid_data, index=hours)
            
            # Render Plotly Table
            fig = create_timetable_figure(df_prof, f"Weekly Schedule: Professor {selected_prof}")
            st.plotly_chart(fig, use_container_width=True)