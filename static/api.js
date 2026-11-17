/* Utilidades comunes del frontend para hablar con el backend. */
(function () {
  function toast(texto, ok) {
    const t = document.createElement('div');
    t.className = 'toast ' + (ok === false ? 'err' : 'ok');
    t.textContent = texto;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 4500);
  }

  async function api(url, opciones) {
    const r = await fetch(url, opciones);
    let datos = null;
    try { datos = await r.json(); } catch (_) { /* respuesta sin cuerpo */ }
    if (r.status === 401) { window.location.href = '/'; throw new Error('Sesión expirada'); }
    if (!r.ok) throw new Error((datos && datos.error) || 'Ocurrió un error inesperado.');
    return datos;
  }

  const getJSON = (url) => api(url);
  const postJSON = (url, cuerpo) => api(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cuerpo),
  });

  // Botón "Filtros" -> muestra/oculta el panel con id="filtersPanel"
  function iniciarFiltros() {
    const btn = document.querySelector('.btn-filters');
    const panel = document.getElementById('filtersPanel');
    if (!btn || !panel) return;
    if (panel.dataset.activo === '1') panel.classList.add('open');
    btn.addEventListener('click', () => panel.classList.toggle('open'));
  }

  window.NS = { toast, getJSON, postJSON, iniciarFiltros };
  document.addEventListener('DOMContentLoaded', iniciarFiltros);
})();
