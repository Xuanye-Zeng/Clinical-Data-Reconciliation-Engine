// JSON payload editor component.
// Shows a textarea for editing raw JSON, a "Load demo payload" button,
// and optional preset case chips for quick switching between sample payloads.

export default function JsonEditor({ label, value, onChange, onLoadSample, presetCases = [], activeCaseId, onSelectCase }) {
  return (
    <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-base font-semibold text-slate-900">{label}</h2>
        <button
          className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-200"
          type="button"
          onClick={onLoadSample}
        >
          Load demo payload
        </button>
      </div>
      {presetCases.length ? (
        <div className="mb-4 flex flex-wrap gap-2">
          {presetCases.map((presetCase) => (
            <button
              key={presetCase.id}
              className={
                activeCaseId === presetCase.id
                  ? "rounded-full border border-blue-600 bg-blue-50 px-3 py-1.5 text-xs font-semibold text-blue-700"
                  : "rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-slate-400 hover:bg-slate-50"
              }
              type="button"
              onClick={() => onSelectCase?.(presetCase)}
            >
              {presetCase.label}
            </button>
          ))}
        </div>
      ) : null}
      <textarea
        className="min-h-80 w-full resize-y rounded-xl border border-slate-300 bg-slate-50 px-3 py-3 font-mono text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:bg-white focus:ring-4 focus:ring-blue-100"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        spellCheck="false"
      />
    </section>
  );
}
