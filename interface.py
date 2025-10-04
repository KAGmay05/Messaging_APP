
import tkinter as tk
from tkinter import scrolledtext
import threading
import send_receive_2 as main
import sys

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

    # --- Panel lateral de peers ---
    peer_frame = tk.Frame(chat_root, bg=PEER_BG, bd=2, relief=tk.RIDGE)
    peer_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

    tk.Label(peer_frame, text="Usuarios conectados", bg=PEER_BG, fg=TEXT_COLOR, font=("Helvetica", 14, "bold")).pack(pady=5)
    peer_listbox = tk.Listbox(peer_frame, width=25, bg=PEER_BG, fg=TEXT_COLOR, bd=0, highlightthickness=0, font=("Helvetica", 11))
    peer_listbox.pack(fill=tk.Y, expand=True, padx=5, pady=5)

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

    selected_peer_mac = [None]

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
        if selection:
            name = peer_listbox.get(selection[0])
            for mac, n in main.known_macs.items():
                if n == name:
                    selected_peer_mac[0] = mac
                    break
            if selected_peer_mac[0]:
                display_chat_history(selected_peer_mac[0])

    peer_listbox.bind("<<ListboxSelect>>", on_peer_select)

    # ---------- Enviar mensaje ----------
    def send_message(event=None):
        msg = message_entry.get().strip()
        if not msg or not selected_peer_mac[0]:
            return
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
        chat_root.after(1000, update_peers)

    # ---------- Actualizar mensajes ----------
    def update_messages():
        while not main.recv_queue.empty():
            sender_mac, payload = main.recv_queue.get()
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
    chat_root = tk.Toplevel(login_root)
    start_chat_window(chat_root)

tk.Button(login_root, text="Aceptar", font=("Helvetica", 12, "bold"), bg=BUTTON_BG, fg=TEXT_COLOR,
          bd=0, relief=tk.RAISED, command=accept_username).pack(pady=10)
username_entry.bind("<Return>", lambda e: accept_username())

login_root.mainloop()
