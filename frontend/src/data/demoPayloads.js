export const reconcileCases = [
  {
    id: "renal-dose-adjustment",
    label: "Renal Dose Adjustment",
    payload: {
      patient_context: {
        age: 67,
        conditions: ["Type 2 Diabetes", "Hypertension"],
        recent_labs: { eGFR: 45 },
      },
      sources: [
        {
          system: "Hospital EHR",
          medication: "Metformin 1000mg twice daily",
          last_updated: "2024-10-15",
          source_reliability: "high",
        },
        {
          system: "Primary Care",
          medication: "Metformin 500mg twice daily",
          last_updated: "2025-01-20",
          source_reliability: "high",
        },
        {
          system: "Pharmacy",
          medication: "Metformin 1000mg daily",
          last_filled: "2025-01-25",
          source_reliability: "medium",
        },
      ],
    },
  },
  {
    id: "recent-pharmacy-fill",
    label: "Recent Pharmacy Fill",
    payload: {
      patient_context: {
        age: 54,
        conditions: ["Coronary Artery Disease"],
        recent_labs: {},
      },
      sources: [
        {
          system: "Hospital EHR",
          medication: "Aspirin 325mg daily",
          last_updated: "2024-08-15",
          source_reliability: "high",
        },
        {
          system: "Clinic EHR",
          medication: "Aspirin 81mg daily",
          last_updated: "2024-12-01",
          source_reliability: "high",
        },
        {
          system: "Pharmacy",
          medication: "Aspirin 81mg daily",
          last_filled: "2024-12-03",
          source_reliability: "medium",
        },
      ],
    },
  },
  {
    id: "mixed-source-conflict",
    label: "Mixed Source Conflict",
    payload: {
      patient_context: {
        age: 72,
        conditions: ["Atrial Fibrillation", "CKD Stage 3"],
        recent_labs: { eGFR: 39 },
      },
      sources: [
        {
          system: "Specialist Cardiology",
          medication: "Apixaban 5mg twice daily",
          last_updated: "2025-02-11",
          source_reliability: "high",
        },
        {
          system: "Hospital Discharge Summary",
          medication: "Apixaban 2.5mg twice daily",
          last_updated: "2025-02-05",
          source_reliability: "high",
        },
        {
          system: "Patient Portal",
          medication: "Not taking apixaban",
          last_updated: "2025-02-10",
          source_reliability: "low",
        },
      ],
    },
  },
];

export const dataQualityCases = [
  {
    id: "implausible-vitals",
    label: "Implausible Vitals",
    payload: {
      demographics: {
        name: "John Doe",
        dob: "1955-03-15",
        gender: "M",
      },
      medications: ["Metformin 500mg", "Lisinopril 10mg"],
      allergies: [],
      conditions: ["Type 2 Diabetes"],
      vital_signs: {
        blood_pressure: "340/180",
        heart_rate: 72,
      },
      last_updated: "2024-06-15",
    },
  },
  {
    id: "stale-record",
    label: "Stale Record",
    payload: {
      demographics: {
        name: "Maria Chen",
        dob: "1948-09-02",
        gender: "F",
      },
      medications: ["Atorvastatin 20mg"],
      allergies: ["Sulfa"],
      conditions: ["Hyperlipidemia"],
      vital_signs: {
        blood_pressure: "128/74",
        heart_rate: 68,
      },
      last_updated: "2023-02-10",
    },
  },
  {
    id: "missing-fields",
    label: "Missing Fields",
    payload: {
      demographics: {
        name: null,
        dob: null,
        gender: "UnknownCode",
      },
      medications: [],
      allergies: [],
      conditions: [],
      vital_signs: {
        blood_pressure: "120/80",
        heart_rate: 72,
      },
      last_updated: null,
    },
  },
];
