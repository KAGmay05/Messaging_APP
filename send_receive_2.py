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
CHUNK_SIZE = 1300
WINDOW_SIZE = 30
SENDER_MAC = None

send_queue = queue.Queue()
recv_queue = queue.Queue()
reassembly_buffers: Dict[Tuple[str,int], Dict] = {}
known_macs: Dict[str, str] = {}
mutex = threading.RLock()
pending_acks_lock = threading.Lock() 
username = None

stop_event = threading.Event() 

pending_acks = {}  # msg_id -> {dst, info, retries, timestamp}
file_windows: Dict[str, Dict[int, Dict]] = {}
ACK_TIMEOUT = 3.0  # segundos antes de reintentar
MAX_RETRIES = 3

ACK_TIMEOUT_2 = 10.0  # segundos antes de reintentar
MAX_RETRIES_2 = 5

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

def enqueue_window(file_id):
    """Envía los primeros fragmentos de la ventana de un archivo"""
    with mutex:
        if file_id not in file_windows:
            return

        pending = file_windows[file_id]
        # Fragmentos aún no enviados
        window = [frag_num for frag_num in sorted(pending) if not pending[frag_num].get("sent", False)]
        for frag_num in window[:WINDOW_SIZE]:
            frag_info = pending[frag_num]
            send_queue.put((2, frag_info["dst"], int(file_id), frag_num, frag_info["total"], frag_info["info"]))
            frag_info["sent"] = True
            frag_info["timestamp"] = time.time() 
           


def announce_thread():
    while not stop_event.is_set():
        if username:
            data = f"{username}|{SENDER_MAC}".encode()
        else:
            data = SENDER_MAC.encode()
        send_queue.put((3, BROADCAST.lower(), data))
        time.sleep(5)
      

def sender_thread():
    s = raw_socket()
    while not stop_event.is_set():
        item = send_queue.get()
        msg_type = item[0]
        
        if msg_type in (1, 5):
            _, dst, msg_id, info = item
            frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, 1, 1, 1, 0, str(msg_id).encode() + b"||" + info)
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
            frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, msg_type, frag_num, total_frag,file_id, info)
        
        elif msg_type == 3:  # anuncio
            _, dst, info = item
            frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, msg_type, 1, 1, 0,info)
        elif msg_type == 4:  # ACK
             print("llllllllllllllllllllll")
             _, dst, info = item
             frame_bytes = frame.encode(dst, SENDER_MAC, ETHERTYPE, msg_type, 1, 1, 0, info)

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
        file_id = decoded["file_id"]

        if receiver != SENDER_MAC.lower() and receiver != BROADCAST.lower():
            continue

        if msg_type == 1:  # Mensaje de texto
            try:
                msg_id, payload = payload.split(b"||", 1)
                msg_id = msg_id.decode()
            except:
                msg_id = None
                payload = payload

            text = payload.decode(errors='ignore')
            recv_queue.put((sender, text))
            print(f"[Mensaje de {sender}]: {text}")

            with mutex:
                if msg_id:
                    ack_data = msg_id.encode()
                    send_queue.put((4, sender, ack_data))

        elif msg_type == 2:  # Fragmento de archivo
            try:
                header, frag = payload.split(b"||", 1)
                file_name = header.decode(errors="ignore")
            except Exception:
                file_name, frag = "desconocido.bin", payload

            key = (sender, file_id)
            with mutex:
                if key not in reassembly_buffers:
                    reassembly_buffers[key] = {
                        "total": total_frag,
                        "parts": {},
                        "file_name": file_name
                    }

                reassembly_buffers[key]["parts"][num_frag] = frag

                # Si ya tenemos todos los fragmentos
                if len(reassembly_buffers[key]["parts"]) == total_frag:
                    ordered = b"".join(
                        reassembly_buffers[key]["parts"][i] for i in range(1, total_frag + 1)
                    )
                    save_name = f"recv_{file_name}"
                    ff.bytes_to_file(ordered, save_name)
                    print(f"💾 Archivo recibido de {sender}: {save_name} ({len(ordered)} bytes)")
                    recv_queue.put((2, sender, save_name, len(ordered)))
                    del reassembly_buffers[key]

                # Enviar ACK del fragmento
                ack_payload = f"{file_name}:{num_frag}".encode()
                send_queue.put((4, sender, ack_payload))

        elif msg_type == 3:  # Anuncio
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
                data = f"{username}|{SENDER_MAC}".encode() if username else SENDER_MAC.encode()
                send_queue.put((3, sender, data))

        elif msg_type == 4:  # ACK
            ack_data = payload.decode(errors="ignore").strip()
            with mutex:
                if ":" in ack_data:  # ACK de fragmento de archivo
                    file_name, frag_num = ack_data.split(":", 1)
                    frag_num = int(frag_num)
                    print(f"✅ ACK{frag_num} recibido")
                    for file_id, frags in list(file_windows.items()):
                        # buscar fragmento correspondiente
                        frag_to_delete = None
                        for fn, info in frags.items():
                            header_name = info["info"].split(b'||')[0].decode()
                            if header_name == file_name and fn == frag_num:
                                frag_to_delete = fn
                                dst_mac = info["dst"]
                                break

                        if frag_to_delete is not None:
                            del frags[frag_to_delete]
                            enqueue_window(file_id)

                            # MARCAR COMPLETADO si no quedan fragmentos
                            if len(frags) == 0:
                                file_windows[file_id]["completed"] = True
                                del file_windows[file_id]
                                print(f"✅ Archivo {file_name} enviado completamente")
                                if ack_update_callback:
                                    ack_update_callback(file_id, "ack")
                        break

                else:  # ACK de mensaje de texto
                    msg_id = str(ack_data)
                    if msg_id in pending_acks:
                        print(f"✅ ACK recibido para {msg_id}")
                        del pending_acks[msg_id]
                        if ack_update_callback:
                            ack_update_callback(msg_id, "ack")



def ack_manager_thread():
    while not stop_event.is_set():
        time.sleep(1)
        now = time.time()

        with mutex:
            # Reintentos de mensajes de texto
            for msg_id in list(pending_acks.keys()):
                info = pending_acks.get(msg_id)
                if info is None:
                    continue
                if now - info["timestamp"] > ACK_TIMEOUT:
                    if info["retries"] < MAX_RETRIES:
                        info["retries"] += 1
                        info["timestamp"] = now
                        send_queue.put((5, info["dst"], str(msg_id), info["info"]))
                        print(f"🔄 Reenviando mensaje {msg_id} a {info['dst']} (intento {info['retries']})")
                    else:
                        print(f"❌ Fallo permanente: no se recibió ACK para mensaje {msg_id}")
                        if ack_update_callback:
                            ack_update_callback(msg_id, "failed")
                        del pending_acks[msg_id]

            # Reintentos de fragmentos de archivos
            for file_id, frags in list(file_windows.items()):
                if not frags or file_windows[file_id].get("completed", False):
                    continue  # ya completado, no reenviar

                for frag_num, frag_info in list(frags.items()):
                    elapsed = now - frag_info.get("timestamp", 0)
                    if elapsed > ACK_TIMEOUT_2:
                        if frag_info["retries"] < MAX_RETRIES_2:
                            frag_info["retries"] += 1
                            frag_info["timestamp"] = now
                            send_queue.put((
                                2,
                                frag_info["dst"],
                                file_id,
                                frag_num,
                                frag_info["total"],
                                frag_info["info"]
                            ))
                            print(f"🔄 Reenviando fragmento {frag_num} de {file_id} a {frag_info['dst']} (intento {frag_info['retries']})")
                        else:
                            print(f"❌ Fallo permanente: fragmento {frag_num} de {file_id} no fue ACKeado")
                            if ack_update_callback:
                                
                                ack_update_callback(file_id, "failed")
                            del frags[frag_num]


if __name__ == "__main__":
    threads = []

    #t_in = threading.Thread(target=input_thread, daemon=True)
    t_send = threading.Thread(target=sender_thread, daemon=True)
    t_recv = threading.Thread(target=receiver_thread, daemon=True)
    t_ann = threading.Thread(target=announce_thread, daemon=True)
    t_ack = threading.Thread(target=ack_manager_thread, daemon=True)
    threads.extend([t_ann,  t_send, t_recv, t_ack])


    # Iniciar los hilos
    for t in threads:
        t.start()

    # send_queue.put((1, SENDER_MAC.lower(), b"hola carlos"))

    for t in threads:
        t.join()


