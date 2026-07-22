const fs = require('fs');
const path = require('path');

const root = __dirname;

const demoUsers = [
  {
    id: 'demo_superadmin',
    name: 'Super Admin',
    email: 'superadmin@farmestates.com',
    password: 'FarmDemo#2026Super',
    role: 'superadmin',
    address: 'Farm Estates HQ',
    phone: '+233000000001',
    department: 'Executive',
    status: 'Active',
  },
  {
    id: 'demo_admin',
    name: 'Admin',
    email: 'admin@farmestates.com',
    password: 'FarmDemo#2026Admin',
    role: 'admin',
    address: 'Farm Estates HQ',
    phone: '+233000000002',
    department: 'Administration',
    status: 'Active',
  },
  {
    id: 'demo_farm_manager',
    name: 'Farm Manager',
    email: 'manager@farmestates.com',
    password: 'FarmDemo#2026Manager',
    role: 'farm_manager',
    address: 'Farm Estates Operations',
    phone: '+233000000003',
    department: 'Farm Operations',
    status: 'Active',
  },
  {
    id: 'demo_farm_owner',
    name: 'Farm Owner',
    email: 'owner@farmestates.com',
    password: 'FarmDemo#2026Owner',
    role: 'farm_owner',
    address: 'Farm Estates Owner Desk',
    phone: '+233000000004',
    department: 'Ownership',
    status: 'Active',
  },
  {
    id: 'demo_caretaker',
    name: 'Caretaker',
    email: 'caretaker@farmestates.com',
    password: 'FarmDemo#2026Caretaker',
    role: 'caretaker',
    address: 'Farm Estate A',
    phone: '+233000000005',
    department: 'Daily Operations',
    status: 'Active',
  },
  {
    id: 'demo_technician',
    name: 'Technician',
    email: 'technician@farmestates.com',
    password: 'FarmDemo#2026Tech',
    role: 'technician',
    address: 'Farm Estates Technical Unit',
    phone: '+233000000006',
    department: 'Maintenance',
    status: 'Active',
  },
  {
    id: 'demo_fulfillment',
    name: 'Fulfillment Manager',
    email: 'fulfillment@farmestates.com',
    password: 'FarmDemo#2026Fulfill',
    role: 'fulfillment_manager',
    address: 'Fulfillment Center',
    phone: '+233000000007',
    department: 'Fulfillment',
    status: 'Active',
  },
  {
    id: 'demo_packaging',
    name: 'Packaging Supervisor',
    email: 'packaging@farmestates.com',
    password: 'FarmDemo#2026Pack',
    role: 'packaging_supervisor',
    address: 'Packaging Center',
    phone: '+233000000008',
    department: 'Packaging',
    status: 'Active',
  },
  {
    id: 'demo_quality',
    name: 'Quality Assurance',
    email: 'quality@farmestates.com',
    password: 'FarmDemo#2026Quality',
    role: 'quality_officer',
    address: 'Quality Control Desk',
    phone: '+233000000009',
    department: 'Quality Assurance',
    status: 'Active',
  },
  {
    id: 'demo_sales_manager',
    name: 'Sales Manager',
    email: 'sales@farmestates.com',
    password: 'FarmDemo#2026Sales',
    role: 'sales_manager',
    address: 'Sales Office',
    phone: '+233000000010',
    department: 'Sales',
    status: 'Active',
  },
  {
    id: 'demo_sales_person',
    name: 'Sales Personnel',
    email: 'salesperson@farmestates.com',
    password: 'FarmDemo#2026Seller',
    role: 'sales_person',
    address: 'Sales Field Team',
    phone: '+233000000011',
    department: 'Sales',
    status: 'Active',
  },
  {
    id: 'demo_accountant',
    name: 'Accountant',
    email: 'accountant@farmestates.com',
    password: 'FarmDemo#2026Account',
    role: 'accountant',
    address: 'Finance Office',
    phone: '+233000000012',
    department: 'Finance',
    status: 'Active',
  },
];

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
    const error = new Error(data && data.message ? data.message : text);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}

async function upsertAccount(env, user) {
  try {
    await request(env, 'POST', '/users', {
      userId: user.id,
      email: user.email,
      password: user.password,
      name: user.name,
    });
    return 'created';
  } catch (error) {
    if (error.status !== 409) throw error;
    await request(env, 'PATCH', `/users/${encodeURIComponent(user.id)}/password`, {
      password: user.password,
    });
    return 'updated';
  }
}

async function upsertProfile(env, user) {
  const route =
    `/databases/${encodeURIComponent(env.APPWRITE_DB_ID)}` +
    `/collections/${encodeURIComponent(env.APPWRITE_COLLECTION_ID1)}` +
    `/documents/${encodeURIComponent(user.id)}`;
  const data = {
    name: user.name,
    email: user.email,
    password: user.password,
    role: user.role,
    address: user.address,
    phone: user.phone,
    department: user.department,
    status: user.status,
  };

  try {
    await request(env, 'GET', route);
    await request(env, 'PATCH', route, { data });
    return 'updated';
  } catch (error) {
    if (error.status !== 404) throw error;
    await request(
      env,
      'POST',
      `/databases/${encodeURIComponent(env.APPWRITE_DB_ID)}` +
        `/collections/${encodeURIComponent(env.APPWRITE_COLLECTION_ID1)}/documents`,
      {
        documentId: user.id,
        data,
        permissions: [],
      }
    );
    return 'created';
  }
}

async function ensureUserRoleEnum(env) {
  const route =
    `/databases/${encodeURIComponent(env.APPWRITE_DB_ID)}` +
    `/collections/${encodeURIComponent(env.APPWRITE_COLLECTION_ID1)}` +
    '/attributes/enum/role';
  await request(env, 'PATCH', route, {
    elements: [
      'superadmin',
      'admin',
      'farm_manager',
      'farm_owner',
      'caretaker',
      'technician',
      'fulfillment_manager',
      'packaging_supervisor',
      'quality_officer',
      'sales_manager',
      'sales_person',
      'accountant',
    ],
    required: true,
    default: null,
  });
}

async function ensureUserStatusEnum(env) {
  const collectionRoute =
    `/databases/${encodeURIComponent(env.APPWRITE_DB_ID)}` +
    `/collections/${encodeURIComponent(env.APPWRITE_COLLECTION_ID1)}`;
  const route = `${collectionRoute}/attributes/enum/status`;
  const payload = {
    elements: ['Active', 'Pending', 'Suspended'],
    required: false,
    default: 'Active',
  };

  try {
    await request(env, 'GET', route);
    await request(env, 'PATCH', route, payload);
  } catch (error) {
    if (error.status !== 404) throw error;
    try {
      await request(env, 'POST', `${collectionRoute}/attributes/enum`, {
        key: 'status',
        ...payload,
        array: false,
      });
    } catch (createError) {
      if (
        createError.status !== 409 ||
        !createError.data ||
        createError.data.type !== 'attribute_already_exists'
      ) {
        throw createError;
      }
    }
  }
}

async function main() {
  const env = readEnv();
  for (const key of [
    'APPWRITE_ENDPOINT',
    'APPWRITE_PROJECT_ID',
    'APPWRITE_API_KEY',
    'APPWRITE_DB_ID',
    'APPWRITE_COLLECTION_ID1',
  ]) {
    if (!env[key]) throw new Error(`Missing ${key} in .env`);
  }

  process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';

  await ensureUserRoleEnum(env);
  await ensureUserStatusEnum(env);

  const report = [];
  for (const user of demoUsers) {
    const account = await upsertAccount(env, user);
    const profile = await upsertProfile(env, user);
    report.push({
      email: user.email,
      role: user.role,
      account,
      profile,
    });
  }
  console.log(JSON.stringify(report, null, 2));
}

main().catch((error) => {
  console.error(error.message);
  if (error.data) console.error(JSON.stringify(error.data, null, 2));
  process.exit(1);
});
