#!/usr/bin/env python3

"""
GPIO to Virtual Gamepad

Hardware Setup:
- Connect buttons between GPIO pins and GND
- Internal pull-up resistors are enabled in software

This script is tolerant to multiple config formats. Supported line formats:
  - pin,button
  - button,pin
  - pin:button
  - button:pin
  - pin=button
  - button=pin
  - pin button

Lines starting with '#' or empty lines are ignored. Button names are
case-insensitive and extra modifiers after a '|' or ';' are ignored.
"""

from gpiozero import Button
from signal import pause
import os
import sys
import time
from evdev import UInput, ecodes as e, AbsInfo

CONFIG_FILE = os.path.expanduser("~/gpio_gamepad_config.txt")

BUTTON_MAP = {
    'BTN_SOUTH': getattr(e, 'BTN_SOUTH', None),
    'BTN_EAST': getattr(e, 'BTN_EAST', None),
    'BTN_NORTH': getattr(e, 'BTN_NORTH', None),
    'BTN_WEST': getattr(e, 'BTN_WEST', None),
    'BTN_TL': getattr(e, 'BTN_TL', None),
    'BTN_TR': getattr(e, 'BTN_TR', None),
    'BTN_SELECT': getattr(e, 'BTN_SELECT', None),
    'BTN_START': getattr(e, 'BTN_START', None),
    'BTN_THUMBL': getattr(e, 'BTN_THUMBL', None),
    'BTN_THUMBR': getattr(e, 'BTN_THUMBR', None),
    'DPAD_UP': ('dpad', getattr(e, 'BTN_DPAD_UP', None)),
    'DPAD_DOWN': ('dpad', getattr(e, 'BTN_DPAD_DOWN', None)),
    'DPAD_LEFT': ('dpad', getattr(e, 'BTN_DPAD_LEFT', None)),
    'DPAD_RIGHT': ('dpad', getattr(e, 'BTN_DPAD_RIGHT', None)),
}

JOYSTICK_MAP = {
    'JOY1_UP': ('analog', getattr(e, 'ABS_Y', None), -1),
    'JOY1_DOWN': ('analog', getattr(e, 'ABS_Y', None), 1),
    'JOY1_LEFT': ('analog', getattr(e, 'ABS_X', None), -1),
    'JOY1_RIGHT': ('analog', getattr(e, 'ABS_X', None), 1),

    'JOY2_UP': ('analog', getattr(e, 'ABS_RY', None), -1),
    'JOY2_DOWN': ('analog', getattr(e, 'ABS_RY', None), 1),
    'JOY2_LEFT': ('analog', getattr(e, 'ABS_RX', None), -1),
    'JOY2_RIGHT': ('analog', getattr(e, 'ABS_RX', None), 1),
}

MOUSE_MAP = {
    'MOUSE_UP': ('move', 'REL_Y', -1),
    'MOUSE_DOWN': ('move', 'REL_Y', 1),
    'MOUSE_LEFT': ('move', 'REL_X', -1),
    'MOUSE_RIGHT': ('move', 'REL_X', 1),
    'MOUSE_BTN_LEFT': ('click', getattr(e, 'BTN_LEFT', None)),
    'MOUSE_BTN_RIGHT': ('click', getattr(e, 'BTN_RIGHT', None)),
    'MOUSE_BTN_MIDDLE': ('click', getattr(e, 'BTN_MIDDLE', None)),
}


def parse_config_line(line):
    if not line:
        return None
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    if '#' in line:
        line = line.split('#', 1)[0].strip()
    for sep in ('|', ';'):
        if sep in line:
            line = line.split(sep, 1)[0].strip()
    separators = [',', ':', '=', '\t']
    for sep in separators:
        if sep in line:
            parts = [p.strip() for p in line.split(sep) if p.strip()]
            if len(parts) >= 2:
                a, b = parts[0], parts[1]
                try:
                    pin = int(a)
                    button = b
                except ValueError:
                    try:
                        pin = int(b)
                        button = a
                    except ValueError:
                        return None
                return (pin, button.upper())
    parts = line.split()
    if len(parts) >= 2:
        a, b = parts[0], parts[1]
        try:
            pin = int(a); button = b
            return (pin, button.upper())
        except ValueError:
            try:
                pin = int(b); button = a
                return (pin, button.upper())
            except ValueError:
                return None
    return None


class GPIOGamepad:
    def __init__(self, config_file):
        self.config = self.load_config(config_file)
        self.setup_gamepad()
        self.setup_mouse()
        self.buttons = []
        self.analog_state = {
            getattr(e, 'ABS_X', 0): 0,
            getattr(e, 'ABS_Y', 0): 0,
            getattr(e, 'ABS_RX', 0): 0,
            getattr(e, 'ABS_RY', 0): 0,
        }
        self.mouse_movement_active = {}
        self.mouse_vector = {'x': 0, 'y': 0}
        self.setup_buttons()

    def load_config(self, config_file):
        config = []
        mouse_speed = 5
        try:
            with open(config_file, 'r') as f:
                for lineno, raw in enumerate(f, start=1):
                    if raw.strip().startswith('MOUSE_SPEED='):
                        try:
                            mouse_speed = int(raw.strip().split('=')[1])
                            print(f"Mouse speed set to: {mouse_speed}")
                            continue
                        except (ValueError, IndexError):
                            print(f"Warning: Invalid MOUSE_SPEED on line {lineno}, using default: 5")
                            continue
                    parsed = parse_config_line(raw)
                    if not parsed:
                        continue
                    gpio_pin, button = parsed
                    button = button.split()[0].upper()
                    if button in BUTTON_MAP or button in JOYSTICK_MAP or button in MOUSE_MAP:
                        config.append((gpio_pin, button))
                        print(f"Configured GPIO {gpio_pin} -> {button}")
                    else:
                        print(f"Warning: Unknown button '{button}' on line {lineno}")
        except FileNotFoundError:
            print(f"Error: Config file not found: {config_file}")
            sys.exit(1)
        if not config:
            print("Error: No valid button mappings found.")
            sys.exit(1)
        self.mouse_speed = mouse_speed
        return config

    def setup_gamepad(self):
        key_codes = [v for v in BUTTON_MAP.values() if v is not None and not isinstance(v, tuple)]
        dpad_codes = [v[1] for v in BUTTON_MAP.values() if isinstance(v, tuple) and v[0] == 'dpad' and v[1] is not None]
        key_codes.extend(dpad_codes)
        abs_caps = []
        for axis in ('ABS_X', 'ABS_Y', 'ABS_RX', 'ABS_RY'):
            code = getattr(e, axis, None)
            if code is not None:
                abs_caps.append((code, AbsInfo(0, -32767, 32767, 0, 0, 0)))
        cap = {}
        if key_codes:
            cap[e.EV_KEY] = key_codes
        if abs_caps:
            cap[e.EV_ABS] = abs_caps
        self.gamepad = UInput(cap, name="GPIO-Virtual-Gamepad", version=0x3)
        print("Virtual gamepad created: GPIO-Virtual-Gamepad")
        time.sleep(1)

    def setup_mouse(self):
        mouse_cap = {
            e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL],
            e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE]
        }
        self.mouse = UInput(mouse_cap, name="GPIO-Virtual-Mouse", version=0x3)
        print("Virtual mouse created: GPIO-Virtual-Mouse")
        time.sleep(1)

    def setup_buttons(self):
        for gpio_pin, button_name in self.config:
            btn = Button(gpio_pin, pull_up=True, bounce_time=0.02)
            btn.when_pressed = lambda b=button_name: self.press(b)
            btn.when_released = lambda b=button_name: self.release(b)
            self.buttons.append(btn)
            print(f"Button attached: GPIO {gpio_pin} → {button_name}")
        print("\nReady! Waiting for button presses...\n")

    def press(self, button_name):
        timestamp = time.strftime('%H:%M:%S')
        if button_name in BUTTON_MAP:
            mapping = BUTTON_MAP[button_name]
            if isinstance(mapping, tuple):
                if mapping[0] == 'dpad' and mapping[1] is not None:
                    self.gamepad.write(e.EV_KEY, mapping[1], 1)
                    self.gamepad.syn()
                    print(f"[{timestamp}] {button_name} PRESSED")
                    return
            elif mapping is not None:
                self.gamepad.write(e.EV_KEY, mapping, 1)
                self.gamepad.syn()
                print(f"[{timestamp}] {button_name} PRESSED")
                return
        if button_name in JOYSTICK_MAP:
            mapping = JOYSTICK_MAP[button_name]
            if mapping[0] == 'dpad' and mapping[1] is not None:
                self.gamepad.write(e.EV_KEY, mapping[1], 1)
                self.gamepad.syn()
                print(f"[{timestamp}] {button_name} PRESSED")
                return
            elif mapping[0] == 'analog' and mapping[1] is not None:
                axis = mapping[1]
                direction = mapping[2]
                value = direction * 32767
                self.analog_state[axis] = value
                self.gamepad.write(e.EV_ABS, axis, value)
                self.gamepad.syn()
                print(f"[{timestamp}] {button_name} PRESSED (axis={axis}, value={value})")
                return
        if button_name in MOUSE_MAP:
            mapping = MOUSE_MAP[button_name]
            if mapping[0] == 'move':
                axis = mapping[1]
                direction = mapping[2]
                if axis == 'REL_X':
                    self.mouse_vector['x'] = direction
                elif axis == 'REL_Y':
                    self.mouse_vector['y'] = direction
                was_moving = any(self.mouse_movement_active.values())
                self.mouse_movement_active[button_name] = True
                if not was_moving:
                    import threading
                    import math
                    def move_mouse():
                        while any(self.mouse_movement_active.values()):
                            x = self.mouse_vector['x']
                            y = self.mouse_vector['y']
                            magnitude = math.sqrt(x*x + y*y)
                            if magnitude > 0:
                                norm_x = (x / magnitude) * self.mouse_speed
                                norm_y = (y / magnitude) * self.mouse_speed
                                if x != 0:
                                    self.mouse.write(e.EV_REL, e.REL_X, int(norm_x))
                                if y != 0:
                                    self.mouse.write(e.EV_REL, e.REL_Y, int(norm_y))
                                self.mouse.syn()
                            time.sleep(0.01)
                    threading.Thread(target=move_mouse, daemon=True).start()
                print(f"[{timestamp}] {button_name} PRESSED (mouse movement started)")
                return
            elif mapping[0] == 'click' and mapping[1] is not None:
                self.mouse.write(e.EV_KEY, mapping[1], 1)
                self.mouse.syn()
                print(f"[{timestamp}] {button_name} PRESSED")
                return
        print(f"[{timestamp}] Unhandled press: {button_name}")

    def release(self, button_name):
        timestamp = time.strftime('%H:%M:%S')
        if button_name in BUTTON_MAP:
            mapping = BUTTON_MAP[button_name]
            if isinstance(mapping, tuple):
                if mapping[0] == 'dpad' and mapping[1] is not None:
                    self.gamepad.write(e.EV_KEY, mapping[1], 0)
                    self.gamepad.syn()
                    print(f"[{timestamp}] {button_name} RELEASED")
                    return
            elif mapping is not None:
                self.gamepad.write(e.EV_KEY, mapping, 0)
                self.gamepad.syn()
                print(f"[{timestamp}] {button_name} RELEASED")
                return
        if button_name in JOYSTICK_MAP:
            mapping = JOYSTICK_MAP[button_name]
            if mapping[0] == 'dpad' and mapping[1] is not None:
                self.gamepad.write(e.EV_KEY, mapping[1], 0)
                self.gamepad.syn()
                print(f"[{timestamp}] {button_name} RELEASED")
                return
            elif mapping[0] == 'analog' and mapping[1] is not None:
                axis = mapping[1]
                self.analog_state[axis] = 0
                self.gamepad.write(e.EV_ABS, axis, 0)
                self.gamepad.syn()
                print(f"[{timestamp}] {button_name} RELEASED (axis={axis}, centered)")
                return
        if button_name in MOUSE_MAP:
            mapping = MOUSE_MAP[button_name]
            if mapping[0] == 'move':
                axis = mapping[1]
                if axis == 'REL_X':
                    self.mouse_vector['x'] = 0
                elif axis == 'REL_Y':
                    self.mouse_vector['y'] = 0
                self.mouse_movement_active[button_name] = False
                print(f"[{timestamp}] {button_name} RELEASED (mouse movement stopped)")
                return
            elif mapping[0] == 'click' and mapping[1] is not None:
                self.mouse.write(e.EV_KEY, mapping[1], 0)
                self.mouse.syn()
                print(f"[{timestamp}] {button_name} RELEASED")
                return
        print(f"[{timestamp}] Unhandled release: {button_name}")

    def run(self):
        try:
            pause()
        except KeyboardInterrupt:
            print("\nExiting...")
        finally:
            self.cleanup()

    def cleanup(self):
        try:
            self.gamepad.close()
        except Exception:
            pass
        try:
            self.mouse.close()
        except Exception:
            pass
        print("Cleanup complete.")


if __name__ == "__main__":
    print("=" * 50)
    print("GPIO to Virtual Gamepad")
    print("=" * 50 + "\n")
    gamepad = GPIOGamepad(CONFIG_FILE)
    gamepad.run()
