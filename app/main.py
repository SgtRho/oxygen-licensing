import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import get_db
from app.models import (
    AdminMeResponse,
    ChangeCredentialsRequest,
    LicenseCreate,
    LicenseOut,
    LicenseUpdate,
    LoginRequest,
    LoginResponse,
    TotpSetupConfirm,
    VerifyRequest,
    VerifyResponse,
)
from app.security import (
    create_session,
    generate_license_key,
    generate_totp_secret,
    get_otpauth_url,
    get_session_user,
    hash_password,
    invalidate_session,
    sign_license,
    validate_session,
    verify_password,
    verify_totp,
)

logger = logging.getLogger("license_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="Oxygen Online License Server",
    description="Zentraler Lizenzserver für Modernewolke Oxygen Online (SelectLine WebUI)",
    version="1.0.0",
)

# CORS setup
origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_COOKIE_NAME = "oxygen_lic_session"
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


def _require_admin(
    oxygen_lic_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
    authorization: Optional[str] = Header(None),
) -> dict:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif oxygen_lic_session:
        token = oxygen_lic_session.strip()

    session_user = get_session_user(token)
    if not session_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Nicht autorisiert. Bitte als Administrator anmelden."},
        )
    return session_user


def _compute_license_status(row: dict) -> str:
    if not bool(row["is_active"]):
        return "inactive"
    valid_until = row.get("valid_until")
    if valid_until:
        try:
            exp_date = datetime.strptime(str(valid_until).split("T")[0], "%Y-%m-%d").date()
            if datetime.now(timezone.utc).date() > exp_date:
                return "expired"
        except Exception:
            pass
    if not str(row.get("instance_uuid") or "").strip():
        return "unassigned_uuid"
    return "active"


# ============================================================
# Public License Verification Endpoint
# ============================================================

@app.post("/api/v1/license/verify", response_model=VerifyResponse)
async def verify_license(req: VerifyRequest, request: Request):
    """
    Verifies a license for an Oxygen Online instance.
    Checks license key existence, active state, expiration date,
    and strict matching with the registered instance UUID.
    """
    key = req.license_key.strip().upper()
    client_uuid = req.instance_uuid.strip().lower()
    client_ip = _get_client_ip(request)
    now_iso = datetime.now(timezone.utc).isoformat()
    now_ts = int(time.time())

    with get_db() as con:
        row = con.execute(
            "SELECT * FROM licenses WHERE UPPER(license_key) = ?",
            (key,),
        ).fetchone()

        if not row:
            con.execute(
                "INSERT INTO audit_logs (action, license_key, instance_uuid, ip_address, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("VERIFY_FAILED_NOT_FOUND", key, client_uuid, client_ip, "Lizenzschlüssel nicht gefunden", now_iso),
            )
            return VerifyResponse(
                valid=False,
                code="KEY_NOT_FOUND",
                message="Der eingegebene Lizenzschlüssel ist ungültig oder existiert nicht.",
                error="Der eingegebene Lizenzschlüssel ist ungültig oder existiert nicht.",
            )

        row_dict = dict(row)
        customer_name = row_dict["customer_name"]
        reg_uuid = str(row_dict.get("instance_uuid") or "").strip().lower()
        is_active = bool(row_dict["is_active"])
        valid_until = row_dict.get("valid_until")
        modules_json = row_dict.get("modules") or "{}"

        # 1. Active check
        if not is_active:
            con.execute(
                "INSERT INTO audit_logs (action, license_key, instance_uuid, ip_address, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("VERIFY_FAILED_INACTIVE", key, client_uuid, client_ip, f"Lizenz für {customer_name} ist deaktiviert", now_iso),
            )
            return VerifyResponse(
                valid=False,
                code="INACTIVE",
                message="Diese Lizenz wurde deaktiviert.",
                error="Diese Lizenz wurde deaktiviert. Bitte kontaktieren Sie Modernewolke.",
            )

        # 2. Expiration check
        if valid_until:
            try:
                exp_date = datetime.strptime(str(valid_until).split("T")[0], "%Y-%m-%d").date()
                if datetime.now(timezone.utc).date() > exp_date:
                    con.execute(
                        "INSERT INTO audit_logs (action, license_key, instance_uuid, ip_address, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                        ("VERIFY_FAILED_EXPIRED", key, client_uuid, client_ip, f"Lizenz für {customer_name} am {valid_until} abgelaufen", now_iso),
                    )
                    return VerifyResponse(
                        valid=False,
                        code="EXPIRED",
                        message=f"Diese Lizenz ist am {valid_until} abgelaufen.",
                        error=f"Diese Lizenz ist am {valid_until} abgelaufen.",
                    )
            except Exception as exc:
                logger.warning("Error parsing valid_until '%s': %s", valid_until, exc)

        # 3. UUID matching check
        if not reg_uuid:
            con.execute(
                "INSERT INTO audit_logs (action, license_key, instance_uuid, ip_address, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("VERIFY_FAILED_NO_UUID", key, client_uuid, client_ip, f"Im Lizenzserver fehlt die Instanz-UUID für {customer_name}", now_iso),
            )
            return VerifyResponse(
                valid=False,
                code="UUID_NOT_ASSIGNED",
                message="Für diese Lizenz ist im Lizenzserver noch keine Instanz-UUID hinterlegt.",
                error="Für diesen Lizenzschlüssel wurde im Lizenzserver noch keine Instanz-UUID hinterlegt. Bitte tragen Sie die Instanz-UUID im Lizenzserver ein.",
            )

        if reg_uuid != client_uuid:
            con.execute(
                "INSERT INTO audit_logs (action, license_key, instance_uuid, ip_address, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                ("VERIFY_FAILED_UUID_MISMATCH", key, client_uuid, client_ip, f"UUID Mismatch (Erwartet: {reg_uuid}, Erhalten: {client_uuid})", now_iso),
            )
            return VerifyResponse(
                valid=False,
                code="UUID_MISMATCH",
                message="Die Instanz-UUID stimmt nicht mit der im Lizenzserver hinterlegten UUID überein.",
                error="Die übergebene Instanz-UUID stimmt nicht mit der für diesen Lizenzschlüssel hinterlegten UUID überein.",
            )

        # Parse modules
        try:
            modules_dict = json.loads(modules_json)
            if not isinstance(modules_dict, dict):
                modules_dict = {}
        except Exception:
            modules_dict = {}

        # Core is always included
        modules_dict["core"] = True

        # Update last seen info
        con.execute(
            """
            UPDATE licenses
            SET last_check_at = ?, last_check_ip = ?, last_check_version = ?, updated_at = ?
            WHERE id = ?
            """,
            (now_iso, client_ip, req.version or "1.0.0", now_iso, row_dict["id"]),
        )

        con.execute(
            "INSERT INTO audit_logs (action, license_key, instance_uuid, ip_address, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("VERIFY_SUCCESS", key, client_uuid, client_ip, f"Erfolgreich verifiziert für {customer_name}", now_iso),
        )

        # Cryptographic signature
        canonical_modules = json.dumps(modules_dict, sort_keys=True)
        sig = sign_license(key, reg_uuid, customer_name, valid_until, canonical_modules, now_ts)

        return VerifyResponse(
            valid=True,
            code="OK",
            message="Lizenz erfolgreich verifiziert.",
            customer=customer_name,
            validUntil=valid_until,
            instanceUuid=reg_uuid,
            modules=modules_dict,
            timestamp=now_ts,
            signature=sig,
        )


# ============================================================
# Admin Authentication (Email, Password & TOTP 2FA)
# ============================================================

@app.get("/api/admin/auth-status")
async def get_auth_status():
    """
    Public status endpoint returning whether the system is in initial 2FA setup mode
    and which admin email is currently configured.
    """
    with get_db() as con:
        user = con.execute("SELECT email, totp_enabled FROM admin_users ORDER BY id ASC LIMIT 1").fetchone()
        if not user:
            return {"needs_initial_setup": True, "admin_email": "admin@modernewolke.de"}
        needs_setup = int(user["totp_enabled"]) == 0
        return {
            "needs_initial_setup": needs_setup,
            "admin_email": user["email"],
        }


@app.post("/api/admin/login", response_model=LoginResponse)
async def admin_login(payload: LoginRequest, response: Response):
    email = payload.email.strip().lower()
    password = payload.password

    with get_db() as con:
        user = con.execute("SELECT * FROM admin_users WHERE email = ? AND is_active = 1", (email,)).fetchone()

    if not user or not verify_password(password, user["salt"], user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Ungültige E-Mail-Adresse oder Passwort. Bitte prüfen Sie ggf. ADMIN_EMAIL und ADMIN_PASSWORD in der .env-Datei."},
        )

    # If TOTP has not yet been set up/confirmed
    if not bool(user["totp_enabled"]):
        otp_url = get_otpauth_url(user["totp_secret"], user["email"])
        return LoginResponse(
            ok=True,
            require_totp_setup=True,
            totp_secret=user["totp_secret"],
            otpauth_url=otp_url,
            email=user["email"],
            message="Bitte richten Sie die Zwei-Faktor-Authentifizierung (TOTP) ein.",
        )

    # TOTP is enabled: check if code was supplied
    if not payload.totp_code:
        return LoginResponse(
            ok=True,
            require_totp=True,
            email=user["email"],
            message="Bitte geben Sie Ihren 6-stelligen Authenticator-Code ein.",
        )

    # Verify TOTP code
    if not verify_totp(user["totp_secret"], payload.totp_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Der 2FA Authenticator-Code ist ungültig oder abgelaufen."},
        )

    # Successful login: create session
    token = create_session(user["id"], user["email"])
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as con:
        con.execute("UPDATE admin_users SET last_login_at = ? WHERE id = ?", (now_iso, user["id"]))

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # Browser sends cookie over HTTP/HTTPS; in production Nginx sets HTTPS
        max_age=48 * 3600,
    )
    return LoginResponse(ok=True, token=token, email=user["email"], message="Erfolgreich angemeldet.")


@app.post("/api/admin/confirm-totp-setup", response_model=LoginResponse)
async def confirm_totp_setup(payload: TotpSetupConfirm, response: Response):
    email = payload.email.strip().lower()
    with get_db() as con:
        user = con.execute("SELECT * FROM admin_users WHERE email = ? AND is_active = 1", (email,)).fetchone()

    if not user or not verify_password(payload.password, user["salt"], user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"message": "Ungültige Anmeldedaten."},
        )

    if not verify_totp(user["totp_secret"], payload.totp_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Der eingegebene Bestätigungscode ist ungültig. Bitte prüfen Sie die Uhrzeit auf Ihrem Smartphone."},
        )

    now_iso = datetime.now(timezone.utc).isoformat()
    with get_db() as con:
        con.execute(
            "UPDATE admin_users SET totp_enabled = 1, last_login_at = ? WHERE id = ?",
            (now_iso, user["id"]),
        )

    token = create_session(user["id"], user["email"])
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=48 * 3600,
    )
    return LoginResponse(ok=True, token=token, email=user["email"], message="2FA erfolgreich aktiviert und angemeldet.")


@app.post("/api/admin/logout")
async def admin_logout(
    response: Response,
    oxygen_lic_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
):
    invalidate_session(oxygen_lic_session)
    response.delete_cookie(key=SESSION_COOKIE_NAME)
    return {"ok": True, "message": "Erfolgreich abgemeldet."}


@app.get("/api/admin/me", response_model=AdminMeResponse)
async def admin_me(
    oxygen_lic_session: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME),
    authorization: Optional[str] = Header(None),
):
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif oxygen_lic_session:
        token = oxygen_lic_session.strip()

    session_user = get_session_user(token)
    if not session_user:
        return AdminMeResponse(authenticated=False)

    return AdminMeResponse(
        authenticated=True,
        email=session_user["email"],
        totp_enabled=True,
    )


@app.post("/api/admin/change-credentials")
async def change_credentials(
    payload: ChangeCredentialsRequest,
    admin_session: dict = Depends(_require_admin),
):
    user_id = admin_session["user_id"]
    with get_db() as con:
        user = con.execute("SELECT * FROM admin_users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        raise HTTPException(404, detail={"message": "Benutzer nicht gefunden."})

    if not verify_password(payload.current_password, user["salt"], user["password_hash"]):
        raise HTTPException(400, detail={"message": "Das aktuelle Passwort ist nicht korrekt."})

    if not verify_totp(user["totp_secret"], payload.totp_code):
        raise HTTPException(400, detail={"message": "Der TOTP-Code ist ungültig."})

    new_email = payload.new_email.strip().lower() if payload.new_email else user["email"]
    new_hash = user["password_hash"]
    new_salt = user["salt"]

    if payload.new_password:
        if len(payload.new_password) < 8:
            raise HTTPException(400, detail={"message": "Das neue Passwort muss mindestens 8 Zeichen lang sein."})
        new_salt, new_hash = hash_password(payload.new_password)

    with get_db() as con:
        con.execute(
            "UPDATE admin_users SET email = ?, password_hash = ?, salt = ? WHERE id = ?",
            (new_email, new_hash, new_salt, user_id),
        )

    admin_session["email"] = new_email
    return {"ok": True, "message": "Zugangsdaten erfolgreich aktualisiert."}


# ============================================================
# Admin License Management CRUD
# ============================================================

@app.get("/api/admin/licenses", response_model=list[LicenseOut])
def list_licenses(
    q: Optional[str] = None,
    status_filter: Optional[str] = None,
    _auth: dict = Depends(_require_admin),
):
    query = "SELECT * FROM licenses ORDER BY id DESC"
    with get_db() as con:
        rows = con.execute(query).fetchall()

    results = []
    for r in rows:
        d = dict(r)
        st = _compute_license_status(d)
        if status_filter and status_filter != "all" and st != status_filter:
            continue

        try:
            mods = json.loads(d["modules"]) if d.get("modules") else {}
        except Exception:
            mods = {}

        if q:
            term = q.strip().lower()
            in_cust = term in d["customer_name"].lower()
            in_key = term in d["license_key"].lower()
            in_uuid = term in (d.get("instance_uuid") or "").lower()
            in_notes = term in (d.get("notes") or "").lower()
            if not (in_cust or in_key or in_uuid or in_notes):
                continue

        results.append(
            LicenseOut(
                id=d["id"],
                license_key=d["license_key"],
                customer_name=d["customer_name"],
                instance_uuid=d.get("instance_uuid") or "",
                is_active=bool(d["is_active"]),
                valid_until=d.get("valid_until"),
                modules=mods,
                notes=d.get("notes") or "",
                created_at=d["created_at"],
                updated_at=d["updated_at"],
                last_check_at=d.get("last_check_at"),
                last_check_ip=d.get("last_check_ip"),
                last_check_version=d.get("last_check_version"),
                status=st,
            )
        )
    return results


@app.post("/api/admin/licenses", response_model=LicenseOut)
def create_license(
    payload: LicenseCreate,
    _auth: dict = Depends(_require_admin),
):
    customer = payload.customer_name.strip()
    if not customer:
        raise HTTPException(400, detail={"message": "Kundenname darf nicht leer sein."})

    key = payload.license_key.strip().upper() if payload.license_key else generate_license_key()
    uuid_val = payload.instance_uuid.strip().lower() if payload.instance_uuid else ""
    valid_until = payload.valid_until.strip() if payload.valid_until else None
    notes = payload.notes.strip() if payload.notes else ""
    now_iso = datetime.now(timezone.utc).isoformat()
    modules_json = json.dumps(payload.modules or {}, ensure_ascii=False)

    with get_db() as con:
        exists = con.execute("SELECT id FROM licenses WHERE UPPER(license_key) = ?", (key,)).fetchone()
        if exists:
            raise HTTPException(400, detail={"message": f"Ein Lizenzschlüssel '{key}' existiert bereits."})

        cur = con.execute(
            """
            INSERT INTO licenses (
                license_key, customer_name, instance_uuid, is_active,
                valid_until, modules, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (key, customer, uuid_val, 1 if payload.is_active else 0, valid_until, modules_json, notes, now_iso, now_iso),
        )
        new_id = cur.lastrowid
        con.execute(
            "INSERT INTO audit_logs (action, license_key, instance_uuid, ip_address, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("LICENSE_CREATED", key, uuid_val, _auth["email"], f"Lizenz für {customer} erstellt", now_iso),
        )
        row = con.execute("SELECT * FROM licenses WHERE id = ?", (new_id,)).fetchone()

    d = dict(row)
    return LicenseOut(
        id=d["id"],
        license_key=d["license_key"],
        customer_name=d["customer_name"],
        instance_uuid=d.get("instance_uuid") or "",
        is_active=bool(d["is_active"]),
        valid_until=d.get("valid_until"),
        modules=json.loads(d["modules"]) if d.get("modules") else {},
        notes=d.get("notes") or "",
        created_at=d["created_at"],
        updated_at=d["updated_at"],
        last_check_at=d.get("last_check_at"),
        last_check_ip=d.get("last_check_ip"),
        last_check_version=d.get("last_check_version"),
        status=_compute_license_status(d),
    )


@app.get("/api/admin/licenses/{license_id}", response_model=LicenseOut)
def get_license(license_id: int, _auth: dict = Depends(_require_admin)):
    with get_db() as con:
        row = con.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
    if not row:
        raise HTTPException(404, detail={"message": "Lizenz nicht gefunden."})
    d = dict(row)
    return LicenseOut(
        id=d["id"],
        license_key=d["license_key"],
        customer_name=d["customer_name"],
        instance_uuid=d.get("instance_uuid") or "",
        is_active=bool(d["is_active"]),
        valid_until=d.get("valid_until"),
        modules=json.loads(d["modules"]) if d.get("modules") else {},
        notes=d.get("notes") or "",
        created_at=d["created_at"],
        updated_at=d["updated_at"],
        last_check_at=d.get("last_check_at"),
        last_check_ip=d.get("last_check_ip"),
        last_check_version=d.get("last_check_version"),
        status=_compute_license_status(d),
    )


@app.put("/api/admin/licenses/{license_id}", response_model=LicenseOut)
def update_license(
    license_id: int,
    payload: LicenseUpdate,
    _auth: dict = Depends(_require_admin),
):
    with get_db() as con:
        row = con.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
        if not row:
            raise HTTPException(404, detail={"message": "Lizenz nicht gefunden."})

        curr = dict(row)
        customer = payload.customer_name.strip() if payload.customer_name is not None else curr["customer_name"]
        uuid_val = payload.instance_uuid.strip().lower() if payload.instance_uuid is not None else (curr.get("instance_uuid") or "")
        valid_until = payload.valid_until.strip() if payload.valid_until is not None else curr.get("valid_until")
        if valid_until == "":
            valid_until = None
        notes = payload.notes.strip() if payload.notes is not None else (curr.get("notes") or "")
        is_active = payload.is_active if payload.is_active is not None else bool(curr["is_active"])

        if payload.modules is not None:
            modules_json = json.dumps(payload.modules, ensure_ascii=False)
        else:
            modules_json = curr.get("modules") or "{}"

        now_iso = datetime.now(timezone.utc).isoformat()
        con.execute(
            """
            UPDATE licenses
            SET customer_name = ?, instance_uuid = ?, valid_until = ?,
                modules = ?, notes = ?, is_active = ?, updated_at = ?
            WHERE id = ?
            """,
            (customer, uuid_val, valid_until, modules_json, notes, 1 if is_active else 0, now_iso, license_id),
        )
        con.execute(
            "INSERT INTO audit_logs (action, license_key, instance_uuid, ip_address, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("LICENSE_UPDATED", curr["license_key"], uuid_val, _auth["email"], f"Lizenz für {customer} aktualisiert (UUID: {uuid_val})", now_iso),
        )
        updated = con.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()

    d = dict(updated)
    return LicenseOut(
        id=d["id"],
        license_key=d["license_key"],
        customer_name=d["customer_name"],
        instance_uuid=d.get("instance_uuid") or "",
        is_active=bool(d["is_active"]),
        valid_until=d.get("valid_until"),
        modules=json.loads(d["modules"]) if d.get("modules") else {},
        notes=d.get("notes") or "",
        created_at=d["created_at"],
        updated_at=d["updated_at"],
        last_check_at=d.get("last_check_at"),
        last_check_ip=d.get("last_check_ip"),
        last_check_version=d.get("last_check_version"),
        status=_compute_license_status(d),
    )


@app.delete("/api/admin/licenses/{license_id}")
def delete_license(license_id: int, _auth: dict = Depends(_require_admin)):
    with get_db() as con:
        row = con.execute("SELECT * FROM licenses WHERE id = ?", (license_id,)).fetchone()
        if not row:
            raise HTTPException(404, detail={"message": "Lizenz nicht gefunden."})
        key = row["license_key"]
        customer = row["customer_name"]
        now_iso = datetime.now(timezone.utc).isoformat()
        con.execute("DELETE FROM licenses WHERE id = ?", (license_id,))
        con.execute(
            "INSERT INTO audit_logs (action, license_key, instance_uuid, ip_address, details, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("LICENSE_DELETED", key, "", _auth["email"], f"Lizenz von {customer} ({key}) gelöscht", now_iso),
        )
    return {"ok": True, "message": f"Lizenz '{key}' wurde gelöscht."}


@app.post("/api/admin/licenses/generate-key")
def generate_key_endpoint(_auth: dict = Depends(_require_admin)):
    return {"license_key": generate_license_key()}


@app.get("/api/admin/stats")
def get_stats(_auth: dict = Depends(_require_admin)):
    with get_db() as con:
        rows = con.execute("SELECT * FROM licenses").fetchall()

    total = len(rows)
    active = 0
    expired = 0
    unassigned = 0
    inactive = 0

    for r in rows:
        st = _compute_license_status(dict(r))
        if st == "active":
            active += 1
        elif st == "expired":
            expired += 1
        elif st == "unassigned_uuid":
            unassigned += 1
        elif st == "inactive":
            inactive += 1

    return {
        "total": total,
        "active": active,
        "expired": expired,
        "unassignedUuid": unassigned,
        "inactive": inactive,
    }


@app.get("/api/admin/audit-logs")
def get_audit_logs(limit: int = 50, _auth: dict = Depends(_require_admin)):
    with get_db() as con:
        rows = con.execute(
            "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# Health & Static UI
# ============================================================

@app.get("/api/health")
def healthcheck():
    return {"status": "ok", "service": "oxygen-license-server", "version": "1.0.0"}


@app.get("/", response_class=HTMLResponse)
@app.get("/admin", response_class=HTMLResponse)
def serve_admin_page():
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        return HTMLResponse("<h1>Oxygen License Server</h1><p>UI-Dateien fehlen in templates/index.html.</p>")
    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
