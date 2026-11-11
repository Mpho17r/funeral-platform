# Deploying FuneralOS to a South African server

`deploy/setup-server.sh` sets up a fresh Ubuntu 24.04 server in one go. **It has not been run on a real server yet** (it is syntax-checked only), so do the first run on a cheap spare server, not the one a customer will use.

## 1. What to buy
- A VPS located in South Africa (for example from Afrihost, Hetzner's Johannesburg-region partners, Xneelo, or AWS af-south-1), Ubuntu 24.04, 2 CPU / 4 GB RAM / 40+ GB disk, with the provider's disk or volume encryption switched on and automatic snapshots if offered.
- A domain name you control (a `.co.za` is fine).

## 2. DNS
Add two A records pointing at the server's IP address:
- `app.yourdomain.co.za`
- `api.yourdomain.co.za`

Wait until they resolve (usually minutes), otherwise HTTPS certificates cannot be issued.

## 3. Run the setup
Log in to the server over SSH, then:

```bash
git clone https://github.com/Mpho17r/funeral-platform.git /tmp/fos   # private repo: use a token in the URL
sudo DOMAIN=yourdomain.co.za REPO_URL=https://github.com/Mpho17r/funeral-platform.git \
     bash /tmp/fos/deploy/setup-server.sh
```

It installs everything, creates a random database password and secret key (in `/srv/funeralos/backend/.env`, readable only by the service user), opens only ports 22, 80 and 443, builds the app and starts three services.

Then create the first business owner and your operator login with the two commands it prints, open `https://app.yourdomain.co.za`, and check `https://api.yourdomain.co.za/health`.

## 4. Updating later
```bash
sudo DOMAIN=yourdomain.co.za bash /srv/funeralos/deploy/update.sh
```
It takes a backup first, pulls the latest code, applies database changes, rebuilds and restarts.

## 5. Before real families are entered
Work through section 4 of [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md): restore one backup onto a spare database, copy backups off the server, add an uptime monitor on `/health`, switch on email in `backend/.env` if wanted, and complete the POPIA items in section 5.

## Rolling back
Updates apply database changes that older code may not understand, so to go back, restore the backup `update.sh` took just before the update (see BACKUPS_AND_RECOVERY.md) and check out the previous commit.
