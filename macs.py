#!/usr/bin/env python3
import subprocess
import re

def run_cmd(cmd):
    """Ejecuta un comando en bash y devuelve la salida como string"""
    return subprocess.check_output(cmd, shell=True, text=True).strip()

# 1. Saber la dirección de red (usamos ip route para obtener el prefijo local)
network = run_cmd("ip route | awk '/proto kernel/ {print $1; exit}'")
print(f"[+] Red detectada: {network}")

prefix = ".".join(network.split(".")[:3])

# 2. Hacer ping a todos los hosts de la red (/24 asumido)
print("[+] Escaneando la red con ping...")
run_cmd(f"for i in $(seq 1 254); do ping -c1 -W1 {prefix}.`echo $i` >/dev/null && echo {prefix}.$i activo & done; wait")

# 3. Mostrar vecinos con MAC conocidos (filtrando INCOMPLETE)
print("[+] Vecinos encontrados con MAC:")
neigh_output = run_cmd("ip neigh show | grep -v INCOMPLETE")

ip_mac_pairs = re.findall(r"(\d+\.\d+\.\d+\.\d+).*?([0-9a-f:]{17})", neigh_output, re.IGNORECASE)

# Crear dos variables separadas
ips = [pair[0] for pair in ip_mac_pairs]  # Lista de IPs
macs = [pair[1] for pair in ip_mac_pairs]  # Lista de MACs

# También puedes mostrarlas juntas si quieres
print("\n[+] Relación IP -> MAC:")
for ip, mac in ip_mac_pairs:
    print(f" {ip} -> {mac}")