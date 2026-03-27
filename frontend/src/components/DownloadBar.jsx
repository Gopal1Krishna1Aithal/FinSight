import React, { useState } from 'react';
import { FileSpreadsheet, FileCode, Brain } from 'lucide-react';

const DownloadBar = ({ onShowInsights }) => {
  const [csvLoading, setCsvLoading] = useState(false);
  const [xmlLoading, setXmlLoading] = useState(false);

  const triggerDownload = async (url, filename, setLoading) => {
    setLoading(true);
    try {
      const res = await fetch(url);
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        alert(d.error || 'File not available. Upload a statement first.');
        return;
      }
      const blob = await res.blob();
      const href = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = href;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(href);
    } catch {
      alert('Download failed. Make sure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="download-bar">
      <h3>Export & Insights</h3>
      <div className="download-buttons">
        <button
          className="dl-btn"
          onClick={() => triggerDownload('http://127.0.0.1:8000/api/download/tally-csv/', 'tally_import.csv', setCsvLoading)}
          disabled={csvLoading}
          id="dl-csv-btn"
        >
          <FileSpreadsheet size={20} />
          <span>{csvLoading ? 'Downloading…' : 'Tally CSV'}</span>
        </button>

        <button
          className="dl-btn"
          onClick={() => triggerDownload('http://127.0.0.1:8000/api/download/tally-xml/', 'tally_import.xml', setXmlLoading)}
          disabled={xmlLoading}
          id="dl-xml-btn"
        >
          <FileCode size={20} />
          <span>{xmlLoading ? 'Downloading…' : 'Tally XML'}</span>
        </button>

        <button className="dl-btn insights" onClick={onShowInsights} id="view-insights-btn">
          <Brain size={20} />
          <span>View Insights</span>
        </button>
      </div>
    </div>
  );
};

export default DownloadBar;
