const API_URL = import.meta.env.VITE_API_URL || 'https://bank-bot-ruby.vercel.app';

// Параметры запуска VK Mini App (включая sign) — бэкенд проверяет подпись
// защищённым ключом приложения, прежде чем выдать наш HMAC.
const launchQuery = window.location.search.replace(/^\?/, '');

let authUserId = '';
let authSig = '';
let cachedFamilyId: number | null = null;
let memberNames: Record<string, string> = {};

function setCredentials(userId: string, sig: string) {
  authUserId = userId || '';
  authSig = sig || '';
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_URL}${path}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string> | undefined),
  };
  if (authUserId && authSig) {
    headers['X-User-Id'] = authUserId;
    headers['X-Budget-Sig'] = authSig;
  }
  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: 'Ошибка сервера' }));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ===== VK Linking =====

export async function getVKStatus(vkUserId: string) {
  const qs = launchQuery || `vk_user_id=${encodeURIComponent(vkUserId)}`;
  const r = await apiFetch<{ linked: boolean; user_id?: string; sig?: string }>(
    `/api/budget/vk/status?${qs}`
  );
  if (r.linked && r.user_id && r.sig) {
    setCredentials(r.user_id, r.sig);
  }
  return r;
}

export async function linkVK(vkUserId: string, code: string) {
  const qs = launchQuery ? `?${launchQuery}` : '';
  const r = await apiFetch<{ linked: boolean; user_id: string; sig?: string }>(
    `/api/budget/vk/link${qs}`,
    {
      method: 'POST',
      body: JSON.stringify({ vk_user_id: vkUserId, code }),
    }
  );
  if (r.linked && r.user_id && r.sig) {
    setCredentials(r.user_id, r.sig);
  }
  return r;
}

// ===== Family =====

export interface FamilyMember {
  user_id: string;
  display_name: string;
  joined_at?: string;
}

export interface FamilyStatus {
  family_id: number | null;
  family_name: string;
  invite_code: string;
  is_admin: boolean;
  members: FamilyMember[];
}

interface BackendFamily {
  id: number;
  name: string;
  admin_id: string;
  invite_code: string;
  members?: FamilyMember[];
}

export async function getFamilyStatus(userId: string): Promise<FamilyStatus> {
  const r = await apiFetch<{ user_id?: string; family: BackendFamily | null }>(
    `/api/budget/family/status?user_id=${encodeURIComponent(userId)}`
  );
  const f = r.family;
  cachedFamilyId = f ? f.id : null;
  memberNames = {};
  (f?.members || []).forEach((m) => {
    memberNames[m.user_id] = m.display_name;
  });
  return {
    family_id: f ? f.id : null,
    family_name: f?.name || '',
    invite_code: f?.invite_code || '',
    is_admin: !!f && f.admin_id === userId,
    members: f?.members || [],
  };
}

async function ensureFamilyId(userId: string): Promise<number> {
  if (cachedFamilyId) return cachedFamilyId;
  const status = await getFamilyStatus(userId);
  if (!status.family_id) throw new Error('Семья не найдена');
  return status.family_id;
}

export async function createFamily(userId: string, name: string, displayName: string) {
  const r = await apiFetch<{ family: BackendFamily }>(
    '/api/budget/family/create',
    {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, name, display_name: displayName }),
    }
  );
  cachedFamilyId = r.family.id;
  return { family_id: r.family.id, invite_code: r.family.invite_code };
}

export async function joinFamily(userId: string, code: string, displayName: string) {
  const r = await apiFetch<{ family: BackendFamily }>(
    '/api/budget/family/join',
    {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, code, display_name: displayName }),
    }
  );
  cachedFamilyId = r.family.id;
  return { family_id: r.family.id };
}

// ===== Transactions =====

export interface Transaction {
  id: number;
  payer_id: string;
  payer_name?: string;
  amount: number;
  category: string;
  description?: string;
  created_at: string;
  for_whom?: Array<{ user_id: string; display_name: string; share: number }>;
}

interface BackendTransaction {
  id: number;
  payer_id: string;
  amount: number;
  category: string;
  description?: string;
  created_at: string;
  details?: Array<{ for_whom_id: string; share: number }>;
}

export async function getTransactions(userId: string, limit = 50) {
  const familyId = await ensureFamilyId(userId);
  const r = await apiFetch<{ transactions: BackendTransaction[] }>(
    `/api/budget/transactions?family_id=${familyId}&limit=${limit}&user_id=${encodeURIComponent(userId)}`
  );
  const transactions: Transaction[] = (r.transactions || []).map((t) => ({
    id: t.id,
    payer_id: t.payer_id,
    payer_name: memberNames[t.payer_id],
    amount: t.amount,
    category: t.category,
    description: t.description,
    created_at: t.created_at,
    for_whom: (t.details || []).map((d) => ({
      user_id: d.for_whom_id,
      display_name: memberNames[d.for_whom_id] || d.for_whom_id,
      share: d.share,
    })),
  }));
  return { transactions };
}

export async function createTransaction(
  userId: string,
  payerId: string,
  amount: number,
  category: string,
  forWhomIds: string[],
  description?: string
) {
  const familyId = await ensureFamilyId(userId);
  const r = await apiFetch<{ id: number; status: string }>(
    '/api/budget/transactions',
    {
      method: 'POST',
      body: JSON.stringify({
        user_id: userId,
        family_id: familyId,
        payer_id: payerId,
        amount,
        category,
        for_whom_ids: forWhomIds,
        description,
      }),
    }
  );
  return { transaction_id: r.id };
}

export async function deleteTransaction(userId: string, transactionId: number) {
  const r = await apiFetch<{ status: string }>(
    `/api/budget/transactions/${transactionId}?user_id=${encodeURIComponent(userId)}`,
    { method: 'DELETE' }
  );
  return { deleted: r.status === 'deleted' };
}

// ===== Debts =====

export interface Debt {
  id?: number;
  debtor_id: string;
  debtor_name?: string;
  creditor_id: string;
  creditor_name?: string;
  amount_left: number;
}

export async function getDebts(userId: string) {
  const familyId = await ensureFamilyId(userId);
  return apiFetch<{ debts: Debt[] }>(
    `/api/budget/debts?family_id=${familyId}&user_id=${encodeURIComponent(userId)}`
  );
}

export async function payDebt(userId: string, debtorId: string, creditorId: string, amount: number) {
  const familyId = await ensureFamilyId(userId);
  return apiFetch<{ paid: boolean; message: string }>(
    '/api/budget/debts/pay',
    {
      method: 'POST',
      body: JSON.stringify({
        user_id: userId,
        family_id: familyId,
        debtor_id: debtorId,
        creditor_id: creditorId,
        amount,
      }),
    }
  );
}

// ===== Balance =====

export interface Balance {
  user_id: string;
  net: number;
}

export async function getBalance(userId: string) {
  const familyId = await ensureFamilyId(userId);
  return apiFetch<{ balances: Balance[] }>(
    `/api/budget/balance?family_id=${familyId}&user_id=${encodeURIComponent(userId)}`
  );
}