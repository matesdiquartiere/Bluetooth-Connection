# Raspberry Pi 4 Bluetooth Signal Strength Monitor

This repository contains three Python scripts for monitoring Bluetooth signal strength on a Raspberry Pi 4:

1. `bleak_bluetooth_signal.py` - **RECOMMENDED** - For Bluetooth Low Energy (BLE) devices using the modern `bleak` library
2. `bluetooth_signal_strength.py` - For BLE devices using the `bluepy` library (may have installation issues on newer systems)
3. `classic_bluetooth_signal.py` - For Classic Bluetooth devices using the `pybluez` library and system tools

All scripts allow you to scan for nearby Bluetooth devices, connect to a specific device, and monitor its signal strength (RSSI - Received Signal Strength Indicator) in real-time.

> **NOTE:** We recommend using the `bleak_bluetooth_signal.py` script as it uses a more modern, actively maintained library that works across platforms and is less likely to have installation issues.

## Requirements

### For Bleak BLE Script (bleak_bluetooth_signal.py) - RECOMMENDED
- Raspberry Pi 4 with Bluetooth capability
- Python 3.7 or higher
- BlueZ stack (usually pre-installed on Raspberry Pi OS)
- `bleak` library

### For BlueZ BLE Script (bluetooth_signal_strength.py)
- Raspberry Pi 4 with Bluetooth capability
- Python 3.6 or higher
- BlueZ stack (usually pre-installed on Raspberry Pi OS)
- `bluepy` library (Note: This library may have installation issues on newer systems)

### For Classic Bluetooth Script (classic_bluetooth_signal.py)
- Raspberry Pi 4 with Bluetooth capability
- Python 3.6 or higher
- BlueZ stack (usually pre-installed on Raspberry Pi OS)
- `pybluez` library
- System Bluetooth tools (bluetooth, libbluetooth-dev)

## Installation

1. Make sure your Raspberry Pi's Bluetooth is enabled:
   ```bash
   sudo systemctl status bluetooth
   ```

2. Install the required dependencies:

   For Bleak BLE script (RECOMMENDED):
   ```bash
   pip3 install bleak
   ```

   For BlueZ BLE script (may have installation issues):
   ```bash
   sudo pip3 install bluepy
   ```
   
   > Note: If you encounter `legacy-install-failure` errors with bluepy, use the bleak script instead.

   For Classic Bluetooth script:
   ```bash
   sudo apt-get install bluetooth libbluetooth-dev
   sudo pip3 install pybluez
   ```

3. Make the scripts executable:
   ```bash
   chmod +x bleak_bluetooth_signal.py
   chmod +x bluetooth_signal_strength.py
   chmod +x classic_bluetooth_signal.py
   ```

## Usage

The classic Bluetooth script needs to be run with root privileges. The bleak script can often be run without sudo.

### Bleak BLE Script (bleak_bluetooth_signal.py) - RECOMMENDED

```bash
python3 bleak_bluetooth_signal.py [options]
```

#### Options

- `-s, --scan`: Scan for nearby BLE devices
- `-t, --time TIME`: Scan duration in seconds (default: 10)
- `-a, --address ADDRESS`: MAC address of the device to monitor
- `-i, --interval INTERVAL`: Interval between RSSI readings in seconds (default: 1.0)
- `-d, --duration DURATION`: Total monitoring duration in seconds (optional)
- `-c, --connect`: Attempt to connect to the device (optional, may not work with all devices)
- `-p, --power POWER`: Calibration value: RSSI at 1 meter distance (default: -59)
- `-n, --factor FACTOR`: Path loss exponent (2.0 for free space, 2.5-4.0 for indoors, default: 2.0)

### BlueZ BLE Script (bluetooth_signal_strength.py)

```bash
sudo python3 bluetooth_signal_strength.py [options]
```

#### Options

- `-s, --scan`: Scan for nearby BLE devices
- `-t, --time TIME`: Scan duration in seconds (default: 10)
- `-a, --address ADDRESS`: MAC address of the device to connect to
- `-i, --interval INTERVAL`: Interval between RSSI readings in seconds (default: 1.0)
- `-d, --duration DURATION`: Total monitoring duration in seconds (optional)

### Classic Bluetooth Script (classic_bluetooth_signal.py)

```bash
sudo python3 classic_bluetooth_signal.py [options]
```

#### Options

- `-s, --scan`: Scan for nearby classic Bluetooth devices
- `-t, --time TIME`: Scan duration in seconds (default: 10)
- `-a, --address ADDRESS`: MAC address of the device to connect to
- `-i, --interval INTERVAL`: Interval between RSSI readings in seconds (default: 1.0)
- `-d, --duration DURATION`: Total monitoring duration in seconds (optional)
- `-l, --list`: List available Bluetooth interfaces

### Examples

#### Bleak BLE Script (RECOMMENDED)

1. Scan for nearby BLE devices:
   ```bash
   python3 bleak_bluetooth_signal.py --scan
   ```

2. Scan for BLE devices and then monitor one interactively:
   ```bash
   python3 bleak_bluetooth_signal.py
   ```

3. Monitor a specific BLE device without connecting:
   ```bash
   python3 bleak_bluetooth_signal.py --address 12:34:56:78:90:AB
   ```

4. Attempt to connect to a BLE device and monitor its signal strength:
   ```bash
   python3 bleak_bluetooth_signal.py --address 12:34:56:78:90:AB --connect
   ```

5. Monitor a device and check signal strength every 2 seconds for 1 minute:
   ```bash
   python3 bleak_bluetooth_signal.py --address 12:34:56:78:90:AB --interval 2 --duration 60
   ```

6. Monitor with custom distance estimation calibration (for more accurate distance):
   ```bash
   python3 bleak_bluetooth_signal.py --address 12:34:56:78:90:AB --power -65 --factor 2.5
   ```

#### BlueZ BLE Script

1. Scan for nearby BLE devices:
   ```bash
   sudo python3 bluetooth_signal_strength.py --scan
   ```

2. Connect directly to a specific BLE device:
   ```bash
   sudo python3 bluetooth_signal_strength.py --address 12:34:56:78:90:AB
   ```

#### Classic Bluetooth Script

1. List available Bluetooth interfaces:
   ```bash
   sudo python3 classic_bluetooth_signal.py --list
   ```

2. Scan for nearby classic Bluetooth devices:
   ```bash
   sudo python3 classic_bluetooth_signal.py --scan
   ```

3. Connect directly to a specific classic Bluetooth device:
   ```bash
   sudo python3 classic_bluetooth_signal.py --address 12:34:56:78:90:AB
   ```

## Signal Strength and Distance Interpretation

### RSSI Values

The RSSI (Received Signal Strength Indicator) is measured in dBm (decibels relative to one milliwatt):

- -30 dBm: Excellent signal (very close proximity)
- -50 to -60 dBm: Good signal
- -70 to -80 dBm: Fair signal
- -90 dBm: Poor signal
- Below -100 dBm: Very poor or no signal

The script provides a visual bar representation of the signal strength for easier interpretation.

### Distance Estimation

The bleak script also estimates the approximate distance to the device based on the RSSI value. This estimation uses the following formula:

```
distance = 10^((TxPower - RSSI)/(10 * n))
```

Where:
- TxPower is the RSSI value at 1 meter (calibration value, default: -59)
- RSSI is the current signal strength reading
- n is the path loss exponent (2.0 for free space, 2.5-4.0 for indoor environments)

Distance categories:
- Very close: < 0.5 meters
- Close: 0.5 - 1 meter
- Near: 1 - 2 meters
- Medium distance: 2 - 5 meters
- Far: 5 - 10 meters
- Very far: > 10 meters

**Note on accuracy**: Distance estimation based on RSSI is approximate and can be affected by many factors including:
- Physical obstacles between devices
- Reflective surfaces
- Device orientation
- Environmental interference
- Differences in transmitter power between device models

For more accurate distance estimation, you can calibrate the script by:
1. Placing a device exactly 1 meter away from the Raspberry Pi
2. Running the script and noting the RSSI value
3. Using this value as the `--power` parameter in future runs

## Troubleshooting

1. If you get permission errors, make sure you're running the script with `sudo`.

2. If no devices are found, ensure:
   - Bluetooth is enabled on your Raspberry Pi
   - The target device is in discoverable mode
   - You're within range of the device

3. If you get connection errors:
   - Make sure the device is still powered on and in range
   - Some devices may require pairing before connection
   - Try scanning again to verify the device is still visible

## Which Script Should I Use?

- Use `bleak_bluetooth_signal.py` (RECOMMENDED) for:
  - Modern devices that support Bluetooth Low Energy (BLE)
  - When you want a more reliable, cross-platform solution
  - When you're using newer versions of Python
  - When you encounter installation issues with bluepy

- Use `bluetooth_signal_strength.py` for:
  - BLE devices when you specifically need the bluepy library
  - When you have an older system where bluepy is already installed

- Use `classic_bluetooth_signal.py` for:
  - Older Bluetooth devices that don't support BLE
  - Headphones, speakers, keyboards, mice, game controllers
  - When you need to work with classic Bluetooth profiles

If you're unsure which type of Bluetooth your device uses, try the bleak script first, then the classic script if needed.

## Notes

- All scripts will continue monitoring signal strength until you press Ctrl+C or until the specified duration is reached.
- The bleak script uses modern async/await patterns and is more future-proof.
- The classic Bluetooth script uses system tools like `hcitool` and `l2ping` which might be deprecated in future Linux releases.
- For some devices, you may need to pair them first using the Raspberry Pi's Bluetooth settings before being able to connect.
- The bleak script can monitor devices without establishing a connection, which works better for devices that don't allow connections or have limited services.
- Distance estimation is approximate and works best after calibration with the specific devices you're using.
- For indoor environments, try using a path loss factor (`--factor`) between 2.5 and 4.0 for more accurate distance estimation.
