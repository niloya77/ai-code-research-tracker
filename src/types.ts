export interface InsertionRecord {
  id: string;
  insertionTimestamp: number;
  fileUri: string;
  fileName: string;
  originalLineCount: number;
  startLine: number;
  endLine: number;
  // true while waiting for user to confirm it's AI-generated
  pendingConfirmation: boolean;
  // true while waiting for user to click Accept in the status bar
  pendingAcceptance: boolean;
  editedBeforeAcceptance: boolean;
  wantsToModify: boolean | null;
  reviewStartTimestamp: number | null;
  reviewDurationMs: number | null;
  condition: 'reviewed' | 'immediate' | null;
  acceptanceTimestamp: number | null;
  observationWindowEndTimestamp: number | null;
  postAcceptance: PostAcceptanceData;
}

export interface PostAcceptanceData {
  editSessions: EditSession[];
  changedAbsoluteLines: number[];
  totalLinesChanged: number;
  proportionLinesChanged: number;
  changeFrequency: number;
  totalActiveModificationTimeMs: number;
  timeToFirstModificationMs: number | null;
}

export interface EditSession {
  startTimestamp: number;
  lastEditTimestamp: number;
  editCount: number;
}
