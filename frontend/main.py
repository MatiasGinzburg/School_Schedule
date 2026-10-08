import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.data_loader import load_and_validate_data
from backend.optimizer import solve_schedule
from backend.control import verify_schedule
from backend.exporter import export_schedule_to_excel, export_professor_schedules_to_excel

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def main():
    input_file = "./data/school_schedule.xlsx"
    
    try:
        data = load_and_validate_data(input_file)
    except Exception as e:
        logging.error(f"Failed to load data: {e}")
        return

    schedule = solve_schedule(data)
    
    if schedule:
        is_valid = verify_schedule(schedule, data)
        
        if is_valid:
            # Export the master schedule (courses vs hours, tab per day)
            export_schedule_to_excel(schedule, data)
            
            # Export the individual professor schedules (hours vs days, tab per prof)
            export_professor_schedules_to_excel(schedule, data)

if __name__ == "__main__":
    main()