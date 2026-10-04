import { useEffect, useRef, useState } from "react";

const ACCEPT = {
  image: "image/jpeg,image/png,image/webp,image/bmp",
  video: "video/mp4,video/quicktime,video/x-msvideo,video/webm",
  pdf: "application/pdf",
};

const PLACEHOLDER = {
  image: "Drop an image here, or click to choose a file",
  video: "Drop a video here, or click to choose a file (max 100MB)",
  pdf: "Drop a PDF here, or click to choose a file (max 20MB)",
};

const FIELD_LABEL = {
  image: "Choose an image",
  video: "Choose a video",
  pdf: "Choose a PDF",
};

// Types that get a visual object-URL preview (image/video). PDFs don't -
// showing a real PDF preview would need a PDF.js viewer, overkill for
// confirming "yes, I picked the right file" - the filename does that fine.
const PREVIEWABLE_TYPES = new Set(["image", "video"]);

export default function UploadPanel({
  mediaType,
  onSubmit,
  onClear,
  hasResult,
  isBusy,
  isLoggedIn,
  statusText,
  progress,
  errorText,
}) {
  const [text, setText] = useState("");
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const hasContent = mediaType === "text" ? text.trim().length > 0 : !!file;
  const canSubmit = !isBusy && hasContent && isLoggedIn;
  const canClear = !isBusy && (hasContent || hasResult);

  useEffect(() => {
    if (!file || !PREVIEWABLE_TYPES.has(mediaType)) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file, mediaType]);

  const handleSubmit = () => {
    if (mediaType === "text") onSubmit({ text: text.trim() });
    else onSubmit({ file });
  };

  const handleClear = () => {
    setText("");
    setFile(null);
    if (inputRef.current) inputRef.current.value = "";
    onClear();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) setFile(dropped);
  };

  return (
    <div className="panel">
      {mediaType === "text" ? (
        <>
          <label className="field-label" htmlFor="text-input">
            Paste the text you want to check
          </label>
          <textarea
            id="text-input"
            className="text-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste a paragraph or more — short snippets are less reliable to score."
          />
          <div className="char-count">
            {text.trim() ? text.trim().split(/\s+/).length : 0} words
          </div>
        </>
      ) : (
        <>
          <label className="field-label">{FIELD_LABEL[mediaType]}</label>
          <div
            className={`dropzone ${dragOver ? "drag-over" : ""} ${previewUrl ? "has-preview" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
            }}
          >
            {previewUrl ? (
              mediaType === "image" ? (
                <img className="preview-image" src={previewUrl} alt="Selected file preview" />
              ) : (
                <video
                  className="preview-video"
                  src={previewUrl}
                  controls
                  onClick={(e) => e.stopPropagation()}
                />
              )
            ) : (
              <p>{PLACEHOLDER[mediaType]}</p>
            )}
            {file && <div className="filename">{file.name}</div>}
            <input
              ref={inputRef}
              type="file"
              accept={ACCEPT[mediaType]}
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </div>
        </>
      )}

      <div className="analyze-row">
        <button className="analyze-button" disabled={!canSubmit} onClick={handleSubmit}>
          {isBusy ? "Analyzing…" : "Analyze"}
        </button>
        <button className="clear-button" disabled={!canClear} onClick={handleClear}>
          Clear
        </button>
        {statusText && <span className="status-text">{statusText}</span>}
      </div>

      {!isLoggedIn && hasContent && (
        <p className="login-prompt">Log in to run this analysis.</p>
      )}

      {progress != null && (
        <div className="progress-track">
          <div className="progress-fill" style={{ width: `${progress}%` }} />
        </div>
      )}

      {errorText && <p className="error-text">{errorText}</p>}
    </div>
  );
}
