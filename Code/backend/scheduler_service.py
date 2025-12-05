"""
Asyncio-based winding scheduler service.
Monitors next_winding.txt and automatically triggers winding at scheduled times.
"""

import uasyncio as asyncio
import utime as time
import next_winding_service
import motor_service

# Maximum sleep time (5 minutes in seconds)
MAX_SLEEP_SECONDS = 300

def parse_iso_time(iso_str):
    """Parse ISO format time string to time tuple.
    Format: YYYY-MM-DDTHH:MM:SS
    Returns: time tuple or None if invalid
    """
    try:
        if not iso_str or iso_str == "Not scheduled":
            return None
        
        date_part, time_part = iso_str.split('T')
        year, month, day = date_part.split('-')
        hour, minute, second = time_part.split(':')
        
        # Create time tuple (year, month, day, hour, minute, second, weekday, yearday)
        # weekday and yearday will be calculated by mktime
        return (int(year), int(month), int(day), int(hour), int(minute), int(second), 0, 0)
    except Exception as e:
        print(f"Error parsing ISO time '{iso_str}': {e}")
        return None

def seconds_until_next_winding():
    """Calculate seconds until next scheduled winding.
    Returns: seconds until next winding, or None if not scheduled
    """
    try:
        # Read next winding time from file
        with open(next_winding_service.NEXT_WINDING_FILE, 'r') as f:
            iso_time = f.read().strip()
        
        if not iso_time or iso_time == "Not scheduled":
            return None
        
        # Parse the ISO time
        next_winding_tuple = parse_iso_time(iso_time)
        if not next_winding_tuple:
            return None
        
        # Convert to seconds since epoch
        next_winding_secs = time.mktime(next_winding_tuple)
        now_secs = time.time()
        
        # Calculate difference
        diff = next_winding_secs - now_secs
        
        print(f"Next winding in {diff:.0f} seconds ({diff/60:.1f} minutes)")
        
        return max(0, diff)  # Return 0 if time has passed
        
    except Exception as e:
        print(f"Error calculating next winding time: {e}")
        return None

def calculate_and_update_next_winding():
    """Calculate the next winding time based on schedule and update next_winding.txt.
    This is called after each winding to prepare for the next one.
    """
    try:
        import services
        
        # Read current schedule
        schedule = services.read_schedule()
        if not schedule or not schedule.get('winding_times'):
            print("No schedule configured")
            next_winding_service.write_next_winding("Not scheduled")
            return
        
        # Get enabled winding times and days
        winding_times = [t for t in schedule.get('winding_times', []) if t.get('enabled', True)]
        enabled_days = [day for day, enabled in schedule.get('days', {}).items() if enabled]
        
        if not winding_times or not enabled_days:
            print("No enabled winding times or days")
            next_winding_service.write_next_winding("Not scheduled")
            return
        
        # Find next winding time
        now = time.localtime()
        now_secs = time.mktime(now)
        next_winding_secs = None
        next_winding_tuple = None
        
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        # Search up to 7 days ahead
        for day_offset in range(8):
            check_secs = now_secs + (86400 * day_offset)
            check_date = time.localtime(check_secs)
            weekday = weekday_names[check_date[6]]
            
            if weekday in enabled_days:
                for winding_time in winding_times:
                    hour = winding_time.get('hour', 0)
                    minute = winding_time.get('minute', 0)
                    ampm = winding_time.get('ampm', 'AM')
                    
                    # Convert to 24-hour format
                    if ampm == 'PM' and hour < 12:
                        hour += 12
                    if ampm == 'AM' and hour == 12:
                        hour = 0
                    
                    winding_tuple = (check_date[0], check_date[1], check_date[2], hour, minute, 0, check_date[6], check_date[7])
                    winding_secs = time.mktime(winding_tuple)
                    
                    if winding_secs > now_secs:
                        if next_winding_secs is None or winding_secs < next_winding_secs:
                            next_winding_secs = winding_secs
                            next_winding_tuple = winding_tuple
                
                if next_winding_tuple:
                    break
        
        # Write next winding time
        if next_winding_tuple:
            iso_str = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
                next_winding_tuple[0], next_winding_tuple[1], next_winding_tuple[2],
                next_winding_tuple[3], next_winding_tuple[4], next_winding_tuple[5]
            )
            next_winding_service.write_next_winding(iso_str)
            print(f"Next winding scheduled for: {iso_str}")
        else:
            next_winding_service.write_next_winding("Not scheduled")
            print("No upcoming winding times found")
            
    except Exception as e:
        print(f"Error calculating next winding: {e}")
        import sys
        sys.print_exception(e)

async def winding_scheduler():
    """Main scheduler loop that monitors and triggers winding."""
    import gc
    
    print("Winding scheduler started")
    
    while True:
        try:
            # Free memory at start of each cycle
            gc.collect()
            
            # Calculate seconds until next winding
            seconds = seconds_until_next_winding()
            
            # If next_winding.txt is empty or not scheduled, wind immediately and recalculate
            if seconds is None:
                print("No scheduled winding time found - winding now and calculating schedule")
                
                # Log event
                import event_log_service
                event_log_service.log_event(event_log_service.EVENT_WIND_IMMEDIATE, 'No schedule found')
                
                # Get winding duration from schedule
                import services
                schedule = services.read_schedule()
                winding_duration = schedule.get('winding_duration', 30) if schedule else 30
                motor_service.wind_watch(winding_duration)
                
                # Update quantity
                import quantity_service
                quantity = quantity_service.read_quantity()
                if quantity > 0:
                    quantity -= 1
                    quantity_service.write_quantity(quantity)
                
                # Update last winding time
                import last_winding_service
                now = time.localtime()
                iso_time = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
                    now[0], now[1], now[2], now[3], now[4], now[5]
                )
                last_winding_service.write_last_winding(iso_time)
                
                # Send notification
                try:
                    import lib.notification
                    time_str = "{:02d}:{:02d}:{:02d}".format(now[3], now[4], now[5])
                    msg = "Watch wound at {}. Winds remaining: {}".format(time_str, quantity)
                    lib.notification.send_ntfy_notification(msg)
                except Exception as e:
                    print(f"Could not send notification: {e}")
                
                # Calculate and update next winding time
                calculate_and_update_next_winding()
                
                # Clean up after winding cycle
                gc.collect()
                
                # Sleep for a bit before checking again
                await asyncio.sleep(60)
                continue
            
            # If winding time is now or past, wind immediately
            if seconds <= 0:
                print("Winding time reached - winding watch")
                
                # Log event
                import event_log_service
                event_log_service.log_event(event_log_service.EVENT_WIND_SCHEDULED, 'Scheduled winding')
                
                # Get winding duration from schedule
                import services
                schedule = services.read_schedule()
                winding_duration = schedule.get('winding_duration', 30) if schedule else 30
                motor_service.wind_watch(winding_duration)
                
                # Update quantity
                import quantity_service
                quantity = quantity_service.read_quantity()
                if quantity > 0:
                    quantity -= 1
                    quantity_service.write_quantity(quantity)
                
                # Update last winding time
                import last_winding_service
                now = time.localtime()
                iso_time = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
                    now[0], now[1], now[2], now[3], now[4], now[5]
                )
                last_winding_service.write_last_winding(iso_time)
                
                # Send notification
                try:
                    import lib.notification
                    time_str = "{:02d}:{:02d}:{:02d}".format(now[3], now[4], now[5])
                    msg = "Watch wound at {}. Winds remaining: {}".format(time_str, quantity)
                    lib.notification.send_ntfy_notification(msg)
                except Exception as e:
                    print(f"Could not send notification: {e}")
                
                # Calculate and update next winding time
                calculate_and_update_next_winding()
                
                # Clean up after winding cycle
                gc.collect()
                
                # Sleep for a bit to avoid immediate re-trigger
                await asyncio.sleep(60)
                continue
            
            # Sleep until next winding or max 5 minutes
            sleep_time = min(seconds, MAX_SLEEP_SECONDS)
            print(f"Scheduler sleeping for {sleep_time:.0f} seconds ({sleep_time/60:.1f} minutes)")
            await asyncio.sleep(sleep_time)
            
        except Exception as e:
            print(f"Error in winding scheduler: {e}")
            
            # Log error
            try:
                import event_log_service
                event_log_service.log_event(event_log_service.EVENT_ERROR, 'Scheduler: {}'.format(str(e)))
            except:
                pass
            
            import sys
            sys.print_exception(e)
            # Sleep a bit before retrying
            await asyncio.sleep(60)

def start_scheduler():
    """Start the winding scheduler as an asyncio task."""
    loop = asyncio.get_event_loop()
    loop.create_task(winding_scheduler())
    print("Winding scheduler task created")
