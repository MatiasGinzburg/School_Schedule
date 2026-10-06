import logging
from data_loader import load_and_validate_data
from optimizer import solve_schedule
from control import verify_schedule

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def main():
    file_path = "./data/school_schedule.xlsx"
    
    try:
        data = load_and_validate_data(file_path)
    except Exception as e:
        logging.error(f"Failed to load data: {e}")
        return

    schedule = solve_schedule(data)
    
    if schedule:
        # Run the validation check
        is_valid = verify_schedule(schedule, data)
        
        if is_valid:
            first_course = data['courses'][0]
            print(f"\n--- Schedule Preview for {first_course} ---")
            for day in data['days']:
                print(f"{day}:")
                for hour in data['hours']:
                    prof = schedule[first_course][day].get(hour, "UNASSIGNED")
                    print(f"  Hour {hour}: {prof}")

if __name__ == "__main__":
    main()