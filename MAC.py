import socket
import struct
import fcntl
import array
import os

# Obtener interfaz principal
def get_default_iface():
    with open("/proc/net/route") as f:
        for line in f.readlines()[1:]:
            iface, dest, _, flags, _, _, _, _, _, _, _ = line.strip().split()
            if dest == "00000000":
                return iface
    return None

# Obtener IP de la interfaz
def get_iface_ip(iface):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', iface[:15].encode())
    )[20:24])

# Obtener MAC de la interfaz
def get_iface_mac(iface):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info = fcntl.ioctl(
        s.fileno(),
        0x8927,  # SIOCGIFHWADDR
        struct.pack('256s', iface[:15].encode())
    )
    return ':'.join('%02x' % b for b in info[18:24])

# Construir trama ARP
def build_arp_request(src_mac, src_ip, target_ip):
    dst_mac = b"\xff\xff\xff\xff\xff\xff"  # broadcast
    src_mac_bytes = bytes.fromhex(src_mac.replace(":", ""))
    eth_hdr = dst_mac + src_mac_bytes + struct.pack("!H", 0x0806)

    # ARP packet
    hw_type = struct.pack("!H", 1)     # Ethernet
    proto_type = struct.pack("!H", 0x0800) # IPv4
    hw_size = struct.pack("!B", 6)
    proto_size = struct.pack("!B", 4)
    opcode = struct.pack("!H", 1)      # request

    src_ip_bytes = socket.inet_aton(src_ip)
    target_ip_bytes = socket.inet_aton(target_ip)

    arp_hdr = hw_type + proto_type + hw_size + proto_size + opcode
    arp_hdr += src_mac_bytes + src_ip_bytes
    arp_hdr += b"\x00"*6 + target_ip_bytes

    return eth_hdr + arp_hdr

# Escanear red
def arp_scan():
    iface = get_default_iface()
    if iface is None:
        print("❌ No se encontró interfaz de red.")
        return

    my_ip = get_iface_ip(iface)
    my_mac = get_iface_mac(iface)

    print(f"Interfaz: {iface}")
    print(f"Mi IP: {my_ip}")
    print(f"Mi MAC: {my_mac}")

    sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0003))
    sock.bind((iface, 0))

    ip_base = ".".join(my_ip.split(".")[:-1]) + "."

    found = {}

    for i in range(1, 255):
        target_ip = ip_base + str(i)
        pkt = build_arp_request(my_mac, my_ip, target_ip)
        sock.send(pkt)

    sock.settimeout(3)
    try:
        while True:
            pkt = sock.recv(2048)
            eth_proto = struct.unpack("!H", pkt[12:14])[0]
            if eth_proto == 0x0806:  # ARP
                src_mac = ':'.join('%02x' % b for b in pkt[6:12])
                src_ip = socket.inet_ntoa(pkt[28:32])
                if src_ip not in found:
                    found[src_ip] = src_mac
    except socket.timeout:
        pass

    print("\nDispositivos encontrados en la red:")
    for ip, mac in found.items():
        print(f"{ip}  ->  {mac}")

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("⚠️ Debes ejecutar este script con sudo")
    else:
        arp_scan()
