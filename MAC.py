import socket      # Para comunicación de red
import struct      # Para empaquetar/desempaquetar datos binarios
import os          # Para interactuar con el sistema operativo

def raw_socket():
    try:
        return socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))#AF_PACKET es para trabajr con las direcciones MAC, SOCK_RAW es para controlar los frames, 0X0003 es para ver todos los paquetes de la red y ntohs( conversionde bytes)
    except PermissionError:
        print("Se necesitan permisos de administracion para socket raw") 
        return None 
    except Exception as e:
        print(f"error creando socket: {e}")
        return None

def get_mac_address():
    interfaces = ['wlan0', 'wlp3s0', 'wlan1', 'wlp2s0', 'wlo1']
    for interfaz in interfaces:
        try:
            with open(f'/sys/class/net/{interfaz}/address', 'r') as f:
                return f.read().strip()
        except:
            continue
    return "00:00:00:00:00:00"

def parse_ethernet_frame(data):
    if len(data) < 14:
        return None, None, None
    
    dest_mac, src_mac, proto = struct.unpack('!6s6sH', data[:14])
    return (
        ':'.join(f'{b:02x}' for b in dest_mac),
        ':'.join(f'{b:02x}' for b in src_mac),
        socket.htons(proto)
    )

def get_vendor_from_mac(mac):
    vendor_db = {
        '00:0c:29': 'VMware (Probable VM)',
        '00:50:56': 'VMware (Probable VM)',
        '00:15:5d': 'Microsoft Hyper-V (Probable VM)',
        '00:1c:42': 'Parallels (Probable VM)',
        '00:05:69': 'VMware (Probable VM)',
        '08:00:27': 'VirtualBox (Probable VM)',
        '0a:00:27': 'VirtualBox (Probable VM)',
        '00:23:54': 'Dell',
        '00:26:b9': 'Apple',
        '00:25:00': 'Cisco',
        '00:50:b6': 'Dell',
        '00:13:d4': 'Intel',
        '00:18:8b': 'LG',
        '00:19:99': 'Samsung',
        '00:1d:60': 'Sony',
        '00:23:12': 'Lenovo',
        '00:24:e9': 'HP',
        '00:26:b0': 'TP-Link',
        'a4:5e:60': 'Apple',
        'a4:5e:60': 'Apple',
        'a8:66:7f': 'Apple',
        'ac:bc:32': 'Apple',
        'b8:e8:56': 'Apple',
        'bc:54:36': 'Apple',
        'd0:25:98': 'Apple',
        'fc:f1:52': 'Samsung',
    }
    mac_prefix = mac.lower()[:8]  # Primeros 3 bytes
    return vendor_db.get(mac_prefix, 'Fabricante desconocido')