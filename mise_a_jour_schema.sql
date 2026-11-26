-- À exécuter UNE FOIS sur la base TiDB (connexion TiDB SAP-Virunga), avant la migration.
-- Le compte « visiteur » a le rôle 'visiteur', absent de la définition initiale.
USE sapvirunga;
ALTER TABLE comptes MODIFY role VARCHAR(20) NOT NULL;
