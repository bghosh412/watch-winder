"""
Last winding timestamp tracking service.
Records the most recent winding time.
"""

import utime as time

LAST_WINDING_FILE = 'data/last_windingtxt'

def read_last_winding():
    """Read last winding timestamp from file.
    Returns: str ISO format timestamp or 'Never' if not found
    """
    try:
        with open(LAST_WINDING_FILE, 'r') as f:
            timestamp = f.read().strip()
            return timestamp if timestamp else 'Never'
    except OSError:
        # File doesn't exist
        return 'Never'
    except Exception as e:
        print(f"Error reading last winding: {e}")
        return 'Never'

def write_last_winding(iso_time):
    """Write last winding timestamp to file.
    Args:
        iso_time: str ISO format timestamp (YYYY-MM-DDTHH:MM:SS)
    Returns: bool success
    """
    try:
        with open(LAST_WINDING_FILE, 'w') as f:
            f.write(iso_time)
        return True
    except Exception as e:
        print(f"Error writing last winding: {e}")
        return False

def write_last_winding_now():
    """Write current time as last winding timestamp.
    Returns: bool success
    """
    now = time.localtime()
    iso_time = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
        now[0], now[1], now[2], now[3], now[4], now[5]
    )
    return write_last_winding(iso_time)
