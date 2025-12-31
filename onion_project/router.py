# router.py
# Routeur virtuel pour routage en oignon
# Corrections : vérification enregistrement, meilleure gestion erreurs

import socket
import threading
import argparse
from crypto_simple import generate_keys, decrypt_int, int_to_text

class Router:
    def __init__(self, name, master_ip, master_port, listen_port):
        self.name = name
        self.master_ip = master_ip
        self.master_port = master_port
        self.listen_port = listen_port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.running = True
        
        # Statistiques
        self.messages_received = 0
        self.messages_forwarded = 0
        self.messages_delivered = 0
        
        # Génération des clés RSA
        print(f"[{self.name}] Génération des clés RSA...")
        self.n, self.e, self.d = generate_keys(bits=512)
        print(f"[{self.name}] Clés générées (n a {self.n.bit_length()} bits)")

    def send_to_master(self, text):
        """Envoie un message au master et retourne la réponse."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        response = ""
        try:
            s.connect((self.master_ip, self.master_port))
            s.send((text + "\n\n").encode())
            
            # Attendre la réponse
            while True:
                chunk = s.recv(4096).decode()
                if not chunk:
                    break
                response += chunk
                if "\n\n" in response:
                    break
        except socket.timeout:
            print(f"[{self.name}] Timeout connexion master")
        except Exception as e:
            print(f"[{self.name}] Erreur connexion master: {e}")
        finally:
            s.close()
        return response.strip()

    def register_to_master(self):
        """S'enregistre auprès du master."""
        msg = (
            f"TYPE:REGISTER_ROUTER\n"
            f"NAME:{self.name}\n"
            f"PORT:{self.listen_port}\n"
            f"PUBN:{self.n}\n"
            f"PUBE:{self.e}"
        )
        
        print(f"[{self.name}] Envoi de la clé publique au master ({self.master_ip}:{self.master_port})...")
        response = self.send_to_master(msg)
        
        if "STATUS:OK" in response:
            print(f"[{self.name}] ✓ Enregistré avec succès auprès du master")
            return True
        else:
            print(f"[{self.name}] ✗ Échec enregistrement: {response}")
            return False

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
            print(f"[{self.name}] Timeout réception")
        return data.strip()

    def start(self):
        """Démarre le routeur."""
        try:
            self.sock.bind(("0.0.0.0", self.listen_port))
            self.sock.listen(50)
            self.listen_port = self.sock.getsockname()[1]
            print(f"[{self.name}] En écoute sur port {self.listen_port}")
        except Exception as e:
            print(f"[{self.name}] Erreur bind: {e}")
            return
        
        # S'enregistrer auprès du master
        if not self.register_to_master():
            print(f"[{self.name}] Impossible de s'enregistrer, arrêt.")
            return
        
        print(f"[{self.name}] Prêt à recevoir des messages")
        
        try:
            while self.running:
                conn, addr = self.sock.accept()
                threading.Thread(
                    target=self.handle_connection, 
                    args=(conn, addr), 
                    daemon=True
                ).start()
        except KeyboardInterrupt:
            print(f"\n[{self.name}] Arrêt demandé")
        finally:
            self.sock.close()
            self.print_stats()

    def print_stats(self):
        """Affiche les statistiques."""
        print(f"\n[{self.name}] === Statistiques ===")
        print(f"[{self.name}] Messages reçus: {self.messages_received}")
        print(f"[{self.name}] Messages forwardés: {self.messages_forwarded}")
        print(f"[{self.name}] Messages délivrés: {self.messages_delivered}")

    def handle_connection(self, conn, addr):
        """Gère une connexion entrante."""
        try:
            msg = self.recv_msg(conn)
            if not msg:
                conn.close()
                return
            
            print(f"[{self.name}] Message reçu de {addr[0]}:{addr[1]}")
            self.messages_received += 1
            
            if msg.startswith("TYPE:ONION"):
                self.handle_onion(msg)
            else:
                print(f"[{self.name}] Type de message inconnu: {msg[:30]}")
        except Exception as e:
            print(f"[{self.name}] Erreur traitement: {e}")
        finally:
            conn.close()

    def handle_onion(self, msg):
        """Traite un message oignon."""
        # Extraire le payload
        try:
            payload_line = [l for l in msg.split("\n") if l.startswith("PAYLOAD:")][0]
            enc_str = payload_line.split(":", 1)[1].strip()
            enc = int(enc_str)
        except Exception as e:
            print(f"[{self.name}] Payload illisible: {e}")
            return

        # Déchiffrer la couche
        try:
            m = decrypt_int(enc, self.n, self.d)
            txt = int_to_text(m)
        except Exception as e:
            print(f"[{self.name}] Erreur déchiffrement: {e}")
            return

        print(f"[{self.name}] Couche déchiffrée ({len(txt)} chars)")
        print(f"[{self.name}] Contenu: {txt[:100]}{'...' if len(txt) > 100 else ''}")

        # Analyser le contenu déchiffré
        if txt.startswith("NEXT:"):
            self.forward_message(txt)
        elif txt.startswith("DEST:"):
            self.deliver_message(txt)
        else:
            print(f"[{self.name}] Format inconnu après déchiffrement")

    def forward_message(self, txt):
        """Forwarde le message au prochain routeur."""
        try:
            lines = txt.split("\n")
            next_ip = lines[0].split(":", 1)[1]
            next_port = int(lines[1].split(":", 1)[1])
            payload = lines[2].split(":", 1)[1]
            
            print(f"[{self.name}] → Forward vers {next_ip}:{next_port}")
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((next_ip, next_port))
            s.send(f"TYPE:ONION\nPAYLOAD:{payload}\n\n".encode())
            s.close()
            
            self.messages_forwarded += 1
            print(f"[{self.name}] ✓ Message forwardé")
        except Exception as e:
            print(f"[{self.name}] ✗ Erreur forward: {e}")

    def deliver_message(self, txt):
        """Délivre le message au destinataire final."""
        try:
            lines = txt.split("\n")
            dest_line = lines[0]  # DEST:ip:port
            msg_line = lines[1]   # MSG:message
            
            # Parser DEST:ip:port
            parts = dest_line.split(":")
            dest_ip = parts[1]
            dest_port = int(parts[2])
            
            # Parser MSG:message
            message = msg_line.split(":", 1)[1]
            
            print(f"[{self.name}] → Livraison finale à {dest_ip}:{dest_port}")
            print(f"[{self.name}] Message: {message[:50]}{'...' if len(message) > 50 else ''}")
            
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect((dest_ip, dest_port))
            s.send(f"TYPE:FINAL\nMESSAGE:{message}\n\n".encode())
            s.close()
            
            self.messages_delivered += 1
            print(f"[{self.name}] ✓ Message délivré")
        except Exception as e:
            print(f"[{self.name}] ✗ Erreur livraison: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Routeur virtuel pour routage en oignon")
    parser.add_argument("--name", required=True, help="Nom du routeur (ex: R1)")
    parser.add_argument("--master-ip", default="127.0.0.1", help="IP du master")
    parser.add_argument("--master-port", type=int, default=9000, help="Port du master")
    parser.add_argument("--port", type=int, default=10001, help="Port d'écoute du routeur")
    args = parser.parse_args()

    router = Router(
        name=args.name,
        master_ip=args.master_ip,
        master_port=args.master_port,
        listen_port=args.port
    )
    router.start()
