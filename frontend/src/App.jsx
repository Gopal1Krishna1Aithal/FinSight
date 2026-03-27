import React, { useState, useEffect } from 'react';
import { LayoutGrid, BarChart3, MessageSquare, UploadCloud, PieChart, Brain } from 'lucide-react';

import UploadSection from './components/UploadSection';
import InsightsDashboard from './components/InsightsDashboard';
import TrendChart from './components/TrendChart';
import DownloadBar from './components/DownloadBar';
import InsightsPanel from './components/InsightsPanel';
import ChatBot from './components/ChatBot';

import InsightsTab from './components/InsightsTab';
import TrendsTab from './components/TrendsTab';
import ChatTab from './components/ChatTab';
import FinancialLedger from './components/FinancialLedger';
import ExportConsole from './components/ExportConsole';

import LoadingOverlay from './components/LoadingOverlay';

import SplashScreen from './components/SplashScreen';

function App() {
  const [results, setResults]       = useState(null);
  const [loading, setLoading]       = useState(false);
  const [showInsights, setShowInsights] = useState(false);
  const [currentTab, setCurrentTab]     = useState('ingestion');
  const [showSplash, setShowSplash]     = useState(true);

  if (showSplash) {
    return <SplashScreen finishSplash={() => setShowSplash(false)} />;
  }

  const onUploadSuccess = (data) => {
    if (data) {
      setResults(data);
      setCurrentTab('ledger'); // Auto-switch to audit view
    }
  };

  const renderActiveTab = () => {
    switch (currentTab) {
      case 'ingestion':
        return (
          <div className="tab-content-wrapper fade-in" style={{ display: 'flex', justifyContent: 'center', paddingTop: '5vh' }}>
            <div style={{ width: '100%', maxWidth: '800px' }}>
              <UploadSection onResults={onUploadSuccess} onLoading={setLoading} />
            </div>
          </div>
        );
      case 'ledger':
        return (
          <div className="tab-content-wrapper fade-in">
            {results ? (
              <main className="bento-grid">
                {/* Audit Summary Matrix */}
                <div className="bento-item bento-half">
                  <div className="glass-card-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <PieChart size={18} color="var(--color-primary-purple)" />
                      <h3>Audit Pulse</h3>
                    </div>
                    <div className="status-badge-compact">{results.summary.total_transactions} tx</div>
                  </div>
                  <div style={{ padding: '0.5rem', flex: 1 }}>
                    <InsightsDashboard data={results} loading={loading} />
                  </div>
                </div>

                {/* Export Command Matrix */}
                <div className="bento-item bento-half">
                  <ExportConsole />
                </div>


                {/* Financial Ledger (Full Width) */}
                <div className="bento-item bento-full">
                  <FinancialLedger transactions={results.transactions} />
                </div>
              </main>
            ) : (
              <div className="empty-state-bento">
                <LayoutGrid size={48} style={{ opacity: 0.2, marginBottom: '1rem' }} />
                <p>Awaiting Data Ingestion...</p>
              </div>
            )}
          </div>
        );
      case 'insights':
        return <InsightsTab />;
      case 'trends':
        return <TrendsTab results={results} onShowInsights={() => setShowInsights(true)} />;
      case 'chat':
        return <ChatTab />;
      default:
        return null;
    }
  };

  return (
    <div className="dashboard-container">
      {loading && <LoadingOverlay />}
      {/* Header */}
      <header>
        <div>
          <h1 className="innovation-text">FinSight</h1>
          <p>Multi-Period Financial Audit Engine</p>
        </div>
        <div className="brand-badge">Agentica 2.0</div>
      </header>

      {/* Tab Navigation */}
      <nav className="tab-nav">
        <button 
          className={currentTab === 'ingestion' ? 'active' : ''} 
          onClick={() => setCurrentTab('ingestion')}
        >
          <UploadCloud size={16} /> Ingestion
        </button>
        <button 
          className={currentTab === 'ledger' ? 'active' : ''} 
          onClick={() => setCurrentTab('ledger')}
          style={{ position: 'relative' }}
        >
          <LayoutGrid size={16} /> Ledger
          {!results && <div style={{ position: 'absolute', top: -4, right: -4, width: 8, height: 8, background: '#ff4d4d', borderRadius: '50%', border: '2px solid #fff' }} />}
        </button>
        <button 
          className={currentTab === 'insights' ? 'active' : ''} 
          onClick={() => setCurrentTab('insights')}
          disabled={!results}
          style={{ opacity: !results ? 0.5 : 1 }}
        >
          <Brain size={16} /> Insights
        </button>
        <button 
          className={currentTab === 'trends' ? 'active' : ''} 
          onClick={() => setCurrentTab('trends')}
          disabled={!results}
          style={{ opacity: !results ? 0.5 : 1 }}
        >
          <BarChart3 size={16} /> Trends
        </button>
        <button 
          className={currentTab === 'chat' ? 'active' : ''} 
          onClick={() => setCurrentTab('chat')}
        >
          <MessageSquare size={16} /> AI Chat
        </button>
      </nav>

      {/* Render Active View */}
      <div className="tab-panels" style={{ marginTop: '1rem' }}>
        {renderActiveTab()}
      </div>

      {showInsights && <InsightsPanel onClose={() => setShowInsights(false)} />}
      <ChatBot />
    </div>
  );
}

export default App;
