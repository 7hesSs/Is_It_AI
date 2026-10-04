import { useRef, useState } from "react";

export default function CompareUploadPanel({
  onSubmit,
  onClear,
  hasResult,
  isBusy,
  isLoggedIn,
  statusText,
  errorText,
}) {
  const [fileA, setFileA] = useState(null);
  const [fileB, setFileB] = useState(null);
  const inputARef = useRef(null);
  const inputBRef = useRef(null);

  const hasContent = !!fileA && !!fileB;
  const canSubmit = !isBusy && hasContent && isLoggedIn;
  const canClear = !isBusy && (fileA || fileB || hasResult);

  const handleSubmit = () => onSubmit({ fileA, fileB });

  const handleClear = () => {
    setFileA(null);
    setFileB(null);
    if (inputARef.current) inputARef.current.value = "";
    if (inputBRef.current) inputBRef.current.value = "";
    onClear();
  };

  return (
    <div className="panel">
      <label className="field-label">Choose two PDFs to compare against each other</label>

      <div className="compare-grid">
        <div
          className="dropzone"
          onClick={() => inputARef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") inputARef.current?.click();
          }}
        >
          <p>{fileA ? "Document A" : "Click to choose Document A"}</p>
          {fileA && <div className="filename">{fileA.name}</div>}
          <input
            ref={inputARef}
            type="file"
            accept="application/pdf"
            onChange={(e) => setFileA(e.target.files?.[0] || null)}
          />
        </div>

        <div
          className="dropzone"
          onClick={() => inputBRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") inputBRef.current?.click();
          }}
        >
          <p>{fileB ? "Document B" : "Click to choose Document B"}</p>
          {fileB && <div className="filename">{fileB.name}</div>}
          <input
            ref={inputBRef}
            type="file"
            accept="application/pdf"
            onChange={(e) => setFileB(e.target.files?.[0] || null)}
          />
        </div>
      </div>

      <div className="analyze-row">
        <button className="analyze-button" disabled={!canSubmit} onClick={handleSubmit}>
          {isBusy ? "Comparing…" : "Compare"}
        </button>
        <button className="clear-button" disabled={!canClear} onClick={handleClear}>
          Clear
        </button>
        {statusText && <span className="status-text">{statusText}</span>}
      </div>

      {!isLoggedIn && hasContent && (
        <p className="login-prompt">Log in to run this comparison.</p>
      )}

      {errorText && <p className="error-text">{errorText}</p>}
    </div>
  );
}
