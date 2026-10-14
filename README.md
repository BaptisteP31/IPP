# IPP : Imt Planning Proxy

IPP est un serveur "proxy" qui permet de récupérer des fichiers ICS (iCalendar) à partir de `webdbf`(site de planning de l'Institut Mines-Télécom d'Alès). Il permet de créer un lien direct et sans authentification vers votre planning, contournant ainsi les restrications d'accès et permettant l'import simple dans des applications comme Google Calendar ou Outlook.

## Paramétrage

Renommer le fichier config.ini.example en config.ini et remplir les informations d'identification nécessaires.

`LOGIN_URL` correspond à la page de connexion de `webdbf`. Vous n'avez pas besoin de changer ce paramètre.

`URL` correspond à l'URL du fichier ICS que vous souhaitez récupérer. Il est différent pour chaque calendrier. Pour le récupérez, sur `webdbf`, accédez à votre emploi du temps et cliquez sur "syncrho". Récupérz le contenu du champ "url". 
![alt text](image.png)

`USERNAME` et `PASSWORD` correspondent à vos identifiants de connexion pour `webdbf`. Vous devez les remplir avec vos propres informations d'identification. Ce sont normalement les mêmes que ceux pour le mail.

Vous pouvez créer autant de section que vous le souhaitez dans le fichier `config.ini`. Chaque section correspond à un calendrier.

## Cache

IPP télécharge chaque calendrier une fois par heure en arrière-plan et le stocke dans `cache/`. Les requêtes des utilisateurs lisent uniquement ce cache : elles ne contactent jamais `webdbf`. Si un téléchargement échoue, IPP garde la dernière version valide.

## Jetons d'accès

Chaque personne reçoit son propre jeton. Les jetons sont stockés dans `tokens.ini` (voir `tokens.ini.example`). Ce fichier est relu à chaque requête : pas besoin de redémarrer après une modification.

```bash
python tokens.py add alice 1A-INFRES   # crée un jeton et affiche le chemin à partager
python tokens.py list                  # liste les personnes et leurs calendriers
python tokens.py revoke alice          # supprime le jeton d'alice
```

Avec Docker : `docker compose exec flask-app python tokens.py add alice 1A-INFRES`.

L'URL à donner est `https://<votre-domaine>/<jeton>/<section>`. Un jeton inconnu ou un calendrier non autorisé renvoie une erreur 404.

## Déploiement

La méthode de déploiement recommandée pour IPP est docker et un reverse proxy. Le code est copié dans l'image. Seules les données sont montées depuis l'hôte : `config.ini` (lecture seule), `tokens.ini` et le dossier `cache/`.

Avant le premier lancement, créez `tokens.ini`. Sinon, Docker crée un dossier à sa place et le conteneur refuse de démarrer.

```bash
touch tokens.ini
docker compose up -d --build
```

Le conteneur démarre en root. Son script d'entrée (`entrypoint.sh`) donne `cache/` et `tokens.ini` à l'utilisateur `PUID:PGID` (1000:1000 par défaut), puis lance l'application avec cet utilisateur. L'application ne tourne jamais en root. Si votre utilisateur a d'autres identifiants, lancez `PUID=$(id -u) PGID=$(id -g) docker compose up -d --build`.

Sur un hôte avec SELinux (Fedora, RHEL…), ajoutez `:z` à chaque montage dans `compose.yml`.

Après une modification du code, reconstruisez l'image avec `docker compose up -d --build`.

Faites pointer votre reverse proxy vers le port 5000 du conteneur. Les jetons sont dans l'URL : le reverse proxy doit imposer HTTPS.
