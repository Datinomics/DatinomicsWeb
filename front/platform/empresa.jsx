// ─────────────────────────────────────────────────────────────
// Vista Detalle de Empresa
// ─────────────────────────────────────────────────────────────

function EmpresaDetail({ empresaId, navigate, range, setRange, currency, setCurrency }) {
  const emp = EMPRESAS.find(e => e.id === empresaId);
  if (!emp) return <div className="view">Empresa no encontrada.</div>;

  const skus = SKUS_BY_EMPRESA[empresaId] || defaultSkus(emp);
  const serie = makeSerie(emp.yoy);

  // siblings in same rubro for comparison
  const peers = EMPRESAS.filter(e => e.rubro === emp.rubro && e.id !== empresaId).slice(0, 3);

  const [tab, setTab] = React.useState('overview'); // overview, skus, fuentes, exportar

  return (
    <div className="view">
      <TopBar
        title={emp.nm}
        subtitle={`${emp.rubro} · ${emp.region} · ${emp.ticker}`}
        onBack={() => navigate('explorador')}
        range={range} currency={currency}
        onRange={setRange} onCurrency={setCurrency}
      />

      <div className="emp-header card">
        <div className="emp-hd-left">
          <div className="emp-avatar lg" style={{background: emp.color}}>{emp.nm.charAt(0)}</div>
          <div>
            <h2 className="emp-hd-nm">{emp.nm}</h2>
            <div className="emp-hd-meta">
              <span className="tag">{emp.rubro}</span>
              <span className="mono ink-3">·</span>
              <span className="ink-2">{emp.region}</span>
              <span className="mono ink-3">·</span>
              <span className="mono ink-3">{emp.ticker}</span>
              <span className="mono ink-3">·</span>
              <span className="mono ink-3">{emp.skus} SKUs relevados</span>
            </div>
          </div>
        </div>
        <div className="emp-hd-right">
          <button className="btn ghost"><Icon name="bell" size={14}/> Crear alerta</button>
          <button className="btn ghost"><Icon name="pin" size={14}/> Fijar</button>
          <button className="btn primary"><Icon name="download" size={14}/> Exportar</button>
        </div>
      </div>

      <div className="tab-bar">
        {[
          {id:'overview', nm:'Resumen'},
          {id:'skus',     nm:`SKUs · ${skus.length}`},
          {id:'fuentes',  nm:'Fuentes'},
          {id:'exportar', nm:'Exportar'},
        ].map(t => (
          <button key={t.id} className={`tab ${tab===t.id?'active':''}`} onClick={() => setTab(t.id)}>
            {t.nm}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <>
          <div className="kpi-row">
            <Kpi icon="bolt"     label="Var. mensual"   value={fmtPct(emp.mom)} delta="vs. abril '26"   deltaTone={emp.mom>0?'up':'down'} big/>
            <Kpi icon="region"   label="Var. interanual" value={fmtPct(emp.yoy)} delta="jun '25"          deltaTone="up" big/>
            <Kpi icon="grid"     label="SKUs activos"    value={emp.skus}         delta="actualizados hoy" deltaTone="up"/>
            <Kpi icon="building" label="Peso en rubro"   value="14.2%"            delta="estable"          deltaTone="up"/>
          </div>

          <div className="emp-grid">
            <div className="card">
              <SectionHead right={
                <div className="legend-mini">
                  <span><i style={{background:emp.color}}></i> {emp.nm}</span>
                  <span><i style={{background:'var(--violet-300)', border:'1px dashed var(--violet-500)'}}></i> Índice general</span>
                  <span><i style={{background:'var(--ink-3)'}}></i> Promedio rubro</span>
                </div>
              }>
                EVOLUCIÓN DE PRECIOS
              </SectionHead>
              <CompareChart
                labels={MESES}
                height={260}
                series={[
                  { name: 'Índice general', color: 'var(--violet-300)', data: SERIE_GENERAL, dashed:true },
                  { name: 'Promedio rubro', color: 'var(--ink-3)',     data: makeSerie(RUBROS.find(r=>r.nm===emp.rubro)?.yoy || 40), dashed:false },
                  { name: emp.nm,           color: emp.color,           data: serie, bold:true },
                ]}
              />
            </div>

            <div className="stack-col">
              <div className="card">
                <SectionHead>COMPETENCIA</SectionHead>
                <div className="peers">
                  {peers.map(p => (
                    <button className="peer" key={p.id} onClick={() => navigate('empresa:'+p.id)}>
                      <div className="emp-avatar sm" style={{background: p.color}}>{p.nm.charAt(0)}</div>
                      <div className="peer-info">
                        <div className="peer-nm">{p.nm}</div>
                        <div className="peer-meta mono ink-3">{p.skus} SKUs</div>
                      </div>
                      <div className="peer-pct">
                        <Delta value={p.yoy}/>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className="card">
                <SectionHead>DESGLOSE</SectionHead>
                <div className="breakdown">
                  <div className="bd-row">
                    <span className="bd-lbl">Mensual</span>
                    <span className="bd-val"><Delta value={emp.mom}/></span>
                  </div>
                  <div className="bd-row">
                    <span className="bd-lbl">Trimestral</span>
                    <span className="bd-val"><Delta value={emp.mom*3 - 0.4}/></span>
                  </div>
                  <div className="bd-row">
                    <span className="bd-lbl">Semestral</span>
                    <span className="bd-val"><Delta value={emp.yoy*0.55}/></span>
                  </div>
                  <div className="bd-row">
                    <span className="bd-lbl">Interanual</span>
                    <span className="bd-val"><Delta value={emp.yoy}/></span>
                  </div>
                  <div className="bd-row total">
                    <span className="bd-lbl">vs. índice gral.</span>
                    <span className="bd-val"><Delta value={emp.yoy - 45.3}/></span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <SectionHead right={
              <div className="row-r mono">
                <button className="chip"><Icon name="filter" size={12}/> Filtros</button>
                <button className="chip"><Icon name="download" size={12}/> CSV</button>
              </div>
            }>
              SKUS RELEVADOS · TOP 8
            </SectionHead>
            <SkuTable skus={skus.slice(0, 8)} />
          </div>
        </>
      )}

      {tab === 'skus' && (
        <div className="card">
          <SectionHead right={<span className="mono ink-3">{skus.length} SKUs activos · actualizado hace 4h</span>}>
            CATÁLOGO COMPLETO
          </SectionHead>
          <SkuTable skus={skus} full/>
        </div>
      )}

      {tab === 'fuentes' && (
        <div className="card">
          <SectionHead>FUENTES DE DATOS</SectionHead>
          <div className="sources">
            <div className="src">
              <div className="src-h"><Icon name="region" size={14}/> Web pública oficial</div>
              <p>Scraping diario del catálogo online y promociones en góndola virtual.</p>
              <span className="src-meta mono">Frecuencia · diaria · 02:00 ART</span>
            </div>
            <div className="src">
              <div className="src-h"><Icon name="building" size={14}/> Trabajo de campo</div>
              <p>Relevadores físicos en sucursales muestrales (CABA, GBA, principales capitales).</p>
              <span className="src-meta mono">Frecuencia · semanal</span>
            </div>
            <div className="src">
              <div className="src-h"><Icon name="code" size={14}/> Reportes oficiales</div>
              <p>Comunicaciones a CNV, balances trimestrales y datos sectoriales públicos.</p>
              <span className="src-meta mono">Frecuencia · trimestral</span>
            </div>
          </div>
          <div className="src-note">
            <Icon name="info" size={14}/>
            <span>Cada serie incluye metadata de origen y se entrega normalizada al BCRA / IPC INDEC para comparabilidad.</span>
          </div>
        </div>
      )}

      {tab === 'exportar' && (
        <div className="card">
          <SectionHead>EXPORTAR SERIE</SectionHead>
          <div className="export-grid">
            <button className="export-opt">
              <Icon name="download" size={20}/>
              <div className="export-nm">CSV</div>
              <div className="export-desc">Una fila por mes y SKU.</div>
            </button>
            <button className="export-opt">
              <Icon name="download" size={20}/>
              <div className="export-nm">Parquet</div>
              <div className="export-desc">Optimizado para análisis.</div>
            </button>
            <button className="export-opt">
              <Icon name="download" size={20}/>
              <div className="export-nm">Excel</div>
              <div className="export-desc">Con gráficos y formato.</div>
            </button>
            <button className="export-opt">
              <Icon name="code" size={20}/>
              <div className="export-nm">cURL</div>
              <div className="export-desc">Snippet API listo.</div>
            </button>
          </div>
          <div className="code-snippet">
            <div className="code-h">
              <span className="mono">cURL</span>
              <button className="chip">Copiar</button>
            </div>
            <pre>{`curl https://api.datinomics.com/v1/empresas/${emp.id}/series \\
  -H "Authorization: Bearer $DTN_KEY" \\
  --data-urlencode "freq=monthly" \\
  --data-urlencode "since=2024-01"`}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
window.EmpresaDetail = EmpresaDetail;

function SkuTable({ skus, full=false }) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>SKU</th>
            <th className="num">Precio actual</th>
            <th className="num">Mensual</th>
            <th className="num">Interanual</th>
            {full && <th>Tendencia</th>}
            <th></th>
          </tr>
        </thead>
        <tbody>
          {skus.map((s, i) => (
            <tr key={i}>
              <td><div className="sku-nm">{s.nm}</div></td>
              <td className="num mono"><b>{fmtMoney(s.precio)}</b></td>
              <td className="num"><Delta value={s.mom}/></td>
              <td className="num"><Delta value={s.yoy}/></td>
              {full && <td><Sparkline data={makeSerie(s.yoy)} width={80} height={24}/></td>}
              <td><Icon name="chevron" size={14}/></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
window.SkuTable = SkuTable;
