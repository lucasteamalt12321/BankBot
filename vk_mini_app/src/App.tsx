import React, { useEffect, useState } from 'react';
import { ConfigProvider, AdaptivityProvider, AppRoot } from '@vkontakte/vkui';
import bridge from '@vkontakte/vk-bridge';
import '@vkontakte/vkui/dist/vkui.css';

import { getVKStatus } from './api/budget';
import { LinkPage } from './pages/LinkPage';
import { CreateFamilyPage } from './pages/CreateFamilyPage';
import { JoinFamilyPage } from './pages/JoinFamilyPage';
import { DashboardPage } from './pages/DashboardPage';
import { AddExpensePage } from './pages/AddExpensePage';
import { PayDebtPage } from './pages/PayDebtPage';
import { HistoryPage } from './pages/HistoryPage';

type Screen =
  | 'loading'
  | 'link'
  | 'create_family'
  | 'join_family'
  | 'dashboard'
  | 'add_expense'
  | 'pay_debt'
  | 'history';

interface AppState {
  screen: Screen;
  vkUserId: string;
  tgUserId: string;
  familyId: number | null;
  familyName: string;
  selectedDebt?: {
    debtorId: string;
    creditorId: string;
    amount: number;
  };
}

const App: React.FC = () => {
  const [state, setState] = useState<AppState>({
    screen: 'loading',
    vkUserId: '',
    tgUserId: '',
    familyId: null,
    familyName: '',
  });

  useEffect(() => {
    bridge.send('VKWebAppInit').catch(() => {});

    bridge
      .send('VKWebAppGetAuthToken', {
        app_id: Number(import.meta.env.VITE_APP_ID) || 0,
        scope: '',
      })
      .then(async (data: any) => {
        const vkUserId = String(data.vk_user_id || '');
        if (!vkUserId) {
          setState((s) => ({ ...s, screen: 'link', vkUserId: '' }));
          return;
        }

        try {
          const status = await getVKStatus(vkUserId);
          if (status.linked && status.user_id) {
            setState((s) => ({
              ...s,
              screen: 'dashboard',
              vkUserId,
              tgUserId: status.user_id,
            }));
          } else {
            setState((s) => ({ ...s, screen: 'link', vkUserId }));
          }
        } catch {
          setState((s) => ({ ...s, screen: 'link', vkUserId }));
        }
      })
      .catch(() => {
        setState((s) => ({ ...s, screen: 'link', vkUserId: 'test_user' }));
      });
  }, []);

  const navigate = (screen: Screen, extra?: Partial<AppState>) => {
    setState((s) => ({ ...s, screen, ...extra }));
  };

  const onLinked = (tgUserId: string) => {
    setState((s) => ({
      ...s,
      screen: 'dashboard',
      tgUserId,
    }));
  };

  const onFamilyReady = (familyId: number, familyName: string) => {
    setState((s) => ({
      ...s,
      screen: 'dashboard',
      familyId,
      familyName,
    }));
  };

  const onAddExpense = () => navigate('add_expense');
  const onPayDebt = (debtorId: string, creditorId: string, amount: number) =>
    setState((s) => ({
      ...s,
      screen: 'pay_debt',
      selectedDebt: { debtorId, creditorId, amount },
    }));
  const onHistory = () => navigate('history');
  const onBack = () => navigate('dashboard');

  return (
    <ConfigProvider>
      <AdaptivityProvider>
        <AppRoot>
          {state.screen === 'loading' && <div style={{ padding: 32, textAlign: 'center' }}>Загрузка...</div>}
          {state.screen === 'link' && (
            <LinkPage vkUserId={state.vkUserId} onLinked={onLinked} />
          )}
          {state.screen === 'create_family' && (
            <CreateFamilyPage
              userId={state.tgUserId}
              onDone={onFamilyReady}
              onBack={onBack}
            />
          )}
          {state.screen === 'join_family' && (
            <JoinFamilyPage
              userId={state.tgUserId}
              onDone={onFamilyReady}
              onBack={onBack}
            />
          )}
          {state.screen === 'dashboard' && (
            <DashboardPage
              userId={state.tgUserId}
              onAddExpense={onAddExpense}
              onPayDebt={onPayDebt}
              onHistory={onHistory}
              onCreateFamily={() => navigate('create_family')}
              onJoinFamily={() => navigate('join_family')}
            />
          )}
          {state.screen === 'add_expense' && (
            <AddExpensePage userId={state.tgUserId} onBack={onBack} />
          )}
          {state.screen === 'pay_debt' && state.selectedDebt && (
            <PayDebtPage
              userId={state.tgUserId}
              debtorId={state.selectedDebt.debtorId}
              creditorId={state.selectedDebt.creditorId}
              maxAmount={state.selectedDebt.amount}
              onBack={onBack}
            />
          )}
          {state.screen === 'history' && (
            <HistoryPage userId={state.tgUserId} onBack={onBack} />
          )}
        </AppRoot>
      </AdaptivityProvider>
    </ConfigProvider>
  );
};

export default App;
