import socket
import frame
import threading
import queue
import time
from typing import Tuple, Dict

INTERFACE = "eth0"
BROADCAST = "ff:ff:ff:ff:ff:ff"
ETHERTYPE = 0x88B5

send_queue = queue.Queue()
recv_queue = queue.Queue()

known_macs: Dict[str, str] = {}

username = None

stop_event = threading.Event() 

def get_own_mac(interface=None):
    if interface is None:
        interface = INTERFACE
    path = f"/sys/class/net/{interface}/address"
    with open(path) as f:
        return f.read().strip().lower()

SENDER_MAC = get_own_mac(INTERFACE)


def raw_socket():
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETHERTYPE))
    s.bind((INTERFACE, 0))
    return s

def announce_thread():
    while not stop_event.is_set():
        if username:
            data = f"{username}|{SENDER_MAC}".encode()
        else:
            data = SENDER_MAC.encode()
        send_queue.put((3, BROADCAST.lower(), data))
        time.sleep(5)

def input_thread():
    while not stop_event.is_set():
        line = input("> ").strip()
        if not line:
            continue
        if line == "peers":
            print("🔎 Peers conocidos:", list(known_macs.keys()))
            continue
        if line.startswith("@"):
            try:
                mac, msg = line.split(maxsplit=1)
                dest = mac.lower()
            except ValueError:
                print("Formato inválido. Usa @<MAC> <mensaje>")
                continue
        else:
            for mac in list(known_macs.keys()):
                send_queue.put((1, mac, line.encode()))
            continue
        send_queue.put((1, dest, msg.encode()))
      

def sender_thread():
    s = raw_socket()
    while not stop_event.is_set():
        type, dst, info = send_queue.get()
        frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, type, 1, 1, info)
        s.send(frame_bytes)
        if type != 3:
            print(f"Enviado a {dst}: {info.decode()}")


def receiver_thread():
    s = raw_socket()
    while not stop_event.is_set():
        raw, addr = s.recvfrom(65535)
        try:
            decoded = frame.decode(raw)
        except ValueError:
            continue  # CRC inválido

        receiver = decoded["receiver"].lower()
        sender   = decoded["sender"].lower()
        msg_type = decoded["type"]
        payload  = decoded["data"]
        if receiver != SENDER_MAC.lower() and receiver != BROADCAST.lower():
            continue
        if msg_type == 1:
            text = payload.decode(errors='ignore')
            recv_queue.put((sender, text))   # guardamos en la cola
            print(f"[Mensaje de {sender}]: {text}")
            print("> ", end="", flush=True)
        elif msg_type == 3:
            try:
                text = payload.decode()
                if "|" in text:
                    peer_name, peer_mac = text.split("|", 1)
                else:
                    peer_name = peer_mac = text
            except Exception:
                peer_name = peer_mac = payload.decode()
            known_macs[peer_mac] = peer_name
            if peer_mac != SENDER_MAC.lower():
                 if username:
                     data = f"{username}|{SENDER_MAC}".encode()
                 else:
                     data = SENDER_MAC.encode()
                 send_queue.put((3, sender, data))
            




if __name__ == "__main__":
    threads = []

    t_in = threading.Thread(target=input_thread, daemon=True)
    t_send = threading.Thread(target=sender_thread, daemon=True)
    t_recv = threading.Thread(target=receiver_thread, daemon=True)
    t_ann = threading.Thread(target=announce_thread, daemon=True)
    threads.extend([t_ann, t_in, t_send, t_recv ])

    # Iniciar los hilos
    for t in threads:
        t.start()

    # send_queue.put((1, SENDER_MAC.lower(), b"hola carlos"))

    # Mantener el programa vivo mientras corren los hilos
    for t in threads:
        t.join()


