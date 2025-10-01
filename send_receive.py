import socket
import frame
import threading

def send(interf, receiver_mac, sender_mac, info, ethertype, type, num_frag, total_frag):
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ethertype))
    s.bind((interf, 0))
    fram = frame.encode(receiver_mac, sender_mac, ethertype, type, num_frag, total_frag, info)
    s.send(fram)

def receive(interf, ethertype):
    s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ethertype))
    s.bind((interf, 0))
    frame_received, addr = s.recvfrom(65535)
    receiver, sender, ethertype_received, type, num_frag, total_frag, length, info = frame.decode(frame_received)
    print(info)
    
mi_mac = "08:14:f4:d5:66:9a"
tu_mac = "ff:ff:ff:ff:ff"
ethert = (0x88B5)
interfaz = "wlo1"

while True:
    mesg = input("> ")
    receive(interfaz,ethert)
    if not mesg.strip():
        continue
    send(interfaz, tu_mac, mi_mac, mesg.encode("utf-8"), ethert, 1, 1, 1)