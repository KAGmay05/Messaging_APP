import tkinter as tk
from tkinter import scrolledtext
import threading
import send_receive_2 as main
import sys
from tkinter import filedialog
import os
import file_fragments as ff

# ---------- Colores y estilos ----------
BG_COLOR = "#f7f7f7"
PEER_BG = "#d0f0fd"
CHAT_BG = "#ffffff"
ENTRY_BG = "#e0f7fa"
BUTTON_BG = "#81d4fa"
TEXT_COLOR = "#212121"
BUBBLE_SELF = "#c8e6c9"
BUBBLE_PEER = "#ffe0b2"
FONT_MAIN = ("Helvetica", 12)
FONT_TITLE = ("Helvetica", 24, "bold")
USERNAME_COLOR = "#0288d1"

# ---------- Login ----------
login_root = tk.Tk()
login_root.title("Messaging APP")
login_root.configure(bg=BG_COLOR)
login_root.geometry("450x250")
login_root.resizable(False, False)

tk.Label(login_root, text="Messaging APP", font=FONT_TITLE, bg=BG_COLOR, fg=USERNAME_COLOR).pack(pady=25)
tk.Label(login_root, text="Ingrese su nombre de usuario:", font=FONT_MAIN, bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=5)

username_entry = tk.Entry(login_root, font=FONT_MAIN, bg=ENTRY_BG, fg=TEXT_COLOR, bd=2, relief=tk.GROOVE)
username_entry.pack(pady=10, ipadx=5, ipady=5)

# ---------- Cierre seguro ----------
def on_close():
    main.stop_event.set()
    login_root.destroy()
    sys.exit(0)

login_root.protocol("WM_DELETE_WINDOW", on_close)

# ---------- Ventana de chat ----------
def start_chat_window(chat_root):
    chat_root.title(f"Chat RAW - {main.username}")
    chat_root.configure(bg=BG_COLOR)
    chat_root.geometry("900x500")

    chat_history = {}  # mac -> lista de mensajes
    broadcast_mode = tk.BooleanVar(value=False)
    selected_peer_mac = [None]
    selected_index = [None]

    # --- Panel lateral de peers ---
    peer_frame = tk.Frame(chat_root, bg=PEER_BG, bd=2, relief=tk.RIDGE)
    peer_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

    tk.Label(peer_frame, text="Usuarios conectados", bg=PEER_BG, fg=TEXT_COLOR,
             font=("Helvetica", 14, "bold")).pack(pady=5)

    # Lista de usuarios
    peer_listbox = tk.Listbox(peer_frame, width=25, bg=PEER_BG, fg=TEXT_COLOR, bd=0, highlightthickness=0,
                              font=("Helvetica", 11))
    peer_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # --- Checkbox "Enviar a todos" al final ---
    def update_peer_highlight():
        for i in range(peer_listbox.size()):
            if broadcast_mode.get():
                # Broadcast activo: todos gris
                peer_listbox.itemconfig(i, bg="#cccccc", fg="#000000")
            else:
                # Broadcast inactivo: todos normales
                peer_listbox.itemconfig(i, bg=PEER_BG, fg=TEXT_COLOR)

        # Sombrear solo el seleccionado si no hay broadcast
        if not broadcast_mode.get() and selected_index[0] is not None:
            if selected_index[0] < peer_listbox.size():
                peer_listbox.itemconfig(selected_index[0], bg="#bbbbbb")

    broadcast_checkbox = tk.Checkbutton(
        peer_frame,
        text="Enviar a todos",
        bg=PEER_BG,
        fg=TEXT_COLOR,
        font=("Helvetica", 11, "bold"),
        variable=broadcast_mode,
        command=update_peer_highlight
    )
    broadcast_checkbox.pack(side=tk.BOTTOM, pady=(10, 5))

    # --- Panel de chat ---
    chat_frame = tk.Frame(chat_root, bg=CHAT_BG, bd=2, relief=tk.RIDGE)
    chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)

    chat_frame.columnconfigure(0, weight=1)
    chat_frame.rowconfigure(0, weight=1)
    chat_frame.rowconfigure(1, weight=0)

    chat_text = scrolledtext.ScrolledText(chat_frame, state='disabled', wrap=tk.WORD, bg=CHAT_BG, fg=TEXT_COLOR, font=FONT_MAIN)
    chat_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    input_frame = tk.Frame(chat_frame, bg=CHAT_BG)
    input_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
    input_frame.columnconfigure(0, weight=1)
    input_frame.columnconfigure(1, weight=0)

    message_entry = tk.Entry(input_frame, bg=ENTRY_BG, fg=TEXT_COLOR, font=FONT_MAIN)
    message_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

    send_button = tk.Button(input_frame, text="Enviar", bg=BUTTON_BG, fg=TEXT_COLOR, font=("Helvetica", 11, "bold"), width=10)
    send_button.grid(row=0, column=1, sticky="ew")

    file_path = tk.StringVar()

    file_button = tk.Button(input_frame, text="Enviar Archivo", bg=BUTTON_BG, fg=TEXT_COLOR, font=("Helvetica", 11, "bold"), width=12)
    file_button.grid(row=0, column=2, sticky="ew", padx=(5, 0))

    # ---------- Función para mostrar historial ----------
    def display_chat_history(mac):
        chat_text.config(state='normal')
        chat_text.delete(1.0, tk.END)
        if mac in chat_history:
            for message in chat_history[mac]:
                if message.startswith("Tú: "):
                    chat_text.insert(tk.END, f"{message}\n", "self")
                else:
                    chat_text.insert(tk.END, f"{message}\n", "peer")
        chat_text.tag_config("self", background=BUBBLE_SELF, lmargin1=10, lmargin2=10, rmargin=50)
        chat_text.tag_config("peer", background=BUBBLE_PEER, lmargin1=50, lmargin2=10, rmargin=10)
        chat_text.config(state='disabled')
        chat_text.see(tk.END)

    # ---------- Guardar mensaje ----------
    def save_message_to_history(mac, message, is_self=True):
        if mac not in chat_history:
            chat_history[mac] = []
        if is_self:
            formatted_message = f"Tú: {message}"
        else:
            sender_name = main.known_macs.get(mac, mac)
            formatted_message = f"[{sender_name}]: {message}"
        chat_history[mac].append(formatted_message)

    # ---------- Selección de usuario ----------
    def on_peer_select(event):
        selection = peer_listbox.curselection()
        if not selection:
            return

        selected_index[0] = selection[0]
        name = peer_listbox.get(selected_index[0])

        # Buscar la MAC asociada al nombre
        for mac, n in main.known_macs.items():
            if n == name:
                selected_peer_mac[0] = mac
                break

        # Mostrar historial
        if selected_peer_mac[0]:
            display_chat_history(selected_peer_mac[0])

        update_peer_highlight()  # <-- repintar correctamente según broadcast o selección

    peer_listbox.bind("<<ListboxSelect>>", on_peer_select)

    # --------- Buscar archivos en la computadora ------------
    def file_browser():
        filepath = filedialog.askopenfilename(
            title="Selecciona un archivo para enviar",
            filetypes=[
                ("Todos los archivos", "*.*"),
                ("Imágenes", "*.png;*.jpg;*.jpeg;*.gif"),
                ("Documentos", "*.pdf;*.docx;*.txt")
            ]
        )
        if filepath:
            file_path.set(filepath)
            message_entry.delete(0, tk.END)
            message_entry.insert(0, os.path.basename(filepath) + " 💾")
            message_entry.focus()
            print("Archivo seleccionado:", filepath)

    file_button.config(command=file_browser)

    # ---------- Enviar mensaje ----------
    def send_message(event=None):
        msg = message_entry.get().strip()
        filepath = file_path.get()
        if not msg or not selected_peer_mac[0]:
            return

        if filepath and os.path.isfile(filepath):
            data = ff.file_to_bytes(filepath)
            file_id = ff.id()
            total = (len(data) + main.CHUNK_SIZE - 1) // main.CHUNK_SIZE
            filename = os.path.basename(filepath)

            if broadcast_mode.get():
                # 🔹 Enviar a todos los peers conocidos
                for mac in main.known_macs.keys():
                    if mac != main.SENDER_MAC.lower():
                        for i, frag in enumerate(ff.fragment_data(data, main.CHUNK_SIZE), start=1):
                            header_info = filename.encode()
                            main.send_queue.put((2, mac, file_id, i, total, header_info + b"||" + frag))
                        save_message_to_history(mac, f"[💾 Archivo enviado: {filename}]", is_self=True)

                # 🔹 Actualizar chat actual
                if selected_peer_mac[0] in main.known_macs:
                    display_chat_history(selected_peer_mac[0])

            else:
                # 🔹 Enviar solo al usuario seleccionado
                for i, frag in enumerate(ff.fragment_data(data, main.CHUNK_SIZE), start=1):
                    header_info = filename.encode()
                    main.send_queue.put((2, selected_peer_mac[0], file_id, i, total, header_info + b"||" + frag))

                save_message_to_history(selected_peer_mac[0], f"[💾 Archivo enviado: {filename}]", is_self=True)
                display_chat_history(selected_peer_mac[0])

            file_path.set("")
        else:
            if broadcast_mode.get():
                for mac in main.known_macs.keys():
                    if mac != main.SENDER_MAC.lower():
                        main.send_queue.put((1, mac, msg.encode()))
                        save_message_to_history(mac, msg, is_self=True)
                if selected_peer_mac[0] in main.known_macs:
                     display_chat_history(selected_peer_mac[0])
            else:
                main.send_queue.put((1, selected_peer_mac[0], msg.encode()))
                save_message_to_history(selected_peer_mac[0], msg, is_self=True)
                display_chat_history(selected_peer_mac[0])
        message_entry.delete(0, tk.END)

    message_entry.bind("<Return>", send_message)
    send_button.config(command=send_message)

    # ---------- Actualizar lista de peers ----------
    def update_peers():
        peer_listbox.delete(0, tk.END)
        for mac, name in main.known_macs.items():
            if mac != main.SENDER_MAC.lower():
                peer_listbox.insert(tk.END, name)

        update_peer_highlight()  # <-- mantener sombreado correcto

        chat_root.after(1000, update_peers)

    # ---------- Actualizar mensajes ----------
    def update_messages():
        while not main.recv_queue.empty():
            msg = main.recv_queue.get()
            if isinstance(msg, tuple) and msg[0] == 2:
                # Archivo recibido
                _, sender_mac, filename, size = msg
                save_message_to_history(sender_mac,
                                        f"[💾 Archivo recibido: {filename} ({size} bytes)]",
                                        is_self=False)
                if sender_mac == selected_peer_mac[0]:
                    display_chat_history(selected_peer_mac[0])
            else:
                sender_mac, payload = msg
                save_message_to_history(sender_mac, payload, is_self=False)
                if sender_mac == selected_peer_mac[0]:
                    display_chat_history(selected_peer_mac[0])
        chat_root.after(500, update_messages)

    # ---------- Iniciar hilos ----------
    threads = [
        threading.Thread(target=main.input_thread, daemon=True),
        threading.Thread(target=main.sender_thread, daemon=True),
        threading.Thread(target=main.announce_thread, daemon=True),
        threading.Thread(target=main.receiver_thread, daemon=True)
    ]
    for t in threads:
        t.start()

    update_peers()
    update_messages()
    chat_root.protocol("WM_DELETE_WINDOW", on_close)
    chat_root.mainloop()

# ---------- Botón login ----------
def accept_username():
    name = username_entry.get().strip()
    if not name:
        return

    main.username = name
    login_root.withdraw()

    select_root = tk.Toplevel(login_root)
    select_root.title("Seleccionar red")
    select_root.configure(bg=BG_COLOR)
    select_root.geometry("400x300")
    select_root.resizable(False, False)

    tk.Label(select_root, text="Elija la red a conectarse:",
             font=("Helvetica", 16, "bold"), bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=20)

    def set_interface(interface_name):
        main.INTERFACE = interface_name
        print(f"[INFO] Interfaz seleccionada: {main.INTERFACE}")
        select_root.destroy()
        chat_root = tk.Toplevel(login_root)
        start_chat_window(chat_root)

    tk.Button(select_root, text="WiFi", font=FONT_MAIN, bg=BUTTON_BG,
              fg=TEXT_COLOR, width=20, command=lambda: set_interface("wlo1")).pack(pady=10)
    tk.Button(select_root, text="Macvlan", font=FONT_MAIN, bg=BUTTON_BG,
              fg=TEXT_COLOR, width=20, command=lambda: set_interface("eth0")).pack(pady=10)
    tk.Button(select_root, text="VM", font=FONT_MAIN, bg=BUTTON_BG,
              fg=TEXT_COLOR, width=20, command=lambda: set_interface("enp0s3")).pack(pady=10)

    def custom_interface():
        custom_root = tk.Toplevel(select_root)
        custom_root.title("Otra interfaz")
        custom_root.configure(bg=BG_COLOR)
        custom_root.geometry("350x180")
        custom_root.resizable(False, False)

        tk.Label(custom_root, text="Escriba el nombre de la interfaz:",
                 font=FONT_MAIN, bg=BG_COLOR, fg=TEXT_COLOR).pack(pady=10)
        entry_iface = tk.Entry(custom_root, font=FONT_MAIN, bg=ENTRY_BG, fg=TEXT_COLOR)
        entry_iface.pack(pady=5, ipadx=5, ipady=5)

        def confirm_custom():
            iface = entry_iface.get().strip()
            if iface:
                main.INTERFACE = iface
                print(f"[INFO] Interfaz personalizada: {main.INTERFACE}")
                custom_root.destroy()
                select_root.destroy()
                chat_root = tk.Toplevel(login_root)
                start_chat_window(chat_root)

        tk.Button(custom_root, text="Aceptar", bg=BUTTON_BG, fg=TEXT_COLOR,
                  font=("Helvetica", 11, "bold"), command=confirm_custom).pack(pady=10)

    tk.Button(select_root, text="Otro...", font=FONT_MAIN, bg=BUTTON_BG,
              fg=TEXT_COLOR, width=20, command=custom_interface).pack(pady=10)

tk.Button(login_root, text="Aceptar", font=("Helvetica", 12, "bold"), bg=BUTTON_BG, fg=TEXT_COLOR,
          bd=0, relief=tk.RAISED, command=accept_username).pack(pady=10)
username_entry.bind("<Return>", lambda e: accept_username())

login_root.mainloop()

