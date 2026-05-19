import * as vscode from 'vscode';

export interface DetectedInsertion {
  startLine: number;
  endLine: number;
  lineCount: number;
}

// Minimum thresholds: multi-line OR a substantial single-line paste
const MIN_CHARS = 80;
const MIN_LINES = 2;

export function detectLargeInsertion(
  event: vscode.TextDocumentChangeEvent
): DetectedInsertion | null {
  let totalChars = 0;
  let totalNewlines = 0;
  let earliestStartLine = Infinity;

  for (const change of event.contentChanges) {
    if (change.text.length === 0) continue;
    totalChars += change.text.length;
    const insertedNewlines = (change.text.match(/\n/g) ?? []).length;
    totalNewlines += insertedNewlines;
    if (change.range.start.line < earliestStartLine) {
      earliestStartLine = change.range.start.line;
    }
  }

  const lineCount = totalNewlines + 1;
  const isCodePaste = lineCount >= MIN_LINES || totalChars >= MIN_CHARS;

  if (isCodePaste && earliestStartLine !== Infinity) {
    return {
      startLine: earliestStartLine,
      endLine: earliestStartLine + totalNewlines,
      lineCount
    };
  }

  return null;
}
