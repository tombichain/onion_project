# Projet de Routage en Oignon

Ce projet implémente un système de communication anonyme basé sur le principe du routage en oignon, similaire à Tor. Les messages sont chiffrés en plusieurs couches et transitent par une chaîne de routeurs, chacun ne connaissant que son voisin immédiat.

## Principe de fonctionnement

Le client qui souhaite envoyer un message commence par récupérer la liste des routeurs disponibles auprès du Master. Il sélectionne ensuite aléatoirement 3 routeurs pour construire sa route. Le message est chiffré en couches successives : d'abord avec la clé du dernier routeur, puis celle de l'avant-dernier, etc. Chaque routeur ne peut déchiffrer que sa propre couche, découvrant ainsi uniquement l'adresse du prochain saut.


## Organisation des machines

Pour faire fonctionner le système, il faut répartir les composants sur plusieurs machines :

La première VM Debian héberge le Master et la base de données MariaDB. Elle écoute sur le port 9000.

La deuxième VM Debian fait tourner les trois routeurs (R1, R2, R3) sur les ports 10001, 10002 et 10003.

Le PC Windows physique sert de client avec l'interface graphique.

Une VM Windows fait office de Receiver et écoute sur le port 7777.


## Configuration réseau des machines virtuelles (VMware)

Pour que toutes les machines puissent communiquer entre elles, il faut configurer les cartes réseau des VMs en mode Bridge (Pont).

Dans VMware, pour chaque VM :

1. Eteindre la VM
2. Aller dans VM > Settings > Network Adapter
3. Sélectionner "Bridged: Connected directly to the physical network"
4. L'option "Replicate physical network connection state" peut rester décochée
5. Valider et redémarrer la VM

En mode Bridge, chaque VM obtient une adresse IP sur le même réseau que le PC physique, ce qui permet à toutes les machines de communiquer directement.


## Activer le copier-coller entre le PC et les VMs

Pour les VMs Debian, installer les VMware Tools :

    sudo apt update
    sudo apt install open-vm-tools open-vm-tools-desktop
    sudo reboot

Pour les VMs Windows, aller dans le menu VM > Install VMware Tools, puis lancer l'installateur qui apparaît dans le lecteur CD virtuel et redémarrer.


## Fichiers nécessaires par machine

Il n'est pas nécessaire de copier tous les fichiers sur chaque machine. Chaque composant a besoin uniquement de ses propres fichiers :

VM Master (Debian) : master.py et mariadb_init.sql

VM Routeurs (Debian) : router.py et crypto_simple.py

VM Receiver (Windows) : receiver.py

PC Client (Windows) : gui_client.py et crypto_simple.py


## Installation sur la VM Master (Debian)

Installer les paquets nécessaires :

    sudo apt update
    sudo apt install mariadb-server python3 python3-pip

Se connecter à MariaDB :

    sudo mysql -u root

Créer la base de données :

    CREATE DATABASE IF NOT EXISTS onion;
    USE onion;
    
    CREATE TABLE IF NOT EXISTS routers (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        ip VARCHAR(45) NOT NULL,
        port INT NOT NULL,
        n TEXT NOT NULL,
        e TEXT NOT NULL,
        registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY unique_name (name)
    );
    
    ALTER USER 'root'@'localhost' IDENTIFIED BY '';
    FLUSH PRIVILEGES;
    EXIT;

Installer le connecteur Python pour MariaDB :

    pip3 install mariadb --break-system-packages

Si une erreur survient concernant des headers manquants :

    sudo apt install libmariadb-dev libmariadb3
    pip3 install mariadb --break-system-packages

Ouvrir le port dans le firewall :

    sudo ufw allow 9000/tcp

Lancer le Master :

    python3 master.py --port 9000


## Installation sur la VM Routeurs (Debian)

Installer Python :

    sudo apt update
    sudo apt install python3

Ouvrir les ports :

    sudo ufw allow 10001/tcp
    sudo ufw allow 10002/tcp
    sudo ufw allow 10003/tcp

Récupérer l'adresse IP de la VM Master avec la commande "ip addr show" ou "hostname -I" sur celle-ci.

Lancer les trois routeurs dans des terminaux séparés en remplaçant l'IP par celle de votre VM Master :

    python3 router.py --name R1 --master-ip 172.20.10.8 --master-port 9000 --port 10001
    
    python3 router.py --name R2 --master-ip 172.20.10.8 --master-port 9000 --port 10002
    
    python3 router.py --name R3 --master-ip 172.20.10.8 --master-port 9000 --port 10003


## Installation sur la VM Receiver (Windows)

Télécharger Python depuis python.org et l'installer. Pendant l'installation, cocher impérativement la case "Add Python to PATH" en bas de la fenêtre.

Copier le fichier receiver.py sur la VM, par exemple dans C:\onion_project

Ouvrir une invite de commandes en tant qu'administrateur (clic droit sur cmd > Exécuter en tant qu'administrateur) et autoriser le port 7777 dans le pare-feu :

    netsh advfirewall firewall add rule name="Onion Receiver" dir=in action=allow protocol=tcp localport=7777

Ouvrir une invite de commandes normale, aller dans le dossier du projet et lancer le receiver :

    cd C:\onion_project
    python receiver.py --port 7777


## Installation sur le PC Client (Windows)

Télécharger Python depuis python.org et l'installer en cochant "Add Python to PATH".

Ouvrir une invite de commandes et installer PyQt5 :

    pip install PyQt5

Copier les fichiers gui_client.py et crypto_simple.py dans un dossier, par exemple C:\onion_project

Lancer le client :

    cd C:\onion_project
    python gui_client.py

Dans l'interface, entrer l'IP du Master, cliquer sur "Récupérer routeurs", puis entrer l'IP du Receiver et le message à envoyer.


## Ordre de démarrage

1. Démarrer le Master sur la VM Debian
2. Démarrer les trois routeurs sur l'autre VM Debian
3. Démarrer le Receiver sur la VM Windows
4. Démarrer le Client sur le PC Windows


## En cas de problème

Si les routeurs n'arrivent pas à s'enregistrer auprès du Master, vérifier que le firewall autorise le port 9000 sur la VM Master :

    sudo ufw allow 9000/tcp

Si le message "Erreur handle: Unknown column 'id' in SELECT" apparaît sur le Master, il faut recréer la table. Se connecter à MariaDB et exécuter :

    USE onion;
    DROP TABLE routers;

Puis recréer la table avec la structure indiquée plus haut.

Si le client affiche "Message trop grand", essayer avec un message plus court. Le système RSA a une limite de taille pour les données à chiffrer.

Si le message n'arrive pas au Receiver, vérifier que le pare-feu Windows autorise bien le port 7777.


## Fichiers du projet

crypto_simple.py : implémentation du chiffrement RSA

master.py : serveur central qui gère l'enregistrement des routeurs

router.py : code des routeurs virtuels

client.py : client en ligne de commande

receiver.py : récepteur de messages

gui_master.py : interface graphique du Master

gui_client.py : interface graphique du Client

mariadb_init.sql : script d'initialisation de la base de données
