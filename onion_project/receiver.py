# receiver.py
import socket

HOST = "0.0.0.0"
PORT = 7777

def recv_msg(conn):
    data = ""
    while True:
        chunk = conn.recv(4096).decode()
        if not chunk:
            break
        data += chunk
        if "\n\n" in data:
            break
    return data.strip()

def start_receiver():
    s = socket.socket()
    s.bind((HOST, PORT))
    s.listen(1)
    print("[RECEIVER] En attente sur port", PORT)
    while True:
        conn, addr = s.accept()
        print("[RECEIVER] Connexion de", addr)
        msg = recv_msg(conn)
        if msg.startswith("TYPE:FINAL"):
            for line in msg.split("\n"):
                if line.startswith("MESSAGE:"):
                    print("[RECEIVER] Message reçu:", line[len("MESSAGE:"):])
        conn.close()

if __name__ == "__main__":
    start_receiver()
