const fs = require('fs');
const path = require('path');

const root = __dirname;

const collectionSpecs = [
  { index: 1, file: '1_users.py', name: 'Users' },
  { index: 2, file: '2_farms.py', name: 'Farms' },
  { index: 3, file: '3_plant_type.py', name: 'Plant types' },
  { index: 4, file: '4_inventory.py', name: 'Inventory' },
  { index: 5, file: '5_batches.py', name: 'Batches' },
  { index: 6, file: '6_audits.py', name: 'Audits' },
  { index: 7, file: '7_fulfillment.py', name: 'Fulfillment' },
  { index: 8, file: '8_sales.py', name: 'Sales' },
  { index: 9, file: '9_package.py', name: 'Package' },
  { index: 10, file: '10_wallet.py', name: 'Wallet' },
  { index: 11, file: '11_sensors.py', name: 'Sensors' },
  { index: 12, file: '12_alerts.py', name: 'Alerts' },
  { index: 13, file: '13_thresholds.py', name: 'Thresholds' },
  { index: 14, file: '14_logs.py', name: 'Logs' },
  { index: 15, file: '15_grow_stages.py', name: 'Grow stages' },
  { index: 16, file: '16_crops.py', name: 'Crops' },
  { index: 17, file: '17_pricing.py', name: 'Pricing' },
  { index: 18, file: '18_system_config.py', name: 'System Config' },
  { index: 19, file: '19_backups.py', name: 'Backups' },
  { index: 20, file: '20_inventory_movements.py', name: 'Inventory Movements' },
  { index: 21, file: '21_sensor_readings.py', name: 'Sensor Readings' },
  { index: 22, file: '22_fund_requests.py', name: 'Fund Requests' },
  { index: 23, file: '23_farm_tasks.py', name: 'Farm Tasks' },
  { index: 25, file: '25_notifications.py', name: 'Notifications' },
  { index: 26, file: '26_input_confirmations.py', name: 'Input confirmations' },
  { index: 27, file: '27_caretaker_settings.py', name: 'Caretaker settings' },
  { index: 28, file: '28_off_takers.py', name: 'Off-takers' },
  { index: 29, file: '29_off_taker_update_requests.py', name: 'Off-taker update requests' },
  { index: 30, file: '30_traceability_settings.py', name: 'Traceability settings', defaultId: 'traceability_settings' },
  { index: 31, file: '31_batch_traceability.py', name: 'Batch traceability', defaultId: 'batch_traceability' },
  { index: 32, file: '32_traceability_promotions.py', name: 'Traceability promotions', defaultId: 'traceability_promotions' },
  { index: 33, file: '33_traceability_events.py', name: 'Traceability events', defaultId: 'traceability_events' },
];

function selectedCollectionSpecs() {
  const onlyArg = process.argv.find((arg) => arg.startsWith('--only='));
  if (!onlyArg) return collectionSpecs;
  const indexes = onlyArg
    .slice('--only='.length)
    .split(',')
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isInteger(item));
  if (indexes.length === 0) throw new Error('Use --only with collection numbers, for example --only=7');
  return collectionSpecs.filter((spec) => indexes.includes(spec.index));
}

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

function stripComments(source) {
  return source
    .split(/\r?\n/)
    .map((line) => {
      let quote = null;
      for (let i = 0; i < line.length; i += 1) {
        const ch = line[i];
        if ((ch === '"' || ch === "'") && line[i - 1] !== '\\') {
          quote = quote === ch ? null : quote || ch;
        }
        if (ch === '#' && !quote) return line.slice(0, i);
      }
      return line;
    })
    .join('\n');
}

function findAttributeCalls(source) {
  const calls = [];
  const regex = /db\.create_([a-z_]+)_attribute\s*\(/g;
  let match;
  while ((match = regex.exec(source)) !== null) {
    let pos = regex.lastIndex;
    let depth = 1;
    let quote = null;
    while (pos < source.length && depth > 0) {
      const ch = source[pos];
      if ((ch === '"' || ch === "'") && source[pos - 1] !== '\\') {
        quote = quote === ch ? null : quote || ch;
      } else if (!quote && ch === '(') {
        depth += 1;
      } else if (!quote && ch === ')') {
        depth -= 1;
      }
      pos += 1;
    }
    calls.push({ type: match[1], body: source.slice(regex.lastIndex, pos - 1) });
  }
  return calls;
}

function splitArgs(body) {
  const parts = [];
  let start = 0;
  let depth = 0;
  let quote = null;
  for (let i = 0; i < body.length; i += 1) {
    const ch = body[i];
    if ((ch === '"' || ch === "'") && body[i - 1] !== '\\') {
      quote = quote === ch ? null : quote || ch;
    } else if (!quote && (ch === '[' || ch === '(' || ch === '{')) {
      depth += 1;
    } else if (!quote && (ch === ']' || ch === ')' || ch === '}')) {
      depth -= 1;
    } else if (!quote && depth === 0 && ch === ',') {
      parts.push(body.slice(start, i).trim());
      start = i + 1;
    }
  }
  const tail = body.slice(start).trim();
  if (tail) parts.push(tail);
  return parts;
}

function parseValue(value) {
  const trimmed = value.trim();
  if (trimmed === 'True') return true;
  if (trimmed === 'False') return false;
  if (/^-?\d+(\.\d+)?$/.test(trimmed)) return Number(trimmed);
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1);
  }
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
    return splitArgs(trimmed.slice(1, -1)).map(parseValue);
  }
  return trimmed;
}

function parseAttributes(file) {
  const source = stripComments(fs.readFileSync(path.join(root, file), 'utf8'));
  return findAttributeCalls(source).map((call) => {
    const args = {};
    for (const part of splitArgs(call.body)) {
      const index = part.indexOf('=');
      if (index === -1) continue;
      const key = part.slice(0, index).trim();
      args[key] = parseValue(part.slice(index + 1));
    }
    return {
      type: call.type,
      key: args.key,
      required: Boolean(args.required),
      size: args.size,
      elements: args.elements,
      min: args.min,
      max: args.max,
      default: args.default,
      array: Boolean(args.array),
    };
  });
}

function toAttributeEndpoint(type) {
  const map = {
    string: 'string',
    email: 'email',
    enum: 'enum',
    float: 'float',
    integer: 'integer',
    boolean: 'boolean',
    datetime: 'datetime',
  };
  return map[type];
}

function toAttributePayload(attribute) {
  const payload = {
    key: attribute.key,
    required: attribute.required,
    array: attribute.array,
  };
  if (attribute.size !== undefined) payload.size = attribute.size;
  if (attribute.elements !== undefined) payload.elements = attribute.elements;
  if (attribute.min !== undefined) payload.min = attribute.min;
  if (attribute.max !== undefined) payload.max = attribute.max;
  if (attribute.default !== undefined) payload.default = attribute.default;
  return payload;
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
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!response.ok) {
    const message = data && data.message ? data.message : text;
    const error = new Error(`${response.status} ${message}`);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

async function exists(getter) {
  try {
    return await getter();
  } catch (error) {
    if (error.status === 404) return null;
    throw error;
  }
}

async function main() {
  const env = readEnv();
  for (const key of ['APPWRITE_ENDPOINT', 'APPWRITE_PROJECT_ID', 'APPWRITE_API_KEY', 'APPWRITE_DB_ID']) {
    if (!env[key]) throw new Error(`Missing ${key} in .env`);
  }
  if (process.argv.includes('--dry-run')) {
    const dryRun = selectedCollectionSpecs().map((spec) => ({
      collection: spec.name,
      collectionId: env[`APPWRITE_COLLECTION_ID${spec.index}`] || spec.defaultId || null,
      schemaFile: spec.file,
      attributes: parseAttributes(spec.file).map((attribute) => ({
        key: attribute.key,
        type: attribute.type,
        required: attribute.required,
      })),
    }));
    console.log(JSON.stringify(dryRun, null, 2));
    return;
  }

  const report = {
    database: 'existing',
    collectionsCreated: [],
    collectionsExisting: [],
    attributesCreated: [],
    attributesExisting: [],
    skipped: [],
  };

  const database = await exists(() =>
    request(env, 'GET', `/databases/${encodeURIComponent(env.APPWRITE_DB_ID)}`)
  );
  if (!database) {
    await request(env, 'POST', '/databases', {
      databaseId: env.APPWRITE_DB_ID,
      name: 'Farm Estates Limited DataBase',
    });
    report.database = 'created';
  }

  for (const spec of selectedCollectionSpecs()) {
    const collectionId = env[`APPWRITE_COLLECTION_ID${spec.index}`] || spec.defaultId;
    if (!collectionId) {
      report.skipped.push(`${spec.name}: missing APPWRITE_COLLECTION_ID${spec.index}`);
      continue;
    }

    const collectionRoute = `/databases/${encodeURIComponent(env.APPWRITE_DB_ID)}/collections/${encodeURIComponent(collectionId)}`;
    const collection = await exists(() => request(env, 'GET', collectionRoute));
    if (!collection) {
      await request(env, 'POST', `/databases/${encodeURIComponent(env.APPWRITE_DB_ID)}/collections`, {
        collectionId,
        name: spec.name,
        permissions: [],
        documentSecurity: false,
        enabled: true,
      });
      report.collectionsCreated.push(spec.name);
    } else {
      report.collectionsExisting.push(spec.name);
    }

    const attributes = parseAttributes(spec.file);
    const current = await request(env, 'GET', `${collectionRoute}/attributes?limit=200`);
    const currentKeys = new Set((current.attributes || []).map((attribute) => attribute.key));

    for (const attribute of attributes) {
      if (!attribute.key) {
        report.skipped.push(`${spec.name}: attribute with missing key in ${spec.file}`);
        continue;
      }
      if (currentKeys.has(attribute.key)) {
        const existingAttribute = (current.attributes || []).find((item) => item.key === attribute.key);
        if (
          existingAttribute &&
          Array.isArray(attribute.elements) &&
          Array.isArray(existingAttribute.elements)
        ) {
          const existingElements = existingAttribute.elements || [];
          const missingElements = attribute.elements.filter((item) => !existingElements.includes(item));
          if (missingElements.length > 0) {
            await request(env, 'PATCH', `${collectionRoute}/attributes/enum/${encodeURIComponent(attribute.key)}`, {
              elements: attribute.elements,
              required: attribute.required,
              default: attribute.default === undefined ? null : attribute.default,
            });
            report.attributesCreated.push(`${spec.name}.${attribute.key}: enum updated`);
            continue;
          }
        }
        report.attributesExisting.push(`${spec.name}.${attribute.key}`);
        continue;
      }
      const endpoint = toAttributeEndpoint(attribute.type);
      if (!endpoint) {
        report.skipped.push(`${spec.name}.${attribute.key}: unsupported type ${attribute.type}`);
        continue;
      }
      try {
        await request(env, 'POST', `${collectionRoute}/attributes/${endpoint}`, toAttributePayload(attribute));
        report.attributesCreated.push(`${spec.name}.${attribute.key}`);
      } catch (error) {
        if (error.status === 409 && error.data && error.data.type === 'attribute_already_exists') {
          report.attributesExisting.push(`${spec.name}.${attribute.key}`);
        } else {
          throw error;
        }
      }
      currentKeys.add(attribute.key);
    }
  }

  console.log(JSON.stringify(report, null, 2));
}

main().catch((error) => {
  console.error(error.message);
  if (error.data) console.error(JSON.stringify(error.data, null, 2));
  process.exit(1);
});
