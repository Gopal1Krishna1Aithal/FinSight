import React, { useEffect, useState } from 'react';
import '../App.css';

const SplashScreen = ({ finishSplash }) => {
  const [zoomed, setZoomed] = useState(false);

  useEffect(() => {
    // Stage 1: Emergence (0s - 4s)
    // Stage 2: Pure Focus on Dot (4s - 5.5s)
    // Stage 3: Mega Zoom (5.5s - 7s)
    const timer = setTimeout(() => {
      setZoomed(true);
      setTimeout(() => {
        finishSplash();
      }, 1500); // Final zoom duration
    }, 5500); // Pre-zoom duration

    return () => clearTimeout(timer);
  }, [finishSplash]);

  return (
    <div className={`splash-container ${zoomed ? 'zoomed-out' : ''}`}>
      <div className="logo-emergence">
        <span className="char">F</span>
        <span className="char">I</span>
        <span className="char">N</span>
        <span className="char">S</span>
        <div className={`i-container ${zoomed ? 'zooming' : ''}`}>
          <div className="dot-circle" />
          <span className="char">I</span>
        </div>
        <span className="char">G</span>
        <span className="char">H</span>
        <span className="char">T</span>
      </div>
    </div>
  );
};

export default SplashScreen;
