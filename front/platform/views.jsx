// ─────────────────────────────────────────────────────────────
// Vistas: Alertas, API & docs, Rubros, Empresas (list), Ajustes
// ─────────────────────────────────────────────────────────────

// ───── ALERTAS ─────
function Alertas({ navigate, range, setRange, currency, setCurrency }) {
  const [tab, setTab] = React.useState('disparadas');

  return (
    <div className="view">
      <TopBar
        title="Alertas"
        subtitle="Monitoreá precios y rubros con umbrales personalizados."
        range={range} currency={currency}
        onRange={setRange} onCurrency={setCurrency}
      />

      <div className="kpi-row">
        <Kpi icon="bell"  label="Activas"        value="3"  delta="hoy"          deltaTone="up"/>
        <Kpi icon="bolt"  label="Disparadas 24h" value="2"  delta="+1 vs. ayer"  deltaTone="up"/>
        <Kpi icon="check" label="Reconocidas"    value="3"  delta="esta semana"  deltaTone="up"/>
        <Kpi icon="x"     label="Cerradas 7d"    value="1"  delta="estable"      deltaTone="up"/>
      </div>

      <div className="tab-bar">
        {[
          {id:'disparadas', nm:'Disparadas · 6'},
          {id:'reglas',     nm:'Reglas · 5'},
          {id:'canales',    nm:'Canales'},
        ].map(t => (
          <button key={t.id} className={`tab ${tab===t.id?'active':''}`} onClick={() => setTab(t.id)}>
            {t.nm}
          </button>
        ))}
        <div className="tab-spacer"></div>
        <button className="btn primary"><Icon name="plus" size={14}/> Nueva regla</button>
      </div>

      {tab === 'disparadas' && (
        <div className="card">
          <SectionHead right={<span className="mono ink-3">últimos 7 días</span>}>
            FEED DE ALERTAS
          </SectionHead>
          <div className="alert-feed">
            {ALERTAS_ACTIVAS.map(a => (
              <div className={`alert-i nivel-${a.nivel} estado-${a.estado}`} key={a.id}>
                <div className={`alert-pill nivel-${a.nivel}`}>
                  {a.nivel === 'crit' ? '!' : a.nivel === 'warn' ? '~' : 'i'}
                </div>
                <div className="alert-body">
                  <div className="alert-h">
                    <span className="alert-tipo mono">{a.tipo}</span>
                    <span className="alert-target">{a.target}</span>
                  </div>
                  <div className="alert-sub">
                    <span className="mono ink-3">{a.trigger}</span>
                    <span className="mono ink-3">·</span>
                    <span className="mono">actual: <b>{a.actual}</b></span>
                  </div>
                </div>
                <div className="alert-rt">
                  <span className="mono ink-3">{a.fecha}</span>
                  <span className={`status-pill ${a.estado}`}>{a.estado}</span>
                  <button className="chip"><Icon name="chevron" size={12}/></button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'reglas' && (
        <div className="card">
          <SectionHead right={
            <button className="btn ghost"><Icon name="plus" size={12}/> Nueva regla</button>
          }>
            REGLAS DE ALERTA
          </SectionHead>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th></th>
                  <th>Nombre</th>
                  <th>Tipo</th>
                  <th>Target</th>
                  <th>Condición</th>
                  <th>Canales</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {ALERTAS_REGLAS.map(r => (
                  <tr key={r.id}>
                    <td><span className={`toggle ${r.activa?'on':''}`}><span className="toggle-d"></span></span></td>
                    <td><b>{r.nm}</b></td>
                    <td><span className="tag">{r.tipo}</span></td>
                    <td className="ink-2">{r.target}</td>
                    <td><span className="mono">{r.cond}</span></td>
                    <td>
                      <div className="chan-list">
                        {r.canales.map(c => <span key={c} className="chan-pill">{c}</span>)}
                      </div>
                    </td>
                    <td><Icon name="chevron" size={14}/></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === 'canales' && (
        <div className="card">
          <SectionHead>CANALES DE NOTIFICACIÓN</SectionHead>
          <div className="canales-grid">
            <Canal nm="Email" ic="bell" desc="Notificaciones a 3 emails configurados" on />
            <Canal nm="Slack" ic="bolt" desc="Workspace BERÁ · canal #precios-alertas" on />
            <Canal nm="Webhook" ic="code" desc="POST a https://api.bera.com.ar/hooks" on />
            <Canal nm="SMS" ic="info" desc="Solo plan Enterprise" />
          </div>
        </div>
      )}
    </div>
  );
}
window.Alertas = Alertas;

function Canal({ nm, ic, desc, on }) {
  return (
    <div className={`canal ${on?'on':'off'}`}>
      <div className="canal-h">
        <div className="canal-ic"><Icon name={ic} size={16}/></div>
        <div className="canal-nm">{nm}</div>
        <span className={`toggle ${on?'on':''}`}><span className="toggle-d"></span></span>
      </div>
      <p className="canal-desc">{desc}</p>
    </div>
  );
}

// ───── API & DOCS ─────
function ApiDocs({ navigate, range, setRange, currency, setCurrency }) {
  const [endpoint, setEndpoint] = React.useState('series');
  const [lang, setLang] = React.useState('python');

  const endpoints = [
    { id: 'series',    method:'GET',  path:'/v1/series/cpi',           desc:'IPC sectorial mensual' },
    { id: 'empresas',  method:'GET',  path:'/v1/empresas/:id/series',  desc:'Serie por empresa' },
    { id: 'skus',      method:'GET',  path:'/v1/skus/:id/precios',     desc:'Histórico por SKU' },
    { id: 'rubros',    method:'GET',  path:'/v1/rubros',               desc:'Índice por rubro' },
    { id: 'alertas',   method:'POST', path:'/v1/alertas',              desc:'Crear regla de alerta' },
    { id: 'webhooks',  method:'POST', path:'/v1/webhooks',             desc:'Registrar webhook' },
  ];

  const snippets = {
    python: `from datinomics import Client

client = Client(api_key=os.environ["DTN_KEY"])

series = client.series.cpi(
    sector="indumentaria",
    freq="monthly",
    since="2024-06",
    region="AR-C"  # CABA
)

print(series.latest)
#  { "date": "2026-05-01", "index": 145.3,
#    "mom": 0.023, "yoy": 0.453, "base": 100 }`,
    js: `import { Datinomics } from '@datinomics/sdk';

const dtn = new Datinomics({ apiKey: process.env.DTN_KEY });

const series = await dtn.series.cpi({
  sector: 'indumentaria',
  freq: 'monthly',
  since: '2024-06',
  region: 'AR-C'
});

console.log(series.latest);
// { date: '2026-05-01', index: 145.3,
//   mom: 0.023, yoy: 0.453, base: 100 }`,
    curl: `curl https://api.datinomics.com/v1/series/cpi \\
  -H "Authorization: Bearer $DTN_KEY" \\
  --data-urlencode "sector=indumentaria" \\
  --data-urlencode "freq=monthly" \\
  --data-urlencode "since=2024-06" \\
  --data-urlencode "region=AR-C" \\
  -G`,
  };

  return (
    <div className="view">
      <TopBar
        title="API & docs"
        subtitle="Endpoints REST, SDKs y webhooks. Una sola key, rate-limits altos."
        range={range} currency={currency}
        onRange={setRange} onCurrency={setCurrency}
      />

      <div className="kpi-row">
        <Kpi icon="code"     label="API key"          value="dtn_•••3a9f" delta="rotada hace 21d" deltaTone="up"/>
        <Kpi icon="bolt"     label="Reqs/mes"         value="48.2k" delta="cuota: 250k"     deltaTone="up"/>
        <Kpi icon="check"    label="Uptime 30d"       value="99.98%" delta="SLA 99.9%"      deltaTone="up"/>
        <Kpi icon="download" label="Egress mes"       value="3.4 GB" delta="estable"        deltaTone="up"/>
      </div>

      <div className="api-grid">
        <div className="card">
          <SectionHead>ENDPOINTS</SectionHead>
          <div className="endpoint-list">
            {endpoints.map(ep => (
              <button
                key={ep.id}
                className={`endpoint ${endpoint===ep.id?'active':''}`}
                onClick={() => setEndpoint(ep.id)}>
                <span className={`method method-${ep.method.toLowerCase()}`}>{ep.method}</span>
                <span className="ep-path mono">{ep.path}</span>
                <span className="ep-desc">{ep.desc}</span>
              </button>
            ))}
          </div>
        </div>

        <div className="stack-col">
          <div className="card">
            <SectionHead right={
              <div className="lang-tabs">
                {['python','js','curl'].map(l => (
                  <button key={l} className={`lang-tab ${lang===l?'active':''}`} onClick={()=>setLang(l)}>
                    {l === 'js' ? 'JavaScript' : l === 'python' ? 'Python' : 'cURL'}
                  </button>
                ))}
              </div>
            }>
              SNIPPET
            </SectionHead>
            <div className="code-snippet dark">
              <pre>{snippets[lang]}</pre>
            </div>
          </div>

          <div className="card">
            <SectionHead>RESPUESTA · 200 OK</SectionHead>
            <div className="code-snippet dark">
              <pre>{`{
  "series_id": "cpi.indumentaria.ar-c",
  "base": 100,
  "base_date": "2024-06-01",
  "points": [
    { "date": "2024-06-01", "index": 100.0, "mom": null,    "yoy": null    },
    { "date": "2024-07-01", "index": 103.2, "mom": 0.032,   "yoy": null    },
    { "date": "2024-08-01", "index": 106.8, "mom": 0.0349,  "yoy": null    },
    // ...
    { "date": "2026-05-01", "index": 145.3, "mom": 0.023,   "yoy": 0.453   }
  ],
  "meta": {
    "sector": "indumentaria",
    "region": "AR-C",
    "freq":   "monthly",
    "n_empresas": 23,
    "n_skus":     141
  }
}`}</pre>
            </div>
          </div>
        </div>
      </div>

      <div className="card">
        <SectionHead right={<a className="link">Ver documentación completa →</a>}>
          LÍMITES Y CUOTAS
        </SectionHead>
        <div className="limits-grid">
          <div className="limit">
            <div className="limit-lbl">Rate limit</div>
            <div className="limit-v mono">600 <span>req/min</span></div>
          </div>
          <div className="limit">
            <div className="limit-lbl">Cuota mensual</div>
            <div className="limit-v mono">250k <span>requests</span></div>
          </div>
          <div className="limit">
            <div className="limit-lbl">Latencia p95</div>
            <div className="limit-v mono">120 <span>ms</span></div>
          </div>
          <div className="limit">
            <div className="limit-lbl">Cache</div>
            <div className="limit-v mono">15 <span>min</span></div>
          </div>
        </div>
      </div>
    </div>
  );
}
window.ApiDocs = ApiDocs;

// ───── RUBROS LIST ─────
function Rubros({ navigate, range, setRange, currency, setCurrency }) {
  return (
    <div className="view">
      <TopBar
        title="Rubros"
        subtitle="Doce rubros relevados, actualizados diariamente."
        range={range} currency={currency}
        onRange={setRange} onCurrency={setCurrency}
      />
      <div className="rubros-grid">
        {RUBROS.map(r => (
          <button key={r.id} className="rubro-tile" onClick={() => navigate('rubros')}>
            <div className="rubro-h">
              <span className="rubro-nm">{r.nm}</span>
              <Delta value={r.yoy}/>
            </div>
            <Sparkline data={makeSerie(r.yoy)} width={220} height={36}/>
            <div className="rubro-meta mono">
              <span>{r.empresas} empresas</span>
              <span className="ink-3">mensual {fmtPct(r.mom)}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
window.Rubros = Rubros;

// ───── EMPRESAS LIST ─────
function Empresas({ navigate, range, setRange, currency, setCurrency }) {
  return (
    <div className="view">
      <TopBar
        title="Empresas"
        subtitle="23 empresas argentinas relevadas en tiempo real."
        range={range} currency={currency}
        onRange={setRange} onCurrency={setCurrency}
      />
      <div className="empresas-grid">
        {EMPRESAS.map(e => (
          <button key={e.id} className="empresa-tile" onClick={() => navigate('empresa:'+e.id)}>
            <div className="emp-avatar lg" style={{background: e.color}}>{e.nm.charAt(0)}</div>
            <div className="emp-tile-info">
              <div className="emp-tile-nm">{e.nm}</div>
              <div className="emp-tile-meta mono ink-3">{e.rubro} · {e.region}</div>
            </div>
            <div className="emp-tile-stats">
              <Sparkline data={makeSerie(e.yoy)} width={70} height={26}/>
              <div className="emp-tile-pct"><Delta value={e.yoy}/></div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
window.Empresas = Empresas;

// ───── AJUSTES ─────
function Ajustes({ navigate, range, setRange, currency, setCurrency }) {
  return (
    <div className="view">
      <TopBar
        title="Ajustes"
        subtitle="Configuración de cuenta, equipo y facturación."
        range={range} currency={currency}
        onRange={setRange} onCurrency={setCurrency}
      />
      <div className="card">
        <SectionHead>PERFIL</SectionHead>
        <div className="ajustes-list">
          <div className="ajuste-row">
            <span className="ajuste-lbl">Nombre</span>
            <span className="ajuste-val">Ana Vargas</span>
          </div>
          <div className="ajuste-row">
            <span className="ajuste-lbl">Email</span>
            <span className="ajuste-val">ana@bera.com.ar</span>
          </div>
          <div className="ajuste-row">
            <span className="ajuste-lbl">Plan</span>
            <span className="ajuste-val"><span className="tag">Pro · API</span></span>
          </div>
          <div className="ajuste-row">
            <span className="ajuste-lbl">Workspace</span>
            <span className="ajuste-val">BERÁ Consultores</span>
          </div>
          <div className="ajuste-row">
            <span className="ajuste-lbl">Zona horaria</span>
            <span className="ajuste-val">America/Argentina/Buenos_Aires</span>
          </div>
        </div>
      </div>
    </div>
  );
}
window.Ajustes = Ajustes;
