import pandas as pd
import io
import logging

logger = logging.getLogger(__name__)

def export_schedule_to_excel_bytes(schedule: dict, data: dict) -> bytes:
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
                        # Direct tuple lookup handles both standard and joint classes
                        val = data.get('subject_map', {}).get((c, prof), prof)
                    elif state == 0:
                        val = "---" 
                    elif state == 2:
                        val = "FREE" 
                    else:
                        val = "UNASSIGNED / ERROR"
                        
                    hour_column.append(val)
                day_data[h] = hour_column
                
            df_day = pd.DataFrame(day_data, index=data['courses'])
            df_day.index.name = "Courses"
            df_day.to_excel(writer, sheet_name=day)
            
    return output.getvalue()

def export_professor_schedules_to_bytes(schedule: dict, data: dict) -> bytes:
    output = io.BytesIO()
    real_profs = [p for p in data['professors'] if not str(p).startswith("free_hour_")]
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for p in real_profs:
            prof_data = {}
            for d in data['days']:
                day_column = []
                for h in data['hours']:
                    assigned_subjects = []
                    
                    for c in data['courses']:
                        scheduled_entity = schedule.get(c, {}).get(d, {}).get(h)
                        if scheduled_entity:
                            active_profs = [x.strip() for x in str(scheduled_entity).split(',')]
                            if str(p) in active_profs:
                                subj = data.get('subject_map', {}).get((c, scheduled_entity), scheduled_entity)
                                if subj not in assigned_subjects:
                                    assigned_subjects.append(str(subj))
                                
                    cell_val = ", ".join(assigned_subjects) if assigned_subjects else "---"
                    day_column.append(cell_val)
                    
                prof_data[d] = day_column
            
            df_prof = pd.DataFrame(prof_data, index=data['hours'])
            df_prof.index.name = "Hours"
            safe_sheet_name = str(p)[:31]
            df_prof.to_excel(writer, sheet_name=safe_sheet_name)
            
    return output.getvalue()