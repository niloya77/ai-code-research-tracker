const https = require('https');

const SUPABASE_URL = 'https://qcyxsuvbcdsxprkzlkkh.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFjeXhzdXZiY2RzeHBya3psa2toIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk4ODg1MzUsImV4cCI6MjA5NTQ2NDUzNX0.g52agmYZgdOmDmNreANtCPW-nYYmiBZH9j-KNNX7n-k';

const now = Date.now();

const row = {
  record_id: `test-${now}`,
  participant_id: 'TEST_USER',
  insertion_timestamp: now,
  file_name: 'test.py',
  original_line_count: 15,
  condition: 'immediate',
  acceptance_timestamp: now + 5000,
  time_to_accept_s: 5.00,
  edited_before_acceptance: false,
  total_lines_changed: 3,
  proportion_lines_changed: 0.2,
  change_frequency: 4,
  total_active_modification_time_s: 31.34,
  time_to_first_modification_s: 12.5,
  observation_complete: false,
  review_duration_s: null,
  last_synced: now
};

const body = JSON.stringify([row]);
const urlObj = new URL(`${SUPABASE_URL}/rest/v1/insertion_records`);

const options = {
  hostname: urlObj.hostname,
  path: urlObj.pathname,
  method: 'POST',
  headers: {
    apikey: SUPABASE_KEY,
    Authorization: `Bearer ${SUPABASE_KEY}`,
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(body),
    Prefer: 'resolution=merge-duplicates'
  }
};

const req = https.request(options, res => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    if (res.statusCode >= 200 && res.statusCode < 300) {
      console.log('✓ Supabase\'e başarıyla gönderildi! Status:', res.statusCode);
    } else {
      console.log('✗ Hata! Status:', res.statusCode);
      console.log('Response:', data);
    }
  });
});

req.on('error', err => console.error('Bağlantı hatası:', err.message));
req.write(body);
req.end();
