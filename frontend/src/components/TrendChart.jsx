import React from 'react';
import {
  AreaChart, Area, BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';

const fmt = (v) => {
  const n = Math.abs(v);
  const prefix = v < 0 ? '-' : '';
  if (n >= 100000) return `${prefix}₹${(n / 100000).toFixed(1)}L`;
  if (n >= 1000)   return `${prefix}₹${(n / 1000).toFixed(1)}K`;
  return `${prefix}₹${n}`;
};

const PURPLE   = '#7353F6';
const SKY      = '#5CC9F5';
const GREEN    = '#4CAF82';
const ORANGE   = '#F6A623';
const RED      = '#E05252';

const QUARTER_COLORS = [PURPLE, SKY, GREEN, ORANGE];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#fff', border: '1px solid #eee',
      borderRadius: '10px', padding: '0.75rem 1rem', fontSize: '0.82rem',
      boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
    }}>
      <p style={{ fontWeight: 700, marginBottom: '4px', color: '#231F20' }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color || p.fill, margin: '2px 0' }}>
          {p.name}: {fmt(p.value)}
        </p>
      ))}
    </div>
  );
};

/* ── Section label ── */
const ChartCard = ({ title, sub, children }) => (
  <div className="chart-card">
    <h3>{title}</h3>
    <p className="chart-sub">{sub}</p>
    {children}
  </div>
);

const TrendChart = ({ monthlyData, periodData }) => {
  const hasMonthly = monthlyData && monthlyData.length > 0;
  const hasPeriod  = periodData  && periodData.length  > 1; // only show if >1 quarter

  if (!hasMonthly && !hasPeriod) return null;

  return (
    <>
      {/* ── Row 1: Monthly Inflow/Outflow + Net ─────────────────── */}
      {hasMonthly && (
        <div className="chart-section">
          <ChartCard
            title="Monthly Cash Flow Trends"
            sub="Inflow vs Outflow over the statement period"
          >
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={monthlyData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="inflowGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={PURPLE} stopOpacity={0.25} />
                    <stop offset="95%" stopColor={PURPLE} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="outflowGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={SKY} stopOpacity={0.25} />
                    <stop offset="95%" stopColor={SKY} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#888' }} />
                <YAxis tickFormatter={fmt} tick={{ fontSize: 11, fill: '#888' }} width={62} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: '0.82rem' }} />
                <Area type="monotone" dataKey="inflow"  name="Inflow"  stroke={PURPLE} strokeWidth={2} fill="url(#inflowGrad)" />
                <Area type="monotone" dataKey="outflow" name="Outflow" stroke={SKY}    strokeWidth={2} fill="url(#outflowGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard
            title="Monthly Net Cash Flow"
            sub="Surplus or deficit per month"
          >
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={monthlyData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#888' }} />
                <YAxis tickFormatter={fmt} tick={{ fontSize: 11, fill: '#888' }} width={62} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="net" name="Net Flow" radius={[6, 6, 0, 0]}>
                  {monthlyData.map((entry, i) => (
                    <Cell key={i} fill={entry.net >= 0 ? PURPLE : RED} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      {/* ── Row 2: Quarterly Comparison (only when >1 quarter) ──── */}
      {hasPeriod && (
        <div className="chart-section" style={{ marginTop: '1.5rem' }}>
          <ChartCard
            title="Quarterly Inflow vs Outflow"
            sub={`Period comparison — ${periodData.map(p => p.label).join(', ')}`}
          >
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={periodData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#888' }} />
                <YAxis tickFormatter={fmt} tick={{ fontSize: 11, fill: '#888' }} width={62} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: '0.82rem' }} />
                <Bar dataKey="total_inflow"  name="Inflow"  fill={PURPLE} radius={[5, 5, 0, 0]} />
                <Bar dataKey="total_outflow" name="Outflow" fill={SKY}    radius={[5, 5, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard
            title="Quarterly Net Cash Flow"
            sub="Net surplus or deficit per quarter"
          >
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={periodData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#888' }} />
                <YAxis tickFormatter={fmt} tick={{ fontSize: 11, fill: '#888' }} width={62} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="net_cashflow" name="Net Flow" radius={[6, 6, 0, 0]}>
                  {periodData.map((entry, i) => (
                    <Cell key={i} fill={entry.net_cashflow >= 0 ? QUARTER_COLORS[i % 4] : RED} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </div>
      )}

      {/* ── Quarterly summary cards (if multi-period) ────────────── */}
      {hasPeriod && (
        <div className="period-cards">
          {periodData.map((p, i) => {
            const net = p.net_cashflow;
            return (
              <div key={i} className="period-card" style={{ borderTop: `4px solid ${QUARTER_COLORS[i % 4]}` }}>
                <div className="period-card-label" style={{ color: QUARTER_COLORS[i % 4] }}>{p.label}</div>
                <div className="period-card-row"><span>Inflow</span>  <strong style={{ color: '#375623' }}>{fmt(p.total_inflow)}</strong></div>
                <div className="period-card-row"><span>Outflow</span> <strong>{fmt(p.total_outflow)}</strong></div>
                <div className="period-card-row">
                  <span>Net</span>
                  <strong style={{ color: net >= 0 ? '#375623' : '#C00000' }}>{fmt(net)}</strong>
                </div>
                <div className="period-card-row">
                  <span>Closing Balance</span>
                  <strong>{fmt(p.closing_balance)}</strong>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
};

export default TrendChart;
