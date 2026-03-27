import React from 'react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';

const fmt = (v) =>
  v >= 100000
    ? `₹${(v / 100000).toFixed(1)}L`
    : v >= 1000
    ? `₹${(v / 1000).toFixed(1)}K`
    : `₹${v}`;

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#fff', border: '1px solid var(--color-light-gray)',
      borderRadius: '10px', padding: '0.75rem 1rem', fontSize: '0.82rem',
      boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
    }}>
      <p style={{ fontWeight: 700, marginBottom: '4px', color: 'var(--color-graphite-black)' }}>{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color, margin: '2px 0' }}>
          {p.name}: {fmt(p.value)}
        </p>
      ))}
    </div>
  );
};

const TrendChart = ({ data }) => {
  if (!data || data.length === 0) return null;

  return (
    <div className="chart-section">
      <div className="chart-card">
        <h3>Monthly Cash Flow Trends</h3>
        <p className="chart-sub">Inflow vs Outflow over the statement period</p>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="inflowGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#7353F6" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#7353F6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="outflowGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#5CC9F5" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#5CC9F5" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#888' }} />
            <YAxis tickFormatter={fmt} tick={{ fontSize: 11, fill: '#888' }} width={60} />
            <Tooltip content={<CustomTooltip />} />
            <Legend wrapperStyle={{ fontSize: '0.82rem' }} />
            <Area type="monotone" dataKey="inflow" name="Inflow" stroke="#7353F6" strokeWidth={2} fill="url(#inflowGrad)" />
            <Area type="monotone" dataKey="outflow" name="Outflow" stroke="#5CC9F5" strokeWidth={2} fill="url(#outflowGrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="chart-card">
        <h3>Monthly Net Cash Flow</h3>
        <p className="chart-sub">Net surplus or deficit per month</p>
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
            <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#888' }} />
            <YAxis tickFormatter={fmt} tick={{ fontSize: 11, fill: '#888' }} width={60} />
            <Tooltip content={<CustomTooltip />} />
            <Bar
              dataKey="net"
              name="Net Flow"
              radius={[6, 6, 0, 0]}
              fill="#7353F6"
              label={false}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default TrendChart;
