import pulp
import logging
import copy

logger = logging.getLogger(__name__)

def solve_schedule(data: dict):
    """
    Solves the V2 scheduling problem using Integer Linear Programming (PuLP).
    Incorporates tri-state course availability (0, 1, 2) and enforces that 
    all free slots for a course are pushed to the end of the day.
    """
    logger.info("Initializing the V2 optimization model...")
    
    courses = data['courses']
    professors = data['professors']
    days = data['days']
    hours = data['hours']
    req_hours = data['req_hours']
    availability = data['availability']
    course_avail = data['course_availability']
    
    # 1. Initialize the Problem (Minimization)
    prob = pulp.LpProblem("School_Scheduling_Optimization_V2", pulp.LpMinimize)
    
    # 2. Decision Variables
    # X: 1 if course c is taught by professor p on day d at hour h
    X = pulp.LpVariable.dicts("X", (courses, professors, days, hours), cat=pulp.LpBinary)
    
    # Y, E, S: Professor optimization variables (Days present, End hour, Start hour)
    Y = pulp.LpVariable.dicts("Y", (professors, days), cat=pulp.LpBinary)
    E = pulp.LpVariable.dicts("E", (professors, days), lowBound=0, cat=pulp.LpInteger)
    S = pulp.LpVariable.dicts("S", (professors, days), lowBound=0, cat=pulp.LpInteger)

    logger.info("Setting up objectives and constraints...")

    # 3. Objective Function
    # Minimize professor days (weight 1000) and daily gaps (End - Start)
    #prob += pulp.lpSum(
    #    1000 * Y[p][d] + (E[p][d] - S[p][d]) 
    #    for p in professors for d in days
    #), "Minimize_Days_and_Gaps"

    prob += 0

    # 4. Constraints
    L = len(hours) - 1 
    
    # --- Professor Optimization Constraints ---
    for p in professors:
        for d in days:
            prob += pulp.lpSum(X[c][p][d][h] for c in courses for h in hours) <= len(hours) * Y[p][d], f"IsTeachingDay_{p}_{d}"
            prob += S[p][d] <= L * Y[p][d], f"ZeroStartIfNoTeach_{p}_{d}"
            
            for h_idx, h in enumerate(hours):
                is_teaching_h = pulp.lpSum(X[c][p][d][h] for c in courses)
                prob += E[p][d] >= h_idx * is_teaching_h, f"EndHour_{p}_{d}_{h}"
                prob += S[p][d] <= h_idx * is_teaching_h + L * (1 - is_teaching_h), f"StartHour_{p}_{d}_{h}"

    # --- Fulfillment Constraints ---[cite: 1]
    for c in courses:
        for p in professors:
            required = req_hours[c].get(p, 0)
            prob += pulp.lpSum(X[c][p][d][h] for d in days for h in hours) == required, f"ReqHours_{c}_{p}"
            if required == 0:
                for d in days:
                    for h in hours:
                        prob += X[c][p][d][h] == 0, f"NoTeach_{c}_{p}_{d}_{h}"

    # --- Tri-State Course Availability & Contiguous Hours ---
    for c in courses:
        for d in days:
            for h_idx, h in enumerate(hours):
                state = course_avail.get(c, {}).get(d, {}).get(h, 0)
                assigned_profs = pulp.lpSum(X[c][p][d][h] for p in professors)
                
                # Rule 0: Course is absent (0 professors)
                if state == 0:
                    prob += assigned_profs == 0, f"CourseAvail0_{c}_{d}_{h}"
                # Rule 1: Course is mandatory (exactly 1 professor)
                elif state == 1:
                    prob += assigned_profs == 1, f"CourseAvail1_{c}_{d}_{h}"
                # Rule 2: Course is optional (0 or 1 professor)
                elif state == 2:
                    prob += assigned_profs <= 1, f"CourseAvail2_{c}_{d}_{h}"

                # Contiguous Logic: Ensure all free slots are strictly at the end.
                # If the current hour is unassigned (0), the next hour must also be unassigned (0).
                if h_idx < len(hours) - 1:
                    next_h = hours[h_idx + 1]
                    next_assigned_profs = pulp.lpSum(X[c][p][d][next_h] for p in professors)
                    prob += assigned_profs >= next_assigned_profs, f"ContiguousCourse_{c}_{d}_{h}"

    # --- Professor Availability & Double Booking ---[cite: 1]
    for d in days:
        for h in hours:
            for p in professors:
                prob += pulp.lpSum(X[c][p][d][h] for c in courses) <= 1, f"NoDoubleBooking_{p}_{d}_{h}"
                
                if availability.get(p, {}).get(d, {}).get(h, 0) == 0:
                    for c in courses:
                        prob += X[c][p][d][h] == 0, f"ProfAvail_{p}_{c}_{d}_{h}"

    # 5. Solve the Model
    logger.info("Calling the solver (CBC)... This may take a moment for complex optimizations.")
    solver = pulp.PULP_CBC_CMD(msg=True, timeLimit=60) # 60s timeout for gap optimization
    prob.solve(solver)
    
    status = pulp.LpStatus[prob.status]
    logger.info(f"Solver finished with status: {status}")
    
    if status not in ["Optimal", "Feasible"]:
        logger.error("No mathematically valid schedule exists with the current constraints.")
        return None

    # 6. Extract the Solution
    schedule = {c: {d: {} for d in days} for c in courses}
    for c in courses:
        for p in professors:
            for d in days:
                for h in hours:
                    if pulp.value(X[c][p][d][h]) and pulp.value(X[c][p][d][h]) > 0.5:
                        schedule[c][d][h] = p
                        
    logger.info("V2 Optimized schedule successfully generated.")
    return schedule



def solve_schedule_(
    data: dict, 
    cost_function: str = "pure_feasibility", 
    active_constraints: list = None
):
    """
    Modular solver that dynamically initializes variables and equations 
    based strictly on the requested cost function and constraints.
    """
    if active_constraints is None:
        active_constraints = [
            "fulfill_req_hours", 
            "respect_course_availability", 
            "no_double_booking_and_prof_availability", 
            "force_free_hours_to_end"
        ]
        
    logger.info(f"Solving model. Cost Function: '{cost_function}'. Constraints: {len(active_constraints)} active.")
    
    d_mod = copy.deepcopy(data)
    courses = d_mod['courses']
    days = d_mod['days']
    hours = d_mod['hours']
    real_profs = d_mod['professors'].copy()
    
    # ---------------------------------------------------------
    # 1. DYNAMIC PRE-PROCESSING (Variables created only if needed)
    # ---------------------------------------------------------
    use_dummy_profs = "force_free_hours_to_end" in active_constraints
    
    if use_dummy_profs:
        for c in courses:
            dummy_prof = f"free_hour_{c}"
            d_mod['professors'].append(dummy_prof)
            d_mod['availability'][dummy_prof] = {d: {h: 0 for h in hours} for d in days}
            
            total_mandatory_slots = 0
            for d in days:
                for h in hours:
                    state = d_mod['course_availability'][c][d][h]
                    if state == 2:
                        d_mod['course_availability'][c][d][h] = 1
                        d_mod['availability'][dummy_prof][d][h] = 1
                        total_mandatory_slots += 1
                    elif state == 1:
                        total_mandatory_slots += 1
                        
            real_required = sum(d_mod['req_hours'][c].get(p, 0) for p in real_profs)
            slack_hours = total_mandatory_slots - real_required
            d_mod['req_hours'][c][dummy_prof] = max(slack_hours, 0)

    prob = pulp.LpProblem("School_Scheduling_Modular_Optimization", pulp.LpMinimize)
    all_profs = d_mod['professors']
    
    # Base Variables (Always needed)
    X = pulp.LpVariable.dicts("X", (courses, all_profs, days, hours), cat=pulp.LpBinary)
    L = len(hours) - 1

    # ---------------------------------------------------------
    # 2. DYNAMIC COST FUNCTIONS (Only 1 active)
    # ---------------------------------------------------------
    if cost_function == "minimize_prof_days_and_gaps":
        # Initialize Y, E, S ONLY because this specific cost function requires them
        Y = pulp.LpVariable.dicts("Y", (real_profs, days), cat=pulp.LpBinary)
        E = pulp.LpVariable.dicts("E", (real_profs, days), lowBound=0, cat=pulp.LpInteger)
        S = pulp.LpVariable.dicts("S", (real_profs, days), lowBound=0, cat=pulp.LpInteger)

        prob += pulp.lpSum(
            1000 * Y[p][d] + (E[p][d] - S[p][d]) 
            for p in real_profs for d in days
        ), "Cost_Minimize_Days_and_Gaps"

        # Auxiliary mapping constraints strictly required to make Y, E, S work
        for p in real_profs:
            for d in days:
                prob += pulp.lpSum(X[c][p][d][h] for c in courses for h in hours) <= len(hours) * Y[p][d]
                prob += S[p][d] <= L * Y[p][d]
                for h_idx, h in enumerate(hours):
                    is_teaching_h = pulp.lpSum(X[c][p][d][h] for c in courses)
                    prob += E[p][d] >= h_idx * is_teaching_h
                    prob += S[p][d] <= h_idx * is_teaching_h + L * (1 - is_teaching_h)

    elif cost_function == "pure_feasibility":
        prob += 0, "Cost_Pure_Feasibility"
        
    else:
        logger.warning(f"Unrecognized cost function '{cost_function}'. Defaulting to pure feasibility.")
        prob += 0, "Cost_Fallback"

    # ---------------------------------------------------------
    # 3. DYNAMIC CONSTRAINTS (Multiple active)
    # ---------------------------------------------------------
    if "fulfill_req_hours" in active_constraints:
        for c in courses:
            for p in all_profs:
                required = d_mod['req_hours'][c].get(p, 0)
                prob += pulp.lpSum(X[c][p][d][h] for d in days for h in hours) == required
                if required == 0:
                    for d in days:
                        for h in hours:
                            prob += X[c][p][d][h] == 0

    if "respect_course_availability" in active_constraints:
        for d in days:
            for h in hours:
                for c in courses:
                    is_active = d_mod['course_availability'][c][d][h]
                    prob += pulp.lpSum(X[c][p][d][h] for p in all_profs) == is_active
                    
    if "no_double_booking_and_prof_availability" in active_constraints:
        for d in days:
            for h in hours:
                for p in all_profs:
                    prob += pulp.lpSum(X[c][p][d][h] for c in courses) <= 1
                    if d_mod['availability'][p][d][h] == 0:
                        for c in courses:
                            prob += X[c][p][d][h] == 0

    if "force_free_hours_to_end" in active_constraints and use_dummy_profs:
        for c in courses:
            dummy_prof = f"free_hour_{c}"
            for d in days:
                for h_idx in range(len(hours) - 1):
                    h_current = hours[h_idx]
                    h_next = hours[h_idx + 1]
                    prob += X[c][dummy_prof][d][h_current] <= X[c][dummy_prof][d][h_next]

    # ---------------------------------------------------------
    # 4. SOLVE & EXTRACT
    # ---------------------------------------------------------
    solver = pulp.PULP_CBC_CMD(msg=True, timeLimit=60) 
    prob.solve(solver)
    
    if pulp.LpStatus[prob.status] not in ["Optimal", "Feasible"]:
        logger.error("No valid schedule exists with these constraints.")
        return None

    schedule = {c: {d: {} for d in days} for c in courses}
    for c in courses:
        for p in real_profs: # Filter out the dummies
            for d in days:
                for h in hours:
                    if pulp.value(X[c][p][d][h]) and pulp.value(X[c][p][d][h]) > 0.5:
                        schedule[c][d][h] = p
                        
    return schedule
