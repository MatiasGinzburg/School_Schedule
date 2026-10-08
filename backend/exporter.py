import pandas as pd
import logging
from pathlib import Path

import tkinter as tk
from tkinter import filedialog

logger = logging.getLogger(__name__)

def export_schedule_to_excel(schedule: dict, data: dict, output_path: str = None):
    """
    Exports the generated schedule to an Excel file.
    If output_path is not provided, opens a file dialog for the user to select the save location.
    """
    if not output_path:
        # Initialize a hidden tkinter root window
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True) # Bring the dialog to the front
        
        # Open the Save As dialog
        logger.info("Waiting for user to select save location...")
        output_path = filedialog.asksaveasfilename(
            title="Save Schedule As",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile="final_schedule.xlsx"
        )
        
        root.destroy()
        
        # If the user clicks "Cancel" in the dialog
        if not output_path:
            logger.warning("Export cancelled by the user. File was not saved.")
            return

    logger.info(f"Exporting schedule to {output_path}...")
    
    courses = data['courses']
    days = data['days']
    hours = data['hours']
    
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with pd.ExcelWriter(out_file, engine='openpyxl') as writer:
            for day in days:
                day_data = {}
                for h in hours:
                    hour_column = []
                    for c in courses:
                        prof = schedule.get(c, {}).get(day, {}).get(h, "UNASSIGNED")
                        hour_column.append(prof)
                    day_data[h] = hour_column
                
                df_day = pd.DataFrame(day_data, index=courses)
                df_day.index.name = "Courses"
                df_day.to_excel(writer, sheet_name=day)
                
        logger.info(f"Schedule exported successfully to {output_path}.")
        
    except Exception as e:
        logger.error(f"Failed to export schedule: {e}")
        raise

def export_professor_schedules_to_excel(schedule: dict, data: dict, output_path: str = None):
    """
    Exports the generated schedule to an Excel file from the professors' perspective.
    Creates one tab per professor. Rows are hours, columns are days, 
    and cells contain the assigned course.
    """
    if not output_path:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        logger.info("Waiting for user to select save location for professor schedules...")
        output_path = filedialog.asksaveasfilename(
            title="Save Professor Schedules As",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialfile="professor_schedules.xlsx"
        )
        
        root.destroy()
        
        if not output_path:
            logger.warning("Export cancelled by the user. Professor schedule file was not saved.")
            return

    logger.info(f"Exporting professor schedules to {output_path}...")
    
    professors = data['professors']
    days = data['days']
    hours = data['hours']
    courses = data['courses']
    
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        with pd.ExcelWriter(out_file, engine='openpyxl') as writer:
            for p in professors:
                # Keys are days (columns), values are lists of courses (rows)
                prof_data = {}
                for d in days:
                    day_column = []
                    for h in hours:
                        assigned_course = ""  # Leave cell blank if not teaching
                        # Search the schedule to find if this professor teaches any course at this day/hour
                        for c in courses:
                            if schedule.get(c, {}).get(d, {}).get(h) == p:
                                assigned_course = c
                                break
                        day_column.append(assigned_course)
                    prof_data[d] = day_column
                
                # Create the DataFrame using hours as the row index
                df_prof = pd.DataFrame(prof_data, index=hours)
                df_prof.index.name = "Hours"
                
                # Excel has a strict 31-character limit for tab names
                safe_sheet_name = str(p)[:31]
                df_prof.to_excel(writer, sheet_name=safe_sheet_name)
                
        logger.info(f"Professor schedules exported successfully to {output_path}.")
        
    except Exception as e:
        logger.error(f"Failed to export professor schedules: {e}")
        raise