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
      formData.append('file', files[0]);

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
        // Django returned an HTML error page — extract a useful message
        throw new Error(
          res.ok
            ? 'Server returned an unexpected response. Check the backend terminal for details.'
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

  return (
    <div className="upload-card">
      <h2>Upload Statement</h2>

      <form onDragEnter={handleDrag} onSubmit={(e) => e.preventDefault()} style={{ position: 'relative' }}>
        <label
          htmlFor="file-upload"
          className={`drop-zone ${dragActive ? 'drag-active' : ''}`}
          onDragEnter={handleDrag}
          onDragOver={handleDrag}
          onDragLeave={handleDrag}
          onDrop={handleDrop}
        >
          {files.length === 0 ? (
            <>
              <UploadCloud size={64} />
              <p>Drag &amp; drop your PDF or Images here</p>
              <span>or click to browse — .pdf, .jpg, .jpeg, .png, .heic</span>
            </>
          ) : (
            <div style={{ width: '100%' }}>
              {files.map((f, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.5rem 0', borderBottom: '1px solid var(--color-light-gray)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <FileText size={20} color="var(--color-primary-purple)" />
                    <span style={{ fontSize: '0.9rem', fontWeight: 500 }}>{f.name}</span>
                  </div>
                  <button
                    type="button"
                    onClick={(e) => { e.preventDefault(); removeFile(i); }}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#888' }}
                  >
                    <X size={18} />
                  </button>
                </div>
              ))}
              <p style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: '#888', textAlign: 'center' }}>
                Click to add more files
              </p>
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
          <p style={{ color: '#C00000', marginTop: '1rem', fontSize: '0.9rem', textAlign: 'center' }}>
            ⚠ {error}
          </p>
        )}

        <button
          type="button"
          className="btn-primary"
          disabled={files.length === 0}
          onClick={handleSubmit}
          id="extract-btn"
        >
          {files.length ? 'Extract Insights' : 'Select a File First'}
        </button>
      </form>
    </div>
  );
};

export default UploadSection;
