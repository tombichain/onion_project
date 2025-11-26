# router.py
import socket
import threading
import argparse
from crypto_simple import *

class Router:
    def __init__(self, name, master_ip, master_port, port):
        self.name = name
        self.master_ip = master_ip
        self.master_port = master_port
        self.port = port
        self.sock = socket.socket()

        print(f"[{self.name}] Génération des clés RSA simplifiées...")
        self.n, self.e, self.d = generate_keys()
        print(f"[{self.name}] Clés générées (n={self.n}, e={self.e})")

    # Envoi au master (texte)
    def send_master(self, text):
        s = socket.socket()
        try:
            s.connect((self.master_ip, self.master_port))
            s.send((text + "\n\n").encode())
        except Exception as e:
            print(f"[{self.name}] ERREUR : impossible de contacter le master :", e)
        finally:
            s.close()

    def register_to_master(self):
        msg = (
            f"TYPE:REGISTER_ROUTER\n"
            f"NAME:{self.name}\n"
            f"PORT:{self.port}\n"
            f"PUBN:{self.n}\n"
            f"PUBE:{self.e}"
        )
        print(f"[{self.name}] Envoi de la clé publique au master...")
        self.send_master(msg)
        print(f"[{self.name}] Enregistré auprès du master.")

    def recv_msg(self, conn):
        data = ""
        while True:
            chunk = conn.recv(4096).decode()
            if not chunk:
                break
            data += chunk
            if "\n\n" in data:
                break
        return data.strip()

    def start(self):
        self.sock.bind(("0.0.0.0", self.port))
        self.sock.listen(50)
        self.port = self.sock.getsockname()[1]
        print(f"[{self.name}] Écoute sur {self.port}")
        self.register_to_master()
        while True:
            conn, addr = self.sock.accept()
            threading.Thread(target=self.handle, args=(conn,), daemon=True).start()

    def handle(self, conn):
        msg = self.recv_msg(conn)
        if not msg or not msg.startswith("TYPE:ONION"):
            conn.close()
            return

        # extraire PAYLOAD
        try:
            enc_str = msg.split("PAYLOAD:")[1].strip()
            enc = int(enc_str)
        except Exception as e:
            print(f"[{self.name}] Payload illisible:", e)
            conn.close()
            return

        # déchiffrement
        try:
            m = decrypt_int(enc, self.n, self.d)
            txt = int_to_text(m)
        except Exception as e:
            print(f"[{self.name}] Erreur déchiffrement:", e)
            conn.close()
            return

        print(f"[{self.name}] Couche déchiffrée:\n{txt}")

        # couche intermédiaire -> forward
        if txt.startswith("NEXT:"):
            parts = txt.split("\n")
            next_ip = parts[0].split(":",1)[1]
            next_port = int(parts[1].split(":",1)[1])
            payload = parts[2].split(":",1)[1]

            print(f"[{self.name}] Forward vers {next_ip}:{next_port}")
            try:
                s = socket.socket()
                s.connect((next_ip, next_port))
                s.send(f"TYPE:ONION\nPAYLOAD:{payload}\n\n".encode())
                s.close()
            except Exception as e:
                print(f"[{self.name}] Erreur connexion next hop:", e)
        else:
            # message final -> livraison au client final
            # format attendu:
            # DEST:ip:port
            # MSG:texte
            try:
                lines = txt.split("\n")
                dest_line = lines[0]
                msg_line = lines[1]
                _, dest_ip, dest_port = dest_line.split(":", 2)
                dest_port = int(dest_port)
                message = msg_line[len("MSG:"):]
            except Exception as e:
                print(f"[{self.name}] Format message final invalide:", e)
                conn.close()
                return

            print(f"[{self.name}] Message final -> envoi au {dest_ip}:{dest_port}")
            try:
                s2 = socket.socket()
                s2.connect((dest_ip, dest_port))
                s2.send(f"TYPE:FINAL\nMESSAGE:{message}\n\n".encode())
                s2.close()
            except Exception as e:
                print(f"[{self.name}] Erreur envoi final:", e)

        conn.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--name", required=True)
    p.add_argument("--master-ip", default="127.0.0.1")
    p.add_argument("--master-port", type=int, default=9000)
    p.add_argument("--port", type=int, default=10001)
    a = p.parse_args()

    Router(a.name, a.master_ip, a.master_port, a.port).start()
