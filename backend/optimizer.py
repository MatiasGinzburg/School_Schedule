import pulp
import logging
import copy

logger = logging.getLogger(__name__)

def solve_schedule(
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
