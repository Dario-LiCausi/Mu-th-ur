# Architecture
```
 phone / laptop ──(private VPN mesh, no public ports)──> reverse proxy (internal CA, HTTPS)
                                                           ├─ file server (Nextcloud)
                                                           ├─ photo library (Immich)
                                                           ├─ password manager (Vaultwarden)
                                                           ├─ log viewer, dashboard
                                                           └─ local LLM runner (Ollama, small model)
 Telegram bot ──> relay (approval codes) ──> agent panes (terminal multiplexer)
 external drives: personal archive (read-only for agents) | backup drive (nightly restic)
```
- **Host:** one Ubuntu 24.04 machine, an old gaming laptop (4 cores / 8 threads, 15 GB RAM, a 3 GB laptop GPU that the model server cannot use yet), Docker for services.
- **Access:** only through a private VPN mesh. Services bind to the mesh address, never to all interfaces.
- **Storage:** an external personal archive, mounted in layers (see `scripts/layered-readonly-mount.sh`); a separate backup drive.
- **Backups:** nightly encrypted, deduplicated backups (restic) plus password-manager database dumps; restore is tested.
- **Monitoring:** a daily plain-text health note (`scripts/health.sh`): backup age, free disk, failed units, containers, pending reboot.
- **Agents:** run in terminal panes managed by a multiplexer; they talk to the owner through a Telegram relay.
