# client.py
# Client pour routage en oignon (version ligne de commande)
# Corrections : meilleure gestion erreurs, affichage des couches

import socket
import random
import argparse
from crypto_simple import text_to_int, encrypt_int

def recv_msg(conn):
    """Reçoit un message jusqu'au terminateur."""
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
        print("[CLIENT] Timeout réception")
    return data.strip()

def get_routers(master_ip, master_port):
    """Récupère la liste des routeurs depuis le master."""
    print(f"[CLIENT] Connexion au master {master_ip}:{master_port}...")
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    
    try:
        s.connect((master_ip, master_port))
        s.send(b"TYPE:GET_ROUTERS\n\n")
        data = recv_msg(s)
    except Exception as e:
        print(f"[CLIENT] Erreur connexion master: {e}")
        return []
    finally:
        s.close()
    
    if not data or "NONE" in data:
        print("[CLIENT] Aucun routeur disponible")
        return []
    
    routers = []
    lines = data.split("\n")
    for l in lines[1:]:  # Skip "ROUTERS:"
        if "," in l:
            parts = l.split(",")
            if len(parts) >= 5:
                name, ip, port, n, e = parts[0], parts[1], int(parts[2]), int(parts[3]), int(parts[4])
                routers.append((name, ip, port, n, e))
    
    print(f"[CLIENT] {len(routers)} routeur(s) disponible(s): {[r[0] for r in routers]}")
    return routers

def build_onion(route, dest_ip, dest_port, message, verbose=True):
    """
    Construit le message en oignon.
    
    route: liste de tuples (name, ip, port, n, e)
    Retourne le payload chiffré final.
    """
    if verbose:
        print(f"\n[CLIENT] === Construction de l'oignon ===")
        print(f"[CLIENT] Message: '{message}'")
        print(f"[CLIENT] Destination: {dest_ip}:{dest_port}")
        print(f"[CLIENT] Route: {' → '.join([r[0] for r in route])} → Destination")
    
    # Couche la plus interne : message final + destination
    layer = f"DEST:{dest_ip}:{dest_port}\nMSG:{message}"
    if verbose:
        print(f"\n[CLIENT] Couche {len(route)} (finale): DEST + MSG")
    
    m = text_to_int(layer)
    name_last, ip_last, port_last, n_last, e_last = route[-1]
    
    # Vérifier que le message n'est pas trop grand
    if m.bit_length() >= n_last.bit_length():
        raise ValueError(f"Message trop grand pour la clé de {name_last}")
    
    c = encrypt_int(m, n_last, e_last)
    if verbose:
        print(f"[CLIENT] → Chiffré avec clé de {name_last}")
    
    # Envelopper les couches intermédiaires (de l'avant-dernier au premier)
    for i in range(len(route) - 2, -1, -1):
        next_router = route[i + 1]
        next_ip, next_port = next_router[1], next_router[2]
        
        # Créer la couche intermédiaire
        wrapped = f"NEXT:{next_ip}\nPORT:{next_port}\nPAYLOAD:{c}"
        
        if verbose:
            print(f"\n[CLIENT] Couche {i + 1}: NEXT → {next_router[0]} ({next_ip}:{next_port})")
        
        m_wrapped = text_to_int(wrapped)
        name, ip, port, n, e = route[i]
        
        # Vérifier la taille
        if m_wrapped.bit_length() >= n.bit_length():
            raise ValueError(f"Couche trop grande pour la clé de {name}")
        
        c = encrypt_int(m_wrapped, n, e)
        if verbose:
            print(f"[CLIENT] → Chiffré avec clé de {name}")
    
    if verbose:
        print(f"\n[CLIENT] Oignon construit ({len(str(c))} chars)")
    
    return c

def send_onion(route, dest_ip, dest_port, message, verbose=True):
    """Construit et envoie le message en oignon."""
    # Construire l'oignon
    payload = build_onion(route, dest_ip, dest_port, message, verbose)
    
    # Envoyer au premier routeur
    first = route[0]
    first_ip, first_port = first[1], first[2]
    
    if verbose:
        print(f"\n[CLIENT] === Envoi au premier routeur ===")
        print(f"[CLIENT] Destination: {first[0]} @ {first_ip}:{first_port}")
    
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10)
    
    try:
        s.connect((first_ip, first_port))
        s.send(f"TYPE:ONION\nPAYLOAD:{payload}\n\n".encode())
        if verbose:
            print(f"[CLIENT] ✓ Oignon envoyé avec succès!")
        return True
    except Exception as e:
        print(f"[CLIENT] ✗ Erreur envoi: {e}")
        return False
    finally:
        s.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Client pour routage en oignon")
    parser.add_argument("--master-ip", default="127.0.0.1", help="IP du master")
    parser.add_argument("--master-port", type=int, default=9000, help="Port du master")
    parser.add_argument("--dest-ip", default="127.0.0.1", help="IP du destinataire")
    parser.add_argument("--dest-port", type=int, default=7777, help="Port du destinataire")
    parser.add_argument("--message", "-m", default="Bonjour depuis le client A!", help="Message à envoyer")
    parser.add_argument("--num-routers", "-n", type=int, default=3, help="Nombre de routeurs à utiliser")
    parser.add_argument("--quiet", "-q", action="store_true", help="Mode silencieux")
    args = parser.parse_args()
    
    verbose = not args.quiet
    
    # Récupérer les routeurs
    routers = get_routers(args.master_ip, args.master_port)
    
    if len(routers) < args.num_routers:
        print(f"[CLIENT] ERREUR: Il faut au moins {args.num_routers} routeurs, seulement {len(routers)} disponible(s)")
        exit(1)
    
    # Sélectionner une route aléatoire
    route = random.sample(routers, args.num_routers)
    print(f"\n[CLIENT] Route sélectionnée: {[r[0] for r in route]}")
    
    # Envoyer le message
    success = send_onion(
        route=route,
        dest_ip=args.dest_ip,
        dest_port=args.dest_port,
        message=args.message,
        verbose=verbose
    )
    
    if success:
        print(f"\n[CLIENT] Message envoyé avec succès via {args.num_routers} routeurs")
    else:
        print(f"\n[CLIENT] Échec de l'envoi")
        exit(1)
