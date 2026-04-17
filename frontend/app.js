/**
 * app.js — AI Early Conflict Warning System v2
 * Multi-page React Application
 */

const { useState, useEffect, useRef, useCallback } = React;

const API_BASE = 'http://localhost:8000';

const RISK_COLORS = {
  CRITICAL: '#ff1744',
  HIGH:     '#ff6d00',
  MODERATE: '#ffab00',
  LOW:      '#00e676',
};

const RISK_EMOJIS = {
  CRITICAL: '🚨',
  HIGH:     '⚠️',
  MODERATE: '⚡',
  LOW:      '✅',
};

const REGION_COORDS = {
  'South China Sea':  [12.5,  115.0],
  'Taiwan':           [23.7,  121.0],
  'Russia-Ukraine':   [49.0,   32.0],
  'Middle East':      [29.5,   45.0],
  'India-Pakistan':   [30.0,   72.0],
  'Korean Peninsula': [37.5,  127.5],
  'Horn of Africa':   [10.5,   42.0],
};

// ─────────────────────────────────────────────
// API Helper
// ─────────────────────────────────────────────
async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─────────────────────────────────────────────
// Hooks
// ─────────────────────────────────────────────
function useHashRouter() {
  const [hash, setHash] = useState(window.location.hash || '#overview');
  useEffect(() => {
    const onHashChange = () => setHash(window.location.hash || '#overview');
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);
  return hash;
}

function useClock() {
  const [time, setTime] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return time;
}

// ─────────────────────────────────────────────
// UI Components
// ─────────────────────────────────────────────
function MetricCard({ icon, label, value, sub, riskLevel, trendDirection }) {
  let valClass = '';
  if (riskLevel) valClass = riskLevel.toLowerCase();
  
  let trendIcon = '';
  let trendClass = '';
  if (trendDirection === 'escalating') { trendIcon = '⬆'; trendClass = 'trend-up'; }
  else if (trendDirection === 'de-escalating') { trendIcon = '⬇'; trendClass = 'trend-down'; }
  else if (trendDirection === 'stable') { trendIcon = '➖'; trendClass = 'trend-flat'; }

  return (
    <div className={`metric-card`}>
      <div className="metric-icon">{icon}</div>
      <div className="metric-label">{label}</div>
      <div className={`metric-value ${valClass}`}>{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
      {trendDirection && (
        <div className={`metric-trend ${trendClass}`}>
          {trendIcon} {trendDirection}
        </div>
      )}
    </div>
  );
}

function RiskGauge({ score, level }) {
  const radius = 90;
  const cx = 110;
  const cy = 110;
  const circumference = Math.PI * radius;
  const fraction = Math.min(1, Math.max(0, score / 100));
  const dashArray = `${fraction * circumference} ${circumference}`;
  const color = RISK_COLORS[level] || '#6ea8ff';

  const toRad = deg => (deg * Math.PI) / 180;
  const arcPath = `M ${cx + radius * Math.cos(toRad(180))} ${cy + radius * Math.sin(toRad(180))} A ${radius} ${radius} 0 0 1 ${cx + radius * Math.cos(toRad(0))} ${cy + radius * Math.sin(toRad(0))}`;

  return (
    <div className="gauge-container">
      <svg viewBox="0 0 220 120" className="gauge-svg">
        <path d={arcPath} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="18" strokeLinecap="round" />
        <path d={arcPath} fill="none" stroke={color} strokeWidth="18" strokeLinecap="round" strokeDasharray={dashArray}
          style={{ transition: 'stroke-dasharray 1s ease-out, stroke 0.5s ease', filter: `drop-shadow(0 0 8px ${color}88)` }} />
        <text x={cx} y={cy + 5} textAnchor="middle" fill={color} fontSize="34" fontWeight="900" fontFamily="Inter">{score}</text>
      </svg>
      <div className={`level-badge level-${level}`}>{RISK_EMOJIS[level]} {level}</div>
    </div>
  );
}

function RadarChart({ dimensions }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || !dimensions) return;
    if (chartRef.current) chartRef.current.destroy();

    const labels = Object.keys(dimensions);
    const data = Object.values(dimensions);

    chartRef.current = new Chart(canvasRef.current, {
      type: 'radar',
      data: {
        labels: labels,
        datasets: [{
          label: 'Threat Dimensions',
          data: data,
          backgroundColor: 'rgba(41, 121, 255, 0.2)',
          borderColor: '#2979ff',
          pointBackgroundColor: '#2979ff',
          borderWidth: 2,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            angleLines: { color: 'rgba(255,255,255,0.1)' },
            grid: { color: 'rgba(255,255,255,0.05)' },
            pointLabels: { color: '#7b8aaa', font: { size: 10 } },
            ticks: { display: false, max: 100, min: 0 }
          }
        },
        plugins: { legend: { display: false } }
      }
    });

    return () => chartRef.current?.destroy();
  }, [dimensions]);

  return <canvas ref={canvasRef} />;
}

function TrendLineChart({ trendData }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || !trendData) return;
    if (chartRef.current) chartRef.current.destroy();

    const labels = trendData.map(d => d.date);
    const data = trendData.map(d => d.risk);

    const gradient = canvasRef.current.getContext('2d').createLinearGradient(0, 0, 0, 200);
    gradient.addColorStop(0, 'rgba(255, 109, 0, 0.3)');
    gradient.addColorStop(1, 'rgba(255, 109, 0, 0)');

    chartRef.current = new Chart(canvasRef.current, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: 'Risk Score',
          data: data,
          borderColor: '#ff6d00',
          backgroundColor: gradient,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointBackgroundColor: '#ff6d00'
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false }, ticks: { color: '#7b8aaa', font: { size: 10 } } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#7b8aaa', font: { size: 10 } }, min: 0, max: 100 }
        },
        plugins: { legend: { display: false } }
      }
    });

    return () => chartRef.current?.destroy();
  }, [trendData]);

  return <canvas ref={canvasRef} />;
}

function ComponentChart({ components }) {
  const canvasRef = useRef(null);
  const chartRef = useRef(null);

  useEffect(() => {
    if (!canvasRef.current || !components) return;
    if (chartRef.current) chartRef.current.destroy();

    chartRef.current = new Chart(canvasRef.current, {
      type: 'bar',
      data: {
        labels: ['Sentiment', 'Keyword', 'Volume'],
        datasets: [{
          data: [components.sentiment, components.keyword, components.volume],
          backgroundColor: ['rgba(0,229,255,0.7)', 'rgba(255,109,0,0.7)', 'rgba(124,58,237,0.7)'],
          borderRadius: 4,
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#7b8aaa' } },
          y: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { color: '#7b8aaa' }, min: 0, max: 100 }
        }
      }
    });
    return () => chartRef.current?.destroy();
  }, [components]);
  return <canvas ref={canvasRef} />;
}

function ConflictMap({ regionData }) {
  const mapRef = useRef(null);
  const leafletRef = useRef(null);

  useEffect(() => {
    if (!mapRef.current) return;
    if (!leafletRef.current) {
      const map = L.map(mapRef.current, { center: [20, 50], zoom: 2 });
      L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; CartoDB', subdomains: 'abcd', maxZoom: 19
      }).addTo(map);
      leafletRef.current = { map, markers: [] };
    }

    const { map, markers } = leafletRef.current;
    markers.forEach(m => m.remove());
    leafletRef.current.markers = [];

    Object.entries(regionData).forEach(([region, data]) => {
      const coords = REGION_COORDS[region];
      if (!coords) return;
      const score = data.risk_score ?? 0;
      const level = data.risk_level ?? 'LOW';
      const color = RISK_COLORS[level] || '#6ea8ff';
      const radius = 15 + (score / 100) * 35;

      const circle = L.circleMarker(coords, { radius, fillColor: color, color: color, weight: 2, opacity: 0.9, fillOpacity: 0.25 }).addTo(map);
      
      const pulseIcon = L.divIcon({
        html: `<div style="width:${radius*2}px;height:${radius*2}px;border-radius:50%;background:${color}22;border:2px solid ${color}88;display:flex;align-items:center;justify-content:center;animation:radarPop 2s infinite"></div>`,
        className: '', iconSize: [radius*2, radius*2], iconAnchor: [radius, radius]
      });
      const marker = L.marker(coords, { icon: pulseIcon }).addTo(map);

      const summaryStr = data.alert?.summary || data.alert_summary || '';
      const popup = `<div style="font-family:Inter;min-width:200px">
        <h4 style="color:#fff;margin-bottom:8px">${region}</h4>
        <div style="display:flex;justify-content:space-between;margin-bottom:4px"><span style="color:#7b8aaa">Score</span><strong style="color:${color}">${score}</strong></div>
        <div style="font-size:0.75rem;color:#7b8aaa;margin-top:8px;line-height:1.4">${summaryStr.substring(0,100)}...</div>
      </div>`;
      circle.bindPopup(popup);
      marker.bindPopup(popup);

      leafletRef.current.markers.push(circle, marker);
    });
  }, [regionData]);

  return <div id="conflict-map" ref={mapRef} style={{height:'100%', minHeight:'300px'}} />;
}

// ─────────────────────────────────────────────
// Pages
// ─────────────────────────────────────────────

function OverviewPage() {
  const [summary, setSummary] = useState(null);
  const [hotspots, setHotspots] = useState([]);
  const [mapData, setMapData] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([apiGet('/summary'), apiGet('/hotspots'), apiGet('/alerts?limit=10')])
      .then(([sData, hData, aData]) => {
        setSummary(sData);
        setHotspots(hData.hotspots || []);
        const coords = {};
        aData.alerts?.forEach(a => coords[a.region] = { risk_score: a.risk_score, risk_level: a.risk_level, alert: a });
        setMapData(coords);
        setLoading(false);
      })
      .catch(e => { console.error(e); setLoading(false); });
  }, []);

  if (loading) return <div className="state-loading"><div className="radar-spinner"><div className="radar-ring"></div><div className="radar-ring"></div></div><div>Compiling global intelligence...</div></div>;
  if (!summary) return <div className="state-error">Failed to load overview data.</div>;

  const worst = summary.worst_region;

  return (
    <div className="page fade-in">
      <div className="card card-accent-top mb-md" style={{ background: 'var(--grad-blue)' }}>
        <h2 style={{color:'white', margin:'0 0 4px 0'}}>Global Intelligence Overview</h2>
        <p style={{color:'rgba(255,255,255,0.8)', fontSize:'0.85rem', margin:0}}>Aggregate risk assessment based on real-time NLP analysis of {summary.total_articles} operational news sources.</p>
      </div>

      <div className="metrics-row">
        <MetricCard icon="🌍" label="Global Avg Risk" value={summary.global_avg_risk} sub="/ 100" />
        <MetricCard icon="🔴" label="Critical Regions" value={summary.critical_count} riskLevel="CRITICAL" />
        <MetricCard icon="🔥" label="Worst Region" value={worst?.region} sub={`Score: ${worst?.risk_score}`} riskLevel={worst?.risk_level} />
        <MetricCard icon="📰" label="Total Articles" value={summary.total_articles} sub="In active dataset" />
      </div>

      <div className="grid-12">
        <div className="col-8 card">
          <div className="card-title"><span className="card-title-icon">🗺️</span> Global Risk Map</div>
          <div style={{height:'350px'}}><ConflictMap regionData={mapData} /></div>
        </div>
        <div className="col-4 card">
          <div className="card-title"><span className="card-title-icon">📈</span> Escalating Hotspots</div>
          <div className="alert-list" style={{maxHeight:'350px', overflowY:'auto'}}>
            {hotspots.map((h, i) => (
              <div className={`alert-row ${h.risk_level}`} style={{padding:'12px'}} key={i}>
                <div className="alert-row-body">
                  <div className="alert-row-region">{h.region}</div>
                  <div className={`metric-trend ${h.trend_direction === 'escalating' ? 'trend-up' : ''}`} style={{marginTop:0}}>
                    {h.trend_delta > 0 ? '+' : ''}{h.trend_delta} delta
                  </div>
                </div>
                <div className="alert-row-right">
                  <span className="alert-row-score" style={{color: RISK_COLORS[h.risk_level]}}>{h.risk_score}</span>
                </div>
              </div>
            ))}
            {hotspots.length === 0 && <p className="text-muted fs-sm">No escalating hotspots detected.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}


function AnalyzePage({ regions, initRegion }) {
  const [selected, setSelected] = useState(initRegion || '');
  const [data, setData] = useState(null);
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchAnalysis = async (region) => {
    if(!region) return;
    setLoading(true); setError(null); setData(null); setTrend(null);
    try {
      const [aData, tData] = await Promise.all([
        apiGet(`/analyze?region=${encodeURIComponent(region)}`),
        apiGet(`/trend?region=${encodeURIComponent(region)}`)
      ]);
      setData(aData);
      setTrend(tData);
    } catch(err) { setError(err.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { if(initRegion) fetchAnalysis(initRegion); }, [initRegion]);

  return (
    <div className="page fade-in">
      <div className="card mb-md flex items-center gap-md" style={{padding:'16px 24px'}}>
        <span className="card-title" style={{margin:0}}>Select Target</span>
        <select className="select flex-1" value={selected} onChange={e => setSelected(e.target.value)}>
          <option value="">— Choose a region —</option>
          {regions.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <button className="btn btn-primary" disabled={!selected || loading} onClick={() => fetchAnalysis(selected)}>
          {loading ? 'Analyzing...' : 'Run Analysis'}
        </button>
      </div>

      {loading && <div className="state-loading"><div className="radar-spinner"><div className="radar-ring"></div></div><p>Running NLP pipeline over latest reports...</p></div>}
      {error && <div className="state-error"><b>Analysis Failed:</b> {error}</div>}

      {!loading && !error && !data && (
        <div className="state-empty">
          <div className="empty-icon">🛰️</div>
          <h2 style={{color:'var(--text-bright)'}}>Deep Dive Analysis</h2>
          <p className="text-secondary" style={{maxWidth:'400px'}}>Select a region above to generate a comprehensive threat assessment including radar dimensions, historical trend, and NLP-annotated articles.</p>
        </div>
      )}

      {!loading && data && (
        <div className="grid-12 fade-in">
          {/* Top row */}
          <div className="col-4 card flex-col items-center">
            <div className="card-title w-full"><span className="card-title-icon">🎯</span> Composite Score</div>
            <RiskGauge score={data.risk_score} level={data.risk_level} />
            <div className={`metric-trend mt-sm fs-sm ${data.trend_direction==='escalating'?'trend-up': data.trend_direction==='de-escalating'?'trend-down':'trend-flat'}`}>
               Trend: {data.trend_direction.toUpperCase()} ({data.trend_delta > 0 ? '+':''}{data.trend_delta})
            </div>
            <div className="mt-md w-full"><ComponentChart components={data.component_scores}/></div>
          </div>
          <div className="col-4 card">
            <div className="card-title"><span className="card-title-icon">🕷️</span> Threat Dimensions</div>
            <div className="chart-wrap h280"><RadarChart dimensions={data.threat_dimensions} /></div>
          </div>
          <div className="col-4 card" style={{background: `linear-gradient(135deg, rgba(20,30,55,0.8), rgba(15,22,40,0.9))`}}>
            <div className="card-title w-full"><span className="card-title-icon">🤖</span> AI Alert Synthesis</div>
            <p style={{fontSize:'0.85rem', lineHeight:'1.6', color:'var(--text-bright)', borderLeft:`3px solid ${RISK_COLORS[data.risk_level]}`, paddingLeft:'12px'}}>
              {data.alert?.summary}
            </p>
            <div className="mt-md">
              <span className="text-muted fs-xs fw-700">KEY ENTITIES</span>
              <div className="tags mt-sm">
                {data.top_entities?.map(e => <span key={e[0]} className="tag tag-entity">{e[0]}</span>)}
              </div>
            </div>
            <div className="mt-md">
              <span className="text-muted fs-xs fw-700">KEYWORDS</span>
              <div className="tags mt-sm">
                {data.top_keywords?.slice(0,6).map((k,i) => <span key={k[0]} className={`tag tag-kw${i%5+1}`}>{k[0]}</span>)}
              </div>
            </div>
          </div>

          <div className="col-12 section-divider">
            <span className="section-divider-label">Detailed Insights</span>
            <div className="section-divider-line"></div>
          </div>

          <div className="col-6 card">
            <div className="card-title"><span className="card-title-icon">📈</span> 14-Day Risk Trend</div>
            <div className="chart-wrap h240"><TrendLineChart trendData={trend?.trend} /></div>
          </div>
          <div className="col-6 card" style={{overflowY:'auto', maxHeight:'360px'}}>
            <div className="card-title"><span className="card-title-icon">📰</span> Sourced Intelligence ({data.articles?.length || 0})</div>
            <div className="feed-list">
              {data.articles?.map(a => (
                <div className={`article-card sentiment-${a.sentiment < -0.1 ? 'neg' : a.sentiment > 0.1 ? 'pos' : 'neu'}`} key={a.id}>
                  <div className="article-meta">
                    <span className="article-source">{a.source}</span>
                    <span className="article-date">{a.date}</span>
                    <span className="sentiment-chip" style={{background: a.sentiment < -0.1 ? 'rgba(255,23,68,0.2)' : 'rgba(123,138,170,0.2)', color: a.sentiment < -0.1 ? '#ff5252' : '#7b8aaa'}}>
                      Sentiment: {a.sentiment?.toFixed(2)}
                    </span>
                  </div>
                  <div className="article-title">{a.title}</div>
                  <div className="tags">
                    {a.keywords?.map(kw => <span key={kw} className="tag" style={{borderColor:'var(--border-subtle)', color:'var(--text-secondary)'}}>{kw}</span>)}
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>
      )}
    </div>
  );
}


function ComparePage({ regions }) {
  const [r1, setR1] = useState(regions[0] || 'Russia-Ukraine');
  const [r2, setR2] = useState(regions[1] || 'Middle East');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const runCompare = async () => {
    if(!r1 || !r2) return;
    setLoading(true);
    try {
      const res = await apiGet(`/compare?regions=${encodeURIComponent(r1)},${encodeURIComponent(r2)}`);
      setData(res.results);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  };

  return (
    <div className="page fade-in">
      <div className="card mb-md flex items-center gap-md" style={{padding:'16px 24px'}}>
        <select className="select flex-1" value={r1} onChange={e=>setR1(e.target.value)}>
          {regions.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <span className="fw-900 text-muted">VS</span>
        <select className="select flex-1" value={r2} onChange={e=>setR2(e.target.value)}>
          {regions.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <button className="btn btn-purple" disabled={loading} onClick={runCompare}>{loading?'Comparing...':'Compare Regions'}</button>
      </div>

      {loading && <div className="state-loading"><div className="radar-spinner"><div className="radar-ring"></div></div><p>Running concurrent analysis...</p></div>}
      
      {!loading && data && data.length === 2 && (
        <div className="compare-grid two fade-in">
          {data.map((res, i) => (
            <div className="compare-card" key={i}>
              <div className="compare-card-header">
                <span className="compare-card-region">{res.region}</span>
                <span className={`level-badge level-${res.risk_level}`}>{res.risk_level}</span>
              </div>
              <div className="compare-card-body">
                <div className="compare-score-display">
                  <span className="compare-score-num" style={{color: RISK_COLORS[res.risk_level]}}>{res.risk_score}</span>
                  <span className="compare-score-denom">/ 100</span>
                </div>
                <div style={{fontSize:'0.85rem', color:'var(--text-secondary)', marginBottom:'16px', minHeight:'60px'}}>
                  {res.alert_summary}
                </div>
                <div className="chart-title">Threat Dimensions</div>
                <div className="chart-wrap h240 mb-md"><RadarChart dimensions={res.threat_dimensions} /></div>
                
                <div className="chart-title">Key Entities</div>
                <div className="tags mb-md">
                  {res.top_entities?.map(e => <span key={e[0]} className="tag tag-entity">{e[0]}</span>)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MapPage() {
  const [mapData, setMapData] = useState(null);
  useEffect(() => {
    apiGet('/alerts?limit=20').then(res => {
      const coords = {};
      res.alerts?.forEach(a => coords[a.region] = { risk_score: a.risk_score, risk_level: a.risk_level, alert: a });
      setMapData(coords);
    });
  }, []);

  return (
    <div className="page" style={{display:'flex', flexDirection:'column'}}>
      <div className="card flex-1 p-0" style={{padding:0, height:'calc(100vh - 120px)'}}>
        {mapData ? <ConflictMap regionData={mapData} /> : <div className="state-loading">Loading map...</div>}
      </div>
    </div>
  );
}

function AlertsPage() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('LOW');

  const fetchAlerts = () => {
    setLoading(true);
    apiGet(`/alerts?limit=50&min_level=${filter}`)
      .then(res => { setAlerts(res.alerts || []); setLoading(false); })
      .catch(e => { console.error(e); setLoading(false); });
  };
  useEffect(() => { fetchAlerts(); }, [filter]);

  return (
    <div className="page fade-in">
      <div className="card mb-md flex items-center justify-between" style={{padding:'16px 24px'}}>
        <div className="card-title" style={{margin:0}}>Global Alerts Registry</div>
        <div className="flex items-center gap-sm">
          <span className="fs-sm text-secondary fw-700">Minimum Severity:</span>
          <select className="select" value={filter} onChange={e=>setFilter(e.target.value)} style={{minWidth:'150px', padding:'6px 12px'}}>
            <option value="CRITICAL">Critical Only</option>
            <option value="HIGH">High +</option>
            <option value="MODERATE">Moderate +</option>
            <option value="LOW">All Regions</option>
          </select>
        </div>
      </div>

      <div className="card">
        {loading ? <div className="state-loading">Fetching alerts...</div> : (
          <div className="alert-list">
            {alerts.map((a, i) => (
              <div className={`alert-row ${a.risk_level}`} key={i}>
                <div className="alert-row-emoji">{RISK_EMOJIS[a.risk_level]}</div>
                <div className="alert-row-body">
                  <div className="alert-row-region">{a.region}</div>
                  <div className="alert-row-summary">{a.summary}</div>
                </div>
                <div className="alert-row-right">
                  <span className="alert-row-score" style={{color: RISK_COLORS[a.risk_level]}}>{a.risk_score}</span>
                  <span className={`level-badge level-${a.risk_level}`} style={{fontSize:'0.55rem', padding:'1px 6px'}}>{a.risk_level}</span>
                </div>
              </div>
            ))}
            {alerts.length === 0 && <div className="state-empty">No alerts match the current filter.</div>}
          </div>
        )}
      </div>
    </div>
  );
}


// ─────────────────────────────────────────────
// App Shell
// ─────────────────────────────────────────────
function App() {
  const hash = useHashRouter();
  const time = useClock();
  const [regions, setRegions] = useState([]);
  const [navRegion, setNavRegion] = useState(''); // Used to pass region to analyze page from other pages

  useEffect(() => {
    apiGet('/regions').then(d => setRegions(d.regions || []));
  }, []);

  const navItems = [
    { id: '#overview', icon: '🌍', label: 'Overview' },
    { id: '#analyze',  icon: '🔍', label: 'Analysis' },
    { id: '#compare',  icon: '⚖️', label: 'Compare' },
    { id: '#map',      icon: '🗺️', label: 'Live Map' },
    { id: '#alerts',   icon: '🚨', label: 'Global Alerts' },
  ];

  return (
    <div className="app-shell">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">🌐</div>
          <div className="brand-text">
            <div className="brand-name">AI Early Warning System</div>
            <div className="brand-version">v2.0 PRO</div>
          </div>
        </div>
        <div className="sidebar-nav">
          <div className="nav-section-label">Main Menu</div>
          {navItems.map(item => (
            <a key={item.id} href={item.id} className={`nav-item ${hash === item.id ? 'active' : ''}`}>
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </a>
          ))}
        </div>
        <div className="sidebar-status">
          <div className="status-dot online"></div>
          <span>System Sentinel Online</span>
        </div>
      </aside>

      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-page-title">
          {navItems.find(i => i.id === hash)?.label || 'Dashboard'}
        </div>
        <div className="topbar-search-wrap">
          <span className="topbar-search-icon">🔍</span>
          <input type="text" className="topbar-search" placeholder="Search Intel Regions..." />
        </div>
        <div className="topbar-actions">
          <div className="clock-display">{time.toISOString().replace('T', ' ').substring(0,19)} UTC</div>
          <button className="icon-btn" title="Settings">⚙️</button>
          <button className="icon-btn" title="Notifications">
            🔔<span className="notif-badge">3</span>
          </button>
        </div>
      </header>

      {/* Content Area */}
      <main className="content-area">
        {hash === '#overview' && <OverviewPage />}
        {hash === '#analyze'  && <AnalyzePage regions={regions} initRegion={navRegion} />}
        {hash === '#compare'  && <ComparePage regions={regions} />}
        {hash === '#map'      && <MapPage />}
        {hash === '#alerts'   && <AlertsPage />}
      </main>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
