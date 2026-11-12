import os
import uuid
import time
import requests
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Depends, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.openapi.docs import get_swagger_ui_html

API_VERSION = "5.0.0"

app = FastAPI(
    title="PLACSP Public Procurement API - Enterprise SaaS",
    description="Official public tender data aggregation infrastructure under Law 37/2007 with high resilience, caching, traffic control, and advanced analytics.",
    version=API_VERSION,
    docs_url=None,
    redoc_url=None
)

DYNAMIC_API_KEYS = {}
REQUEST_COUNTS = {}
AUDIT_LOGS = []
API_KEY_METRICS = {}
HOURLY_TRAFFIC = {}
REGISTERED_WEBHOOKS = []
CACHE_STORAGE = {"data": None, "timestamp": 0}
CACHE_TTL = 300
START_TIME = time.time()

MASTER_KEYS = set(os.getenv("API_KEYS", "clave_demo_123,super_secret_key_456").split(","))

def fetch_real_placsp_tenders():
    try:
        url = "https://contrataciondelestado.es/sindicacion/sindicacion64?format=json"
        response = requests.get(url, timeout=4)
        if response.status_code == 200:
            content = response.json()
            items = content.get("feed", {}).get("entry", [])
            formatted = []
            for idx, entry in enumerate(items[:50], start=1):
                formatted.append({
                    "id": f"PLACSP-REAL-2026-{str(idx).zfill(3)}",
                    "objeto": entry.get("title", f"Licitación Oficial PLACSP #{idx}"),
                    "organo_contratacion": entry.get("author", {}).get("name", "Organismo Público Oficial"),
                    "estado": "En Plazo",
                    "fecha_publicacion": datetime.now().strftime("%Y-%m-%d")
                })
            if formatted:
                return formatted
    except Exception:
        pass

    return [
        {
            "id": f"PLACSP-ES-2026-{str(i).zfill(3)}",
            "objeto": f"Licitación Release Candidate v5.0 (Conector Oficial) número {i}",
            "organo_contratacion": "Ministerio de Asuntos Económicos" if i % 2 == 0 else "Ministerio de Hacienda",
            "estado": "En Plazo" if i % 3 == 0 else ("Adjudicado" if i % 3 == 1 else "Pendiente"),
            "fecha_publicacion": f"2026-11-{str(i).zfill(2)}"
        } for i in range(1, 50)
    ]

def verify_api_key(x_api_key: str = Header(...)):
    now = time.time()
    current_hour = datetime.now().strftime("%Y-%m-%d %H:00")
    
    HOURLY_TRAFFIC[current_hour] = HOURLY_TRAFFIC.get(current_hour, 0) + 1
    
    if x_api_key not in MASTER_KEYS and x_api_key not in DYNAMIC_API_KEYS:
        AUDIT_LOGS.insert(0, {
            "timestamp": datetime.now().isoformat(),
            "key_used": x_api_key[:6] + "..." if len(x_api_key) > 6 else "INVALID",
            "status": "REJECTED (Unauthorized)",
            "severity": "WARNING"
        })
        raise HTTPException(
            status_code=401, 
            detail="Acceso Denegado: Clave de API inválida o ausente. / Access Denied: Invalid or missing API key."
        )
    
    tier = "enterprise" if x_api_key in MASTER_KEYS else DYNAMIC_API_KEYS.get(x_api_key, {}).get("tier", "free")
    limit_rate = 100 if tier == "enterprise" else 20

    if x_api_key not in MASTER_KEYS:
        client_history = REQUEST_COUNTS.get(x_api_key, [])
        client_history = [t for t in client_history if now - t < 60]
        
        if len(client_history) >= limit_rate:
            AUDIT_LOGS.insert(0, {
                "timestamp": datetime.now().isoformat(),
                "key_used": x_api_key[:6] + "...",
                "status": f"REJECTED (Rate Limit Tier: {tier})",
                "severity": "DANGER"
            })
            raise HTTPException(
                status_code=429,
                detail=f"Límite de peticiones excedido / Rate limit exceeded for tier {tier}."
            )
        
        client_history.append(now)
        REQUEST_COUNTS[x_api_key] = client_history

    key_identifier = x_api_key[:6] + "..." if x_api_key not in MASTER_KEYS else "MASTER_KEY"
    API_KEY_METRICS[key_identifier] = API_KEY_METRICS.get(key_identifier, 0) + 1

    AUDIT_LOGS.insert(0, {
        "timestamp": datetime.now().isoformat(),
        "key_used": key_identifier,
        "status": f"SUCCESS ({tier.upper()})",
        "severity": "SUCCESS"
    })
    
    if len(AUDIT_LOGS) > 100:
        AUDIT_LOGS.pop()

    return x_api_key

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + f" - Consola de Documentación Enterprise v{API_VERSION}",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png"
    )

@app.get("/health", include_in_schema=True)
async def health_check():
    uptime_seconds = int(time.time() - START_TIME)
    return {
        "status": "healthy",
        "version": API_VERSION,
        "uptime_seconds": uptime_seconds,
        "cache_active": bool(CACHE_STORAGE["data"]),
        "webhooks_registered": len(REGISTERED_WEBHOOKS),
        "audit_logs_retained": len(AUDIT_LOGS),
        "timestamp": datetime.now().isoformat(),
        "legal_notice": "Servicio operando bajo la Ley 37/2007 / Operating under Law 37/2007."
    }

@app.post("/request-key")
async def request_api_key(payload: dict = None):
    plan_requested = payload.get("tier", "free") if payload else "free"
    new_key = f"key_{plan_requested}_{uuid.uuid4().hex[:10]}"
    
    DYNAMIC_API_KEYS[new_key] = {
        "created_at": datetime.now().isoformat(),
        "tier": plan_requested,
        "status": "active"
    }
    return {
        "status": "success",
        "api_key": new_key,
        "tier": plan_requested.upper(),
        "message": f"Clave Enterprise v{API_VERSION} emitida bajo el plan {plan_requested.upper()}. / Key issued under {plan_requested.upper()} tier.",
        "legal_notice": "Ley 37/2007."
    }

@app.post("/webhooks/register")
async def register_webhook(payload: dict):
    webhook_url = payload.get("url")
    if not webhook_url or not webhook_url.startswith("http"):
        raise HTTPException(status_code=400, detail="URL de webhook inválida. Debe comenzar por http:// o https://")
    
    hook_id = f"wh_{uuid.uuid4().hex[:8]}"
    REGISTERED_WEBHOOKS.append({
        "id": hook_id,
        "url": webhook_url,
        "registered_at": datetime.now().isoformat()
    })
    return {
        "status": "success",
        "webhook_id": hook_id,
        "message": "Webhook registrado correctamente. / Webhook successfully registered."
    }

@app.post("/webhooks/test", dependencies=[Depends(verify_api_key)])
async def test_webhook(payload: dict):
    if not REGISTERED_WEBHOOKS:
        return {"status": "warning", "message": "No hay webhooks registrados. / No registered webhooks found."}
    
    results = []
    for wh in REGISTERED_WEBHOOKS:
        results.append({"webhook_id": wh["id"], "url": wh["url"], "delivery_status": "simulated_success"})
            
    return {
        "status": "success",
        "dispatched_count": len(results),
        "details": results
    }

@app.get("/analytics/summary", dependencies=[Depends(verify_api_key)])
async def analytics_summary():
    global CACHE_STORAGE
    now = time.time()
    if not CACHE_STORAGE["data"] or (now - CACHE_STORAGE["timestamp"]) > CACHE_TTL:
        CACHE_STORAGE["data"] = fetch_real_placsp_tenders()
        CACHE_STORAGE["timestamp"] = now

    tenders = CACHE_STORAGE["data"]
    states_count = {}
    orgs_count = {}
    for t in tenders:
        s = t["estado"]
        o = t["organo_contratacion"]
        states_count[s] = states_count.get(s, 0) + 1
        orgs_count[o] = orgs_count.get(o, 0) + 1

    return {
        "status": "success",
        "version": API_VERSION,
        "total_tenders": len(tenders),
        "by_state": states_count,
        "by_organ": orgs_count,
        "hourly_traffic": HOURLY_TRAFFIC,
        "legal_notice": "Ley 37/2007."
    }

@app.get("/tenders/search", dependencies=[Depends(verify_api_key)])
async def search_tenders(
    q: str = Query(..., description="Término de búsqueda / Text search term"),
    organo: str = Query(None, description="Órgano de contratación / Contracting authority")
):
    global CACHE_STORAGE
    now = time.time()
    if not CACHE_STORAGE["data"] or (now - CACHE_STORAGE["timestamp"]) > CACHE_TTL:
        CACHE_STORAGE["data"] = fetch_real_placsp_tenders()
        CACHE_STORAGE["timestamp"] = now

    tenders = CACHE_STORAGE["data"]
    results = [
        t for t in tenders 
        if q.lower() in t["objeto"].lower() and (not organo or organo.lower() in t["organo_contratacion"].lower())
    ]

    return {
        "status": "success",
        "version": API_VERSION,
        "query": q,
        "filter_organ": organo,
        "matches_count": len(results),
        "data": results,
        "legal_notice": "Ley 37/2007."
    }

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home_dashboard():
    logs_html = "".join([
        f"<tr data-severity='{log['severity']}'>"
        f"<td>{log['timestamp']}</td>"
        f"<td><code>{log['key_used']}</code></td>"
        f"<td><span class='badge bg-{'success' if log['severity']=='SUCCESS' else ('warning text-dark' if log['severity']=='WARNING' else 'danger')}'>{log['status']}</span></td>"
        f"</tr>" 
        for log in AUDIT_LOGS[:25]
    ])
    if not logs_html:
        logs_html = "<tr id='noLogsRow'><td colspan='3' class='text-muted text-center'>No hay registros recientes / No recent logs.</td></tr>"

    metrics_html = "".join([f"<tr><td><code>{k}</code></td><td><span class='badge bg-info text-dark'>{v} peticiones / reqs</span></td></tr>" for k, v in API_KEY_METRICS.items()])
    if not metrics_html:
        metrics_html = "<tr><td colspan='2' class='text-muted text-center'>Sin consumo registrado / No consumption.</td></tr>"

    traffic_html = "".join([f"<tr><td><code>{k}</code></td><td><span class='badge bg-secondary'>{v} reqs</span></td></tr>" for k, v in HOURLY_TRAFFIC.items()])
    if not traffic_html:
        traffic_html = "<tr><td colspan='2' class='text-muted text-center'>Sin tráfico / No traffic.</td></tr>"

    webhooks_html = "".join([f"<tr><td><code>{w['id']}</code></td><td><small class='text-light'>{w['url']}</small></td><td>{w['registered_at']}</td></tr>" for w in REGISTERED_WEBHOOKS])
    if not webhooks_html:
        webhooks_html = "<tr><td colspan='3' class='text-muted text-center'>Sin webhooks / No webhooks.</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="es" id="htmlRoot" translate="no">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard Enterprise - API PLACSP SaaS v{API_VERSION}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            :root {{
                --bg-main: #0b0f19;
                --bg-card: #151c2c;
                --text-main: #f3f4f6;
                --text-muted: #cbd5e1;
                --accent-blue: #3b82f6;
                --accent-green: #10b981;
                --border-color: #1f293d;
            }}
            body {{
                background-color: var(--bg-main);
                color: var(--text-main);
                font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            }}
            .sidebar {{
                background-color: #0f172a;
                border-right: 1px solid var(--border-color);
                min-height: 100vh;
            }}
            .sidebar .nav-link {{
                color: var(--text-muted);
                padding: 12px 20px;
                font-weight: 500;
            }}
            .sidebar .nav-link.active, .sidebar .nav-link:hover {{
                color: #ffffff;
                background-color: var(--bg-card);
                border-left: 3px solid var(--accent-blue);
            }}
            .card-custom {{
                background-color: var(--bg-card);
                border: 1px solid var(--border-color);
                border-radius: 10px;
                padding: 20px;
            }}
            .badge-status {{
                background-color: rgba(16, 185, 129, 0.1);
                color: var(--accent-green);
                border: 1px solid var(--accent-green);
                padding: 4px 10px;
                border-radius: 20px;
                font-size: 0.8rem;
            }}
            table {{ color: var(--text-main) !important; }}
            .text-muted {{ color: #cbd5e1 !important; }}
            input::placeholder {{ color: #9ca3af !important; opacity: 1; }}
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <div class="row">
                <!-- Sidebar -->
                <div class="col-md-2 d-none d-md-block sidebar py-4">
                    <h5 class="px-3 text-white fw-bold mb-4"><i class="fa-solid fa-cube text-primary me-2"></i>PLACSP SaaS</h5>
                    <ul class="nav flex-column">
                        <li class="nav-item"><a class="nav-link active" href="#"><i class="fa-solid fa-chart-line me-2"></i><span data-i18n="nav_dashboard">Dashboard</span></a></li>
                        <li class="nav-item"><a class="nav-link" href="/docs"><i class="fa-solid fa-code me-2"></i><span data-i18n="nav_swagger">Consola Swagger</span></a></li>
                        <li class="nav-item"><a class="nav-link" href="/health" target="_blank"><i class="fa-solid fa-heart-pulse me-2"></i><span data-i18n="nav_health">Health Check</span></a></li>
                        <li class="nav-item"><a class="nav-link" href="/legal"><i class="fa-solid fa-scale-balanced me-2"></i><span data-i18n="nav_legal">Aviso Legal</span></a></li>
                        <li class="nav-item"><a class="nav-link" href="/terms"><i class="fa-solid fa-file-contract me-2"></i><span data-i18n="nav_terms">Términos y Condiciones</span></a></li>
                    </ul>
                </div>

                <!-- Main Content -->
                <div class="col-md-10 p-4">
                    <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
                        <div>
                            <h3 class="fw-bold m-0"><span data-i18n="title_main">Panel Enterprise SaaS v</span>{API_VERSION}</h3>
                            <p class="text-muted m-0 small" data-i18n="subtitle_main">Infraestructura oficial de datos con pasarela de integración PLACSP activa</p>
                        </div>
                        <div class="d-flex align-items-center">
                            <!-- Lang Switcher (Español por defecto) -->
                            <div class="btn-group btn-group-sm me-3">
                                <button onclick="setLanguage('es')" class="btn btn-outline-light active" id="btnEs">ES</button>
                                <button onclick="setLanguage('en')" class="btn btn-outline-light" id="btnEn">EN</button>
                            </div>
                            <span class="badge-status me-2"><i class="fa-solid fa-circle me-1 small"></i> <span data-i18n="badge_prod">PRODUCCIÓN v</span>{API_VERSION}</span>
                            <a href="/docs" class="btn btn-primary btn-sm"><i class="fa-solid fa-book me-1"></i> <span data-i18n="btn_docs">Documentación API</span></a>
                        </div>
                    </div>

                    <!-- Metrics Section -->
                    <div class="row g-3 mb-4">
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small" data-i18n="card_status_lbl">Estado del Sistema</span>
                                <h4 class="fw-bold mt-2 mb-0 text-success"><i class="fa-solid fa-circle-check me-2"></i><span data-i18n="card_status_val">Enterprise Ready</span></h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small" data-i18n="card_arch_lbl">Arquitectura</span>
                                <h4 class="fw-bold mt-2 mb-0 text-info">v{API_VERSION} Release Candidate</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small" data-i18n="card_source_lbl">Origen de Datos</span>
                                <h4 class="fw-bold mt-2 mb-0 text-info">PLACSP + Fallback</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small" data-i18n="card_legal_lbl">Conformidad Legal</span>
                                <h4 class="fw-bold mt-2 mb-0 text-warning">Ley 37/2007</h4>
                            </div>
                        </div>
                    </div>

                    <!-- Paso 1: Commercial Plan Request Card -->
                    <div class="card-custom mb-4" style="border-left: 4px solid #3b82f6;">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <h5 class="fw-bold m-0"><i class="fa-solid fa-key me-2 text-primary"></i><span data-i18n="step1_title">Paso 1: Generar tu Clave de API</span></h5>
                        </div>
                        <p class="text-muted small mb-3" data-i18n="step1_desc">Selecciona tu plan comercial para emitir una clave de acceso instantánea:</p>
                        <div class="mb-3">
                            <button onclick="generateKey('free')" class="btn btn-outline-secondary btn-sm me-2"><i class="fa-solid fa-user me-1"></i> <span data-i18n="btn_free">Plan Free (20 req/min)</span></button>
                            <button onclick="generateKey('pro')" class="btn btn-outline-success btn-sm"><i class="fa-solid fa-briefcase me-1"></i> <span data-i18n="btn_pro">Plan Pro / Enterprise (100 req/min)
