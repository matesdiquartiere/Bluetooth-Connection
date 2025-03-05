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

# Importazione delle librerie necessarie
import asyncio  # Libreria per la programmazione asincrona
import argparse  # Libreria per gestire gli argomenti da linea di comando
import time  # Libreria per funzioni relative al tempo
import sys  # Libreria per interagire con il sistema
import math  # Libreria per funzioni matematiche
import warnings  # Libreria per gestire gli avvisi
from bleak import BleakScanner, BleakClient  # Libreria Bleak per interagire con dispositivi Bluetooth LE
from datetime import datetime  # Libreria per gestire date e orari

def estimate_distance(rssi, tx_power=-59, n=2.0):
    """
    Stima la distanza approssimativa basata sul valore RSSI.
    
    Args:
        rssi (int): Il valore RSSI in dBm
        tx_power (int): Il valore RSSI a 1 metro di distanza (valore di calibrazione)
        n (float): L'esponente di perdita del percorso (2.0 per spazio libero, 2.5-4.0 per interni)
        
    Returns:
        float: Distanza stimata in metri
    """
    if rssi == 0:
        return -1.0  # Restituisce -1 se RSSI è zero (non valido)
    
    # Calcola la distanza utilizzando il modello di perdita del percorso
    ratio = (tx_power - rssi) / (10 * n)
    distance = math.pow(10, ratio)
    
    return round(distance, 2)  # Arrotonda a 2 decimali

def get_distance_description(distance):
    """
    Fornisce una descrizione leggibile della distanza.
    
    Args:
        distance (float): Distanza in metri
        
    Returns:
        str: Descrizione della distanza
    """
    # Restituisce una descrizione testuale in base alla distanza calcolata
    if distance < 0:
        return "Unknown"  # Distanza sconosciuta
    elif distance < 0.5:
        return "Very close (< 0.5m)"  # Molto vicino
    elif distance < 1.0:
        return "Close (< 1m)"  # Vicino
    elif distance < 2.0:
        return "Near (1-2m)"  # Nelle vicinanze
    elif distance < 5.0:
        return "Medium distance (2-5m)"  # Media distanza
    elif distance < 10.0:
        return "Far (5-10m)"  # Lontano
    else:
        return "Very far (> 10m)"  # Molto lontano

def identify_apple_device(mfg_data):
    """
    Identifica il tipo specifico di dispositivo Apple dai dati del produttore.
    
    Args:
        mfg_data: Dizionario dei dati del produttore
        
    Returns:
        str: Tipo di dispositivo Apple identificato o "Apple Device" se sconosciuto
    """
    apple_device_type = "Apple Device"  # Valore predefinito
    
    # Se non abbiamo dati del produttore, restituisce comunque "Apple Device"
    if not mfg_data or 76 not in mfg_data:
        return apple_device_type
    
    # Se abbiamo dati del produttore ma non abbastanza byte, identifica comunque come Apple
    if 76 in mfg_data and len(mfg_data[76]) < 2:
        return apple_device_type
    
    try:
        # Il primo byte nei dati del produttore indica il tipo di dispositivo Apple
        type_byte = mfg_data[76][0]
        
        # Mappa il byte del tipo al tipo di dispositivo
        # Riferimento: https://github.com/furiousMAC/continuity/blob/master/dissector/packet-bthci_evt.c
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
        # Continua con il nome predefinito in caso di errore
        pass
    
    return apple_device_type  # Restituisce il tipo di dispositivo identificato

def is_likely_apple_device(address):
    """
    Controlla se un dispositivo è probabilmente un dispositivo Apple in base al suo indirizzo MAC.
    
    Args:
        address: Indirizzo MAC del dispositivo
        
    Returns:
        bool: True se il dispositivo è probabilmente un dispositivo Apple
    """
    # Prefissi comuni degli indirizzi MAC Apple
    # Questa è una lista estesa di prefissi MAC noti utilizzati da Apple
    apple_prefixes = [
        "AC:", "00:C6:", "00:CD:", "88:66:", "98:01:", "7C:9A:",
        # ... (lista molto lunga di prefissi MAC di Apple)
        "FC:E9:", "FC:FC:"
    ]
    
    # Controlla se l'indirizzo inizia con uno dei prefissi Apple
    for prefix in apple_prefixes:
        if address.upper().startswith(prefix):
            return True
    
    return False  # Non è un dispositivo Apple in base al prefisso MAC

async def scan_devices(duration=10):
    """
    Scansiona i dispositivi BLE nelle vicinanze.
    
    Args:
        duration (int): Durata della scansione in secondi
        
    Returns:
        Lista dei dispositivi scoperti
    """
    print(f"Scanning for Bluetooth devices for {duration} seconds...")  # Messaggio di inizio scansione
    devices = await BleakScanner.discover(timeout=duration)  # Avvia la scansione per il tempo specificato
    
    if not devices:
        print("No devices found.")  # Nessun dispositivo trovato
        return []
    
    print("\nDevices found:")  # Intestazione per i dispositivi trovati
    for i, device in enumerate(devices):
        # Accede al RSSI - prova diversi approcci per assicurarsi di ottenere un valore
        rssi = 'Unknown'  # Valore predefinito
        
        # Prima prova l'approccio consigliato con advertisement_data
        if hasattr(device, 'advertisement_data') and hasattr(device.advertisement_data, 'rssi'):
            rssi = device.advertisement_data.rssi
        
        # Se non ha funzionato, prova la proprietà diretta (con soppressione degli avvisi)
        if rssi == 'Unknown' and hasattr(device, 'rssi'):
            rssi = device.rssi
                
        # Se ancora non abbiamo un valore, prova altre proprietà che potrebbero contenere RSSI
        if rssi == 'Unknown' and hasattr(device, 'metadata') and 'rssi' in device.metadata:
            rssi = device.metadata['rssi']
        
        # Ottiene un nome leggibile
        name = "Unknown Device"  # Nome predefinito
        
        # Funzione per verificare se il nome è solo un indirizzo MAC formattato
        def is_mac_address_name(name_str, address_str):
            # Rimuove i due punti dall'indirizzo
            clean_addr = address_str.replace(':', '')
            # Rimuove trattini e altri separatori comuni dal nome
            clean_name = name_str.replace('-', '').replace(':', '').replace('_', '')
            # Controlla se il nome pulito è lo stesso dell'indirizzo pulito (case insensitive)
            return clean_name.lower() == clean_addr.lower()
        
        # Prova a ottenere il nome dal dispositivo
        if device.name:
            # Prova a decodificare se è in bytes
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
                
            # Pulisce il nome
            name = name.strip()
            if not name:
                name = "Unknown Device"
                
            # Controlla se il nome è solo un indirizzo MAC formattato
            if is_mac_address_name(name, device.address):
                name = "Unknown Device"
        
        # Prova a ottenere un nome migliore dai dati di advertisement
        if name == "Unknown Device" and hasattr(device, 'advertisement_data'):
            adv_data = device.advertisement_data
            
            # Prova a ottenere il nome locale completo
            if hasattr(adv_data, 'local_name') and adv_data.local_name:
                name = adv_data.local_name
            
            # Prova i dati di servizio per suggerimenti sul tipo di dispositivo
            if name == "Unknown Device" and hasattr(adv_data, 'service_data') and adv_data.service_data:
                # Controlla gli UUID di servizio comuni per identificare i tipi di dispositivo
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
        
        # Ottiene i dati del produttore se disponibili utilizzando l'approccio consigliato
        manufacturer = ""
        manufacturer_id = None
        mfg_data = None
        
        # Prova a ottenere i dati del produttore da advertisement_data (modo consigliato)
        if hasattr(device, 'advertisement_data') and hasattr(device.advertisement_data, 'manufacturer_data'):
            mfg_data = device.advertisement_data.manufacturer_data
            if mfg_data and len(mfg_data) > 0:
                manufacturer_id = list(mfg_data.keys())[0]
                manufacturer = f" (Manufacturer: {manufacturer_id})"
        
        # Prova a identificare produttori comuni e tipi di dispositivo specifici
        if name == "Unknown Device":
            if manufacturer_id is not None:
                if manufacturer_id == 76:  # Apple
                    # Identifica sempre come Apple, anche se non possiamo determinare il tipo specifico
                    name = identify_apple_device(mfg_data)
                    # Rimuove le informazioni duplicate del produttore poiché sono nel nome
                    manufacturer = ""
                elif manufacturer_id == 6:  # Microsoft
                    name = "Microsoft Device"
                elif manufacturer_id == 224:  # Google
                    name = "Google Device"
                elif manufacturer_id == 117:  # Samsung
                    name = "Samsung Device"
                else:
                    # Per altri produttori, mostra almeno "Device (Manufacturer: X)"
                    name = f"Device"
            # Se ancora non abbiamo un nome e l'indirizzo segue i modelli Apple, fai una stima educata
            elif name == "Unknown Device" and is_likely_apple_device(device.address):
                name = "Likely Apple Device"
        
        # Stampa le informazioni del dispositivo
        print(f"{i+1}. Address: {device.address} - Name: {name}{manufacturer} - RSSI: {rssi} dB")
    
    return devices  # Restituisce la lista dei dispositivi trovati

async def monitor_signal_strength(address, interval=1.0, duration=None, tx_power=-59, n_factor=2.0):
    """
    Monitora la potenza del segnale di un dispositivo BLE senza connettersi.
    
    Args:
        address (str): Indirizzo MAC o identificatore del dispositivo
        interval (float): Tempo tra le letture RSSI in secondi
        duration (int, optional): Durata totale del monitoraggio in secondi
        tx_power (int): Valore di calibrazione per la stima della distanza
        n_factor (float): Esponente di perdita del percorso per la stima della distanza
    """
    # Prima scansione per ottenere il dispositivo
    print(f"Looking for device with address: {address}")
    device = await BleakScanner.find_device_by_address(address, timeout=10.0)
    
    if not device:
        print(f"Device with address {address} not found. Make sure it's powered on and in range.")
        return
    
    print(f"Found device: {device.address} - {device.name or 'Unknown'}")
    
    # Utilizziamo uno scanner per ottenere continuamente RSSI senza mantenere una connessione
    # Questo funziona meglio per i dispositivi che non consentono connessioni o hanno servizi limitati
    scanner = BleakScanner()
    
    print("\nMonitoring signal strength...")
    print("(Press Ctrl+C to stop)")
    
    start_time = time.time()  # Tempo di inizio
    count = 0  # Contatore delle letture
    
    try:
        while True:
            # Se è stata specificata una durata e l'abbiamo superata, esci dal ciclo
            if duration and (time.time() - start_time) > duration:
                break
                
            # Scansiona il dispositivo per ottenere RSSI aggiornato
            await scanner.start()
            await asyncio.sleep(1.0)  # Dà tempo per la scansione
            
            # Usa la proprietà invece del metodo deprecato
            devices = scanner.discovered_devices
            await scanner.stop()
            
            # Trova il nostro dispositivo nei risultati della scansione
            target_device = next((d for d in devices if d.address.lower() == address.lower()), None)
            
            count += 1
            timestamp = datetime.now().strftime("%H:%M:%S")  # Timestamp corrente
            
            if target_device:
                # Ottiene RSSI in modo sicuro dai dati di advertisement se disponibili
                rssi = None
                
                # Prova diversi approcci per ottenere RSSI
                rssi = None
                
                # Prova a ottenere RSSI dagli advertisement (approccio consigliato)
                if hasattr(scanner, 'advertisements'):
                    for adv in scanner.advertisements.values():
                        if adv.device.address.lower() == address.lower():
                            rssi = adv.rssi
                            break
                
                # Se non ha funzionato, prova la proprietà diretta (con soppressione degli avvisi)
                if rssi is None and hasattr(target_device, 'rssi'):
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        rssi = target_device.rssi
                        
                # Se ancora non abbiamo un valore, prova altre proprietà che potrebbero contenere RSSI
                if rssi is None and hasattr(target_device, 'metadata') and 'rssi' in target_device.metadata:
                    rssi = target_device.metadata['rssi']
                
                if rssi is not None:
                    # Stima la distanza in base a RSSI utilizzando i valori di calibrazione forniti
                    distance = estimate_distance(rssi, tx_power, n_factor)
                    distance_desc = get_distance_description(distance)
                    
                    # Stampa la potenza del segnale con una semplice visualizzazione a barre
                    bars = min(10, max(0, int((rssi + 100) / 10)))
                    bar_str = '█' * bars + '░' * (10 - bars)
                    
                    print(f"[{timestamp}] Reading #{count}: Signal Strength: {rssi} dB [{bar_str}]")
                    print(f"                      Estimated Distance: {distance} meters ({distance_desc})")
                else:
                    print(f"[{timestamp}] Reading #{count}: Device found but could not get RSSI value.")
            else:
                print(f"[{timestamp}] Reading #{count}: Device not found in scan results. It may be out of range.")
            
            # Attende il prossimo intervallo
            await asyncio.sleep(interval)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await scanner.stop()  # Assicura che lo scanner venga fermato

async def connect_and_monitor(address, interval=1.0, duration=None, tx_power=-59, n_factor=2.0):
    """
    Si connette a un dispositivo e monitora la sua potenza del segnale.
    Questo metodo tenta di stabilire e mantenere una connessione,
    che potrebbe non funzionare con tutti i dispositivi.
    
    Args:
        address (str): Indirizzo MAC o identificatore del dispositivo
        interval (float): Tempo tra le letture RSSI in secondi
        duration (int, optional): Durata totale del monitoraggio in secondi
        tx_power (int): Valore di calibrazione per la stima della distanza
        n_factor (float): Esponente di perdita del percorso per la stima della distanza
    """
    print(f"\nAttempting to connect to device: {address}")
    
    try:
        # Tenta di connettersi al dispositivo
        async with BleakClient(address) as client:
            if client.is_connected:
                print("Connected successfully!")
                
                start_time = time.time()
                count = 0
                
                try:
                    while True:
                        # Se è stata specificata una durata e l'abbiamo superata, esci dal ciclo
                        if duration and (time.time() - start_time) > duration:
                            break
                            
                        # Ottiene l'ora corrente per il timestamp
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        
                        # Per i dispositivi connessi, possiamo ottenere direttamente RSSI
                        rssi = None
                        if hasattr(client, 'rssi'):
                            rssi = await client.get_rssi()
                        else:
                            # Torna allo scanner se RSSI diretto non è disponibile
                            scanner = BleakScanner()
                            await scanner.start()
                            await asyncio.sleep(0.5)
                            
                            # Usa la proprietà invece del metodo deprecato
                            devices = scanner.discovered_devices
                            await scanner.stop()
                            
                            # Prova diversi approcci per ottenere RSSI
                            rssi = None
                            
                            # Prova a ottenere RSSI dagli advertisement (approccio consigliato)
                            if hasattr(scanner, 'advertisements'):
                                for adv in scanner.advertisements.values():
                                    if adv.device.address.lower() == address.lower():
                                        rssi = adv.rssi
                                        break
                            
                            # Se non ha funzionato, prova la proprietà diretta (con soppressione degli avvisi)
                            if rssi is None:
                                device = next((d for d in devices if d.address.lower() == address.lower()), None)
                                if device and hasattr(device, 'rssi'):
                                    import warnings
                                    with warnings.catch_warnings():
                                        warnings.simplefilter("ignore")
                                        rssi = device.rssi
                                        
                            # Se ancora non abbiamo un valore, prova altre proprietà che potrebbero contenere RSSI
                            if rssi is None and device and hasattr(device, 'metadata') and 'rssi' in device.metadata:
                                rssi = device.metadata['rssi']
                        
                        count += 1
                        
                        if rssi is not None:
                            # Stima la distanza in base a RSSI utilizzando i valori di calibrazione forniti
                            distance = estimate_distance(rssi, tx_power, n_factor)
                            distance_desc = get_distance_description(distance)
                            
                            # Stampa la potenza del segnale con una semplice visualizzazione a barre
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
                # Torna al monitoraggio senza connessione
                await monitor_signal_strength(address, interval, duration, tx_power, n_factor)
                
    except Exception as e:
        print(f"Connection error: {e}")
        print("Falling back to monitoring without connection...")
        await monitor_signal_strength(address, interval, duration, tx_power, n_factor)

async def main_async():
    """
    Funzione principale asincrona che gestisce il flusso del programma.
    Analizza gli argomenti della riga di comando e avvia le operazioni appropriate.
    """
    # Configura il parser degli argomenti
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
    
    args = parser.parse_args()  # Analizza gli argomenti
    
    # Se è richiesta una scansione o non è fornito un indirizzo, esegue una scansione
    if args.scan or not args.address:
        devices = await scan_devices(args.time)
        if not args.address and devices:
            # Se non è fornito un indirizzo ma sono stati trovati dispositivi, chiede all'utente di selezionarne uno
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
    
    # Se è disponibile un indirizzo, avvia il monitoraggio
    if args.address:
        # Ottiene i valori di calibrazione
        tx_power = args.power
        n_factor = args.factor
        
        if args.connect:
            # Tenta di connettersi e monitorare
            await connect_and_monitor(args.address, args.interval, args.duration, tx_power, n_factor)
        else:
            # Monitora senza connessione
            await monitor_signal_strength(args.address, args.interval, args.duration, tx_power, n_factor)

def main():
    """
    Punto di ingresso per lo script.
    Gestisce l'esecuzione della funzione asincrona principale e le eccezioni.
    """
    try:
        asyncio.run(main_async())  # Esegue la funzione asincrona principale
    except KeyboardInterrupt:
        print("\nProgram terminated by user")  # Gestisce l'interruzione da tastiera
    except Exception as e:
        print(f"Error: {e}")  # Gestisce altre eccezioni

# Punto di ingresso dello script quando eseguito direttamente
if __name__ == "__main__":
    main()
