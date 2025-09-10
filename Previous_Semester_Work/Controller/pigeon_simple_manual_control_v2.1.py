import clr
import MissionPlanner
import time
from System.Windows.Forms import Form, TrackBar, Button, Label, Application, Timer, TextBox, ScrollBars
from System.Drawing import Size, Point

# Constants
RC_CHANNEL_THROTTLE = 3
RC_CHANNEL_RUDDER = 1
NEUTRAL_PWM = 1500

class ServoControlGUI(Form):
    def __init__(self):
        # Increase form height to accommodate the new command input
        self.Text = "Boat Servo Control"
        self.Width = 400
        self.Height = 600

        # Flag to indicate if the rudder slider is being dragged
        self.rudder_dragging = False

        # Throttle Label and Slider
        self.label_throttle = Label()
        self.label_throttle.Text = f"RC Channel {RC_CHANNEL_THROTTLE} Output: 1000 µs"
        self.label_throttle.Top = 20
        self.label_throttle.Left = 50
        self.Controls.Add(self.label_throttle)

        self.slider_throttle = TrackBar()
        self.slider_throttle.Minimum = 1000
        self.slider_throttle.Maximum = 2000
        self.slider_throttle.Value = 1000  # Default set to 1000 µs
        self.slider_throttle.TickFrequency = 50
        self.slider_throttle.Top = 50
        self.slider_throttle.Width = 300
        self.slider_throttle.Scroll += self.update_throttle
        self.Controls.Add(self.slider_throttle)

        # Rudder Label and Slider
        self.label_rudder = Label()
        self.label_rudder.Text = f"RC Channel {RC_CHANNEL_RUDDER} Output: {NEUTRAL_PWM} µs"
        self.label_rudder.Top = 100
        self.label_rudder.Left = 50
        self.Controls.Add(self.label_rudder)

        self.slider_rudder = TrackBar()
        self.slider_rudder.Minimum = 1000
        self.slider_rudder.Maximum = 2000
        self.slider_rudder.Value = NEUTRAL_PWM
        self.slider_rudder.TickFrequency = 50
        self.slider_rudder.Top = 130
        self.slider_rudder.Width = 300
        self.slider_rudder.Scroll += self.update_rudder
        self.slider_rudder.MouseDown += self.rudder_mouse_down
        self.slider_rudder.MouseUp += self.rudder_mouse_up
        self.Controls.Add(self.slider_rudder)

        # Arm Button
        self.arm_button = Button()
        self.arm_button.Text = "ARM"
        self.arm_button.Top = 200
        self.arm_button.Left = 50
        self.arm_button.Click += self.arm_fc
        self.Controls.Add(self.arm_button)

        # Disarm Button
        self.disarm_button = Button()
        self.disarm_button.Text = "DISARM"
        self.disarm_button.Top = 200
        self.disarm_button.Left = 150
        self.disarm_button.Click += self.disarm_fc
        self.Controls.Add(self.disarm_button)

        # AUTO Mode Button
        self.auto_button = Button()
        self.auto_button.Text = "AUTO MODE"
        self.auto_button.Top = 250
        self.auto_button.Left = 50
        self.auto_button.Click += self.set_auto_mode
        self.Controls.Add(self.auto_button)

        # MANUAL Mode Button
        self.manual_button = Button()
        self.manual_button.Text = "MANUAL MODE"
        self.manual_button.Top = 250
        self.manual_button.Left = 150
        self.manual_button.Click += self.set_manual_mode
        self.Controls.Add(self.manual_button)

        # Chatbox for logging messages (read-only)
        self.chatBox = TextBox()
        self.chatBox.Multiline = True
        self.chatBox.ScrollBars = ScrollBars.Vertical
        self.chatBox.ReadOnly = True
        self.chatBox.Top = 300
        self.chatBox.Left = 10
        self.chatBox.Width = 360
        self.chatBox.Height = 100
        self.Controls.Add(self.chatBox)

        # Command Input TextBox (for entering MAVLink commands)
        self.txtCommandInput = TextBox()
        self.txtCommandInput.Multiline = False
        self.txtCommandInput.Top = 410
        self.txtCommandInput.Left = 10
        self.txtCommandInput.Width = 260
        # Removed the line: self.txtCommandInput.PlaceholderText = "Enter MAVLink command..."
        self.Controls.Add(self.txtCommandInput)

        # Send Command Button
        self.send_button = Button()
        self.send_button.Text = "SEND COMMAND"
        self.send_button.Top = 410
        self.send_button.Left = 280
        self.send_button.Width = 100
        self.send_button.Click += self.send_command
        self.Controls.Add(self.send_button)

        # Terminate Button for MAVLink termination command
        self.terminate_button = Button()
        self.terminate_button.Text = "TERMINATE"
        self.terminate_button.Top = 450
        self.terminate_button.Left = 50
        self.terminate_button.Click += self.terminate_fc
        self.Controls.Add(self.terminate_button)

        # Timer for rudder auto-centering (act every 0.1 seconds)
        self.timer_rudder = Timer()
        self.timer_rudder.Interval = 100  # 100 ms
        self.timer_rudder.Tick += self.center_rudder
        self.inactive_time_rudder = 0

    # Throttle update (no auto-center)
    def update_throttle(self, sender, event):
        pwm = self.slider_throttle.Value
        self.label_throttle.Text = f"RC Channel {RC_CHANNEL_THROTTLE} Output: {pwm} µs"
        Script.SendRC(RC_CHANNEL_THROTTLE, pwm, True)

    # Rudder update (with auto-center)
    def update_rudder(self, sender, event):
        pwm = self.slider_rudder.Value
        self.label_rudder.Text = f"RC Channel {RC_CHANNEL_RUDDER} Output: {pwm} µs"
        Script.SendRC(RC_CHANNEL_RUDDER, pwm, True)
        self.inactive_time_rudder = 0
        self.timer_rudder.Start()

    def center_rudder(self, sender, event):
        if self.rudder_dragging:
            return

        self.inactive_time_rudder += 1
        if self.inactive_time_rudder < 1:
            return

        current = self.slider_rudder.Value
        if current > NEUTRAL_PWM:
            new_val = max(NEUTRAL_PWM, current - 13)
            self.slider_rudder.Value = new_val
        elif current < NEUTRAL_PWM:
            new_val = min(NEUTRAL_PWM, current + 13)
            self.slider_rudder.Value = new_val
        else:
            self.timer_rudder.Stop()
        self.update_rudder(None, None)

    # Mouse event handlers to detect when the rudder slider is being dragged
    def rudder_mouse_down(self, sender, event):
        self.rudder_dragging = True

    def rudder_mouse_up(self, sender, event):
        self.rudder_dragging = False

    # Arm/Disarm functions
    def arm_fc(self, sender, event):
        self.logMessage("Arming Flight Controller...")
        MAV.doARM(True)
        time.sleep(2)
        self.logMessage("Flight Controller Armed.")

    def disarm_fc(self, sender, event):
        self.logMessage("Disarming Flight Controller...")
        MAV.doARM(False)
        time.sleep(2)
        self.logMessage("Flight Controller Disarmed.")

    # Mode switching functions
    def set_auto_mode(self, sender, event):
        self.logMessage("Switching to AUTO mode...")
        Script.ChangeMode("AUTO")

    def set_manual_mode(self, sender, event):
        self.logMessage("Switching to MANUAL mode...")
        Script.ChangeMode("MANUAL")

    # Terminate function - sends a termination message via MAVLink
    def terminate_fc(self, sender, event):
        self.logMessage("Terminating communication via MAVLink...")
        # Insert the appropriate MAVLink termination command here:
        # For example: Script.SendMavlink("TERMINATE")
        self.logMessage("Termination command sent.")

    # Send Command function - reads command from input box and sends it
    def send_command(self, sender, event):
        command_text = self.txtCommandInput.Text.strip()
        if command_text != "":
            self.logMessage(f"Sending command: {command_text}")
            try:
                # Example: Send the command over MAVLink.
                MAV.doCommand(command_text);
                self.logMessage("Command sent successfully.")
            except Exception as ex:
                self.logMessage(f"Error sending command: {ex}")
            self.txtCommandInput.Text = ""
        else:
            self.logMessage("No command entered.")

    def logMessage(self, message):
        # Append message to the chatbox with a timestamp
        timestamp = time.strftime("%H:%M:%S")
        self.chatBox.AppendText(f"[{timestamp}] {message}\r\n")

# Launch the GUI application
form = ServoControlGUI()
Application.Run(form)
