import subprocess
import re

def get_bluetooth_devices():
    devices = {}

    try:
        # Obtener conexiones activas
        output = subprocess.check_output(["hcitool", "con"], text=True)
    except FileNotFoundError:
        print("hcitool no está instalado.")
        return {}
    except subprocess.CalledProcessError:
        return {}

    # Buscar todas las direcciones MAC
    macs = re.findall(r"[0-9A-F]{2}(?::[0-9A-F]{2}){5}", output, re.I)

    for mac in macs:
        try:
            # Consultar el nombre del dispositivo por MAC
            name = subprocess.check_output(["hcitool", "name", mac], text=True).strip()
            if not name:   # Si no devuelve nada, le ponemos un alias
                name = "Desconocido"
        except subprocess.CalledProcessError:
            name = "Desconocido"

        devices[name] = mac   # Guardar en diccionario: {nombre: mac}

    return devices
