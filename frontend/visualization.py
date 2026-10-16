import streamlit as st
import pandas as pd
import plotly.graph_objects as go

def create_timetable_figure(df: pd.DataFrame, title: str):
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
        height=400 + (len(df) * 35)
    )
    return fig

def render_schedule_visualizer(schedule: dict, data: dict):
    st.divider()
    st.subheader("👀 Schedule Visualizer")
    
    view_type = st.radio("View schedule by:", options=["Course", "Professor"], horizontal=True)
    
    days = data['days']
    hours = data['hours']
    
    if view_type == "Course":
        courses = data['courses']
        selected_course = st.selectbox("Select a Course:", options=courses)
        
        if selected_course:
            grid_data = {}
            for d in days:
                day_col = []
                for h in hours:
                    prof_or_alias = schedule.get(selected_course, {}).get(d, {}).get(h)
                    if prof_or_alias:
                        # Direct tuple lookup
                        subj = data.get('subject_map', {}).get((selected_course, prof_or_alias), prof_or_alias)
                        day_col.append(str(subj))
                    else:
                        day_col.append("---")
                grid_data[d] = day_col
                
            df_course = pd.DataFrame(grid_data, index=hours)
            fig = create_timetable_figure(df_course, f"Weekly Schedule: Course {selected_course}")
            st.plotly_chart(fig, use_container_width=True)

    elif view_type == "Professor":
        real_profs = [p for p in data['professors'] if not str(p).startswith("free_hour_")]
        selected_prof = st.selectbox("Select a Professor:", options=real_profs)
        
        if selected_prof:
            grid_data = {}
            for d in days:
                day_col = []
                for h in hours:
                    assigned_subjects = []
                    for c in data['courses']:
                        scheduled_entity = schedule.get(c, {}).get(d, {}).get(h)
                        if scheduled_entity:
                            active_profs = [x.strip() for x in str(scheduled_entity).split(',')]
                            if str(selected_prof) in active_profs:
                                subj = data.get('subject_map', {}).get((c, scheduled_entity), scheduled_entity)
                                if subj not in assigned_subjects:
                                    assigned_subjects.append(str(subj))
                                    
                    cell_val = ", ".join(assigned_subjects) if assigned_subjects else "---"
                    day_col.append(cell_val)
                grid_data[d] = day_col
                
            df_prof = pd.DataFrame(grid_data, index=hours)
            fig = create_timetable_figure(df_prof, f"Weekly Schedule: Professor {selected_prof}")
            st.plotly_chart(fig, use_container_width=True)