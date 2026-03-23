import { useState } from "react";

import JsonEditor from "../components/JsonEditor";
import ResultCard from "../components/ResultCard";
import { reconcileCases } from "../data/demoPayloads";
import { reconcileMedication } from "../lib/api";

const defaultCase = reconcileCases[0];
const initialValue = JSON.stringify(defaultCase.payload, null, 2);

export default function ReconcilePage() {
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
    setResult(null);

    try {
      const payload = JSON.parse(payloadText);
      const response = await reconcileMedication(payload);
      setResult(response);
    } catch (submitError) {
      setError(submitError.message || "Unable to reconcile medication data.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="grid gap-4">
      <JsonEditor
        label="Medication Reconciliation Payload"
        value={payloadText}
        onChange={setPayloadText}
        onLoadSample={() => loadCase(defaultCase)}
        presetCases={reconcileCases}
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
          {isLoading ? "Reconciling..." : "Run reconciliation"}
        </button>
      </div>
      <ResultCard title="Reconciliation Result" data={result} error={error} />
    </div>
  );
}
