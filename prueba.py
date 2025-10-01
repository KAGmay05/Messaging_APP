#!/usr/bin/env python3
"""
Esqueleto: mensajería a nivel de enlace con 4 hilos y 2 colas.
- Hilos: input, sender, receiver, neighbors
- Colas: send_queue (mensajes/archivos a mandar), recv_queue (lo que llega decodificado)
- Reensamblado simple de archivos (por remitente). Para producción añadir file_id.
"""

import threading
import queue
import socket
import time
import os
import frame   # tu módulo encode/decode
from typing import Tuple, Dict

# -------------------------
# Configuración
# -------------------------
INTERFACE = "wlo1"                       # interfaz a usar
MI_MAC = "08:14:f4:d5:66:9a"             # tu MAC (6 pares hex)
BCAST_MAC = "ff:ff:ff:ff:ff:ff"
ETHERTYPE = 0x88B5
HELLO_INTERVAL = 5                       # segundos entre HELLOs
NEIGHBOR_TIMEOUT = 20                    # considerar vecino muerto si no responde en X s

# -------------------------
# Colas y estructuras
# -------------------------
send_queue = queue.Queue()               # elementos: ('msg'|'file', dest_mac, data_or_path)
recv_queue = queue.Queue()               # elementos: dict con keys del frame decodificado

neighbors: Dict[str, Dict] = {}          # mac -> {'last_seen': float, 'name': str}
neighbors_lock = threading.Lock()

# Buffer para reensamblado de archivos (key: sender_mac)
reassembly_buffers: Dict[str, Dict] = {} # sender -> {'total': int, 'parts': {num: bytes}}

# -------------------------
# Helper: crear socket AF_PACKET
# -------------------------
def make_raw_socket() -> socket.socket:
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETHERTYPE))
    s.bind((INTERFACE, 0))
    return s

# -------------------------
# Hilo 1: lectura de usuario (input)
# Sintaxis simple:
# - Enviar mensaje:         @<mac> texto...      (si no pones @mac -> broadcast)
# - Enviar archivo:         file @<mac> /ruta/a/archivo
# -------------------------
def hilo_input():
    print("Comandos:\n  @<mac> mensaje   (ej: @aa:bb:cc:11:22:33 Hola)\n  file @<mac> /ruta\n  file /ruta   (broadcast)\n")
    while True:
        try:
            linea = input("> ").strip()
        except EOFError:
            break

        if not linea:
            continue

        if linea.startswith("file "):
            parts = linea.split(maxsplit=2)
            # file @mac path  OR file path
            if len(parts) == 3 and parts[1].startswith("@"):
                dest = parts[1][1:]
                path = parts[2]
            elif len(parts) >= 2:
                dest = BCAST_MAC
                path = parts[1]
            else:
                print("Uso: file @<mac> /ruta  OR  file /ruta")
                continue

            if not os.path.isfile(path):
                print("Archivo no existe:", path)
                continue

            send_queue.put(("file", dest.lower(), path))
        else:
            # Mensaje: opcionalmente @mac al inicio
            if linea.startswith("@"):
                try:
                    mac, msg = linea.split(maxsplit=1)
                    dest = mac[1:].lower()
                except ValueError:
                    print("Uso: @<mac> mensaje")
                    continue
            else:
                dest = BCAST_MAC
                msg = linea
            send_queue.put(("msg", dest, msg.encode("utf-8")))


# -------------------------
# Hilo 2: envío (mensajes + archivos fragmentados)
# -------------------------
def hilo_sender():
    s = make_raw_socket()
    print("[sender] socket listo en", INTERFACE)
    FRAG_SIZE = 1400   # tamaño por fragmento (ajustable)

    while True:
        tipo, dest_mac, payload = send_queue.get()
        try:
            if tipo == "msg":
                # payload es bytes
                frame_bytes = frame.encode(dest_mac, MI_MAC, ETHERTYPE, 1, 1, 1, payload)
                s.send(frame_bytes)
            elif tipo == "file":
                ruta = payload
                with open(ruta, "rb") as f:
                    data = f.read()
                total_frag = (len(data) + FRAG_SIZE - 1) // FRAG_SIZE or 1
                for i in range(total_frag):
                    frag = data[i*FRAG_SIZE:(i+1)*FRAG_SIZE]
                    frame_bytes = frame.encode(dest_mac, MI_MAC, ETHERTYPE, 2, i+1, total_frag, frag)
                    s.send(frame_bytes)
                    # pequeña pausa para no saturar la NIC si el archivo es grande
                    time.sleep(0.005)
                print(f"[sender] archivo '{ruta}' enviado a {dest_mac} en {total_frag} fragmentos")
            else:
                print("[sender] tipo desconocido en cola:", tipo)
        except PermissionError:
            print("[sender] Error: necesitar ejecutar como root para sockets RAW")
        except Exception as e:
            print("[sender] excepción:", e)


# -------------------------
# Función para procesar items del recv_queue
# -------------------------
def procesar_recibidos():
    """
    Consume todos los elementos en recv_queue y:
      - imprime mensajes
      - reensambla archivos por remitente (clave = sender MAC)
      - actualiza neighbors si llega HELLO/HELLO-REPLY
    """
    while True:
        try:
            item = recv_queue.get_nowait()
        except queue.Empty:
            break

        sender = item["sender"]
        tipo = item["tipo"]
        info = item["info"]

        if tipo == 1:
            # Mensaje de texto
            try:
                texto = info.decode("utf-8", errors="replace")
            except Exception:
                texto = repr(info)
            print(f"\n[Mensaje] {sender} -> {texto}\n> ", end="", flush=True)

        elif tipo == 2:
            # Fragmento de archivo: guardar en buffer por sender
            num = item["num_frag"]
            total = item["total_frag"]
            buf = reassembly_buffers.setdefault(sender, {"total": total, "parts": {}})
            buf["parts"][num] = info
            buf["total"] = total
            # si ya tenemos todos los fragmentos:
            if len(buf["parts"]) == buf["total"]:
                # ensamblar en orden
                data = b"".join(buf["parts"][i] for i in range(1, buf["total"] + 1))
                timestamp = int(time.time())
                fname = f"archivo_de_{sender.replace(':','')}_{timestamp}.bin"
                with open(fname, "wb") as f:
                    f.write(data)
                print(f"\n[Archivo recibido] de {sender} guardado en {fname} ({len(data)} bytes)\n> ", end="", flush=True)
                del reassembly_buffers[sender]

        elif tipo == 3:
            # HELLO recibido: payload puede contener nombre del nodo
            try:
                name = info.decode("utf-8", errors="ignore")
            except:
                name = ""
            with neighbors_lock:
                neighbors[sender] = {"last_seen": time.time(), "name": name}
            # responder HELLO-REPLY (opcional) -> lo hacemos en recv thread que llamó a esta func
        elif tipo == 4:
            # HELLO-REPLY: update neighbors
            try:
                name = info.decode("utf-8", errors="ignore")
            except:
                name = ""
            with neighbors_lock:
                neighbors[sender] = {"last_seen": time.time(), "name": name}
        else:
            print(f"[recv] Tipo desconocido {tipo} de {sender}")

# -------------------------
# Hilo 3: recepción (escucha y encola decodificados)
# - Además responde HELLO automáticamente
# -------------------------
def hilo_receiver():
    s = make_raw_socket()
    s_tx = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETHERTYPE))
    s_tx.bind((INTERFACE, 0))  # socket para enviar respuestas (HELLO-REPLY)

    print("[receiver] escuchando en", INTERFACE)
    while True:
        try:
            raw_frame, addr = s.recvfrom(65535)
            try:
                receiver, sender, etype, tipo, num_frag, total_frag, length, info = frame.decode(raw_frame)
            except Exception:
                # frame inválido / CRC fallido -> ignorar
                continue

            sender = sender.lower()
            # ignora los frames que yo mismo envié (opcional)
            if sender == MI_MAC.lower():
                continue

            # encolar lo decodificado en recv_queue para su procesamiento
            recv_queue.put({
                "sender": sender,
                "receiver": receiver,
                "ethertype": etype,
                "tipo": tipo,
                "num_frag": num_frag,
                "total_frag": total_frag,
                "length": length,
                "info": info
            })

            # Si es HELLO, responder HELLO-REPLY con nombre
            if tipo == 3:
                my_name = ("node-" + MI_MAC.split(":")[-1])[:32].encode("utf-8")
                reply_frame = frame.encode(sender, MI_MAC, ETHERTYPE, 4, 1, 1, my_name)
                s_tx.send(reply_frame)

            # procesar la cola localmente (sin añadir hilo extra)
            procesar_recibidos()

        except PermissionError:
            print("[receiver] Error: ejecutar como root para AF_PACKET")
            time.sleep(1)
        except Exception as e:
            print("[receiver] excepción:", e)
            time.sleep(0.1)


# -------------------------
# Hilo 4: descubrimiento de vecinos (envía HELLO periódicamente)
# -------------------------
def hilo_neighbors():
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETHERTYPE))
    s.bind((INTERFACE, 0))
    my_name = ("node-" + MI_MAC.split(":")[-1])[:32].encode("utf-8")

    while True:
        try:
            # HELLO broadcast (tipo=3)
            hello_frame = frame.encode(BCAST_MAC, MI_MAC, ETHERTYPE, 3, 1, 1, my_name)
            s.send(hello_frame)
        except Exception as e:
            print("[neighbors] excepcion al mandar HELLO:", e)

        # limpiar vecinos que no respondieron en NEIGHBOR_TIMEOUT
        with neighbors_lock:
            now = time.time()
            stale = [mac for mac, info in neighbors.items() if now - info["last_seen"] > NEIGHBOR_TIMEOUT]
            for mac in stale:
                del neighbors[mac]

        # imprimir tabla simple de vecinos
        with neighbors_lock:
            if neighbors:
                print("\n[Vecinos activos]")
                for mac, info in neighbors.items():
                    age = int(time.time() - info["last_seen"])
                    print(f"  {mac}  ({info.get('name','')})  last_seen: {age}s")
                print("> ", end="", flush=True)

        time.sleep(HELLO_INTERVAL)


# -------------------------
# Main: lanzar hilos
# -------------------------
def main():
    threads = [
        threading.Thread(target=hilo_input, daemon=True),
        threading.Thread(target=hilo_sender, daemon=True),
        threading.Thread(target=hilo_receiver, daemon=True),
        threading.Thread(target=hilo_neighbors, daemon=True),
    ]
    for t in threads:
        t.start()
    print("Sistema iniciado. Presiona Ctrl+C para salir.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Saliendo...")

if __name__ == "__main__":
    main()
