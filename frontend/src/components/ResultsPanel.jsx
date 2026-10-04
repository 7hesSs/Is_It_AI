import DownloadReportButton from "./DownloadReportButton";

const COMPONENT_LABELS = {
  classifier_score: "Classifier score",
  perplexity: "Perplexity",
  perplexity_score: "Perplexity signal",
  burstiness: "Sentence variance",
  burstiness_score: "Variance signal",
  fft_score: "Frequency-pattern signal",
  frames_analyzed: "Frames analyzed",
  frame_score_mean: "Average frame score",
  frame_score_std_dev: "Frame score variation",
  frame_score_min: "Lowest frame score",
  frame_score_max: "Highest frame score",
};

const FLAG_TEXT = {
  low_perplexity:
    "The text reads as unusually predictable — a pattern common in AI writing.",
  low_sentence_variance:
    "Sentence lengths are unusually uniform, another common AI-writing pattern.",
  short_text_low_reliability:
    "This text is short. Treat the score as a rough read, not a verdict.",
  high_frequency_grid_pattern:
    "The image shows a frequency pattern often left behind by AI image generators.",
  strong_classifier_match:
    "The image classifier matched AI-generated examples with high confidence.",
  inconsistent_frame_scores:
    "Frame-by-frame scores varied a lot — parts of this video may differ from others.",
  high_average_ai_score: "Most sampled frames scored high for AI-generated content.",
  very_short_video_low_reliability:
    "Very few frames were available to analyze. Treat this score as rough.",
  pdf_truncated_long_document:
    "This document was long, so only part of it was scored — treat the result as a partial read.",
  sentence_highlighting_partial:
    "This document has many sentences — only the first portion was scored individually for highlighting below. The overall score above still reflects the full text.",
};

// Sentences below this score aren't highlighted at all, so the view
// doesn't turn into a wall of color - only sentences that actually stood
// out get marked.
const SENTENCE_HIGHLIGHT_THRESHOLD = 0.6;

function sentenceHighlightStyle(aiProbability) {
  if (aiProbability < SENTENCE_HIGHLIGHT_THRESHOLD) return undefined;
  const intensity = Math.min(
    (aiProbability - SENTENCE_HIGHLIGHT_THRESHOLD) / (1 - SENTENCE_HIGHLIGHT_THRESHOLD),
    1
  );
  const percent = Math.round(15 + intensity * 35); // 15% to 50% tint
  return { backgroundColor: `color-mix(in srgb, var(--flagged) ${percent}%, transparent)` };
}

function verdictClass(aiProbability) {
  if (aiProbability < 0.35) return "human";
  if (aiProbability > 0.65) return "ai";
  return "uncertain";
}

function verdictLabel(aiProbability) {
  if (aiProbability < 0.35) return "Likely human";
  if (aiProbability > 0.65) return "Likely AI-generated";
  return "Uncertain";
}

function formatValue(value) {
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(3);
  }
  return String(value);
}

export default function ResultsPanel({ result, token }) {
  if (!result) return null;

  const cls = verdictClass(result.ai_probability);
  const percent = Math.round(result.ai_probability * 100);

  return (
    <div className="results">
      <DownloadReportButton scanId={result.id} token={token} />

      <div className={`verdict-band ${cls}`}>
        <div className="verdict-top">
          <span className="verdict-label">{verdictLabel(result.ai_probability)}</span>
          <span className="verdict-score">{percent}%</span>
        </div>
        <div className="verdict-confidence">
          Confidence: {result.confidence} · estimated probability of AI generation
        </div>
        <div className="score-track">
          <div className="score-fill" style={{ width: `${percent}%` }} />
        </div>
      </div>

      {result.components && Object.keys(result.components).length > 0 && (
        <div className="breakdown">
          <div className="breakdown-title">Signal breakdown</div>
          {Object.entries(result.components).map(([key, value]) => (
            <div className="breakdown-row" key={key}>
              <span className="key">{COMPONENT_LABELS[key] || key}</span>
              <span>{formatValue(value)}</span>
            </div>
          ))}
        </div>
      )}

      {result.risk_flags && result.risk_flags.length > 0 && (
        <div className="flags">
          <div className="flags-title">What stood out</div>
          <ul>
            {result.risk_flags.map((flag) => (
              <li key={flag}>{FLAG_TEXT[flag] || flag}</li>
            ))}
          </ul>
        </div>
      )}

      {result.sentences && result.sentences.length > 0 ? (
        <div className="extracted-text">
          <div className="extracted-text-title">
            Sentence-level view — highlighted sentences scored highest for AI-likelihood
          </div>
          <p className="sentence-view">
            {result.sentences.map((sentence, i) => (
              <span
                key={i}
                className="sentence-span"
                style={sentenceHighlightStyle(sentence.ai_probability)}
                title={`${Math.round(sentence.ai_probability * 100)}% AI-likelihood`}
              >
                {sentence.text}{" "}
              </span>
            ))}
          </p>
        </div>
      ) : (
        result.extracted_text && (
          <div className="extracted-text">
            <div className="extracted-text-title">
              Text that was scored (references/bibliography excluded)
            </div>
            <pre className="extracted-text-body">{result.extracted_text}</pre>
          </div>
        )
      )}

      <p className="disclaimer">
        This score is a probability estimate from automated signals, not a
        determination of fact. Short inputs, edited or paraphrased AI content,
        and heavily compressed media all reduce reliability — read it as one
        input alongside your own judgment, not a verdict.
      </p>
    </div>
  );
}
