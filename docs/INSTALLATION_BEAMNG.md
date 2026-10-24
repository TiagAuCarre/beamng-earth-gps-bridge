# Pont GPS BeamNG.earth

Le pont est un **mod BeamNG séparé**. Il ne modifie pas `beamng_earth`, donc les mises à jour quotidiennes du mod principal ne remplacent pas le pont. Son extension lit `beamngEarth_core._state()`, qui contient la latitude et la longitude WGS84 calculées par l’ancre Earth. La vitesse est en m/s, l’altitude vient de l’état du joueur et le cap est calculé dans le nord local à partir du mouvement.

## Installation

Depuis la racine du projet, installez le mod dans le dossier de données utilisateur du jeu :

```powershell
py .\beamng-mod\install_bridge_mod.py "C:\CHEMIN\VERS\BeamNG\current"
```

Le mod est copié dans `mods/unpacked/bng_gps_bridge`. Redémarrez BeamNG.drive ou rechargez les mods, puis vérifiez qu’il est activé dans le Gestionnaire de mods. L’installateur refuse d’écraser un dossier du même nom s’il ne contient pas `info.json`.

Le relais est **désactivé par défaut**. Pour l’activer, ouvrez `mods/unpacked/bng_gps_bridge/lua/ge/extensions/bngGpsBridge/config.lua` et mettez `enabled = true`. Il ouvre alors seulement une connexion TCP vers `127.0.0.1:47720`, sans attente bloquante. Remettez `false` pour le couper.

## Démarrage et diagnostic

1. Lancez l’application Android et démarrez son service Bluetooth SPP.
2. Lancez `py .\windows-connector\connector.py`, sélectionnez le téléphone appairé et connectez-vous.
3. Activez le relais dans `config.lua`. Pour tester sans la carte, utilisez le bouton de position fictive du connecteur.
4. Chargez la carte BeamNG.earth et attendez que le véhicule et son ancre géographique soient actifs. Dans la console BeamNG (`~`), filtrez `beamngEarth.gpsbridge`.

`pont activé` indique que le relais tourne; `connecté au connecteur Windows` confirme le TCP local; `positions préparées` indique que des coordonnées sont émises. Le compteur Windows doit augmenter. Si rien n’apparaît, vérifiez que le mod GPS est monté et activé, puis que la carte Earth a chargé son extension cœur.

La fréquence par défaut est 30 Hz (une position toutes les ~33 ms), bornée par la cadence de mise à jour du jeu. Les lignes JSON UTF-8 sont limitées à 4096 octets et la file à 8 KiB. Le socket est non bloquant; les erreurs sont journalisées et retentées. La lecture de `_state()` dépend de l’API du cœur BeamNG.earth; si cette API change dans une mise à jour, seul ce petit mod devra être adapté.
