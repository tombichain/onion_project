-- mariadb_init.sql
-- Script d'initialisation de la base de données pour le routage en oignon
-- À exécuter avec: mysql -u root -p < mariadb_init.sql

-- Création de la base de données
CREATE DATABASE IF NOT EXISTS onion;
USE onion;

-- Suppression des anciennes tables (optionnel, pour réinitialisation)
DROP TABLE IF EXISTS routers;
DROP TABLE IF EXISTS logs;

-- Table des routeurs
CREATE TABLE IF NOT EXISTS routers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ip VARCHAR(45) NOT NULL,
    port INT NOT NULL,
    n TEXT NOT NULL,                    -- Clé publique (modulus)
    e TEXT NOT NULL,                    -- Clé publique (exposant)
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_name (name),
    INDEX idx_ip_port (ip, port)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Table des logs (optionnel, pour le suivi)
CREATE TABLE IF NOT EXISTS logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level VARCHAR(10) DEFAULT 'INFO',   -- INFO, WARNING, ERROR
    source VARCHAR(50),                  -- master, router, client
    message TEXT,
    INDEX idx_timestamp (timestamp),
    INDEX idx_source (source)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Utilisateur dédié (optionnel, recommandé pour la production)
-- CREATE USER IF NOT EXISTS 'onion_user'@'%' IDENTIFIED BY 'onion_password';
-- GRANT ALL PRIVILEGES ON onion.* TO 'onion_user'@'%';
-- FLUSH PRIVILEGES;

-- Vérification
SELECT 'Base de données onion initialisée avec succès!' AS status;
SHOW TABLES;
