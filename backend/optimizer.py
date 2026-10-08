import pulp
import logging

logger = logging.getLogger(__name__)

def solve_schedule(data: dict):
    """
    Solves the scheduling problem using Integer Linear Programming (PuLP).
    Optimized to minimize the number of days professors come to school, 
    and minimize empty gaps between their classes.
    """
    logger.info("Initializing the optimization model...")
    
    courses = data['courses']
    professors = data['professors']
    days = data['days']
    hours = data['hours']
    req_hours = data['req_hours']
    availability = data['availability']
    
    # 1. Initialize the Problem (Now as a Minimization problem)
    prob = pulp.LpProblem("School_Scheduling_Optimization", pulp.LpMinimize)
    
    # 2. Decision Variables
    # X: 1 if course c is taught by professor p on day d at hour h
    X = pulp.LpVariable.dicts("X", (courses, professors, days, hours), cat=pulp.LpBinary)
    
    # Y: 1 if professor p teaches AT LEAST one class on day d
    Y = pulp.LpVariable.dicts("Y", (professors, days), cat=pulp.LpBinary)
    
    # E: The integer index of the LAST hour a professor teaches on day d
    E = pulp.LpVariable.dicts("E", (professors, days), lowBound=0, cat=pulp.LpInteger)
    
    # S: The integer index of the FIRST hour a professor teaches on day d
    S = pulp.LpVariable.dicts("S", (professors, days), lowBound=0, cat=pulp.LpInteger)

    logger.info("Setting up objectives and constraints...")

    # 3. Objective Function
    # We heavily penalize making a professor come in on a day (1000 points).
    # We lightly penalize the span of their day (End - Start) to minimize empty gaps (1 point).
    prob += pulp.lpSum(
        1000 * Y[p][d] + (E[p][d] - S[p][d]) 
        for p in professors for d in days
    ), "Minimize_Days_and_Gaps"

    # 4. Constraints
    L = len(hours) - 1 # Maximum hour index
    
    # Link the new optimization variables to the schedule (X)
    for p in professors:
        for d in days:
            # A. If X is 1 anywhere on this day, Y must be 1
            prob += pulp.lpSum(X[c][p][d][h] for c in courses for h in hours) <= len(hours) * Y[p][d], f"IsTeachingDay_{p}_{d}"
            
            # B. If they don't teach today, force start hour to 0 to avoid false gap calculations
            prob += S[p][d] <= L * Y[p][d], f"ZeroStartIfNoTeach_{p}_{d}"
            
            for h_idx, h in enumerate(hours):
                is_teaching_h = pulp.lpSum(X[c][p][d][h] for c in courses)
                
                # C. End hour must be >= this hour index if they teach right now
                prob += E[p][d] >= h_idx * is_teaching_h, f"EndHour_{p}_{d}_{h}"
                
                # D. Start hour must be <= this hour index if they teach right now
                # If they don't teach right now (is_teaching_h = 0), this safely bounds S by L
                prob += S[p][d] <= h_idx * is_teaching_h + L * (1 - is_teaching_h), f"StartHour_{p}_{d}_{h}"

    # Standard scheduling constraints
    for c in courses:
        for p in professors:
            required = req_hours[c].get(p, 0)
            prob += pulp.lpSum(X[c][p][d][h] for d in days for h in hours) == required, f"ReqHours_{c}_{p}"
            if required == 0:
                for d in days:
                    for h in hours:
                        prob += X[c][p][d][h] == 0, f"NoTeach_{c}_{p}_{d}_{h}"

    for d in days:
        for h in hours:
            for c in courses:
                prob += pulp.lpSum(X[c][p][d][h] for p in professors) == 1, f"OneProfPerCourse_{c}_{d}_{h}"
                
            for p in professors:
                prob += pulp.lpSum(X[c][p][d][h] for c in courses) <= 1, f"NoDoubleBooking_{p}_{d}_{h}"
                
                is_available = availability.get(p, {}).get(d, {}).get(h, 0)
                if is_available == 0:
                    for c in courses:
                        prob += X[c][p][d][h] == 0, f"Availability_{p}_{c}_{d}_{h}"

    # 5. Solve the Model
    logger.info("Calling the solver (CBC)... This may take a moment for complex optimizations.")
    
    # We add a time limit (e.g., 60 seconds). Finding the *perfect* minimum gaps can take a long 
    # time on large datasets, so it will return the best schedule it found within the limit.
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=60) 
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
                        
    logger.info("Optimized schedule successfully generated.")
    return schedule

    
def solve_schedule_(data: dict):
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