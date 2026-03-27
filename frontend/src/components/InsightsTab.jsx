import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { FileText, Printer } from 'lucide-react';

const InsightsTab = () => {
  const [content, setContent] = useState('');
  const [insLoading, setInsLoading] = useState(true);

  useEffect(() => {
    fetch('http://127.0.0.1:8000/api/insights/')
      .then((r) => r.json())
      .then((d) => { if (d.available) setContent(d.content); })
      .catch(() => {})
      .finally(() => setInsLoading(false));
  }, []);

  const handlePrint = () => {
    const win = window.open('', '_blank');
    const el = document.getElementById('insights-report-view');
    if (!el) return;
    const html = el.innerHTML;
    win.document.write(`
      <html><head><title>FinSight Report</title>
      <style>
        body { font-family: sans-serif; padding: 3rem; line-height: 1.8; color: #333; max-width: 800px; margin: 0 auto; }
        h1,h2,h3 { color: #7353F6; margin-top: 2rem; }
        table { border-collapse: collapse; width: 100%; margin: 1rem 0; } 
        td,th { border: 1px solid #eee; padding: 0.75rem; text-align: left; }
        th { background: #f9f9f9; }
        p { margin-bottom: 1rem; }
      </style></head>
      <body>${html}</body></html>
    `);
    win.document.close();
    win.print();
  };

  return (
    <div className="tab-content-wrapper fade-in">
      <div className="insights-report-centered">
        <div className="upload-card report-container full-width">
          <div className="report-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
              <FileText size={24} color="var(--color-primary-purple)" />
              <h2 style={{ margin: 0, fontSize: '1.4rem' }}>AI Intelligent Financial Report</h2>
            </div>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button className="icon-btn-small" onClick={handlePrint} title="Print / Export PDF">
                <Printer size={18} />
                <span style={{ marginLeft: '4px', fontSize: '0.8rem' }}>Print PDF</span>
              </button>
            </div>
          </div>

          <div className="report-body">
            {insLoading ? (
              <div className="loading-placeholder" style={{ padding: '5rem 0' }}>
                <div className="spinner-small" />
                <p style={{ marginTop: '1rem', color: '#888' }}>Generating financial intelligence...</p>
              </div>
            ) : content ? (
              <div className="markdown-container">
                <div id="insights-report-view" className="markdown-body">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                </div>
              </div>
            ) : (
              <div className="empty-state-report">
                <p>No intelligence report has been generated yet.</p>
                <p style={{ fontSize: '0.85rem', color: '#888', marginTop: '0.5rem' }}>
                  Please upload and process your bank statements in the <strong>Extraction</strong> tab first.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default InsightsTab;
