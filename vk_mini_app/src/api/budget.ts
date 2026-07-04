const API_URL = import.meta.env.VITE_API_URL || 'https://bank-bot-ruby.vercel.app';

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_URL}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: 'Ошибка сервера' }));
    throw new Error(body.error || `HTTP ${res.status}`);
  }
  return res.json();
}

// ===== VK Linking =====

export async function getVKStatus(vkUserId: string) {
  return apiFetch<{ linked: boolean; user_id?: string }>(
    `/api/budget/vk/status?vk_user_id=${vkUserId}`
  );
}

export async function linkVK(vkUserId: string, code: string) {
  return apiFetch<{ linked: boolean; user_id: string }>(
    '/api/budget/vk/link',
    {
      method: 'POST',
      body: JSON.stringify({ vk_user_id: vkUserId, code }),
    }
  );
}

// ===== Family =====

export async function getFamilyStatus(userId: string) {
  return apiFetch<{
    family_id?: number;
    family_name?: string;
    invite_code?: string;
    is_admin?: boolean;
    members?: Array<{ user_id: string; display_name: string; joined_at: string }>;
    error?: string;
  }>(`/api/budget/family/status?user_id=${userId}`);
}

export async function createFamily(userId: string, name: string, displayName: string) {
  return apiFetch<{ family_id: number; invite_code: string }>(
    '/api/budget/family/create',
    {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, name, display_name: displayName }),
    }
  );
}

export async function joinFamily(userId: string, code: string, displayName: string) {
  return apiFetch<{ family_id: number }>(
    '/api/budget/family/join',
    {
      method: 'POST',
      body: JSON.stringify({ user_id: userId, code, display_name: displayName }),
    }
  );
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

export async function getTransactions(userId: string, limit = 50) {
  return apiFetch<{ transactions: Transaction[] }>(
    `/api/budget/transactions?user_id=${userId}&limit=${limit}`
  );
}

export async function createTransaction(
  userId: string,
  payerId: string,
  amount: number,
  category: string,
  forWhomIds: string[],
  description?: string
) {
  return apiFetch<{ transaction_id: number }>(
    '/api/budget/transactions',
    {
      method: 'POST',
      body: JSON.stringify({
        user_id: userId,
        payer_id: payerId,
        amount,
        category,
        for_whom_ids: forWhomIds,
        description,
      }),
    }
  );
}

export async function deleteTransaction(userId: string, transactionId: number) {
  return apiFetch<{ deleted: boolean }>(
    `/api/budget/transactions/${transactionId}?user_id=${userId}`,
    { method: 'DELETE' }
  );
}

// ===== Debts =====

export interface Debt {
  debtor_id: string;
  debtor_name?: string;
  creditor_id: string;
  creditor_name?: string;
  amount_left: number;
}

export async function getDebts(userId: string) {
  return apiFetch<{ debts: Debt[] }>(
    `/api/budget/debts?user_id=${userId}`
  );
}

export async function payDebt(userId: string, debtorId: string, creditorId: string, amount: number) {
  return apiFetch<{ paid: boolean; message: string }>(
    '/api/budget/debts/pay',
    {
      method: 'POST',
      body: JSON.stringify({
        user_id: userId,
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
  return apiFetch<{ balances: Balance[] }>(
    `/api/budget/balance?user_id=${userId}`
  );
}
