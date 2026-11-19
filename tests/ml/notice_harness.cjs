// Ejecuta el JavaScript real con un DOM mínimo para verificar aviso, sondeo y cierre de sesión.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

class Element {
    constructor(text = '') {
        this.children = [];
        this.text = text;
        this.classes = new Set(['hidden']);
        this.classList = {
            add: (c) => this.classes.add(c),
            remove: (c) => this.classes.delete(c),
            toggle: (c, value) => value ? this.classes.add(c) : this.classes.delete(c),
            contains: (c) => this.classes.has(c),
        };
    }
    set textContent(text) { this.text = text; this.children = []; }
    get textContent() { return this.text + this.children.map((c) => c.textContent).join(''); }
    append(child) { this.children.push(child); }
    replaceChildren(...children) { this.text = ''; this.children = children; }
    addEventListener() {}
    setAttribute() {}
    removeAttribute() {}
}

async function main() {
    const elements = new Map();
    const timers = new Map();
    const storage = new Map();
    let sequence = 0;
    let response = [];
    const context = vm.createContext({
        Node: Element, Intl, Date, URLSearchParams, console,
        document: {
            getElementById(id) {
                if (!elements.has(id)) elements.set(id, new Element());
                return elements.get(id);
            },
            createElement: () => new Element(),
            createTextNode: (text) => new Element(text),
            querySelectorAll: () => [],
        },
        sessionStorage: {
            getItem: (k) => storage.get(k) || null,
            setItem: (k, v) => storage.set(k, v),
            removeItem: (k) => storage.delete(k),
        },
        setInterval: (fn) => { timers.set(++sequence, fn); return sequence; },
        clearInterval: (id) => timers.delete(id),
        setTimeout: () => 1, clearTimeout: () => {},
        fetch: async () => ({ ok: true, status: 200, json: async () => response }),
    });
    vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), context);
    const evaluate = (code) => vm.runInContext(code, context);
    const notice = elements.get('quarantine-notice') || new Element();
    elements.set('quarantine-notice', notice);
    evaluate("renderQuarantineNotices([{name:'<img src=x onerror=alert(1)>',active:true,quarantine_run_id:7}])");
    assert.equal(notice.classList.contains('hidden'), false);
    assert.match(notice.textContent, /<img src=x onerror=alert\(1\)>.*#7/);
    assert.equal(notice.children.length, 1);
    assert.equal(notice.children[0].children.length, 1); // El nombre completo es un nodo de texto.
    evaluate("renderQuarantineNotices([{name:'P',active:true,quarantine_run_id:null}])");
    assert.equal(notice.classList.contains('hidden'), true);
    evaluate("renderQuarantineNotices([{name:'P',active:false,quarantine_run_id:7}])");
    assert.equal(notice.textContent, '');
    storage.set('ivostock.token', 'first-session');
    evaluate("state.user='operador'; startQuarantineNotices()");
    response = [{ name: 'P', active: true, quarantine_run_id: 8 }];
    await timers.get(evaluate('state.noticePoll'))();
    assert.match(notice.textContent, /P.*#8/);

    let finishRequest;
    context.fetch = () => new Promise((resolve) => { finishRequest = resolve; });
    const inFlight = timers.get(evaluate('state.noticePoll'))();
    evaluate('endSession()');
    finishRequest({ok:true, status:200, json:async () => response});
    await inFlight;
    assert.equal(notice.textContent, '');
    assert.equal(notice.classList.contains('hidden'), true);
    assert.equal(timers.size, 0);
    console.log('Aviso de cuarentena: renderizado, recuperación y cierre de sesión correctos');
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
