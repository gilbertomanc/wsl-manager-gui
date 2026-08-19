"""Panel web local (M7): dashboard en http://<bind>:<port>.

AUTENTICACION OBLIGATORIA: la clave se configura en Ajustes de la app
(ui.web_panel_password). Sin clave el panel no arranca. Todos los
endpoints /api/* exigen 'Authorization: Bearer <clave>'.
"""
from __future__ import annotations

import hmac
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

INDEX_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WSL Manager</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #14181f; color: #e8eaf0; margin: 0; padding: 16px; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .sub { color: #8b93a3; font-size: 13px; margin-bottom: 16px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
  .card { background: #1d2430; border: 1px solid #2a3344; border-radius: 10px; padding: 14px; }
  .card h3 { margin: 0 0 8px; font-size: 15px; display: flex; justify-content: space-between; align-items: center; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; }
  .dot.on { background: #2ecc71; box-shadow: 0 0 8px #2ecc7188; }
  .dot.off { background: #566070; }
  .card .row { font-size: 13px; color: #b8c0cf; margin: 3px 0; }
  .card .row b { color: #e8eaf0; font-weight: 600; }
  .btns { margin-top: 10px; display: flex; gap: 6px; flex-wrap: wrap; }
  button { background: #2a3344; color: #e8eaf0; border: 1px solid #39445c; border-radius: 6px; padding: 4px 10px; font-size: 12px; cursor: pointer; }
  button:hover { background: #35415c; }
  button.ok { background: #1f5c33; border-color: #2ecc71; }
  button.warn { background: #5c3d1f; border-color: #e67e22; }
  button.danger { background: #5c1f1f; border-color: #e74c3c; }
  .bar { height: 8px; background: #2a3344; border-radius: 4px; overflow: hidden; margin-top: 4px; }
  .bar > div { height: 100%; background: linear-gradient(90deg, #2ecc71, #f1c40f); }
  .bar > div.hot { background: #e74c3c; }
  .alert { border-left: 3px solid #e67e22; padding: 6px 10px; margin: 6px 0; font-size: 13px; background: #241f17; border-radius: 4px; }
  .muted { color: #8b93a3; font-size: 12px; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #2a3344; }
  th { color: #8b93a3; font-weight: 500; }
  #login { position: fixed; inset: 0; display: flex; align-items: center; justify-content: center; background: #10141aee; }
  #login form { background: #1d2430; border: 1px solid #2a3344; padding: 24px; border-radius: 12px; text-align: center; }
  #login input { padding: 8px 10px; border-radius: 6px; border: 1px solid #39445c; background: #14181f; color: #e8eaf0; margin: 8px 0; width: 220px; }
</style>
</head>
<body>
<h1>WSL Manager</h1>
<div class="sub">Panel de control — distros, metricas y alertas · <span id="ts">cargando...</span></div>

<div id="login" style="display:none">
  <form onsubmit="submitLogin(event)">
    <div style="font-size:15px;margin-bottom:6px">Clave del panel web</div>
    <input type="password" id="pw" autocomplete="current-password" autofocus>
    <div><button type="submit" class="ok">Entrar</button></div>
  </form>
</div>

<div class="grid" id="cards"></div>

<h2 style="font-size:15px;margin-top:22px">Metricas</h2>
<table id="metrics"><thead><tr><th>Distro</th><th>Estado</th><th>RAM usada/total</th><th>%</th><th>CPU</th><th>Uptime</th></tr></thead><tbody></tbody></table>

<h2 style="font-size:15px;margin-top:22px">Alertas recientes</h2>
<div id="alerts"><span class="muted">sin alertas</span></div>

<script>
const $ = (s) => document.querySelector(s);
let TOKEN = localStorage.getItem('wslm_token') || '';
function esc(s) { const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML; }
function askLogin() { $('#login').style.display = 'flex'; setTimeout(() => $('#pw').focus(), 50); }
function submitLogin(e) { e.preventDefault(); TOKEN = $('#pw').value.trim(); localStorage.setItem('wslm_token', TOKEN); $('#login').style.display = 'none'; load(); }
async function api(path, method = 'GET') {
  const r = await fetch(path, { method, headers: TOKEN ? { Authorization: 'Bearer ' + TOKEN } : {} });
  if (r.status === 401) { TOKEN = ''; localStorage.removeItem('wslm_token'); askLogin(); throw new Error('clave requerida'); }
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
function fmtRam(mb) { return mb == null ? '-' : (mb >= 1024 ? (mb/1024).toFixed(1)+' GB' : mb+' MB'); }
function fmtUptime(s) { if (!s) return '-'; const h = Math.floor(s/3600), m = Math.floor((s%3600)/60); return h ? h+'h '+m+'m' : m+'m'; }
function uptime(s) { return s < 60 ? Math.floor(s)+'s' : fmtUptime(s); }
function toast(msg) { $('#ts').textContent = new Date().toLocaleTimeString() + ' · ' + msg; }

async function load() {
  try {
    const st = await api('/api/status');
    $('#ts').textContent = new Date().toLocaleTimeString();
    $('#cards').innerHTML = st.distros.map(d => {
      const pct = d.ram_percent ?? null;
      const hot = pct != null && pct >= 85;
      return `<div class="card">
        <h3>${esc(d.name)} <span class="dot ${d.running ? 'on' : 'off'}"></span></h3>
        <div class="row">Estado: <b>${esc(d.state)}</b>${d.default ? ' · default' : ''}</div>
        <div class="row">IP: <b>${esc(d.ip ?? '-')}</b></div>
        <div class="row">RAM: <b>${pct != null ? pct.toFixed(0)+'%' : '-'}</b></div>
        ${pct != null ? `<div class="bar"><div class="${hot ? 'hot' : ''}" style="width:${Math.min(100, pct)}%"></div></div>` : ''}
        <div class="btns">
          ${d.running ? `<button class="danger" onclick="act('stop','${esc(d.name)}')">Detener</button>
                         <button onclick="act('restart','${esc(d.name)}')">Reiniciar</button>
                         <button onclick="act('snapshot','${esc(d.name)}')">Snapshot</button>`
                       : `<button class="ok" onclick="act('start','${esc(d.name)}')">Iniciar</button>`}
        </div>
      </div>`;
    }).join('') || '<div class="card">Sin distros detectadas</div>';

    const m = await api('/api/metrics');
    $('#metrics tbody').innerHTML = m.metrics.map(x => `<tr>
      <td>${esc(x.name)}</td><td>${x.running ? 'RUN' : 'STOP'}</td>
      <td>${fmtRam(x.ram_used_mb)} / ${fmtRam(x.ram_total_mb)}</td>
      <td>${x.ram_percent != null ? x.ram_percent.toFixed(0)+'%' : '-'}</td>
      <td>${x.cpus ?? '-'}</td><td>${uptime(x.uptime_s)}</td></tr>`).join('');

    const al = await api('/api/alerts');
    $('#alerts').innerHTML = al.alerts.length ? al.alerts.slice(0, 8).map(a =>
      `<div class="alert"><b>${esc(a.tipo)}</b> — ${esc(a.message)} <span class="muted">(${new Date(a.ts*1000).toLocaleTimeString()})</span></div>`
    ).join('') : '<span class="muted">sin alertas</span>';
  } catch (e) {
    if (e.message !== 'clave requerida') $('#ts').textContent = 'error: ' + e.message;
  }
}

async function act(action, name) {
  try { await api('/api/distros/' + encodeURIComponent(name) + '/' + action, 'POST'); toast(action + ' ' + name + ': ok'); }
  catch (e) { toast(action + ' ' + name + ': ' + e.message); }
  setTimeout(load, 800);
}
load();
setInterval(load, 3000);
</script>
</body>
</html>
"""


def _web_panel_password(cfg) -> str:
    """Clave del panel: primero SecretsStore (DPAPI), fallback a config (tests/legacy)."""
    from src.utils import secrets as sec

    store = sec.SecretsStore()
    if store.check("web_panel_password"):
        return store.get("web_panel_password")
    return cfg.ui.web_panel_password


def _require_auth(request: Request):
    """Dependencia: todos los /api/* exigen 'Authorization: Bearer <clave>'."""
    cfg = request.app.state.ctx.config  # type: ignore[attr-defined]
    password = _web_panel_password(cfg)
    header = request.headers.get("Authorization", "")
    if not password or not hmac.compare_digest(header, f"Bearer {password}"):
        raise HTTPException(status_code=401, detail="clave requerida")


def create_web_app(ctx) -> FastAPI:
    """App del panel web sobre el CliContext compartido (duck typing)."""
    from src.api.server import apply_security_headers

    app = FastAPI(title="WSL Manager Panel", version="0.1.0")
    app.state.ctx = ctx  # type: ignore[attr-defined]
    apply_security_headers(app)

    def get_ctx():
        return app.state.ctx  # type: ignore[attr-defined]

    @app.get("/", response_class=HTMLResponse)
    def index():
        return INDEX_HTML

    @app.get("/api/status", dependencies=[Depends(_require_auth)])
    def status():
        from src.core.watcher import Watcher

        c = get_ctx()
        state = Watcher(c.store, c.metrics, c.bus, c.wsl).snapshot_state()
        # adjunta ram_percent de metricas al payload de distros
        metrics = {m.name: m for m in c.resources.get_metrics()}
        for d in state["distros"]:
            m = metrics.get(d["name"])
            d["ram_percent"] = m.ram_percent if m else None
        return state

    @app.get("/api/metrics", dependencies=[Depends(_require_auth)])
    def metrics():
        c = get_ctx()
        return {"metrics": [m.to_dict() for m in c.resources.get_metrics()]}

    @app.get("/api/alerts", dependencies=[Depends(_require_auth)])
    def alerts():
        c = get_ctx()
        return {"alerts": c.metrics.list_alerts(30)}

    @app.get("/api/events", dependencies=[Depends(_require_auth)])
    def events():
        c = get_ctx()
        return {"events": c.metrics.list_events(30)}

    @app.post("/api/distros/{name}/start", dependencies=[Depends(_require_auth)])
    def start(name: str):
        c = get_ctx()
        r = c.wsl.start(name)
        if not r.ok:
            raise HTTPException(status_code=500, detail=r.error)
        c.metrics.log_event("web_start", name, "iniciada desde el panel web")
        return {"ok": True}

    @app.post("/api/distros/{name}/stop", dependencies=[Depends(_require_auth)])
    def stop(name: str):
        c = get_ctx()
        r = c.wsl.stop(name)
        if not r.ok:
            raise HTTPException(status_code=500, detail=r.error)
        c.metrics.log_event("web_stop", name, "detenida desde el panel web")
        return {"ok": True}

    @app.post("/api/distros/{name}/restart", dependencies=[Depends(_require_auth)])
    def restart(name: str):
        c = get_ctx()
        r = c.wsl.restart(name)
        if not r.ok:
            raise HTTPException(status_code=500, detail=r.error)
        return {"ok": True}

    @app.post("/api/distros/{name}/snapshot", dependencies=[Depends(_require_auth)])
    def snapshot(name: str):
        c = get_ctx()
        try:
            path = c.wsl.snapshot(name, c.config.snapshots.retention_days, c.config.snapshots.target_dir)
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail=str(e))
        size = path.stat().st_size if path.exists() else 0
        c.metrics.record_snapshot(name, str(path), size)
        return {"ok": True, "path": str(path), "size_bytes": size}

    @app.post("/api/shutdown", dependencies=[Depends(_require_auth)])
    def shutdown():
        c = get_ctx()
        r = c.wsl.shutdown_all()
        if not r.ok:
            raise HTTPException(status_code=500, detail=r.error)
        return {"ok": True}

    return app
