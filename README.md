# 🔑 Modernewolke Oxygen Online License Server

Zentraler, leichtgewichtiger Lizenzserver zur Verwaltung und kryptografischen Verifizierung von Lizenzen und Modulen für **Oxygen Online (SelectLine WebUI)**.

Erreichbar unter: `https://lizensierung.modernewolke.de`

---

## 🎯 Architektur & Lizenz-Workflow

Das Lizenzmodell basiert auf einer **strikt hardware- und instanzgebundenen Paarung**:

```
+------------------------------------+           +-----------------------------------------+
|    Oxygen Online Instanz           |           |  Modernewolke Lizenzserver             |
|   (Kunde / On-Premise / Cloud)     |           |  (lizensierung.modernewolke.de)         |
+------------------------------------+           +-----------------------------------------+
|                                    |           |                                         |
| 1. Generiert einmalige UUID        |           | 2. Lizenz wird angelegt                 |
|    beim ersten Start               |           |    - Lizenzschlüssel: OXY-XXXX-XXXX...  |
|    (z.B. in /data/oxygen-inst-id)  |           |    - Kunde: z.B. Musterfirma GmbH       |
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

## 🚀 Schnelle Inbetriebnahme (Docker Compose)

### 1. Repository klonen & Verzeichnis betreten
```bash
cd c:\Users\ph\dev\dev\oxygen-license-server
```

### 2. Konfiguration anlegen (`.env`)
Erstellen Sie eine `.env`-Datei basierend auf `.env.example`:
```bash
cp .env.example .env
```

Wichtige Parameter:
```env
PORT=8000
DATA_DIR=/data
ADMIN_PASSWORD=IhrGeheimesMasterPasswort123!
SIGNING_SECRET=EinLangerZufaelligerGeheimerSchluesselFuerHMACSignatur
CORS_ORIGINS=*
```

### 3. Container starten
```bash
docker compose up -d --build
```

Der Server ist anschließend unter `http://localhost:8000` erreichbar.

---

## 🌐 Bereitstellung unter `lizensierung.modernewolke.de`

### Nginx Reverse-Proxy Beispiel
```nginx
server {
    listen 80;
    server_name lizensierung.modernewolke.de;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name lizensierung.modernewolke.de;

    ssl_certificate /etc/letsencrypt/live/lizensierung.modernewolke.de/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/lizensierung.modernewolke.de/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 🖥️ Web-Verwaltungsoberfläche

Nach dem Aufruf von `https://lizensierung.modernewolke.de/` erscheint das Login-Formular:
- **Master-Passwort:** Das in `ADMIN_PASSWORD` konfigurierte Kennwort eingeben.

### Funktionen im Dashboard:
- **Übersicht & KPI-Cards:** Gesamtanzahl, Aktive Lizenzen, Wartet auf UUID, Abgelaufene Lizenzen.
- **Schnellsuche & Filter:** Sofortige Filterung nach Kundenname, Schlüssel oder UUID.
- **1-Klick-UUID-Zuweisung:** Wenn eine Lizenz noch keine UUID hat, genügt ein Klick auf `⚠️ UUID eintragen`, um die UUID aus der Kundeninstanz einzufügen.
- **Lizenzschlüssel-Generator:** Automatische Erzeugung sicherer Schlüssel im Format `OXY-XXXX-XXXX-XXXX-XXXX`.
- **Modul-Checkboxen:** Gezieltes Aktivieren/Deaktivieren einzelner Module:
  - `starface` (STARFACE Telefonie & UCI)
  - `server_reports` (Serverberichte & Sensoren)
  - `server_report_backups` (Datensicherungs-Überwachung)
  - `warehouse` (Lager & Bestände)
  - `advanced_documents` (Erweiterte Belege & Folgebelege)
  - `tickets` (Helpdesk & Servicetickets)
- **Gültigkeitsdauer:** Befristet auf ein Datum oder unbegrenzt gültig.
- **Audit-Log:** Vollständiges Protokoll aller Abrufe, erfolgreichen Verifizierungen und Fehlversuche.

---

## 📡 REST-API Dokumentation

### 1. Lizenz verifizieren (Public Endpoint für Oxygen-Instanzen)
`POST /api/v1/license/verify`

**Request Body:**
```json
{
  "license_key": "OXY-ABCD-1234-EFGH-5678",
  "instance_uuid": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "version": "1.0.0"
}
```

**Erfolgreiche Antwort (HTTP 200):**
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

**Fehlerantwort (z.B. UUID-Fehler):**
```json
{
  "valid": false,
  "code": "UUID_MISMATCH",
  "message": "Die Instanz-UUID stimmt nicht mit der im Lizenzserver hinterlegten UUID überein.",
  "error": "Die übergebene Instanz-UUID stimmt nicht mit der für diesen Lizenzschlüssel hinterlegten UUID überein."
}
```

### 2. Admin API
- `POST /api/admin/login` – Authentifizierung via Passwort
- `POST /api/admin/logout` – Sitzung beenden
- `GET /api/admin/me` – Status der aktuellen Admin-Sitzung
- `GET /api/admin/licenses` – Liste aller Lizenzen (`?q=...&status_filter=...`)
- `POST /api/admin/licenses` – Neue Lizenz anlegen
- `GET /api/admin/licenses/{id}` – Details einer Lizenz
- `PUT /api/admin/licenses/{id}` – Lizenz bearbeiten (z.B. UUID eintragen)
- `DELETE /api/admin/licenses/{id}` – Lizenz löschen
- `POST /api/admin/licenses/generate-key` – Frischen Lizenzschlüssel generieren
- `GET /api/admin/stats` – Statistiken für das Dashboard
- `GET /api/admin/audit-logs` – Abruf-Historie

---

## 🗄️ Datenhaltung & Persistenz
- Die SQLite-Datenbank liegt persistent unter `/data/licenses.db`.
- WAL-Modus (`Write-Ahead Logging`) und Timeout-Sicherungen sind standardmäßig aktiviert.
- Bei Docker-Betrieb wird das Volume `oxygen_license_data` verwendet, sodass Rebuilds und Updates die Daten nicht beeinträchtigen.
