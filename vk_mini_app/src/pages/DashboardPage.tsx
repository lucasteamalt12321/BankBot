import React, { useEffect, useState } from 'react';
import {
  Panel,
  PanelHeader,
  Group,
  Div,
  Text,
  Button,
  Card,
  CardGrid,
  Badge,
  Spacing,
  Placeholder,
  Spinner,
} from '@vkontakte/vkui';
import { Icon24AddOutline, Icon24StoryOutline, Icon24WalletOutline } from '@vkontakte/icons';
import { getFamilyStatus, getDebts, getBalance, type Debt, type Balance } from '../api/budget';

interface Props {
  userId: string;
  onAddExpense: () => void;
  onPayDebt: (debtorId: string, creditorId: string, amount: number) => void;
  onHistory: () => void;
  onCreateFamily: () => void;
  onJoinFamily: () => void;
}

export const DashboardPage: React.FC<Props> = ({
  userId,
  onAddExpense,
  onPayDebt,
  onHistory,
  onCreateFamily,
  onJoinFamily,
}) => {
  const [loading, setLoading] = useState(true);
  const [familyName, setFamilyName] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [debts, setDebts] = useState<Debt[]>([]);
  const [balances, setBalances] = useState<Balance[]>([]);
  const [memberNames, setMemberNames] = useState<Record<string, string>>({});

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const status = await getFamilyStatus(userId);
      if (!status.family_id) {
        setLoading(false);
        return;
      }

      setFamilyName(status.family_name || '');
      setInviteCode(status.invite_code || '');

      const names: Record<string, string> = {};
      status.members?.forEach((m) => {
        names[m.user_id] = m.display_name;
      });
      setMemberNames(names);

      const [debtsRes, balanceRes] = await Promise.all([
        getDebts(userId),
        getBalance(userId),
      ]);
      setDebts(debtsRes.debts || []);
      setBalances(balanceRes.balances || []);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  const getName = (id: string) => memberNames[id] || id;

  if (loading) {
    return (
      <Panel>
        <PanelHeader>Бюджет</PanelHeader>
        <Div style={{ textAlign: 'center', padding: 48 }}>
          <Spinner size="m" />
        </Div>
      </Panel>
    );
  }

  if (!familyName) {
    return (
      <Panel>
        <PanelHeader>Бюджет</PanelHeader>
        <Placeholder
          icon={<Icon24WalletOutline width={48} height={48} />}
          title="Семья не найдена"
        >
          <Text style={{ marginBottom: 16 }}>Создайте семью или присоединитесь по коду</Text>
          <Button size="l" stretched onClick={onCreateFamily} style={{ marginBottom: 8 }}>
            Создать семью
          </Button>
          <Button size="l" stretched mode="secondary" onClick={onJoinFamily}>
            Присоединиться по коду
          </Button>
        </Placeholder>
      </Panel>
    );
  }

  return (
    <Panel>
      <PanelHeader>{familyName}</PanelHeader>

      {/* Balances */}
      {balances.length > 0 && (
        <Group header={<Text weight="2">Балансы</Text>}>
          <Div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {balances.map((b) => (
              <Card key={b.user_id} style={{ flex: '1 1 80px', padding: 12, textAlign: 'center' }}>
                <Text weight="2" style={{ fontSize: 12, color: 'var(--vkui-color-text-secondary)' }}>
                  {getName(b.user_id)}
                </Text>
                <Text
                  weight="3"
                  style={{
                    fontSize: 18,
                    color: b.net >= 0 ? 'var(--vkui-color-positive)' : 'var(--vkui-color-negative)',
                  }}
                >
                  {b.net >= 0 ? '+' : ''}{b.net} ₽
                </Text>
              </Card>
            ))}
          </Div>
        </Group>
      )}

      {/* Debts */}
      <Group header={<Text weight="2">Долги</Text>}>
        {debts.length === 0 ? (
          <Div>
            <Text style={{ color: 'var(--vkui-color-text-secondary)', textAlign: 'center' }}>
              Долгов нет 🎉
            </Text>
          </Div>
        ) : (
          debts.map((d, i) => (
            <Div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0' }}>
              <div>
                <Text weight="2">{getName(d.debtor_id)} → {getName(d.creditor_id)}</Text>
                <Text style={{ color: 'var(--vkui-color-text-secondary)' }}>{d.amount_left} ₽</Text>
              </div>
              <Button
                size="s"
                appearance="accent"
                onClick={() => onPayDebt(d.debtor_id, d.creditor_id, d.amount_left)}
              >
                Оплатить
              </Button>
            </Div>
          ))
        )}
      </Group>

      {/* Invite code */}
      {inviteCode && (
        <Group header={<Text weight="2">Код приглашения</Text>}>
          <Div style={{ textAlign: 'center' }}>
            <Text weight="3" style={{ fontSize: 24, letterSpacing: 4 }}>
              {inviteCode}
            </Text>
            <Text style={{ color: 'var(--vkui-color-text-secondary)', marginTop: 4 }}>
              Передайте этот код для вступления в семью
            </Text>
          </Div>
        </Group>
      )}

      {/* FAB */}
      <div
        onClick={onAddExpense}
        style={{
          position: 'fixed',
          bottom: 24,
          right: 24,
          width: 56,
          height: 56,
          borderRadius: 28,
          background: 'var(--vkui-color-accent)',
          color: 'white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
          cursor: 'pointer',
          zIndex: 100,
        }}
      >
        <Icon24AddOutline />
      </div>
    </Panel>
  );
};
