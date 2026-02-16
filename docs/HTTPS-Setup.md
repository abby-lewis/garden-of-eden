# HTTPS setup (Option 1: separate port for garden API)

Use this if port 443 is already forwarded to another service (e.g. Home Assistant). The garden API is exposed on **port 8444** with HTTPS; 443 stays unchanged.

**Result:** `https://<your-ddns-hostname>:8444` → garden API (TLS encrypted).

---

## Prerequisites

- DDNS hostname pointing to your home IP (e.g. `manliestben.zapto.org`).
- Raspberry Pi running garden-of-eden (Flask on port 5000).
- Port 443 remains forwarded to your other service (e.g. Home Assistant).

---

## Step 1: Forward ports on the router

1. Log into your router and open **Port Forwarding** (or **Virtual Server** / **NAT**).
2. Add two rules:

   | External port | Internal IP (Pi) | Internal port | Purpose        |
   |---------------|------------------|---------------|----------------|
   | **80**        | \<Pi IP\>        | 80            | Let's Encrypt  |
   | **8444**      | \<Pi IP\>        | 443           | Garden API HTTPS |

   - **80** is used only for Let's Encrypt certificate issuance and renewal (HTTP-01 challenge). If you already use 80 for something else, see [Certificate options](#certificate-options) below.
   - **8444** is the port you’ll use in the browser/API base URL. If your router uses 8444 too, pick another (e.g. 9443, 8445) and use it in the table and in the Caddy `:80` redirect.

3. Save and apply. Ensure the Pi has a **static/reserved IP** on your LAN so the forward always targets it.

---

## Step 2: Install Caddy on the Pi

Caddy will terminate TLS and reverse-proxy to Flask.

**On Raspberry Pi OS (Debian):**

```bash
sudo apt update
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

Or use the [official install instructions](https://caddy.com/docs/install) for your OS.

---

## Step 3: Create the Caddyfile

Replace `<your-ddns-hostname>` with your actual hostname (e.g. `manliestben.zapto.org`).

```bash
sudo nano /etc/caddy/Caddyfile
```

**Contents:** Use **only** the block below. It uses your hostname so Caddy can obtain and renew a Let's Encrypt certificate automatically. Do **not** add a separate `:443 { ... }` block — that would be redundant and wouldn't get a proper cert.

```caddyfile
<your-ddns-hostname>:443 {
    reverse_proxy 127.0.0.1:5000
}
```

Replace `<your-ddns-hostname>` with your actual hostname (e.g. `manliestben.zapto.org`). Caddy will obtain and renew the certificate via HTTP-01 (port 80 must reach this Pi; see Step 1).

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

## Step 4: Allow Caddy to bind to port 443

Port 443 is privileged. Either:

**A) Run Caddy as root (default with `apt`):**

```bash
sudo systemctl enable caddy
sudo systemctl start caddy
```

**B) Or grant the binary permission to bind to low ports (alternative):**

```bash
sudo setcap 'cap_net_bind_service=+ep' $(which caddy)
```

Then run Caddy as your preferred user (e.g. via systemd unit with `User=gardyn`).

---

## Step 5: Start Caddy and the Flask app

1. Start (or restart) the garden-of-eden app so it is listening on `127.0.0.1:5000`:

   ```bash
   cd /path/to/garden-of-eden
   source venv/bin/activate
   python run.py
   ```

   (Run this under systemd/screen/tmux so it stays up; see main README for your setup.)

2. Start Caddy:

   ```bash
   sudo systemctl start caddy
   sudo systemctl status caddy
   ```

   If you used the hostname in the Caddyfile, Caddy will request a certificate on first start; ensure port 80 is reachable from the internet (Step 1).

---

## Step 6: Test from outside your network

From a device **not** on your home LAN (e.g. phone on cellular, or a friend’s network):

- Open: `https://<your-ddns-hostname>:8444`
- You should see your API (or a JSON response), with a valid lock icon if using Let's Encrypt.

Use this as the **base URL** for the API, e.g. in the gardyn-dashboard `.env`:

```env
VITE_API_BASE_URL=https://<your-ddns-hostname>:8444
```

---

## Step 7: Firewall (if enabled on the Pi)

If `ufw` or similar is enabled, allow HTTP and HTTPS:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

---

## Certificate options

- **Let's Encrypt (HTTP-01):** Port 80 must be forwarded to the Pi so Caddy can complete the challenge. Renewal is automatic; leave the 80 forward in place.
- **Let's Encrypt (DNS-01):** No port 80 needed; requires a DNS API (e.g. for a domain you control). Not covered here.
- **Self-signed:** No port 80 or internet challenge. Run Caddy with `tls internal` in the Caddyfile to generate a self-signed cert. Browsers and API clients will show a “not trusted” warning unless you install the cert or disable verification (acceptable for a private dashboard).

---

## Troubleshooting

| Issue | Check |
|-------|--------|
| Connection refused on :8444 | Router forwards 8444 → Pi:443; Caddy is running (`systemctl status caddy`); firewall allows 443. |
| Certificate errors | Port 80 must reach the Pi for HTTP-01. Test with `curl -I http://<your-hostname>` from outside. |
| 502 Bad Gateway | Flask is running on port 5000; Caddy’s `reverse_proxy` points at `127.0.0.1:5000`. |
| Caddy won’t start | Run `sudo caddy validate --config /etc/caddy/Caddyfile`. Ensure no other process uses 80 or 443. |

---

## Summary

1. Forward **80** → Pi:80 and **8444** → Pi:443; Pi has a static IP.
2. Install Caddy; Caddyfile with hostname:443 and `reverse_proxy 127.0.0.1:5000`.
3. Start Caddy and Flask; use `https://<hostname>:8444` as the API base URL.
