# master.py
# Master : enregistre les routeurs et renvoie la liste
# Corrections : nettoyage table au démarrage, meilleure gestion erreurs

import socket
import threading
import mariadb
import sys

HOST = "0.0.0.0"

class Master:
    def __init__(self, port=9000, db_host="localhost", db_user="root", db_password="", db_name="onion"):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((HOST, port))
        self.sock.listen(50)
        
        # Connexion MariaDB
        try:
            self.db = mariadb.connect(
                host=db_host,
                user=db_user,
                password=db_password,
                database=db_name
            )
            self.cursor = self.db.cursor()
            print(f"[MASTER] Connecté à MariaDB ({db_host}/{db_name})")
        except mariadb.Error as e:
            print(f"[MASTER] ERREUR connexion MariaDB: {e}")
            sys.exit(1)
        
        # Créer la table si elle n'existe pas
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
        
        # Nettoyer les anciens routeurs au démarrage
        self.cursor.execute("DELETE FROM routers")
        self.db.commit()
        print("[MASTER] Table routers nettoyée")
        
        # Liste des routeurs en mémoire (pour accès rapide)
        self.routers = {}
        self.lock = threading.Lock()
        
        print(f"[MASTER] Initialisé sur port {port}")

    def start(self):
        print(f"[MASTER] En écoute sur {HOST}:{self.port}")
        print("[MASTER] En attente de connexions...")
        try:
            while True:
                conn, addr = self.sock.accept()
                threading.Thread(target=self.handle, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            print("\n[MASTER] Arrêt demandé")
            self.cleanup()

    def cleanup(self):
        """Nettoyage à l'arrêt."""
        try:
            self.cursor.execute("DELETE FROM routers")
            self.db.commit()
            self.db.close()
            self.sock.close()
            print("[MASTER] Nettoyage effectué")
        except:
            pass

    def recv_msg(self, conn):
        """Lit jusqu'à la double nouvelle ligne terminatrice."""
        data = ""
        conn.settimeout(10)  # Timeout de 10 secondes
        try:
            while True:
                chunk = conn.recv(4096).decode()
                if not chunk:
                    break
                data += chunk
                if "\n\n" in data:
                    break
        except socket.timeout:
            print("[MASTER] Timeout réception")
        return data.strip()

    def send(self, conn, text):
        """Envoie un message avec le terminateur."""
        try:
            conn.send((text + "\n\n").encode())
        except Exception as e:
            print(f"[MASTER] Erreur envoi: {e}")

    def handle(self, conn, addr):
        """Gère une connexion entrante."""
        try:
            msg = self.recv_msg(conn)
            if not msg:
                conn.close()
                return
            
            print(f"[MASTER] Message de {addr[0]}:{addr[1]} -> {msg[:50]}...")
            
            if msg.startswith("TYPE:REGISTER_ROUTER"):
                self.register_router(msg, addr, conn)
            elif msg.startswith("TYPE:GET_ROUTERS"):
                self.send_routers(conn)
            elif msg.startswith("TYPE:PING"):
                self.send(conn, "STATUS:PONG")
            else:
                print(f"[MASTER] Commande inconnue: {msg[:30]}")
                self.send(conn, "STATUS:ERROR\nMESSAGE:Commande inconnue")
        except Exception as e:
            print(f"[MASTER] Erreur handle: {e}")
        finally:
            conn.close()

    def register_router(self, msg, addr, conn):
        """Enregistre un nouveau routeur."""
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
        
        # Vérifier si ce routeur existe déjà (même nom)
        with self.lock:
            self.cursor.execute("SELECT id FROM routers WHERE name = ?", (name,))
            existing = self.cursor.fetchone()
            
            if existing:
                # Mettre à jour
                self.cursor.execute(
                    "UPDATE routers SET ip=?, port=?, n=?, e=?, registered_at=CURRENT_TIMESTAMP WHERE name=?",
                    (ip, port, n, e, name)
                )
                print(f"[MASTER] Routeur mis à jour: {name} @ {ip}:{port}")
            else:
                # Insérer
                self.cursor.execute(
                    "INSERT INTO routers (name, ip, port, n, e) VALUES (?, ?, ?, ?, ?)",
                    (name, ip, port, n, e)
                )
                print(f"[MASTER] Nouveau routeur: {name} @ {ip}:{port}")
            
            self.db.commit()
            
            # Mettre à jour le cache mémoire
            self.routers[name] = {
                'ip': ip,
                'port': port,
                'n': n,
                'e': e
            }
        
        self.send(conn, f"STATUS:OK\nMESSAGE:Routeur {name} enregistré")

    def send_routers(self, conn):
        """Envoie la liste des routeurs enregistrés."""
        with self.lock:
            self.cursor.execute("SELECT name, ip, port, n, e FROM routers")
            rows = self.cursor.fetchall()
        
        if not rows:
            self.send(conn, "ROUTERS:\nNONE")
            return
        
        txt = "ROUTERS:\n"
        for r in rows:
            txt += f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]}\n"
        
        print(f"[MASTER] Envoi liste de {len(rows)} routeur(s)")
        self.send(conn, txt)

    def get_router_count(self):
        """Retourne le nombre de routeurs enregistrés."""
        with self.lock:
            self.cursor.execute("SELECT COUNT(*) FROM routers")
            return self.cursor.fetchone()[0]


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Master server pour routage en oignon")
    parser.add_argument("--port", type=int, default=9000, help="Port d'écoute (défaut: 9000)")
    parser.add_argument("--db-host", default="localhost", help="Hôte MariaDB")
    parser.add_argument("--db-user", default="root", help="Utilisateur MariaDB")
    parser.add_argument("--db-password", default="", help="Mot de passe MariaDB")
    parser.add_argument("--db-name", default="onion", help="Nom de la base de données")
    args = parser.parse_args()
    
    master = Master(
        port=args.port,
        db_host=args.db_host,
        db_user=args.db_user,
        db_password=args.db_password,
        db_name=args.db_name
    )
    master.start()
