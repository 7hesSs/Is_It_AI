const TYPES = [
  { id: "text", label: "Text" },
  { id: "image", label: "Image" },
  { id: "video", label: "Video" },
  { id: "pdf", label: "PDF" },
  { id: "compare", label: "Compare" },
];

export default function MediaTypeTabs({ active, onChange }) {
  return (
    <div className="tabs" role="tablist" aria-label="Media type">
      {TYPES.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          className={`tab ${active === t.id ? "active" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}
