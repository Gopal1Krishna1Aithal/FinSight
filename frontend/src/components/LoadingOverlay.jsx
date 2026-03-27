import React, { useState, useEffect } from 'react';
import { Loader2, ShieldCheck, Cpu, Database, Brain } from 'lucide-react';
import '../App.css';

const LoadingOverlay = () => {
  const [stage, setStage] = useState(0);
  const stages = [
    { text: "Parsing Financial Layout...", icon: <Cpu size={24} /> },
    { text: "Mapping Chart of Accounts...", icon: <Database size={24} /> },
    { text: "Verifying Mathematical Integrity...", icon: <ShieldCheck size={24} /> },
    { text: "Synthesizing Professional Insights...", icon: <Brain size={24} /> }
  ];

  useEffect(() => {
    const interval = setInterval(() => {
      setStage((prev) => (prev + 1) % stages.length);
    }, 2500);
    return () => clearInterval(interval);
  }, [stages.length]);

  return (
    <div className="loading-overlay-container">
      <div className="loading-glass-box">
        <div className="loading-pulse-logo">
           <div className="dot-pulse" />
        </div>
        
        <div className="loading-status-text">
          <div className="status-icon-glow">
            {stages[stage].icon}
          </div>
          <p className="status-label">{stages[stage].text}</p>
        </div>

        <div className="progress-bar-container">
          <div className="progress-bar-fill" style={{ width: `${((stage + 1) / stages.length) * 100}%` }} />
        </div>

        <div className="loading-footer-note">
          DO NOT REFRESH — AUDIT PIPELINE ACTIVE
        </div>
      </div>
    </div>
  );
};

export default LoadingOverlay;
