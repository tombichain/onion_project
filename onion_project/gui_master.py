# gui_master.py
# Interface graphique du Master avec serveur intégré
# Corrections : serveur intégré, logs en temps réel, meilleure interface

import sys
import socket
import threading
import mariadb
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QTableWidget, 
    QTableWidgetItem, QGroupBox, QSpinBox, QLineEdit,
    QMessageBox, QHeaderView
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont

# Signal pour communication thread-safe avec l'UI
class LogSignal(QObject):
    log_message = pyqtSignal(str)
    router_update = pyqtSignal()


class MasterServer:
    """Serveur Master en arrière-plan."""
    
    def __init__(self, port, db_config, log_signal):
        self.port = port
        self.db_config = db_config
        self.log_signal = log_signal
        self.sock = None
        self.db = None
        self.cursor = None
        self.running = False
        self.lock = threading.Lock()
    
    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_signal.log_message.emit(f"[{timestamp}] {message}")
    
    def connect_db(self):
        try:
            self.db = mariadb.connect(**self.db_config)
            self.cursor = self.db.cursor()
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS routers(
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255),
                    ip VARCHAR(45),
                    port INT,
                    n TEXT,
                    e TEXT,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self.db.commit()
            self.cursor.execute("DELETE FROM routers")
            self.db.commit()
            self.log("Base de données connectée et nettoyée")
            return True
        except mariadb.Error as e:
            self.log(f"ERREUR DB: {e}")
            return False
    
    def start(self):
        if not self.connect_db():
            return False
        
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("0.0.0.0", self.port))
            self.sock.listen(50)
            self.running = True
            self.log(f"Serveur démarré sur port {self.port}")
            
            # Thread d'écoute
            threading.Thread(target=self.accept_loop, daemon=True).start()
            return True
        except Exception as e:
            self.log(f"ERREUR démarrage: {e}")
            return False
    
    def stop(self):
        self.running = False
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        if self.db:
            try:
                self.cursor.execute("DELETE FROM routers")
                self.db.commit()
                self.db.close()
            except:
                pass
        self.log("Serveur arrêté")
    
    def accept_loop(self):
        while self.running:
            try:
                self.sock.settimeout(1)
                conn, addr = self.sock.accept()
                threading.Thread(target=self.handle, args=(conn, addr), daemon=True).start()
            except socket.timeout:
                continue
            except:
                break
    
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
        except:
            pass
        return data.strip()
    
    def send(self, conn, text):
        try:
            conn.send((text + "\n\n").encode())
        except:
            pass
    
    def handle(self, conn, addr):
        try:
            msg = self.recv_msg(conn)
            if not msg:
                return
            
            if msg.startswith("TYPE:REGISTER_ROUTER"):
                self.register_router(msg, addr, conn)
            elif msg.startswith("TYPE:GET_ROUTERS"):
                self.send_routers(conn)
                self.log(f"Liste envoyée à {addr[0]}")
            elif msg.startswith("TYPE:PING"):
                self.send(conn, "STATUS:PONG")
        except Exception as e:
            self.log(f"Erreur: {e}")
        finally:
            conn.close()
    
    def register_router(self, msg, addr, conn):
        lines = [l for l in msg.split("\n") if ":" in l]
        d = {}
        for line in lines:
            k, v = line.split(":", 1)
            d[k] = v.strip()
        
        name = d.get("NAME", "unknown")
        port = int(d.get("PORT", "0"))
        n = d.get("PUBN", "")
        e = d.get("PUBE", "")
        ip = addr[0]
        
        with self.lock:
            self.cursor.execute("SELECT id FROM routers WHERE name = ?", (name,))
            existing = self.cursor.fetchone()
            
            if existing:
                self.cursor.execute(
                    "UPDATE routers SET ip=?, port=?, n=?, e=?, registered_at=CURRENT_TIMESTAMP WHERE name=?",
                    (ip, port, n, e, name)
                )
            else:
                self.cursor.execute(
                    "INSERT INTO routers (name, ip, port, n, e) VALUES (?, ?, ?, ?, ?)",
                    (name, ip, port, n, e)
                )
            self.db.commit()
        
        self.send(conn, f"STATUS:OK\nMESSAGE:Routeur {name} enregistré")
        self.log(f"Routeur enregistré: {name} @ {ip}:{port}")
        self.log_signal.router_update.emit()
    
    def send_routers(self, conn):
        with self.lock:
            self.cursor.execute("SELECT name, ip, port, n, e FROM routers")
            rows = self.cursor.fetchall()
        
        txt = "ROUTERS:\n"
        for r in rows:
            txt += f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]}\n"
        self.send(conn, txt)
    
    def get_routers(self):
        if not self.db or not self.cursor:
            return []
        with self.lock:
            self.cursor.execute("SELECT name, ip, port FROM routers ORDER BY registered_at")
            return self.cursor.fetchall()


class MasterGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.server = None
        self.log_signal = LogSignal()
        self.log_signal.log_message.connect(self.append_log)
        self.log_signal.router_update.connect(self.refresh_routers)
        
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("🧅 Master - Routage en Oignon")
        self.resize(700, 500)
        
        layout = QVBoxLayout(self)
        
        # Configuration
        config_group = QGroupBox("Configuration")
        config_layout = QHBoxLayout(config_group)
        
        config_layout.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)
        self.port_spin.setValue(9000)
        config_layout.addWidget(self.port_spin)
        
        config_layout.addWidget(QLabel("DB Host:"))
        self.db_host = QLineEdit("localhost")
        self.db_host.setMaximumWidth(100)
        config_layout.addWidget(self.db_host)
        
        config_layout.addWidget(QLabel("DB User:"))
        self.db_user = QLineEdit("root")
        self.db_user.setMaximumWidth(80)
        config_layout.addWidget(self.db_user)
        
        config_layout.addWidget(QLabel("DB Pass:"))
        self.db_pass = QLineEdit("")
        self.db_pass.setEchoMode(QLineEdit.Password)
        self.db_pass.setMaximumWidth(80)
        config_layout.addWidget(self.db_pass)
        
        config_layout.addStretch()
        layout.addWidget(config_group)
        
        # Boutons
        btn_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶ Démarrer")
        self.start_btn.clicked.connect(self.start_server)
        self.start_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("⏹ Arrêter")
        self.stop_btn.clicked.connect(self.stop_server)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("background-color: #f44336; color: white; font-weight: bold;")
        btn_layout.addWidget(self.stop_btn)
        
        self.refresh_btn = QPushButton("🔄 Actualiser")
        self.refresh_btn.clicked.connect(self.refresh_routers)
        btn_layout.addWidget(self.refresh_btn)
        
        btn_layout.addStretch()
        
        self.status_label = QLabel("⚪ Arrêté")
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))
        btn_layout.addWidget(self.status_label)
        
        layout.addLayout(btn_layout)
        
        # Table des routeurs
        router_group = QGroupBox("Routeurs enregistrés")
        router_layout = QVBoxLayout(router_group)
        
        self.router_table = QTableWidget()
        self.router_table.setColumnCount(3)
        self.router_table.setHorizontalHeaderLabels(["Nom", "IP", "Port"])
        self.router_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        router_layout.addWidget(self.router_table)
        
        layout.addWidget(router_group)
        
        # Logs
        log_group = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
    
    def append_log(self, message):
        self.log_text.append(message)
        # Auto-scroll
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def start_server(self):
        db_config = {
            'host': self.db_host.text(),
            'user': self.db_user.text(),
            'password': self.db_pass.text(),
            'database': 'onion'
        }
        
        self.server = MasterServer(self.port_spin.value(), db_config, self.log_signal)
        
        if self.server.start():
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.port_spin.setEnabled(False)
            self.status_label.setText("🟢 En cours")
            self.status_label.setStyleSheet("color: green;")
        else:
            QMessageBox.critical(self, "Erreur", "Impossible de démarrer le serveur")
    
    def stop_server(self):
        if self.server:
            self.server.stop()
            self.server = None
        
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.port_spin.setEnabled(True)
        self.status_label.setText("⚪ Arrêté")
        self.status_label.setStyleSheet("color: gray;")
        self.router_table.setRowCount(0)
    
    def refresh_routers(self):
        if not self.server:
            return
        
        routers = self.server.get_routers()
        self.router_table.setRowCount(len(routers))
        
        for i, (name, ip, port) in enumerate(routers):
            self.router_table.setItem(i, 0, QTableWidgetItem(str(name)))
            self.router_table.setItem(i, 1, QTableWidgetItem(str(ip)))
            self.router_table.setItem(i, 2, QTableWidgetItem(str(port)))
    
    def closeEvent(self, event):
        if self.server:
            self.server.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MasterGUI()
    window.show()
    sys.exit(app.exec_())
