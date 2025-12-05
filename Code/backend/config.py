# Configuration file for Fish Feeder
# All configurable parameters for the ESP8266 fish feeder

# WiFi Configuration
WIFI_SSID = "your_wifi_ssid"
WIFI_PASSWORD = "your_wifi_password"

# mDNS/Hostname Configuration
MDNS_HOSTNAME = "feeder"  # Access via http://feeder.local:5000
MDNS_SERVICE_NAME = "Fish Feeder Device"

# Feeding Schedule (24-hour format)
FEEDING_TIMES = [
    (8, 0),   # 8:00 AM
    (20, 0),  # 8:00 PM
]

# Motor Configuration
MOTOR_STEPS_PER_FEEDING = 512  # Full rotation for 28BYJ-48
MOTOR_SPEED_MS = 2  # Delay between steps in milliseconds

# Motor pins (GPIO numbers connected to ULN2003)
# For ESP32: Actual wiring: IN1=D21, IN2=D18, IN3=D5, IN4=TX2
MOTOR_PIN_1 = 19  # D19 → IN1 (ESP32)
MOTOR_PIN_2 = 18  # D18 → IN2 (ESP32)
MOTOR_PIN_3 = 5   # D5 → IN3 (ESP32)
MOTOR_PIN_4 = 17  # TX2 → IN4 (ESP32)

# For ESP8266 (uncomment if using ESP8266):
# MOTOR_PIN_1 = 12  # D6
# MOTOR_PIN_2 = 13  # D7
# MOTOR_PIN_3 = 14  # D5
# MOTOR_PIN_4 = 15  # D8

# Servo Configuration (for continuous rotation servo)
SERVO_PIN = 18  # GPIO18 (D18) - Servo signal pin

# RTC Configuration (I2C)
RTC_SDA_PIN = 4   # D2
RTC_SCL_PIN = 5   # D1

# Power Management
DEEP_SLEEP_MINUTES = 30  # Wake up every 30 minutes to check schedule

# Notification Configuration (ntfy)
NTFY_TOPIC = "FF0x98854"
NTFY_SERVER = "http://ntfy.sh"
SEND_NOTIFICATIONS = True

# Debug Mode
DEBUG = True
