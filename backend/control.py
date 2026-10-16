import logging

logger = logging.getLogger(__name__)


def pre_optimization_checks(data: dict, margin: float = 1.3):
    """
    Validates trivial constraints before running the solver. 
    Updated to validate joint lectures (virtual aliases) and their overlapping availabilities.
    Returns a tuple: (is_feasible, list_of_errors, list_of_warnings).
    """
    courses = data['courses']
    professors = data['professors']
    days = data['days']
    hours = data['hours']
    req_hours = data.get('req_hours', {})
    availability = data.get('availability', {})
    course_avail = data.get('course_availability', {})
    
    # Extract alias data generated in data_loader
    aliases = data.get('aliases', {})
    alias_reqs = data.get('alias_requirements', {})
    
    is_feasible = True
    errors = []
    warnings = []

    # 1. Alias-Specific Checks (Joint Lectures)
    for a_name, a_data in aliases.items():
        req_a = alias_reqs.get(a_name, 0)
        if req_a > 0:
            # Alias availability is pre-calculated as the strict intersection of all component grids
            total_avail_a = sum(availability.get(a_name, {}).get(d, {}).get(h, 0) for d in days for h in hours)
            if total_avail_a < req_a:
                errors.append(f"Infeasible Joint Lecture: '{a_name}' requires {req_a} hours, but the strict overlap of its components only allows {total_avail_a} available slots.")
                is_feasible = False

    # 2. Course-Specific Checks
    for c in courses:
        # Course total includes base required hours PLUS any joint lectures it belongs to
        base_req_course = sum(req_hours[c].get(p, 0) for p in professors)
        alias_req_course = sum(alias_reqs.get(a, 0) for a, a_data in aliases.items() if c in a_data['courses'])
        total_req_course = base_req_course + alias_req_course

        assigned_profs = [p for p in professors if req_hours[c].get(p, 0) > 0]
        assigned_aliases = [a for a, a_data in aliases.items() if c in a_data['courses'] and alias_reqs.get(a, 0) > 0]
        
        slots_1 = 0
        slots_2 = 0
        for d in days:
            for h in hours:
                state = course_avail[c][d][h]
                if state == 1:
                    slots_1 += 1
                    # Check if ANY individual prof or joint alias is available for this mandatory slot
                    available_count = sum(1 for p in assigned_profs if availability[p][d][h] == 1)
                    available_alias_count = sum(1 for a in assigned_aliases if availability.get(a, {}).get(d, {}).get(h, 0) == 1)
                    
                    if (available_count + available_alias_count) == 0:
                        errors.append(f"Course '{c}' has a mandatory slot (1) on {d} at {h}, but ZERO assigned professors (or joint aliases) are available.")
                        is_feasible = False
                elif state == 2:
                    slots_2 += 1
                    
        max_possible_slots = slots_1 + slots_2

        if total_req_course < slots_1:
            errors.append(f"Course '{c}' requires {total_req_course} total hours (including joint classes), but has {slots_1} mandatory slots (1).")
            is_feasible = False
            
        if total_req_course > max_possible_slots:
            errors.append(f"Course '{c}' requires {total_req_course} total hours (including joint classes), but only has {max_possible_slots} valid slots (1 and 2).")
            is_feasible = False

        # Verify strict individual intersections
        for p in assigned_profs:
            req_cp = req_hours[c][p]
            intersect_slots = sum(
                1 for d in days for h in hours
                if course_avail[c][d][h] in [1, 2] and availability[p][d][h] == 1
            )
            if intersect_slots < req_cp:
                errors.append(f"'{p}' must teach '{c}' individually for {req_cp} hours, but their overlapping availability only allows {intersect_slots} hours.")
                is_feasible = False

    # 3. Professor-Specific Checks
    for p in professors:
        # Professor total includes base required hours PLUS any joint lectures they belong to
        base_req_prof = sum(req_hours[c].get(p, 0) for c in courses)
        alias_req_prof = sum(alias_reqs.get(a, 0) for a, a_data in aliases.items() if p in a_data['professors'])
        total_req_prof = base_req_prof + alias_req_prof
        
        if total_req_prof > 0:
            total_avail_prof = sum(availability[p][d][h] for d in days for h in hours)
            required_with_margin = total_req_prof * margin
            
            if total_avail_prof < total_req_prof:
                errors.append(f"Professor '{p}' is assigned {total_req_prof} total hours (including joint classes), but only available for {total_avail_prof} slots.")
                is_feasible = False
            elif total_avail_prof < required_with_margin:
                warnings.append(f"Tight Schedule: '{p}' is assigned {total_req_prof} hours but only has {total_avail_prof} available slots. (Recommended: {required_with_margin} for margin).")

    return is_feasible, errors, warnings



def verify_schedule(schedule: dict, data: dict, active_constraints: list = None) -> bool:
    """
    Validates that the generated V2 schedule strictly adheres to all selected constraints,
    including tri-state course availabilities, contiguous free hours, and joint aliases.
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
    aliases = data.get('aliases', {})
    
    is_valid = True

    # 1. Gather actual assigned hours
    actual_hours = {c: {p: 0 for p in professors} for c in courses}
    actual_alias_hours = {a: 0 for a in aliases}
    
    for c in courses:
        for d in days:
            for h in hours:
                p_val = schedule[c][d].get(h)
                if not p_val:
                    continue
                
                # Check if this assignment matches an alias (which we joined with commas)
                is_alias = False
                for a_name, a_data in aliases.items():
                    if c in a_data['courses'] and p_val == ", ".join(a_data['professors']):
                        is_alias = True
                        actual_alias_hours[a_name] += 1
                        break
                        
                if not is_alias and p_val in professors:
                    actual_hours[c][p_val] += 1

    # Because a joint lecture spans multiple courses, actual_alias_hours overcounts 
    # (e.g. if C1 and C2 both log the alias hour, it increments twice).
    # We normalize it by dividing by the number of courses involved.
    for a_name, a_data in aliases.items():
        if len(a_data['courses']) > 0:
            actual_alias_hours[a_name] //= len(a_data['courses'])

    # 2. Verify Exact Required Hours
    if "fulfill_req_hours" in active_constraints:
        # Standard Hours
        for c in courses:
            for p in professors:
                required = req_hours[c].get(p, 0)
                assigned = actual_hours[c][p]
                if required != assigned:
                    logger.error(f"Hours Mismatch: Course '{c}' requires {required} individual hours from '{p}', but got {assigned}.")
                    is_valid = False
                    
        # Alias Hours
        for a_name, a_data in aliases.items():
            required = data['alias_requirements'].get(a_name, 0)
            assigned = actual_alias_hours[a_name]
            if required != assigned:
                logger.error(f"Alias Hours Mismatch: Joint alias '{a_name}' requires {required} hours, but got {assigned}.")
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
                    
                    is_current_dummy = (course_avail[c][d][h_current] in [1, 2]) and not schedule[c][d].get(h_current)
                    is_next_dummy = (course_avail[c][d][h_next] in [1, 2]) and not schedule[c][d].get(h_next)
                    
                    if is_current_dummy and (course_avail[c][d][h_next] in [1, 2]) and not is_next_dummy:
                        logger.error(f"Contiguous Violation: '{c}' has a free slot on {d} at {h_current}, but is followed by an assigned slot at {h_next}.")
                        is_valid = False

    # 5. Verify Professor Availability and No Double-Booking
    if "no_double_booking_and_prof_availability" in active_constraints:
        for d in days:
            for h in hours:
                assigned_profs_this_slot = set()
                
                for c in courses:
                    p_val = schedule[c][d].get(h)
                    if not p_val:
                        continue
                        
                    # If it's a comma-separated alias string, split it into individual profs
                    active_profs = [p.strip() for p in p_val.split(',')]
                    
                    for p in active_profs:
                        # Double Booking
                        # (If C1 and C2 share the alias, p will appear twice, which is valid for a joint lecture. 
                        #  We only flag double booking if they are assigned to DIFFERENT distinct lectures.)
                        # We track uniqueness by course, but if it's a joint lecture, they are inherently shared.
                        # For simplicity in verification, we track the specific assignments.
                        
                        # We must ensure that a professor isn't teaching two *distinct* subjects.
                        # Since aliases are the only way to teach multiple courses at once, we ensure
                        # the specific string configuration matches exactly if seen multiple times.
                        pass # Double booking logic requires a broader pass to allow joint aliases

                # Re-evaluate Double Booking allowing for joint lectures
                prof_teaching_count = {p: 0 for p in professors}
                
                for c in courses:
                    p_val = schedule[c][d].get(h)
                    if not p_val:
                        continue
                        
                    is_alias = False
                    for a_name, a_data in aliases.items():
                        if c in a_data['courses'] and p_val == ", ".join(a_data['professors']):
                            is_alias = True
                            # Only increment once per alias, not once per course
                            # We can achieve this by doing it at the day/hour level rather than the course level loop
                            break
                            
                # A more robust double-booking check at the day/hour level
                prof_active_classes = {p: set() for p in professors}
                
                for c in courses:
                    p_val = schedule[c][d].get(h)
                    if not p_val:
                        continue
                        
                    for p in [x.strip() for x in p_val.split(',')]:
                        if p in professors:
                            prof_active_classes[p].add(p_val) # The 'class identity' is the string assigned
                            
                            is_available = availability.get(p, {}).get(d, {}).get(h, 0)
                            if is_available == 0:
                                logger.error(f"Availability Violation: '{p}' is assigned to '{c}' on {d} at {h}, but is marked unavailable.")
                                is_valid = False
                                
                for p, classes in prof_active_classes.items():
                    if len(classes) > 1:
                        logger.error(f"Double Booking: '{p}' is assigned to multiple distinct classes {classes} on {d} at {h}.")
                        is_valid = False

    if is_valid:
        logger.info("Schedule verified successfully: All modular constraints are strictly met.")
    else:
        logger.error("Schedule verification failed: One or more constraints were violated.")
        
    return is_valid