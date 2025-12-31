# receiver.py
# Récepteur de messages (Client B)
# Corrections : horodatage, meilleur affichage, historique des messages

import socket
import threading
import argparse
from datetime import datetime

class Receiver:
    def __init__(self, host="0.0.0.0", port=7777):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.running = True
        self.messages = []  # Historique des messages
        self.lock = threading.Lock()

    def recv_msg(self, conn):
        """Reçoit un message jusqu'au terminateur."""
        data = ""
        conn.settimeout(30)
        try:
            while True:
                chunk = conn.recv(4096).decode()
                if not chunk:
                    break
                data += chunk
                if "\n\n" in data:
                    break
        except socket.timeout:
            pass
        return data.strip()

    def start(self):
        """Démarre le récepteur."""
        try:
            self.sock.bind((self.host, self.port))
            self.sock.listen(10)
            print("=" * 50)
            print(f"[RECEIVER] Démarré sur {self.host}:{self.port}")
            print(f"[RECEIVER] En attente de messages...")
            print("=" * 50)
        except Exception as e:
            print(f"[RECEIVER] Erreur bind: {e}")
            return
        
        try:
            while self.running:
                conn, addr = self.sock.accept()
                threading.Thread(
                    target=self.handle_connection,
                    args=(conn, addr),
                    daemon=True
                ).start()
        except KeyboardInterrupt:
            print(f"\n[RECEIVER] Arrêt demandé")
        finally:
            self.sock.close()
            self.print_history()

    def handle_connection(self, conn, addr):
        """Gère une connexion entrante."""
        try:
            msg = self.recv_msg(conn)
            if not msg:
                return
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if msg.startswith("TYPE:FINAL"):
                # Extraire le message
                message = ""
                for line in msg.split("\n"):
                    if line.startswith("MESSAGE:"):
                        message = line[len("MESSAGE:"):]
                        break
                
                # Stocker dans l'historique
                with self.lock:
                    self.messages.append({
                        'timestamp': timestamp,
                        'from': f"{addr[0]}:{addr[1]}",
                        'message': message
                    })
                
                # Afficher
                print()
                print("=" * 50)
                print(f"[RECEIVER] ✉ NOUVEAU MESSAGE")
                print(f"[RECEIVER] Heure: {timestamp}")
                print(f"[RECEIVER] De: {addr[0]}:{addr[1]} (dernier routeur)")
                print(f"[RECEIVER] Message: {message}")
                print("=" * 50)
            else:
                print(f"[RECEIVER] Message non reconnu de {addr[0]}:{addr[1]}: {msg[:50]}")
        except Exception as e:
            print(f"[RECEIVER] Erreur: {e}")
        finally:
            conn.close()

    def print_history(self):
        """Affiche l'historique des messages."""
        if not self.messages:
            print("\n[RECEIVER] Aucun message reçu")
            return
        
        print(f"\n[RECEIVER] === Historique ({len(self.messages)} message(s)) ===")
        for i, msg in enumerate(self.messages, 1):
            print(f"{i}. [{msg['timestamp']}] {msg['message']}")


def start_receiver(host="0.0.0.0", port=7777):
    """Fonction de compatibilité avec l'ancien code."""
    receiver = Receiver(host, port)
    receiver.start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Récepteur de messages (Client B)")
    parser.add_argument("--host", default="0.0.0.0", help="Adresse d'écoute")
    parser.add_argument("--port", "-p", type=int, default=7777, help="Port d'écoute")
    args = parser.parse_args()
    
    receiver = Receiver(host=args.host, port=args.port)
    receiver.start()

