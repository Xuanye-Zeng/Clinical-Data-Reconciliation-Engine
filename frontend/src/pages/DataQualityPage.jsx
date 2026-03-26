// Data quality validation page.
// Lets the user load a sample patient record or type their own JSON,
// submit it to POST /api/validate/data-quality, and view the result.

import { useState } from "react";

import JsonEditor from "../components/JsonEditor";
import ResultCard from "../components/ResultCard";
import { dataQualityCases } from "../data/demoPayloads";
import { validateDataQuality } from "../lib/api";

const defaultCase = dataQualityCases[0];
const initialValue = JSON.stringify(defaultCase.payload, null, 2);

export default function DataQualityPage() {
  const [activeCaseId, setActiveCaseId] = useState(defaultCase.id);
  const [payloadText, setPayloadText] = useState(initialValue);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  function loadCase(selectedCase) {
    setActiveCaseId(selectedCase.id);
    setPayloadText(JSON.stringify(selectedCase.payload, null, 2));
  }

  async function handleSubmit() {
    setIsLoading(true);
    setError("");
    setResult(null); // Clear stale result so it doesn't linger alongside a new error

    try {
      const payload = JSON.parse(payloadText);
      const response = await validateDataQuality(payload);
      setResult(response);
    } catch (submitError) {
      setError(submitError.message || "Unable to validate data quality.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="grid gap-4">
      <JsonEditor
        label="Data Quality Payload"
        value={payloadText}
        onChange={setPayloadText}
        onLoadSample={() => loadCase(defaultCase)}
        presetCases={dataQualityCases}
        activeCaseId={activeCaseId}
        onSelectCase={loadCase}
      />
      <div className="flex justify-start">
        <button
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          type="button"
          onClick={handleSubmit}
          disabled={isLoading}
        >
          {isLoading ? "Validating..." : "Run data quality check"}
        </button>
      </div>
      <ResultCard title="Data Quality Result" data={result} error={error} />
    </div>
  );
}
