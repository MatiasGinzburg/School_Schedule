import pandas as pd
import io
import logging

logger = logging.getLogger(__name__)

def export_schedule_to_excel_bytes(schedule: dict, data: dict) -> bytes:
    """
    Exports the master schedule to an in-memory Excel file.
    Rows are courses, columns are hours, tabs are days.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for day in data['days']:
            day_data = {}
            for h in data['hours']:
                hour_column = []
                for c in data['courses']:
                    prof = schedule.get(c, {}).get(day, {}).get(h)
                    state = data.get('course_availability', {}).get(c, {}).get(day, {}).get(h, 0)
                    
                    if prof:
                        val = prof # Handles both individual ("P1") and joint strings ("P1, P2")
                    elif state == 0:
                        val = "---" # Closed / Not at school
                    elif state == 2:
                        val = "FREE" # Optional slot intentionally left empty
                    else:
                        val = "UNASSIGNED / ERROR"
                        
                    hour_column.append(val)
                day_data[h] = hour_column
                
            df_day = pd.DataFrame(day_data, index=data['courses'])
            df_day.index.name = "Courses"
            df_day.to_excel(writer, sheet_name=day)
            
    return output.getvalue()

def export_schedule_to_excel_bytes_(schedule: dict, data: dict) -> bytes:
    """
    Exports the master schedule to an in-memory Excel file.
    Rows are courses, columns are hours, tabs are days.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for day in data['days']:
            day_data = {}
            for h in data['hours']:
                hour_column = []
                for c in data['courses']:
                    prof = schedule.get(c, {}).get(day, {}).get(h)
                    state = data['course_availability'].get(c, {}).get(day, {}).get(h, 0)
                    
                    if prof:
                        val = prof
                    elif state == 0:
                        val = "---" # Closed / Not at school
                    elif state == 2:
                        val = "FREE" # Optional slot intentionally left empty
                    else:
                        val = "UNASSIGNED / ERROR"
                        
                    hour_column.append(val)
                day_data[h] = hour_column
                
            df_day = pd.DataFrame(day_data, index=data['courses'])
            df_day.index.name = "Courses"
            df_day.to_excel(writer, sheet_name=day)
            
    return output.getvalue()
def export_professor_schedules_to_bytes(schedule: dict, data: dict) -> bytes:
    """
    Exports the individual professor schedules to an in-memory Excel file.
    Rows are hours, columns are days, tabs are professors.
    Handles joint aliases by merging multi-course assignments natively.
    """
    output = io.BytesIO()
    
    # Filter out any injected dummy 'free_hour' variables so they don't get a tab
    real_profs = [p for p in data['professors'] if not str(p).startswith("free_hour_")]
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for p in real_profs:
            prof_data = {}
            for d in data['days']:
                day_column = []
                for h in data['hours']:
                    assigned_courses_list = []
                    
                    for c in data['courses']:
                        assigned_prof = schedule.get(c, {}).get(d, {}).get(h)
                        if assigned_prof:
                            # Split string in case it's a joint alias (e.g., "ING7, ING4")
                            active_profs = [x.strip() for x in str(assigned_prof).split(',')]
                            
                            # If this specific human professor is part of the assignment, append the course
                            if str(p) in active_profs:
                                assigned_courses_list.append(str(c))
                                
                    # Join multiple courses if they are co-teaching a joint class (e.g., "3A, 2A")
                    assigned_course = ", ".join(assigned_courses_list)
                    day_column.append(assigned_course)
                    
                prof_data[d] = day_column
            
            df_prof = pd.DataFrame(prof_data, index=data['hours'])
            df_prof.index.name = "Hours"
            
            # Excel limits sheet names to 31 characters
            safe_sheet_name = str(p)[:31]
            df_prof.to_excel(writer, sheet_name=safe_sheet_name)
            
    return output.getvalue()

def export_professor_schedules_to_bytes_(schedule: dict, data: dict) -> bytes:
    """
    Exports the individual professor schedules to an in-memory Excel file.
    Rows are hours, columns are days, tabs are professors.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for p in data['professors']:
            prof_data = {}
            for d in data['days']:
                day_column = []
                for h in data['hours']:
                    assigned_course = ""
                    for c in data['courses']:
                        if schedule.get(c, {}).get(d, {}).get(h) == p:
                            assigned_course = c
                            break
                    day_column.append(assigned_course)
                prof_data[d] = day_column
            
            df_prof = pd.DataFrame(prof_data, index=data['hours'])
            df_prof.index.name = "Hours"
            
            # Excel limits sheet names to 31 characters
            safe_sheet_name = str(p)[:31]
            df_prof.to_excel(writer, sheet_name=safe_sheet_name)
            
    return output.getvalue()