# Limites techniques et dépannage

## Bluetooth

- Le protocole est JSON Lines UTF-8, un objet par ligne, limite de 4096 octets, version 1. Les horodatages sont en millisecondes UTC. Les messages périmés et les coordonnées invalides sont rejetés.
- TCP est limité à `127.0.0.1` entre BeamNG Lua et le connecteur. Bluetooth utilise RFCOMM classique et le service SPP UUID `00001101-0000-1000-8000-00805F9B34FB`; ce n’est ni BLE, ni HID.
- Android publie le service RFCOMM/SPP. Windows initie la connexion vers l’adresse du téléphone appairé et résout le canal par SDP. L’adresse provient de la liste PnP Windows ou peut être saisie manuellement. La reconnexion est automatique tant qu’elle est activée dans le connecteur.
- La publication d’un serveur SPP depuis Windows via `WSASetService` échouait sur la machine de test avec Winsock 10022; le flux a donc été inversé pour éviter cet appel.
- Le mod fourni est une copie non-Git. La licence observée est MIT. L’installateur crée une sauvegarde et ne modifie la copie source qu’après exécution explicite.

## Localisation et Android Auto

L’application utilise l’API publique `LocationManager` de localisation fictive. Android exige de choisir manuellement l’application dans les options pour les développeurs. Certaines applications peuvent détecter ou ignorer une position de test; Android Auto, Google Maps et Waze ne sont pas garantis. L’injection Android ne confirme pas le scénario Android Auto + GPS bridge.

Pour diagnostiquer Open Headunit sans modifier le réseau existant, vérifiez séparément : (1) la position reçue dans l’application du téléphone, (2) la position vue par une application de navigation sur le téléphone, puis (3) Android Auto sans fil sur Open Headunit. Notez à quelle étape la position cesse d’être utilisée. Gardez la connexion Wi-Fi Direct actuelle; ce pont ne configure pas le réseau.

## Dépannage

- **Téléphone absent de la liste Windows** : appairer les appareils dans les réglages système, actualiser la liste, ou saisir l’adresse Bluetooth du téléphone.
- **SPP introuvable** : démarrer le service de réception dans l’application Android avant de lancer **Connecter / réessayer** dans Windows.
- **Connexion refusée** : vérifier que l’adresse correspond au Galaxy appairé et que le service Android est en cours.
- **Aucune donnée du jeu** : démarrer le connecteur, vérifier `127.0.0.1:47720`, la configuration du pont et une session Earth active.
- **Injection refusée** : choisir l’application comme fournisseur fictif dans les options développeur, accorder la localisation, puis redémarrer le service.
- **Données périmées** : l’injection s’arrête après 3 s sans message; la position n’est pas extrapolée.

Le rapport Android omet les coordonnées et identifiants Bluetooth. Les journaux sont locaux et limités à 80 événements.
