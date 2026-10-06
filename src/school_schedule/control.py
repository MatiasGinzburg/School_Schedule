import logging

logger = logging.getLogger(__name__)

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