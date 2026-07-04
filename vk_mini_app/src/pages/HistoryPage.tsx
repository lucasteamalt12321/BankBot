import React, { useEffect, useState } from 'react';
import {
  Panel,
  PanelHeader,
  PanelHeaderBack,
  Group,
  Div,
  Text,
  Select,
  Spacing,
  Spinner,
} from '@vkontakte/vkui';
import { getTransactions, getFamilyStatus, type Transaction } from '../api/budget';

const CATEGORIES = ['Все', 'Еда', 'Транспорт', 'Хозяйство', 'Развлечения', 'Другое'];

interface Props {
  userId: string;
  onBack: () => void;
}

export const HistoryPage: React.FC<Props> = ({ userId, onBack }) => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [members, setMembers] = useState<Record<string, string>>({});
  const [filterCategory, setFilterCategory] = useState('Все');
  const [filterMember, setFilterMember] = useState('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [txnRes, status] = await Promise.all([
        getTransactions(userId, 100),
        getFamilyStatus(userId),
      ]);
      setTransactions(txnRes.transactions || []);
      const names: Record<string, string> = {};
      status.members?.forEach((m) => {
        names[m.user_id] = m.display_name;
      });
      setMembers(names);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  const getName = (id: string) => members[id] || id;

  const filtered = transactions.filter((t) => {
    if (filterCategory !== 'Все' && t.category !== filterCategory) return false;
    if (filterMember !== 'all' && t.payer_id !== filterMember) return false;
    return true;
  });

  if (loading) {
    return (
      <Panel>
        <PanelHeader before={<PanelHeaderBack onClick={onBack} />}>
          История
        </PanelHeader>
        <Div style={{ textAlign: 'center', padding: 48 }}>
          <Spinner size="m" />
        </Div>
      </Panel>
    );
  }

  return (
    <Panel>
      <PanelHeader before={<PanelHeaderBack onClick={onBack} />}>
        История
      </PanelHeader>

      {/* Filters */}
      <Group>
        <Div style={{ display: 'flex', gap: 8 }}>
          <div style={{ flex: 1 }}>
            <Select
              value={filterCategory}
              onChange={(e) => setFilterCategory(e.target.value)}
              options={CATEGORIES.map((c) => ({ label: c, value: c }))}
            />
          </div>
          <div style={{ flex: 1 }}>
            <Select
              value={filterMember}
              onChange={(e) => setFilterMember(e.target.value)}
              options={[
                { label: 'Все', value: 'all' },
                ...Object.entries(members).map(([id, name]) => ({
                  label: name,
                  value: id,
                })),
              ]}
            />
          </div>
        </Div>
      </Group>

      {/* Transactions */}
      <Group header={<Text weight="2">Транзакции ({filtered.length})</Text>}>
        {filtered.length === 0 ? (
          <Div>
            <Text style={{ color: 'var(--vkui-color-text-secondary)', textAlign: 'center' }}>
              Нет транзакций
            </Text>
          </Div>
        ) : (
          filtered.map((t) => (
            <Div key={t.id} style={{ padding: '8px 0', borderBottom: '1px solid var(--vkui-color_separator)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <Text weight="2">{getName(t.payer_id)}</Text>
                  <Text style={{ color: 'var(--vkui-color-text-secondary)', fontSize: 13 }}>
                    {t.category}{t.description ? ` · ${t.description}` : ''}
                  </Text>
                  {t.for_whom && t.for_whom.length > 0 && (
                    <Text style={{ color: 'var(--vkui-color-text-secondary)', fontSize: 12 }}>
                      для: {t.for_whom.map((f) => f.display_name).join(', ')}
                    </Text>
                  )}
                </div>
                <Text weight="3" style={{ color: 'var(--vkui-color-negative)' }}>
                  -{t.amount} ₽
                </Text>
              </div>
              <Text style={{ color: 'var(--vkui-color-text-secondary)', fontSize: 12, marginTop: 4 }}>
                {new Date(t.created_at).toLocaleDateString('ru-RU', {
                  day: 'numeric',
                  month: 'short',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </Text>
            </Div>
          ))
        )}
      </Group>
    </Panel>
  );
};
