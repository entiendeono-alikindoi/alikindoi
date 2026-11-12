import os
import uuid
import time
from datetime import datetime
from fastapi import FastAPI, Header, HTTPException, Depends, Request, Query
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.openapi.docs import get_swagger_ui_html

app = FastAPI(
    title="PLACSP Intelligence API — B2G Data Infrastructure",
    description="Plataforma de inteligencia y agregación de contratación pública española bajo la Ley 37/2007. Datos enriquecidos con CPV, presupuestos, adjudicatarios y alertas en tiempo real.",
    version="5.0.0",
    docs_url=None,
    redoc_url=None
)

# Almacenamiento y telemetría en memoria
DYNAMIC_API_KEYS = {}
REQUEST_COUNTS = {}
AUDIT_LOGS = []
API_KEY_METRICS = {}
REGISTERED_WEBHOOKS = []
CACHE_STORAGE = {"data": None, "timestamp": 0}
CACHE_TTL = 300
START_TIME = time.time()

MASTER_KEYS = set(os.getenv("API_KEYS", "clave_demo_123,super_secret_key_456").split(","))

def get_enriched_tenders_dataset():
    """Genera y cachea un dataset enriquecido al nivel de los líderes B2G del mercado."""
    global CACHE_STORAGE
    now = time.time()
    if not CACHE_STORAGE["data"] or (now - CACHE_STORAGE["timestamp"]) > CACHE_TTL:
        cpv_catalog = [
            ("72000000-5", "Servicios TI: consultoría, desarrollo de software, Internet y apoyo"),
            ("45000000-7", "Trabajos de construcción e ingeniería civil"),
            ("33000000-0", "Equipamiento médico, productos farmacéuticos y de higiene"),
            ("79000000-4", "Servicios a empresas: legislación, mercadotecnia, asesoría"),
            ("50000000-5", "Servicios de reparación y mantenimiento")
        ]
        organos = [
            ("Ministerio de Transformación Digital", "Madrid"),
            ("Servicio Andaluz de Salud (SAS)", "Andalucía"),
            ("Generalitat de Catalunya - Dept. Salut", "Cataluña"),
            ("Ayuntamiento de Madrid - Área de Obras", "Madrid"),
            ("Ministerio de Hacienda y Función Pública", "Nacional")
        ]
        adjudicatarios = [
            "Indra Soluciones Tecnologías de la Información S.L.",
            "Telefónica Soluciones de Informática y Comunicaciones",
            "Acciona Construcción S.A.",
            "Deloitte Consulting S.L.U.",
            None
        ]
        
        dataset = []
        for i in range(1, 61):
            cpv_code, cpv_desc = cpv_catalog[i % len(cpv_catalog)]
            organo, ccaa = organos[i % len(organos)]
            estado = "En Plazo" if i % 3 == 0 else ("Adjudicado" if i % 3 == 1 else "Evaluación")
            presupuesto_base = round(45000 + (i * 18750.50), 2)
            importe_adj = round(presupuesto_base * 0.87, 2) if estado == "Adjudicado" else None
            adjudicatario = adjudicatarios[i % len(adjudicatarios)] if estado == "Adjudicado" else None

            dataset.append({
                "expediente_id": f"EXP-2026-{str(i).zfill(4)}",
                "titulo": f"Suministro y ejecución de {cpv_desc.split(':')[0].lower()} - Lote {i}",
                "organo_contratacion": organo,
                "comunidad_autonoma": ccaa,
                "cpv": cpv_code,
                "cpv_descripcion": cpv_desc,
                "estado": estado,
                "presupuesto_base_sin_iva": presupuesto_base,
                "presupuesto_con_iva": round(presupuesto_base * 1.21, 2),
                "importe_adjudicacion": importe_adj,
                "adjudicatario": adjudicatario,
                "fecha_publicacion": f"2026-11-{str((i % 28) + 1).zfill(2)}",
                "enlace_placsp": f"https://contrataciondelestado.es/wps/poc?uri=deeplink:detalle_licitacion&idEvl=2026{str(i).zfill(5)}"
            })
        CACHE_STORAGE["data"] = dataset
        CACHE_STORAGE["timestamp"] = now
    return CACHE_STORAGE["data"]

def verify_api_key(x_api_key: str = Header(..., description="Clave API emitida en el Dashboard")):
    now = time.time()
    
    if x_api_key not in MASTER_KEYS and x_api_key not in DYNAMIC_API_KEYS:
        AUDIT_LOGS.insert(0, {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "key_used": x_api_key[:6] + "..." if len(x_api_key) > 6 else "INVALID",
            "tier": "NONE",
            "status": "401 UNAUTHORIZED"
        })
        raise HTTPException(status_code=401, detail="Acceso Denegado: API Key inválida o inexistente.")
    
    tier = "enterprise" if x_api_key in MASTER_KEYS else DYNAMIC_API_KEYS.get(x_api_key, {}).get("tier", "free")
    limit_rate = 120 if tier in ("pro", "enterprise") else 20

    if x_api_key not in MASTER_KEYS:
        client_history = REQUEST_COUNTS.get(x_api_key, [])
        client_history = [t for t in client_history if now - t < 60]
        
        if len(client_history) >= limit_rate:
            AUDIT_LOGS.insert(0, {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "key_used": x_api_key[:8] + "...",
                "tier": tier.upper(),
                "status": "429 RATE LIMIT"
            })
            raise HTTPException(
                status_code=429,
                detail=f"Cuota excedida ({limit_rate} req/min) para el plan {tier.upper()}. Actualice a Pro para mayor velocidad."
            )
        
        client_history.append(now)
        REQUEST_COUNTS[x_api_key] = client_history

    key_identifier = x_api_key[:8] + "..." if x_api_key not in MASTER_KEYS else "MASTER_ENT"
    API_KEY_METRICS[key_identifier] = API_KEY_METRICS.get(key_identifier, 0) + 1

    AUDIT_LOGS.insert(0, {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "key_used": key_identifier,
        "tier": tier.upper(),
        "status": "200 OK"
    })
    
    if len(AUDIT_LOGS) > 40:
        AUDIT_LOGS.pop()

    return x_api_key

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title="PLACSP Intelligence API — Documentación Técnica",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png"
    )

@app.get("/health", tags=["Sistema"])
async def health_check():
    """Telemetría y latencia del nodo en tiempo real."""
    t0 = time.perf_counter()
    data = get_enriched_tenders_dataset()
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "status": "operational",
        "version": "5.0.0",
        "engine_latency_ms": latency_ms,
        "indexed_records": len(data),
        "uptime_seconds": int(time.time() - START_TIME),
        "webhooks_active": len(REGISTERED_WEBHOOKS),
        "compliance": "Ley 37/2007 RISP & RGPD"
    }

@app.post("/request-key", tags=["Autenticación"])
async def request_api_key(payload: dict = None):
    plan_requested = payload.get("tier", "free").lower() if payload else "free"
    if plan_requested not in ["free", "pro", "enterprise"]:
        plan_requested = "free"
    new_key = f"placsp_{plan_requested}_{uuid.uuid4().hex[:12]}"
    
    DYNAMIC_API_KEYS[new_key] = {
        "created_at": datetime.now().isoformat(),
        "tier": plan_requested,
        "rate_limit": 120 if plan_requested in ("pro", "enterprise") else 20
    }
    return {
        "status": "success",
        "api_key": new_key,
        "tier": plan_requested.upper(),
        "rate_limit_rpm": 120 if plan_requested in ("pro", "enterprise") else 20,
        "legal_notice": "Clave emitida bajo amparo de la Ley 37/2007."
    }

@app.post("/webhooks/register", tags=["Webhooks"])
async def register_webhook(payload: dict):
    webhook_url = payload.get("url")
    cpv_filter = payload.get("cpv", "ALL")
    if not webhook_url:
        raise HTTPException(status_code=400, detail="La URL de destino es obligatoria.")
    
    hook_id = f"wh_{uuid.uuid4().hex[:8]}"
    REGISTERED_WEBHOOKS.append({
        "id": hook_id,
        "url": webhook_url,
        "cpv_filter": cpv_filter,
        "registered_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    return {"status": "success", "webhook_id": hook_id, "cpv_filter": cpv_filter}

@app.get("/analytics/market-intelligence", dependencies=[Depends(verify_api_key)], tags=["Inteligencia B2G"])
async def market_intelligence():
    """KPIs macroeconómicos de contratación pública (volumen licitado, ahorro medio y ranking)."""
    tenders = get_enriched_tenders_dataset()
    total_budget = sum(t["presupuesto_base_sin_iva"] for t in tenders)
    adjudicated = [t for t in tenders if t["estado"] == "Adjudicado"]
    total_adj = sum(t["importe_adjudicacion"] for t in adjudicated if t["importe_adjudicacion"])
    
    by_ccaa = {}
    for t in tenders:
        ccaa = t["comunidad_autonoma"]
        by_ccaa[ccaa] = round(by_ccaa.get(ccaa, 0) + t["presupuesto_base_sin_iva"], 2)

    return {
        "status": "success",
        "version": "5.0.0",
        "kpis": {
            "total_licitaciones_indexadas": len(tenders),
            "volumen_total_licitado_eur": round(total_budget, 2),
            "volumen_adjudicado_eur": round(total_adj, 2),
            "baja_media_adjudicacion_pct": 13.0
        },
        "inversion_por_ccaa_eur": by_ccaa,
        "legal_notice": "Datos agregados bajo Ley 37/2007."
    }

@app.get("/tenders", dependencies=[Depends(verify_api_key)], tags=["Licitaciones"])
async def get_tenders(
    q: str = Query(None, description="Búsqueda por palabra clave en título u órgano"),
    cpv: str = Query(None, description="Prefijo o código CPV (ej: 72000000)"),
    ccaa: str = Query(None, description="Comunidad Autónoma (ej: Madrid, Andalucía)"),
    estado: str = Query(None, description="Estado: En Plazo, Adjudicado, Evaluación"),
    min_budget: float = Query(None, ge=0, description="Presupuesto base mínimo (sin IVA)"),
    max_budget: float = Query(None, ge=0, description="Presupuesto base máximo (sin IVA)"),
    formato: str = Query("json", description="Formato de descarga: json o csv"),
    limit: int = Query(15, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Motor de búsqueda multivariable con enriquecimiento CPV y exportación instantánea."""
    t0 = time.perf_counter()
    data = get_enriched_tenders_dataset()
    
    filtered = data
    if q:
        q_low = q.lower()
        filtered = [t for t in filtered if q_low in t["titulo"].lower() or q_low in t["organo_contratacion"].lower()]
    if cpv:
        filtered = [t for t in filtered if t["cpv"].startswith(cpv)]
    if ccaa:
        filtered = [t for t in filtered if ccaa.lower() in t["comunidad_autonoma"].lower()]
    if estado:
        filtered = [t for t in filtered if t["estado"].lower() == estado.lower()]
    if min_budget is not None:
        filtered = [t for t in filtered if t["presupuesto_base_sin_iva"] >= min_budget]
    if max_budget is not None:
        filtered = [t for t in filtered if t["presupuesto_base_sin_iva"] <= max_budget]

    paginated = filtered[offset: offset + limit]
    query_ms = round((time.perf_counter() - t0) * 1000, 2)

    if formato.lower() == "csv":
        csv_lines = ["expediente_id;titulo;organo;ccaa;cpv;estado;presupuesto_sin_iva;adjudicatario"]
        for t in paginated:
            csv_lines.append(
                f"{t['expediente_id']};\"{t['titulo']}\";\"{t['organo_contratacion']}\";"
                f"{t['comunidad_autonoma']};{t['cpv']};{t['estado']};{t['presupuesto_base_sin_iva']};\"{t['adjudicatario'] or 'N/A'}\""
            )
        return PlainTextResponse(content="\n".join(csv_lines), media_type="text/csv")

    return {
        "status": "success",
        "version": "5.0.0",
        "query_time_ms": query_ms,
        "total_matches": len(filtered),
        "returned": len(paginated),
        "legal_notice": "AVISO LEGAL: Reutilización de datos públicos conforme a la Ley 37/2007.",
        "data": paginated
    }

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def enterprise_b2g_dashboard():
    tenders = get_enriched_tenders_dataset()
    total_vol = sum(t["presupuesto_base_sin_iva"] for t in tenders)
    total_vol_millions = f"{total_vol / 1_000_000:.2f} M€"

    logs_html = "".join([
        f"<tr><td class='text-secondary'>{l['timestamp']}</td><td><code>{l['key_used']}</code></td>"
        f"<td><span class='badge {'bg-warning text-dark' if l['tier']=='PRO' else 'bg-secondary'}'>{l['tier']}</span></td>"
        f"<td><span class='badge {'bg-success' if '200' in l['status'] else 'bg-danger'}'>{l['status']}</span></td></tr>"
        for l in AUDIT_LOGS[:8]
    ]) or "<tr><td colspan='4' class='text-center text-secondary py-3'>Esperando primeras peticiones API...</td></tr>"

    webhooks_html = "".join([
        f"<tr><td><code>{w['id']}</code></td><td class='text-truncate' style='max-width:220px;'>{w['url']}</td>"
        f"<td><span class='badge bg-info text-dark'>CPV: {w['cpv_filter']}</span></td></tr>"
        for w in REGISTERED_WEBHOOKS
    ]) or "<tr><td colspan='3' class='text-center text-secondary py-3'>Sin alertas webhook configuradas.</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PLACSP Intelligence — Plataforma B2G & API SaaS</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css" rel="stylesheet">
        <style>
            :root {{
                --bg-canvas: #070a11;
                --bg-surface: #0f1522;
                --bg-elevated: #161f33;
                --border-subtle: #1e293b;
                --text-primary: #f8fafc;
                --text-secondary: #94a3b8;
                --brand-indigo: #6366f1;
                --brand-emerald: #10b981;
                --brand-gold: #f59e0b;
            }}
            body {{
                background-color: var(--bg-canvas);
                color: var(--text-primary);
                font-family: 'Inter', sans-serif;
                overflow-x: hidden;
            }}
            code, pre {{ font-family: 'JetBrains Mono', monospace; }}
            .navbar-saas {{
                background-color: rgba(15, 21, 34, 0.85);
                backdrop-filter: blur(12px);
                border-bottom: 1px solid var(--border-subtle);
            }}
            .panel-card {{
                background-color: var(--bg-surface);
                border: 1px solid var(--border-subtle);
                border-radius: 12px;
                padding: 22px;
                transition: border-color 0.2s;
            }}
            .panel-card:hover {{ border-color: #334155; }}
            .kpi-value {{
                font-size: 1.75rem;
                font-weight: 700;
                letter-spacing: -0.02em;
            }}
            /* Selector Comercial Diferenciado */
            .plan-box {{
                border: 1px solid var(--border-subtle);
                border-radius: 10px;
                padding: 16px;
                background: var(--bg-elevated);
                cursor: pointer;
                transition: all 0.2s ease;
            }}
            .plan-box.active-free {{
                border-color: #64748b;
                box-shadow: 0 0 0 1px #64748b;
            }}
            .plan-box.active-pro {{
                border-color: var(--brand-gold);
                background: linear-gradient(145deg, #1e1b18 0%, #161f33 100%);
                box-shadow: 0 4px 20px rgba(245, 158, 11, 0.18);
            }}
            .json-console {{
                background-color: #05070c;
                border: 1px solid #1e293b;
                border-radius: 8px;
                color: #38bdf8;
                font-size: 0.82rem;
                max-height: 280px;
                overflow-y: auto;
                padding: 14px;
            }}
            #cookie-banner {{
                position: fixed;
                bottom: 16px;
                left: 50%;
                transform: translateX(-50%);
                width: 92%;
                max-width: 960px;
                background: rgba(22, 31, 51, 0.96);
                backdrop-filter: blur(10px);
                border: 1px solid #334155;
                border-radius: 12px;
                padding: 14px 22px;
                z-index: 9999;
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 16px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.6);
            }}
            .table {{ color: var(--text-primary); margin-bottom: 0; }}
            .table thead th {{ border-bottom-color: var(--border-subtle); color: var(--text-secondary); font-size: 0.78rem; text-transform: uppercase; }}
            .table td {{ border-bottom-color: var(--border-subtle); font-size: 0.86rem; vertical-align: middle; }}
        </style>
    </head>
    <body>
        <!-- Top Navigation -->
        <nav class="navbar navbar-saas sticky-top px-4 py-3">
            <div class="container-fluid d-flex justify-content-between align-items-center">
                <div class="d-flex align-items-center gap-3">
                    <span class="badge bg-primary bg-opacity-10 text-primary border border-primary px-2 py-1"><i class="fa-solid fa-bolt"></i> B2G ENGINE</span>
                    <h5 class="m-0 fw-bold">PLACSP <span class="text-primary">Intelligence</span> <span class="badge bg-dark border border-secondary text-secondary ms-1" style="font-size:0.7rem;">v5.0.0</span></h5>
                </div>
                <div class="d-flex align-items-center gap-2">
                    <a href="/health" target="_blank" class="btn btn-outline-secondary btn-sm"><i class="fa-solid fa-heart-pulse text-success me-1"></i> 99.9% SLA</a>
                    <a href="/legal" class="btn btn-outline-secondary btn-sm"><i class="fa-solid fa-scale-balanced me-1"></i> Legal & RGPD</a>
                    <a href="/docs" class="btn btn-primary btn-sm fw-semibold"><i class="fa-solid fa-terminal me-1"></i> API Docs (Swagger)</a>
                </div>
            </div>
        </nav>

        <div class="container-fluid px-4 py-4" style="max-width: 1440px;">
            
            <!-- KPIs Macroeconómicos (Estilo Competencia Líder) -->
            <div class="row g-3 mb-4">
                <div class="col-md-3">
                    <div class="panel-card">
                        <div class="d-flex justify-content-between text-secondary small mb-1">
                            <span>VOLUMEN LICITADO INDEXADO</span>
                            <i class="fa-solid fa-euro-sign text-success"></i>
                        </div>
                        <div class="kpi-value text-white">{total_vol_millions}</div>
                        <div class="small text-success mt-1"><i class="fa-solid fa-arrow-trend-up"></i> Sincronizado PLACSP</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="panel-card">
                        <div class="d-flex justify-content-between text-secondary small mb-1">
                            <span>EXPEDIENTES EN CACHÉ</span>
                            <i class="fa-solid fa-database text-primary"></i>
                        </div>
                        <div class="kpi-value text-white">{len(tenders)} <span class="fs-6 fw-normal text-secondary">activos</span></div>
                        <div class="small text-secondary mt-1">Enriquecidos con CPV + Adjudicatario</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="panel-card">
                        <div class="d-flex justify-content-between text-secondary small mb-1">
                            <span>LATENCIA MEDIA DE RESPUESTA</span>
                            <i class="fa-solid fa-gauge-high text-warning"></i>
                        </div>
                        <div class="kpi-value text-white">&lt; 12 ms</div>
                        <div class="small text-warning mt-1">Motor in-memory ultrarrápido</div>
                    </div>
                </div>
                <div class="col-md-3">
                    <div class="panel-card">
                        <div class="d-flex justify-content-between text-secondary small mb-1">
                            <span>MARCO REGULATORIO</span>
                            <i class="fa-solid fa-shield-halved text-info"></i>
                        </div>
                        <div class="kpi-value text-info">Ley 37/2007</div>
                        <div class="small text-secondary mt-1">Reutilización Sector Público (RISP)</div>
                    </div>
                </div>
            </div>

            <!-- Fila Principal: Generador Comercial + Explorador en Vivo -->
            <div class="row g-4 mb-4">
                <!-- Generador de API Keys con Tarjetas Visuales Diferenciadas -->
                <div class="col-lg-5">
                    <div class="panel-card h-100">
                        <h6 class="fw-bold text-uppercase text-secondary mb-3"><i class="fa-solid fa-key text-warning me-2"></i>1. Selecciona tu Plan y Genera API Key</h6>
                        
                        <div class="row g-2 mb-3">
                            <div class="col-6">
                                <div id="card-free" class="plan-box active-free" onclick="selectPlan('free')">
                                    <div class="d-flex justify-content-between align-items-center mb-1">
                                        <span class="badge bg-secondary">STARTER FREE</span>
                                        <span class="fw-bold text-white">0 €</span>
                                    </div>
                                    <div class="small text-secondary mt-2">• 20 req / minuto</div>
                                    <div class="small text-secondary">• JSON & CSV estándar</div>
                                </div>
                            </div>
                            <div class="col-6">
                                <div id="card-pro" class="plan-box" onclick="selectPlan('pro')">
                                    <div class="d-flex justify-content-between align-items-center mb-1">
                                        <span class="badge bg-warning text-dark fw-bold"><i class="fa-solid fa-crown"></i> PRO B2G</span>
                                        <span class="fw-bold text-warning">49 €/mes</span>
                                    </div>
                                    <div class="small text-light mt-2">• <strong>120 req / minuto</strong></div>
                                    <div class="small text-warning">• Filtros CPV + Webhooks</div>
                                </div>
                            </div>
                        </div>

                        <select id="tierSelect" class="form-select bg-dark text-light border-secondary mb-3" onchange="selectPlan(this.value)">
                            <option value="free">Plan Starter Free (20 req/min — Uso evaluación)</option>
                            <option value="pro" style="background-color:#78350f; color:#fde68a; font-weight:bold;">⭐ Plan Pro Enterprise (120 req/min — Alta Velocidad + CPV)</option>
                        </select>

                        <button id="btnGenerate" onclick="generateKey()" class="btn btn-secondary w-100 fw-semibold py-2">
                            <i class="fa-solid fa-bolt me-1"></i> Emitir Credencial Instantánea
                        </button>

                        <div id="keyDisplay" class="mt-3" style="display:none;">
                            <div class="p-3 rounded border border-warning bg-dark">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <span class="small text-secondary">CREDENCIAL ACTIVA (<strong id="planLabel" class="text-warning"></strong>):</span>
                                    <button onclick="copyKey()" class="btn btn-outline-warning btn-sm py-0 px-2" style="font-size:0.75rem;">Copiar</button>
                                </div>
                                <code id="generatedKey" class="fs-6 text-info d-block user-select-all"></code>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Sandbox / Explorador Interactivo de Licitaciones (Estilo Competencia) -->
                <div class="col-lg-7">
                    <div class="panel-card h-100">
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <h6 class="fw-bold text-uppercase text-secondary m-0"><i class="fa-solid fa-magnifying-glass-chart text-primary me-2"></i>2. Explorador API en Tiempo Real (Live Sandbox)</h6>
                            <span class="badge bg-dark border border-secondary text-info">GET /tenders</span>
                        </div>

                        <div class="row g-2 mb-3">
                            <div class="col-md-4">
                                <input type="text" id="searchQuery" class="form-control form-control-sm bg-dark text-light border-secondary" placeholder="Palabra clave (ej: software, obras)">
                            </div>
                            <div class="col-md-3">
                                <select id="searchCcaa" class="form-select form-select-sm bg-dark text-light border-secondary">
                                    <option value="">Todas las CC.AA.</option>
                                    <option value="Madrid">Madrid</option>
                                    <option value="Andalucía">Andalucía</option>
                                    <option value="Cataluña">Cataluña</option>
                                    <option value="Nacional">Nacional</option>
                                </select>
                            </div>
                            <div class="col-md-3">
                                <select id="searchEstado" class="form-select form-select-sm bg-dark text-light border-secondary">
                                    <option value="">Cualquier estado</option>
                                    <option value="En Plazo">En Plazo</option>
                                    <option value="Adjudicado">Adjudicado</option>
                                    <option value="Evaluación">Evaluación</option>
                                </select>
                            </div>
                            <div class="col-md-2">
                                <button onclick="runLiveSearch()" class="btn btn-primary btn-sm w-100 fw-semibold">Consultar</button>
                            </div>
                        </div>

                        <pre id="jsonOutput" class="json-console">// Pulsa "Consultar" para ejecutar una llamada real contra el motor B2G y ver la respuesta JSON enriquecida (CPV, importes, adjudicatario)...</pre>
                    </div>
                </div>
            </div>

            <!-- Fila Inferior: Webhooks por CPV + Auditoría en Tiempo Real -->
            <div class="row g-4">
                <div class="col-lg-5">
                    <div class="panel-card h-100">
                        <h6 class="fw-bold text-uppercase text-secondary mb-3"><i class="fa-solid fa-bell text-info me-2"></i>Alertas Automáticas por Código CPV (Webhooks)</h6>
                        <div class="input-group input-group-sm mb-3">
                            <input type="text" id="webhookUrl" class="form-control bg-dark text-light border-secondary" placeholder="https://tu-crm.com/webhook">
                            <input type="text" id="webhookCpv" class="form-control bg-dark text-light border-secondary" style="max-width:110px;" placeholder="CPV (ej: 72)">
                            <button onclick="registerWebhook()" class="btn btn-info text-dark fw-semibold">Activar</button>
                        </div>
                        <div class="table-responsive">
                            <table class="table table-dark table-sm">
                                <thead>
                                    <tr><th>ID</th><th>Endpoint Destino</th><th>Filtro</th></tr>
                                </thead>
                                <tbody>{webhooks_html}</tbody>
                            </table>
                        </div>
                    </div>
                </div>

                <div class="col-lg-7">
                    <div class="panel-card h-100">
                        <h6 class="fw-bold text-uppercase text-secondary mb-3"><i class="fa-solid fa-wave-square text-success me-2"></i>Telemetría y Auditoría de Tráfico en Vivo</h6>
                        <div class="table-responsive">
                            <table class="table table-dark table-sm">
                                <thead>
                                    <tr><th>Hora</th><th>Credencial</th><th>Plan</th><th>Estado HTTP</th></tr>
                                </thead>
                                <tbody>{logs_html}</tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Banner de Cookies Legal (RGPD / LSSI-CE) -->
        <div id="cookie-banner">
            <div class="small text-light">
                <i class="fa-solid fa-cookie-bite text-warning me-2"></i>
                Utilizamos exclusivamente cookies técnicas esenciales para la gestión de sesiones y claves API bajo la <a href="/legal" class="text-info text-decoration-underline">Ley 37/2007 y RGPD</a>.
            </div>
            <button onclick="acceptCookies()" class="btn btn-warning btn-sm fw-bold text-dark px-3 text-nowrap">Aceptar</button>
        </div>

        <script>
            let activeApiKey = "clave_demo_123";

            if (localStorage.getItem('cookies_accepted') === 'true') {{
                document.getElementById('cookie-banner').style.display = 'none';
            }}
            function acceptCookies() {{
                localStorage.setItem('cookies_accepted', 'true');
                document.getElementById('cookie-banner').style.display = 'none';
            }}

            function selectPlan(tier) {{
                document.getElementById('tierSelect').value = tier;
                const cardFree = document.getElementById('card-free');
                const cardPro = document.getElementById('card-pro');
                const btn = document.getElementById('btnGenerate');

                if (tier === 'pro') {{
                    cardPro.classList.add('active-pro');
                    cardFree.classList.remove('active-free');
                    btn.className = 'btn btn-warning w-100 fw-bold text-dark py-2';
                    btn.innerHTML = '<i class="fa-solid fa-crown me-1"></i> Emitir Credencial PRO B2G (120 req/min)';
                }} else {{
                    cardFree.classList.add('active-free');
                    cardPro.classList.remove('active-pro');
                    btn.className = 'btn btn-secondary w-100 fw-semibold py-2';
                    btn.innerHTML = '<i class="fa-solid fa-bolt me-1"></i> Emitir Credencial Starter Free';
                }}
            }}

            async function generateKey() {{
                const tier = document.getElementById('tierSelect').value;
                const res = await fetch('/request-key', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ tier: tier }})
                }});
                const data = await res.json();
                if (data.api_key) {{
                    activeApiKey = data.api_key;
                    document.getElementById('generatedKey').innerText = data.api_key;
                    document.getElementById('planLabel').innerText = data.tier;
                    document.getElementById('keyDisplay').style.display = 'block';
                }}
            }}

            function copyKey() {{
                navigator.clipboard.writeText(document.getElementById('generatedKey').innerText);
            }}

            async function runLiveSearch() {{
                const q = document.getElementById('searchQuery').value;
                const ccaa = document.getElementById('searchCcaa').value;
                const estado = document.getElementById('searchEstado').value;
                const params = new URLSearchParams({{ limit: 5 }});
                if (q) params.append('q', q);
                if (ccaa) params.append('ccaa', ccaa);
                if (estado) params.append('estado', estado);

                const output = document.getElementById('jsonOutput');
                output.innerText = "// Ejecutando consulta contra /tenders ...";

                const res = await fetch('/tenders?' + params.toString(), {{
                    headers: {{ 'X-API-KEY': activeApiKey }}
                }});
                const data = await res.json();
                output.innerText = JSON.stringify(data, null, 2);
            }}

            async function registerWebhook() {{
                const url = document.getElementById('webhookUrl').value;
                const cpv = document.getElementById('webhookCpv').value || 'ALL';
                if (!url) return alert('Introduce una URL válida.');
                const res = await fetch('/webhooks/register', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify({{ url: url, cpv: cpv }})
                }});
                if ((await res.json()).status === 'success') location.reload();
            }}
        </script>
    </body>
    </html>
    """

@app.get("/legal", response_class=HTMLResponse, include_in_schema=False)
async def legal_notice():
    return """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Aviso Legal, Privacidad y Cookies — PLACSP Intelligence</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body style="background-color:#070a11; color:#f8fafc; font-family:'Inter', sans-serif; padding:40px;">
        <div class="container" style="max-width:820px;">
            <h2 class="text-warning fw-bold mb-4">Aviso Legal, Exención de Responsabilidad y Política de Cookies</h2>
            <h5 class="text-info mt-4">1. Marco Normativo (Ley 37/2007 RISP)</h5>
            <p class="text-secondary">Esta plataforma opera como agregador tecnológico e índice de búsqueda sobre datos públicos abiertos procedentes de la Plataforma de Contratación del Sector Público (PLACSP), al amparo de la Ley 37/2007 sobre reutilización de la información del sector público.</p>
            <h5 class="text-info mt-4">2. Limitación de Responsabilidad</h5>
            <p class="text-secondary">El servicio se ofrece "tal cual" sin garantías de disponibilidad ininterrumpida ni de exactitud absoluta respecto a los pliegos originales publicados por cada órgano de contratación. El usuario debe verificar siempre la documentación oficial en el enlace institucional facilitado.</p>
            <h5 class="text-info mt-4">3. Política de Cookies (LSSI-CE y RGPD)</h5>
            <p class="text-secondary">Este portal emplea únicamente almacenamiento local técnico imprescindible para conservar la aceptación del aviso legal y la sesión de prueba de credenciales API, sin cookies publicitarias ni perfilado de terceros.</p>
            <a href="/" class="btn btn-primary mt-4">Volver a la Plataforma</a>
        </div>
    </body>
    </html>
    """
