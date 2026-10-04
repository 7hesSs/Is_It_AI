import DownloadReportButton from "./DownloadReportButton";

function verdictLabel(verdict) {
  if (verdict === "high") return "High overlap";
  if (verdict === "medium") return "Moderate overlap";
  return "Low overlap";
}

// Reuses the same three color classes as the AI verdict band (ai=red,
// uncertain=amber, human=green) - the colors mean "high/medium/low" in
// both contexts, just applied to a different kind of score here.
function verdictClass(verdict) {
  if (verdict === "high") return "ai";
  if (verdict === "medium") return "uncertain";
  return "human";
}

export default function SimilarityResultsPanel({ result, token }) {
  if (!result) return null;

  const percent = Math.round(result.similarity_score * 100);
  const cls = verdictClass(result.verdict);
  const passages = result.matching_passages || [];
  const paraphraseMatches = result.paraphrase_matches || [];

  return (
    <div className="results">
      <DownloadReportButton scanId={result.id} token={token} />

      <div className={`verdict-band ${cls}`}>
        <div className="verdict-top">
          <span className="verdict-label">{verdictLabel(result.verdict)}</span>
          <span className="verdict-score">{percent}%</span>
        </div>
        <div className="verdict-confidence">
          Shared phrasing between "{result.document_a_label}" and "{result.document_b_label}"
        </div>
        <div className="score-track">
          <div className="score-fill" style={{ width: `${percent}%` }} />
        </div>
      </div>

      {passages.length > 0 ? (
        <div className="breakdown">
          <div className="breakdown-title">Matching passages found (shared wording)</div>
          {passages.map((passage, i) => (
            <div className="match-row" key={i}>
              "{passage.text}"
            </div>
          ))}
        </div>
      ) : (
        <p className="history-empty">No significant overlapping wording found.</p>
      )}

      <div className="breakdown" style={{ marginTop: "1.5rem" }}>
        <div className="breakdown-title">
          Possible paraphrased passages (same meaning, different wording) —{" "}
          {Math.round((result.semantic_overlap_score || 0) * 100)}% of sentences matched
        </div>
        {paraphraseMatches.length > 0 ? (
          paraphraseMatches.map((match, i) => (
            <div className="paraphrase-pair" key={i}>
              <div className="paraphrase-doc-label">{result.document_a_label}</div>
              <div className="match-row">"{match.sentence_a}"</div>
              <div className="paraphrase-doc-label">{result.document_b_label}</div>
              <div className="match-row">"{match.sentence_b}"</div>
              <div className="paraphrase-score">
                {Math.round(match.semantic_similarity * 100)}% semantic match
              </div>
            </div>
          ))
        ) : (
          <p className="history-empty" style={{ padding: "0.85rem 1.1rem" }}>
            No likely paraphrased passages detected.
          </p>
        )}
      </div>

      <p className="disclaimer">
        This compares the two uploaded documents directly against each
        other only — it does not check against the internet or any other
        source. The wording-match score reflects shared phrasing, not
        necessarily copying (shared templates, quoted material, or standard
        phrasing can also cause overlap). The paraphrase check can also be
        wrong in both directions: two independently written reports on the
        same topic may share meaning without copying, and a genuinely
        reworded passage can still be missed if the rewording was thorough.
      </p>
    </div>
  );
}
