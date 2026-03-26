// Root application component.
// Uses a simple tab-based layout to switch between the two main flows:
// medication reconciliation and data quality validation.

import { useState } from "react";

import DataQualityPage from "./pages/DataQualityPage";
import ReconcilePage from "./pages/ReconcilePage";

const tabs = [
  { id: "reconcile", label: "Medication Reconciliation" },
  { id: "quality", label: "Data Quality Validation" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState("reconcile");

  return (
    <main className="mx-auto max-w-6xl px-5 py-8 md:px-6 md:py-12">
      <header className="mb-6">
        <p className="mb-2 text-sm font-bold uppercase tracking-[0.08em] text-blue-600">
          Clinical Data Reconciliation Engine
        </p>
        <h1 className="mb-3 text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
          AI-Assisted EHR Reconciliation Dashboard
        </h1>
        <p className="max-w-3xl text-sm leading-6 text-slate-600 md:text-base">
          Review conflicting medication records, validate patient record quality, and inspect structured AI-assisted recommendations.
        </p>
      </header>

      <nav className="mb-5 flex flex-wrap gap-3" aria-label="Application sections">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            className={
              activeTab === tab.id
                ? "rounded-full border border-blue-600 bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition"
                : "rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50"
            }
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {activeTab === "reconcile" ? <ReconcilePage /> : <DataQualityPage />}
    </main>
  );
}
