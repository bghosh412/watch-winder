import gc
import utime as time
import uasyncio as asyncio

# Collect garbage before starting
gc.collect()

# Add a small delay to ensure WiFi is fully ready
time.sleep(2)

print('Starting Fish Feeder System...')
print('Free memory:', gc.mem_free())

try:
    # Import scheduler service first
    import scheduler_service
    print('Scheduler service imported')
    gc.collect()
    
    # Start the feeding scheduler (this creates an asyncio task)
    scheduler_service.start_scheduler()
    print('Feeding scheduler started')
    gc.collect()
    
    # Import and start API server
    import api
    print('API module imported successfully')
    gc.collect()
    print('Free memory after import:', gc.mem_free())
    
    # Start the server (this will run the asyncio event loop)
    api.app.run(host='0.0.0.0', port=80)
    
except ImportError as e:
    print('Import error:', e)
    print('Make sure all required files are uploaded to the ESP32')
    import sys
    sys.print_exception(e)
except MemoryError as e:
    print('Memory error:', e)
    print('ESP32 ran out of memory. Try reducing features.')
    import sys
    sys.print_exception(e)
except Exception as e:
    print('Error starting system:', e)
    import sys
    sys.print_exception(e)
