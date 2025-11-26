# crypto_simple.py
# RSA pédagogique minimal (uniquement random)
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
    g, x, y = egcd(a, m)
    if g != 1:
        raise Exception("modinv impossible")
    return x % m

def gen_prime():
    """Générateur simple de nombres premiers 'suffisants' pour exercice."""
    while True:
        n = random.randrange(10000, 50000)
        # test de divisibilité simple
        is_prime = True
        for i in range(2, 200):
            if n % i == 0 and n != i:
                is_prime = False
                break
        if is_prime:
            return n

def generate_keys():
    """Génère (n, e, d). e fixé à 17."""
    p = gen_prime()
    q = gen_prime()
    # éviter p == q
    while q == p:
        q = gen_prime()
    n = p * q
    phi = (p - 1) * (q - 1)
    e = 17
    # s'assurer que gcd(e, phi) == 1
    # si e n'est pas coprime, essayer un autre petit e impair
    def gcd(a, b):
        while b:
            a, b = b, a % b
        return a
    if gcd(e, phi) != 1:
        e = 3
        while gcd(e, phi) != 1:
            e += 2
    d = modinv(e, phi)
    return (n, e, d)

def encrypt_int(m, n, e):
    """Chiffre un entier m -> c mod n."""
    return pow(m, e, n)

def decrypt_int(c, n, d):
    """Déchiffre un entier c -> m mod n."""
    return pow(c, d, n)

def text_to_int(s):
    """Convertit une chaine en entier via bytes big-endian."""
    return int.from_bytes(s.encode('utf-8'), 'big')

def int_to_text(x):
    """Convertit entier en chaine (retourne '' si échec)."""
    if x == 0:
        return ""
    try:
        length = (x.bit_length() + 7) // 8
        return x.to_bytes(length, 'big').decode('utf-8')
    except Exception:
        return ""
