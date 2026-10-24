# Installation Android

1. Réinstallez `android/app/build/outputs/apk/debug/app-debug.apk` (USB, transfert local ou `adb install -r app-debug.apk`). Cette version déclare `ACCESS_MOCK_LOCATION`, nécessaire à la sélection comme application de localisation fictive.
2. Ouvrez **Paramètres → Options de développement → Application de localisation fictive** et sélectionnez **BeamNG GPS Bridge**. Ce choix reste manuel.
3. Appairez le PC Windows depuis les réglages Bluetooth du téléphone.
4. Ouvrez l’application, accordez l’autorisation Bluetooth demandée, puis appuyez sur **Démarrer la réception Bluetooth**. La réception fonctionne sans autorisation de localisation.
5. Dans le connecteur Windows, sélectionnez le Galaxy appairé et cliquez **Connecter / réessayer**. Il doit afficher **Téléphone Android connecté en RFCOMM**.
6. Activez l’injection dans l’application seulement quand des positions valides arrivent; l’application demandera alors la permission de localisation. La position courante et son âge s’affichent à l’écran. L’application ne conserve pas d’historique ni de journal de positions.

La réception Bluetooth et l’injection Android sont deux étapes séparées. Sans app sélectionnée comme fournisseur fictif, l’injection sera refusée par Android. Même après injection, le comportement de Google Maps, Waze ou Android Auto dépend de ces applications et doit être testé séparément; le pont ne touche pas au Wi-Fi Direct.
