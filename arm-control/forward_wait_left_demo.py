#!/usr/bin/env python3
# coding=utf-8

import argparse
import math
import pathlib
import signal
import sqlite3
import time


SPEED = 120
FORWARD_SECONDS = 5.0
WAIT_SECONDS = 2.0
APPROACH_SECONDS = 1.5
TURN_ANGULAR = 0.20
TURN_RAMP_SECONDS = 0.8
# Preserve the old empirical command integral as a starting estimate, not a yaw measurement.
TURN_COMMAND_AREA = math.pi / 2.0 * (90.0 / 180.0)
RIGHT_TURN_AREA_SCALE = 0.95
TURN_90_SECONDS = TURN_COMMAND_AREA / TURN_ANGULAR + TURN_RAMP_SECONDS
CYCLES = 3
ACTION_FILE = "/home/ubuntu/share/tmp/custom_forward_down_v1.d6a"
ACTIVE_ARM_SERVOS = (1, 2, 3, 4, 6)
INITIAL_ARM_POSE = {2: 501, 3: 82, 4: 828, 6: 498}
INITIAL_ARM_TOLERANCE = 12
# Verified on the installed SDK: 1 unloads; 0 loads (despite the field name).
ARM_LOAD_VALUE = 0


def positive_float(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Must be a finite positive number")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Forward, turn left, approach, run arm, reverse, turn right; repeat."
    )
    parser.add_argument("--cycles", type=int, choices=range(1, 4), default=CYCLES)
    parser.add_argument("--left-seconds", type=positive_float,
                        help="Total left turn duration, including acceleration and deceleration")
    parser.add_argument("--right-seconds", type=positive_float,
                        help="Total right turn duration, including acceleration and deceleration")
    parser.add_argument("--turn-angular", type=positive_float, default=TURN_ANGULAR,
                        help="Peak angular command for both turns (default: 0.20)")
    parser.add_argument("--turn-ramp-seconds", type=positive_float, default=TURN_RAMP_SECONDS,
                        help="Duration of each acceleration/deceleration ramp (default: 0.8)")
    parser.add_argument("--approach-seconds", type=positive_float, default=APPROACH_SECONDS,
                        help="Forward duration after the left turn")
    parser.add_argument("--left-sign", type=int, choices=(-1, 1), default=1,
                        help="Sign of chassis angular velocity for a physical left turn")
    parser.add_argument("--action-file", default=ACTION_FILE)
    parser.add_argument("--calibrate-turn", choices=("left", "right"),
                        help="Only make one turn, without forward motion or arm motion")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the sequence without connecting to ROS or moving hardware")
    args = parser.parse_args(argv)
    if not 0.05 <= args.turn_angular <= 0.35:
        parser.error("Peak turn angular command must be between 0.05 and 0.35")
    if args.turn_ramp_seconds > 2:
        parser.error("A turn ramp cannot exceed 2 seconds")
    # The integral of a trapezoid with two equal ramps is peak * (duration - ramp).
    nominal_seconds = TURN_COMMAND_AREA / args.turn_angular + args.turn_ramp_seconds
    if args.left_seconds is None:
        args.left_seconds = nominal_seconds
    if args.right_seconds is None:
        args.right_seconds = (TURN_COMMAND_AREA * RIGHT_TURN_AREA_SCALE /
                              args.turn_angular + args.turn_ramp_seconds)
    if args.left_seconds > 15 or args.right_seconds > 15:
        parser.error("A single turn cannot exceed 15 seconds")
    if args.approach_seconds > 5:
        parser.error("The approach cannot exceed 5 seconds")
    return args


def turn_angular_at(elapsed, seconds, peak, ramp_seconds):
    ramp = min(ramp_seconds, seconds / 2.0)
    factor = max(0.0, min(1.0, elapsed / ramp, (seconds - elapsed) / ramp))
    return peak * factor


def load_action(filename):
    path = pathlib.Path(filename)
    if not path.is_file():
        raise RuntimeError("Arm action file missing: " + str(path))
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Arm action database failed integrity check")
        rows = db.execute(
            "SELECT Time,Servo1,Servo2,Servo3,Servo4,Servo5,Servo6 "
            "FROM ActionGroup ORDER BY [Index]"
        ).fetchall()
    if not rows:
        raise RuntimeError("Arm action contains no frames")
    for row in rows:
        if any(type(value) is not int for value in row):
            raise RuntimeError("Arm frame must contain integer values")
        if not 1 <= row[0] <= 10000 or any(not 0 <= value <= 1000 for value in row[1:]):
            raise RuntimeError("Invalid arm frame duration or servo position")
    if sum(row[0] for row in rows) > 30000:
        raise RuntimeError("Arm action exceeds 30 seconds")
    return rows


def show_plan(args):
    print("Smooth turn: peak=%.2f, ramp up/down=%.2f s each. "
          "Turn durations are initial estimates; calibrate on the actual floor." % (
              args.turn_angular, args.turn_ramp_seconds))
    if args.calibrate_turn:
        seconds = args.left_seconds if args.calibrate_turn == "left" else args.right_seconds
        print("TURN ONLY: %s, peak angular=%+.2f, total duration=%.3f s" % (
            args.calibrate_turn,
            args.turn_angular * args.left_sign * (1 if args.calibrate_turn == "left" else -1),
            seconds))
        return
    print("Servo 5 is skipped: no commands or feedback checks. "
          "Load active joints at their measured positions before commanding motion. "
          "Restore initial arm joints 2,3,4,6 before forward motion and after the arm action; "
          "confirm the initial pose again after the return turn. Gripper keeps its position.")
    for cycle in range(1, args.cycles + 1):
        print("CYCLE %d/%d: forward %d mm/s for %.1f s -> stop %.1f s -> "
              "rotate LEFT for %.3f s -> forward %.1f s -> stop -> arm action %s -> "
              "restore arm -> reverse %.1f s -> stop -> rotate RIGHT for %.3f s "
              "-> confirm initial arm pose -> stop" % (
                  cycle, args.cycles, SPEED, FORWARD_SECONDS, WAIT_SECONDS,
                  args.left_seconds, args.approach_seconds, args.action_file,
                  args.approach_seconds, args.right_seconds))


class TimedChassisDemo:
    def __init__(self, args, rows):
        import rospy
        from chassis_control.msg import SetVelocity
        from ros_robot_controller.msg import BusServoState, GetBusServoCmd, SetBusServoState
        from ros_robot_controller.srv import GetBusServoState
        from std_srvs.srv import Trigger

        self.ros = rospy
        self.args = args
        self.rows = rows
        self.BusServoState = BusServoState
        self.GetBusServoCmd = GetBusServoCmd
        self.SetBusServoState = SetBusServoState
        self.Trigger = Trigger
        self.arm_active = False
        self.publisher = rospy.Publisher("/chassis_control/set_velocity", SetVelocity, queue_size=1)
        self.arm_publisher = rospy.Publisher(
            "/ros_robot_controller/bus_servo/set_state", SetBusServoState, queue_size=10)
        self.reader = rospy.ServiceProxy(
            "/ros_robot_controller/bus_servo/get_state", GetBusServoState)

    def wait_for_subscribers(self):
        deadline = time.monotonic() + 5
        while (self.publisher.get_num_connections() == 0 or
               (self.rows and self.arm_publisher.get_num_connections() == 0)):
            if self.ros.is_shutdown():
                raise RuntimeError("ROS is shutting down")
            if time.monotonic() >= deadline:
                raise RuntimeError("Chassis or arm controller subscriber unavailable")
            time.sleep(0.05)

    def publish_for(self, velocity, direction, angular, duration):
        end_time = time.monotonic() + duration
        while time.monotonic() < end_time:
            if self.ros.is_shutdown():
                raise RuntimeError("ROS is shutting down")
            self.publisher.publish(velocity, direction, angular)
            time.sleep(min(0.05, max(0, end_time - time.monotonic())))

    def stop(self):
        # The chassis driver ramps commands; keep sending zero while it settles.
        for _ in range(16):
            self.publisher.publish(0, 90, 0)
            time.sleep(0.05)

    def stop_arm(self):
        command = self.SetBusServoState()
        for servo_id in ACTIVE_ARM_SERVOS:
            state = self.BusServoState()
            state.present_id = [1, servo_id]
            state.stop = [1, 1]
            command.state.append(state)
        for _ in range(3):
            self.arm_publisher.publish(command)
            time.sleep(0.05)
        self.arm_active = False

    def exit_visual_control(self):
        for name in ("visual_patrol", "color_tracking", "face_detect", "apriltag_detect"):
            service_name = "/" + name + "/exit"
            self.ros.wait_for_service(service_name, timeout=3)
            if not self.ros.ServiceProxy(service_name, self.Trigger)().success:
                raise RuntimeError("Cannot exit competing visual controller: " + name)

    def read_arm(self):
        result = self.reader([
            self.GetBusServoCmd(id=i, get_position=1, get_position_limit=1)
            for i in ACTIVE_ARM_SERVOS
        ])
        if not result.success or len(result.state) != len(ACTIVE_ARM_SERVOS):
            raise RuntimeError("Cannot read all active servos")
        # Keep servo-ID indexing for action rows; servo 5 has no required feedback.
        states = [None] * 6
        for servo_id, state in zip(ACTIVE_ARM_SERVOS, result.state):
            if len(state.position) != 1 or len(state.position_limit) != 2:
                raise RuntimeError("Missing servo feedback: " + str(servo_id))
            states[servo_id - 1] = state
        return states

    def validate_arm(self):
        self.ros.wait_for_service("/ros_robot_controller/bus_servo/get_state", timeout=4)
        states = self.read_arm()
        for row in self.rows:
            for servo_id in ACTIVE_ARM_SERVOS:
                state, target = states[servo_id - 1], row[servo_id]
                low, high = state.position_limit
                if not low <= target <= high:
                    raise RuntimeError("Arm target outside limits: servo " + str(servo_id))
        for servo_id, target in INITIAL_ARM_POSE.items():
            low, high = states[servo_id - 1].position_limit
            if not low <= target <= high:
                raise RuntimeError("Initial arm pose outside limits: servo " + str(servo_id))

    def load_arm(self, servo_ids, states):
        # Set current targets first so loading cannot resume an old destination.
        hold = self.SetBusServoState()
        hold.duration = 0.2
        load = self.SetBusServoState()
        for servo_id in servo_ids:
            state = self.BusServoState()
            state.present_id = [1, servo_id]
            state.position = [1, states[servo_id - 1].position[0]]
            hold.state.append(state)
            state = self.BusServoState()
            state.present_id = [1, servo_id]
            state.enable_torque = [1, ARM_LOAD_VALUE]
            load.state.append(state)
        self.arm_active = True
        self.arm_publisher.publish(hold)
        self.publish_for(0, 90, 0, 0.3)
        self.arm_publisher.publish(load)
        self.publish_for(0, 90, 0, 0.1)
        self.arm_active = False

    def restore_initial_arm(self):
        states = self.read_arm()
        self.stop()
        self.load_arm(sorted(INITIAL_ARM_POSE), states)
        errors = {servo_id: states[servo_id - 1].position[0] - target
                  for servo_id, target in INITIAL_ARM_POSE.items()}
        if all(abs(error) <= INITIAL_ARM_TOLERANCE for error in errors.values()):
            self.ros.loginfo("Arm already at initial pose: %s", errors)
            return
        command = self.SetBusServoState()
        command.duration = 2.0
        for servo_id, target in sorted(INITIAL_ARM_POSE.items()):
            state = self.BusServoState()
            state.present_id = [1, servo_id]
            state.position = [1, target]
            command.state.append(state)
        self.arm_active = True
        try:
            self.arm_publisher.publish(command)
            self.publish_for(0, 90, 0, command.duration + 0.5)
            states = self.read_arm()
            errors = {servo_id: states[servo_id - 1].position[0] - target
                      for servo_id, target in INITIAL_ARM_POSE.items()}
            self.ros.loginfo("Initial arm pose feedback errors: %s", errors)
            if any(abs(error) > INITIAL_ARM_TOLERANCE for error in errors.values()):
                raise RuntimeError("Arm did not return to its initial pose; sequence stopped")
        finally:
            self.stop_arm()

    def turn(self, left):
        seconds = self.args.left_seconds if left else self.args.right_seconds
        angular = self.args.turn_angular * self.args.left_sign * (1 if left else -1)
        self.ros.loginfo("Smooth turn %s: peak=%.2f, total=%.3f seconds (initial estimate)",
                         "left" if left else "right", angular, seconds)
        try:
            started = time.monotonic()
            while True:
                elapsed = time.monotonic() - started
                if elapsed >= seconds:
                    break
                if self.ros.is_shutdown():
                    raise RuntimeError("ROS is shutting down")
                command = turn_angular_at(elapsed, seconds, angular, self.args.turn_ramp_seconds)
                self.publisher.publish(0, 90, command)
                time.sleep(min(0.05, max(0, seconds - elapsed)))
        finally:
            self.stop()

    def run_arm_action(self):
        self.validate_arm()
        self.load_arm(ACTIVE_ARM_SERVOS, self.read_arm())
        self.arm_active = True
        try:
            for row in self.rows:
                command = self.SetBusServoState()
                command.duration = row[0] / 1000.0
                for servo_id in ACTIVE_ARM_SERVOS:
                    target = row[servo_id]
                    state = self.BusServoState()
                    state.present_id = [1, servo_id]
                    state.position = [1, target]
                    command.state.append(state)
                self.arm_publisher.publish(command)
                self.publish_for(0, 90, 0, command.duration + 0.4)
            states = self.read_arm()
            errors = {servo_id: states[servo_id - 1].position[0] - self.rows[-1][servo_id]
                      for servo_id in ACTIVE_ARM_SERVOS}
            self.ros.loginfo("Arm feedback error (ticks): %s", errors)
            if any(abs(error) > 20 for error in errors.values()):
                raise RuntimeError("Arm did not reach target; sequence stopped")
        finally:
            self.stop_arm()

    def run(self):
        self.wait_for_subscribers()
        try:
            self.stop()
            self.exit_visual_control()
            if self.rows:
                self.validate_arm()
                self.restore_initial_arm()
            if self.args.calibrate_turn:
                self.turn(self.args.calibrate_turn == "left")
                return
            for cycle in range(1, self.args.cycles + 1):
                self.ros.loginfo("Starting cycle %d/%d", cycle, self.args.cycles)
                self.publish_for(SPEED, 90, 0, FORWARD_SECONDS)
                self.publish_for(0, 90, 0, WAIT_SECONDS)
                self.turn(left=True)
                self.publish_for(SPEED, 90, 0, self.args.approach_seconds)
                self.stop()
                self.run_arm_action()
                self.restore_initial_arm()
                self.publish_for(SPEED, 270, 0, self.args.approach_seconds)
                self.stop()
                self.turn(left=False)
                self.restore_initial_arm()
            self.ros.loginfo("All cycles complete")
        finally:
            try:
                self.stop()
            finally:
                if self.arm_active:
                    self.stop_arm()


def interrupted(signum, frame):
    raise KeyboardInterrupt()


def main():
    args = parse_args()
    show_plan(args)
    if args.dry_run:
        return
    rows = [] if args.calibrate_turn else load_action(args.action_file)
    import rospy
    rospy.init_node("forward_wait_left_demo", disable_signals=True)
    signal.signal(signal.SIGINT, interrupted)
    signal.signal(signal.SIGTERM, interrupted)
    TimedChassisDemo(args, rows).run()


if __name__ == "__main__":
    main()
