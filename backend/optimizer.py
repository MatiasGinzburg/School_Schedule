import pulp
import logging
import copy

logger = logging.getLogger(__name__)

def solve_schedule(
    data: dict, 
    cost_function: list = None, 
    active_constraints: list = None,
    timeLimit=120
):
    """
    Modular solver that dynamically initializes variables and equations 
    based strictly on the requested cost function and constraints.
    Supports virtual aliases for joint/multi-component lectures.
    """
    if cost_function is None:
        cost_function = []
        
    if active_constraints is None:
        active_constraints = [
            "fulfill_req_hours", 
            "respect_course_availability", 
            "no_double_booking_and_prof_availability", 
            "force_free_hours_to_end"
        ]
        
    logger.info(f"Solving model. Cost Function: {cost_function}. Constraints: {len(active_constraints)} active.")
    
    d_mod = copy.deepcopy(data)
    courses = d_mod['courses']
    days = d_mod['days']
    hours = d_mod['hours']
    real_profs = d_mod['professors'].copy()
    aliases = d_mod.get('aliases', {})
    alias_names = list(aliases.keys())
    
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
                        
            # Real required hours must account for base professors AND the course's involvement in aliases
            real_required = sum(d_mod['req_hours'][c].get(p, 0) for p in real_profs)
            alias_required = sum(
                d_mod['alias_requirements'].get(a, 0) 
                for a in aliases 
                if c in aliases[a]['courses']
            )
            slack_hours = total_mandatory_slots - (real_required + alias_required)
            d_mod['req_hours'][c][dummy_prof] = max(slack_hours, 0)

    prob = pulp.LpProblem("School_Scheduling_Modular_Optimization", pulp.LpMinimize)
    all_profs = d_mod['professors']
    
    # Base Variables (Always needed)
    X = pulp.LpVariable.dicts("X", (courses, all_profs, days, hours), cat=pulp.LpBinary)
    
    # Alias Variables
    X_alias = pulp.LpVariable.dicts("X_alias", (alias_names, days, hours), cat=pulp.LpBinary)
    
    L = len(hours) - 1

    # ---------------------------------------------------------
    # 2. DYNAMIC COST FUNCTIONS
    # ---------------------------------------------------------
    # Start with finding a feasible solution
    prob += 0, "Cost_Base_Feasibility"

    # Define the variables that we are going to need based on the list
    if "minimize_prof_gaps" in cost_function:
        Y = pulp.LpVariable.dicts("Y", (real_profs, days), cat=pulp.LpBinary)
        E = pulp.LpVariable.dicts("E", (real_profs, days), lowBound=0, cat=pulp.LpInteger)
        S = pulp.LpVariable.dicts("S", (real_profs, days), lowBound=0, cat=pulp.LpInteger)
        
        for p in real_profs:
            for d in days:
                # Total classes = individual classes + alias classes where this prof is involved
                alias_involvement_h = [
                    X_alias[a][d][h] for a in alias_names for h in hours 
                    if p in aliases[a]['professors']
                ]
                
                prob += pulp.lpSum(X[c][p][d][h] for c in courses for h in hours) + pulp.lpSum(alias_involvement_h) <= len(hours) * Y[p][d]
                # len(hours) * Y[p][d] is bigger than the amount of hours that professor p at day d teaches at school
                prob += S[p][d] <= L * Y[p][d]
                
                for h_idx, h in enumerate(hours):
                    # Active this hour = individual + alias
                    is_teaching_h = pulp.lpSum(X[c][p][d][h] for c in courses) + pulp.lpSum(
                        X_alias[a][d][h] for a in alias_names if p in aliases[a]['professors']
                    )
                    prob += E[p][d] >= h_idx * is_teaching_h
                    prob += S[p][d] <= h_idx * is_teaching_h + L * (1 - is_teaching_h)
                    
    elif "minimize_prof_days" in cost_function:
        # We only hit this elif if 'minimize_prof_gaps' is NOT present, avoiding duplicate 'Y' constraints
        Y = pulp.LpVariable.dicts("Y", (real_profs, days), cat=pulp.LpBinary)
        
        for p in real_profs:
            for d in days:
                # Total classes = individual classes + alias classes where this prof is involved
                alias_involvement_h = [
                    X_alias[a][d][h] for a in alias_names for h in hours 
                    if p in aliases[a]['professors']
                ]
                
                prob += pulp.lpSum(X[c][p][d][h] for c in courses for h in hours) + pulp.lpSum(alias_involvement_h) <= len(hours) * Y[p][d]

    # For each term in cost_function we add a new term to prob.objective 
    # First terms have priority 100 times bigger
    number_of_cost_function_terms = len(cost_function)
    weight = 1000 ** (number_of_cost_function_terms -1)

    for term in cost_function:
        if term == "minimize_prof_days":
            prob.objective += pulp.lpSum( weight * Y[p][d] for p in real_profs for d in days )
        elif term == "minimize_prof_gaps":
            prob.objective += pulp.lpSum( weight * (E[p][d] - S[p][d]) for p in real_profs for d in days )
        elif term == "pure_feasibility":
            pass # Inherently handled by 'prob += 0' earlier
        else:
            logger.warning(f"Unrecognized cost function term '{term}'. Ignoring.")
        
        weight /= 1000

    # ---------------------------------------------------------
    # 3. DYNAMIC CONSTRAINTS (Multiple active)
    # ---------------------------------------------------------
    if "fulfill_req_hours" in active_constraints:
        # Standard Classes
        for c in courses:
            for p in all_profs:
                required = d_mod['req_hours'][c].get(p, 0)
                prob += pulp.lpSum(X[c][p][d][h] for d in days for h in hours) == required
                if required == 0:
                    for d in days:
                        for h in hours:
                            prob += X[c][p][d][h] == 0
                            
        # Alias Classes
        for a in alias_names:
            required = d_mod['alias_requirements'].get(a, 0)
            prob += pulp.lpSum(X_alias[a][d][h] for d in days for h in hours) == required

    if "respect_course_availability" in active_constraints:
        for d in days:
            for h in hours:
                for c in courses:
                    is_active = d_mod['course_availability'][c][d][h]
                    # Total profs = individual assignments + any active alias involving this course
                    alias_involvement = [X_alias[a][d][h] for a in alias_names if c in aliases[a]['courses']]
                    prob += pulp.lpSum(X[c][p][d][h] for p in all_profs) + pulp.lpSum(alias_involvement) == is_active
                    
    if "no_double_booking_and_prof_availability" in active_constraints:
        for d in days:
            for h in hours:
                for p in all_profs:
                    # Total classes = individual classes + alias classes where this prof is involved
                    alias_involvement = [X_alias[a][d][h] for a in alias_names if p in aliases.get(a, {}).get('professors', [])]
                    prob += pulp.lpSum(X[c][p][d][h] for c in courses) + pulp.lpSum(alias_involvement) <= 1
                    
                    if d_mod['availability'].get(p, {}).get(d, {}).get(h, 0) == 0:
                        for c in courses:
                            prob += X[c][p][d][h] == 0
                            
                # Check alias availability directly
                for a in alias_names:
                    if d_mod['availability'].get(a, {}).get(d, {}).get(h, 0) == 0:
                        prob += X_alias[a][d][h] == 0

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
    solver = pulp.PULP_CBC_CMD(msg=True, timeLimit=timeLimit) 
    prob.solve(solver)
    
    if pulp.LpStatus[prob.status] not in ["Optimal", "Feasible"]:
        logger.error("No valid schedule exists with these constraints.")
        return None

    schedule = {c: {d: {} for d in days} for c in courses}
    for c in courses:
        for d in days:
            for h in hours:
                # Check Individual Assignments
                for p in real_profs:
                    if pulp.value(X[c][p][d][h]) and pulp.value(X[c][p][d][h]) > 0.5:
                        schedule[c][d][h] = p
                        
                # Check Alias Assignments
                for a in alias_names:
                    if c in aliases[a]['courses']:
                        if pulp.value(X_alias[a][d][h]) and pulp.value(X_alias[a][d][h]) > 0.5:
                            # Reconstruct the string for the final output
                            profs = aliases[a]['professors']
                            schedule[c][d][h] = ", ".join(profs)
                        
    return schedule