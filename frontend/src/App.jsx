import React, { useState, useEffect } from 'react';
import UploadSection from './components/UploadSection';
import InsightsDashboard from './components/InsightsDashboard';
import TrendChart from './components/TrendChart';
import DownloadBar from './components/DownloadBar';
import InsightsPanel from './components/InsightsPanel';
import './App.css';

function App() {
  const [results, setResults]       = useState(null);
  const [loading, setLoading]       = useState(false);
  const [showInsights, setShowInsights] = useState(false);

  useEffect(() => {
    // Attempt to load current cumulative database state on boot
    fetch('http://127.0.0.1:8000/api/dashboard/')
      .then(res => { if (res.ok) return res.json(); })
      .then(data => { if (data) setResults(data); })
      .catch(() => {}); // silent fail if empty
  }, []);

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header>
        <div>
          <h1 className="innovation-text">FinSight</h1>
          <p>Financial Data Extraction &amp; AI Analysis</p>
        </div>
        <div className="brand-badge">Agentica 2.0</div>
      </header>

      {/* Upload + Intelligence row */}
      <main className="content-grid">
        <UploadSection onResults={setResults} onLoading={setLoading} />
        <InsightsDashboard data={results} loading={loading} />
      </main>

      {/* Charts — show only after successful upload */}
      {results && !results.error && (
        <>
          <TrendChart
            monthlyData={results.monthly_trends}
            periodData={results.period_breakdown}
          />
          <DownloadBar onShowInsights={() => setShowInsights(true)} />
        </>
      )}

      {/* Insights modal */}
      {showInsights && <InsightsPanel onClose={() => setShowInsights(false)} />}
    </div>
  );
}

export default App;
