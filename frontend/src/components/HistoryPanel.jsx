import { useEffect, useState } from "react";
import { getScanHistory, getScan } from "../api";
import ResultsPanel from "./ResultsPanel";
import SimilarityResultsPanel from "./SimilarityResultsPanel";

const MEDIA_LABELS = {
  text: "Text",
  image: "Image",
  video: "Video",
  pdf: "PDF",
  similarity: "Compare",
};

// Similarity scans are stored using the same generic columns as every
// other scan type (ai_probability/confidence/components) - this maps
// those back into the shape SimilarityResultsPanel expects.
function toSimilarityResult(scan) {
  return {
    id: scan.id,
    similarity_score: scan.ai_probability,
    verdict: scan.confidence,
    matching_passages: scan.components?.matching_passages || [],
    semantic_overlap_score: scan.components?.semantic_overlap_score || 0,
    paraphrase_matches: scan.components?.paraphrase_matches || [],
    document_a_label: scan.components?.document_a_label || "Document A",
    document_b_label: scan.components?.document_b_label || "Document B",
  };
}

function timeAgo(isoString) {
  const diffMs = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function HistoryPanel({ token }) {
  const [scans, setScans] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const [details, setDetails] = useState({}); // scan id -> full detail

  useEffect(() => {
    if (!token) return;
    setIsLoading(true);
    getScanHistory(token, 10)
      .then(setScans)
      .catch((err) => setError(err.message || "Could not load history."))
      .finally(() => setIsLoading(false));
  }, [token]);

  if (!token) return null;

  const handleToggle = async (scanId) => {
    if (expandedId === scanId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(scanId);
    if (!details[scanId]) {
      try {
        const detail = await getScan(token, scanId);
        setDetails((prev) => ({ ...prev, [scanId]: detail }));
      } catch (err) {
        setError(err.message || "Could not load that scan.");
      }
    }
  };

  return (
    <div className="history-panel">
      <div className="history-title">Recent scans</div>

      {isLoading && <p className="status-text">Loading…</p>}
      {error && <p className="error-text">{error}</p>}
      {!isLoading && scans.length === 0 && !error && (
        <p className="history-empty">Your past scans will show up here.</p>
      )}

      <ul className="history-list">
        {scans.map((scan) => (
          <li key={scan.id}>
            <button className="history-item" onClick={() => handleToggle(scan.id)}>
              {scan.thumbnail && <img className="history-thumb" src={scan.thumbnail} alt="" />}
              <span className="history-media-badge">
                {MEDIA_LABELS[scan.media_type] || scan.media_type}
              </span>
              <span className="history-label">{scan.label}</span>
              <span className="history-score">{Math.round(scan.ai_probability * 100)}%</span>
              <span className="history-time">{timeAgo(scan.created_at)}</span>
            </button>

            {expandedId === scan.id && (
              <div className="history-expanded">
                {details[scan.id] ? (
                  scan.media_type === "similarity" ? (
                    <SimilarityResultsPanel
                      result={toSimilarityResult(details[scan.id])}
                      token={token}
                    />
                  ) : (
                    <ResultsPanel result={details[scan.id]} token={token} />
                  )
                ) : (
                  <p className="status-text">Loading details…</p>
                )}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
