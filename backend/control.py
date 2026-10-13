import logging

logger = logging.getLogger(__name__)

def pre_optimization_checks(data: dict, margin: float = 1.3) -> bool:
    """
    Validates trivial constraints before running the solver. 
    Catches mathematical impossibilities in the grid inputs.
    """
    logger.info("Running pre-optimization feasibility checks...")
    
    courses = data['courses']
    professors = data['professors']
    days = data['days']
    hours = data['hours']
    req_hours = data['req_hours']
    availability = data['availability']
    course_avail = data['course_availability']
    
    is_feasible = True

    for c in courses:
        total_req_course = sum(req_hours[c].get(p, 0) for p in professors)
        # Filter down to only the professors who actually teach this course
        assigned_profs = [p for p in professors if req_hours[c].get(p, 0) > 0]
        
        slots_1 = 0
        slots_2 = 0
        for d in days:
            for h in hours:
                state = course_avail[c][d][h]
                
                if state == 1:
                    slots_1 += 1
                    # NEW CHECK: At least one assigned professor must be available
                    available_count = sum(1 for p in assigned_profs if availability[p][d][h] == 1)
                    if available_count == 0:
                        logger.error(f"Infeasible Coverage: Course '{c}' has a mandatory slot (1) on {d} at {h}, but ZERO assigned professors are available.")
                        is_feasible = False
                        
                elif state == 2:
                    slots_2 += 1
                    
        max_possible_slots = slots_1 + slots_2

        # 1. Course total hours >= mandatory slots (1)
        if total_req_course < slots_1:
            logger.error(f"Infeasible Course '{c}': Requires {total_req_course} total hours, but has {slots_1} mandatory slots (1).")
            is_feasible = False
            
        # 2. Course total hours <= mandatory (1) + optional (2) slots
        if total_req_course > max_possible_slots:
            logger.error(f"Infeasible Course '{c}': Requires {total_req_course} total hours, but only has {max_possible_slots} valid slots (1 and 2).")
            is_feasible = False

        # 3. Intersection of Course and Professor Availability
        for p in assigned_profs:
            req_cp = req_hours[c][p]
            intersect_slots = sum(
                1 for d in days for h in hours
                if course_avail[c][d][h] in [1, 2] and availability[p][d][h] == 1
            )
            if intersect_slots < req_cp:
                logger.error(f"Infeasible Intersection: '{p}' must teach '{c}' for {req_cp} hours, but their overlapping availability only allows {intersect_slots} hours.")
                is_feasible = False

    # 4. Professor Availability Margin
    for p in professors:
        total_req_prof = sum(req_hours[c].get(p, 0) for c in courses)
        if total_req_prof > 0:
            total_avail_prof = sum(availability[p][d][h] for d in days for h in hours)
            required_with_margin = total_req_prof * margin
            
            # Strict fail if they mathematically don't have enough hours at all
            if total_avail_prof < total_req_prof:
                logger.error(f"Infeasible Professor '{p}': Assigned {total_req_prof} hours, but only available for {total_avail_prof} slots.")
                is_feasible = False
            # Margin fail to ensure flexibility
            elif total_avail_prof < required_with_margin:
                logger.warning(f"Tight Professor Schedule: '{p}' is assigned {total_req_prof} hours but only has {total_avail_prof} available slots. (Recommended: {required_with_margin} for {margin}x margin).")
                #is_feasible = False

    if is_feasible:
        logger.info("Pre-checks passed. The inputs are theoretically feasible.")
    else:
        logger.error("Pre-checks failed. The schedule is mathematically impossible.")
        
    return is_feasible


def verify_schedule(schedule: dict, data: dict) -> bool:
    """
    Validates that the generated schedule strictly adheres to all original constraints
    defined in the input data.
    """
    logger.info("Starting post-optimization schedule verification...")
    
    courses = data['courses']
    professors = data['professors']
    days = data['days']
    hours = data['hours']
    req_hours = data['req_hours']
    availability = data['availability']
    
    is_valid = True

    # 1. Verify exact required hours per course per professor
    actual_hours = {c: {p: 0 for p in professors} for c in courses}
    for c in courses:
        for d in days:
            for h in hours:
                p = schedule[c][d].get(h)
                if p:
                    actual_hours[c][p] += 1

    for c in courses:
        for p in professors:
            required = req_hours[c].get(p, 0)
            assigned = actual_hours[c][p]
            if required != assigned:
                logger.error(f"Hours Mismatch: Course '{c}' requires {required} hours from '{p}', but got {assigned}.")
                is_valid = False

    # 2. Verify no student gaps (every course has a professor at every timeslot)
    for c in courses:
        for d in days:
            for h in hours:
                if h not in schedule[c][d] or not schedule[c][d][h]:
                    logger.error(f"Student Gap: Course '{c}' has no professor assigned on {d} at hour {h}.")
                    is_valid = False

    # 3. Verify professor availability and no double-booking
    for d in days:
        for h in hours:
            assigned_profs_this_slot = set()
            for c in courses:
                p = schedule[c][d].get(h)
                if not p:
                    continue
                
                # Check Double Booking
                if p in assigned_profs_this_slot:
                    logger.error(f"Double Booking: '{p}' is assigned to multiple courses on {d} at hour {h}.")
                    is_valid = False
                assigned_profs_this_slot.add(p)
                
                # Check Availability
                is_available = availability.get(p, {}).get(d, {}).get(h, 0)
                if is_available == 0:
                    logger.error(f"Availability Violation: '{p}' is assigned to '{c}' on {d} at hour {h}, but is marked unavailable.")
                    is_valid = False

    if is_valid:
        logger.info("Schedule verified successfully: All constraints are strictly met.")
    else:
        logger.error("Schedule verification failed: One or more constraints were violated.")
        
    return is_valid