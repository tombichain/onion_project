# client.py
import socket
import random
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
    lines = data.split("\n")
    for l in lines[1:]:
        if "," in l:
            name, ip, port, n, e = l.split(",")
            routers.append((name, ip, int(port), int(n), int(e)))
    return routers

def send_onion(route, dest_ip, dest_port, message):
    # dernière couche : DEST + MSG
    layer = f"DEST:{dest_ip}:{dest_port}\nMSG:{message}"
    m = text_to_int(layer)
    name_last, ip_last, port_last, n_last, e_last = route[-1]
    c = encrypt_int(m, n_last, e_last)

    # wrap les couches
    for i in range(len(route)-2, -1, -1):
        nxt = route[i+1]
        wrapped = f"NEXT:{nxt[1]}\nPORT:{nxt[2]}\nPAYLOAD:{c}"
        m_wr = text_to_int(wrapped)
        name, ip, port, n, e = route[i]
        c = encrypt_int(m_wr, n, e)

    # envoie au premier routeur
    first = route[0]
    s = socket.socket()
    s.connect((first[1], first[2]))
    s.send(f"TYPE:ONION\nPAYLOAD:{c}\n\n".encode())
    s.close()

if __name__ == "__main__":
    routers = get_routers()
    if len(routers) < 3:
        print("Il faut au moins 3 routeurs enregistrés.")
        exit(1)
    route = random.sample(routers, 3)
    print("Route sélectionnée:", [r[0] for r in route])
    send_onion(route, "127.0.0.1", 7777, "Bonjour depuis A")
    print("Onion envoyé.")
