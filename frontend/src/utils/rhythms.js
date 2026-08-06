import { RHYTHM_GROUPS, RHYTHM_LABELS } from "../types/ecgState";

const LEGACY_LABEL_TO_ENGINE = {
  "Sinus Rhythm": "NSR",
  "Sinus Bradycardia": "SINUS_BRADY",
  "Sinus Tachycardia": "SINUS_TACHY",
  "Atrial Fibrillation": "AFIB",
  "Atrial Flutter": "AFLUTTER",
  "Junctional Rhythm": "JUNCTIONAL",
  "1st Degree AV Block": "AVB1",
  "2nd Degree AV Block": "AVB2_II",
  "3rd Degree AV Block": "AVB3",
  SVT: "SVT",
  "Ventricular Tachycardia": "VT",
  "Ventricular Fibrillation": "VF",
  Asystole: "ASYSTOLE",
  "Paced Rhythm": "NSR",
};

const LABEL_TO_ENGINE = Object.fromEntries(
  Object.entries(RHYTHM_LABELS).map(([rhythm, label]) => [label, rhythm])
);

export const ENGINE_RHYTHM_OPTIONS = RHYTHM_GROUPS.map((group) => ({
  label: group.label,
  rhythms: group.rhythms.map((rhythm) => ({
    value: rhythm,
    label: RHYTHM_LABELS[rhythm] || rhythm,
  })),
}));

export function getEngineRhythm(rhythm) {
  if (!rhythm) return "NSR";
  if (RHYTHM_LABELS[rhythm]) return rhythm;
  return LABEL_TO_ENGINE[rhythm] || LEGACY_LABEL_TO_ENGINE[rhythm] || "NSR";
}

export function getMonitorRhythmLabel(engineRhythm) {
  return RHYTHM_LABELS[engineRhythm] || "Normal Sinus Rhythm";
}
