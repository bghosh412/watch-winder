# Event logging service for fish feeder
# Stores critical events in a rotating log file (max 100 entries)

import utime as time

LOG_FILE = 'data/events.log'
MAX_ENTRIES = 100

# Event types
EVENT_FEED_SCHEDULED = 'FEED_SCHEDULED'
EVENT_FEED_MANUAL = 'FEED_MANUAL'
EVENT_FEED_IMMEDIATE = 'FEED_IMMEDIATE'
EVENT_ERROR = 'ERROR'
EVENT_RESTART = 'RESTART'
EVENT_CONFIG_CHANGE = 'CONFIG_CHANGE'
EVENT_QUANTITY_UPDATE = 'QUANTITY_UPDATE'

def log_event(event_type, details=''):
    """Log an event with timestamp.
    Args:
        event_type: Type of event (use EVENT_* constants)
        details: Additional details about the event
    """
    try:
        import gc
        gc.collect()
        
        # Get current timestamp
        now = time.localtime()
        timestamp = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
            now[0], now[1], now[2], now[3], now[4], now[5]
        )
        
        # Create log entry
        entry = "{},{},{}".format(timestamp, event_type, details)
        
        # Read existing entries
        entries = []
        try:
            with open(LOG_FILE, 'r') as f:
                entries = [line.strip() for line in f.readlines() if line.strip()]
        except:
            # File doesn't exist yet, start fresh
            pass
        
        # Add new entry
        entries.append(entry)
        
        # Keep only last MAX_ENTRIES
        if len(entries) > MAX_ENTRIES:
            entries = entries[-MAX_ENTRIES:]
        
        # Write back to file
        with open(LOG_FILE, 'w') as f:
            for e in entries:
                f.write(e + '\n')
        
        print("Event logged: {}".format(entry))
        gc.collect()
        
        return True
        
    except Exception as e:
        print("Failed to log event: {}".format(e))
        return False

def read_events(limit=50):
    """Read recent events from log.
    Args:
        limit: Maximum number of events to return (default 50)
    Returns: List of event dictionaries
    """
    try:
        entries = []
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
        
        # Get last 'limit' entries
        lines = lines[-limit:] if len(lines) > limit else lines
        
        # Parse entries
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(',', 2)  # Split on first 2 commas only
            if len(parts) >= 2:
                entries.append({
                    'timestamp': parts[0],
                    'event_type': parts[1],
                    'details': parts[2] if len(parts) > 2 else ''
                })
        
        return entries
        
    except:
        return []

def clear_events():
    """Clear all events from log file."""
    try:
        with open(LOG_FILE, 'w') as f:
            f.write('')
        return True
    except:
        return False

def get_event_count():
    """Get total number of events in log."""
    try:
        with open(LOG_FILE, 'r') as f:
            return len([line for line in f.readlines() if line.strip()])
    except:
        return 0

def get_recent_errors(limit=10):
    """Get recent error events.
    Args:
        limit: Maximum number of errors to return
    Returns: List of error event dictionaries
    """
    all_events = read_events(limit=MAX_ENTRIES)
    errors = [e for e in all_events if e['event_type'] == EVENT_ERROR]
    return errors[-limit:] if len(errors) > limit else errors
