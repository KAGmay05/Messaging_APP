import subprocess  #ejecutar comandos del sistema operativo 

def get_container_macs():
    containers = {}
    interfaces_output = subprocess.check_output(["ip", "-o", "link", "show"], text=True)  #Ejecuta el comando ip -o link show en el sistema operativo.-o produce salida “oneline” (cada interfaz en una línea), subprocess.check_output captura la salida como texto (text=True) y la guarda en interfaces_output.
    macvlan_ifaces = [line.split(":")[1].strip() for line in interfaces_output.splitlines() if "macvlan" in line]  #interfaces_output.splitlines() divide la salida en una lista de líneas, luego filtra solo las líneas que contienen "macvlan" (tu red virtual). line.split(":")[1].strip() extrae el nombre de la interfaz de esa línea.
 
    if not macvlan_ifaces:
        print("No se encontró ninguna interfaz macvlan.")
        return {}

    iface = macvlan_ifaces[0].split("@")[0]  #macvlan_ifaces[0] toma la primera interfaz encontrada, split("@")[0] elimina la parte @parent para usar solo el nombre base

    try:
        neigh_output = subprocess.check_output(["ip", "neigh", "show", "dev", iface], text=True) #Ejecuta ip neigh show dev <iface> para obtener la tabla ARP de la interfaz macvlan, ip neigh muestra la relación IP → MAC que el sistema conoce.
    except subprocess.CalledProcessError:#La tabla ARP (Address Resolution Protocol) es una lista que mantiene el sistema operativo para mapear direcciones IP a direcciones MAC en una red local
        print("No se pudo leer la tabla ARP con 'ip neigh'.")
        return {}

    for line in neigh_output.splitlines(): #Itera por cada línea de la tabla ARP (neigh_output.splitlines()), divide la línea en palabras (line.split()).Busca "lladdr" que indica la MAC asociada, mac_addr = parts[parts.index("lladdr") + 1] obtiene la dirección MAC, state captura el estado de la entrada (REACHABLE, STALE o FAILED) si existe
        parts = line.split()
        if "lladdr" in parts:  #lladdr significa “link-layer address”, es decir, la dirección de capa de enlace, que en términos prácticos es la dirección MAC del dispositivo
            ip_addr = parts[0]
            mac_addr = parts[parts.index("lladdr") + 1]

            try:
                inspect_out = subprocess.check_output(["sudo", "docker", "ps", "--format", "{{.Names}} {{.ID}} {{.Networks}}"],text=True)
                name = "Desconocido"
                for cont_line in inspect_out.splitlines():
                    try:
                        name_out = subprocess.check_output(["sudo", "docker", "ps", "--filter", f"network={iface}", "--format", "{{.Names}}"],text=True)
                        for n in name_out.splitlines():
                            ip_check = subprocess.check_output(["sudo","docker", "inspect", "-f","{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", n],text=True).strip()
                            if ip_check == ip_addr:
                                name = n
                                break
                    except subprocess.CalledProcessError:
                        pass

                containers[name] = mac_addr
            except subprocess.CalledProcessError:
                containers["Desconocido"] = mac_addr
    return containers


if __name__ == "__main__":
    result = get_container_macs()
    if result:
        print("Contenedores y sus MACs:")
        for name, mac in result.items():
            print(f"{name} -> {mac}")
    else:
        print("No se detectaron contenedores en la red macvlan.")

