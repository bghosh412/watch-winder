
#include "StepperMotorDriver.h"
#include "NtfyClient.h"
#include "ConfigConstants.h"
#include <time.h>

// 28BYJ-48 stepper motor sequence (8 steps for half-stepping)
const int STEPS_PER_REV = 4096; // 64*64 (gear ratio)
const uint8_t stepSequence[8][4] = {
    {1, 0, 0, 0},
    {1, 1, 0, 0},
    {0, 1, 0, 0},
    {0, 1, 1, 0},
    {0, 0, 1, 0},
    {0, 0, 1, 1},
    {0, 0, 0, 1},
    {1, 0, 0, 1}
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
    if (now - _lastStepTime >= _stepDelay) {
        _currentStep += _direction;
        if (_currentStep < 0) _currentStep = 7;
        if (_currentStep > 7) _currentStep = 0;
        stepMotor(_currentStep);
        _lastStepTime = now;
        _stepsRemaining--;
        if (_stepsRemaining <= 0) {
            _running = false;
            release();
        }
    }
}

bool StepperMotorDriver::isRunning() const {
    return _running;
}

// Adapter: run for duration (minutes) at given speed (non-blocking)
void StepperMotorDriver::runForDuration(float durationMinutes, float rpm, bool clockwise) {
    setSpeed(rpm);
    // Steps per revolution for 28BYJ-48
    const int stepsPerRev = 4096;
    // Total steps = RPM * steps/rev * minutes
    int totalSteps = (int)(rpm * stepsPerRev * durationMinutes);

    // Send ntfy notification when winding starts
    NtfyClient ntfy(NTFY_TOPIC);
    char timeStr[32];
    time_t nowT = time(nullptr);
    strftime(timeStr, sizeof(timeStr), "%Y-%m-%d %H:%M:%S", localtime(&nowT));
    String msg = String("{Winding started at ") + timeStr + " and will wind your favorite Automatic Watch for next " + durationMinutes + " min, at " + String(rpm) + " RPM.}";
    ntfy.send(msg);

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
        if (_currentStep < 0) _currentStep = 7;
        if (_currentStep > 7) _currentStep = 0;
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
float StepperMotorDriver::speedStringToRPM(const String& speedStr) {
    if (speedStr == "Very Slow") return 5.0;
    if (speedStr == "Slow") return 10.0;
    if (speedStr == "Medium") return 15.0;
    if (speedStr == "Fast") return 20.0;
    if (speedStr == "Very Fast") return 25.0;
    // Default fallback
    return 10.0;
}
