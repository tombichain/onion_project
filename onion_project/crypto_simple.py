# crypto_simple.py
# RSA pédagogique amélioré (uniquement random)
# Corrections : nombres premiers plus grands + chunking pour messages longs

import random

def egcd(a, b):
    """Extended gcd: retourne (g, x, y) tel que a*x + b*y = g = gcd(a,b)."""
    if a == 0:
        return (b, 0, 1)
    else:
        g, x1, y1 = egcd(b % a, a)
        x = y1 - (b // a) * x1
        y = x1
        return (g, x, y)

def modinv(a, m):
    """Inverse modulaire de a modulo m."""
    g, x, _ = egcd(a, m)
    if g != 1:
        raise Exception("modinv impossible")
    return x % m

def is_prime_miller_rabin(n, k=10):
    """Test de primalité Miller-Rabin (plus fiable que la division simple)."""
    if n < 2:
        return False
    if n == 2 or n == 3:
        return True
    if n % 2 == 0:
        return False
    
    # Écrire n-1 comme 2^r * d
    r, d = 0, n - 1
    while d % 2 == 0:
        r += 1
        d //= 2
    
    # Tester k témoins
    for _ in range(k):
        a = random.randrange(2, n - 1)
        x = pow(a, d, n)
        
        if x == 1 or x == n - 1:
            continue
        
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True

def gen_prime(bits=512):
    """Génère un nombre premier de 'bits' bits (défaut: 512 bits)."""
    while True:
        # Générer un nombre impair de la bonne taille
        n = random.getrandbits(bits)
        n |= (1 << bits - 1) | 1  # S'assurer qu'il a bien 'bits' bits et qu'il est impair
        
        if is_prime_miller_rabin(n):
            return n

def gcd(a, b):
    """Plus grand commun diviseur."""
    while b:
        a, b = b, a % b
    return a

def generate_keys(bits=1024):
    """
    Génère (n, e, d) avec des nombres premiers de 'bits' bits.
    n aura environ 2*bits bits, ce qui permet de chiffrer des messages
    de taille (2*bits - 1) bits.
    """
    print(f"[CRYPTO] Génération de clés RSA ({bits} bits par premier)...")
    
    p = gen_prime(bits)
    q = gen_prime(bits)
    
    # Éviter p == q
    while q == p:
        q = gen_prime(bits)
    
    n = p * q
    phi = (p - 1) * (q - 1)
    
    # e = 65537 est standard et sécurisé
    e = 65537
    
    # S'assurer que gcd(e, phi) == 1
    if gcd(e, phi) != 1:
        e = 17
        while gcd(e, phi) != 1:
            e += 2
    
    d = modinv(e, phi)
    
    print(f"[CRYPTO] Clés générées (n a {n.bit_length()} bits)")
    return (n, e, d)

def encrypt_int(m, n, e):
    """Chiffre un entier m -> c mod n."""
    if m >= n:
        raise ValueError(f"Message trop grand: {m.bit_length()} bits, max {n.bit_length()-1} bits")
    return pow(m, e, n)

def decrypt_int(c, n, d):
    """Déchiffre un entier c -> m mod n."""
    return pow(c, d, n)

def text_to_int(s):
    """Convertit une chaîne en entier via bytes big-endian."""
    return int.from_bytes(s.encode('utf-8'), 'big')

def int_to_text(x):
    """Convertit entier en chaîne (retourne '' si échec)."""
    if x == 0:
        return ""
    try:
        length = (x.bit_length() + 7) // 8
        return x.to_bytes(length, 'big').decode('utf-8')
    except Exception:
        return ""

def get_max_message_size(n):
    """Retourne la taille max en bytes d'un message pour ce n."""
    return (n.bit_length() - 1) // 8

def encrypt_text(text, n, e):
    """
    Chiffre un texte en gérant les messages plus grands que n.
    Retourne une chaîne de chunks séparés par '|'.
    """
    max_bytes = get_max_message_size(n)
    text_bytes = text.encode('utf-8')
    
    chunks = []
    for i in range(0, len(text_bytes), max_bytes):
        chunk = text_bytes[i:i + max_bytes]
        m = int.from_bytes(chunk, 'big')
        c = encrypt_int(m, n, e)
        chunks.append(str(c))
    
    return '|'.join(chunks)

def decrypt_text(encrypted, n, d):
    """
    Déchiffre un texte chiffré par encrypt_text.
    """
    max_bytes = get_max_message_size(n)
    chunks = encrypted.split('|')
    
    result_bytes = b''
    for chunk_str in chunks:
        c = int(chunk_str)
        m = decrypt_int(c, n, d)
        # Calculer la longueur en bytes
        length = (m.bit_length() + 7) // 8
        result_bytes += m.to_bytes(length, 'big')
    
    return result_bytes.decode('utf-8')


# === Tests si exécuté directement ===
if __name__ == "__main__":
    print("=== Test du module crypto_simple ===\n")
    
    # Générer des clés (plus petites pour le test)
    n, e, d = generate_keys(bits=256)
    print(f"n = {n}")
    print(f"e = {e}")
    print(f"d = {d}")
    print(f"Taille de n: {n.bit_length()} bits")
    print(f"Taille max message: {get_max_message_size(n)} bytes\n")
    
    # Test simple
    message = "Hello World!"
    print(f"Message original: {message}")
    m = text_to_int(message)
    c = encrypt_int(m, n, e)
    m2 = decrypt_int(c, n, d)
    decrypted = int_to_text(m2)
    print(f"Message déchiffré: {decrypted}")
    print(f"Test simple: {'OK' if message == decrypted else 'ERREUR'}\n")
    
    # Test message long
    long_message = "Ceci est un message très long qui dépasse la taille maximale permise par n. " * 5
    print(f"Message long ({len(long_message)} chars): {long_message[:50]}...")
    encrypted = encrypt_text(long_message, n, e)
    print(f"Chiffré ({len(encrypted.split('|'))} chunks)")
    decrypted_long = decrypt_text(encrypted, n, d)
    print(f"Déchiffré: {decrypted_long[:50]}...")
    print(f"Test long: {'OK' if long_message == decrypted_long else 'ERREUR'}")
