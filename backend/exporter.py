import pandas as pd
import io

def export_schedule_to_excel_bytes(schedule: dict, data: dict) -> bytes:
    """Exports the master schedule to an in-memory Excel file."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for day in data['days']:
            day_data = {}
            for h in data['hours']:
                hour_column = []
                for c in data['courses']:
                    prof = schedule.get(c, {}).get(day, {}).get(h, "UNASSIGNED")
                    hour_column.append(prof)
                day_data[h] = hour_column
            df_day = pd.DataFrame(day_data, index=data['courses'])
            df_day.index.name = "Courses"
            df_day.to_excel(writer, sheet_name=day)
    return output.getvalue()

def export_professor_schedules_to_bytes(schedule: dict, data: dict) -> bytes:
    """Exports the professor schedules to an in-memory Excel file."""
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
            safe_sheet_name = str(p)[:31]
            df_prof.to_excel(writer, sheet_name=safe_sheet_name)
    return output.getvalue()