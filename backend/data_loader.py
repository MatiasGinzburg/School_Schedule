import pandas as pd
from pathlib import Path
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def load_and_validate_data(file_path):
    """
    Reads the consolidated spreadsheet, generating both standard requirements 
    and virtual aliases for joint lectures entirely from the Subjects sheet.
    """
    logger.info("Loading data from uploaded file...")
    xls = pd.ExcelFile(file_path)
    
    # 1. Load Canonical Lists from "Names" Tab
    df_names = pd.read_excel(xls, sheet_name="Names")
    courses = df_names['Courses'].iloc[1:].dropna().astype(str).str.strip().tolist()
    professors = df_names['Professors'].iloc[1:].dropna().astype(str).str.strip().tolist()
    days = df_names['Days'].iloc[1:].dropna().astype(str).str.strip().tolist()
    hours = df_names['Hours'].iloc[1:].dropna().astype(str).str.strip().tolist()

    # 2. Load Availabilities
    df_c_disp = pd.read_excel(xls, sheet_name="Courses_disponibility", skiprows=5, index_col=0).fillna(0)
    df_c_disp.index = df_c_disp.index.astype(str).str.strip()

    df_p_disp = pd.read_excel(xls, sheet_name="Professors_disponibility", skiprows=5, index_col=0).fillna(0)
    df_p_disp.index = df_p_disp.index.astype(str).str.strip()

    # 3. Load Subjects (Replacing the old requirements matrix)
    df_subj = pd.read_excel(xls, sheet_name="Subjects", header=1)

    logger.info("Restructuring base grids into dictionaries...")
    
    # Base Availabilities
    A_prof = {}
    for p in professors:
        A_prof[p] = {}
        for i, d in enumerate(days):
            A_prof[p][d] = {}
            for j, h in enumerate(hours):
                col_idx = i * len(hours) + j
                if p in df_p_disp.index and col_idx < len(df_p_disp.columns):
                    val = df_p_disp.iloc[df_p_disp.index.get_loc(p), col_idx]
                    if isinstance(val, pd.Series): val = val.iloc[0]
                    A_prof[p][d][h] = 1 if int(val) > 0 else 0
                else:
                    A_prof[p][d][h] = 0

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

    # Initialize empty requirements
    R = {c: {p: 0 for p in professors} for c in courses}
    aliases = {} 
    alias_requirements = {}

    # --- PROCESS REQUIREMENTS AND ALIASES DIRECTLY FROM SUBJECTS ---
    for _, row in df_subj.iterrows():
        p_str = str(row['Professor'])
        c_str = str(row['Course'])
        
        # Skip invalid/empty rows safely
        if pd.isna(row['Total Hours']) or p_str.lower() in ['nan', 'none'] or c_str.lower() in ['nan', 'none']:
            continue
            
        target_profs = [p.strip() for p in p_str.split(',')]
        target_courses = [c.strip() for c in c_str.split(',')]
        hours_needed = int(row['Total Hours'])
        
        # Check if it's a joint class (commas present)
        if len(target_profs) > 1 or len(target_courses) > 1:
            alias_name = f"ALIAS_{'_'.join(target_profs)}_FOR_{'_'.join(target_courses)}"
            
            if alias_name not in aliases:
                aliases[alias_name] = {'professors': target_profs, 'courses': target_courses}
                alias_requirements[alias_name] = 0
                
                # 1. Generate Availability Intersection for the Alias
                A_prof[alias_name] = {}
                for d in days:
                    A_prof[alias_name][d] = {}
                    for h in hours:
                        # Alias is available only if ALL component profs and courses are available
                        is_available = 1
                        for p in target_profs:
                            if A_prof.get(p, {}).get(d, {}).get(h, 0) == 0:
                                is_available = 0
                                break
                        if is_available:
                            for c in target_courses:
                                if A_course.get(c, {}).get(d, {}).get(h, 0) == 0:
                                    is_available = 0
                                    break
                        A_prof[alias_name][d][h] = is_available
                        
            # Accumulate hours for the joint alias
            alias_requirements[alias_name] += hours_needed
            
        else:
            # Standard individual class (1 Prof, 1 Course)
            p = target_profs[0]
            c = target_courses[0]
            
            if c in R and p in R[c]:
                # Accumulate hours directly into the base matrix
                R[c][p] += hours_needed
            else:
                logger.warning(f"Subject row references unknown course '{c}' or professor '{p}'.")

    logger.info(f"Generated {len(aliases)} virtual aliases for joint lectures.")

    return {
        "courses": courses,
        "professors": professors,
        "days": days,
        "hours": hours,
        "req_hours": R,
        "availability": A_prof,
        "course_availability": A_course,
        "aliases": aliases,
        "alias_requirements": alias_requirements
    }

