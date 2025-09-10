import time
import serial.tools.list_ports
from pymavlink import mavutil

def find_pixhawk_port():
    """Automatically detect the Pixhawk COM port on Windows."""
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        print(f"Checking {port.device} - {port.description}")
        
        # Look for Pixhawk-related keywords in the description
        if "Silicon Labs" in port.description or "FTDI" in port.description or "USB Serial" in port.description:
            print(f"Found Pixhawk on {port.device}")
            return port.device
    
    print("No Pixhawk detected. Check connections.")
    return None

# Auto-detect Pixhawk COM port
serial_port = find_pixhawk_port()
if serial_port is None:
    exit()

# Connect to the flight controller
baud_rate = 57600 
print(f"Connecting to Pixhawk on {serial_port} at {baud_rate} baud...")
master = mavutil.mavlink_connection(serial_port, baud=baud_rate)

# Wait for the heartbeat from Pixhawk
print("Waiting for heartbeat...")
master.wait_heartbeat()
print("Connected! MAVLink heartbeat received.")

# Read and display telemetry data
while True:
    msg = master.recv_match(blocking=True)
    if msg:
        print(f"<< {msg.get_type()} >>: {msg}")
    time.sleep(1)

