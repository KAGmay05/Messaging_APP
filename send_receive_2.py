import socket
import frame
import threading
import queue
import time
import os
from typing import Tuple, Dict

INTERFACE = "enp0s3"
SENDER_MAC = "08:00:27:19:91:61"
BROADCAST = "ff:ff:ff:ff:ff:ff"
ETHERTYPE = 0x88B5

send_queue = queue.Queue()
recv_queue = queue.Queue()

# reassembly_buffer : Dict[str, Dict] = {}

def raw_socket() -> socket.socket:
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETHERTYPE))
    s.bind((INTERFACE, 0))
    return s

def input_thread():
    while True:
        line = input("> ").strip()
        if not line:
            continue
        if line.startswith("@"):
            try:
                mac, msg = line.split(maxsplit=1)
                # dest = mac[1:].lower()
                dest = BROADCAST.lower()
            except ValueError:
                print("Formato inválido. Usa @<MAC> <mensaje>")
                continue
        else:
            dest = BROADCAST.lower()
            msg = line
        send_queue.put((1, dest, msg.encode()))
      

def sender_thread():
    s = raw_socket()
    while True:
        type, dst, info = send_queue.get()
        frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, type, 1, 1, info)
        s.send(frame_bytes)
        print(f"Enviado a {dst}: {info.decode()}")

# def receiver_thread():
#     s = raw_socket()
#     while True:
#         raw, addr = s.recvfrom(65535)
#         # print(f"Frame recibido: {raw.hex()[:60]} ...")  # solo los primeros bytes
#         try:
#             decoded = frame.decode(raw)
#         except ValueError:
#             print("CRC inválido")
#             continue
#         print(f"[Mensaje de {decoded['sender']}]: {decoded['data'].decode(errors='ignore')}")


def receiver_thread():
    s = raw_socket()
    while True:
        raw, addr = s.recvfrom(65535)
        try:
            decoded = frame.decode(raw)
        except ValueError:
            continue  # CRC inválido
        receiver = decoded["receiver"].lower()
        if receiver != SENDER_MAC.lower() and receiver != BROADCAST.lower():
            continue
        print(f"[Mensaje de {decoded['sender']}]: {decoded['data'].decode(errors='ignore')}")

# def pocessor_thread():
#     while True:
#         sender, type, info = recv_queue.get()
#         if type == 1:

if __name__ == "__main__":
    threads = []

    t_in = threading.Thread(target=input_thread, daemon=True)
    t_send = threading.Thread(target=sender_thread, daemon=True)
    t_recv = threading.Thread(target=receiver_thread, daemon=True)

    threads.extend([t_in, t_send, t_recv])

    # Iniciar los hilos
    for t in threads:
        t.start()

    # send_queue.put((1, SENDER_MAC.lower(), b"hola carlos"))

    # Mantener el programa vivo mientras corren los hilos
    for t in threads:
        t.join()


