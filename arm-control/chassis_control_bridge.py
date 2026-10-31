#!/usr/bin/env python3
"""Bridge legacy ArmPi Pro chassis commands to the newer motor controller."""

import math
import threading

import rospy
from chassis_control.msg import SetTranslation, SetVelocity
from ros_robot_controller.msg import MotorState, MotorsState


WHEEL_DIAMETER_MM = 96.5
CHASSIS_A_MM = 110.0
CHASSIS_B_MM = 97.5
COMMAND_TIMEOUT_SECONDS = 0.5


class ChassisControlBridge:
    def __init__(self):
        rospy.init_node("chassis_control")
        self._lock = threading.Lock()
        self._last_command = rospy.Time.now()
        self._stopped = True
        self._motor_pub = rospy.Publisher(
            "/ros_robot_controller/set_motor", MotorsState, queue_size=1
        )
        rospy.Subscriber(
            "/chassis_control/set_velocity", SetVelocity, self._set_velocity,
            queue_size=1,
        )
        rospy.Subscriber(
            "/chassis_control/set_translation", SetTranslation,
            self._set_translation, queue_size=1,
        )
        rospy.Timer(rospy.Duration(0.1), self._watchdog)
        rospy.on_shutdown(self.stop)

    @staticmethod
    def _wheel_rps(velocity, direction, angular):
        velocity = -velocity
        angular = -angular
        radians = math.radians(direction)
        vx = velocity * math.cos(radians)
        vy = velocity * math.sin(radians)
        vp = angular * (CHASSIS_A_MM + CHASSIS_B_MM)
        v1 = vy - vx + vp
        v2 = vy + vx - vp
        v3 = vy - vx - vp
        v4 = vy + vx + vp
        circumference = math.pi * WHEEL_DIAMETER_MM
        return [-v1 / circumference, v4 / circumference,
                v2 / circumference, -v3 / circumference]

    def _publish(self, wheel_rps):
        msg = MotorsState()
        msg.data = [
            MotorState(id=index, rps=value, duty=0)
            for index, value in enumerate(wheel_rps, start=1)
        ]
        self._motor_pub.publish(msg)

    def _set_velocity(self, msg):
        with self._lock:
            self._last_command = rospy.Time.now()
            self._stopped = msg.velocity == 0 and msg.angular == 0
            self._publish(self._wheel_rps(msg.velocity, msg.direction, msg.angular))

    def _set_translation(self, msg):
        velocity = math.hypot(msg.velocity_x, msg.velocity_y)
        direction = math.degrees(math.atan2(msg.velocity_y, msg.velocity_x)) % 360
        with self._lock:
            self._last_command = rospy.Time.now()
            self._stopped = velocity == 0
            self._publish(self._wheel_rps(velocity, direction, 0))

    def _watchdog(self, _event):
        with self._lock:
            elapsed = (rospy.Time.now() - self._last_command).to_sec()
            if not self._stopped and elapsed > COMMAND_TIMEOUT_SECONDS:
                self._publish([0.0] * 4)
                self._stopped = True

    def stop(self):
        with self._lock:
            self._publish([0.0] * 4)
            self._stopped = True


if __name__ == "__main__":
    bridge = ChassisControlBridge()
    rospy.loginfo("Legacy chassis bridge ready")
    rospy.spin()
