import * as vscode from 'vscode';
import { InsertionRecord } from './types';

// Edits within 5 seconds of each other belong to the same edit session
const IDLE_THRESHOLD_MS = 5000;
// 7-day observation window after acceptance
const OBSERVATION_WINDOW_MS = 7 * 24 * 60 * 60 * 1000;

export class BlockTracker {
  private records: Map<string, InsertionRecord> = new Map();

  add(record: InsertionRecord): void {
    this.records.set(record.id, record);
  }

  get(id: string): InsertionRecord | undefined {
    return this.records.get(id);
  }

  getAll(): InsertionRecord[] {
    return Array.from(this.records.values());
  }

  remove(id: string): void {
    this.records.delete(id);
  }

  // Returns records whose observation window just elapsed (need re-sync to Supabase)
  loadAll(records: InsertionRecord[]): InsertionRecord[] {
    this.records.clear();
    const now = Date.now();
    const newlyCompleted: InsertionRecord[] = [];
    for (const r of records) {
      // Migrate records saved before these fields existed
      r.observationComplete = r.observationComplete ??
        (r.observationWindowEndTimestamp ? now > r.observationWindowEndTimestamp : false);
      r.lastSynced = r.lastSynced ?? null;
      // Mark complete if window already elapsed
      if (!r.observationComplete && r.observationWindowEndTimestamp && now > r.observationWindowEndTimestamp) {
        r.observationComplete = true;
        newlyCompleted.push(r);
      }
      this.records.set(r.id, r);
    }
    return newlyCompleted;
  }

  // Returns records whose observation window has elapsed since the last check
  checkExpiredWindows(): InsertionRecord[] {
    const now = Date.now();
    const newlyCompleted: InsertionRecord[] = [];
    for (const r of this.records.values()) {
      if (!r.observationComplete && r.observationWindowEndTimestamp && now > r.observationWindowEndTimestamp) {
        r.observationComplete = true;
        newlyCompleted.push(r);
      }
    }
    return newlyCompleted;
  }

  handleDocumentChange(
    event: vscode.TextDocumentChangeEvent,
    onModification: (record: InsertionRecord) => void,
    onDeletion?: (record: InsertionRecord) => void
  ): void {
    const fileUri = event.document.uri.toString();
    const now = Date.now();

    for (const record of this.records.values()) {
      if (record.fileUri !== fileUri) continue;
      if (record.pendingConfirmation) {
        for (const change of event.contentChanges) {
          this.shiftLines(record, change);
        }
        continue;
      }

      // Record pre-change positions to check if changes touched this block
      const preStartLine = record.startLine;
      const preEndLine = record.endLine;
      let touchedBlock = false;

      for (const change of event.contentChanges) {
        const cs = change.range.start.line;
        const ce = change.range.end.line;
        if (!(ce < preStartLine || cs > preEndLine)) {
          touchedBlock = true;
        }
        this.processChange(record, change, now, onModification, onDeletion);
      }

      // Only if a change actually overlapped this block: check if all lines are now blank/gone
      if (touchedBlock && !record.blockDeleted && record.acceptanceTimestamp && !record.pendingAcceptance) {
        const doc = event.document;
        const checkEnd = Math.min(record.endLine, record.startLine + record.originalLineCount - 1);
        let allBlank = true;
        for (let l = record.startLine; l <= checkEnd; l++) {
          if (l < doc.lineCount && doc.lineAt(l).text.trim().length > 0) {
            allBlank = false;
            break;
          }
        }
        if (allBlank) {
          record.blockDeleted = true;
          record.blockDeletionTimestamp = now;
          onDeletion?.(record);
        }
      }
    }
  }

  private processChange(
    record: InsertionRecord,
    change: vscode.TextDocumentContentChangeEvent,
    now: number,
    onModification: (record: InsertionRecord) => void,
    onDeletion?: (record: InsertionRecord) => void
  ): void {
    const changeStart = change.range.start.line;
    const changeEnd = change.range.end.line;
    const insertedNewlines = (change.text.match(/\n/g) ?? []).length;
    const removedLines = changeEnd - changeStart;
    const lineDelta = insertedNewlines - removedLines;

    const isAbove = changeEnd < record.startLine;
    const isBelow = changeStart > record.endLine;

    if (isAbove) {
      record.startLine += lineDelta;
      record.endLine += lineDelta;
      return;
    }

    if (isBelow) return;

    // Detect full block deletion before clamping
    // Use original footprint to avoid false negatives when endLine grew due to nested pastes
    const effectiveEndLine = Math.min(record.endLine, record.startLine + record.originalLineCount - 1);
    const newEndLine = record.endLine + lineDelta;
    const blockFullyCovered = change.text === '' && changeStart <= record.startLine && changeEnd >= effectiveEndLine;
    if ((newEndLine < record.startLine || blockFullyCovered) && !record.blockDeleted && record.acceptanceTimestamp) {
      record.blockDeleted = true;
      record.blockDeletionTimestamp = now;
      onDeletion?.(record);
      return;
    }

    // Change overlaps with the block — adjust block size and record as modification
    record.endLine = Math.max(record.startLine, newEndLine);

    if (record.pendingAcceptance) {
      record.editedBeforeAcceptance = true;
      return;
    }

    if (record.acceptanceTimestamp && record.observationWindowEndTimestamp) {
      if (now <= record.observationWindowEndTimestamp) {
        this.recordPostAcceptanceEdit(record, changeStart, changeEnd, now);
        onModification(record);
      } else if (!record.observationComplete) {
        record.observationComplete = true;
        onModification(record);
      }
    }
  }

  private shiftLines(
    record: InsertionRecord,
    change: vscode.TextDocumentContentChangeEvent
  ): void {
    const changeEnd = change.range.end.line;
    if (changeEnd >= record.startLine) return;

    const insertedNewlines = (change.text.match(/\n/g) ?? []).length;
    const removedLines = change.range.end.line - change.range.start.line;
    const lineDelta = insertedNewlines - removedLines;
    record.startLine += lineDelta;
    record.endLine += lineDelta;
  }

  private recordPostAcceptanceEdit(
    record: InsertionRecord,
    changeStart: number,
    changeEnd: number,
    now: number
  ): void {
    const data = record.postAcceptance;

    // Collect affected absolute line numbers (intersect with current block range)
    const overlapStart = Math.max(changeStart, record.startLine);
    const overlapEnd = Math.min(changeEnd, record.endLine);
    for (let l = overlapStart; l <= Math.max(overlapStart, overlapEnd); l++) {
      if (!data.changedAbsoluteLines.includes(l)) {
        data.changedAbsoluteLines.push(l);
      }
    }

    // Track edit sessions (consecutive edits within IDLE_THRESHOLD belong to same session)
    const lastSession = data.editSessions[data.editSessions.length - 1];
    if (lastSession && now - lastSession.lastEditTimestamp < IDLE_THRESHOLD_MS) {
      lastSession.lastEditTimestamp = now;
      lastSession.editCount++;
    } else {
      data.editSessions.push({ startTimestamp: now, lastEditTimestamp: now, editCount: 1 });
    }

    if (data.timeToFirstModificationMs === null) {
      data.timeToFirstModificationMs = now - record.acceptanceTimestamp!;
    }

    // Recalculate aggregate metrics
    data.totalLinesChanged = data.changedAbsoluteLines.length;
    data.proportionLinesChanged = Math.min(
      1.0,
      data.totalLinesChanged / record.originalLineCount
    );
    // Session duration = time from first to last edit + 1s minimum per session
    data.totalActiveModificationTimeMs = data.editSessions.reduce((sum, s) => {
      return sum + Math.max(1000, s.lastEditTimestamp - s.startTimestamp + 1000);
    }, 0);
  }

  accept(id: string): void {
    const record = this.records.get(id);
    if (!record) return;

    const now = Date.now();
    record.condition = record.editedBeforeAcceptance ? 'reviewed' : 'immediate';
    record.acceptanceTimestamp = now;
    record.observationWindowEndTimestamp = now + OBSERVATION_WINDOW_MS;
    record.observationComplete = false;
    record.pendingAcceptance = false;
  }

  reject(id: string): void {
    const record = this.records.get(id);
    if (!record) return;

    record.condition = 'rejected';
    record.pendingConfirmation = false;
    record.pendingAcceptance = false;
    // 7-day window from insertion so checkExpiredWindows() can close it automatically
    record.observationWindowEndTimestamp = record.insertionTimestamp + OBSERVATION_WINDOW_MS;
  }

  confirmAI(id: string): void {
    const record = this.records.get(id);
    if (!record) return;
    record.pendingConfirmation = false;
  }
}
