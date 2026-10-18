// ─────────────────────────────────────────────────────────────
// Chart components — pure SVG, no libs
// ─────────────────────────────────────────────────────────────

// Sparkline (mini line chart for tables / tiles)
function Sparkline({ data, width=120, height=32, color='var(--violet-700)', accent='var(--amber)', showDot=true }) {
  if (!data || !data.length) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return [x, y];
  });
  const path = 'M ' + pts.map(p => p.join(',')).join(' L ');
  const last = pts[pts.length-1];
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{display:'block'}}>
      <path d={path} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      {showDot && <circle cx={last[0]} cy={last[1]} r="2.5" fill={accent} />}
    </svg>
  );
}

// AreaChart (with gridlines, axis labels, hover dot)
function AreaChart({ data, labels, height=260, baseLine=100 }) {
  const W = 800, H = height;
  const pad = { l: 50, r: 24, t: 16, b: 36 };
  const w = W - pad.l - pad.r;
  const h = H - pad.t - pad.b;
  const min = Math.min(...data, baseLine);
  const max = Math.max(...data);
  const range = (max - min) || 1;

  const x = (i) => pad.l + (i / (data.length-1)) * w;
  const y = (v) => pad.t + h - ((v - min) / range) * h;

  const pts = data.map((v, i) => [x(i), y(v)]);
  const path = 'M ' + pts.map(p => p.join(',')).join(' L ');
  const area = path + ` L ${x(data.length-1)},${pad.t+h} L ${x(0)},${pad.t+h} Z`;

  // y ticks
  const ticks = 4;
  const tickVals = Array.from({length: ticks+1}, (_, i) => min + (range/ticks)*i);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" style={{width:'100%', height:H, display:'block'}}>
      <defs>
        <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="var(--violet-500)" stopOpacity="0.30" />
          <stop offset="100%" stopColor="var(--violet-500)" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* gridlines */}
      {tickVals.map((v, i) => (
        <g key={i}>
          <line x1={pad.l} x2={pad.l+w} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeWidth="1" strokeDasharray={i===0?'':'2 4'} />
          <text x={pad.l-10} y={y(v)+4} fontSize="11" textAnchor="end" fill="var(--ink-3)" fontFamily="JetBrains Mono">{v.toFixed(0)}</text>
        </g>
      ))}

      {/* x labels */}
      {labels.map((l, i) => (
        (i % 2 === 0) ? <text key={i} x={x(i)} y={H-12} fontSize="10" textAnchor="middle" fill="var(--ink-3)" fontFamily="JetBrains Mono">{l}</text> : null
      ))}

      <path d={area} fill="url(#areaGrad)" />
      <path d={path} fill="none" stroke="var(--violet-700)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />

      {/* dots */}
      {pts.map((p, i) => (
        <circle key={i} cx={p[0]} cy={p[1]} r={i===pts.length-1?5:0} fill="var(--amber)" stroke="white" strokeWidth="2" />
      ))}
    </svg>
  );
}

// Horizontal bar chart (for variación por rubro)
function HBarChart({ items, max, height=null }) {
  return (
    <div className="hbar-list">
      {items.map((it, i) => {
        const pct = (it.value / max) * 100;
        return (
          <div className="hbar" key={i}>
            <div className="hbar-head">
              <span className="hbar-nm">{it.label}</span>
              <span className="hbar-v mono">{it.formatted ?? (it.value > 0 ? '+' : '') + it.value.toFixed(1) + '%'}</span>
            </div>
            <div className="hbar-track">
              <div className="hbar-fill" style={{ width: pct + '%', background: it.color || 'var(--violet-700)' }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Comparison multi-line chart (interactivo: hover muestra la empresa)
function CompareChart({ series, labels, height=240, valueFmt }) {
  const fmt = valueFmt || ((v) => v.toLocaleString('es-AR', { maximumFractionDigits: 0 }));
  const [hi, setHi] = React.useState(null);   // { i, si }
  const wrapRef = React.useRef(null);
  const W = 800, H = height;
  const pad = { l: 50, r: 24, t: 16, b: 36 };
  const w = W - pad.l - pad.r;
  const h = H - pad.t - pad.b;

  const all = series.flatMap(s => s.data);
  const min = Math.min(...all);
  const max = Math.max(...all);
  const range = max - min || 1;

  const x = (i) => pad.l + (i / (labels.length-1)) * w;
  const y = (v) => pad.t + h - ((v - min) / range) * h;

  const ticks = 4;
  const tickVals = Array.from({length: ticks+1}, (_, i) => min + (range/ticks)*i);

  const onMove = (e) => {
    const r = wrapRef.current.getBoundingClientRect();
    const vx = (e.clientX - r.left) / r.width * W;
    const vy = (e.clientY - r.top) / r.height * H;
    let i = Math.round((vx - pad.l) / w * (labels.length-1));
    i = Math.max(0, Math.min(labels.length-1, i));
    let best = 0, bd = Infinity;
    series.forEach((s, si) => { const d = Math.abs(y(s.data[i]) - vy); if (d < bd){ bd = d; best = si; } });
    setHi({ i, si: best });
  };

  return (
    <div className="cc-wrap" ref={wrapRef} onPointerMove={onMove} onPointerLeave={()=>setHi(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{width:'100%', height:H, display:'block'}}>
        {tickVals.map((v, i) => (
          <g key={i}>
            <line x1={pad.l} x2={pad.l+w} y1={y(v)} y2={y(v)} stroke="var(--line)" strokeDasharray={i===0?'':'2 4'} vectorEffect="non-scaling-stroke" />
            <text x={pad.l-10} y={y(v)+4} fontSize="11" textAnchor="end" fill="var(--ink-3)" fontFamily="JetBrains Mono">{v.toFixed(0)}</text>
          </g>
        ))}
        {labels.map((l, i) => (
          (i % 2 === 0) ? <text key={i} x={x(i)} y={H-12} fontSize="10" textAnchor="middle" fill="var(--ink-3)" fontFamily="JetBrains Mono">{l}</text> : null
        ))}
        {hi && <line x1={x(hi.i)} x2={x(hi.i)} y1={pad.t} y2={pad.t+h} stroke="var(--violet-300)" strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />}

        {series.map((s, idx) => {
          const dim = hi && hi.si !== idx;
          const pts = s.data.map((v, i) => [x(i), y(v)]);
          const path = 'M ' + pts.map(p => p.join(',')).join(' L ');
          const last = pts[pts.length-1];
          return (
            <g key={idx} style={{opacity: dim ? 0.22 : 1, transition:'opacity .12s'}}>
              <path d={path} fill="none" stroke={s.color} strokeWidth={s.bold?3:2} strokeDasharray={s.dashed?'4 4':''} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
              <circle cx={last[0]} cy={last[1]} r={s.bold?5:3.5} fill={s.color} stroke="white" strokeWidth="2" vectorEffect="non-scaling-stroke" />
              {hi && <circle cx={x(hi.i)} cy={y(s.data[hi.i])} r={hi.si===idx?5.5:3} fill={s.color} stroke="white" strokeWidth="2" vectorEffect="non-scaling-stroke" />}
            </g>
          );
        })}
      </svg>
      {hi && (
        <div className="cc-tip" style={{ left:(x(hi.i)/W*100)+'%', top:(y(series[hi.si].data[hi.i])/H*100)+'%' }}>
          <span className="cc-tip-nm"><i style={{background:series[hi.si].color}}></i>{series[hi.si].name}</span>
          <span className="cc-tip-v">{fmt(series[hi.si].data[hi.i])}</span>
          <span className="cc-tip-m">{labels[hi.i]}</span>
        </div>
      )}
    </div>
  );
}

// Donut / ring breakdown — for distribución por rubro
function DonutChart({ items, size=180, thickness=22 }) {
  const total = items.reduce((s, it) => s + it.value, 0);
  const r = (size - thickness)/2;
  const cx = size/2, cy = size/2;
  const circ = 2 * Math.PI * r;
  let acc = 0;

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{display:'block'}}>
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--line)" strokeWidth={thickness}/>
      {items.map((it, i) => {
        const frac = it.value / total;
        const len = frac * circ;
        const offset = -acc * circ;
        acc += frac;
        return (
          <circle
            key={i}
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke={it.color}
            strokeWidth={thickness}
            strokeDasharray={`${len} ${circ-len}`}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${cx} ${cy})`}
            strokeLinecap="butt"
          />
        );
      })}
    </svg>
  );
}

Object.assign(window, { Sparkline, AreaChart, HBarChart, CompareChart, DonutChart });
