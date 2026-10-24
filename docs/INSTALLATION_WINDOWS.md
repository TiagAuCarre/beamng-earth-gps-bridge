# Installation Windows

1. Installer Python 3.11 ou plus récent et vérifier `py --version`. Le connecteur utilise uniquement la bibliothèque standard Python; aucun paquet `pip` ni connexion Internet n’est nécessaire après installation.
2. Appairer le PC et le Galaxy dans **Paramètres → Bluetooth** sur les deux appareils.
3. Dans l’application Android, accorder les autorisations demandées et appuyer sur **Démarrer la réception Bluetooth**.
4. Depuis la racine du dépôt, lancer `py .\windows-connector\connector.py`. Dans la liste des appareils appairés, choisir le téléphone puis cliquer sur **Connecter / réessayer**. Si la liste est vide, saisir l’adresse Bluetooth du téléphone dans le champ (format `AA:BB:CC:DD:EE:FF`). Windows réessaie automatiquement tant que la connexion est activée.
5. Pour un essai indépendant du jeu, utiliser **Envoyer position fictive…**. Les positions sont marquées `source=test` et `test=true`.
6. Pour BeamNG.earth, installer le pont comme décrit dans `INSTALLATION_BEAMNG.md`.

Le connecteur ne modifie ni le Wi-Fi, ni Android Auto, ni Mobile connecté. Android publie le service SPP; Windows s’y connecte au moyen de l’adresse Bluetooth appairée et de l’UUID RFCOMM. Cela évite l’enregistrement SDP Windows (`WSASetService`) qui échoue sur certaines piles Bluetooth avec l’erreur 10022.
