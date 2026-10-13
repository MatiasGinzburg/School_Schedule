import pandas as pd
from pathlib import Path
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def load_and_validate_data(file_path: str):
    """
    Reads the consolidated spreadsheet 'Horarios_SG.xlsx', extracts canonical lists, 
    and builds the requirement and availability matrices.
    """
    logger.info(f"Loading data from {file_path}...")
    xls = pd.ExcelFile(file_path)
    
    # 1. Load Canonical Lists from "Names" Tab
    # We skip row 0 (the counts) and extract the names from row 1 onwards
    df_names = pd.read_excel(xls, sheet_name="Names")
    courses = df_names['Courses'].iloc[1:].dropna().astype(str).str.strip().tolist()
    professors = df_names['Professors'].iloc[1:].dropna().astype(str).str.strip().tolist()
    days = df_names['Days'].iloc[1:].dropna().astype(str).str.strip().tolist()
    hours = df_names['Hours'].iloc[1:].dropna().astype(str).str.strip().tolist()
    
    logger.info(f"Found {len(courses)} Courses, {len(professors)} Professors, {len(days)} Days, {len(hours)} Hours.")

    # 2. Load Requirements Matrix
    # Using index_col=0 sets the courses as the row labels
    df_req = pd.read_excel(xls, sheet_name="_hours_per_course_per_professor", index_col=0).fillna(0)
    df_req.index = df_req.index.astype(str).str.strip()
    df_req.columns = df_req.columns.astype(str).str.strip()

    # 3. Load Availabilities (skiprows=5 skips your notes)
    # Course grid: Contains 0, 1, or 2
    df_c_disp = pd.read_excel(xls, sheet_name="Courses_disponibility", skiprows=5, index_col=0).fillna(0)
    df_c_disp.index = df_c_disp.index.astype(str).str.strip()

    # Professor grid: Contains 0 or 1
    df_p_disp = pd.read_excel(xls, sheet_name="Professors_disponibility", skiprows=5, index_col=0).fillna(0)
    df_p_disp.index = df_p_disp.index.astype(str).str.strip()

    # 4. Restructure Data into Dictionaries for PuLP
    logger.info("Restructuring grids into constraint dictionaries...")
    
    # R[course][professor] = assigned hours
    R = {}
    for c in courses:
        R[c] = {}
        for p in professors:
            if p in df_req.columns and c in df_req.index:
                val = int(df_req.at[c, p])
                if val > 0:
                    R[c][p] = val

    # Because pandas renames duplicate columns (e.g., Monday, Monday.1, Monday.2), 
    # we use linear column indexing based on the length of the hours list.
    
    # A_prof[professor][day][hour] = 1 or 0
    A_prof = {}
    for p in professors:
        A_prof[p] = {}
        for i, d in enumerate(days):
            A_prof[p][d] = {}
            for j, h in enumerate(hours):
                col_idx = i * len(hours) + j
                if p in df_p_disp.index and col_idx < len(df_p_disp.columns):
                    val = df_p_disp.iloc[df_p_disp.index.get_loc(p), col_idx]
                    # Handle duplicate index safety
                    if isinstance(val, pd.Series): val = val.iloc[0]
                    A_prof[p][d][h] = 1 if int(val) > 0 else 0
                else:
                    A_prof[p][d][h] = 0

    # A_course[course][day][hour] = 0, 1, or 2
    A_course = {}
    for c in courses:
        A_course[c] = {}
        for i, d in enumerate(days):
            A_course[c][d] = {}
            for j, h in enumerate(hours):
                col_idx = i * len(hours) + j
                if c in df_c_disp.index and col_idx < len(df_c_disp.columns):
                    val = df_c_disp.iloc[df_c_disp.index.get_loc(c), col_idx]
                    if isinstance(val, pd.Series): val = val.iloc[0]
                    A_course[c][d][h] = int(val)
                else:
                    A_course[c][d][h] = 0

    logger.info("Data loaded successfully.")

    return {
        "courses": courses,
        "professors": professors,
        "days": days,
        "hours": hours,
        "req_hours": R,
        "availability": A_prof,
        "course_availability": A_course
    }

if __name__ == "__main__":
    # Quick test execution
    try:
        data = load_and_validate_data("./Example_data/Horarios_SG.xlsx")
        
        # Test Professor Extraction
        prof = data['professors'][0]
        print(f"\n--- Sample Req Hours for {prof} ---")
        for c in data['courses']:
            h = data['req_hours'][c].get(prof, 0)
            if h > 0: print(f"{c}: {h} hours")
            
        # Test Course Tri-State Availability Extraction
        sample_course = data['courses'][0]
        sample_day = data['days'][0]
        print(f"\n--- {sample_course} Availability on {sample_day} (0, 1, or 2) ---")
        for h, state in data['course_availability'][sample_course][sample_day].items():
            print(f"{h}: {state}")
            
    except Exception as e:
        logger.error(f"Failed: {e}")