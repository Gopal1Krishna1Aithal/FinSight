import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { X, FileText, Printer, Download } from 'lucide-react';

const InsightsPanel = ({ onClose }) => {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/insights/')
      .then((r) => r.json())
      .then((d) => {
        if (d.available) setContent(d.content);
        else setError('Insights not yet generated. Upload a statement first.');
      })
      .catch(() => setError('Could not connect to the backend.'))
      .finally(() => setLoading(false));
  }, []);

  const handlePrint = () => {
    const win = window.open('', '_blank');
    win.document.write(`
      <html><head><title>FinSight Financial Insights</title>
      <style>
        body { font-family: 'Montserrat', sans-serif; padding: 2rem; line-height: 1.7; color: #231F20; }
        h1,h2,h3 { color: #7353F6; }
        pre { background: #f5f5f5; padding: 1rem; border-radius: 8px; white-space: pre-wrap; }
        table { border-collapse: collapse; width: 100%; } td,th { border: 1px solid #ddd; padding: 0.5rem; }
      </style></head>
      <body>${document.getElementById('insights-content').innerHTML}</body></html>
    `);
    win.document.close();
    win.print();
  };

  const handleDownloadMd = () => {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = 'financial_insights.md';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <FileText size={22} color="var(--color-primary-purple)" />
            <h2 style={{ margin: 0 }}>AI Financial Insights</h2>
          </div>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            {content && (
              <>
                <button className="icon-btn" onClick={handleDownloadMd} title="Download as Markdown">
                  <Download size={18} />
                  <span>.md</span>
                </button>
                <button className="icon-btn" onClick={handlePrint} title="Print / Save as PDF">
                  <Printer size={18} />
                  <span>PDF</span>
                </button>
              </>
            )}
            <button className="icon-btn danger" onClick={onClose} title="Close">
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="modal-body">
          {loading && (
            <div style={{ textAlign: 'center', padding: '3rem' }}>
              <div className="spinner" />
              <p style={{ marginTop: '1rem', color: '#888' }}>Loading insights…</p>
            </div>
          )}
          {error && <p style={{ color: '#C00000', padding: '2rem' }}>{error}</p>}
          {content && (
            <div style={{ maxWidth: '680px', margin: '0 auto' }}>
              <div id="insights-content" className="markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default InsightsPanel;
