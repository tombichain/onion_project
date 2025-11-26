# gui_client.py
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton, QTextEdit
import socket, random
import sys
from crypto_simple import text_to_int, encrypt_int

MASTER_IP = "127.0.0.1"
MASTER_PORT = 9000

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

def get_routers(master_ip=MASTER_IP, master_port=MASTER_PORT):
    s = socket.socket()
    s.connect((master_ip, master_port))
    s.send(b"TYPE:GET_ROUTERS\n\n")
    data = recv_msg(s)
    s.close()
    routers = []
    for l in data.split("\n")[1:]:
        if "," in l:
            name, ip, port, n, e = l.split(",")
            routers.append((name, ip, int(port), int(n), int(e)))
    return routers

class ClientGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Client Onion GUI")
        self.resize(400,300)
        self.layout = QVBoxLayout(self)
        self.dest_ip = QLineEdit("127.0.0.1")
        self.dest_port = QLineEdit("7777")
        self.message = QLineEdit("Bonjour B !")
        self.send_btn = QPushButton("Envoyer")
        self.log = QTextEdit()
        self.layout.addWidget(self.dest_ip)
        self.layout.addWidget(self.dest_port)
        self.layout.addWidget(self.message)
        self.layout.addWidget(self.send_btn)
        self.layout.addWidget(self.log)
        self.send_btn.clicked.connect(self.on_send)

    def on_send(self):
        try:
            routers = get_routers()
            if len(routers) < 3:
                self.log.append("Pas assez de routeurs enregistrés.")
                return
            route = random.sample(routers, 3)
            self.log.append("Route: " + str([r[0] for r in route]))
            # construire oignon
            layer = f"DEST:{self.dest_ip.text()}:{self.dest_port.text()}\nMSG:{self.message.text()}"
            m = text_to_int(layer)
            name_last, ip_last, port_last, n_last, e_last = route[-1]
            c = encrypt_int(m, n_last, e_last)
            for i in range(len(route)-2, -1, -1):
                nxt = route[i+1]
                wrapped = f"NEXT:{nxt[1]}\nPORT:{nxt[2]}\nPAYLOAD:{c}"
                m_wr = text_to_int(wrapped)
                name, ip, port, n, e = route[i]
                c = encrypt_int(m_wr, n, e)
            first = route[0]
            s = socket.socket()
            s.connect((first[1], first[2]))
            s.send(f"TYPE:ONION\nPAYLOAD:{c}\n\n".encode())
            s.close()
            self.log.append("Onion envoyé.")
        except Exception as e:
            self.log.append("Erreur: " + str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = ClientGUI()
    w.show()
    sys.exit(app.exec_())
