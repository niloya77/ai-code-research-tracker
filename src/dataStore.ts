import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';
import { InsertionRecord } from './types';

export class DataStore {
  private filePath: string;

  constructor(context: vscode.ExtensionContext) {
    const storageDir = context.globalStorageUri.fsPath;
    if (!fs.existsSync(storageDir)) {
      fs.mkdirSync(storageDir, { recursive: true });
    }
    this.filePath = path.join(storageDir, 'insertion-records.json');
  }

  load(): InsertionRecord[] {
    try {
      if (!fs.existsSync(this.filePath)) return [];
      return JSON.parse(fs.readFileSync(this.filePath, 'utf8')) as InsertionRecord[];
    } catch {
      return [];
    }
  }

  save(records: InsertionRecord[]): void {
    try {
      fs.writeFileSync(this.filePath, JSON.stringify(records, null, 2), 'utf8');
    } catch (err) {
      console.error('[AITracker] Failed to save:', err);
    }
  }

  buildCSV(records: InsertionRecord[]): string {
    const header = [
      'insertion_id',
      'insertion_timestamp',
      'file_name',
      'original_line_count',
      'condition',
      'acceptance_timestamp',
      'time_to_accept_ms',
      'edited_before_acceptance',
      'total_lines_changed',
      'proportion_lines_changed',
      'change_frequency',
      'total_active_modification_time_ms',
      'time_to_first_modification_ms',
      'review_duration_ms'
    ].join(',');

    const rows = records
      .filter(r => r.condition !== null)
      .map(r =>
        [
          r.id,
          r.insertionTimestamp,
          r.fileName,
          r.originalLineCount,
          r.condition ?? '',
          r.acceptanceTimestamp ?? '',
          r.acceptanceTimestamp ? r.acceptanceTimestamp - r.insertionTimestamp : '',
          r.editedBeforeAcceptance ? 1 : 0,
          r.postAcceptance.totalLinesChanged,
          r.postAcceptance.proportionLinesChanged.toFixed(4),
          r.postAcceptance.changeFrequency,
          r.postAcceptance.totalActiveModificationTimeMs,
          r.postAcceptance.timeToFirstModificationMs ?? '',
          r.reviewDurationMs ?? ''
        ].join(',')
      );

    return [header, ...rows].join('\n');
  }
}
