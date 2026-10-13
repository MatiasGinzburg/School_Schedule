import logging

logger = logging.getLogger(__name__)

def pre_optimization_checks(data: dict, margin: float = 1.3):
    """
    Validates trivial constraints before running the solver. 
    Returns a tuple: (is_feasible, list_of_errors, list_of_warnings).
    """
    courses = data['courses']
    professors = data['professors']
    days = data['days']
    hours = data['hours']
    req_hours = data['req_hours']
    availability = data['availability']
    course_avail = data['course_availability']
    
    is_feasible = True
    errors = []
    warnings = []

    for c in courses:
        total_req_course = sum(req_hours[c].get(p, 0) for p in professors)
        assigned_profs = [p for p in professors if req_hours[c].get(p, 0) > 0]
        
        slots_1 = 0
        slots_2 = 0
        for d in days:
            for h in hours:
                state = course_avail[c][d][h]
                if state == 1:
                    slots_1 += 1
                    available_count = sum(1 for p in assigned_profs if availability[p][d][h] == 1)
                    if available_count == 0:
                        errors.append(f"Course '{c}' has a mandatory slot (1) on {d} at {h}, but ZERO assigned professors are available.")
                        is_feasible = False
                elif state == 2:
                    slots_2 += 1
                    
        max_possible_slots = slots_1 + slots_2

        if total_req_course < slots_1:
            errors.append(f"Course '{c}' requires {total_req_course} total hours, but has {slots_1} mandatory slots (1).")
            is_feasible = False
            
        if total_req_course > max_possible_slots:
            errors.append(f"Course '{c}' requires {total_req_course} total hours, but only has {max_possible_slots} valid slots (1 and 2).")
            is_feasible = False

        for p in assigned_profs:
            req_cp = req_hours[c][p]
            intersect_slots = sum(
                1 for d in days for h in hours
                if course_avail[c][d][h] in [1, 2] and availability[p][d][h] == 1
            )
            if intersect_slots < req_cp:
                errors.append(f"'{p}' must teach '{c}' for {req_cp} hours, but their overlapping availability only allows {intersect_slots} hours.")
                is_feasible = False

    for p in professors:
        total_req_prof = sum(req_hours[c].get(p, 0) for c in courses)
        if total_req_prof > 0:
            total_avail_prof = sum(availability[p][d][h] for d in days for h in hours)
            required_with_margin = total_req_prof * margin
            
            if total_avail_prof < total_req_prof:
                errors.append(f"Professor '{p}' is assigned {total_req_prof} hours, but only available for {total_avail_prof} slots.")
                is_feasible = False
            elif total_avail_prof < required_with_margin:
                warnings.append(f"Tight Schedule: '{p}' is assigned {total_req_prof} hours but only has {total_avail_prof} available slots. (Recommended: {required_with_margin} for margin).")

    return is_feasible, errors, warnings


def verify_schedule(schedule: dict, data: dict, active_constraints: list = None) -> bool:
    """
    Validates that the generated V2 schedule strictly adheres to all selected constraints,
    including tri-state course availabilities and contiguous end-of-day free hours.
    """
    if active_constraints is None:
        active_constraints = [
            "fulfill_req_hours", 
            "respect_course_availability", 
            "no_double_booking_and_prof_availability", 
            "force_free_hours_to_end"
        ]
        
    logger.info("Starting post-optimization schedule verification...")
    
    courses = data['courses']
    professors = data['professors']
    days = data['days']
    hours = data['hours']
    req_hours = data['req_hours']
    availability = data['availability']
    course_avail = data['course_availability']
    
    is_valid = True

    # 1. Gather actual assigned hours
    actual_hours = {c: {p: 0 for p in professors} for c in courses}
    for c in courses:
        for d in days:
            for h in hours:
                p = schedule[c][d].get(h)
                if p:
                    actual_hours[c][p] += 1

    # 2. Verify Exact Required Hours
    if "fulfill_req_hours" in active_constraints:
        for c in courses:
            for p in professors:
                required = req_hours[c].get(p, 0)
                assigned = actual_hours[c][p]
                if required != assigned:
                    logger.error(f"Hours Mismatch: Course '{c}' requires {required} hours from '{p}', but got {assigned}.")
                    is_valid = False

    # 3. Verify Course Availability states (0, 1, 2)
    if "respect_course_availability" in active_constraints:
        for c in courses:
            for d in days:
                for h in hours:
                    state = course_avail[c][d][h]
                    p = schedule[c][d].get(h)
                    assigned_count = 1 if p else 0
                    
                    if state == 0 and assigned_count != 0:
                        logger.error(f"Course Avail Violation: '{c}' on {d} at {h} is state 0 (closed) but got assigned '{p}'.")
                        is_valid = False
                    elif state == 1 and assigned_count != 1:
                        logger.error(f"Course Avail Violation: '{c}' on {d} at {h} is state 1 (mandatory) but got {assigned_count} profs.")
                        is_valid = False
                    elif state == 2 and assigned_count > 1:
                        logger.error(f"Course Avail Violation: '{c}' on {d} at {h} is state 2 (optional) but got {assigned_count} profs.")
                        is_valid = False

    # 4. Verify Contiguous Free Hours at the end of the day
    if "force_free_hours_to_end" in active_constraints:
        for c in courses:
            for d in days:
                for h_idx in range(len(hours) - 1):
                    h_current = hours[h_idx]
                    h_next = hours[h_idx + 1]
                    
                    # A slot is considered a "dummy" (free hour) if it's open (1 or 2) but unassigned
                    is_current_dummy = (course_avail[c][d][h_current] in [1, 2]) and not schedule[c][d].get(h_current)
                    is_next_dummy = (course_avail[c][d][h_next] in [1, 2]) and not schedule[c][d].get(h_next)
                    
                    # If current is free, and the next slot is an open school slot, the next slot MUST also be free
                    if is_current_dummy and (course_avail[c][d][h_next] in [1, 2]) and not is_next_dummy:
                        logger.error(f"Contiguous Violation: '{c}' has a free slot on {d} at {h_current}, but is followed by an assigned slot at {h_next}.")
                        is_valid = False

    # 5. Verify Professor Availability and No Double-Booking
    if "no_double_booking_and_prof_availability" in active_constraints:
        for d in days:
            for h in hours:
                assigned_profs_this_slot = set()
                for c in courses:
                    p = schedule[c][d].get(h)
                    if not p:
                        continue
                    
                    if p in assigned_profs_this_slot:
                        logger.error(f"Double Booking: '{p}' is assigned to multiple courses on {d} at {h}.")
                        is_valid = False
                    assigned_profs_this_slot.add(p)
                    
                    is_available = availability.get(p, {}).get(d, {}).get(h, 0)
                    if is_available == 0:
                        logger.error(f"Availability Violation: '{p}' is assigned to '{c}' on {d} at {h}, but is marked unavailable.")
                        is_valid = False

    if is_valid:
        logger.info("Schedule verified successfully: All modular constraints are strictly met.")
    else:
        logger.error("Schedule verification failed: One or more constraints were violated.")
        
    return is_valid