'use strict';

// Interfaz de configuración (RF-25, ADR-0013). JavaScript sin dependencias ni etapa de build.
//
// Reglas que esta interfaz respeta y que tests/test_interface.py comprueba:
//  - Todo dato que viene de la API se inserta con createTextNode/textContent, nunca como HTML.
//  - No hay manejadores ni estilos en línea (la página se sirve con una CSP que los bloquea).
//  - Sólo se llama a endpoints documentados en OpenAPI, a través de api().
//  - El token vive en sessionStorage y se descarta ante cualquier 401.

const API_BASE = '';
const TOKEN_KEY = 'ivostock.token';
const POLL_MS = 5000;
const PAGE_SIZE = 50;
const RUNS_PAGE_SIZE = 20;
const SUGGESTION_LIMIT = 50;
const SAMPLE_ROWS = 10;

const state = {
    user: null,
    view: null,
    poll: null,
    pollBusy: false,
    busy: 0,
    toastTimer: null,
    availableKey: '',
    providers: [],
    providerNames: new Map(),
    suggestions: null,
    linksOffset: 0,
    nextOffset: null,
    runsOffset: 0,
    nextRunsOffset: null,
};

const $ = (id) => document.getElementById(id);

// --- Utilidades de presentación -----------------------------------------------------------

const numberFormat = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 2 });
const fmtNumber = (n) => (n === null || n === undefined ? '—' : numberFormat.format(n));
const fmtPercent = (fraction) => `${fmtNumber(fraction * 100)} %`;

function fmtDate(iso) {
    if (!iso) return '—';
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('es-AR');
}

function shorten(text, max = 120) {
    if (!text) return '';
    return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

const PROPS = new Set(['value', 'checked', 'disabled', 'max', 'min']);

// Crea un elemento. Los hijos de tipo texto se agregan como nodos de texto: no se interpretan.
function h(tag, attrs = {}, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
        if (value === null || value === undefined || value === false) continue;
        if (key === 'class') el.className = value;
        else if (key === 'on') {
            for (const [name, handler] of Object.entries(value)) el.addEventListener(name, handler);
        } else if (PROPS.has(key)) el[key] = value;
        else el.setAttribute(key, value === true ? '' : String(value));
    }
    for (const child of children.flat()) {
        if (child === null || child === undefined || child === false) continue;
        el.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
}

const td = (...children) => h('td', {}, ...children);
const tdNum = (value) => h('td', { class: 'num' }, fmtNumber(value));
const button = (label, onClick, cls = '') =>
    h('button', { type: 'button', class: cls, on: { click: onClick } }, label);

function fillBody(table, rows, emptyText) {
    const tbody = table.querySelector('tbody');
    tbody.replaceChildren(...rows);
    if (rows.length === 0) {
        const columns = table.querySelectorAll('thead th').length;
        tbody.append(h('tr', {}, h('td', { colspan: columns, class: 'muted' }, emptyText)));
    }
}

function setOptions(select, options, keep = true) {
    const previous = keep ? select.value : '';
    select.replaceChildren(
        ...options.map((o) => h('option', { value: o.value, disabled: o.disabled }, o.label)),
    );
    if (previous && options.some((o) => o.value === previous && !o.disabled)) select.value = previous;
}

function showInline(element, message, kind) {
    element.textContent = message;
    element.className = `notice ${kind}`;
}

// --- Avisos y estado de carga -------------------------------------------------------------

function setBusy(delta) {
    state.busy = Math.max(0, state.busy + delta);
    $('loading-overlay').classList.toggle('hidden', state.busy === 0);
}

function toast(message, kind = 'ok') {
    const element = $('toast');
    element.textContent = message;
    element.className = kind;
    clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => element.classList.add('hidden'), 6000);
}

// --- Cliente de la API --------------------------------------------------------------------

class ApiError extends Error {
    constructor(status, message, handled = false) {
        super(message);
        this.status = status;
        this.handled = handled;
    }
}

// El detalle es un texto propio del servidor o, en un 422 de validación, una lista sin el valor
// recibido (ver ADR-0011).
function describe(data, status) {
    const detail = data && data.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
        return detail
            .map((e) => `${(e.loc || []).slice(1).join('.') || 'petición'}: ${e.msg}`)
            .join('; ');
    }
    return `Error inesperado (HTTP ${status})`;
}

// quiet: sin overlay ni aviso (sondeos); silent: sin aviso, el llamador muestra el error;
// full: devuelve { status, data } en lugar de sólo los datos.
async function api(method, path, { query, body, quiet = false, silent = false, full = false } = {}) {
    let url = API_BASE + path;
    if (query) {
        const params = new URLSearchParams();
        for (const [key, value] of Object.entries(query)) {
            if (value !== '' && value !== null && value !== undefined && value !== false) {
                params.set(key, String(value));
            }
        }
        const text = params.toString();
        if (text) url += `?${text}`;
    }
    const headers = {};
    const token = sessionStorage.getItem(TOKEN_KEY);
    if (token) headers.Authorization = `Bearer ${token}`;
    if (body !== undefined) headers['Content-Type'] = 'application/json';

    if (!quiet) setBusy(1);
    try {
        let response;
        try {
            response = await fetch(url, {
                method,
                headers,
                body: body === undefined ? undefined : JSON.stringify(body),
            });
        } catch {
            throw new ApiError(0, 'No se pudo conectar con el servidor');
        }
        let data = null;
        try {
            data = await response.json();
        } catch {
            // Sin cuerpo JSON: se informa sólo el código.
        }
        if (!response.ok) {
            if (response.status === 401 && path !== '/auth/login') {
                if (state.user) endSession('Tu sesión venció. Ingresá de nuevo.');
                else sessionStorage.removeItem(TOKEN_KEY);
                throw new ApiError(401, 'No autenticado', true);
            }
            throw new ApiError(response.status, describe(data, response.status));
        }
        return full ? { status: response.status, data } : data;
    } catch (error) {
        if (!silent && !quiet && error instanceof ApiError && !error.handled) {
            toast(error.message, 'error');
        }
        throw error;
    } finally {
        if (!quiet) setBusy(-1);
    }
}

// Los errores de la API ya se avisaron; cualquier otro es un defecto y queda en la consola.
const guard = (fn) => async (...args) => {
    try {
        await fn(...args);
    } catch (error) {
        if (!(error instanceof ApiError)) console.error(error);
    }
};

// --- Sesión y navegación ------------------------------------------------------------------

function stopPolling() {
    if (state.poll) clearInterval(state.poll);
    state.poll = null;
}

function startPolling(task) {
    stopPolling();
    state.poll = setInterval(async () => {
        if (state.pollBusy) return;
        state.pollBusy = true;
        try {
            await task();
        } catch {
            // El próximo ciclo reintenta; un 401 ya cerró la sesión.
        } finally {
            state.pollBusy = false;
        }
    }, POLL_MS);
}

function showView(name) {
    for (const section of document.querySelectorAll('.view')) {
        section.classList.toggle('hidden', section.id !== `view-${name}`);
    }
    for (const link of document.querySelectorAll('#main-nav [data-view]')) {
        if (link.dataset.view === name) link.setAttribute('aria-current', 'page');
        else link.removeAttribute('aria-current');
    }
}

const LOADERS = {
    proveedores: () => loadProviders(),
    tiendas: () => loadStores(),
    vinculacion: () => loadLinkingFilters(),
    vinculos: () => loadLinksView(),
    corridas: () => loadRunsView(),
};

function switchView(name) {
    stopPolling();
    state.view = name;
    showView(name);
    if (LOADERS[name]) guard(LOADERS[name])();
}

function startSession(username) {
    state.user = username;
    $('who').textContent = username;
    $('main-nav').classList.remove('hidden');
    switchView('proveedores');
}

function endSession(message) {
    const wasActive = state.user !== null;
    stopPolling();
    sessionStorage.removeItem(TOKEN_KEY);
    state.user = null;
    state.view = null;
    state.suggestions = null;
    $('main-nav').classList.add('hidden');
    $('who').textContent = '';
    $('login-error').classList.add('hidden');
    for (const id of ['prov-result', 'vinc-results', 'vinc-rechazos', 'prov-validation']) {
        $(id).classList.add('hidden');
    }
    showView('login');
    if (message && wasActive) toast(message, 'error');
}

async function onLogin(event) {
    event.preventDefault();
    const box = $('login-error');
    box.classList.add('hidden');
    const username = $('username').value.trim();
    const password = $('password').value;
    try {
        const session = await api('POST', '/auth/login', {
            body: { username, password },
            silent: true,
        });
        sessionStorage.setItem(TOKEN_KEY, session.token);
        $('password').value = '';
        startSession(session.username);
    } catch (error) {
        $('password').value = '';
        showInline(box, error.message, 'error');
    }
}

async function logout() {
    // Se invalida el token en el servidor; si ya no sirve, igual se cierra la sesión local.
    state.user = null;
    try {
        await api('POST', '/auth/logout', { silent: true });
    } catch {
        // Token ya vencido o servidor inaccesible: no hay nada más que revocar desde acá.
    }
    endSession();
}

async function restoreSession() {
    if (!sessionStorage.getItem(TOKEN_KEY)) return;
    $('view-login').classList.add('hidden');
    try {
        const me = await api('GET', '/auth/me', { silent: true });
        startSession(me.username);
    } catch {
        endSession();
    }
}

// --- Proveedores --------------------------------------------------------------------------

async function loadProviders() {
    const providers = await api('GET', '/providers');
    state.providers = providers;
    state.providerNames = new Map(providers.map((p) => [p.id, p.name]));
    fillBody(
        $('table-proveedores'),
        providers.map((p) =>
            h(
                'tr',
                {},
                td(String(p.id)),
                td(p.name),
                td(p.active ? 'Activo' : 'Dado de baja', h('br'), h('small', { class: 'muted' }, p.status)),
                td(fmtDate(p.next_run_at)),
                td(p.last_accepted_run === null ? '—' : `#${p.last_accepted_run}`),
                h('td', { title: p.last_error || null }, shorten(p.last_error, 120) || '—'),
                td(p.active ? button('Dar de baja', () => disableProvider(p), 'danger') : ''),
            ),
        ),
        'Todavía no hay proveedores.',
    );
}

async function onCreateProvider(event) {
    event.preventDefault();
    const box = $('prov-validation');
    box.classList.add('hidden');
    $('prov-result').classList.add('hidden');
    const name = $('prov-nombre').value.trim();
    const url = $('prov-url').value.trim();
    let result;
    try {
        result = await api('POST', '/providers', { body: { name, url }, silent: true });
    } catch (error) {
        showInline(box, error.message, 'error');
        return;
    }
    $('form-proveedor').reset();
    renderProviderResult(result);
    toast(`Proveedor «${name}» dado de alta.`);
    guard(loadProviders)();
}

function renderProviderResult(r) {
    const box = $('prov-result');
    const parts = [
        h('h3', {}, `Proveedor #${r.id} dado de alta`),
        h('p', {}, `SKU válidos: ${fmtNumber(r.sku)}`),
        h('p', {}, `Filas descartadas por error de parseo: ${fmtPercent(r.parse_error_rate)}`),
    ];
    if (r.parse_alert) {
        parts.push(
            h(
                'p',
                { class: 'notice warn' },
                'Alerta: la tasa de errores de parseo supera el 10 %. Revisá la fuente antes de vincular.',
            ),
        );
    }
    parts.push(
        h(
            'p',
            {},
            r.awaiting_first_ingest
                ? `La primera ingesta ocurre el ${fmtDate(r.next_run_at)}; hasta entonces los vínculos esperan.`
                : `Próxima ingesta: ${fmtDate(r.next_run_at)}.`,
        ),
    );

    const sample = h(
        'table',
        {},
        h('thead', {}, h('tr', {}, h('th', {}, 'SKU'), h('th', {}, 'Stock'))),
        h(
            'tbody',
            {},
            r.preview
                .slice(0, SAMPLE_ROWS)
                .map((row) => h('tr', {}, td(row.sku), tdNum(row.stock))),
        ),
    );
    parts.push(h('h4', {}, `Muestra de la fuente (primeras ${Math.min(SAMPLE_ROWS, r.preview.length)} filas)`));
    parts.push(h('div', { class: 'table-wrap' }, sample));

    if (r.suggestions.length > 0) {
        parts.push(h('h4', {}, 'Publicaciones sugeridas por tienda'));
        parts.push(
            h(
                'ul',
                {},
                r.suggestions.map((s) =>
                    h(
                        'li',
                        {},
                        `${s.store}: ${fmtNumber(s.total)} sugeridas`,
                        s.examples.length > 0
                            ? ` (por ejemplo ${s.examples
                                  .slice(0, 3)
                                  .map((e) => e.sku)
                                  .join(', ')})`
                            : '',
                    ),
                ),
            ),
        );
    }
    box.replaceChildren(...parts);
    box.classList.remove('hidden');
}

async function disableProvider(provider) {
    const question =
        `¿Dar de baja a «${provider.name}»? Se llevarán a cero todos sus vínculos antes de ` +
        'desactivarlo y no se puede deshacer.';
    if (!window.confirm(question)) return;
    try {
        const result = await api('POST', `/providers/${Number(provider.id)}/disable`);
        toast(`Baja iniciada: ${fmtNumber(result.cuts)} vínculos se llevan a cero.`);
    } catch {
        return;
    }
    await guard(loadProviders)();
}

// --- Tiendas ------------------------------------------------------------------------------

async function refreshStores(quiet) {
    const [available, stores] = await Promise.all([
        api('GET', '/stores/available', { quiet }),
        api('GET', '/stores', { quiet }),
    ]);
    renderStoreSelector(available);
    renderStoreCards(stores);
}

function renderStoreSelector(available) {
    const pending = available.filter((s) => !s.incorporated).map((s) => s.id);
    const key = pending.join(',');
    if (key !== state.availableKey) {
        state.availableKey = key;
        const options =
            pending.length === 0
                ? [{ value: '', label: 'No hay tiendas para incorporar' }]
                : [
                      { value: '', label: 'Seleccioná una tienda a incorporar…' },
                      ...pending.map((id) => ({ value: id, label: id })),
                  ];
        setOptions($('select-tienda-incorporar'), options);
    }
    $('btn-incorporar').disabled = pending.length === 0;
}

function storeProgressText(store) {
    if (store.catalog_imported) {
        return `Catálogo importado (${fmtNumber(store.processed)} publicaciones).`;
    }
    if (store.total === null) {
        return `${fmtNumber(store.processed)} publicaciones importadas (total aún desconocido).`;
    }
    return (
        `${fmtNumber(store.processed)} de ${fmtNumber(store.total)} publicaciones ` +
        `(${fmtNumber(store.progress_percent)} %).`
    );
}

function renderStoreCards(stores) {
    const container = $('tiendas-list');
    if (stores.length === 0) {
        container.replaceChildren(h('p', { class: 'muted' }, 'Todavía no hay tiendas incorporadas.'));
        return;
    }
    container.replaceChildren(
        ...stores.map((s) =>
            h(
                'div',
                { class: 'tienda-card' },
                h('h4', {}, `${s.id} · ${s.catalog_imported ? 'catálogo listo' : 'importando catálogo'}`),
                h('small', { class: 'muted' }, `Estado: ${s.status}`),
                h('progress', { max: 100, value: s.progress_percent }),
                h('small', {}, storeProgressText(s)),
                s.last_error ? h('p', { class: 'notice error' }, shorten(s.last_error, 200)) : null,
            ),
        ),
    );
}

async function loadStores() {
    try {
        await refreshStores(false);
    } finally {
        if (state.user && state.view === 'tiendas') startPolling(() => refreshStores(true));
    }
}

async function onIncorporate() {
    const store = $('select-tienda-incorporar').value;
    if (!store) {
        toast('Seleccioná una tienda.', 'error');
        return;
    }
    let result;
    try {
        result = await api('POST', '/stores', { body: { store }, full: true });
    } catch {
        return;
    }
    toast(
        result.status === 201
            ? `Tienda ${store} incorporada. Su catálogo se importa en segundo plano.`
            : `La tienda ${store} ya estaba incorporada.`,
    );
    state.availableKey = '';
    await guard(() => refreshStores(false))();
}

// --- Vinculación --------------------------------------------------------------------------

async function loadLinkingFilters() {
    const [providers, stores] = await Promise.all([api('GET', '/providers'), api('GET', '/stores')]);
    state.providers = providers;
    state.providerNames = new Map(providers.map((p) => [p.id, p.name]));
    const active = providers.filter((p) => p.active);
    setOptions($('vinc-proveedor'), [
        { value: '', label: 'Seleccionar proveedor…' },
        ...active.map((p) => ({ value: String(p.id), label: p.name })),
    ]);
    setOptions($('vinc-tienda'), [
        { value: '', label: 'Seleccionar tienda…' },
        ...stores.map((s) => ({
            value: s.id,
            disabled: !s.catalog_imported,
            label: s.catalog_imported
                ? s.id
                : `${s.id} (importando, ${fmtNumber(s.progress_percent)} %)`,
        })),
    ]);
}

async function fetchSuggestions(params) {
    const result = await api('GET', `/providers/${Number(params.provider)}/suggestions`, {
        query: {
            store: params.store,
            sku: params.sku,
            limit: SUGGESTION_LIMIT,
            positive_only: params.positive,
        },
    });
    state.suggestions = { ...params, total: result.total };
    renderSuggestions(result);
}

async function onSearch() {
    const provider = $('vinc-proveedor').value;
    const store = $('vinc-tienda').value;
    if (!provider || !store) {
        toast('Elegí un proveedor y una tienda con catálogo importado.', 'error');
        return;
    }
    $('vinc-rechazos').classList.add('hidden');
    await guard(fetchSuggestions)({
        provider: Number(provider),
        store,
        sku: $('vinc-sku').value.trim(),
        positive: $('vinc-positivo').checked,
    });
}

function renderSuggestions(result) {
    const search = state.suggestions;
    const filtered = Boolean(search.sku);
    $('vinc-results').classList.remove('hidden');
    $('vinc-resumen').textContent =
        `${fmtNumber(result.items.length)} mostradas de ${fmtNumber(result.total)} sugerencias ` +
        `para ${state.providerNames.get(search.provider) || `el proveedor #${search.provider}`} en ${search.store}.`;
    $('vinc-hint').classList.toggle('hidden', !filtered);
    $('btn-aprobar-todo').disabled = filtered || result.total === 0;
    $('btn-aprobar-cantidad').disabled = filtered || result.total === 0;
    $('btn-aprobar-seleccion').disabled = result.items.length === 0;
    $('check-all').checked = false;
    fillBody(
        $('table-vinculacion'),
        result.items.map((item) =>
            h(
                'tr',
                {},
                td(h('input', { type: 'checkbox', class: 'check-sku', value: item.item_id })),
                td(item.sku),
                td(item.item_id),
                tdNum(item.desired),
                tdNum(item.confirmed),
            ),
        ),
        'No hay sugerencias con esos criterios.',
    );
}

async function approve(selection, description) {
    const search = state.suggestions;
    if (!search) {
        toast('Primero buscá sugerencias.', 'error');
        return;
    }
    const box = $('vinc-rechazos');
    box.classList.add('hidden');
    let result;
    try {
        result = await api('POST', `/providers/${Number(search.provider)}/approve`, {
            body: { store: search.store, positive_only: search.positive, ...selection },
            silent: true,
        });
    } catch (error) {
        if (error.handled) return;
        // El servidor rechaza la petición completa (RF-07): no se creó ningún vínculo.
        $('vinc-rechazo-texto').textContent = error.message;
        box.classList.remove('hidden');
        return;
    }
    toast(
        `Se aprobaron ${fmtNumber(result.approved)} vínculos (${description}).` +
            (result.awaiting_ingest
                ? ' Esperan la primera ingesta del proveedor.'
                : ''),
    );
    await guard(fetchSuggestions)(search);
}

function onApproveSelection() {
    const items = Array.from(document.querySelectorAll('.check-sku:checked')).map((c) => c.value);
    if (items.length === 0) {
        toast('Seleccioná al menos una publicación.', 'error');
        return;
    }
    return approve({ items }, `${items.length} seleccionadas`);
}

function onApproveCount() {
    const count = Number.parseInt($('input-cantidad').value, 10);
    if (!Number.isInteger(count) || count < 1) {
        toast('La cantidad debe ser un entero mayor que cero.', 'error');
        return;
    }
    return approve({ count }, `las primeras ${count}`);
}

function onApproveAll() {
    const search = state.suggestions;
    if (!search) {
        toast('Primero buscá sugerencias.', 'error');
        return;
    }
    if (!window.confirm(`¿Aprobar las ${fmtNumber(search.total)} sugerencias de ${search.store}?`)) {
        return;
    }
    return approve({ all: true }, 'todas las sugerencias');
}

// --- Vínculos -----------------------------------------------------------------------------

async function loadLinksView() {
    const [stores, providers] = await Promise.all([api('GET', '/stores'), api('GET', '/providers')]);
    state.providerNames = new Map(providers.map((p) => [p.id, p.name]));
    setOptions($('vinculos-tienda'), [
        { value: '', label: 'Todas las tiendas' },
        ...stores.map((s) => ({ value: s.id, label: s.id })),
    ]);
    await loadLinks(0);
}

function linkStatus(link) {
    if (link.state === 'inactive') return ['Inactivo', 'muted'];
    if (link.cut_requested) return ['Apagando…', 'warn'];
    if (link.state === 'error') return ['Con falla', 'bad'];
    if (link.awaiting_ingest) return ['Esperando ingesta', 'warn'];
    if (link.pending) return ['Publicación pendiente', 'warn'];
    return ['Activo', 'ok'];
}

function badge(label, value) {
    return h('span', { class: 'badge' }, `${label}: `, h('strong', {}, fmtNumber(value)));
}

async function loadLinks(offset) {
    const store = $('vinculos-tienda').value;
    const [summary, page] = await Promise.all([
        api('GET', '/links/summary', { query: { store } }),
        api('GET', '/links', { query: { store, limit: PAGE_SIZE, offset } }),
    ]);
    state.linksOffset = offset;
    state.nextOffset = page.next_offset;
    $('vinculos-resumen').replaceChildren(
        badge('Total', summary.total),
        badge('Sincronizados', summary.synchronized),
        badge('Pendientes', summary.pending),
        badge('Esperando ingesta', summary.awaiting_ingest),
        badge('Con falla', summary.failed),
        badge('Inactivos', summary.inactive),
    );
    fillBody(
        $('table-vinculos'),
        page.items.map((link) => {
            const [label, cls] = linkStatus(link);
            const actions = [];
            if (link.state !== 'inactive' && !link.cut_requested) {
                actions.push(button('Apagar', () => turnOffLink(link), 'danger'));
            }
            if (link.state === 'error') {
                actions.push(button('Reanudar', () => resumeLink(link), 'secondary'));
            }
            return h(
                'tr',
                {},
                td(String(link.id)),
                td(state.providerNames.get(link.provider_id) || `#${link.provider_id}`),
                td(link.store_id),
                td(link.item_id),
                td(link.sku),
                td(h('span', { class: cls }, label)),
                tdNum(link.desired),
                tdNum(link.confirmed),
                h('td', { title: link.last_error || null }, shorten(link.last_error, 80) || '—'),
                td(...actions),
            );
        }),
        'No hay vínculos para mostrar.',
    );
    $('current-page').textContent = String(Math.floor(offset / PAGE_SIZE) + 1);
    $('btn-prev-page').disabled = offset === 0;
    $('btn-next-page').disabled = page.next_offset === null;
}

async function turnOffLink(link) {
    const question =
        `¿Apagar el vínculo #${link.id} (${link.sku} en ${link.store_id})? ` +
        'Se llevará a cero la cantidad publicada.';
    if (!window.confirm(question)) return;
    try {
        await api('POST', `/links/${Number(link.id)}/off`);
        toast(`Corte ordenado para el vínculo #${link.id}.`);
    } catch {
        return;
    }
    await guard(() => loadLinks(state.linksOffset))();
}

async function resumeLink(link) {
    try {
        await api('POST', `/links/${Number(link.id)}/resume`);
        toast(`Vínculo #${link.id} reanudado.`);
    } catch {
        return;
    }
    await guard(() => loadLinks(state.linksOffset))();
}

// --- Corridas (tablero de RF-25) -----------------------------------------------------------

const RUN_STATUS = {
    accepted: ['Aceptada', 'ok'],
    quarantined: ['En cuarentena', 'warn'],
    failed: ['Fallida', 'bad'],
    interrupted: ['Interrumpida', 'bad'],
    running: ['En curso', 'warn'],
};

async function loadRunsView() {
    const providers = await api('GET', '/providers');
    state.providerNames = new Map(providers.map((p) => [p.id, p.name]));
    setOptions($('corridas-proveedor'), [
        { value: '', label: 'Todos los proveedores' },
        ...providers.map((p) => ({ value: String(p.id), label: p.name })),
    ]);
    await loadRuns(0);
    // La vista se actualiza sola mientras está abierta; el sondeo no muestra overlay ni avisos.
    startPolling(() => loadRuns(state.runsOffset, true));
}

function runDetail(run) {
    const m = run.metrics;
    if (run.error) return run.error;
    if (m.reused_inventory) return 'Fuente sin cambios: se reutilizó el inventario.';
    if (m.parse_alert) return 'Más del 10 % de filas con error de parseo.';
    if (run.status === 'quarantined') return 'Cambio sospechoso respecto de la corrida anterior.';
    return '';
}

async function loadRuns(offset, quiet = false) {
    const provider = $('corridas-proveedor').value;
    const [summary, page] = await Promise.all([
        api('GET', '/runs/summary', { query: { provider }, quiet }),
        api('GET', '/runs', {
            query: { provider, limit: RUNS_PAGE_SIZE, offset },
            quiet,
        }),
    ]);
    state.runsOffset = offset;
    state.nextRunsOffset = page.next_offset;
    $('corridas-resumen').replaceChildren(
        badge('Total', summary.total),
        badge('Aceptadas', summary.accepted),
        badge('En cuarentena', summary.quarantined),
        badge('Fallidas', summary.failed),
        badge('Interrumpidas', summary.interrupted),
        badge('En curso', summary.running),
    );
    fillBody(
        $('table-corridas'),
        page.items.map((run) => {
            const [label, cls] = RUN_STATUS[run.status] || [run.status, 'muted'];
            const m = run.metrics;
            const detail = runDetail(run);
            return h(
                'tr',
                {},
                td(`#${run.id}`, run.replay_of ? h('small', { class: 'muted' }, ` (repite #${run.replay_of})`) : null),
                td(state.providerNames.get(run.provider_id) || `#${run.provider_id}`),
                td(h('span', { class: cls }, label)),
                td(fmtDate(run.started_at)),
                td(fmtDate(run.finished_at)),
                tdNum(m.sku),
                tdNum(m.discarded),
                td(m.parse_error_rate === null || m.parse_error_rate === undefined ? '—' : fmtPercent(m.parse_error_rate)),
                h(
                    'td',
                    { title: m.p === null || m.p === undefined ? null : `Ausentes ${fmtPercent(m.D)} · a cero ${fmtPercent(m.Z)}` },
                    fmtNumber(m.p),
                ),
                h('td', { title: detail || null }, shorten(detail, 80) || '—'),
            );
        }),
        'Todavía no hay corridas.',
    );
    $('current-runs-page').textContent = String(Math.floor(offset / RUNS_PAGE_SIZE) + 1);
    $('btn-prev-runs').disabled = offset === 0;
    $('btn-next-runs').disabled = page.next_offset === null;
}

// --- Inicio -------------------------------------------------------------------------------

function init() {
    $('form-login').addEventListener('submit', onLogin);
    $('btn-logout').addEventListener('click', guard(logout));
    for (const link of document.querySelectorAll('#main-nav [data-view]')) {
        link.addEventListener('click', () => switchView(link.dataset.view));
    }
    $('form-proveedor').addEventListener('submit', guard(onCreateProvider));
    $('btn-incorporar').addEventListener('click', guard(onIncorporate));
    $('btn-buscar-sku').addEventListener('click', guard(onSearch));
    $('btn-aprobar-seleccion').addEventListener('click', guard(onApproveSelection));
    $('btn-aprobar-cantidad').addEventListener('click', guard(onApproveCount));
    $('btn-aprobar-todo').addEventListener('click', guard(onApproveAll));
    $('check-all').addEventListener('change', (event) => {
        for (const box of document.querySelectorAll('.check-sku')) box.checked = event.target.checked;
    });
    $('vinculos-tienda').addEventListener('change', guard(() => loadLinks(0)));
    $('btn-prev-page').addEventListener(
        'click',
        guard(() => loadLinks(Math.max(0, state.linksOffset - PAGE_SIZE))),
    );
    $('btn-next-page').addEventListener(
        'click',
        guard(() => loadLinks(state.nextOffset)),
    );
    $('corridas-proveedor').addEventListener('change', guard(() => loadRuns(0)));
    $('btn-prev-runs').addEventListener(
        'click',
        guard(() => loadRuns(Math.max(0, state.runsOffset - RUNS_PAGE_SIZE))),
    );
    $('btn-next-runs').addEventListener(
        'click',
        guard(() => loadRuns(state.nextRunsOffset)),
    );
    guard(restoreSession)();
}

init();
