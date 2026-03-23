import { useMemo, useState } from "react";

function getStatusTone(value) {
  const normalized = String(value || "").toLowerCase();

  if (["passed", "approved"].includes(normalized)) {
    return "success";
  }

  if (["review"].includes(normalized)) {
    return "warning";
  }

  if (["rejected", "fail", "failed", "high-risk"].includes(normalized)) {
    return "danger";
  }

  return "neutral";
}

function getPillClass(tone) {
  if (tone === "success") {
    return "bg-emerald-100 text-emerald-700";
  }

  if (tone === "warning") {
    return "bg-amber-100 text-amber-800";
  }

  if (tone === "danger") {
    return "bg-rose-100 text-rose-700";
  }

  return "bg-slate-100 text-slate-700";
}

function getSeverityTone(value) {
  const normalized = String(value || "").toLowerCase();

  if (normalized === "high") {
    return "danger";
  }

  if (normalized === "medium") {
    return "warning";
  }

  if (normalized === "low") {
    return "neutral";
  }

  return "neutral";
}

function ScoreBadge({ label, value }) {
  const tone = value >= 80 ? "success" : value >= 60 ? "warning" : "danger";

  return (
    <div className="grid gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-4">
      <span className="text-sm text-slate-500">{label}</span>
      <span className={`inline-flex w-fit items-center rounded-full px-2.5 py-1 text-sm font-semibold ${getPillClass(tone)}`}>
        {value}
      </span>
    </div>
  );
}

function ReconciliationView({ data }) {
  const [decision, setDecision] = useState("");
  const confidencePercent = Math.round((data.confidence_score || 0) * 100);
  const safetyTone = getStatusTone(data.clinical_safety_check);

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">Most likely truth</p>
          <h3 className="text-2xl font-semibold text-slate-900">{data.reconciled_medication}</h3>
        </div>
        <div className="grid min-w-[120px] gap-1 rounded-2xl border border-slate-200 bg-slate-50 p-4">
          <span className="text-sm text-slate-500">Confidence</span>
          <span className="text-xl font-semibold text-slate-900">{confidencePercent}%</span>
        </div>
      </div>

      <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200" aria-hidden="true">
        <div className="h-full rounded-full bg-gradient-to-r from-blue-600 to-teal-500" style={{ width: `${confidencePercent}%` }} />
      </div>

      <div className="flex flex-wrap gap-3">
        <span className={`inline-flex items-center rounded-full px-3 py-1.5 text-sm font-semibold ${getPillClass(safetyTone)}`}>
          Safety check: {data.clinical_safety_check}
        </span>
        {decision ? (
          <span className={`inline-flex items-center rounded-full px-3 py-1.5 text-sm font-semibold ${getPillClass(getStatusTone(decision))}`}>
            Decision: {decision}
          </span>
        ) : null}
      </div>

      <div className="grid gap-2">
        <h4 className="text-sm font-semibold text-slate-900">Why this decision?</h4>
        <p className="text-sm leading-6 text-slate-700">{data.reasoning}</p>
      </div>

      <div className="grid gap-2">
        <h4 className="text-sm font-semibold text-slate-900">Recommended actions</h4>
        <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-slate-700">
          {data.recommended_actions.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      </div>

      <div className="grid gap-2">
        <div className="flex flex-wrap gap-3">
          <button
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
            type="button"
            onClick={() => setDecision("approved")}
            disabled={!!decision}
          >
            Approve suggestion
          </button>
          <button
            className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-200 disabled:cursor-not-allowed disabled:opacity-60"
            type="button"
            onClick={() => setDecision("rejected")}
            disabled={!!decision}
          >
            Reject suggestion
          </button>
        </div>
        {decision ? (
          <p className="text-xs text-slate-500">Decision recorded for this session only.</p>
        ) : null}
      </div>
    </div>
  );
}

function DataQualityView({ data }) {
  const breakdownEntries = [
    ["Completeness", data.breakdown.completeness],
    ["Accuracy", data.breakdown.accuracy],
    ["Timeliness", data.breakdown.timeliness],
    ["Clinical plausibility", data.breakdown.clinical_plausibility],
  ];

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">Overall data quality</p>
          <h3 className="text-2xl font-semibold text-slate-900">{data.overall_score}/100</h3>
        </div>
        <span
          className={`inline-flex items-center rounded-full px-3 py-1.5 text-sm font-semibold ${getPillClass(
            data.overall_score >= 80 ? "success" : data.overall_score >= 60 ? "warning" : "danger",
          )}`}
        >
          {data.overall_score >= 80 ? "Healthy" : data.overall_score >= 60 ? "Needs review" : "Poor quality"}
        </span>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {breakdownEntries.map(([label, value]) => (
          <ScoreBadge key={label} label={label} value={value} />
        ))}
      </div>

      <div className="grid gap-2">
        <h4 className="text-sm font-semibold text-slate-900">Detected issues</h4>
        {data.issues_detected.length ? (
          <div className="grid gap-3">
            {data.issues_detected.map((issue, index) => (
              <div className="rounded-2xl border border-slate-200 bg-white p-4" key={`${issue.field}-${index}`}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <strong>{issue.field}</strong>
                  <span
                    className={`inline-flex items-center rounded-full px-2.5 py-1 text-sm font-semibold ${getPillClass(
                      getSeverityTone(issue.severity),
                    )}`}
                  >
                    {issue.severity}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-700">{issue.issue}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-600">No issues detected.</p>
        )}
      </div>
    </div>
  );
}

export default function ResultCard({ title, data, error }) {
  const viewType = useMemo(() => {
    if (!data) {
      return "empty";
    }

    if ("reconciled_medication" in data) {
      return "reconcile";
    }

    if ("overall_score" in data) {
      return "quality";
    }

    return "raw";
  }, [data]);

  return (
    <section className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      </div>
      {error ? <p className="font-medium text-rose-700">{error}</p> : null}
      {!data ? <p className="text-sm text-slate-600">No result yet.</p> : null}
      {viewType === "reconcile" ? <ReconciliationView data={data} /> : null}
      {viewType === "quality" ? <DataQualityView data={data} /> : null}
      {viewType === "raw" ? (
        <pre className="overflow-auto rounded-xl bg-slate-900 p-4 text-sm text-slate-100">
          {JSON.stringify(data, null, 2)}
        </pre>
      ) : null}
    </section>
  );
}
