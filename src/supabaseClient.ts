import * as https from 'https';
import * as vscode from 'vscode';
import { InsertionRecord } from './types';

interface SupabaseRow {
  record_id: string;
  participant_id: string;
  insertion_timestamp: number;
  file_name: string;
  original_line_count: number;
  condition: string | null;
  acceptance_timestamp: number | null;
  time_to_accept_s: number | null;
  edited_before_acceptance: boolean;
  total_lines_changed: number;
  proportion_lines_changed: number;
  change_frequency: number;
  total_active_modification_time_s: number;
  time_to_first_modification_s: number | null;
  observation_complete: boolean;
  review_duration_s: number | null;
  self_reported_confidence: number | null;
  block_deleted: boolean;
  block_deletion_timestamp_s: number | null;
  last_synced: number;
}

const DEFAULT_URL = 'https://wvyrgdbjmxfnmduzhnha.supabase.co';
const DEFAULT_KEY = 'sb_publishable_ZeDW_bl7vuno6k4oFBp71Q_QGowtcgI';

export class SupabaseClient {
  private supabaseUrl: string;
  private supabaseKey: string;

  constructor() {
    const cfg = vscode.workspace.getConfiguration('aiTracker');
    this.supabaseUrl = (cfg.get<string>('supabaseUrl', '') || DEFAULT_URL).replace(/\/$/, '');
    this.supabaseKey = cfg.get<string>('supabaseKey', '') || DEFAULT_KEY;
  }

  isConfigured(): boolean {
    return this.supabaseUrl.length > 0 && this.supabaseKey.length > 0;
  }

  async sync(record: InsertionRecord, participantId: string): Promise<void> {
    if (!this.isConfigured()) return;

    const now = Date.now();
    const observationDone =
      record.observationWindowEndTimestamp !== null &&
      now > record.observationWindowEndTimestamp;

    const row: SupabaseRow = {
      record_id: record.id,
      participant_id: participantId,
      insertion_timestamp: record.insertionTimestamp,
      file_name: record.fileName,
      original_line_count: record.originalLineCount,
      condition: record.condition,
      acceptance_timestamp: record.acceptanceTimestamp,
      time_to_accept_s:
        record.acceptanceTimestamp !== null
          ? Math.round((record.acceptanceTimestamp - record.insertionTimestamp) / 1000 * 100) / 100
          : null,
      edited_before_acceptance: record.editedBeforeAcceptance,
      total_lines_changed: record.postAcceptance.totalLinesChanged,
      proportion_lines_changed: record.postAcceptance.proportionLinesChanged,
      change_frequency: record.postAcceptance.changeFrequency,
      total_active_modification_time_s:
        Math.round(record.postAcceptance.totalActiveModificationTimeMs / 1000 * 100) / 100,
      time_to_first_modification_s:
        record.postAcceptance.timeToFirstModificationMs !== null
          ? Math.round(record.postAcceptance.timeToFirstModificationMs / 1000 * 100) / 100
          : null,
      observation_complete: observationDone,
      review_duration_s: record.reviewDurationMs !== null ? Math.round(record.reviewDurationMs / 1000 * 100) / 100 : null,
      self_reported_confidence: record.selfReportedConfidence,
      block_deleted: record.blockDeleted,
      block_deletion_timestamp_s: record.blockDeletionTimestamp !== null ? Math.round(record.blockDeletionTimestamp / 1000 * 100) / 100 : null,
      last_synced: now
    };

    await this.upsert(row);
  }

  private upsert(row: SupabaseRow): Promise<void> {
    return new Promise(resolve => {
      const body = JSON.stringify([row]);
      const urlObj = new URL(`${this.supabaseUrl}/rest/v1/insertion_records`);

      const options: https.RequestOptions = {
        hostname: urlObj.hostname,
        path: urlObj.pathname,
        method: 'POST',
        headers: {
          apikey: this.supabaseKey,
          Authorization: `Bearer ${this.supabaseKey}`,
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(body),
          Prefer: 'resolution=merge-duplicates'
        }
      };

      const req = https.request(options, res => {
        res.resume();
        res.on('end', resolve);
      });

      req.on('error', err => {
        console.error('[AITracker] Supabase sync error:', err.message);
        resolve();
      });

      req.write(body);
      req.end();
    });
  }
}
