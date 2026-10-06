import pulp
import logging

logger = logging.getLogger(__name__)

def solve_schedule(data: dict):
    """
    Takes the structured dictionary from data_loader.py and solves the scheduling 
    problem using Integer Linear Programming (PuLP).
    """
    logger.info("Initializing the optimization model...")
    
    courses = data['courses']
    professors = data['professors']
    days = data['days']
    hours = data['hours']
    req_hours = data['req_hours']
    availability = data['availability']
    
    # 1. Initialize the Problem
    prob = pulp.LpProblem("School_Scheduling_Problem", pulp.LpMinimize)
    
    # Dummy objective for a pure feasibility problem
    prob += 0, "Arbitrary Objective"

    # 2. Decision Variables
    # X[c][p][d][h] = 1 if course c is taught by professor p on day d at hour h
    X = pulp.LpVariable.dicts("X", 
                              (courses, professors, days, hours), 
                              cat=pulp.LpBinary)

    logger.info("Adding constraints...")

    # 3. Constraints
    
    # Constraint A: Fulfill exact required hours for each course/professor combo
    for c in courses:
        for p in professors:
            required = req_hours[c].get(p, 0)
            prob += pulp.lpSum(X[c][p][d][h] for d in days for h in hours) == required, f"ReqHours_{c}_{p}"
                
            # Optimization: If a professor doesn't teach a course, force all their variables for that course to 0
            if required == 0:
                for d in days:
                    for h in hours:
                        prob += X[c][p][d][h] == 0, f"NoTeach_{c}_{p}_{d}_{h}"

    for d in days:
        for h in hours:
            # Constraint B: Exactly one professor per course per timeslot (no student gaps/double-booking)
            for c in courses:
                prob += pulp.lpSum(X[c][p][d][h] for p in professors) == 1, f"OneProfPerCourse_{c}_{d}_{h}"
                
            for p in professors:
                # Constraint C: Professor can only teach one course at a time
                prob += pulp.lpSum(X[c][p][d][h] for c in courses) <= 1, f"NoDoubleBooking_{p}_{d}_{h}"
                
                # Constraint D: Professor must be available
                is_available = availability[p][d].get(h, 0)
                if is_available == 0:
                    for c in courses:
                        prob += X[c][p][d][h] == 0, f"Availability_{p}_{c}_{d}_{h}"

    # 4. Solve the Model
    logger.info("Calling the solver (CBC)...")
    solver = pulp.PULP_CBC_CMD(msg=False) # msg=True if you want to see the solver's raw math output
    prob.solve(solver)
    
    status = pulp.LpStatus[prob.status]
    logger.info(f"Solver finished with status: {status}")
    
    if status != "Optimal":
        logger.error("No mathematically valid schedule exists with the current constraints.")
        return None

    # 5. Extract the Solution
    schedule = {c: {d: {} for d in days} for c in courses}
    
    for c in courses:
        for p in professors:
            for d in days:
                for h in hours:
                    # Floating point safety check for binary variables
                    if pulp.value(X[c][p][d][h]) and pulp.value(X[c][p][d][h]) > 0.5:
                        schedule[c][d][h] = p
                        
    logger.info("Optimal schedule successfully generated.")
    return schedule