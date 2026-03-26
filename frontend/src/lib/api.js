// Shared API client for backend communication.
// All protected endpoints require the x-api-key header.

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const API_KEY = import.meta.env.VITE_APP_API_KEY || "demo-key";

async function postJson(path, payload) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": API_KEY,
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Request failed");
  }

  return response.json();
}

export function reconcileMedication(payload) {
  return postJson("/api/reconcile/medication", payload);
}

export function validateDataQuality(payload) {
  return postJson("/api/validate/data-quality", payload);
}
