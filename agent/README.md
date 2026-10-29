# Agent IPP

L'accès au planning étant limité au réseau de l'école, cet agent télécharge les calendriers depuis votre ordinateur et les envoie au serveur IPP. Un minuteur utilisateur le lance toutes les 15 minutes et après le démarrage.

## Installation et configuration

Il faut Linux, systemd utilisateur, Python 3.11 ou plus et uv (`sudo pacman -S uv` sur Arch). Lancez `./install.sh`, puis modifiez `~/.config/ipp-agent/config.ini` : renseignez le serveur HTTPS, le jeton et vos identifiants et URL webdbf pour chaque section. Le nom de section doit correspondre à celui du serveur. Gardez ce fichier privé (`chmod 600`).

L'administrateur du serveur crée le jeton avec `python tokens.py push-add <name> <section>` et vous le transmet.

## Test et journaux

```bash
uv run --script ~/.local/share/ipp-agent/ipp_agent.py --dry-run
systemctl --user start ipp-agent.service && journalctl --user -u ipp-agent -e
```

L'option `--config chemin` choisit un autre fichier et `-v` active les messages de diagnostic. Le mode `--dry-run` télécharge et vérifie sans envoyer.

## Déclenchement NetworkManager facultatif

Modifiez la variable `user` dans `networkmanager/90-ipp-agent`, puis installez manuellement le fichier avec `sudo install -m 755 networkmanager/90-ipp-agent /etc/NetworkManager/dispatcher.d/90-ipp-agent`. Il lance aussi le service lors d'une connexion réseau. Supprimez ce fichier avec sudo pour le désactiver.

## Désinstallation et problèmes

Lancez `./uninstall.sh` ; la configuration est conservée.

Chaque hôte de connexion est testé une fois : les sections dont l'hôte est inaccessible sont ignorées sans erreur. Une réponse 403 au test est aussi considérée comme un accès hors du réseau de l'école. Si le réseau est inaccessible sur place, vérifiez la connexion et l'URL de connexion. Une erreur 401 indique un jeton incorrect ou une section non autorisée ; 409 indique que la section n'est pas en mode push ; 400 indique que le serveur a rejeté le calendrier. Contactez l'administrateur si nécessaire.
