import React from 'react';
import TrendChart from './TrendChart';
import DownloadBar from './DownloadBar';
import { BarChart2 } from 'lucide-react';

const TrendsTab = ({ results, onShowInsights }) => {
  if (!results || results.error) {
    return (
      <div className="tab-content-wrapper fade-in">
        <div className="empty-state-card">
          <BarChart2 size={48} color="#ccc" />
          <p>Please upload a statement to view trends.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="tab-content-wrapper fade-in">
      <div className="trends-container">
        <TrendChart
          monthlyData={results.monthly_trends}
          periodData={results.period_breakdown}
          categoryData={results.category_breakdown}
        />
      </div>
    </div>
  );
};

export default TrendsTab;
