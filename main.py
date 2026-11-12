import os
import uuid
import time
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Depends, Request, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(
    title="PLACSP Intelligence — API & B2G Data Platform",
    description="Infraestructura comercial de datos de contratación pública bajo la Ley 37/2007.",
    version="6.0.0",
    docs_url=None,
    redoc_url=None
)

# Estructuras de datos comerciales
DYNAMIC_API_KEYS = {}
REQUEST_COUNTS = {}
API_KEY_METRICS = {}
REGISTERED_WEBHOOKS = []
CACHE_STORAGE = {"data": None, "timestamp": 0}
CACHE_TTL = 300
START_TIME = time.time()

MASTER_KEYS = set(os.getenv("API_KEYS", "clave_demo_123,super_secret_key_456").split(","))

def get_commercial_dataset():
    """Dataset enriquecido para competir con soluciones de inteligencia comercial."""
    global CACHE_STORAGE
    now = time.time()
    if not CACHE_STORAGE["data"] or (now - CACHE_STORAGE["timestamp"]) > CACHE_TTL:
        ccaa_list = ["Madrid", "Andalucía", "Cataluña", "Comunidad Valenciana", "País Vasco"]
        organos = ["Ministerio de Asuntos Económicos", "Ministerio de Hacienda", "Servicio Andaluz de Salud", "Ayuntamiento de Madrid"]
        dataset = []
        for i in range(1, 51):
            estado = "En Plazo" if i % 3 != 0 else "Adjudicado"
            dataset.append({
                "id": f"EXP-2026-{str(i).zfill(4)}",
                "titulo": f"Servicios de consultoría y desarrollo tecnológico avanzado - Lote {i}",
                "organo": organos[i % len(organos)],
                "ccaa": ccaa_list[i % len(ccaa_list)],
                "estado": estado,
                "presupuesto": round(45000 + (i * 15500), 2),
                "adjudicatario": "Indra / Telefónica UTE" if estado == "Adjudicado" else None,
                "fecha": f"2026-11-{str((i % 28) + 1).zfill(2)}"
            })
        CACHE_STORAGE["data"] = dataset
        CACHE_STORAGE["timestamp"] = now
    return CACHE_STORAGE["data"]

def verify_commercial_api_key(x_api_key: str = Header(...)):
    now = time.time()
    if x_api_key not in MASTER_KEYS and x_api_key not in DYNAMIC_API_KEYS:
        raise HTTPException(status_code=401, detail="Acceso Denegado: API Key inválida o inexistente.")
    
    tier = "enterprise" if x_api_key in MASTER_KEYS else DYNAMIC_API_KEYS.get(x_api_key, {}).get("tier", "free")
    limits = {"free": 20, "pro": 120, "enterprise": 500}
    limit_rate = limits.get(tier, 20)

    if x_api_key not in MASTER_KEYS:
        client_history = REQUEST_COUNTS.get(x_api_key, [])
        client_history = [t for t in client_history if now - t < 60]
        if len(client_history) >= limit_rate:
            raise HTTPException(status_code=429, detail=f"Límite de peticiones excedido para el plan {tier.upper()}.")
        client_history.append(now)
        REQUEST_COUNTS[x_api_key] = client_history

    API_KEY_METRICS[x_api_key[:10] + "..."] = API_KEY_METRICS.get(x_api_key[:10] + "...", 0) + 1
    return x_api_key

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(openapi_url=app.openapi_url, title="PLACSP API Docs", swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png")

@app.get("/health", tags=["Sistema"])
async def health():
    return {"status": "operational", "version": "6.0.0", "uptime_seconds": int(time.time() - START_TIME), "compliance": "Ley 37/2007 RISP"}

@app.post("/commercial/subscribe", tags=["Comercial"])
async def commercial_subscribe(payload: dict):
    tier = payload.get("tier", "free").lower()
    if tier not in ["free", "pro", "enterprise"]:
        tier = "free"
    
    new_key = f"placsp_{tier}_{uuid.uuid4().hex[:12]}"
    DYNAMIC_API_KEYS[new_key] = {"tier": tier, "created_at": datetime.now().isoformat()}
    
    return {
        "status": "success",
        "message": f"Suscripción al plan {tier.upper()} completada con éxito.",
        "api_key": new_key,
        "tier": tier.upper(),
        "rate_limit_rpm": 20 if tier=="free" else (120 if tier=="pro" else 500)
    }

@app.post("/webhooks/register", tags=["Webhooks"])
async def register_webhook(payload: dict):
    url = payload.get("url")
    if not url:
        raise HTTPException(status_code=400, detail="URL obligatoria.")
    hook_id = f"wh_{uuid.uuid4().hex[:8]}"
    REGISTERED_WEBHOOKS.append({"id": hook_id, "url": url, "registered": datetime.now().strftime("%d/%m/%Y")})
    return {"status": "success", "webhook_id": hook_id}

@app.get("/tenders", dependencies=[Depends(verify_commercial_api_key)], tags=["Licitaciones"])
async def get_tenders(
    q: str = Query(None, description="Búsqueda textual"),
    ccaa: str = Query(None, description="Filtrar por Comunidad Autónoma"),
    estado: str = Query(None, description="Filtrar por estado"),
    limit: int = Query(15, ge=1, le=50)
):
    data = get_commercial_dataset()
    if q:
        q_low = q.lower()
        data = [t for t in data if q_low in t["titulo"].lower() or q_low in t["organo"].lower()]
    if ccaa:
        data = [t for t in data if ccaa.lower() in t["ccaa"].lower()]
    if estado:
        data = [t for t in data if estado.lower() in t["estado"].lower()]
    
    return {"total_matches": len(data), "data": data[:limit], "legal_notice": "Datos bajo amparo de la Ley 37/2007."}

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def commercial_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PLACSP Intelligence — Plataforma de Contratación Pública B2G</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet">
        <style>
            :root {
                --bg: #070a11;
                --surface: #0f172a;
                --border: #1e293b;
                --text: #f8fafc;
                --muted: #94a3b8;
                --primary: #3b82f6;
                --accent-pro: #f59e0b;
            }
            body { background-color: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; }
            .navbar-saas { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(10px); border-bottom: 1px solid var(--border); }
            .card-saas { background-color: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 24px; }
            .pricing-card { background: #131c31; border: 1px solid var(--border); border-radius: 12px; padding: 24px; transition: all 0.2s; position: relative; }
            .pricing-card.featured { border-color: var(--accent-pro); box-shadow: 0 10px 30px rgba(245, 158, 11, 0.15); }
            .form-control, .form-select { background-color: #070a11; border-color: var(--border); color: white; font-size: 0.9rem; }
            .form-control:focus, .form-select:focus { background-color: #070a11; border-color: var(--primary); color: white; box-shadow: none; }
            #cookie-banner { position: fixed; bottom: 0; left: 0; right: 0; background: #0f172a; border-top: 1px solid var(--border); padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; z-index: 9999; }
            .table { color: var(--text); }
            .table th { color: var(--muted); border-bottom-color: var(--border); font-size: 0.78rem; text-transform: uppercase; }
            .table td { border-bottom-color: var(--border); font-size: 0.88rem; vertical-align: middle; }
        </style>
    </head>
    <body>
        <!-- Navbar -->
        <nav class="navbar navbar-expand-lg navbar-saas sticky-top px-4 py-3">
            <div class="container-fluid">
                <span class="fw-bold fs-5 text-white"><i class="fa-solid fa-cube text-primary me-2"></i>PLACSP <span class="text-primary">Intelligence</span></span>
                <div class="d-flex align-items-center gap-3">
                    <a href="/docs" class="btn btn-outline-light btn-sm"><i class="fa-solid fa-terminal me-1"></i> Documentación API</a>
                    <a href="/legal" class="btn btn-outline-secondary btn-sm"><i class="fa-solid fa-scale-balanced me-1"></i> Aviso Legal</a>
                </div>
            </div>
        </nav>

        <div class="container py-5" style="max-width: 1200px;">
            
            <!-- Hero Comercial -->
            <div class="text-center mb-5">
                <span class="badge bg-primary bg-opacity-10 text-primary border border-primary px-3 py-1 rounded-pill mb-3">INFRAESTRUCTURA B2G PROFESIONAL</span>
                <h1 class="fw-bold display-6 mb-3">Inteligencia de Contratación Pública en Tiempo Real</h1>
                <p class="text-muted mx-auto" style="max-width: 650px;">Agrega, filtra y automatiza licitaciones oficiales del Estado bajo la Ley 37/2007 con latencia ultrabaja y alertas por webhooks.</p>
            </div>

            <!-- Sección de Precios y Suscripción (Checkout Comercial) -->
            <div class="row g-4 mb-5">
                <div class="col-md-4">
                    <div class="pricing-card h-100 d-flex flex-column justify-content-between">
                        <div>
                            <span class="badge bg-secondary mb-2">STARTER</span>
                            <h3 class="fw-bold mb-1">0 € <span class="fs-6 fw-normal text-muted">/ gratis</span></h3>
                            <p class="text-muted small mb-4">Para validación y pruebas iniciales de desarrollo.</p>
                            <ul class="list-unstyled small text-muted mb-4">
                                <li class="mb-2">✓ 20 peticiones / minuto</li>
                                <li class="mb-2">✓ Datos estándar PLACSP</li>
                                <li class="mb-2">✓ Soporte comunitario</li>
                            </ul>
                        </div>
                        <button onclick="subscribePlan('free')" class="btn btn-outline-light w-100 fw-semibold btn-sm">Obtener Plan Free</button>
                    </div>
                </div>

                <div class="col-md-4">
                    <div class="pricing-card featured h-100 d-flex flex-column justify-content-between">
                        <div>
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="badge bg-warning text-dark fw-bold">PRO BUSINESS</span>
                                <span class="small text-warning">¡Más Popular!</span>
                            </div>
                            <h3 class="fw-bold mb-1">49 € <span class="fs-6 fw-normal text-muted">/ mes</span></h3>
                            <p class="text-muted small mb-4">Para empresas y despachos que buscan adjudicaciones.</p>
                            <ul class="list-unstyled small text-light mb-4">
                                <li class="mb-2">✓ <strong>120 peticiones / minuto</strong></li>
                                <li class="mb-2">✓ Filtros avanzados por CCAA</li>
                                <li class="mb-2">✓ Alertas automáticas Webhooks</li>
                            </ul>
                        </div>
                        <button onclick="subscribePlan('pro')" class="btn btn-warning w-100 fw-bold text-dark btn-sm">Suscribirme a Pro</button>
                    </div>
                </div>

                <div class="col-md-4">
                    <div class="pricing-card h-100 d-flex flex-column justify-content-between">
                        <div>
                            <span class="badge bg-info text-dark mb-2">ENTERPRISE</span>
                            <h3 class="fw-bold mb-1">199 € <span class="fs-6 fw-normal text-muted">/ mes</span></h3>
                            <p class="text-muted small mb-4">Para grandes consultorías y corporaciones.</p>
                            <ul class="list-unstyled small text-muted mb-4">
                                <li class="mb-2">✓ <strong>500 peticiones / minuto</strong></li>
                                <li class="mb-2">✓ SLA garantizado 99.9%</li>
                                <li class="mb-2">✓ Soporte técnico prioritario</li>
                            </ul>
                        </div>
                        <button onclick="subscribePlan('enterprise')" class="btn btn-outline-info w-100 fw-semibold btn-sm">Contratar Enterprise</button>
                    </div>
                </div>
            </div>

            <!-- Caja de Credencial Generada -->
            <div id="credentialBox" class="card-saas mb-5" style="display:none; border-color: var(--accent-pro);">
                <h5 class="fw-bold text-warning mb-2"><i class="fa-solid fa-key me-2"></i>¡Suscripción Activada con Éxito!</h5>
                <p class="text-muted small mb-2">Utiliza esta API Key en el encabezado <code>X-API-KEY</code> de tus peticiones:</p>
                <code id="activeApiKey" class="text-info fs-6 d-block bg-dark p-3 rounded border border-secondary user-select-all"></code>
            </div>

            <!-- Buscador Comercial en Vivo (Sandbox) -->
            <div class="card-saas mb-5">
                <h5 class="fw-semibold mb-3"><i class="fa-solid fa-magnifying-glass me-2 text-primary"></i>Probador Comercial de Licitaciones</h5>
                <div class="row g-2 mb-4">
                    <div class="col-md-5">
                        <input type="text" id="searchInput" class="form-control" placeholder="Buscar por palabra clave...">
                    </div>
                    <div class="col-md-3">
                        <select id="searchCcaa" class="form-select">
                            <option value="">Todas las CCAA</option>
                            <option value="Madrid">Madrid</option>
                            <option value="Andalucía">Andalucía</option>
                            <option value="Cataluña">Cataluña</option>
                        </select>
                    </div>
                    <div class="col-md-2">
                        <select id="searchEstado" class="form-select">
                            <option value="">Cualquier estado</option>
                            <option value="En Plazo">En Plazo</option>
                            <option value="Adjudicado">Adjudicado</option>
                        </select>
                    </div>
                    <div class="col-md-2">
                        <button onclick="runSearch()" class="btn btn-primary w-100 fw-semibold">Consultar</button>
                    </div>
                </div>

                <div class="table-responsive">
                    <table class="table table-hover align-middle">
                        <thead>
                            <tr>
                                <th>Expediente</th>
                                <th>Objeto / Título</th>
                                <th>Órgano</th>
                                <th>CCAA</th>
                                <th>Presupuesto</th>
                                <th>Estado</th>
                            </tr>
                        </thead>
                        <tbody id="resultsTable">
                            <tr><td colspan="6" class="text-center text-muted py-4">Selecciona tu plan, genera tu API Key y realiza tu primera consulta.</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>

        </div>

        <!-- Banner Cookies RGPD -->
        <div id="cookie-banner">
            <span class="small text-muted"><i class="fa-solid fa-cookie-bite text-warning me-2"></i>Utilizamos cookies técnicas esenciales amparadas por la Ley 37/2007. Al navegar, acepta su uso.</span>
            <button onclick="acceptCookies()" class="btn btn-sm btn-light fw-bold px-3">Aceptar</button>
        </div>

        <script>
            let currentApiKey = "clave_demo_123";

            if (localStorage.getItem('cookies_accepted') === 'true') {
                document.getElementById('cookie-banner').style.display = 'none';
            }
            function acceptCookies() {
                localStorage.setItem('cookies_accepted', 'true');
                document.getElementById('cookie-banner').style.display = 'none';
            }

            async function subscribePlan(tier) {
                const res = await fetch('/commercial/subscribe', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({tier: tier})
                });
                const data = await res.json();
                if (data.api_key) {
                    currentApiKey = data.api_key;
                    document.getElementById('activeApiKey').innerText = data.api_key;
                    document.getElementById('credentialBox').style.display = 'block';
                    window.scrollTo({top: document.getElementById('credentialBox').offsetTop - 100, behavior: 'smooth'});
                }
            }

            async function runSearch() {
                const q = document.getElementById('searchInput').value;
                const ccaa = document.getElementById('searchCcaa').value;
                const estado = document.getElementById('searchEstado').value;
                const tbody = document.getElementById('resultsTable');
                
                tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-3">Consultando motor de datos...</td></tr>';

                const params = new URLSearchParams();
                if (q) params.append('q', q);
                if (ccaa) params.append('ccaa', ccaa);
                if (estado) params.append('estado', estado);

                try {
                    const res = await fetch('/tenders?' + params.toString(), {
                        headers: {'X-API-KEY': currentApiKey}
                    });
                    const data = await res.json();
                    
                    if (data.data && data.data.length > 0) {
                        tbody.innerHTML = data.data.map(t => `
                            <tr>
                                <td><code>${t.id}</code></td>
                                <td class="fw-medium">${t.titulo}</td>
                                <td class="text-muted small">${t.organo}</td>
                                <td><span class="badge bg-dark border border-secondary text-light">${t.ccaa}</span></td>
                                <td class="text-success fw-semibold">${t.presupuesto.toLocaleString()} €</td>
                                <td><span class="badge ${t.estado === 'En Plazo' ? 'bg-success bg-opacity-25 text-success' : 'bg-secondary bg-opacity-25 text-light'}">${t.estado}</span></td>
                            </tr>
                        `).join('');
                    } else {
                        tbody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No se encontraron licitaciones con esos filtros.</td></tr>';
                    }
                } catch (e) {
                    tbody.innerHTML = '<tr><td colspan="6" class="text-center text-danger py-4">Error de acceso o límite de peticiones superado. Verifica tu API Key.</td></tr>';
                }
            }
        </script>
    </body>
    </html>
    """

@app.get("/legal", response_class=HTMLResponse, include_in_schema=False)
async def legal():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head><title>Aviso Legal — PLACSP Intelligence</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body style="background:#070a11; color:#f8fafc; padding:50px; font-family:'Inter',sans-serif;">
        <div class="container" style="max-width:750px;">
            <h2 class="text-warning fw-bold mb-4">Aviso Legal, Privacidad y Ley 37/2007</h2>
            <p class="text-muted">Este servicio opera como una plataforma tecnológica de agregación y consulta optimizada de datos públicos abiertos de contratación estatal, amparada bajo la <strong>Ley 37/2007</strong> sobre reutilización de la información del sector público (RISP).</p>
            <p class="text-muted">El proveedor actúa como mero agregador tecnológico exento de responsabilidad sobre la inalterabilidad o exactitud de los datos originales institucionales de la PLACSP.</p>
            <a href="/" class="btn btn-primary btn-sm mt-4">Volver a la Plataforma</a>
        </div>
    </body>
    </html>
    """
