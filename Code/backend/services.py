"""
Schedule data operations service.
Handles reading and writing winding schedule configuration.
"""

SCHEDULE_FILE = 'data/schedule.txt'

def read_schedule():
    """Read winding schedule from file.
    Returns: dict with schedule data or None if not found
    """
    try:
        with open(SCHEDULE_FILE, 'r') as f:
            content = f.read().strip()
            if not content:
                return None
            
            # Simple JSON parser for MicroPython
            import ujson
            schedule = ujson.loads(content)
            return schedule
    except OSError:
        # File doesn't exist
        return None
    except Exception as e:
        print(f"Error reading schedule: {e}")
        return None

def write_schedule(schedule_data):
    """Write winding schedule to file.
    Args:
        schedule_data: dict with schedule configuration
    Returns: bool success
    """
    try:
        import ujson
        content = ujson.dumps(schedule_data)
        
        with open(SCHEDULE_FILE, 'w') as f:
            f.write(content)
        
        print("Schedule saved successfully")
        return True
    except Exception as e:
        print(f"Error writing schedule: {e}")
        return False
