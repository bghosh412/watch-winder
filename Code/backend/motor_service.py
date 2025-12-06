"""
Motor control service for watch winder.
Controls the 28BYJ-48 stepper motor via ULN2003 driver.
"""

import utime as time

try:
    from machine import Pin
except ImportError:
    # Mock Pin class for development/testing
    class Pin:
        OUT = 1
        def __init__(self, pin, mode):
            self.pin = pin
            self.mode = mode
            self._value = 0
        def value(self, val=None):
            if val is not None:
                self._value = val
            return self._value

class MotorService:
    """Service class for controlling the stepper motor."""
    
    # 28BYJ-48 stepper motor half-step sequence
    HALF_STEP_SEQUENCE = [
        [1, 0, 0, 0],
        [1, 1, 0, 0],
        [0, 1, 0, 0],
        [0, 1, 1, 0],
        [0, 0, 1, 0],
        [0, 0, 1, 1],
        [0, 0, 0, 1],
        [1, 0, 0, 1]
    ]
    
    def __init__(self, pin_in1=5, pin_in2=4, pin_in3=14, pin_in4=12):
        """Initialize motor control pins.
        
        Args:
            pin_in1: GPIO pin for IN1 (default: GPIO5)
            pin_in2: GPIO pin for IN2 (default: GPIO4)
            pin_in3: GPIO pin for IN3 (default: GPIO14)
            pin_in4: GPIO pin for IN4 (default: GPIO12)
        """
        self.pins = [
            Pin(pin_in1, Pin.OUT),
            Pin(pin_in2, Pin.OUT),
            Pin(pin_in3, Pin.OUT),
            Pin(pin_in4, Pin.OUT)
        ]
        self.step_position = 0
        self.motor_off()
    
    def motor_off(self):
        """Turn off all motor coils to save power."""
        for pin in self.pins:
            pin.value(0)
    
    def step(self, direction=1):
        """Execute one step in the specified direction.
        
        Args:
            direction: 1 for clockwise, -1 for counter-clockwise
        """
        self.step_position = (self.step_position + direction) % 8
        sequence = self.HALF_STEP_SEQUENCE[self.step_position]
        
        for i, pin in enumerate(self.pins):
            pin.value(sequence[i])
    
    def rotate(self, steps, delay_ms=2, direction=1):
        """Rotate motor for specified number of steps.
        
        Args:
            steps: Number of steps to rotate
            delay_ms: Delay between steps in milliseconds (speed control)
            direction: 1 for clockwise, -1 for counter-clockwise
        """
        for _ in range(steps):
            self.step(direction)
            time.sleep_ms(delay_ms)
        
        # Turn off motor after rotation
        self.motor_off()
    
    def wind_watch(self, duration_minutes=30, direction=1):
        """Wind watch for specified duration.
        
        Args:
            duration_minutes: Duration to wind in minutes
            direction: 1 for clockwise, -1 for counter-clockwise
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            print(f"Starting winding for {duration_minutes} minutes")
            
            # Calculate total steps for duration
            # 4096 steps = 1 full rotation (for 28BYJ-48 in half-step mode)
            # Assuming we want continuous rotation for the duration
            # We'll do 1 rotation every 2 seconds for smooth operation
            rotations_per_minute = 30  # 1 rotation every 2 seconds
            total_rotations = duration_minutes * rotations_per_minute
            steps_per_rotation = 4096
            total_steps = total_rotations * steps_per_rotation
            
            print(f"Total rotations: {total_rotations}, Total steps: {total_steps}")
            
            # Execute rotation with 2ms delay between steps
            self.rotate(total_steps, delay_ms=2, direction=direction)
            
            print("Winding completed successfully")
            return True
            
        except Exception as e:
            print(f"Error during winding: {e}")
            self.motor_off()
            return False

# Global motor service instance
_motor_service = None

def get_motor_service():
    """Get or create the global motor service instance."""
    global _motor_service
    if _motor_service is None:
        # Import config to get motor pin configuration
        try:
            import config
            _motor_service = MotorService(
                pin_in1=config.MOTOR_PIN_1,
                pin_in2=config.MOTOR_PIN_2,
                pin_in3=config.MOTOR_PIN_3,
                pin_in4=config.MOTOR_PIN_4
            )
        except ImportError:
            # Fall back to default pins if config not available
            _motor_service = MotorService()
    return _motor_service

def wind_watch(duration_minutes=30, direction=1):
    """Convenience function to wind watch.
    
    Args:
        duration_minutes: Duration to wind in minutes
        direction: 1 for clockwise, -1 for counter-clockwise
    
    Returns:
        bool: True if successful, False otherwise
    """
    motor = get_motor_service()
    return motor.wind_watch(duration_minutes, direction)
