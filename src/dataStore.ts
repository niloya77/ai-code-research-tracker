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
      'time_to_accept_s',
      'edited_before_acceptance',
      'total_lines_changed',
      'proportion_lines_changed',
      'change_frequency',
      'total_active_modification_time_s',
      'time_to_first_modification_s',
      'review_duration_s',
      'self_reported_confidence',
      'block_deleted',
      'block_deletion_timestamp_s'
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
          r.acceptanceTimestamp ? ((r.acceptanceTimestamp - r.insertionTimestamp) / 1000).toFixed(2) : '',
          r.editedBeforeAcceptance ? 1 : 0,
          r.postAcceptance.totalLinesChanged,
          r.postAcceptance.proportionLinesChanged.toFixed(4),
          r.postAcceptance.changeFrequency,
          (r.postAcceptance.totalActiveModificationTimeMs / 1000).toFixed(2),
          r.postAcceptance.timeToFirstModificationMs !== null ? (r.postAcceptance.timeToFirstModificationMs / 1000).toFixed(2) : '',
          r.reviewDurationMs !== null ? (r.reviewDurationMs / 1000).toFixed(2) : '',
          r.selfReportedConfidence ?? '',
          r.blockDeleted ? 1 : 0,
          r.blockDeletionTimestamp !== null ? (r.blockDeletionTimestamp / 1000).toFixed(2) : ''
        ].join(',')
      );

    return [header, ...rows].join('\n');
  }
}
