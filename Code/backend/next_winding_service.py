"""
Next winding time tracking service.
Stores the calculated next scheduled winding time.
"""

NEXT_WINDING_FILE = 'data/next_winding.txt'

def read_next_winding():
    """Read next winding timestamp from file.
    Returns: str ISO format timestamp or 'Not scheduled' if not found
    """
    try:
        with open(NEXT_WINDING_FILE, 'r') as f:
            timestamp = f.read().strip()
            return timestamp if timestamp else 'Not scheduled'
    except OSError:
        # File doesn't exist
        return 'Not scheduled'
    except Exception as e:
        print(f"Error reading next winding: {e}")
        return 'Not scheduled'

def write_next_winding(iso_time):
    """Write next winding timestamp to file.
    Args:
        iso_time: str ISO format timestamp (YYYY-MM-DDTHH:MM:SS) or 'Not scheduled'
    Returns: bool success
    """
    try:
        with open(NEXT_WINDING_FILE, 'w') as f:
            f.write(iso_time)
        return True
    except Exception as e:
        print(f"Error writing next winding: {e}")
        return False
