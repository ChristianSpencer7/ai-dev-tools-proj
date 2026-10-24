# Deployment

The app runs on one DigitalOcean Droplet with the same Docker Compose setup as local development, plus Caddy for HTTPS. GitHub Actions deploys `main` after every check passes.

| | |
| --- | --- |
| Address | <https://159-89-228-242.sslip.io> |
| Server | DigitalOcean Droplet `stepboard`, Ubuntu 24.04, 1 GB memory + 2 GB swap, New York |
| IP address | `159.89.228.242` (SSH host key `SHA256:Kqaj87mXjy/WENy30kqWTCRx33qDTKZsnTZXEi69LWg`) |
| Login | `ssh deploy@159.89.228.242`, SSH keys only; root and passwords are refused |
| App folder | `/srv/stepboard`, a clone of this repository, with its settings in `/srv/stepboard/.env` |

`159-89-228-242.sslip.io` is a free [sslip.io](https://sslip.io) name that resolves to the IP address. To use a domain instead, point its `A` record at the IP and change `SITE_ADDRESS` in `.env`.

## How it fits together

```
internet ──▶ Caddy :80/:443 ─┬─ /admin, /static ──────────▶ backend (gunicorn) ──▶ db (Postgres)
  (HTTPS, certificates)      └─ everything else ─▶ frontend (nginx) ─ /api ─┘          ▲
                                                    serves the React app       scheduler ┘
```

- **Caddy** (`Caddyfile`) is the only service reachable from the internet. It gets the Let's Encrypt certificate, redirects HTTP to HTTPS, and tells the services behind it the request came in over HTTPS.
- **`docker-compose.prod.yml`** layers production onto `docker-compose.yml`: it adds Caddy, removes the public 8000 and 8080 ports, turns on Django's HTTPS protections (`DJANGO_HTTPS=1`), and takes the database password and secret key from `.env`.
- Every `docker compose` command on the server needs both files: `docker compose -f docker-compose.yml -f docker-compose.prod.yml …`. The commands below shorten this to `dc`; add `alias dc='docker compose -f docker-compose.yml -f docker-compose.prod.yml'` to `~/.bashrc`.

## Setting up a new server

Done once, in this order. Run the commands one block at a time and check each block's output.

### 1. Create the Droplet

- Ubuntu 24.04 LTS, Basic / Regular, the plan with **at least 1 GB of memory** (512 MB can't build the React app).
- Authentication: **SSH key** (`ssh-keygen -t ed25519`, then paste the `.pub` file). No password.
- Optional: improved metrics monitoring (free), backups (paid).

### 2. Secure it (as root, the first time only)

```bash
apt update && apt -y upgrade                     # keep the local sshd_config if asked
apt -y install ufw unattended-upgrades
hostnamectl set-hostname stepboard

adduser --gecos "" deploy                        # the password is for sudo only
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh && cp /root/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh && chmod 600 /home/deploy/.ssh/authorized_keys
```

Check `ssh deploy@<ip>` and `sudo whoami` work in a second window **before** the next block, or it can lock you out.

```bash
# SSH uses the first value it finds; 00- sorts before the image's 50-cloud-init.conf.
cat > /etc/ssh/sshd_config.d/00-hardening.conf <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
EOF
sshd -t && systemctl reload ssh

ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
```

Docker bypasses `ufw` for ports that containers publish, so the production compose file publishes only Caddy's. A DigitalOcean Cloud Firewall allowing only 22, 80 and 443 adds a second layer that Docker can't get around; if you add one, it must allow 80 and 443 too.

### 3. Install Docker (as deploy)

From Docker's instructions for Ubuntu (<https://docs.docker.com/engine/install/ubuntu/>):

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker deploy                   # then log out and back in
```

Being in the `docker` group is equivalent to root on the server: keep the `deploy` user's SSH keys safe.

### 4. First start

```bash
sudo mkdir -p /srv/stepboard && sudo chown deploy:deploy /srv/stepboard
git clone https://github.com/ChristianSpencer7/ai-dev-tools-proj.git /srv/stepboard
cd /srv/stepboard

# The server's own settings. Never committed; readable only by deploy.
cat > .env <<EOF
SITE_ADDRESS=159-89-228-242.sslip.io
POSTGRES_PASSWORD=$(openssl rand -hex 32)
DJANGO_SECRET_KEY=$(openssl rand -hex 32)
EOF
chmod 600 .env

./scripts/deploy.sh                              # fetches main, builds and starts everything
dc exec backend python manage.py createsuperuser # an admin account for /admin/
```

Optional: add `DISCORD_WEBHOOK_URL=…` to `.env` to post digests to Discord, then run `./scripts/deploy.sh` again.

Check: `https://<address>` shows the Demo Family's boards, `http://<address>` redirects to HTTPS, `/admin/` is styled and logs in, and ports 8000 and 8080 aren't reachable from outside.

### 5. Let GitHub Actions deploy

The `Deploy to production` job in `.github/workflows/ci.yml` runs on every push to `main` once all checks pass: it connects over SSH, which runs `scripts/deploy.sh`, then waits until the live site's health check, API and React app all respond.

GitHub gets its own SSH key, which the server allows to do one thing only: run `deploy.sh`. No shell, no other commands, no port forwarding.

1. On your computer, make the key. Leave the passphrase empty, since nobody is there to type it:
   `ssh-keygen -t ed25519 -f $env:USERPROFILE\.ssh\stepboard-deploy -C "github-actions-deploy"`
2. On the server, add its **public** half to the end of `/home/deploy/.ssh/authorized_keys`, with the restriction in front:
   `restrict,command="/srv/stepboard/scripts/deploy.sh" ssh-ed25519 AAAA… github-actions-deploy`
   In PowerShell, this copies that line: `'restrict,command="/srv/stepboard/scripts/deploy.sh" ' + (Get-Content $env:USERPROFILE\.ssh\stepboard-deploy.pub) | Set-Clipboard`
3. Test it: `ssh -i $env:USERPROFILE\.ssh\stepboard-deploy deploy@159.89.228.242` should run a deploy and disconnect, without a shell.
4. In the repository's **Settings → Secrets and variables → Actions**, add:

| Secret | Value |
| --- | --- |
| `DEPLOY_HOST` | `159.89.228.242` |
| `DEPLOY_USER` | `deploy` |
| `DEPLOY_SSH_KEY` | the **private** key file `stepboard-deploy` |
| `DEPLOY_KNOWN_HOSTS` | the output of `ssh-keyscan -t ed25519 159.89.228.242`, so the deploy can tell it's talking to the real server |

5. Delete the private key file from your computer once it's stored in GitHub. To replace the key, repeat these steps and remove the old line from `authorized_keys`.

## Day to day

Run these on the server, in `/srv/stepboard`.

| Task | Command |
| --- | --- |
| Deploy the latest `main` by hand | `./scripts/deploy.sh` |
| What's running | `dc ps` |
| Logs (follow) | `dc logs -f backend` (or `scheduler`, `caddy`, `frontend`, `db`) |
| When the digests run next | `dc logs scheduler \| grep -E '(weekly\|monthly) +[A-Z]'` |
| Health report, safe to share | `ops/collect.sh`; when something's wrong, see the [runbook](../ops/runbook.md) |
| Restart one service | `dc restart backend` |
| Admin account | `dc exec backend python manage.py createsuperuser` |
| Refresh the demo data | `dc exec backend python manage.py seed_demo --reset` (also removes anyone who joined it) |
| Send this week's digests now | `dc exec backend python manage.py send_digests weekly` |

### Backups

The data lives in the `pgdata` Docker volume. To make a backup:

```bash
mkdir -p ~/backups
dc exec -T db pg_dump -U stepboard stepboard | gzip > ~/backups/stepboard-$(date +%F).sql.gz
```

To restore one into an empty database: `gunzip -c ~/backups/<file>.sql.gz | dc exec -T db psql -U stepboard stepboard`. Copy backups off the server too, for example with `scp`.

### Undoing a bad deploy

Revert the commit on GitHub, or push a fix, so `main` is good again; CI then deploys it. In an emergency, deploy an earlier commit by hand without waiting for CI:

```bash
git reset --hard <good commit> && dc up -d --build --wait
```

The next deploy from `main` replaces it.

### Troubleshooting

**`Bind for 0.0.0.0:80 failed: port is already allocated`.** Something else holds port 80 or 443, such as a test container (`docker ps` shows it; `docker stop <name>`). After freeing the port, recreate the containers that were created during the failed run, or they stay half set up (next item):
`dc up -d --force-recreate --wait caddy frontend`.

**Caddy logs `lookup acme-v02.api.letsencrypt.org on 127.0.0.53:53 … connection refused`, and the site doesn't answer.** The Caddy container was created during a failed start: `dc ps` shows no ports for it, and `docker exec stepboard-caddy-1 cat /etc/resolv.conf` shows `127.0.0.53` instead of Docker's `127.0.0.11`. Recreate it with the command above; within a minute `dc logs caddy` should say "certificate obtained successfully".

**The site doesn't load at all.** `dc ps` should list all five services as running, the backend as healthy, and Caddy with `0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp`. Then check `dc logs caddy --tail 30` and `dc logs backend --tail 30`.

### Changing a secret

Edit `.env`, then `./scripts/deploy.sh`. A new `DJANGO_SECRET_KEY` logs everyone out of the admin. `POSTGRES_PASSWORD` is only read when the database is first created, so changing it later also needs `ALTER USER stepboard PASSWORD '…'` in `dc exec db psql -U stepboard`.
