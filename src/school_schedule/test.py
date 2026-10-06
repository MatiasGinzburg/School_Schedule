from data_loader import *


try:
    # Note: adjust the path as necessary for your uv project
    data = load_and_validate_data("./data/school_schedule.xlsx")
    logger.info("Data loaded and validated successfully.")
    
    prof = "Profesor 14"
    
    print(f"\n--- Hours assigned to {prof} ---")
    for course in data['courses']:
        hours_val = data['req_hours'][course].get(prof, 0)
        if hours_val > 0:
            print(f"{course}: {hours_val} hours")
            
    print(f"\n--- Availability for {prof} ---")
    if prof in data['availability']:
        for day, time_slots in data['availability'][prof].items():
            print(f"{day}:")
            for hour, status in time_slots.items():
                state = "Available" if status == 1 else "Unavailable"
                print(f"  Hour {hour}: {state}")
    else:
        print(f"No availability data found for {prof}.")

except Exception as e:
    logger.error(f"Error loading data: {e}")
    logger.error(traceback.format_exc())