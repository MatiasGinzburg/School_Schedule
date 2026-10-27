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



def is_a_valid_simple_swap(c: str, d1: str, h1: str, d2: str, h2: str, schedule: dict, data: dict) -> bool:
    """
    Validates if swapping two slots within the SAME course is mathematically valid 
    without affecting any other courses or violating contiguous free hour rules.
    """
    p1_str = schedule.get(c, {}).get(d1, {}).get(h1)
    p2_str = schedule.get(c, {}).get(d2, {}).get(h2)

    # --- 1. SINGLE COURSE CHECK (No Joint Classes) ---
    def is_shared(p_str, d, h):
        """Checks if this exact assignment is shared with any other course (alias)."""
        if not p_str: return False
        for other_c in data['courses']:
            if other_c != c and schedule.get(other_c, {}).get(d, {}).get(h) == p_str:
                return True
        return False
        
    if is_shared(p1_str, d1, h1) or is_shared(p2_str, d2, h2):
        return False
        
    # --- 2. PROFESSOR SYMMETRIC DIFFERENCE ---
    profs1 = set([p.strip() for p in p1_str.split(',')]) if p1_str else set()
    profs2 = set([p.strip() for p in p2_str.split(',')]) if p2_str else set()
    
    moving_to_2 = profs1 - profs2  # Profs leaving slot 1 going to slot 2
    moving_to_1 = profs2 - profs1  # Profs leaving slot 2 going to slot 1

    # --- 3. AVAILABILITY & DOUBLE BOOKING ---
    def check_profs(profs_moving, target_d, target_h):
        for p in profs_moving:
            # Check if professor is available to work at the new slot
            if data.get('availability', {}).get(p, {}).get(target_d, {}).get(target_h, 0) == 0:
                return False
                
            # Check if professor is already teaching another course at the new slot
            for other_c in data['courses']:
                if other_c != c:
                    other_p_str = schedule.get(other_c, {}).get(target_d, {}).get(target_h)
                    if other_p_str and p in [ap.strip() for ap in other_p_str.split(',')]:
                        return False
        return True

    if not check_profs(moving_to_2, d2, h2): return False
    if not check_profs(moving_to_1, d1, h1): return False

    # --- 4. COURSE STATE AVAILABILITY ---
    c_avail_d1 = data.get('course_availability', {}).get(c, {}).get(d1, {}).get(h1, 0)
    c_avail_d2 = data.get('course_availability', {}).get(c, {}).get(d2, {}).get(h2, 0)
    
    # Cannot move a working professor into a slot where the course is closed (State 0)
    if p1_str and c_avail_d2 == 0: return False
    if p2_str and c_avail_d1 == 0: return False

    # --- 5. CONTIGUOUS FREE HOURS CHECK ---
    def validates_contiguous(day, simulated_schedule):
        hours = data['hours']
        c_avail_day = data.get('course_availability', {}).get(c, {})
        for i in range(len(hours) - 1):
            h_curr = hours[i]
            h_next = hours[i + 1]
            
            # An open slot (1 or 2) that has no professor assigned is a "free hour"
            curr_empty = (c_avail_day.get(h_curr, 0) in [1, 2]) and not simulated_schedule.get(h_curr)
            next_empty = (c_avail_day.get(h_next, 0) in [1, 2]) and not simulated_schedule.get(h_next)
            
            # If current is empty, but the next open slot has a class, the free hour is trapped
            if curr_empty and (c_avail_day.get(h_next, 0) in [1, 2]) and not next_empty:
                return False
        return True

    # Simulate Day 1
    sim_d1 = schedule.get(c, {}).get(d1, {}).copy()
    sim_d1[h1] = p2_str
    
    if d1 == d2:
        # If the swap happens on the same day, update both slots before verifying
        sim_d1[h2] = p1_str
        if not validates_contiguous(d1, sim_d1): return False
    else:
        # If the swap spans two different days, simulate Day 2 separately
        sim_d2 = schedule.get(c, {}).get(d2, {}).copy()
        sim_d2[h2] = p1_str
        if not validates_contiguous(d1, sim_d1): return False
        if not validates_contiguous(d2, sim_d2): return False

    # If it passed every single check, the simple swap is clean and valid.
    return True


def find_simple_swaps_by_course(course: str, target_day: str, target_hour: str, data: dict, schedule: dict) -> list:
    """
    Loops through all available timeslots in the week and identifies valid simple swaps 
    for a specific course and target slot without violating constraints.
    """
    valid_swaps = []
    
    # Extract global sets from the parsed data
    days = data.get('days', [])
    hours = data.get('hours', [])
    
    for d in days:
        for h in hours:
            # Prevent evaluating a swap of the target slot with itself
            if d == target_day and h == target_hour:
                continue
                
            # Utilize the strict, single-course swap validation logic
            is_valid = is_a_valid_simple_swap(course, target_day, target_hour, d, h, schedule, data)
            
            if is_valid:
                valid_swaps.append((d, h))
                
    return valid_swaps


def find_simple_swaps_by_professor(prof: str, target_day: str, target_hour: str, data: dict, schedule: dict) -> list:
    """
    Loops through all available timeslots and identifies valid simple swaps 
    for a specific professor and target slot. A simple swap strictly involves 
    only a single course without violating constraints.
    """
    valid_swaps = []
    
    def get_course_for_prof(p, d, h):
        """Identifies which course a professor is teaching at a specific slot."""
        for c in data.get('courses', []):
            scheduled_entity = schedule.get(c, {}).get(d, {}).get(h)
            if scheduled_entity:
                active_profs = [x.strip() for x in str(scheduled_entity).split(',')]
                if str(p) in active_profs:
                    return c
        return None

    # Identify what course the professor is teaching at the target slot
    c_target = get_course_for_prof(prof, target_day, target_hour)

    days = data.get('days', [])
    hours = data.get('hours', [])
    
    for d in days:
        for h in hours:
            if d == target_day and h == target_hour:
                continue
                
            # Identify what course the professor is teaching at the candidate slot
            c_candidate = get_course_for_prof(prof, d, h)
            
            # If the professor is completely free at both slots, there is no assignment to swap
            if not c_target and not c_candidate:
                continue
                
            # A simple swap strictly involves only ONE course. 
            # If the professor is moving between two different courses, it is a complex swap and fails here.
            if c_target and c_candidate and c_target != c_candidate:
                continue
                
            # Determine the single course involved in this potential simple swap
            course_to_check = c_target if c_target else c_candidate
            
            # Utilize the strict, single-course swap validation logic
            is_valid = is_a_valid_simple_swap(course_to_check, target_day, target_hour, d, h, schedule, data)
            
            if is_valid:
                valid_swaps.append((d, h))
                
    return valid_swaps

