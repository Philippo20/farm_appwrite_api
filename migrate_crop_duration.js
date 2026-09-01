const fs = require('fs');
const path = require('path');

const root = __dirname;
const validUnits = new Set(['days', 'months']);

function readEnv() {
  const env = {};
  const body = fs.readFileSync(path.join(root, '.env'), 'utf8');
  for (const rawLine of body.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const match = line.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (!match) continue;
    let value = match[2].trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[match[1]] = value;
  }
  return env;
}

function parseDuration(rawValue) {
  if (Number.isInteger(rawValue) && rawValue > 0) {
    return { value: rawValue, unit: 'days' };
  }
  const match = String(rawValue || '')
    .trim()
    .toLowerCase()
    .match(/(\d+)\s*(day|days|month|months|week|weeks)?/);
  if (!match) return null;
  const value = Number(match[1]);
  if (!Number.isInteger(value) || value <= 0) return null;
  const unit = match[2] || 'days';
  if (unit.startsWith('week')) return { value: value * 7, unit: 'days' };
  return { value, unit: unit.startsWith('month') ? 'months' : 'days' };
}

async function request(env, method, route, body) {
  const endpoint = env.APPWRITE_ENDPOINT.replace(/\/$/, '');
  const response = await fetch(`${endpoint}${route}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Appwrite-Project': env.APPWRITE_PROJECT_ID,
      'X-Appwrite-Key': env.APPWRITE_API_KEY,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!response.ok) {
    throw new Error(`${response.status} ${data?.message || text}`);
  }
  return data;
}

async function listDocuments(env) {
  const documents = [];
  let offset = 0;
  while (true) {
    const queries = [
      JSON.stringify({ method: 'limit', values: [100] }),
      JSON.stringify({ method: 'offset', values: [offset] }),
    ];
    const params = new URLSearchParams();
    for (const query of queries) params.append('queries[]', query);
    const route = `/databases/${encodeURIComponent(env.APPWRITE_DB_ID)}` +
      `/collections/${encodeURIComponent(env.APPWRITE_COLLECTION_ID16)}` +
      `/documents?${params}`;
    const result = await request(env, 'GET', route);
    const page = result.documents || [];
    documents.push(...page);
    if (page.length < 100) return documents;
    offset += page.length;
  }
}

async function main() {
  const env = readEnv();
  for (const key of [
    'APPWRITE_ENDPOINT',
    'APPWRITE_PROJECT_ID',
    'APPWRITE_API_KEY',
    'APPWRITE_DB_ID',
    'APPWRITE_COLLECTION_ID16',
  ]) {
    if (!env[key]) throw new Error(`Missing ${key} in .env`);
  }

  const documents = await listDocuments(env);
  let migrated = 0;
  let unchanged = 0;
  const unresolved = [];

  for (const document of documents) {
    const currentValue = Number(document.plant_duration_value);
    const currentUnit = String(document.plant_duration_unit || '').toLowerCase();
    if (Number.isInteger(currentValue) && currentValue > 0 && validUnits.has(currentUnit)) {
      unchanged += 1;
      continue;
    }

    const duration = parseDuration(document.plant_duration);
    if (!duration) {
      unresolved.push(document.$id);
      continue;
    }
    const route = `/databases/${encodeURIComponent(env.APPWRITE_DB_ID)}` +
      `/collections/${encodeURIComponent(env.APPWRITE_COLLECTION_ID16)}` +
      `/documents/${encodeURIComponent(document.$id)}`;
    await request(env, 'PATCH', route, {
      data: {
        plant_duration_value: duration.value,
        plant_duration_unit: duration.unit,
      },
    });
    migrated += 1;
  }

  console.log(JSON.stringify({ migrated, unchanged, unresolved }, null, 2));
  if (unresolved.length > 0) {
    process.exitCode = 2;
    return;
  }

  if (process.argv.includes('--delete-legacy')) {
    const route = `/databases/${encodeURIComponent(env.APPWRITE_DB_ID)}` +
      `/collections/${encodeURIComponent(env.APPWRITE_COLLECTION_ID16)}` +
      '/attributes/plant_duration';
    await request(env, 'DELETE', route);
    console.log('Legacy plant_duration attribute deletion requested.');
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
