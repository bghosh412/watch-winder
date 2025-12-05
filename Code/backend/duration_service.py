"""
Duration service for managing winding duration configuration.
Reads and writes winding duration in minutes.
"""

DURATION_FILE = 'data/duration.txt'
DEFAULT_DURATION = 30  # Default 30 minutes

def read_duration():
    """Read winding duration from file.
    
    Returns:
        int: Duration in minutes (default: 30)
    """
    try:
        with open(DURATION_FILE, 'r') as f:
            content = f.read().strip()
            return int(content) if content else DEFAULT_DURATION
    except:
        return DEFAULT_DURATION

def write_duration(duration):
    """Write winding duration to file.
    
    Args:
        duration: Duration in minutes
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(DURATION_FILE, 'w') as f:
            f.write(str(duration))
        return True
    except Exception as e:
        print(f"Error writing duration: {e}")
        return False
