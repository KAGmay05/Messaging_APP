import socket
import frame
import file_fragments as ff
import threading
import queue
import time
import os
from typing import Tuple, Dict

INTERFACE = "eth0"
BROADCAST = "ff:ff:ff:ff:ff:ff"
ETHERTYPE = 0x88B5
CHUNK_SIZE = 1400
SENDER_MAC = None

send_queue = queue.Queue()
recv_queue = queue.Queue()
reassembly_buffers: Dict[Tuple[str,int], Dict] = {}
known_macs: Dict[str, str] = {}
mutex = threading.Lock()
username = None

stop_event = threading.Event() 

pending_acks = {}  # msg_id -> {dst, info, retries, timestamp}
ACK_TIMEOUT = 3.0  # segundos antes de reintentar
MAX_RETRIES = 3

ack_update_callback = None

def get_own_mac(interface=None):
    if interface is None:
        interface = INTERFACE
    path = f"/sys/class/net/{interface}/address"
    with open(path) as f:
        return f.read().strip().lower()

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
            with mutex:
                peers = list(known_macs.keys())
            print("🔎 Peers conocidos:", peers)
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
            with mutex:
                dests = list(known_macs.keys())
            
            for mac in dests:
                send_queue.put((1, mac, line.encode()))
            continue
        msg_id = str(ff.id())  # genera un ID único para el mensaje
        send_queue.put((1, dest, msg_id, msg.encode()))

      

def sender_thread():
    s = raw_socket()
    while not stop_event.is_set():
        item = send_queue.get()
        msg_type = item[0]
        
        if msg_type in (1, 5):
            _, dst, msg_id, info = item
            frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, 1, 1, 1, str(msg_id).encode() + b"||" + info)
            print(msg_id)
            if msg_type == 1:  # solo agregar a pending_acks si es la primera vez
                with mutex:
                    pending_acks[msg_id] = {
                        "dst": dst,
                        "info": info,
                        "retries": 0,
                        "timestamp": time.time()
                    }
                    print(pending_acks[msg_id]["info"])
            
        
        elif msg_type ==2:
            _,dst, file_id, frag_num, total_frag, info = item
            frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, msg_type, frag_num, total_frag, info)
        
        elif msg_type == 3:  # anuncio
            _, dst, info = item
            frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, msg_type, 1, 1, info)
        elif msg_type == 4:  # ACK
             print("llllllllllllllllllllll")
             _, dst, info = item
             frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, msg_type, 1, 1, info)

        if frame_bytes is None:
            print("⚠️ Tipo de mensaje desconocido:", item)
            continue

        try:
            s.send(frame_bytes)
            if msg_type != 3: 
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
            try:
                msg_id, payload = payload.split(b"||", 1)
                msg_id = msg_id.decode()
            except:
                msg_id = None
                payload = payload

            text = payload.decode(errors='ignore')
            recv_queue.put((sender, text))
            print(f"[Mensaje de {sender}]: {text}")

            print(msg_id)
            with mutex:
                ack_data = msg_id.encode()
                send_queue.put((4, sender, ack_data))


        elif msg_type == 2:
            try:
                header, frag = payload.split(b"||", 1)
                file_name = header.decode(errors="ignore")
            except Exception:
                file_name, frag = "desconocido.bin", payload
            key = (sender, decoded["ethertype"])
            with mutex:
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
                    recv_queue.put((2, sender, save_name, len(ordered)))
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
            with mutex:
                known_macs[peer_mac] = peer_name
            if peer_mac != SENDER_MAC.lower():
                 if username:
                     data = f"{username}|{SENDER_MAC}".encode()
                 else:
                     data = SENDER_MAC.encode()
                 send_queue.put((3, sender, data))
            
        elif msg_type == 4:  # ACK
            msg_id = payload.decode(errors="ignore").strip()
            print("🔹 Pending acks actuales:", list(pending_acks.keys()))
            msg_id= str(msg_id)
            with mutex:
                if msg_id in pending_acks:
                    print(f"✅ ACK recibido para {msg_id}")
                    del pending_acks[msg_id]
                    if ack_update_callback:
                         ack_update_callback(msg_id, "ack")



                
                

def ack_manager_thread():
    while not stop_event.is_set():
        time.sleep(1)
        now = time.time()
        resend_list = []

        with mutex:
            pending_keys = list(pending_acks.keys())
            for msg_id in pending_keys:
                info = pending_acks.get(msg_id)
                if info is None:
                    continue  # ya fue eliminado
                if now - info["timestamp"] > ACK_TIMEOUT:
                    if info["retries"] < MAX_RETRIES:
                        print(f"⚠️ Reintentando envío de {msg_id} a {info['dst']} (intento {info['retries']+1})")
                        info["retries"] += 1
                        info["timestamp"] = now
                        # ❌ Solo poner en send_queue **si todavía existe**
                        send_queue.put((5, info["dst"], str(msg_id), info["info"]))
                    else:
                        print(f"❌ Fallo permanente: no se recibió ACK para {msg_id}")
                        if ack_update_callback:  # si la GUI registró un callback
                              ack_update_callback(msg_id, "failed")
                        del pending_acks[msg_id]




if __name__ == "__main__":
    threads = []

    t_in = threading.Thread(target=input_thread, daemon=True)
    t_send = threading.Thread(target=sender_thread, daemon=True)
    t_recv = threading.Thread(target=receiver_thread, daemon=True)
    t_ann = threading.Thread(target=announce_thread, daemon=True)
    t_ack = threading.Thread(target=ack_manager_thread, daemon=True)
    threads.extend([t_ann, t_in, t_send, t_recv, t_ack])


    # Iniciar los hilos
    for t in threads:
        t.start()

    # send_queue.put((1, SENDER_MAC.lower(), b"hola carlos"))

    for t in threads:
        t.join()


