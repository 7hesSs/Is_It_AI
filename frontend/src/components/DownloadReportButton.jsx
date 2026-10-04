import { useState } from "react";
import { downloadReport } from "../api";

export default function DownloadReportButton({ scanId, token }) {
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState("");

  if (!scanId || !token) return null;

  const handleClick = async () => {
    setIsBusy(true);
    setError("");
    try {
      await downloadReport(scanId, token);
    } catch (err) {
      setError(err.message || "Could not generate report.");
    } finally {
      setIsBusy(false);
    }
  };

  return (
    <div className="download-report">
      <button className="clear-button" onClick={handleClick} disabled={isBusy}>
        {isBusy ? "Generating…" : "Download PDF report"}
      </button>
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}
