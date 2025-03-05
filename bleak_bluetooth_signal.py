#!/usr/bin/env python3
"""
Raspberry Pi 4 Bluetooth Signal Strength Monitor using Bleak

This script scans for nearby Bluetooth Low Energy (BLE) devices,
connects to a specified device, and continuously monitors its signal strength.
It also estimates the approximate distance based on signal strength.

Requirements:
- bleak library: pip install bleak
- asyncio: pip install asyncio (usually included with Python 3.7+)
"""

import asyncio
import argparse
import time
import sys
import math
import warnings
from bleak import BleakScanner, BleakClient
from datetime import datetime

def estimate_distance(rssi, tx_power=-59, n=2.0):
    """
    Estimate the approximate distance based on RSSI value.
    
    Args:
        rssi (int): The RSSI value in dBm
        tx_power (int): The RSSI value at 1 meter distance (calibration value)
        n (float): The path loss exponent (2.0 for free space, 2.5-4.0 for indoors)
        
    Returns:
        float: Estimated distance in meters
    """
    if rssi == 0:
        return -1.0  # Return -1 if RSSI is zero (invalid)
    
    # Calculate distance using the path loss model
    ratio = (tx_power - rssi) / (10 * n)
    distance = math.pow(10, ratio)
    
    return round(distance, 2)

def get_distance_description(distance):
    """
    Get a human-readable description of the distance.
    
    Args:
        distance (float): Distance in meters
        
    Returns:
        str: Description of the distance
    """
    if distance < 0:
        return "Unknown"
    elif distance < 0.5:
        return "Very close (< 0.5m)"
    elif distance < 1.0:
        return "Close (< 1m)"
    elif distance < 2.0:
        return "Near (1-2m)"
    elif distance < 5.0:
        return "Medium distance (2-5m)"
    elif distance < 10.0:
        return "Far (5-10m)"
    else:
        return "Very far (> 10m)"

def identify_apple_device(mfg_data):
    """
    Identify specific Apple device type from manufacturer data.
    
    Args:
        mfg_data: Manufacturer data dictionary
        
    Returns:
        str: Identified Apple device type or "Apple Device" if unknown
    """
    apple_device_type = "Apple Device"
    
    # If we don't have manufacturer data, still return Apple Device
    if not mfg_data or 76 not in mfg_data:
        return apple_device_type
    
    # If we have manufacturer data but not enough bytes, still identify as Apple
    if 76 in mfg_data and len(mfg_data[76]) < 2:
        return apple_device_type
    
    try:
        type_byte = mfg_data[76][0]
        
        # Map type byte to device type
        # Reference: https://github.com/furiousMAC/continuity/blob/master/dissector/packet-bthci_evt.c
        if type_byte == 0x01:
            apple_device_type = "Apple AirPods"
        elif type_byte == 0x02:
            apple_device_type = "Apple Pencil"
        elif type_byte == 0x03:
            apple_device_type = "Apple Watch"
        elif type_byte == 0x05:
            apple_device_type = "Apple MacBook"
        elif type_byte == 0x06:
            apple_device_type = "Apple iPhone"
        elif type_byte == 0x07:
            apple_device_type = "Apple iPad"
        elif type_byte == 0x09:
            apple_device_type = "Apple HomePod"
        elif type_byte == 0x0A:
            apple_device_type = "Apple TV"
        elif type_byte == 0x10:
            apple_device_type = "Apple AirTag"
        elif type_byte == 0x0C:
            apple_device_type = "Apple Beats Headphones"
        elif type_byte == 0x0F:
            apple_device_type = "Apple AirPods Max"
        elif type_byte == 0x0B:
            apple_device_type = "Apple AirPods Pro"
    except (IndexError, TypeError) as e:
        # Just continue with the default name
        pass
    
    return apple_device_type

def is_likely_apple_device(address):
    """
    Check if a device is likely an Apple device based on its MAC address.
    
    Args:
        address: MAC address of the device
        
    Returns:
        bool: True if the device is likely an Apple device
    """
    # Common Apple MAC address prefixes
    apple_prefixes = [
        "AC:", "00:C6:", "00:CD:", "88:66:", "98:01:", "7C:9A:",
        "28:CF:", "54:33:", "C8:2A:", "60:C5:", "68:96:", "24:A0:",
        "F4:31:", "F0:D1:", "F0:F6:", "F8:1E:", "F8:62:", "FC:E9:",
        "10:40:", "10:93:", "14:10:", "14:20:", "18:34:", "18:65:",
        "18:F6:", "1C:36:", "1C:91:", "20:78:", "24:F0:", "28:37:",
        "28:6A:", "28:E0:", "28:E7:", "34:08:", "34:12:", "34:15:",
        "34:AB:", "38:0F:", "38:48:", "3C:07:", "3C:D0:", "40:30:",
        "40:4D:", "40:9C:", "40:A6:", "40:D3:", "44:00:", "44:2A:",
        "44:D1:", "48:3B:", "48:43:", "48:74:", "4C:32:", "4C:57:",
        "4C:74:", "4C:B1:", "50:32:", "50:EA:", "54:26:", "54:4E:",
        "54:99:", "58:40:", "58:55:", "58:7F:", "5C:59:", "5C:95:",
        "5C:96:", "5C:97:", "5C:F5:", "5C:F7:", "5C:F8:", "60:33:",
        "60:69:", "60:8C:", "60:92:", "60:9A:", "60:A3:", "60:C5:",
        "60:F4:", "60:FA:", "60:FB:", "64:20:", "64:76:", "64:9A:",
        "64:A3:", "64:B0:", "64:B9:", "64:E6:", "68:09:", "68:64:",
        "68:96:", "68:9C:", "68:A8:", "68:AB:", "68:AE:", "68:D9:",
        "68:FB:", "6C:19:", "6C:3E:", "6C:70:", "6C:72:", "6C:8D:",
        "6C:94:", "6C:96:", "6C:AB:", "70:14:", "70:3E:", "70:48:",
        "70:56:", "70:73:", "70:A2:", "70:CD:", "70:DE:", "70:E7:",
        "70:EC:", "74:1B:", "74:81:", "74:8D:", "74:E1:", "74:E2:",
        "78:31:", "78:32:", "78:6C:", "78:7B:", "78:88:", "78:9F:",
        "78:A3:", "78:CA:", "7C:01:", "7C:04:", "7C:11:", "7C:50:",
        "7C:6D:", "7C:FA:", "80:00:", "80:49:", "80:82:", "80:92:",
        "80:B0:", "80:E6:", "84:29:", "84:38:", "84:41:", "84:78:",
        "84:85:", "84:89:", "84:A1:", "84:B1:", "84:FC:", "88:19:",
        "88:1F:", "88:53:", "88:66:", "88:C6:", "8C:00:", "8C:29:",
        "8C:2D:", "8C:7B:", "8C:8E:", "8C:FA:", "90:27:", "90:60:",
        "90:72:", "90:84:", "90:8D:", "90:B0:", "90:B2:", "90:C1:",
        "90:FD:", "94:94:", "94:BF:", "94:E9:", "94:F6:", "98:00:",
        "98:01:", "98:03:", "98:10:", "98:5A:", "98:9E:", "98:B8:",
        "98:D6:", "98:E0:", "98:F0:", "98:F4:", "98:FE:", "9C:04:",
        "9C:20:", "9C:29:", "9C:35:", "9C:4F:", "9C:8B:", "9C:F3:",
        "9C:F4:", "A0:99:", "A0:D7:", "A4:31:", "A4:67:", "A4:B1:",
        "A4:B8:", "A4:C3:", "A4:D1:", "A4:D9:", "A8:20:", "A8:5B:",
        "A8:5C:", "A8:66:", "A8:88:", "A8:8E:", "A8:96:", "A8:BB:",
        "A8:FA:", "AC:1F:", "AC:29:", "AC:3C:", "AC:61:", "AC:7F:",
        "AC:87:", "AC:BC:", "AC:CF:", "AC:E4:", "AC:FD:", "B0:19:",
        "B0:34:", "B0:48:", "B0:65:", "B0:70:", "B0:9F:", "B0:CA:",
        "B0:EC:", "B4:18:", "B4:4B:", "B4:8B:", "B4:F0:", "B8:09:",
        "B8:17:", "B8:41:", "B8:44:", "B8:53:", "B8:63:", "B8:78:",
        "B8:8D:", "B8:C1:", "B8:C7:", "B8:E8:", "B8:F6:", "B8:FF:",
        "BC:3B:", "BC:4C:", "BC:52:", "BC:54:", "BC:67:", "BC:92:",
        "BC:9F:", "BC:A9:", "BC:EC:", "C0:1A:", "C0:63:", "C0:84:",
        "C0:A5:", "C0:CC:", "C0:CE:", "C0:D0:", "C0:F2:", "C4:2C:",
        "C4:98:", "C4:B3:", "C8:1E:", "C8:2A:", "C8:33:", "C8:3C:",
        "C8:69:", "C8:85:", "C8:B5:", "C8:BC:", "C8:BF:", "C8:D0:",
        "C8:E0:", "C8:F6:", "CC:08:", "CC:20:", "CC:25:", "CC:29:",
        "CC:44:", "CC:78:", "CC:7E:", "CC:C7:", "D0:03:", "D0:23:",
        "D0:25:", "D0:33:", "D0:4B:", "D0:81:", "D0:A6:", "D0:C5:",
        "D0:D2:", "D0:E1:", "D4:61:", "D4:9A:", "D4:A3:", "D4:DC:",
        "D4:F4:", "D8:00:", "D8:1D:", "D8:30:", "D8:8F:", "D8:96:",
        "D8:9E:", "D8:BB:", "D8:CF:", "D8:D1:", "DC:0C:", "DC:2B:",
        "DC:37:", "DC:41:", "DC:86:", "DC:A4:", "DC:A9:", "DC:D2:",
        "DC:F7:", "E0:5F:", "E0:66:", "E0:B5:", "E0:B9:", "E0:C7:",
        "E0:F5:", "E0:F8:", "E4:25:", "E4:2B:", "E4:8B:", "E4:9A:",
        "E4:C6:", "E4:CE:", "E4:E0:", "E4:E4:", "E8:04:", "E8:06:",
        "E8:80:", "E8:8D:", "E8:B2:", "EC:35:", "EC:85:", "EC:AD:",
        "F0:18:", "F0:79:", "F0:98:", "F0:99:", "F0:B0:", "F0:B1:",
        "F0:C1:", "F0:CB:", "F0:D1:", "F0:DB:", "F0:DC:", "F0:F6:",
        "F4:0F:", "F4:1B:", "F4:31:", "F4:37:", "F4:5C:", "F4:D4:",
        "F4:F1:", "F4:F5:", "F8:03:", "F8:1E:", "F8:27:", "F8:38:",
        "F8:62:", "F8:6F:", "FC:25:", "FC:A8:", "FC:B6:", "FC:D8:",
        "FC:E9:", "FC:FC:"
    ]
    
    for prefix in apple_prefixes:
        if address.upper().startswith(prefix):
            return True
    
    return False

async def scan_devices(duration=10):
    """
    Scan for nearby BLE devices.
    
    Args:
        duration (int): Duration of scan in seconds
        
    Returns:
        List of discovered devices
    """
    print(f"Scanning for Bluetooth devices for {duration} seconds...")
    devices = await BleakScanner.discover(timeout=duration)
    
    if not devices:
        print("No devices found.")
        return []
    
    print("\nDevices found:")
    for i, device in enumerate(devices):
        # Access RSSI - try multiple approaches to ensure we get a value
        rssi = 'Unknown'
        
        # First try the recommended approach with advertisement_data
        if hasattr(device, 'advertisement_data') and hasattr(device.advertisement_data, 'rssi'):
            rssi = device.advertisement_data.rssi
        
        # If that didn't work, try the direct property (with warning suppression)
        if rssi == 'Unknown' and hasattr(device, 'rssi'):
            rssi = device.rssi
                
        # If we still don't have a value, try other properties that might contain RSSI
        if rssi == 'Unknown' and hasattr(device, 'metadata') and 'rssi' in device.metadata:
            rssi = device.metadata['rssi']
        
        # Get a human-readable name
        name = "Unknown Device"
        
        # Function to check if name is just a formatted MAC address
        def is_mac_address_name(name_str, address_str):
            # Remove colons from address
            clean_addr = address_str.replace(':', '')
            # Remove dashes and other common separators from name
            clean_name = name_str.replace('-', '').replace(':', '').replace('_', '')
            # Check if the cleaned name is the same as the cleaned address (case insensitive)
            return clean_name.lower() == clean_addr.lower()
        
        # Try to get name from device
        if device.name:
            # Try to decode if it's bytes
            if isinstance(device.name, bytes):
                try:
                    name = device.name.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        name = device.name.decode('ascii', errors='replace')
                    except Exception:
                        name = str(device.name)
            else:
                name = str(device.name)
                
            # Clean up the name
            name = name.strip()
            if not name:
                name = "Unknown Device"
                
            # Check if name is just a formatted MAC address
            if is_mac_address_name(name, device.address):
                name = "Unknown Device"
        
        # Try to get a better name from advertisement data
        if name == "Unknown Device" and hasattr(device, 'advertisement_data'):
            adv_data = device.advertisement_data
            
            # Try to get complete local name
            if hasattr(adv_data, 'local_name') and adv_data.local_name:
                name = adv_data.local_name
            
            # Try service data for device type hints
            if name == "Unknown Device" and hasattr(adv_data, 'service_data') and adv_data.service_data:
                # Check for common service UUIDs to identify device types
                services = list(adv_data.service_data.keys())
                if services:
                    if any('1800' in s.lower() for s in services):  # Generic Access Profile
                        name = "Generic BLE Device"
                    elif any('180f' in s.lower() for s in services):  # Battery Service
                        name = "Battery-powered Device"
                    elif any('180a' in s.lower() for s in services):  # Device Information
                        name = "BLE Device"
                    elif any('1812' in s.lower() for s in services):  # HID Service
                        name = "HID Device (Keyboard/Mouse)"
                    elif any('1802' in s.lower() for s in services):  # Immediate Alert
                        name = "Alert Device"
                    elif any('1803' in s.lower() for s in services):  # Link Loss
                        name = "Proximity Device"
        
        # Get manufacturer data if available using the recommended approach
        manufacturer = ""
        manufacturer_id = None
        mfg_data = None
        
        # Try to get manufacturer data from advertisement_data (recommended way)
        if hasattr(device, 'advertisement_data') and hasattr(device.advertisement_data, 'manufacturer_data'):
            mfg_data = device.advertisement_data.manufacturer_data
            if mfg_data and len(mfg_data) > 0:
                manufacturer_id = list(mfg_data.keys())[0]
                manufacturer = f" (Manufacturer: {manufacturer_id})"
        
        # Try to identify common manufacturers and specific device types
        if name == "Unknown Device":
            if manufacturer_id is not None:
                if manufacturer_id == 76:  # Apple
                    # Always identify as Apple, even if we can't determine the specific type
                    name = identify_apple_device(mfg_data)
                    # Remove the duplicate manufacturer info since it's in the name
                    manufacturer = ""
                elif manufacturer_id == 6:  # Microsoft
                    name = "Microsoft Device"
                elif manufacturer_id == 224:  # Google
                    name = "Google Device"
                elif manufacturer_id == 117:  # Samsung
                    name = "Samsung Device"
                else:
                    # For other manufacturers, at least show "Device (Manufacturer: X)"
                    name = f"Device"
            # If we still don't have a name and the address follows Apple patterns, make an educated guess
            elif name == "Unknown Device" and is_likely_apple_device(device.address):
                name = "Likely Apple Device"
        
        print(f"{i+1}. Address: {device.address} - Name: {name}{manufacturer} - RSSI: {rssi} dB")
    
    return devices

async def monitor_signal_strength(address, interval=1.0, duration=None, tx_power=-59, n_factor=2.0):
    """
    Monitor the signal strength of a BLE device.
    
    Args:
        address (str): MAC address or device identifier
        interval (float): Time between RSSI readings in seconds
        duration (int, optional): Total monitoring duration in seconds
        tx_power (int): Calibration value for distance estimation
        n_factor (float): Path loss exponent for distance estimation
    """
    # First scan to get the device
    print(f"Looking for device with address: {address}")
    device = await BleakScanner.find_device_by_address(address, timeout=10.0)
    
    if not device:
        print(f"Device with address {address} not found. Make sure it's powered on and in range.")
        return
    
    print(f"Found device: {device.address} - {device.name or 'Unknown'}")
    
    # We'll use a scanner to continuously get RSSI without maintaining a connection
    # This works better for devices that don't allow connections or have limited services
    scanner = BleakScanner()
    
    print("\nMonitoring signal strength...")
    print("(Press Ctrl+C to stop)")
    
    start_time = time.time()
    count = 0
    
    try:
        while True:
            if duration and (time.time() - start_time) > duration:
                break
                
            # Scan for the device to get updated RSSI
            await scanner.start()
            await asyncio.sleep(1.0)  # Give it time to scan
            
            # Use the property instead of the deprecated method
            devices = scanner.discovered_devices
            await scanner.stop()
            
            # Find our device in the scan results
            target_device = next((d for d in devices if d.address.lower() == address.lower()), None)
            
            count += 1
            timestamp = datetime.now().strftime("%H:%M:%S")
            
            if target_device:
                # Get RSSI safely from advertisement data if available
                rssi = None
                
                # Try multiple approaches to get RSSI
                rssi = None
                
                # Try to get RSSI from advertisements (recommended approach)
                if hasattr(scanner, 'advertisements'):
                    for adv in scanner.advertisements.values():
                        if adv.device.address.lower() == address.lower():
                            rssi = adv.rssi
                            break
                
                # If that didn't work, try the direct property (with warning suppression)
                if rssi is None and hasattr(target_device, 'rssi'):
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        rssi = target_device.rssi
                        
                # If we still don't have a value, try other properties that might contain RSSI
                if rssi is None and hasattr(target_device, 'metadata') and 'rssi' in target_device.metadata:
                    rssi = target_device.metadata['rssi']
                
                if rssi is not None:
                    # Estimate distance based on RSSI using the provided calibration values
                    distance = estimate_distance(rssi, tx_power, n_factor)
                    distance_desc = get_distance_description(distance)
                    
                    # Print signal strength with a simple bar visualization
                    bars = min(10, max(0, int((rssi + 100) / 10)))
                    bar_str = '█' * bars + '░' * (10 - bars)
                    
                    print(f"[{timestamp}] Reading #{count}: Signal Strength: {rssi} dB [{bar_str}]")
                    print(f"                      Estimated Distance: {distance} meters ({distance_desc})")
                else:
                    print(f"[{timestamp}] Reading #{count}: Device found but could not get RSSI value.")
            else:
                print(f"[{timestamp}] Reading #{count}: Device not found in scan results. It may be out of range.")
            
            # Wait for the next interval
            await asyncio.sleep(interval)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await scanner.stop()

async def connect_and_monitor(address, interval=1.0, duration=None, tx_power=-59, n_factor=2.0):
    """
    Connect to a device and monitor its signal strength.
    This method attempts to establish and maintain a connection,
    which may not work with all devices.
    
    Args:
        address (str): MAC address or device identifier
        interval (float): Time between RSSI readings in seconds
        duration (int, optional): Total monitoring duration in seconds
        tx_power (int): Calibration value for distance estimation
        n_factor (float): Path loss exponent for distance estimation
    """
    print(f"\nAttempting to connect to device: {address}")
    
    try:
        async with BleakClient(address) as client:
            if client.is_connected:
                print("Connected successfully!")
                
                start_time = time.time()
                count = 0
                
                try:
                    while True:
                        if duration and (time.time() - start_time) > duration:
                            break
                            
                        # Get current time for timestamp
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        
                        # For connected devices, we can directly get the RSSI
                        rssi = None
                        if hasattr(client, 'rssi'):
                            rssi = await client.get_rssi()
                        else:
                            # Fall back to scanner if direct RSSI not available
                            scanner = BleakScanner()
                            await scanner.start()
                            await asyncio.sleep(0.5)
                            
                            # Use the property instead of the deprecated method
                            devices = scanner.discovered_devices
                            await scanner.stop()
                            
                            # Try multiple approaches to get RSSI
                            rssi = None
                            
                            # Try to get RSSI from advertisements (recommended approach)
                            if hasattr(scanner, 'advertisements'):
                                for adv in scanner.advertisements.values():
                                    if adv.device.address.lower() == address.lower():
                                        rssi = adv.rssi
                                        break
                            
                            # If that didn't work, try the direct property (with warning suppression)
                            if rssi is None:
                                device = next((d for d in devices if d.address.lower() == address.lower()), None)
                                if device and hasattr(device, 'rssi'):
                                    import warnings
                                    with warnings.catch_warnings():
                                        warnings.simplefilter("ignore")
                                        rssi = device.rssi
                                        
                            # If we still don't have a value, try other properties that might contain RSSI
                            if rssi is None and device and hasattr(device, 'metadata') and 'rssi' in device.metadata:
                                rssi = device.metadata['rssi']
                        
                        count += 1
                        
                        if rssi is not None:
                            # Estimate distance based on RSSI using the provided calibration values
                            distance = estimate_distance(rssi, tx_power, n_factor)
                            distance_desc = get_distance_description(distance)
                            
                            # Print signal strength with a simple bar visualization
                            bars = min(10, max(0, int((rssi + 100) / 10)))
                            bar_str = '█' * bars + '░' * (10 - bars)
                            
                            print(f"[{timestamp}] Reading #{count}: Signal Strength: {rssi} dB [{bar_str}]")
                            print(f"                      Estimated Distance: {distance} meters ({distance_desc})")
                        else:
                            print(f"[{timestamp}] Reading #{count}: Could not get signal strength.")
                        
                        await asyncio.sleep(interval)
                        
                except KeyboardInterrupt:
                    print("\nMonitoring stopped by user")
            else:
                print("Failed to connect. Device may not be connectable or may be out of range.")
                # Fall back to monitoring without connection
                await monitor_signal_strength(address, interval, duration, tx_power, n_factor)
                
    except Exception as e:
        print(f"Connection error: {e}")
        print("Falling back to monitoring without connection...")
        await monitor_signal_strength(address, interval, duration, tx_power, n_factor)

async def main_async():
    parser = argparse.ArgumentParser(description='Bluetooth Signal Strength Monitor using Bleak')
    parser.add_argument('-a', '--address', help='MAC address or identifier of the device to monitor')
    parser.add_argument('-s', '--scan', action='store_true', help='Scan for devices')
    parser.add_argument('-t', '--time', type=int, default=10, help='Scan duration in seconds')
    parser.add_argument('-i', '--interval', type=float, default=1.0, help='Interval between RSSI readings in seconds')
    parser.add_argument('-d', '--duration', type=int, help='Total monitoring duration in seconds')
    parser.add_argument('-c', '--connect', action='store_true', help='Attempt to connect to the device (may not work with all devices)')
    parser.add_argument('-p', '--power', type=int, default=-59, help='Calibration value: RSSI at 1 meter (default: -59)')
    parser.add_argument('-n', '--factor', type=float, default=2.0, 
                        help='Path loss exponent (2.0 for free space, 2.5-4.0 for indoors, default: 2.0)')
    
    args = parser.parse_args()
    
    if args.scan or not args.address:
        devices = await scan_devices(args.time)
        if not args.address and devices:
            # If no address provided but devices found, ask user to select one
            try:
                choice = int(input("\nEnter the number of the device to monitor (0 to exit): "))
                if choice > 0 and choice <= len(devices):
                    args.address = devices[choice-1].address
                else:
                    print("Exiting...")
                    return
            except (ValueError, IndexError):
                print("Invalid selection. Exiting...")
                return
    
    if args.address:
        # Get the calibration values
        tx_power = args.power
        n_factor = args.factor
        
        if args.connect:
            await connect_and_monitor(args.address, args.interval, args.duration, tx_power, n_factor)
        else:
            await monitor_signal_strength(args.address, args.interval, args.duration, tx_power, n_factor)

def main():
    """Entry point for the script."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\nProgram terminated by user")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
