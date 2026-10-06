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
