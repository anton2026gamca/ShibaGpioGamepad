#!/bin/bash

# ============================================
# Raspberry Pi Setup Script for Shiba Arcade
# ============================================

set -e

if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    CYAN=''
    BOLD=''
    RESET=''
fi

cecho() { printf "%b\n" "$1$2$RESET"; }
err() { printf "%b\n" "$RED$1$RESET" >&2; }
info() { cecho "$CYAN" "$1"; }
ok() { cecho "$GREEN" "$1"; }
warn() { cecho "$YELLOW" "$1"; }
if [ "$EUID" -ne 0 ]; then 
    err "Please run with sudo"
    exit 1
fi

ACTUAL_USER=${SUDO_USER:-$USER}
if [ "$ACTUAL_USER" = "root" ]; then
    err "Please run this script with sudo, not as root user directly"
    exit 1
fi

USER_HOME=$(eval echo ~$ACTUAL_USER)
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)


cecho "=========================================="
cecho "Raspberry Pi Setup Script"
cecho "=========================================="
echo ""
info "Setting up for user: $ACTUAL_USER"
info "Home directory: $USER_HOME"
echo ""

# ============================================
# PART 1: Game Auto-Start Setup
# ============================================

read -p "$(printf '%b' "${YELLOW}Do you want to set up auto-start for a game? (y/n) > ${RESET}")" SETUP_GAME

if [ "$SETUP_GAME" = "y" ] || [ "$SETUP_GAME" = "Y" ]; then
    echo ""
    cecho "=========================================="
    cecho "Game Auto-Start Setup"
    cecho "=========================================="
    echo ""
    
    read -p "Please enter the full path to the game executable: " EXECUTABLE_PATH
    
    if [ ! -f "$EXECUTABLE_PATH" ]; then
        err "Error: Executable not found at $EXECUTABLE_PATH"
        exit 1
    fi
    
    if [ ! -x "$EXECUTABLE_PATH" ]; then
        info "Making it executable..."
        chmod +x "$EXECUTABLE_PATH"
    fi
    
    echo ""
    info "Setting up desktop autostart..."
    
    mkdir -p "$USER_HOME/.config/autostart"
    
    cat > "$USER_HOME/.config/autostart/game-autostart.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Game Autostart
Exec=$EXECUTABLE_PATH
X-GNOME-Autostart-enabled=true
EOF
    
    chown -R $ACTUAL_USER:$ACTUAL_USER "$USER_HOME/.config/autostart"
    
    ok "Game autostart configured"
    info "  Executable: $EXECUTABLE_PATH"
    echo ""
fi

# ============================================
# PART 2: GPIO to Virtual Gamepad Setup
# ============================================

cecho "=========================================="
cecho "GPIO to Virtual Gamepad Setup"
cecho "=========================================="
echo ""

info "Installing GPIO gamepad packages..."
apt update
apt install -y python3 python3-pip python3-dev

pip3 install --break-system-packages evdev gpiozero

echo ""
echo "=========================================="
echo "Raspberry Pi 5 GPIO Pinout"
echo "=========================================="
echo ""
echo "    3V3  (1) (2)  5V       "
echo "  GPIO2  (3) (4)  5V       "
echo "  GPIO3  (5) (6)  GND      "
echo "  GPIO4  (7) (8)  GPIO14   "
echo "    GND  (9) (10) GPIO15   "
echo " GPIO17 (11) (12) GPIO18   "
echo " GPIO27 (13) (14) GND      "
echo " GPIO22 (15) (16) GPIO23   "
echo "    3V3 (17) (18) GPIO24   "
echo " GPIO10 (19) (20) GND      "
echo "  GPIO9 (21) (22) GPIO25   "
echo " GPIO11 (23) (24) GPIO8    "
echo "    GND (25) (26) GPIO7    "
echo "  GPIO0 (27) (28) GPIO1    "
echo "  GPIO5 (29) (30) GND      "
echo "  GPIO6 (31) (32) GPIO12   "
echo " GPIO13 (33) (34) GND      "
echo " GPIO19 (35) (36) GPIO16   "
echo " GPIO26 (37) (38) GPIO20   "
echo "    GND (39) (40) GPIO21   "
echo ""
echo "Common GPIO pins for buttons: 17, 27, 22, 23, 24, 25, 5, 6, 12, 13, 16, 19, 20, 21, 26"
echo ""
echo "=========================================="
echo "Available Gamepad Buttons"
echo "=========================================="
echo ""
echo "  BTN_SOUTH        - A button (PlayStation Cross)"
echo "  BTN_EAST         - B button (PlayStation Circle)"
echo "  BTN_NORTH        - X button (PlayStation Triangle)"
echo "  BTN_WEST         - Y button (PlayStation Square)"
echo "  BTN_TL           - L1 / Left Bumper"
echo "  BTN_TR           - R1 / Right Bumper"
echo "  BTN_SELECT       - Select / Back button"
echo "  BTN_START        - Start button"
echo "  BTN_THUMBL       - L3 (Left stick click)"
echo "  BTN_THUMBR       - R3 (Right stick click)"
echo "  DPAD_UP          - D-pad Up"
echo "  DPAD_DOWN        - D-pad Down"
echo "  DPAD_LEFT        - D-pad Left"
echo "  DPAD_RIGHT       - D-pad Right"
echo "  JOY1_UP          - Joystick 1 Up"
echo "  JOY1_DOWN        - Joystick 1 Down"
echo "  JOY1_LEFT        - Joystick 1 Left"
echo "  JOY1_RIGHT       - Joystick 1 Right"
echo "  JOY2_UP          - Joystick 2 Up"
echo "  JOY2_DOWN        - Joystick 2 Down"
echo "  JOY2_LEFT        - Joystick 2 Left"
echo "  JOY2_RIGHT       - Joystick 2 Right"
echo "  MOUSE_UP         - Mouse Up"
echo "  MOUSE_DOWN       - Mouse Down"
echo "  MOUSE_LEFT       - Mouse Left"
echo "  MOUSE_RIGHT      - Mouse Right"
echo "  MOUSE_BTN_LEFT   - Mouse Left Click"
echo "  MOUSE_BTN_RIGHT  - Mouse Right Click"
echo "  MOUSE_BTN_MIDDLE - Mouse Middle Click"
echo ""
echo ""
warn "Press Enter to continue..."
read

CONFIG_FILE="$SCRIPT_DIR/gpio_gamepad_config.txt"
> "$CONFIG_FILE"

echo ""
echo "How many buttons would you like to configure?"
read -p "$(printf '%b' "${YELLOW}> ${RESET}")" NUM_BUTTONS

HAS_MOUSE_KEYBIND=false

for ((i=1; i<=NUM_BUTTONS; i++)); do
    echo ""
    echo "Button $i/$NUM_BUTTONS:"
    
    while true; do
    read -p "$(printf '%b' "${YELLOW}  GPIO pin (e.g. GPIO27 (13) -> 27): ${RESET}")" GPIO_PIN
        if [[ "$GPIO_PIN" =~ ^[0-9]+$ ]]; then
            break
        else
            err "  Error: Please enter a valid number"
        fi
    done
    
    VALID_BUTTONS=(
        "BTN_SOUTH" "BTN_EAST" "BTN_NORTH" "BTN_WEST" "BTN_TL" "BTN_TR" "BTN_SELECT" "BTN_START" "BTN_THUMBL" "BTN_THUMBR"
        "DPAD_UP" "DPAD_DOWN" "DPAD_LEFT" "DPAD_RIGHT"
        "JOY1_UP" "JOY1_DOWN" "JOY1_LEFT" "JOY1_RIGHT"
        "JOY2_UP" "JOY2_DOWN" "JOY2_LEFT" "JOY2_RIGHT"
        "JOY3_UP" "JOY3_DOWN" "JOY3_LEFT" "JOY3_RIGHT"
        "MOUSE_UP" "MOUSE_DOWN" "MOUSE_LEFT" "MOUSE_RIGHT"
        "MOUSE_BTN_LEFT" "MOUSE_BTN_RIGHT" "MOUSE_BTN_MIDDLE"
    )
    
    while true; do
        read -p "$(printf '%b' "${YELLOW}  Button mapping: ${RESET}")" BUTTON_MAP

        BUTTON_MAP=$(echo "$BUTTON_MAP" | tr '[:lower:]' '[:upper:]' | xargs)

        if [[ " ${VALID_BUTTONS[@]} " =~ " ${BUTTON_MAP} " ]]; then
            echo "$GPIO_PIN,$BUTTON_MAP" >> "$CONFIG_FILE"
            ok "  ✓ GPIO $GPIO_PIN -> $BUTTON_MAP"
            if [[ "$BUTTON_MAP" == MOUSE_* ]]; then
                HAS_MOUSE_KEYBIND=true
            fi
            break
        else
            err "  Error: Invalid button mapping '$BUTTON_MAP'"
        fi
    done
done

if [ "$HAS_MOUSE_KEYBIND" = true ]; then
    echo ""
    echo "Configure mouse speed (pixels per movement):"
    read -p "$(printf '%b' "${YELLOW}Mouse speed (1-20, default 5): ${RESET}")" MOUSE_SPEED
    if [[ ! "$MOUSE_SPEED" =~ ^[0-9]+$ ]] || [ "$MOUSE_SPEED" -lt 1 ] || [ "$MOUSE_SPEED" -gt 20 ]; then
        warn "Invalid speed, using default: 5"
        MOUSE_SPEED=5
    fi
    echo "MOUSE_SPEED=$MOUSE_SPEED" >> "$CONFIG_FILE"
    ok "Mouse speed set to: $MOUSE_SPEED"
fi

chown $ACTUAL_USER:$ACTUAL_USER "$CONFIG_FILE"

echo ""
info "Setting up GPIO gamepad autostart..."

mkdir -p "$USER_HOME/.config/autostart"

cat > "$USER_HOME/.config/autostart/gpio-gamepad.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=GPIO Gamepad
Exec=/usr/bin/python3 -u $SCRIPT_DIR/gpio_gamepad.py
X-GNOME-Autostart-enabled=true
EOF

chown -R $ACTUAL_USER:$ACTUAL_USER "$USER_HOME/.config/autostart"

ok "GPIO gamepad autostart configured"

echo ""
info "Preparing the Python GPIO gamepad script..."


chmod +x "$SCRIPT_DIR/gpio_gamepad.py"
chown $ACTUAL_USER:$ACTUAL_USER "$SCRIPT_DIR/gpio_gamepad.py"

echo ""
info "Setting up permissions for uinput and GPIO access..."

usermod -a -G input $ACTUAL_USER
usermod -a -G gpio $ACTUAL_USER

cat > /etc/udev/rules.d/99-uinput.rules <<EOF
KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"
EOF

modprobe uinput
echo "uinput" >> /etc/modules

echo ""
info "Creating log directory..."

mkdir -p /var/log/gpio-gamepad
chown $ACTUAL_USER:$ACTUAL_USER /var/log/gpio-gamepad
chmod 755 /var/log/gpio-gamepad

udevadm control --reload-rules
udevadm trigger

echo ""
cecho "$BOLD$GREEN" "=========================================="
cecho "$BOLD$GREEN" "Setup Complete!"
cecho "$BOLD$GREEN" "=========================================="
echo ""

if [ "$SETUP_GAME" = "y" ] || [ "$SETUP_GAME" = "Y" ]; then
    cecho "Game Configuration:"
    info "  Executable:  $EXECUTABLE_PATH"
    info "  Autostart:   ~/.config/autostart/game-autostart.desktop"
    echo ""
fi

cecho "GPIO Gamepad Configuration:"
cat "$CONFIG_FILE" | while IFS=',' read -r pin button; do
    info "  GPIO $pin → $button"
done
echo ""
cecho "Files:"
info "  Config:     $CONFIG_FILE"
info "  Script:     $SCRIPT_DIR/gpio_gamepad.py"
info "  Autostart:  ~/.config/autostart/gpio-gamepad.desktop"
if [ "$SETUP_GAME" = "y" ] || [ "$SETUP_GAME" = "Y" ]; then
    info "  Game start: ~/.config/autostart/game-autostart.desktop"
fi
echo ""
echo ""
info "Hardware: [GPIO] ←→ [Button] ←→ [GND]"
echo ""

echo ""
ok "All done!"
echo ""

echo ""
info "Reboot to apply changes."

read -p "Do you want to reboot now? (y/n) " REBOOT_NOW
if [ "$REBOOT_NOW" = "y" ] || [ "$REBOOT_NOW" = "Y" ]; then
    info "Rebooting..."
    reboot
fi
