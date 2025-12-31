# gui_client.py
# Interface graphique du Client pour routage en oignon
# Corrections : meilleure interface, logs détaillés, configuration flexible

import sys
import socket
import random
import threading
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QLineEdit,
    QGroupBox, QSpinBox, QComboBox, QListWidget,
    QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject
from PyQt5.QtGui import QFont

from crypto_simple import text_to_int, encrypt_int


class LogSignal(QObject):
    log_message = pyqtSignal(str)


class ClientGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.routers = []
        self.log_signal = LogSignal()
        self.log_signal.log_message.connect(self.append_log)
        
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("🧅 Client - Routage en Oignon")
        self.resize(600, 600)
        
        layout = QVBoxLayout(self)
        
        # Configuration Master
        master_group = QGroupBox("Connexion au Master")
        master_layout = QHBoxLayout(master_group)
        
        master_layout.addWidget(QLabel("IP Master:"))
        self.master_ip = QLineEdit("127.0.0.1")
        self.master_ip.setMaximumWidth(120)
        master_layout.addWidget(self.master_ip)
        
        master_layout.addWidget(QLabel("Port:"))
        self.master_port = QSpinBox()
        self.master_port.setRange(1, 65535)
        self.master_port.setValue(9000)
        master_layout.addWidget(self.master_port)
        
        self.fetch_btn = QPushButton("🔄 Récupérer routeurs")
        self.fetch_btn.clicked.connect(self.fetch_routers)
        master_layout.addWidget(self.fetch_btn)
        
        master_layout.addStretch()
        layout.addWidget(master_group)
        
        # Liste des routeurs
        router_group = QGroupBox("Routeurs disponibles")
        router_layout = QVBoxLayout(router_group)
        
        self.router_list = QListWidget()
        self.router_list.setMaximumHeight(100)
        router_layout.addWidget(self.router_list)
        
        nb_layout = QHBoxLayout()
        nb_layout.addWidget(QLabel("Nombre de routeurs à utiliser:"))
        self.num_routers = QSpinBox()
        self.num_routers.setRange(1, 10)
        self.num_routers.setValue(3)
        nb_layout.addWidget(self.num_routers)
        nb_layout.addStretch()
        router_layout.addLayout(nb_layout)
        
        layout.addWidget(router_group)
        
        # Destination
        dest_group = QGroupBox("Destination (Receiver)")
        dest_layout = QHBoxLayout(dest_group)
        
        dest_layout.addWidget(QLabel("IP:"))
        self.dest_ip = QLineEdit("127.0.0.1")
        self.dest_ip.setMaximumWidth(120)
        dest_layout.addWidget(self.dest_ip)
        
        dest_layout.addWidget(QLabel("Port:"))
        self.dest_port = QSpinBox()
        self.dest_port.setRange(1, 65535)
        self.dest_port.setValue(7777)
        dest_layout.addWidget(self.dest_port)
        
        dest_layout.addStretch()
        layout.addWidget(dest_group)
        
        # Message
        msg_group = QGroupBox("Message")
        msg_layout = QVBoxLayout(msg_group)
        
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Entrez votre message ici...")
        self.message_input.setMaximumHeight(80)
        msg_layout.addWidget(self.message_input)
        
        self.send_btn = QPushButton("📤 Envoyer le message")
        self.send_btn.clicked.connect(self.send_message)
        self.send_btn.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold; padding: 10px;")
        msg_layout.addWidget(self.send_btn)
        
        layout.addWidget(msg_group)
        
        # Logs
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)
        
        clear_btn = QPushButton("🗑 Effacer les logs")
        clear_btn.clicked.connect(lambda: self.log_text.clear())
        log_layout.addWidget(clear_btn)
        
        layout.addWidget(log_group)
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        # Auto-scroll
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def append_log(self, message):
        self.log(message)
    
    def recv_msg(self, conn):
        data = ""
        conn.settimeout(10)
        try:
            while True:
                chunk = conn.recv(4096).decode()
                if not chunk:
                    break
                data += chunk
                if "\n\n" in data:
                    break
        except socket.timeout:
            self.log("Timeout réception")
        return data.strip()
    
    def fetch_routers(self):
        """Récupère la liste des routeurs depuis le master."""
        self.log(f"Connexion au master {self.master_ip.text()}:{self.master_port.value()}...")
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((self.master_ip.text(), self.master_port.value()))
            s.send(b"TYPE:GET_ROUTERS\n\n")
            data = self.recv_msg(s)
            s.close()
        except Exception as e:
            self.log(f"❌ Erreur connexion: {e}")
            QMessageBox.warning(self, "Erreur", f"Impossible de contacter le master:\n{e}")
            return
        
        self.routers = []
        self.router_list.clear()
        
        if not data or "NONE" in data:
            self.log("Aucun routeur disponible")
            return
        
        lines = data.split("\n")
        for l in lines[1:]:
            if "," in l:
                parts = l.split(",")
                if len(parts) >= 5:
                    name, ip, port, n, e = parts[0], parts[1], int(parts[2]), int(parts[3]), int(parts[4])
                    self.routers.append((name, ip, port, n, e))
                    self.router_list.addItem(f"{name} - {ip}:{port}")
        
        self.log(f"✅ {len(self.routers)} routeur(s) récupéré(s)")
        
        # Ajuster le max du spinbox
        self.num_routers.setMaximum(len(self.routers))
        if self.num_routers.value() > len(self.routers):
            self.num_routers.setValue(len(self.routers))
    
    def send_message(self):
        """Construit et envoie le message en oignon."""
        message = self.message_input.toPlainText().strip()
        
        if not message:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer un message")
            return
        
        if len(self.routers) < self.num_routers.value():
            QMessageBox.warning(self, "Erreur", 
                f"Pas assez de routeurs. Disponibles: {len(self.routers)}, requis: {self.num_routers.value()}")
            return
        
        # Lancer dans un thread pour ne pas bloquer l'UI
        threading.Thread(target=self._send_message_thread, args=(message,), daemon=True).start()
    
    def _send_message_thread(self, message):
        """Thread d'envoi du message."""
        try:
            dest_ip = self.dest_ip.text()
            dest_port = self.dest_port.value()
            num = self.num_routers.value()
            
            # Sélectionner une route aléatoire
            route = random.sample(self.routers, num)
            route_names = [r[0] for r in route]
            
            self.log_signal.log_message.emit(f"Route sélectionnée: {' → '.join(route_names)}")
            self.log_signal.log_message.emit(f"Destination: {dest_ip}:{dest_port}")
            self.log_signal.log_message.emit(f"Message: {message[:50]}{'...' if len(message) > 50 else ''}")
            
            # Construire l'oignon
            self.log_signal.log_message.emit("--- Construction de l'oignon ---")
            
            # Couche finale
            layer = f"DEST:{dest_ip}:{dest_port}\nMSG:{message}"
            m = text_to_int(layer)
            
            name_last, ip_last, port_last, n_last, e_last = route[-1]
            c = encrypt_int(m, n_last, e_last)
            self.log_signal.log_message.emit(f"Couche {num}: chiffrée avec clé de {name_last}")
            
            # Couches intermédiaires
            for i in range(len(route) - 2, -1, -1):
                nxt = route[i + 1]
                wrapped = f"NEXT:{nxt[1]}\nPORT:{nxt[2]}\nPAYLOAD:{c}"
                m_wr = text_to_int(wrapped)
                name, ip, port, n, e = route[i]
                c = encrypt_int(m_wr, n, e)
                self.log_signal.log_message.emit(f"Couche {i+1}: chiffrée avec clé de {name} (→ {nxt[0]})")
            
            # Envoyer au premier routeur
            first = route[0]
            self.log_signal.log_message.emit(f"--- Envoi au premier routeur: {first[0]} ({first[1]}:{first[2]}) ---")
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((first[1], first[2]))
            s.send(f"TYPE:ONION\nPAYLOAD:{c}\n\n".encode())
            s.close()
            
            self.log_signal.log_message.emit("✅ Message envoyé avec succès!")
            
        except Exception as e:
            self.log_signal.log_message.emit(f"❌ Erreur: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ClientGUI()
    window.show()
    sys.exit(app.exec_())
