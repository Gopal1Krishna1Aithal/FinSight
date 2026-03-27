import React from 'react';
import {
  AreaChart, Area, BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip,
  ResponsiveContainer, Legend,
  PieChart as RechartsPie, Pie,
} from 'recharts';
import { TrendingUp, BarChart3, PieChart as PieIcon } from 'lucide-react';

const fmt = (v) => {
  const n = Math.abs(v);
  const prefix = v < 0 ? '-' : '';
  if (n >= 100000) return `${prefix}₹${(n / 100000).toFixed(1)}L`;
  if (n >= 1000)   return `${prefix}₹${(n / 1000).toFixed(1)}K`;
  return `${prefix}₹${n}`;
};

/* ── STYLE GUIDE HEX CODES ── */
const PURPLE   = '#7353F6';
const SKY      = '#5CC9F5';
const GRAPHITE = '#2C2C2C';
const PALE     = '#EBE4FF';
const LAVENDER = '#A88BFF';

const PIE_COLORS = [PURPLE, SKY, LAVENDER, '#00C0FF', '#7E57C2', '#4FC3F7', '#B39DDB', '#81D4FA', '#9575CD', '#B0BEC5'];

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'rgba(255, 255, 255, 0.95)',
      backdropFilter: 'blur(10px)',
      border: '1px solid rgba(115, 83, 246, 0.2)',
      borderRadius: '12px',
      padding: '1rem',
      boxShadow: '0 10px 40px rgba(0,0,0,0.1)',
    }}>
      <p style={{ 
        fontFamily: 'var(--font-heading)', 
        fontSize: '1.1rem', 
        marginBottom: '0.5rem', 
        color: GRAPHITE,
        letterSpacing: '0.5px'
      }}>
        {label || payload[0].name}
      </p>
      {payload.map((p, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '1rem', margin: '4px 0' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: p.color || p.fill }} />
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#555' }}>{p.name}:</span>
          <span style={{ fontSize: '0.85rem', fontWeight: 700, fontFamily: 'monospace', marginLeft: 'auto' }}>
            {fmt(p.value)}
          </span>
        </div>
      ))}
    </div>
  );
};

const EliteChartContainer = ({ title, icon: Icon, children, fullWidth = false }) => (
  <div className={`bento-item ${fullWidth ? 'bento-full' : 'bento-wide'}`} style={{ padding: 0 }}>
    <div className="glass-card-header">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
        <Icon size={18} color={PURPLE} />
        <h3 style={{ textTransform: 'uppercase', letterSpacing: '1px' }}>{title}</h3>
      </div>
    </div>
    <div className="premium-chart-container">
      {children}
    </div>
  </div>
);

const TrendChart = ({ monthlyData, periodData, categoryData }) => {
  const hasMonthly = monthlyData && monthlyData.length > 0;
  const hasPeriod  = periodData  && periodData.length  > 1;
  const hasCategory = categoryData && categoryData.length > 0;

  if (!hasMonthly && !hasPeriod && !hasCategory) return null;

  // ── Pie Chart Aggregation Logic (Fix small slice clutter) ────────
  const processPieData = (data) => {
    if (!data || data.length === 0) return [];
    const total = data.reduce((acc, curr) => acc + curr.value, 0);
    const result = [];
    let othersValue = 0;

    data.forEach(item => {
      if (item.value / total < 0.02) {
        othersValue += item.value;
      } else {
        result.push(item);
      }
    });

    if (othersValue > 0) {
      result.push({ category: 'OTHERS', value: othersValue });
    }
    return result;
  };

  const processedCategoryData = processPieData(categoryData);

  return (
    <div className="bento-grid">
      {/* ── Monthly Inflow/Outflow Trends ─────────────────── */}
      {hasMonthly && (
        <>
          <EliteChartContainer title="Cash Flow Trajectory" icon={TrendingUp} >
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={monthlyData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="inflowGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={PURPLE} stopOpacity={0.15} />
                    <stop offset="95%" stopColor={PURPLE} stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="outflowGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={SKY} stopOpacity={0.15} />
                    <stop offset="95%" stopColor={SKY} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.03)" vertical={false} />
                <XAxis 
                  dataKey="month" 
                  tick={{ fontSize: 10, fill: '#aaa', fontWeight: 600 }} 
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis 
                  tickFormatter={fmt} 
                  tick={{ fontSize: 10, fill: '#aaa', fontWeight: 600 }} 
                  width={60} 
                  axisLine={false}
                  tickLine={false}
                />
                <RechartsTooltip content={<CustomTooltip />} cursor={{ stroke: LAVENDER, strokeWidth: 1 }} />
                <Legend iconType="circle" wrapperStyle={{ paddingTop: '1rem', fontSize: '0.75rem', fontWeight: 600 }} />
                <Area type="monotone" dataKey="inflow"  name="Inflow"  stroke={PURPLE} strokeWidth={3} fill="url(#inflowGrad)" />
                <Area type="monotone" dataKey="outflow" name="Outflow" stroke={SKY}    strokeWidth={3} fill="url(#outflowGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </EliteChartContainer>

          <div className="bento-item bento-medium">
             <div className="glass-card-header">
                <h3>Insights</h3>
             </div>
             <div style={{ padding: '1rem', fontSize: '0.85rem', lineHeight: '1.6', color: '#666' }}>
                <p>
                  Month-over-month trajectory shows <strong>{monthlyData[monthlyData.length-1].net >= 0 ? 'Positive Surplus' : 'Negative Burn'}</strong> in the latest period.
                </p>
                <div style={{ marginTop: '1.5rem', padding: '1.5rem', background: 'var(--color-pale-purple)', borderRadius: '12px', border: '1px solid var(--glass-border)' }}>
                   <span style={{ fontSize: '0.7rem', fontWeight: 700, color: PURPLE, letterSpacing: '1px' }}>STRATEGIC ADVISORY</span>
                   <p style={{ marginTop: '0.5rem', fontStyle: 'italic', color: GRAPHITE }}>
                     Minimize "Sky Blue" outflow variance to stabilize runway liquidity.
                   </p>
                </div>
             </div>
          </div>
        </>
      )}

      {/* ── Expense Distribution (Pie) ───────────────────── */}
      {hasCategory && (
        <>
          <div className="bento-item bento-medium">
             <div className="glass-card-header">
                <h3>Allocation Matrix</h3>
             </div>
             <div style={{ padding: '1rem' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                   {processedCategoryData.slice(0, 6).map((c, i) => (
                     <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #f9f9f9', paddingBottom: '0.5rem' }}>
                        <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#555' }}>{c.category}</span>
                        <span style={{ fontSize: '0.85rem', fontFamily: 'monospace', fontWeight: 700 }}>{fmt(c.value)}</span>
                     </div>
                   ))}
                </div>
             </div>
          </div>

          <EliteChartContainer title="Capital Distribution" icon={PieIcon} >
            <ResponsiveContainer width="100%" height={320}>
              <RechartsPie>
                <Pie
                  data={processedCategoryData}
                  dataKey="value"
                  nameKey="category"
                  cx="50%"
                  cy="50%"
                  outerRadius={105}
                  innerRadius={70}
                  paddingAngle={5}
                  stroke="none"
                >
                  {processedCategoryData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <RechartsTooltip content={<CustomTooltip />} />
                <Legend iconType="circle" verticalAlign="bottom" height={36} wrapperStyle={{ paddingTop: '1.5rem', fontSize: '0.7rem', fontWeight: 600 }} />
              </RechartsPie>
            </ResponsiveContainer>
          </EliteChartContainer>
        </>
      )}

      {/* ── Quarterly Analysis ───────────────────── */}
      {hasPeriod && (
        <EliteChartContainer title="Quarterly Velocity" icon={BarChart3} fullWidth >
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={periodData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.03)" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: '#aaa', fontWeight: 600 }} axisLine={false} tickLine={false} />
              <YAxis tickFormatter={fmt} tick={{ fontSize: 10, fill: '#aaa', fontWeight: 600 }} width={60} axisLine={false} tickLine={false} />
              <RechartsTooltip content={<CustomTooltip />} cursor={{ fill: PALE, opacity: 0.4 }} />
              <Legend iconType="circle" wrapperStyle={{ paddingTop: '1rem', fontSize: '0.75rem', fontWeight: 600 }} />
              <Bar dataKey="total_inflow"  name="Inflow"  fill={PURPLE} radius={[6, 6, 0, 0]} barSize={40}  />
              <Bar dataKey="total_outflow" name="Outflow" fill={SKY}    radius={[6, 6, 0, 0]} barSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </EliteChartContainer>
      )}
    </div>
  );
};

export default TrendChart;
