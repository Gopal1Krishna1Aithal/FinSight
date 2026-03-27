import React from 'react';
import { Activity, TrendingDown, TrendingUp, AlertTriangle, Cpu, BarChart2, DollarSign } from 'lucide-react';

const fmt = (n) =>
  `₹ ${Number(n || 0).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;const Metric = ({ icon: Icon, label, value, highlight, sub }) => (
  <div style={{
    padding: '0.85rem 0',
    borderBottom: '1px solid rgba(0,0,0,0.05)',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px'
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', opacity: 0.6 }}>
      <Icon size={14} />
      <span style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 600 }}>{label}</span>
    </div>
    <div style={{ 
      fontSize: '1.65rem', 
      fontFamily: 'var(--font-heading)', 
      color: highlight || 'var(--color-graphite-black)',
      letterSpacing: '0.5px',
      lineHeight: 1
    }}>
      {value}
    </div>
    {sub && <div style={{ fontSize: '0.7rem', color: '#888', fontWeight: 500 }}>{sub}</div>}
  </div>
);

const healthColor = (status) => {
  if (status === 'HEALTHY') return '#2e7d32';
  if (status === 'WARNING') return '#ed6c02';
  return '#d32f2f';
};

const InsightsDashboard = ({ data, loading }) => {
  if (loading) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center' }}>
        <div className="spinner" style={{ width: '32px', height: '32px' }} />
        <p style={{ marginTop: '1rem', fontSize: '0.8rem', color: '#888' }}>Analyzing Ledger...</p>
      </div>
    );
  }

  if (!data || data.error) {
    return (
      <div style={{ opacity: 0.5, textAlign: 'center', padding: '2rem' }}>
        <Activity size={32} style={{ marginBottom: '1rem' }} />
        <p style={{ fontSize: '0.85rem' }}>Awaiting ingestion cycle...</p>
      </div>
    );
  }

  const { summary = {}, runway_and_burn_rate: runway = {}, draft_pnl_statement: pnl = {} } = data;
  const hStatus = runway.health_status || 'UNKNOWN';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
      <Metric
        icon={Activity}
        label="Pulse Status"
        value={hStatus}
        highlight={healthColor(hStatus)}
        sub={summary.date_range ? `${summary.date_range.start} → ${summary.date_range.end}` : null}
      />
      
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginTop: '1rem' }}>
        <Metric icon={TrendingUp} label="Revenue" value={fmt(pnl.Total_Income)} />
        <Metric icon={TrendingDown} label="Burn" value={fmt(pnl.Operating_Expenses)} />
      </div>

      <Metric 
        icon={DollarSign} 
        label="Available Liquidity" 
        value={fmt(summary.latest_balance)} 
        highlight="var(--color-primary-purple)"
      />

      <Metric 
        icon={AlertTriangle} 
        label="Cash Runway" 
        value={`${Math.round(runway.runway_days_left || 0)} DAYS`}
        sub={`Velocity: ${fmt(runway.monthly_burn_rate)}/mo`}
      />
    </div>
  );
};

export default InsightsDashboard;
