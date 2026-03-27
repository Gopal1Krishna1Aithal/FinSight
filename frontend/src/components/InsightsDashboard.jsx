import React from 'react';
import { Activity, TrendingDown, TrendingUp, AlertTriangle, Cpu, BarChart2, DollarSign } from 'lucide-react';

const fmt = (n) =>
  `₹ ${Number(n || 0).toLocaleString('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const Metric = ({ icon: Icon, label, value, highlight, sub }) => (
  <div style={{
    background: 'var(--color-white)',
    padding: '1.1rem 1.4rem',
    borderRadius: '12px',
    display: 'flex',
    alignItems: 'center',
    gap: '1rem',
  }}>
    <Icon size={26} color="var(--color-primary-purple)" style={{ flexShrink: 0 }} />
    <div style={{ minWidth: 0 }}>
      <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.07em', color: '#888', marginBottom: '2px' }}>
        {label}
      </p>
      <p style={{ fontSize: '1.15rem', fontWeight: 700, color: highlight || 'var(--color-neutral-dark-gray)', wordBreak: 'break-word' }}>
        {value}
      </p>
      {sub && <p style={{ fontSize: '0.78rem', color: '#888', marginTop: '1px' }}>{sub}</p>}
    </div>
  </div>
);

const healthColor = (status) => {
  if (status === 'HEALTHY') return '#375623';
  if (status === 'WARNING') return '#c07000';
  return '#C00000';
};

const InsightsDashboard = ({ data, loading }) => {
  /* ── Loading state ── */
  if (loading) {
    return (
      <div className="upload-card" style={{ background: 'var(--color-pale-purple)', justifyContent: 'center', alignItems: 'center', minHeight: '300px' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" />
          <p style={{ marginTop: '1rem', color: 'var(--color-primary-purple)', fontWeight: 600 }}>
            Processing statement…
          </p>
          <span style={{ fontSize: '0.85rem', color: '#888' }}>
            Extracting → Categorising via AI → Generating Insights
          </span>
        </div>
      </div>
    );
  }

  /* ── Empty state ── */
  if (!data) {
    return (
      <div className="upload-card" style={{ background: 'var(--color-pale-purple)' }}>
        <h2>Financial Intelligence</h2>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem', marginTop: '0.75rem' }}>
          <Metric icon={Activity} label="Status" value="Awaiting upload…" />
          <Metric icon={TrendingUp} label="Total Income" value="₹ —" />
          <Metric icon={TrendingDown} label="Total Expenses" value="₹ —" />
          <Metric icon={BarChart2} label="Gross Profit" value="₹ —" />
          <Metric icon={Cpu} label="Runway" value="— days" />
        </div>
      </div>
    );
  }

  /* ── Error state ── */
  if (data.error) {
    return (
      <div className="upload-card" style={{ background: '#fff0f0' }}>
        <h2 style={{ color: '#C00000' }}>Processing Error</h2>
        <p style={{ marginTop: '1rem', color: '#C00000', fontSize: '0.95rem' }}>
          {data.error}
        </p>
        <p style={{ marginTop: '0.5rem', color: '#888', fontSize: '0.82rem' }}>
          Check the backend terminal for details, then try again.
        </p>
      </div>
    );
  }

  /* ── Data state ── */
  const { summary = {}, runway_and_burn_rate: runway = {}, draft_pnl_statement: pnl = {},
          crisis_survival_mode: crisis = {}, vendor_dependency: vendorDep = {},
          recurring_subscriptions: subs = {} } = data;

  const vendors = vendorDep.top_vendors || [];
  const hStatus = runway.health_status || 'UNKNOWN';

  return (
    <div className="upload-card" style={{ background: 'var(--color-pale-purple)', overflowY: 'auto', maxHeight: '82vh' }}>
      <h2>Financial Intelligence</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem', marginTop: '0.75rem' }}>

        {/* Health */}
        <Metric
          icon={Activity}
          label="Business Health"
          value={hStatus}
          highlight={healthColor(hStatus)}
          sub={summary.date_range ? `${summary.date_range.start} → ${summary.date_range.end}` : null}
        />

        {/* P&L */}
        <Metric icon={TrendingUp} label="Total Income" value={fmt(pnl.Total_Income)} highlight="#375623" />
        <Metric icon={TrendingDown} label="Operating Expenses" value={fmt(pnl.Operating_Expenses)} />
        <Metric
          icon={BarChart2}
          label="Gross Estimated Profit"
          value={fmt(pnl.Gross_Estimated_Profit)}
          highlight={(pnl.Gross_Estimated_Profit || 0) >= 0 ? '#375623' : '#C00000'}
        />

        {/* Burn rate */}
        <Metric icon={Cpu} label="Daily Burn Rate" value={fmt(runway.daily_burn_rate)} />
        <Metric
          icon={AlertTriangle}
          label="Cash Runway"
          value={`${Math.round(runway.runway_days_left || 0)} days`}
          highlight={healthColor(hStatus)}
          sub={`Monthly burn: ${fmt(runway.monthly_burn_rate)}`}
        />

        {/* Balance + Transactions */}
        <Metric icon={DollarSign} label="Current Balance" value={fmt(summary.latest_balance)} />
        <Metric icon={Activity} label="Total Transactions" value={summary.total_transactions || 0} />

        {/* Crisis mode */}
        {crisis.essential_monthly_overhead != null && (
          <Metric
            icon={AlertTriangle}
            label="Crisis Mode Monthly Overhead"
            value={fmt(crisis.essential_monthly_overhead)}
            sub={`Crisis runway: ${Math.round(crisis.crisis_runway_days_left || 0)} days`}
          />
        )}

        {/* Top vendors */}
        {vendors.length > 0 && (
          <div style={{ background: 'var(--color-white)', borderRadius: '12px', padding: '1.1rem 1.4rem' }}>
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.07em', color: '#888', marginBottom: '0.6rem' }}>
              Top Vendors by Spend
            </p>
            {vendors.map((v, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '0.35rem 0', borderBottom: i < vendors.length - 1 ? '1px solid var(--color-light-gray)' : 'none',
                fontSize: '0.85rem',
              }}>
                <span style={{ fontWeight: 600, maxWidth: '55%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {v.vendor_name}
                </span>
                <span style={{ color: '#888' }}>
                  {fmt(v.total_spend)}
                  <span style={{ color: '#c00', marginLeft: '4px' }}>({v.percentage_of_total_outflow}%)</span>
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Recurring */}
        {subs.total_recurring_subscriptions_found > 0 && (
          <Metric
            icon={Cpu}
            label="Recurring Payments Found"
            value={`${subs.total_recurring_subscriptions_found} contracts`}
            sub={`Est. fixed cost: ${fmt(subs.estimated_fixed_monthly_cost)}/mo`}
          />
        )}
      </div>
    </div>
  );
};

export default InsightsDashboard;
