import React from 'react';
import { FileText, Calendar, Tag, CreditCard, ShieldCheck, AlertCircle, Zap, BrainCircuit } from 'lucide-react';

const FinancialLedger = ({ transactions = [] }) => {
  if (!transactions || transactions.length === 0) return null;

  const fmt = (n) =>
    Number(n || 0).toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });

  return (
    <div className="glass-card">
      <div className="glass-card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <FileText size={20} color="var(--color-primary-purple)" />
          <h3>Audit Console & Ledger</h3>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
           <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.7rem', color: '#666' }}>
             <ShieldCheck size={14} color="#2e7d32" /> INTEGRITY SECURED
           </div>
           <div style={{ fontSize: '0.75rem', color: '#888', fontWeight: 600 }}>
             {transactions.length} ITEMS AUDITED
           </div>
        </div>
      </div>
      
      <div className="ledger-container">
        <table className="ledger-table">
          <thead>
            <tr>
              <th style={{ width: '100px' }}><div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Calendar size={12}/> DATE</div></th>
              <th><div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Tag size={12}/> TRANSACTION DETAILS & AUDIT TRAIL</div></th>
              <th style={{ width: '80px', textAlign: 'center' }}>AUDIT</th>
              <th style={{ width: '140px' }}><div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><CreditCard size={12}/> DEBIT (₹)</div></th>
              <th style={{ width: '140px' }}><div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><CreditCard size={12}/> CREDIT (₹)</div></th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((tx, idx) => (
              <tr key={idx} style={{ background: tx.Math_Error ? 'rgba(211, 47, 47, 0.05)' : 'inherit' }}>
                <td style={{ color: '#888', fontWeight: 500, fontSize: '0.75rem' }}>
                  {tx.Date}
                </td>
                <td>
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontWeight: 600, color: 'var(--color-neutral-dark-gray)', fontSize: '0.82rem', flexBasis: '100%' }}>
                      {tx.Clean_Description || tx.Narration}
                    </span>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <span style={{ 
                        fontSize: '0.6rem', 
                        background: 'var(--color-pale-purple)', 
                        color: 'var(--color-primary-purple)', 
                        padding: '1px 6px', 
                        borderRadius: '4px',
                        fontWeight: 700
                      }}>
                        {tx.CoA_Category?.toUpperCase() || 'UNCATEGORIZED'}
                      </span>
                      {tx.Confidence_Score >= 100 ? (
                        <span style={{ fontSize: '0.6rem', color: '#2e7d32', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '2px' }}>
                           <Zap size={10} /> TAXONOMY MATCH
                        </span>
                      ) : (
                        <span style={{ fontSize: '0.6rem', color: '#666', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '2px' }}>
                           <BrainCircuit size={10} /> AI PREDICTION ({tx.Confidence_Score}%)
                        </span>
                      )}
                    </div>
                  </div>
                </td>
                <td style={{ textAlign: 'center' }}>
                  {tx.Math_Error ? (
                    <div title="Mathematical Integrity Error: Balance mismatch detected in OCR source." style={{ cursor: 'help' }}>
                      <AlertCircle size={18} color="#d32f2f" />
                    </div>
                  ) : (
                    <div title="Mathematically Verified: (Prev Bal - Dr + Cr == Curr Bal)" style={{ cursor: 'help' }}>
                      <ShieldCheck size={18} color="#2e7d32" opacity={0.6} />
                    </div>
                  )}
                </td>
                <td className="amount-monospaced" style={{ color: tx.Debit > 0 ? '#d32f2f' : '#ccc', fontSize: '0.8rem' }}>
                  {tx.Debit > 0 ? fmt(tx.Debit) : '-'}
                </td>
                <td className="amount-monospaced" style={{ color: tx.Credit > 0 ? '#2e7d32' : '#ccc', fontSize: '0.8rem' }}>
                  {tx.Credit > 0 ? fmt(tx.Credit) : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default FinancialLedger;
