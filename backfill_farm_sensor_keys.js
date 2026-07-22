const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const root = __dirname;

function readEnv() {
  const envPath = path.join(root, '.env');
  const env = {};
  const body = fs.readFileSync(envPath, 'utf8');
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

function farmSensorKey() {
  return `fs_farm_sensor_${crypto.randomBytes(32).toString('base64url')}`;
}

async function request(env, method, route, body) {
  const base = env.APPWRITE_ENDPOINT.replace(/\/$/, '');
  const response = await fetch(`${base}${route}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Appwrite-Project': env.APPWRITE_PROJECT_ID,
      'X-Appwrite-Key': env.APPWRITE_API_KEY,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) {
    throw new Error(`${response.status} ${data?.message || text}`);
  }
  return data;
}

async function main() {
  const env = readEnv();
  const databaseId = encodeURIComponent(env.APPWRITE_DB_ID);
  const collectionId = encodeURIComponent(env.APPWRITE_COLLECTION_ID2);
  const route = `/databases/${databaseId}/collections/${collectionId}/documents`;
  const result = await request(env, 'GET', `${route}?limit=500`);
  let updated = 0;

  for (const farm of result.documents || []) {
    if (farm.sensor_ingest_api_key) continue;
    await request(env, 'PATCH', `${route}/${encodeURIComponent(farm.$id)}`, {
      data: { sensor_ingest_api_key: farmSensorKey() },
    });
    updated += 1;
  }

  console.log(JSON.stringify({ scanned: result.total || 0, updated }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
