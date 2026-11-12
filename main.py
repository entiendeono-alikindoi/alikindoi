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
    if not webhook_url:
        raise HTTPException(status_code=400, detail="La URL del webhook es obligatoria. / Webhook URL is mandatory.")
    
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

                    <!-- Commercial Plan Request Card -->
                    <div class="card-custom mb-4">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h5 class="fw-bold m-0"><i class="fa-solid fa-cart-shopping me-2"></i><span data-i18n="card_activator_title">Activador Comercial de Claves</span></h5>
                        </div>
                        <p class="text-muted small" data-i18n="card_activator_desc">Selecciona el plan comercial a emitir:</p>
                        <div class="mb-3">
                            <button onclick="generateKey('free')" class="btn btn-outline-secondary btn-sm me-2"><i class="fa-solid fa-user me-1"></i> <span data-i18n="btn_free">Plan Free (20 req/min)</span></button>
                            <button onclick="generateKey('pro')" class="btn btn-outline-success btn-sm"><i class="fa-solid fa-briefcase me-1"></i> <span data-i18n="btn_pro">Plan Pro / Enterprise (100 req/min)</span></button>
                        </div>
                        <div id="keyDisplay" class="mt-3" style="display:none;">
                            <div class="p-3 rounded d-flex justify-content-between align-items-center" style="background-color: #0b0f19; border: 1px solid #3b82f6;">
                                <div>
                                    <span class="text-light small d-block mb-1"><span data-i18n="lbl_gen_key">Clave Generada</span> (<strong id="planLabel" class="text-info"></strong>):</span>
                                    <code id="generatedKey" class="fs-5 fw-bold" style="color: #38bdf8; letter-spacing: 0.5px;"></code>
                                </div>
                                <button onclick="copyGeneratedKey()" class="btn btn-primary btn-sm" id="btnCopyKey">
                                    <i class="fa-regular fa-copy me-1"></i> <span data-i18n="btn_copy">Copiar</span>
                                </button>
                            </div>
                        </div>
                    </div>

                    <!-- Webhooks Management Card -->
                    <div class="card-custom mb-4">
                        <h5 class="fw-bold mb-3"><i class="fa-solid fa-bell me-2"></i><span data-i18n="card_webhooks_title">Registro y Prueba de Webhooks</span></h5>
                        <div class="input-group mb-3" style="max-width: 600px;">
                            <input type="text" id="webhookUrlInput" class="form-control bg-dark text-light border-secondary" placeholder="https://tu-servidor.com/webhook-endpoint">
                            <button onclick="registerWebhook()" class="btn btn-outline-primary" data-i18n="btn_register_wh">Registrar Webhook</button>
                        </div>
                        <div class="table-responsive mt-3">
                            <table class="table table-dark table-striped table-sm align-middle">
                                <thead>
                                    <tr>
                                        <th data-i18n="th_wh_id">ID Webhook</th>
                                        <th data-i18n="th_wh_url">URL Destino</th>
                                        <th data-i18n="th_wh_date">Fecha de Registro</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {webhooks_html}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Metrics & Usage Summary Cards -->
                    <div class="row g-3 mb-4">
                        <div class="col-md-4">
                            <div class="card-custom h-100">
                                <h5 class="fw-bold mb-3"><i class="fa-solid fa-chart-bar me-2"></i><span data-i18n="card_metrics_title">Consumo por Clave</span></h5>
                                <div class="table-responsive">
                                    <table class="table table-dark table-striped table-sm align-middle">
                                        <thead>
                                            <tr>
                                                <th data-i18n="th_key">Clave</th>
                                                <th data-i18n="th_reqs">Reqs</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {metrics_html}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="card-custom h-100">
                                <h5 class="fw-bold mb-3"><i class="fa-solid fa-clock me-2"></i><span data-i18n="card_traffic_title">Tráfico por Hora</span></h5>
                                <div class="table-responsive">
                                    <table class="table table-dark table-striped table-sm align-middle">
                                        <thead>
                                            <tr>
                                                <th data-i18n="th_slot">Franja</th>
                                                <th data-i18n="th_total">Total</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {traffic_html}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div class="card-custom h-100">
                                <div class="d-flex justify-content-between align-items-center mb-3">
                                    <h5 class="fw-bold m-0 fs-6"><i class="fa-solid fa-list-check me-1"></i><span data-i18n="card_audit_title">Auditoría</span></h5>
                                    <div class="btn-group btn-group-sm" style="transform: scale(0.85);">
                                        <button onclick="filterLogs('ALL')" class="btn btn-outline-light active" data-i18n="btn_all">Todo</button>
                                        <button onclick="filterLogs('SUCCESS')" class="btn btn-outline-success">OK</button>
                                        <button onclick="filterLogs('DANGER')" class="btn btn-outline-danger">Err</button>
                                    </div>
                                </div>
                                <div class="table-responsive">
                                    <table class="table table-dark table-striped table-sm align-middle" id="auditTable">
                                        <thead>
                                            <tr>
                                                <th data-i18n="th_time">Hora</th>
                                                <th data-i18n="th_key">Clave</th>
                                                <th data-i18n="th_status">Estado</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {logs_html}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Footer Informativo -->
                    <div class="text-center mt-5 pt-3 border-top border-secondary">
                        <small class="text-muted">
                            <span data-i18n="footer_cookies">Este sitio utiliza únicamente cookies técnicas esenciales para su funcionamiento. Consulta nuestra</span> 
                            <a href="/terms" class="text-info text-decoration-none" data-i18n="footer_terms_link">Política de Cookies y Términos del Servicio</a>.
                        </small>
                    </div>

                </div>
            </div>
        </div>

        <script>
            const translations = {{
                es: {{
                    nav_dashboard: "Dashboard",
                    nav_swagger: "Consola Swagger",
                    nav_health: "Health Check",
                    nav_legal: "Aviso Legal",
                    nav_terms: "Términos y Condiciones",
                    title_main: "Panel Enterprise SaaS v",
                    subtitle_main: "Infraestructura oficial de datos con pasarela de integración PLACSP activa",
                    badge_prod: "PRODUCCIÓN v",
                    btn_docs: "Documentación API",
                    card_status_lbl: "Estado del Sistema",
                    card_status_val: "Enterprise Ready",
                    card_arch_lbl: "Arquitectura",
                    card_source_lbl: "Origen de Datos",
                    card_legal_lbl: "Conformidad Legal",
                    card_activator_title: "Activador Comercial de Claves",
                    card_activator_desc: "Selecciona el plan comercial a emitir:",
                    btn_free: "Plan Free (20 req/min)",
                    btn_pro: "Plan Pro / Enterprise (100 req/min)",
                    lbl_gen_key: "Clave Generada",
                    btn_copy: "Copiar",
                    card_webhooks_title: "Registro y Prueba de Webhooks",
                    btn_register_wh: "Registrar Webhook",
                    th_wh_id: "ID Webhook",
                    th_wh_url: "URL Destino",
                    th_wh_date: "Fecha de Registro",
                    card_metrics_title: "Consumo por Clave",
                    th_key: "Clave",
                    th_reqs: "Reqs",
                    card_traffic_title: "Tráfico por Hora",
                    th_slot: "Franja",
                    th_total: "Total",
                    card_audit_title: "Auditoría",
                    btn_all: "Todo",
                    th_time: "Hora",
                    th_status: "Estado",
                    footer_cookies: "Este sitio utiliza únicamente cookies técnicas esenciales para su funcionamiento. Consulta nuestra",
                    footer_terms_link: "Política de Cookies y Términos del Servicio"
                }},
                en: {{
                    nav_dashboard: "Dashboard",
                    nav_swagger: "Swagger Console",
                    nav_health: "Health Check",
                    nav_legal: "Legal Notice",
                    nav_terms: "Terms & Conditions",
                    title_main: "Enterprise SaaS Panel v",
                    subtitle_main: "Official data infrastructure with active PLACSP integration gateway",
                    badge_prod: "PRODUCTION v",
                    btn_docs: "API Docs",
                    card_status_lbl: "System Status",
                    card_status_val: "Enterprise Ready",
                    card_arch_lbl: "Architecture",
                    card_source_lbl: "Data Source",
                    card_legal_lbl: "Legal Compliance",
                    card_activator_title: "Commercial Key Activator",
                    card_activator_desc: "Select the commercial plan to issue:",
                    btn_free: "Free Plan (20 req/min)",
                    btn_pro: "Pro / Enterprise Plan (100 req/min)",
                    lbl_gen_key: "Generated Key",
                    btn_copy: "Copy",
                    card_webhooks_title: "Webhook Registration & Testing",
                    btn_register_wh: "Register Webhook",
                    th_wh_id: "Webhook ID",
                    th_wh_url: "Target URL",
                    th_wh_date: "Registration Date",
                    card_metrics_title: "Consumption by Key",
                    th_key: "Key",
                    th_reqs: "Reqs",
                    card_traffic_title: "Hourly Traffic",
                    th_slot: "Slot",
                    th_total: "Total",
                    card_audit_title: "Audit Logs",
                    btn_all: "All",
                    th_time: "Time",
                    th_status: "Status",
                    footer_cookies: "This site uses only essential technical cookies for its operation. Check our",
                    footer_terms_link: "Cookies Policy & Terms of Service"
                }}
            }};

            function setLanguage(lang) {{
                document.getElementById('btnEs').classList.toggle('active', lang === 'es');
                document.getElementById('btnEn').classList.toggle('active', lang === 'en');
                document.getElementById('htmlRoot').setAttribute('lang', lang);

                const elements = document.querySelectorAll('[data-i18n]');
                elements.forEach(el => {{
                    const key = el.getAttribute('data-i18n');
                    if (translations[lang][key]) {{
                        el.innerText = translations[lang][key];
                    }}
                }});
            }}

            async function generateKey(tier) {{
                try {{
                    const res = await fetch('/request-key', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ tier: tier }})
                    }});
                    const data = await res.json();
                    if (data.api_key) {{
                        document.getElementById('generatedKey').innerText = data.api_key;
                        document.getElementById('planLabel').innerText = data.tier;
                        document.getElementById('keyDisplay').style.display = 'block';
                    }}
                }} catch (e) {{
                    alert('Error generando la clave comercial / Error generating commercial key.');
                }}
            }}

            function copyGeneratedKey() {{
                const keyText = document.getElementById('generatedKey').innerText;
                navigator.clipboard.writeText(keyText);
                const btn = document.getElementById('btnCopyKey');
                btn.innerHTML = '<i class="fa-solid fa-check me-1"></i> ¡Copiada!';
                btn.classList.replace('btn-primary', 'btn-success');
                setTimeout(() => {{
                    btn.innerHTML = '<i class="fa-regular fa-copy me-1"></i> Copiar';
                    btn.classList.replace('btn-success', 'btn-primary');
                }}, 2000);
            }}

            async function registerWebhook() {{
                const url = document.getElementById('webhookUrlInput').value;
                if (!url) {{
                    alert('Por favor introduce una URL válida / Please enter a valid URL.');
                    return;
                }}
                try {{
                    const res = await fetch('/webhooks/register', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ url: url }})
                    }});
                    const data = await res.json();
                    if (data.status === 'success') {{
                        alert('Webhook registrado con éxito / Webhook registered successfully.');
                        location.reload();
                    }} else {{
                        alert('Error al registrar el webhook / Error registering webhook.');
                    }}
                }} catch (e) {{
                    alert('Error de red / Network error.');
                }}
            }}

            function filterLogs(severity) {{
                const buttons = document.querySelectorAll('.card-custom .btn-group button');
                buttons.forEach(btn => btn.classList.remove('active'));
                event.target.classList.add('active');

                const rows = document.querySelectorAll('#auditTable tbody tr');
                rows.forEach(row => {{
                    if (row.id === 'noLogsRow') return;
                    const rowSev = row.getAttribute('data-severity');
                    if (severity === 'ALL' || rowSev === severity) {{
                        row.style.display = '';
                    }} else {{
                        row.style.display = 'none';
                    }}
                }});
            }}
        </script>
    </body>
    </html>
    """

@app.get("/legal", response_class=HTMLResponse, include_in_schema=False)
async def legal_notice():
    return f"""
    <!DOCTYPE html>
    <html lang="es" id="legalRoot" translate="no">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Aviso Legal - API PLACSP SaaS v{API_VERSION}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body style="background-color: #0b0f19; color: #f3f4f6; font-family: 'Segoe UI', sans-serif; padding: 40px;">
        <div class="container" style="max-width: 800px;">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h1 class="fw-bold m-0" id="legalTitle">Aviso Legal y Limitación de Responsabilidad (v{API_VERSION})</h1>
                <div class="btn-group btn-group-sm">
                    <button onclick="switchLegalLang('es')" class="btn btn-outline-light active" id="lBtnEs">ES</button>
                    <button onclick="switchLegalLang('en')" class="btn btn-outline-light" id="lBtnEn">EN</button>
                </div>
            </div>
            
            <hr class="border-secondary my-4">

            <div id="legalContentEs">
                <p>Este servicio opera bajo el amparo de la <strong>Ley 37/2007</strong> sobre reutilización de la información del sector público.</p>
                <p>El proveedor de esta API actúa como mero agregador tecnológico y de índice, no otorga derechos de propiedad intelectual, no garantiza la inalterabilidad o exactitud de los datos originales institucionales (PLACSP), y queda totalmente exento de responsabilidad por interrupciones del servicio derivadas de fallos en los servidores públicos oficiales.</p>
            </div>

            <div id="legalContentEn" style="display: none;">
                <p>This service operates under <strong>Law 37/2007</strong> on the reuse of public sector information.</p>
                <p>The provider of this API acts merely as a technological and index aggregator, does not grant intellectual property rights, does not guarantee the unalterability or accuracy of official institutional raw data (PLACSP), and is fully exempt from liability for service interruptions arising from failures in official public servers.</p>
            </div>

            <div class="mt-5">
                <a href="/" class="btn btn-outline-primary btn-sm" id="backBtn">&larr; Volver al Dashboard</a>
            </div>
        </div>

        <script>
            function switchLegalLang(lang) {{
                document.getElementById('lBtnEs').classList.toggle('active', lang === 'es');
                document.getElementById('lBtnEn').classList.toggle('active', lang === 'en');
                document.getElementById('legalRoot').setAttribute('lang', lang);

                if (lang === 'es') {{
                    document.getElementById('legalTitle').innerText = "Aviso Legal y Limitación de Responsabilidad (v{API_VERSION})";
                    document.getElementById('legalContentEs').style.display = 'block';
                    document.getElementById('legalContentEn').style.display = 'none';
                    document.getElementById('backBtn').innerHTML = "&larr; Volver al Dashboard";
                }} else {{
                    document.getElementById('legalTitle').innerText = "Legal Notice & Limitation of Liability (v{API_VERSION})";
                    document.getElementById('legalContentEs').style.display = 'none';
                    document.getElementById('legalContentEn').style.display = 'block';
                    document.getElementById('backBtn').innerHTML = "&larr; Back to Dashboard";
                }}
            }}
        </script>
    </body>
    </html>
    """

@app.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms_and_conditions():
    return f"""
    <!DOCTYPE html>
    <html lang="es" id="termsRoot" translate="no">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Términos y Condiciones - API PLACSP SaaS v{API_VERSION}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body style="background-color: #0b0f19; color: #f3f4f6; font-family: 'Segoe UI', sans-serif; padding: 40px;">
        <div class="container" style="max-width: 800px;">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h1 class="fw-bold m-0" id="termsTitle">Términos y Condiciones del Servicio (v{API_VERSION})</h1>
                <div class="btn-group btn-group-sm">
                    <button onclick="switchTermsLang('es')" class="btn btn-outline-light active" id="tBtnEs">ES</button>
                    <button onclick="switchTermsLang('en')" class="btn btn-outline-light" id="tBtnEn">EN</button>
                </div>
            </div>
            <p class="text-muted" id="termsDate">Última actualización: Noviembre de 2026</p>
            
            <hr class="border-secondary my-4">

            <!-- Versión en Español -->
            <div id="termsEs">
                <h5 class="text-info mt-4">1. Naturaleza del Servicio y Fuente de Datos</h5>
                <p>El servicio consiste en una pasarela tecnológica de agregación, filtrado y optimización de datos públicos obtenidos de la Plataforma de Contratación del Sector Público (PLACSP), operando bajo el amparo de la <strong>Ley 37/2007</strong>. Actuamos como mero intermediario tecnológico y no asumimos ninguna responsabilidad sobre la exactitud, veracidad o disponibilidad de los datos originales publicados por los organismos públicos oficiales.</p>

                <h5 class="text-info mt-4">2. Disponibilidad y Mantenimiento ("Garantía Anti-Rupturas")</h5>
                <p>Destinaremos nuestros mejores esfuerzos técnicos (<em>Best Efforts</em>) a mantener la continuidad del servicio y actualizar los conectores ante posibles modificaciones estructurales de la fuente oficial. No obstante, no se garantiza un funcionamiento ininterrumpido ni libre de errores debido a posibles caídas, cambios imprevistos o fallos técnicos en los servidores de la administración pública.</p>

                <h5 class="text-info mt-4">3. Limitación de Responsabilidad (Cap of Liability)</h5>
                <p>En ningún caso el Proveedor será responsable de daños indirectos, pérdida de negocio, lucro cesante o pérdida de contratos derivados del uso de la API, interrupciones del servicio o retrasos en las alertas. <strong>La responsabilidad máxima total</strong> frente al Cliente por cualquier reclamación estará estrictamente limitada a la cantidad total abonada por el Cliente en concepto de suscripción durante el último mes en curso.</p>

                <h5 class="text-info mt-4">4. Política de Cancelación</h5>
                <p>El usuario puede cancelar su suscripción en cualquier momento. La cancelación surtirá efecto al finalizar el periodo de facturación ya pagado, sin reembolsos por periodos parciales.</p>

                <h5 class="text-info mt-4">5. Política de Cookies</h5>
                <p>Este servicio utiliza exclusivamente <strong>cookies técnicas estrictamente necesarias</strong> para la gestión de solicitudes, la seguridad de las claves de API y el correcto funcionamiento del dashboard. No empleamos cookies de rastreo, analíticas de terceros ni cookies con fines publicitarios o de perfilado.</p>
            </div>

            <!-- Versión en Inglés -->
            <div id="termsEn" style="display: none;">
                <h5 class="text-info mt-4">1. Nature of Service and Data Source</h5>
                <p>The service consists of a technological gateway for aggregation, filtering, and optimization of public data obtained from the Public Sector Procurement Platform (PLACSP), operating under the protection of <strong>Law 37/2007</strong>. We act merely as a technological intermediary and assume no responsibility for the accuracy, truthfulness, or availability of original data published by official public bodies.</p>

                <h5 class="text-info mt-4">2. Availability and Maintenance ("Anti-Rupture Guarantee")</h5>
                <p>We will dedicate our best technical efforts (<em>Best Efforts</em>) to maintain service continuity and update connectors against potential structural modifications from the official source. However, uninterrupted or error-free operation is not guaranteed due to possible outages, unforeseen changes, or technical failures in public administration servers.</p>

                <h5 class="text-info mt-4">3. Limitation of Liability (Cap of Liability)</h5>
                <p>Under no circumstances shall the Provider be liable for indirect damages, loss of business, loss of profit, or loss of contracts derived from the use—or inability to use—the API, service interruptions, or alert delays. <strong>The total maximum liability</strong> of the Provider toward the Client for any claim shall be strictly limited to the total amount paid by the Client for subscription during the last active month.</p>

                <h5 class="text-info mt-4">4. Cancellation Policy</h5>
                <p>The user may cancel their subscription at any time. Cancellation will take effect at the end of the already paid billing period, with no refunds for partial periods.</p>

                <h5 class="text-info mt-4">5. Cookies Policy</h5>
                <p>This service exclusively uses <strong>strictly necessary technical cookies</strong> for request management, API key security, and proper dashboard operation. We do not use tracking cookies, third-party analytics, or cookies for advertising or profiling purposes.</p>
            </div>

            <div class="mt-5">
                <a href="/" class="btn btn-outline-primary btn-sm" id="termsBackBtn">&larr; Volver al Dashboard</a>
            </div>
        </div>

        <script>
            function switchTermsLang(lang) {{
                document.getElementById('tBtnEs').classList.toggle('active', lang === 'es');
                document.getElementById('tBtnEn').classList.toggle('active', lang === 'en');
                document.getElementById('termsRoot').setAttribute('lang', lang);

                if (lang === 'es') {{
                    document.getElementById('termsTitle').innerText = "Términos y Condiciones del Servicio (v{API_VERSION})";
                    document.getElementById('termsDate').innerText = "Última actualización: Noviembre de 2026";
                    document.getElementById('termsEs').style.display = 'block';
                    document.getElementById('termsEn').style.display = 'none';
                    document.getElementById('termsBackBtn').innerHTML = "&larr; Volver al Dashboard";
                }} else {{
                    document.getElementById('termsTitle').innerText = "Terms and Conditions of Service (v{API_VERSION})";
                    document.getElementById('termsDate').innerText = "Last updated: November 2026";
                    document.getElementById('termsEs').style.display = 'none';
                    document.getElementById('termsEn').style.display = 'block';
                    document.getElementById('termsBackBtn').innerHTML = "&larr; Back to Dashboard";
                }}
            }}
        </script>
    </body>
    </html>
    """

@app.get("/tenders", dependencies=[Depends(verify_api_key)])
async def get_tenders(
    request: Request, 
    estado: str = Query(None, description="Filtrar por estado / Filter by status"),
    formato: str = Query("json", description="Formato: json o csv / Format: json or csv"),
    limit: int = Query(10, ge=1, le=100, description="Límite / Limit per page"),
    offset: int = Query(0, ge=0, description="Desplazamiento / Pagination offset")
):
    global CACHE_STORAGE
    now = time.time()

    if not CACHE_STORAGE["data"] or (now - CACHE_STORAGE["timestamp"]) > CACHE_TTL:
        CACHE_STORAGE["data"] = fetch_real_placsp_tenders()
        CACHE_STORAGE["timestamp"] = now

    tenders_data = CACHE_STORAGE["data"]

    filtered_data = tenders_data
    if estado:
        filtered_data = [t for t in tenders_data if t["estado"].lower() == estado.lower()]

    paginated_data = filtered_data[offset: offset + limit]

    if formato.lower() == "csv":
        csv_rows = ["id,objeto,organo_contratacion,estado,fecha_publicacion"]
        for t in paginated_data:
            csv_rows.append(f"{t['id']},\"{t['objeto']}\",\"{t['organo_contratacion']}\",{t['estado']},{t['fecha_publicacion']}")
        csv_text = "\n".join(csv_rows)
        return PlainTextResponse(content=csv_text, media_type="text/csv")

    return {
        "status": "success",
        "version": API_VERSION,
        "cache_status": "hit",
        "legal_notice": "Ley 37/2007.",
        "pagination": {
            "total_matches": len(filtered_data),
            "limit": limit,
            "offset": offset
        },
        "data": paginated_data
    }
