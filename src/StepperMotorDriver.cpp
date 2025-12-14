
#include "StepperMotorDriver.h"
#include "NtfyClient.h"
#include "ConfigConstants.h"
#include <time.h>

// 28BYJ-48 stepper motor sequences
// Full-step mode for higher speed and torque (4 steps per cycle)
const int STEPS_PER_REV = 2048; // Half of 4096 because we're using full-step mode
const uint8_t stepSequence[4][4] = {
    {1, 0, 1, 0},  // Coils 1 & 3
    {0, 1, 1, 0},  // Coils 2 & 3
    {0, 1, 0, 1},  // Coils 2 & 4
    {1, 0, 0, 1}   // Coils 1 & 4
};

// Non-blocking state machine: start a move
void StepperMotorDriver::start(int steps, bool clockwise) {
    _stepsRemaining = abs(steps);
    _direction = clockwise ? 1 : -1;
    _running = (_stepsRemaining > 0);
    _lastStepTime = micros();
}

// Non-blocking state machine: call frequently from loop()
void StepperMotorDriver::update() {
    if (!_running) return;
    
    unsigned long now = micros();
    
    // Process multiple steps if we've fallen behind
    while (_running && (now - _lastStepTime >= _stepDelay)) {
        _currentStep += _direction;
        if (_currentStep < 0) _currentStep = 3;
        if (_currentStep > 3) _currentStep = 0;
        stepMotor(_currentStep);
        _lastStepTime += _stepDelay;
        _stepsRemaining--;
        
        if (_stepsRemaining <= 0) {
            _running = false;
            
            // Fully release motor to remove holding torque
            release();
            Serial.println("[Motor] Winding complete - motor released");
            
            // Small delay to ensure pins are fully released
            delay(10);
            
            // Send completion notification
            NtfyClient ntfy(NTFY_TOPIC);
            char timeStr[32];
            time_t nowT = time(nullptr);
            strftime(timeStr, sizeof(timeStr), "%Y-%m-%d %H:%M:%S", localtime(&nowT));
            char msgBuf[128];
            snprintf(msgBuf, sizeof(msgBuf), "{" NTFY_MSG_WINDING_COMPLETE "}", timeStr);
            ntfy.send(String(msgBuf));
            
            break;
        }
        
        // Limit catch-up to prevent blocking too long
        if (micros() - now > 5000) break; // Max 5ms per update call
    }
}

bool StepperMotorDriver::isRunning() const {
    return _running;
}

void StepperMotorDriver::stop() {
    _running = false;
    _stepsRemaining = 0;
    release();
    Serial.println("[MOTOR] Stopped by user request");
}

// Adapter: run for duration (minutes) at given speed (non-blocking)
void StepperMotorDriver::runForDuration(float durationMinutes, float rpm, bool clockwise) {
    setSpeed(rpm);
    // Total steps = RPM * steps/rev * minutes
    // Use STEPS_PER_REV constant defined at top of file (2048 for full-step mode)
    int totalSteps = (int)(rpm * STEPS_PER_REV * durationMinutes);

    // Send ntfy notification when winding starts
    NtfyClient ntfy(NTFY_TOPIC);
    char timeStr[32];
    time_t nowT = time(nullptr);
    strftime(timeStr, sizeof(timeStr), "%Y-%m-%d %H:%M:%S", localtime(&nowT));
    char msgBuf[160];
    snprintf(msgBuf, sizeof(msgBuf), "" NTFY_MSG_WINDING "", timeStr, durationMinutes, rpm);
    ntfy.send(String(msgBuf));

    start(totalSteps, clockwise);
}

StepperMotorDriver::StepperMotorDriver(int in1, int in2, int in3, int in4)
    : _in1(in1), _in2(in2), _in3(in3), _in4(in4), _rpm(15), _currentStep(0) {
    pinMode(_in1, OUTPUT);
    pinMode(_in2, OUTPUT);
    pinMode(_in3, OUTPUT);
    pinMode(_in4, OUTPUT);
    setSpeed(_rpm);
}

void StepperMotorDriver::setSpeed(float rpm) {
    _rpm = rpm;
    _stepDelay = (60L * 1000000L) / (STEPS_PER_REV * _rpm); // microseconds per step
}

void StepperMotorDriver::step(int steps, bool clockwise) {
    int direction = clockwise ? 1 : -1;
    for (int i = 0; i < abs(steps); i++) {
        _currentStep += direction;
        if (_currentStep < 0) _currentStep = 3;
        if (_currentStep > 3) _currentStep = 0;
        stepMotor(_currentStep);
        delayMicroseconds(_stepDelay);
    }
    release();
}

void StepperMotorDriver::stepMotor(int stepIdx) {
    digitalWrite(_in1, stepSequence[stepIdx][0]);
    digitalWrite(_in2, stepSequence[stepIdx][1]);
    digitalWrite(_in3, stepSequence[stepIdx][2]);
    digitalWrite(_in4, stepSequence[stepIdx][3]);
}


void StepperMotorDriver::release() {
    digitalWrite(_in1, LOW);
    digitalWrite(_in2, LOW);
    digitalWrite(_in3, LOW);
    digitalWrite(_in4, LOW);
}

// Map 5 speed levels to RPM for 28BYJ-48
// Full-step mode - conservative speeds for reliability
float StepperMotorDriver::speedStringToRPM(const String& speedStr) {
    if (speedStr == "Very Slow") return 8.0;
    if (speedStr == "Slow") return 10.0;
    if (speedStr == "Medium") return 12.0;
    if (speedStr == "Fast") return 14.0;
    if (speedStr == "Very Fast") return 16.0;
    // Default fallback
    return 12.0;
}
