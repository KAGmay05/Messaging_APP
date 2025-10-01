import customtkinter as ctk
from tkinter import filedialog
import socket
import uuid
import threading
import ipaddress
import subprocess
import platform

# ---------- Funciones auxiliares ----------

def get_mac_address():
    mac = uuid.getnode()
    return ':'.join([f'{(mac >> ele) & 0xff:02x}' for ele in range(40, -1, -8)])

def ping(host):
    """Verifica si un host responde al ping."""
    param = "-n" if platform.system().lower() == "windows" else "-c"
    try:
        subprocess.check_output(
            ["ping", param, "1", host],
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        return True
    except subprocess.CalledProcessError:
        return False

def scan_network():
    """Escanea la red local para encontrar dispositivos activos."""
    devices_listbox.delete("1.0", "end")
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
    except:
        devices_listbox.insert("end", "No se pudo obtener la IP local\n")
        return

    net = ipaddress.ip_network(local_ip + "/24", strict=False)
    devices_listbox.insert("end", "Escaneando la red...\n")

    def worker():
        devices_listbox.delete("1.0", "end")
        for host in net.hosts():
            if ping(str(host)):
                devices_listbox.insert("end", f"Dispositivo activo: {host}\n")
        if devices_listbox.get("1.0", "end").strip() == "":
            devices_listbox.insert("end", "No se encontraron dispositivos\n")

    threading.Thread(target=worker, daemon=True).start()

def browse_file():
    """Abre el explorador de archivos y guarda la ruta en file_var."""
    filepath = filedialog.askopenfilename()
    if filepath:
        file_var.set(filepath)
        chat_box.insert("end", f"Archivo seleccionado: {filepath}\n")

def send_action():
    """Simula el envío de un mensaje o archivo."""
    message = input_var.get().strip()
    file_path = file_var.get().strip()

    if message:
        chat_box.insert("end", f"Tú: {message}\n")
        input_var.set("")

    if file_path:
        chat_box.insert("end", f"Tú enviaste un archivo: {file_path}\n")
        file_var.set("")

# ---------- Ventana principal ----------

ctk.set_appearance_mode("light")  # "dark" para modo oscuro
ctk.set_default_color_theme("blue")

root = ctk.CTk()
root.title("Mensajería Capa de Enlace")
root.geometry("800x500")

# Layout principal: panel lateral + panel chat
main_frame = ctk.CTkFrame(root, corner_radius=0)
main_frame.pack(fill="both", expand=True)

# Panel lateral (lista de dispositivos)
sidebar = ctk.CTkFrame(main_frame, width=200, corner_radius=0)
sidebar.pack(side="left", fill="y")

sidebar_label = ctk.CTkLabel(sidebar, text="Dispositivos en red", font=("", 14, "bold"))
sidebar_label.pack(pady=10)

devices_listbox = ctk.CTkTextbox(sidebar, width=180, height=350)
devices_listbox.pack(padx=10, pady=5, fill="both", expand=True)

scan_button = ctk.CTkButton(sidebar, text="Escanear red", command=scan_network)
scan_button.pack(pady=10)

# Panel de chat
chat_frame = ctk.CTkFrame(main_frame, corner_radius=12)
chat_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

# Info del usuario (solo MAC)
mac_label = ctk.CTkLabel(chat_frame, text=f"Tu MAC: {get_mac_address()}")
mac_label.pack(anchor="w", padx=20, pady=(10, 10))

# Caja de chat
chat_box = ctk.CTkTextbox(chat_frame, width=500, height=250)
chat_box.pack(pady=10, padx=20, fill="both", expand=True)

# Entrada de mensaje
input_var = ctk.StringVar()
input_entry = ctk.CTkEntry(chat_frame, textvariable=input_var, placeholder_text="Escribe tu mensaje aquí...")
input_entry.pack(pady=5, padx=20, fill="x")

# Botón de seleccionar archivo
file_var = ctk.StringVar()
file_button = ctk.CTkButton(chat_frame, text="Seleccionar archivo", command=browse_file)
file_button.pack(pady=5)

# Botón de enviar
send_button = ctk.CTkButton(chat_frame, text="Enviar", command=send_action)
send_button.pack(pady=10)

root.mainloop()
