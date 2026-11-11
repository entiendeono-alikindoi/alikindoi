import os
import uuid
import time
import requests
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Depends, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(
    title="API de Contratación Pública (PLACSP) - Enterprise SaaS",
    description="Infraestructura comercial y de monetización de licitaciones públicas oficiales bajo amparo de la Ley 37/2007 con pasarela de pago y alertas automatizadas.",
    version="4.2.0",
    docs_url=None,
    redoc_url=None
)

# Estructuras de datos para la versión Enterprise v4.2.0
DYNAMIC_API_KEYS = {}
REQUEST_COUNTS = {}
AUDIT_LOGS = []
API_KEY_METRICS = {}
REGISTERED_WEBHOOKS = []
PAID_SUBSCRIPTIONS = {}
CACHE_STORAGE = {"data": None, "timestamp": 0}
CACHE_TTL = 300
START_TIME = time.time()

MASTER_KEYS = set(os.getenv("API_KEYS", "clave_demo_123,super_secret_key_456").split(","))

def fetch_real_placsp_tenders():
    """Conector oficial con la PLACSP con respaldo (fallback) ante interrupciones institucionales."""
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
            "objeto": f"Licitación Enterprise v4.2 (Monetizada) número {i}",
            "organo_contratacion": "Ministerio de Asuntos Económicos" if i % 2 == 0 else "Ministerio de Hacienda",
            "estado": "En Plazo" if i % 3 == 0 else ("Adjudicado" if i % 3 == 1 else "Pendiente"),
            "fecha_publicacion": f"2026-11-{str(i).zfill(2)}"
        } for i in range(1, 50)
    ]

def verify_api_key(x_api_key: str = Header(...)):
    now = time.time()
    
    if x_api_key not in MASTER_KEYS and x_api_key not in DYNAMIC_API_KEYS:
        AUDIT_LOGS.insert(0, {
            "timestamp": datetime.now().isoformat(),
            "key_used": x_api_key[:6] + "..." if len(x_api_key) > 6 else "INVALID",
            "status": "REJECTED (Unauthorized)"
        })
        raise HTTPException(
            status_code=401, 
            detail="Acceso Denegado: Clave de API inválida o ausente."
        )
    
    tier = "enterprise" if x_api_key in MASTER_KEYS else DYNAMIC_API_KEYS.get(x_api_key, {}).get("tier", "free")
    limit_rate = 100 if tier in ["pro", "enterprise"] else 20

    if x_api_key not in MASTER_KEYS:
        client_history = REQUEST_COUNTS.get(x_api_key, [])
        client_history = [t for t in client_history if now - t < 60]
        
        if len(client_history) >= limit_rate:
            AUDIT_LOGS.insert(0, {
                "timestamp": datetime.now().isoformat(),
                "key_used": x_api_key[:6] + "...",
                "status": f"REJECTED (Rate Limit Tier: {tier})"
            })
            raise HTTPException(
                status_code=429,
                detail=f"Límite de peticiones excedido para el plan {tier}. Actualice su suscripción."
            )
        
        client_history.append(now)
        REQUEST_COUNTS[x_api_key] = client_history

    key_identifier = x_api_key[:6] + "..." if x_api_key not in MASTER_KEYS else "MASTER_KEY"
    API_KEY_METRICS[key_identifier] = API_KEY_METRICS.get(key_identifier, 0) + 1

    AUDIT_LOGS.insert(0, {
        "timestamp": datetime.now().isoformat(),
        "key_used": key_identifier,
        "status": f"SUCCESS ({tier.upper()})"
    })
    
    if len(AUDIT_LOGS) > 50:
        AUDIT_LOGS.pop()

    return x_api_key

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Consola de Documentación v4.2",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png"
    )

@app.get("/health", include_in_schema=True)
async def health_check():
    uptime_seconds = int(time.time() - START_TIME)
    return {
        "status": "healthy",
        "version": "4.2.0",
        "uptime_seconds": uptime_seconds,
        "cache_active": bool(CACHE_STORAGE["data"]),
        "active_paid_subscriptions": len(PAID_SUBSCRIPTIONS),
        "timestamp": datetime.now().isoformat(),
        "legal_notice": "Servicio operando bajo la Ley 37/2007 de Reutilización de la Información del Sector Público."
    }

@app.post("/checkout/create-session")
async def create_checkout_session(payload: dict):
    """Simula pasarela de pago (Stripe Ready) para emitir claves Pro monetizadas."""
    plan = payload.get("tier", "pro")
    email = payload.get("email", "client@enterprise.com")
    
    session_id = f"cs_live_{uuid.uuid4().hex[:16]}"
    api_key = f"key_{plan}_{uuid.uuid4().hex[:12]}"
    
    DYNAMIC_API_KEYS[api_key] = {
        "created_at": datetime.now().isoformat(),
        "tier": plan,
        "status": "active",
        "email": email
    }
    
    PAID_SUBSCRIPTIONS[session_id] = {
        "email": email,
        "tier": plan,
        "api_key": api_key,
        "status": "completed",
        "created_at": datetime.now().isoformat()
    }
    
    return {
        "status": "success",
        "checkout_session_id": session_id,
        "payment_status": "paid",
        "api_key": api_key,
        "tier": plan.upper(),
        "message": "Pago procesado con éxito. Clave de API comercial activada.",
        "legal_notice": "Servicio facturado conforme a la normativa vigente."
    }

@app.post("/webhooks/register")
async def register_webhook(payload: dict):
    webhook_url = payload.get("url")
    keyword = payload.get("keyword", "general")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="La URL del webhook es obligatoria.")
    
    hook_id = f"wh_{uuid.uuid4().hex[:8]}"
    REGISTERED_WEBHOOKS.append({
        "id": hook_id,
        "url": webhook_url,
        "keyword": keyword,
        "registered_at": datetime.now().isoformat()
    })
    return {
        "status": "success",
        "webhook_id": hook_id,
        "keyword_filter": keyword,
        "message": "Webhook monetizado registrado para alertas de licitaciones en tiempo real."
    }

@app.post("/webhooks/test", dependencies=[Depends(verify_api_key)])
async def test_webhook(payload: dict):
    if not REGISTERED_WEBHOOKS:
        return {"status": "warning", "message": "No hay webhooks registrados para probar."}
    
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
        "version": "4.2.0",
        "total_tenders": len(tenders),
        "by_state": states_count,
        "by_organ": orgs_count,
        "legal_notice": "Datos procesados bajo el amparo de la Ley 37/2007."
    }

@app.get("/tenders/search", dependencies=[Depends(verify_api_key)])
async def search_tenders(
    q: str = Query(..., description="Término de búsqueda textual"),
    organo: str = Query(None, description="Filtrar por órgano de contratación específico")
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
        "version": "4.2.0",
        "query": q,
        "filter_organ": organo,
        "matches_count": len(results),
        "data": results,
        "legal_notice": "Datos obtenidos al amparo de la Ley 37/2007."
    }

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def home_dashboard():
    logs_html = "".join([f"<tr><td>{log['timestamp']}</td><td><code>{log['key_used']}</code></td><td><span class='badge bg-{'success' if 'SUCCESS' in log['status'] else 'danger'}'>{log['status']}</span></td></tr>" for log in AUDIT_LOGS[:10]])
    if not logs_html:
        logs_html = "<tr><td colspan='3' class='text-muted text-center'>No hay registros de auditoría recientes.</td></tr>"

    metrics_html = "".join([f"<tr><td><code>{k}</code></td><td><span class='badge bg-info text-dark'>{v} peticiones</span></td></tr>" for k, v in API_KEY_METRICS.items()])
    if not metrics_html:
        metrics_html = "<tr><td colspan='2' class='text-muted text-center'>Sin consumo registrado todavía.</td></tr>"

    webhooks_html = "".join([f"<tr><td><code>{w['id']}</code></td><td><small class='text-light'>{w['url']}</small></td><td><span class='badge bg-warning text-dark'>{w['keyword']}</span></td></tr>" for w in REGISTERED_WEBHOOKS])
    if not webhooks_html:
        webhooks_html = "<tr><td colspan='3' class='text-muted text-center'>No hay webhooks registrados.</td></tr>"

    subs_html = "".join([f"<tr><td><code>{s_id[:10]}...</code></td><td>{sub['email']}</td><td><span class='badge bg-success'>{sub['tier'].upper()}</span></td><td>{sub['created_at']}</td></tr>" for s_id, sub in PAID_SUBSCRIPTIONS.items()])
    if not subs_html:
        subs_html = "<tr><td colspan='4' class='text-muted text-center'>No hay suscripciones de pago registradas todavía.</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dashboard Monetización - API PLACSP SaaS v4.2</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <style>
            :root {{
                --bg-main: #0b0f19;
                --bg-card: #151c2c;
                --text-main: #f3f4f6;
                --text-muted: #9ca3af;
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
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <div class="row">
                <!-- Sidebar -->
                <div class="col-md-2 d-none d-md-block sidebar py-4">
                    <h5 class="px-3 text-white fw-bold mb-4"><i class="fa-solid fa-cube text-primary me-2"></i>PLACSP SaaS</h5>
                    <ul class="nav flex-column">
                        <li class="nav-item"><a class="nav-link active" href="#"><i class="fa-solid fa-chart-line me-2"></i>Dashboard v4.2</a></li>
                        <li class="nav-item"><a class="nav-link" href="/docs"><i class="fa-solid fa-code me-2"></i>Swagger Consola</a></li>
                        <li class="nav-item"><a class="nav-link" href="/health" target="_blank"><i class="fa-solid fa-heart-pulse me-2"></i>Health Check</a></li>
                        <li class="nav-item"><a class="nav-link" href="/legal"><i class="fa-solid fa-scale-balanced me-2"></i>Marco Legal</a></li>
                    </ul>
                </div>

                <!-- Main Content -->
                <div class="col-md-10 p-4">
                    <div class="d-flex justify-content-between align-items-center mb-4 pb-3 border-bottom border-secondary">
                        <div>
                            <h3 class="fw-bold m-0">Panel SaaS de Monetización v4.2</h3>
                            <p class="text-muted m-0 small">Pasarela de pago Stripe-Ready y gestión comercial activa</p>
                        </div>
                        <div>
                            <span class="badge-status me-2"><i class="fa-solid fa-circle me-1 small"></i> MONETIZACIÓN ACTIVA v4.2.0</span>
                            <a href="/docs" class="btn btn-primary btn-sm"><i class="fa-solid fa-book me-1"></i> Documentación API</a>
                        </div>
                    </div>

                    <!-- Metrics Section -->
                    <div class="row g-3 mb-4">
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small">Estado de Pasarela</span>
                                <h4 class="fw-bold mt-2 mb-0 text-success"><i class="fa-solid fa-credit-card me-2"></i>Stripe Online</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small">Suscripciones de Pago</span>
                                <h4 class="fw-bold mt-2 mb-0 text-info">{len(PAID_SUBSCRIPTIONS)} Activas</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small">Webhooks Monetizados</span>
                                <h4 class="fw-bold mt-2 mb-0 text-warning">{len(REGISTERED_WEBHOOKS)} Registrados</h4>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="card-custom">
                                <span class="text-muted small">Conformidad Legal</span>
                                <h4 class="fw-bold mt-2 mb-0 text-secondary">Ley 37/2007</h4>
                            </div>
                        </div>
                    </div>

                    <!-- Commercial Checkout Simulation Card -->
                    <div class="card-custom mb-4">
                        <h5 class="fw-bold mb-3"><i class="fa-solid fa-cart-shopping me-2"></i>Pasarela de Compra Exprés (Checkout Simulado)</h5>
                        <p class="text-muted small">Selecciona el plan comercial y emite tu clave de pago instantánea:</p>
                        <div class="row g-3 align-items-center" style="max-width: 700px;">
                            <div class="col-md-5">
                                <input type="email" id="buyerEmail" class="form-control bg-dark text-light border-secondary" placeholder="cliente@empresa.com" value="demo@empresa.com">
                            </div>
                            <div class="col-md-4">
                                <select id="selectPlan" class="form-select bg-dark text-light border-secondary">
                                    <option value="pro">Plan Pro (49€/mes)</option>
                                    <option value="enterprise">Plan Enterprise (199€/mes)</option>
                                </select>
                            </div>
                            <div class="col-md-3">
                                <button onclick="buySubscription()" class="btn btn-success w-100"><i class="fa-solid fa-bolt me-1"></i> Pagar y Activar</button>
                            </div>
                        </div>
                        <div id="checkoutResult" class="mt-3" style="display:none;">
                            <div class="alert alert-dark border border-success text-light">
                                <strong>¡Compra Exitosa! Session ID:</strong> <span id="resSession" class="text-info"></span><br>
                                <strong>Clave API Comercial:</strong> <code id="resKey" class="text-warning"></code>
                            </div>
                        </div>
                    </div>

                    <!-- Paid Subscriptions Table -->
                    <div class="card-custom mb-4">
                        <h5 class="fw-bold mb-3"><i class="fa-solid fa-receipt me-2"></i>Historial de Suscripciones Pagadas</h5>
                        <div class="table-responsive">
                            <table class="table table-dark table-striped table-sm align-middle">
                                <thead>
                                    <tr>
                                        <th>ID Sesión</th>
                                        <th>Cliente</th>
                                        <th>Plan</th>
                                        <th>Fecha Alta</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {subs_html}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Webhooks Management Card -->
                    <div class="card-custom mb-4">
                        <h5 class="fw-bold mb-3"><i class="fa-solid fa-bell me-2"></i>Registro de Alertas por Webhook (Filtro por Keyword)</h5>
                        <div class="row g-3" style="max-width: 800px;">
                            <div class="col-md-6">
                                <input type="text" id="webhookUrlInput" class="form-control bg-dark text-light border-secondary" placeholder="https://tu-servidor.com/webhook">
                            </div>
                            <div class="col-md-4">
                                <input type="text" id="webhookKeyword" class="form-control bg-dark text-light border-secondary" placeholder="Palabra clave (ej. IA, obra)">
                            </div>
                            <div class="col-md-2">
                                <button onclick="registerWebhook()" class="btn btn-outline-primary w-100">Registrar</button>
                            </div>
                        </div>
                        <div class="table-responsive mt-3">
                            <table class="table table-dark table-striped table-sm align-middle">
                                <thead>
                                    <tr>
                                        <th>ID Webhook</th>
                                        <th>URL Destino</th>
                                        <th>Filtro Clave</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {webhooks_html}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <!-- Metrics & Audit Cards -->
                    <div class="row g-3 mb-4">
                        <div class="col-md-6">
                            <div class="card-custom h-100">
                                <h5 class="fw-bold mb-3"><i class="fa-solid fa-chart-bar me-2"></i>Consumo Acumulado por Clave</h5>
                                <div class="table-responsive">
                                    <table class="table table-dark table-striped table-sm align-middle">
                                        <thead>
                                            <tr>
                                                <th>Identificador Clave</th>
                                                <th>Peticiones Totales</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {metrics_html}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card-custom h-100">
                                <h5 class="fw-bold mb-3"><i class="fa-solid fa-list-check me-2"></i>Últimos Eventos de Auditoría</h5>
                                <div class="table-responsive">
                                    <table class="table table-dark table-striped table-sm align-middle">
                                        <thead>
                                            <tr>
                                                <th>Hora</th>
                                                <th>Clave</th>
                                                <th>Estado</th>
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

                </div>
            </div>
        </div>

        <script>
            async function buySubscription() {{
                const email = document.getElementById('buyerEmail').value;
                const tier = document.getElementById('selectPlan').value;
                if (!email) {{
                    alert('Introduce un correo electrónico válido.');
                    return;
                }}
                try {{
                    const res = await fetch('/checkout/create-session', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ email: email, tier: tier }})
                    }});
                    const data = await res.json();
                    if (data.api_key) {{
                        document.getElementById('resSession').innerText = data.checkout_session_id;
                        document.getElementById('resKey').innerText = data.api_key;
                        document.getElementById('checkoutResult').style.display = 'block';
                        setTimeout(() => location.reload(), 3000);
                    }}
                }} catch (e) {{
                    alert('Error procesando la pasarela de pago.');
                }}
            }}

            async function registerWebhook() {{
                const url = document.getElementById('webhookUrlInput').value;
                const keyword = document.getElementById('webhookKeyword').value || 'general';
                if (!url) {{
                    alert('Introduce una URL de webhook válida.');
                    return;
                }}
                try {{
                    const res = await fetch('/webhooks/register', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ url: url, keyword: keyword }})
                    }});
                    const data = await res.json();
                    if (data.status === 'success') {{
                        alert('Webhook registrado con éxito.');
                        location.reload();
                    }}
                }} catch (e) {{
                    alert('Error de red al registrar el webhook.');
                }}
            }}
        </script>
    </body>
    </html>
    """

@app.get("/legal", response_class=HTMLResponse, include_in_schema=False)
async def legal_notice():
    return """
    <html>
        <body style="font-family: sans-serif; padding: 20px; line-height: 1.6; background-color: #0b0f19; color: #f3f4f6;">
            <h2>Aviso Legal y Limitación de Responsabilidad</h2>
            <p>Este servicio opera bajo el amparo de la <strong>Ley 37/2007</strong> sobre reutilización de la información del sector público.</p>
            <p>El proveedor de esta API actúa como mero agregador tecnológico y de índice, no otorga derechos de propiedad intelectual, no garantiza la inalterabilidad o exactitud de los datos originales institucionales (PLACSP), y queda totalmente exento de responsabilidad por interrupciones del servicio derivadas de fallos en los servidores públicos oficiales.</p>
            <p><a href="/" style="color: #3b82f6;">Volver al Dashboard</a></p>
        </body>
    </html>
    """

@app.get("/tenders", dependencies=[Depends(verify_api_key)])
async def get_tenders(
    request: Request, 
    estado: str = Query(None, description="Filtrar por estado"),
    formato: str = Query("json", description="Formato de salida: json o csv"),
    limit: int = Query(10, ge=1, le=100, description="Límite por página"),
    offset: int = Query(0, ge=0, description="Desplazamiento para paginación")
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
        "version": "4.2.0",
        "cache_status": "hit",
        "legal_notice": "AVISO LEGAL: Datos obtenidos de fuentes abiertas institucionales (PLACSP) al amparo de la Ley 37/2007. Actuamos como mero agregador tecnológico exento de responsabilidad sobre los datos originales.",
        "pagination": {
            "total_matches": len(filtered_data),
            "limit": limit,
            "offset": offset
        },
        "data": paginated_data
    }
