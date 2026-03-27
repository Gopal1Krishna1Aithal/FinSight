import React, { useState } from 'react';
import { FileSpreadsheet, FileCode, CheckCircle2, Download } from 'lucide-react';

const ExportConsole = () => {
  const [loading, setLoading] = useState({});

  const triggerDownload = async (url, filename, key) => {
    setLoading(prev => ({ ...prev, [key]: true }));
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error('Export unavailable');
      const blob = await res.blob();
      const href = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = href;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(href);
    } catch (err) {
      alert('Failed: ' + err.message);
    } finally {
      setLoading(prev => ({ ...prev, [key]: false }));
    }
  };

  const ExportItem = ({ icon: Icon, label, sub, onClick, isLoading }) => (
    <button 
      className="bento-item" 
      onClick={onClick}
      disabled={isLoading}
      style={{
        background: 'var(--color-white)',
        border: '1px solid var(--color-light-gray)',
        borderRadius: '12px',
        padding: '1.25rem',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        cursor: 'pointer',
        textAlign: 'left',
        width: '100%',
        transition: 'all 0.3s ease'
      }}
    >
      <div style={{
        padding: '0.75rem',
        background: 'var(--color-pale-purple)',
        borderRadius: '10px',
        color: 'var(--color-primary-purple)'
      }}>
        <Icon size={24} />
      </div>
      <div>
        <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.1rem', color: 'var(--color-graphite-black)', letterSpacing: '0.5px' }}>{label}</p>
        <span style={{ fontSize: '0.7rem', color: '#888', fontWeight: 600, textTransform: 'uppercase' }}>{sub}</span>
      </div>
      <div style={{ marginLeft: 'auto', opacity: isLoading ? 1 : 0.3 }}>
        {isLoading ? <div className="spinner" style={{ width: '16px', height: '16px' }} /> : <Download size={18} />}
      </div>
    </button>
  );

  return (
    <div className="glass-card" style={{ height: '100%' }}>
      <div className="glass-card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <FileSpreadsheet size={20} color="var(--color-sky-blue)" />
          <h3>Export Matrix</h3>
        </div>
      </div>
      
      <div style={{ padding: '1.5rem', display: 'grid', gridTemplateColumns: '1fr', gap: '1rem' }}>
        <ExportItem 
          icon={FileCode} 
          label="TALLY.ERP 9 (CSV)" 
          sub="Import Ledger compatible" 
          onClick={() => triggerDownload('http://127.0.0.1:8000/api/download/tally-csv/', 'tally_import.csv', 'csv')}
          isLoading={loading.csv}
        />
        <ExportItem 
          icon={FileCode} 
          label="TALLY PRIME (XML)" 
          sub="Direct XML Integration" 
          onClick={() => triggerDownload('http://127.0.0.1:8000/api/download/tally-xml/', 'tally_import.xml', 'xml')}
          isLoading={loading.xml}
        />
        <ExportItem 
          icon={FileSpreadsheet} 
          label="ANNUAL EXCEL (.XLSX)" 
          sub="Clean multi-period report" 
          onClick={() => triggerDownload('http://127.0.0.1:8000/api/download/excel/', 'clean_statement.xlsx', 'excel')}
          isLoading={loading.excel}
        />
      </div>
    </div>
  );
};

export default ExportConsole;
