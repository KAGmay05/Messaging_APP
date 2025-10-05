import socket
import frame
import file_fragments as ff
import threading
import queue
import time
import os
from typing import Tuple, Dict

INTERFACE = "enp0s3"
BROADCAST = "ff:ff:ff:ff:ff:ff"
ETHERTYPE = 0x88B5
CHUNK_SIZE = 1400

send_queue = queue.Queue()
recv_queue = queue.Queue()
reassembly_buffers: Dict[Tuple[str,int], Dict] = {}
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

        if line.startswith("/send "):  
            try:
                _, filepath, mac = line.split(maxsplit=2)
                dest = mac[1:].lower() if mac.startswith("@") else mac.lower()

                if not os.path.exists(filepath):
                    print("❌ Archivo no encontrado")
                    continue

                data = ff.file_to_bytes(filepath)
                file_id = ff.id()
                total = (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE

                print(f"📤 Enviando {filepath} ({len(data)} bytes) en {total} fragmentos...")

                for i, frag in enumerate(ff.fragment_data(data, CHUNK_SIZE), start=1):
                    # type=2 → archivo
                    header_info = f"{os.path.basename(filepath)}".encode()
                    send_queue.put((2, dest, file_id, i, total, header_info + b"||" + frag))

            except ValueError:
                print("Formato: /send <archivo> @<MAC>")
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
        item = send_queue.get()
        msg_type = item[0]
        if msg_type == 1:
            _,dst, info = item
            frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, msg_type, 1, 1, info)
        elif msg_type ==2:
            _,dst, file_id, frag_num, total_frag, info = item
            frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, msg_type, frag_num, total_frag, info)
        
        # s.send(frame_bytes)
        # if msg_type != 3:
        #     print(f"Enviado a {dst}: {info.decode()}")
        elif msg_type == 3:  # anuncio
            _, dst, info = item
            frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, msg_type, 1, 1, info)

        if frame_bytes is None:
            print("⚠️ Tipo de mensaje desconocido:", item)
            continue

        try:
            s.send(frame_bytes)
            if msg_type != 3:  # no imprimimos los heartbeats
                try:
                    print(f"Enviado a {dst}: {info.decode(errors='ignore')}")
                except Exception:
                    print(f"Enviado a {dst} (datos binarios)")
        except Exception as e:
            print("❌ Error al enviar:", e)


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
        num_frag = decoded["num_frag"]
        total_frag = decoded["total_frag"]
        payload  = decoded["data"]

        if receiver != SENDER_MAC.lower() and receiver != BROADCAST.lower():
            continue

        if msg_type == 1:
            text = payload.decode(errors='ignore')
            recv_queue.put((sender, text))   # guardamos en la cola
            print(f"[Mensaje de {sender}]: {text}")
            print("> ", end="", flush=True)

        elif msg_type == 2:
            try:
                header, frag = payload.split(b"||", 1)
                file_name = header.decode(errors="ignore")
            except Exception:
                file_name, frag = "desconocido.bin", payload
            key = (sender, decoded["ethertype"])
            if key not in reassembly_buffers:
                reassembly_buffers[key] = {
                    "total" : total_frag,
                    "parts" : {},
                    "file_name": file_name
                }      

            reassembly_buffers[key]["parts"][num_frag] = frag
            if len(reassembly_buffers[key]["parts"]) == total_frag:
                ordered = b"".join(reassembly_buffers[key]["parts"][i] for i in range(1, total_frag + 1))
                save_name = f"recv_{file_name}"
                ff.bytes_to_file(ordered, save_name)
                print (f"💾 Archivo recibido de {sender}: {save_name} ({len(ordered)} bytes)")    
                del reassembly_buffers[key]   

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

    for t in threads:
        t.join()


