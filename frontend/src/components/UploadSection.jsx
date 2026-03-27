import React, { useState, useCallback } from 'react';
import { UploadCloud, FileText, X, Loader } from 'lucide-react';

const UploadSection = ({ onResults, onLoading }) => {
  const [dragActive, setDragActive] = useState(false);
  const [files, setFiles] = useState([]);
  const [error, setError] = useState(null);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true);
    else if (e.type === 'dragleave') setDragActive(false);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.length) setFiles(Array.from(e.dataTransfer.files));
  }, []);

  const handleChange = (e) => {
    if (e.target.files?.length) setFiles(Array.from(e.target.files));
  };

  const removeFile = (idx) => setFiles((prev) => prev.filter((_, i) => i !== idx));

  const handleSubmit = async () => {
    if (!files.length) return;
    setError(null);
    onLoading(true);

    try {
      const formData = new FormData();
      files.forEach(f => {
        formData.append('file', f);
      });

      const res = await fetch('http://127.0.0.1:8000/api/upload/', {
        method: 'POST',
        body: formData,
      });

      // Always try to parse as JSON; fall back gracefully if the server returned HTML
      const text = await res.text();
      let data;
      try {
        data = JSON.parse(text);
      } catch {
        // Handle invalid JSON (often caused by NaN/Inf in the backend response)
        throw new Error(
          res.ok
            ? 'The server returned an invalid data format (likely a mathematical error in the backend). Please check the backend logs.'
            : `Backend error ${res.status}: The server returned an HTML page instead of JSON. Check the backend terminal.`
        );
      }

      if (!res.ok || data.error) {
        throw new Error(data.error || `Server error ${res.status}`);
      }

      onResults(data);
    } catch (err) {
      setError(err.message);
      onResults(null);
    } finally {
      onLoading(false);
    }
  };

  const onInputClick = () => {
    document.getElementById('file-upload')?.click();
  };

  return (
    <div className="glass-card">
      <div className="glass-card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <UploadCloud size={20} color="var(--color-primary-purple)" />
          <h3>Secure Data Ingestion</h3>
        </div>
        <span style={{ fontSize: '0.75rem', color: '#888', fontWeight: 600 }}>BANK-GRADE OCR</span>
      </div>

      <div style={{ padding: '1.75rem' }}>
        <form onDragEnter={handleDrag} onSubmit={(e) => e.preventDefault()} style={{ position: 'relative' }}>
          <label
            htmlFor="file-upload"
            className={`upload-console ${dragActive ? 'drag-active' : ''}`}
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
          >
            {files.length === 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', padding: '1rem 0' }}>
                <div style={{ padding: '1.25rem', background: 'var(--color-pale-purple)', borderRadius: '50%', color: 'var(--color-primary-purple)' }}>
                  <UploadCloud size={48} />
                </div>
                <div style={{ textAlign: 'center' }}>
                  <p style={{ fontFamily: 'var(--font-heading)', fontSize: '1.6rem', color: 'var(--color-graphite-black)', letterSpacing: '1px' }}>DROP FINANCIAL STATEMENTS</p>
                  <p style={{ fontSize: '0.85rem', color: '#888', marginTop: '4px' }}>Click or drag PDF, JPG, or PNG files to begin</p>
                </div>
              </div>
            ) : (
              <div style={{ width: '100%', textAlign: 'left' }}>
                <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: '#888', marginBottom: '1rem', fontWeight: 700 }}>Documents Staged For Analysis</p>
                {files.map((f, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 1rem', background: '#fff', borderRadius: '10px', marginBottom: '0.5rem', border: '1px solid var(--color-light-gray)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <FileText size={18} color="var(--color-primary-purple)" />
                      <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--color-neutral-dark-gray)' }}>{f.name}</span>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => { e.preventDefault(); removeFile(i); }}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ff4d4d', display: 'flex' }}
                    >
                      <X size={16} />
                    </button>
                  </div>
                ))}
                <div style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.8rem', color: 'var(--color-primary-purple)', fontWeight: 700, cursor: 'pointer' }} onClick={onInputClick}>
                  + ADD MORE DOCUMENTS
                </div>
              </div>
            )}
          </label>

          <input
            id="file-upload"
            type="file"
            multiple
            accept=".pdf,.jpg,.jpeg,.png,.heic"
            onChange={handleChange}
            style={{ display: 'none' }}
          />

          {error && (
            <div style={{ color: '#C00000', marginTop: '1.5rem', fontSize: '0.85rem', background: '#fff0f0', padding: '1rem', borderRadius: '8px', border: '1px solid #ffcccc' }}>
               {error}
            </div>
          )}

          <div style={{ marginTop: '2rem' }}>
            <button
              type="button"
              className="btn-innovation"
              onClick={files.length > 0 ? handleSubmit : onInputClick}
              id="extract-btn"
              style={{ width: '100%' }}
            >
              {files.length ? 'LAUNCH INTELLIGENCE PIPELINE' : 'DRIVE DATA INGESTION'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UploadSection;
