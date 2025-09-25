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
    interfaces = ['wlan0', 'wlp3s0', 'wlan1']
    for interfaz in interfaces:
        try:
            with open(f'/sys/class/net/{interfaz}/address', 'r') as f:
                return f.read().strip()
        except:
            continue
    return "00:00:00:00:00:00"