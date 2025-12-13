#ifndef STEPPER_MOTOR_DRIVER_H
#define STEPPER_MOTOR_DRIVER_H

#include <Arduino.h>


class StepperMotorDriver {
public:
    StepperMotorDriver(int in1, int in2, int in3, int in4);
    void setSpeed(float rpm);
    void step(int steps, bool clockwise = true); // blocking
    void release();
    void runForDuration(float durationMinutes, float rpm, bool clockwise = true); // non-blocking, speed as parameter
    static float speedStringToRPM(const String& speedStr);

    // Non-blocking state machine interface
    void start(int steps, bool clockwise = true);
    void update(); // call frequently from loop()
    bool isRunning() const;

private:
    int _in1, _in2, _in3, _in4;
    float _rpm;
    unsigned long _stepDelay; // microseconds
    void stepMotor(int stepIdx);
    int _currentStep;

    // State machine variables
    volatile bool _running = false;
    int _stepsRemaining = 0;
    int _direction = 1;
    unsigned long _lastStepTime = 0;
};

#endif // STEPPER_MOTOR_DRIVER_H
