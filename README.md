# 🔑 Modernewolke Oxygen Online License Server

Zentraler, leichtgewichtiger Lizenzserver zur Verwaltung und kryptografischen Verifizierung von Lizenzen und Modulen für **Oxygen Online (SelectLine WebUI)**.

Öffentliche Adresse: `https://lizensierung.modernewolke.de`

---

## 🎯 Architektur & Lizenz-Workflow

Das Lizenzmodell basiert auf einer **strikt hardware- und instanzgebundenen Paarung**:

```
+------------------------------------+           +-----------------------------------------+
|    Oxygen Online Instanz           |           |  Modernewolke Lizenzserver             |
|   (Kunde / On-Premise / Cloud)     |           |  (lizensierung.modernewolke.de)         |
+------------------------------------+           +-----------------------------------------+
|                                    |           |                                         |
| 1. Generiert einmalige UUID        |           | 2. Lizenz wird im Web-UI angelegt       |
|    beim ersten Start               |           |    - Lizenzschlüssel: OXY-XXXX-XXXX...  |
|    (z. B. in /data/oxygen-inst-id) |           |    - Kunde: z. B. Musterfirma GmbH      |
|                                    |           |    - Module: starface, tickets, ...     |
| 3. Admin kopiert Instanz-UUID ---> | --------> | 4. Admin trägt Instanz-UUID             |
|                                    |           |    für diese Lizenz ein                 |
|                                    |           |                                         |
| 5. Lizenzschlüssel wird in der     |           |                                         |
|    Instanz eingetragen <---------- | <-------- |                                         |
|                                    |           |                                         |
| 6. Instanz ruft Lizenzserver auf   |           |                                         |
|    POST /api/v1/license/verify     |           |                                         |
|    { key: "...", uuid: "..." }     | --------> | 7. Prüft: Key aktiv? Datum gültig?      |
|                                    |           |           UUID stimmt überein?          |
| 8. Instanz speichert Cache &       |           |                                         |
|    schaltet Module aktiv <-------- | <-------- | 9. Antwort mit signiertem Token         |
+------------------------------------+           +-----------------------------------------+
```

### Die 3 Kernprinzipien
1. **Instanz-UUID:** Jede Oxygen Online Instanz erhält beim Erstellen automatisch eine persistente `UUID` (`/data/oxygen-installation-id`).
2. **Lizenzschlüssel:** Im Lizenzserver wird für den Kunden ein Lizenzschlüssel generiert (z. B. `OXY-ABCD-1234-EFGH-5678`).
3. **Koppelung:**
   - Im Lizenzserver wird die **Instanz-UUID** eingetragen.
   - In der Oxygen Online Instanz wird der **Lizenzschlüssel** eingetragen.
   - Der Schlüssel ist **nur in Kombination mit genau dieser Instanz-UUID gültig**.

---

## 🚀 Einrichtung & Deployment auf einem VPS (Ubuntu / Debian)

Diese Anleitung führt Schritt für Schritt durch das Klonen, Konfigurieren und Starten des Lizenzservers auf einem Linux-VPS unter der Domain `lizensierung.modernewolke.de`.

### 1. Voraussetzungen auf dem VPS
Stellen Sie sicher, dass Git, Docker und das Docker Compose Plugin installiert sind:

```bash
# Paketlisten aktualisieren & Basistools installieren
sudo apt update && sudo apt install -y git curl ufw

# Docker & Docker Compose Plugin installieren (falls noch nicht vorhanden)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# Nach dem usermod einmal neu einloggen oder 'newgrp docker' ausführen
```

Prüfen Sie die Installation:
```bash
docker --version
docker compose version
```

Stellen Sie außerdem sicher, dass im DNS der **A-Record** für Ihre Subdomain gesetzt ist:
* **Host:** `lizensierung` (oder `lizensierung.modernewolke.de`)
* **Typ:** `A`
* **Ziel:** Öffentliche IPv4-Adresse Ihres VPS

---

### 2. Repository auf dem VPS klonen

Wir empfehlen die Ablage unter `/opt/oxygen-licensing` (oder im Home-Verzeichnis):

```bash
# Nach /opt wechseln und Repository klonen
sudo mkdir -p /opt
cd /opt

# Per HTTPS klonen (bei privatem Repo: GitHub Token oder SSH Deploy Key verwenden)
sudo git clone https://github.com/SgtRho/oxygen-licensing.git

# Besitzer auf den aktuellen Benutzer anpassen
sudo chown -R $USER:$USER /opt/oxygen-licensing
cd /opt/oxygen-licensing
```

> **Tipp (Authentifizierung bei privatem GitHub-Repo):**  
> Nutzen Sie einen GitHub Personal Access Token (PAT) als Passwort oder hinterlegen Sie den SSH-Key des VPS unter GitHub: `Settings > Deploy keys`.  
> Klonen per SSH: `git clone git@github.com:SgtRho/oxygen-licensing.git`

---

### 3. Konfiguration anlegen (`.env`)

Erstellen Sie Ihre Produktionskonfiguration aus der Vorlage:

```bash
cp .env.example .env
```

Generieren Sie einen sicheren Signaturschlüssel:
```bash
openssl rand -hex 32
```

Bearbeiten Sie die `.env`-Datei:
```bash
nano .env
```

Passen Sie mindestens folgende Werte an:
```env
# Server Port (bleibt intern auf 8000, Nginx leitet darauf weiter)
PORT=8000
HOST=0.0.0.0
DATA_DIR=/data

# WICHTIG: E-Mail und Master-Passwort für den ersten Login!
# Beim ersten Login wird automatisch das 2FA/TOTP-Setup mit QR-Code angezeigt.
ADMIN_EMAIL=admin@modernewolke.de
ADMIN_PASSWORD=IhrSuperSicheresAdminPasswortHier123!

# Optional: Bei true wird der 2FA-Schlüssel zurückgesetzt (z.B. bei Handywechsel)
RESET_ADMIN_TOTP=false

# WICHTIG: Den zuvor mit 'openssl rand -hex 32' erzeugten Key eintragen!
SIGNING_SECRET=e7b4c91a82f3...geheimer_32_byte_hex_key...

# Gültigkeitsdauer der Admin-Sitzung in Stunden
SESSION_EXPIRE_HOURS=48

# CORS
CORS_ORIGINS=*
```
Speichern mit `Strg + O`, beenden mit `Strg + X`.

---

### 4. Lizenzserver per Docker starten

Bauen und starten Sie den Container als Hintergrunddienst:

```bash
docker compose up -d --build
```

Status und Logs prüfen:
```bash
# Container-Status prüfen
docker compose ps

# Live-Logs ansehen
docker compose logs -f
```

Der Dienst läuft nun lokal auf Port `8000`. Sie können den Healthcheck lokal testen:
```bash
curl http://localhost:8000/api/health
# Ausgabe: {"status":"ok","service":"oxygen-license-server","version":"1.0.0"}
```

---

### 5. Reverse-Proxy mit Nginx & SSL (Let's Encrypt) einrichten

Damit der Lizenzserver unter `https://lizensierung.modernewolke.de` sicher per HTTPS erreichbar ist, richten Sie Nginx als Reverse Proxy ein:

```bash
# Nginx & Certbot installieren
sudo apt install -y nginx certbot python3-certbot-nginx
```

Erstellen Sie eine Nginx-Konfigurationsdatei:
```bash
sudo nano /etc/nginx/sites-available/lizensierung.modernewolke.de
```

Fügen Sie folgende Konfiguration ein:
```nginx
server {
    listen 80;
    listen [::]:80;
    server_name lizensierung.modernewolke.de;

    # Weiterleitung auf HTTPS erfolgt automatisch nach Certbot
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Aktivieren Sie die Konfiguration und laden Sie Nginx neu:
```bash
sudo ln -s /etc/nginx/sites-available/lizensierung.modernewolke.de /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Rufen Sie das kostenlose SSL-Zertifikat von Let's Encrypt ab:
```bash
sudo certbot --nginx -d lizensierung.modernewolke.de
```
Certbot konfiguriert HTTPS und die automatische HTTP->HTTPS-Weiterleitung selbstständig.

---

### 6. Firewall konfigurieren (UFW)

Geben Sie nur SSH, HTTP und HTTPS frei:
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

---

### 7. Updates & Wartung auf dem VPS

Wenn Sie Änderungen am Repository pushen, aktualisieren Sie den VPS in Sekunden:

```bash
cd /opt/oxygen-licensing
git pull
docker compose up -d --build
```
> Die Lizenzen und das Audit-Log bleiben im Docker-Volume `oxygen_license_data` erhalten und gehen bei Rebuilds **nicht** verloren.

#### Backup der SQLite-Datenbank erstellen:
```bash
docker run --rm \
  -v oxygen_license_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/license-backup-$(date +%F).tar.gz /data
```

---

## 🖥️ Web-Verwaltungsoberfläche & Authentifizierung

Rufen Sie im Browser auf:
👉 **`https://lizensierung.modernewolke.de/`**

### Authentifizierung & 2-Faktor-Sicherheit (TOTP)
Das Admin-Panel ist standardmäßig durch **E-Mail, Passwort und zeitbasiertes Einmalkennwort (TOTP / RFC 6238)** geschützt:

1. **Erster Login (Erst-Einrichtung von 2FA):**
   - Geben Sie Ihre `ADMIN_EMAIL` und Ihr `ADMIN_PASSWORD` aus der `.env` ein.
   - Da 2FA noch nicht aktiviert ist, öffnet sich sofort der **2FA-Einrichtungsbildschirm**.
   - Scannen Sie den angezeigten **QR-Code** mit Ihrer bevorzugten Authenticator-App (z. B. Google Authenticator, Microsoft Authenticator, 1Password, Bitwarden, etc.) oder kopieren Sie den geheimen Schlüssel manuell.
   - Geben Sie den ersten **6-stelligen Code** aus Ihrer App ein, um 2FA zu bestätigen und zu aktivieren.
   - Sie werden sofort ins Dashboard weitergeleitet.

2. **Regulärer Login:**
   - Geben Sie **E-Mail**, **Passwort** und den aktuellen **6-stelligen TOTP-Code** ein.

3. **Zugangsdaten & 2FA verwalten:**
   - Im Dashboard oben rechts über das Profil-Icon (Klick auf Ihre E-Mail-Adresse) können Sie Ihr Passwort ändern oder bei Bedarf das TOTP-Geheimnis erneuern.

---

### Lizenz-Workflow im Dashboard

1. **Neue Lizenz anlegen:**
   - Klicken Sie auf **`+ Neue Lizenz anlegen`**.
   - Tragen Sie den Kundennamen ein (z. B. *Musterfirma GmbH*).
   - Klicken Sie auf **`🎲 Neu generieren`**, um einen Lizenzschlüssel (z. B. `OXY-ABCD-1234-EFGH-5678`) zu erzeugen.
   - Wählen Sie die freizuschaltenden Module (`starface`, `server_reports`, `warehouse`, etc.) und optional ein Ablaufdatum.
   - Die **Instanz-UUID** kann vorerst leer bleiben, wenn der Kunde die Instanz noch nicht eingerichtet hat.
2. **Instanz verknüpfen:**
   - Der Kunde öffnet seine Oxygen-Instanz unter **Verwaltung > Module & Lizenz** und kopiert seine **Instanz-UUID**.
   - Im Lizenzserver klicken Sie bei der Kundenlizenz auf **`⚠️ UUID eintragen`** und fügen die UUID ein.
   - Der Kunde trägt in seiner Instanz den Lizenzschlüssel ein und klickt auf **"Speichern & Prüfen"**.
   - Die Module werden sofort freigeschaltet!

---

## 📡 REST-API Endpunkte

### Public Verification (für Oxygen Online Clients)
`POST /api/v1/license/verify`

**Request:**
```json
{
  "license_key": "OXY-ABCD-1234-EFGH-5678",
  "instance_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "version": "1.0.0"
}
```

**Erfolgsantwort (HTTP 200):**
```json
{
  "valid": true,
  "code": "OK",
  "message": "Lizenz erfolgreich verifiziert.",
  "customer": "Musterfirma GmbH",
  "validUntil": "2027-12-31",
  "instanceUuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "modules": {
    "core": true,
    "starface": true,
    "server_reports": true,
    "server_report_backups": true,
    "warehouse": true,
    "advanced_documents": true,
    "tickets": true
  },
  "timestamp": 1727260800,
  "signature": "d9f8a3..."
}
```

### Admin API
* `POST /api/admin/login` – Login mit E-Mail, Passwort und optional TOTP-Code (liefert `require_totp_setup` falls Erst-Einrichtung nötig)
* `POST /api/admin/confirm-totp-setup` – Bestätigung des 2FA-Setups mit dem ersten 6-stelligen TOTP-Code
* `POST /api/admin/logout` – Logout
* `GET /api/admin/me` – Sitzungsstatus & angemeldeter Benutzer
* `POST /api/admin/change-credentials` – Passwort ändern oder neues TOTP-Secret anfordern/aktivieren
* `GET /api/admin/licenses` – Liste aller Lizenzen
* `POST /api/admin/licenses` – Neue Lizenz anlegen
* `GET /api/admin/licenses/{id}` – Details einer Lizenz
* `PUT /api/admin/licenses/{id}` – Lizenz bearbeiten (z. B. UUID eintragen)
* `DELETE /api/admin/licenses/{id}` – Lizenz entfernen
* `POST /api/admin/licenses/generate-key` – Frischen Lizenzschlüssel generieren
* `GET /api/admin/stats` – Zähler (Gesamt, Aktiv, Wartet auf UUID, Abgelaufen)
* `GET /api/admin/audit-logs` – Abfrage- und Zugriffsverlauf

---

## 📁 Verzeichnis- & Pfad-Referenz

| Komponente | Pfad | Beschreibung |
| :--- | :--- | :--- |
| **VPS Repository-Wurzel** | `/opt/oxygen-licensing/` | Basisverzeichnis der Anwendung auf dem VPS |
| **Lokale Dev-Kopie** | `c:\Users\ph\dev\dev\oxygen-licensing\` | Lokales Arbeitsverzeichnis auf Windows-Entwicklungsrechner |
| **Git Remote** | `https://github.com/SgtRho/oxygen-licensing.git` | GitHub Upstream (Branch `main`) |
| **Docker Compose** | `/opt/oxygen-licensing/compose.yaml` | Container-Definition für `oxygen-license-server` |
| **Umgebungsvariablen** | `/opt/oxygen-licensing/.env` | Produktions-Konfiguration (Vorlage: `.env.example`) |
| **Dockerfile** | `/opt/oxygen-licensing/Dockerfile` | Python 3.12-slim Container-Spezifikation |
| **Python Requirements** | `/opt/oxygen-licensing/requirements.txt` | Minimaler Stack: FastAPI, Uvicorn, Pydantic, HTTPX |
| **Backend-Kern** | `/opt/oxygen-licensing/app/main.py` | FastAPI Endpunkte (Public Verify API, Admin API & Auth) |
| **Datenbank-Modul** | `/opt/oxygen-licensing/app/db.py` | SQLite Schema & automatischer Abgleich von `.env` |
| **Sicherheits-Modul** | `/opt/oxygen-licensing/app/security.py` | PBKDF2 Password-Hashing, TOTP RFC 6238, HMAC-SHA256 |
| **Pydantic-Modelle** | `/opt/oxygen-licensing/app/models.py` | Request-/Response-Schemas |
| **Web-Template** | `/opt/oxygen-licensing/app/templates/index.html` | HTML5 Dashboard & 2FA-Setup-Maske |
| **Frontend-Controller** | `/opt/oxygen-licensing/app/static/admin.js` | Vanilla JS Controller für Dashboard & 2FA Setup |
| **Stylesheets** | `/opt/oxygen-licensing/app/static/app.css` | UI Theme & Responsive Layout |
| **Offline QR-Code Lib** | `/opt/oxygen-licensing/app/static/qrious.min.js` | Lokale QR-Code Erzeugung ohne externe Drittanbieter-APIs |
| **Persistentes Volume** | `oxygen_license_data` (`/data`) | Docker Named-Volume für langlebige Daten |
| **SQLite-Datenbank** | `/data/licenses.db` | Tabellen: `licenses`, `admin_users`, `audit_logs`, `settings` |
| **Nginx Konfiguration** | `/etc/nginx/sites-available/lizensierung.modernewolke.de` | Reverse-Proxy auf Port 8000 |
| **SSL-Zertifikate** | `/etc/letsencrypt/live/lizensierung.modernewolke.de/` | Let's Encrypt HTTPS-Zertifikate |
