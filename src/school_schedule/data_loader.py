import pandas as pd
from pathlib import Path
import logging
import traceback

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def clean_dataframe(df):
    """Used only for the course hours sheet. Removes completely empty rows/cols."""
    df = df.dropna(how='all', axis=0).dropna(how='all', axis=1)
    if len(df) > 0 and isinstance(df.index[0], str):
        df.index = df.index.str.strip()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def parse_availability(x):
    """Robustly maps human input (1, x, yes, True) to 1, and blanks/zeros to 0."""
    if pd.isna(x):
        return 0
    if isinstance(x, (int, float)):
        return 1 if x > 0 else 0
    val = str(x).strip().lower()
    if val in ['1', 'x', 'yes', 'y', 'true', 'v', 'ok']:
        return 1
    return 0

def load_and_validate_data(file_path: str):
    """
    Reads the spreadsheet, extracts metadata, bounds grids, runs strict 
    compatibility checks, and returns data structured for PuLP.
    """
    file_path = Path(file_path)
    xls = pd.ExcelFile(file_path)
    
    if "hours_per_course" not in xls.sheet_names:
        raise ValueError("The Excel file must contain a sheet named 'hours_per_course'.")
        
    # --- 1. Load Metadata (Range T1:U3) ---
    logger.info("Extracting schedule metadata...")
    try:
        df_meta = pd.read_excel(xls, sheet_name="hours_per_course", usecols="T:U", nrows=3, header=None)
        
        days_per_week = int(df_meta.iloc[0, 1])
        hours_per_day = int(df_meta.iloc[1, 1])
        expected_course_hours = int(df_meta.iloc[2, 1])
        
        if expected_course_hours != (days_per_week * hours_per_day):
            raise ValueError(
                f"Metadata mismatch: 'Hours per week' ({expected_course_hours}) does not equal "
                f"'days per week' ({days_per_week}) * 'hours per day' ({hours_per_day})."
            )
        logger.info(f"Metadata verified: {days_per_week} days, {hours_per_day} hours/day, {expected_course_hours} total hours.")
    except Exception as e:
        raise ValueError(f"Failed to read or parse metadata from T1:U3 in 'hours_per_course'. Details: {e}")

    # --- 2. Load and clean Hours Per Course ---
    prof_sheet_names = [sheet.strip() for sheet in xls.sheet_names if sheet.strip() != "hours_per_course"]
    
    df_hours = pd.read_excel(xls, sheet_name="hours_per_course", index_col=0)
    df_hours = clean_dataframe(df_hours)
    
    valid_courses = [idx for idx in df_hours.index if str(idx).lower() not in ['total', 'sum', 'nan', 'none']]
    df_hours = df_hours.loc[valid_courses]
    
    valid_prof_columns = [col for col in df_hours.columns if col in prof_sheet_names]
    df_hours = df_hours[valid_prof_columns].fillna(0)
    
    courses = df_hours.index.astype(str).tolist()
    assigned_professors = df_hours.columns.tolist()
    
    # --- 3. Load Professor Availability (FIXED) ---
    availability_dfs = {}
    columns_to_read = list(range(days_per_week + 1)) 
    
    for prof_name in assigned_professors:
        df_avail = pd.read_excel(
            xls, 
            sheet_name=prof_name, 
            index_col=0, 
            usecols=columns_to_read, 
            nrows=hours_per_day
        )
        
        # FIX A: We no longer drop empty rows here, preserving the hour alignment.
        # FIX B: Force all row/column labels to strings to prevent index fallback bugs.
        df_avail.index = df_avail.index.astype(str).str.strip()
        df_avail.columns = df_avail.columns.astype(str).str.strip()
        
        # FIX C: Apply the robust parsing logic
        df_avail = df_avail.map(parse_availability)
            
        availability_dfs[prof_name] = df_avail

    sample_prof = list(availability_dfs.keys())[0]
    hours = availability_dfs[sample_prof].index.tolist()
    days = availability_dfs[sample_prof].columns.tolist()

    # --- 4. Phase 1: Compatibility Checks ---
    logger.info("Running Mathematical Compatibility Checks...")
    
    course_totals = df_hours.sum(axis=1)
    for course, total in course_totals.items():
        if total != expected_course_hours:
            raise ValueError(
                f"Validation Failed: Course '{course}' is assigned {total} hours, "
                f"but metadata requires exactly {expected_course_hours} hours."
            )
            
    prof_assigned_hours = df_hours.sum(axis=0)
    for prof, assigned in prof_assigned_hours.items():
        if assigned == 0:
            continue
            
        total_available_slots = availability_dfs[prof].values.sum()
        required_margin = 1.3 * assigned
        
        if total_available_slots < required_margin:
            raise ValueError(
                f"Validation Failed: Professor '{prof}' only has {total_available_slots} available slots. "
                f"They need at least {required_margin} (130% of {assigned} assigned hours)."
            )

    logger.info("All compatibility checks passed successfully.")

    # --- 5. Restructure data for PuLP ---
    R = {}
    for course in courses:
        R[course] = {}
        for prof in assigned_professors:
            val = int(df_hours.at[course, prof])
            if val > 0:
                R[course][prof] = val
                
    A = {}
    for prof, df in availability_dfs.items():
        A[prof] = {}
        for day in days:
            A[prof][day] = {}
            for hour in hours:
                A[prof][day][hour] = int(df.at[hour, day])

    return {
        "courses": courses,
        "professors": assigned_professors,
        "days": days,
        "hours": hours,
        "req_hours": R,
        "availability": A
    }

if __name__ == "__main__":
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