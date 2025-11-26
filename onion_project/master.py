# master.py
# Master minimal : enregistre les routeurs et renvoie la liste
import socket
import threading
import mariadb

HOST = "0.0.0.0"

class Master:
    def __init__(self, port=9000):
        self.port = port
        self.sock = socket.socket()
        self.sock.bind((HOST, port))
        self.sock.listen(50)

        # Connexion MariaDB (ajuste user/password si nécessaire)
        self.db = mariadb.connect(
            host="192.168.133.130",
            user="root",
            password="osboxes.org",
            database="onion"
        )
        self.cursor = self.db.cursor()

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS routers(
            name TEXT,
            ip TEXT,
            port INT,
            n TEXT,
            e TEXT
        )
        """)
        self.db.commit()
        print("[MASTER] Base initialisée")

    def start(self):
        print("[MASTER] écoute sur port", self.port)
        while True:
            conn, addr = self.sock.accept()
            threading.Thread(target=self.handle, args=(conn, addr), daemon=True).start()

    def recv_msg(self, conn):
        """Lit jusqu'à la double nouvelle ligne terminatrice."""
        data = ""
        while True:
            chunk = conn.recv(4096).decode()
            if not chunk:
                break
            data += chunk
            if "\n\n" in data:
                break
        return data.strip()

    def send(self, conn, text):
        conn.send((text + "\n\n").encode())

    def handle(self, conn, addr):
        try:
            msg = self.recv_msg(conn)
            if not msg:
                conn.close()
                return

            if msg.startswith("TYPE:REGISTER_ROUTER"):
                self.register_router(msg, addr)
                self.send(conn, "STATUS:OK")
            elif msg.startswith("TYPE:GET_ROUTERS"):
                self.send_routers(conn)
            else:
                self.send(conn, "STATUS:ERROR")
        except Exception as e:
            print("[MASTER] erreur handle:", e)
        finally:
            conn.close()

    def register_router(self, msg, addr):
        lines = [l for l in msg.split("\n") if ":" in l]
        d = {}
        for line in lines:
            k, v = line.split(":", 1)
            d[k] = v
        # Insert
        self.cursor.execute(
            "INSERT INTO routers (name, ip, port, n, e) VALUES (?, ?, ?, ?, ?)",
            (d.get("NAME",""), addr[0], int(d.get("PORT", "0")), d.get("PUBN",""), d.get("PUBE",""))
        )
        self.db.commit()
        print(f"[MASTER] Router enregistré: {d.get('NAME','?')} @ {addr[0]}:{d.get('PORT','?')}")

    def send_routers(self, conn):
        self.cursor.execute("SELECT name, ip, port, n, e FROM routers")
        rows = self.cursor.fetchall()
        txt = "ROUTERS:\n"
        for r in rows:
            txt += f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]}\n"
        self.send(conn, txt)

if __name__ == "__main__":
    m = Master(port=9000)
    m.start()
