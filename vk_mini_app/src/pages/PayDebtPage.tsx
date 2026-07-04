import React, { useState } from 'react';
import {
  Panel,
  PanelHeader,
  PanelHeaderBack,
  Group,
  FormItem,
  Input,
  Button,
  Text,
  Div,
  Spacing,
} from '@vkontakte/vkui';
import { payDebt } from '../api/budget';

interface Props {
  userId: string;
  debtorId: string;
  creditorId: string;
  maxAmount: number;
  onBack: () => void;
}

export const PayDebtPage: React.FC<Props> = ({
  userId,
  debtorId,
  creditorId,
  maxAmount,
  onBack,
}) => {
  const [amount, setAmount] = useState(String(maxAmount));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handlePay = async () => {
    const amountNum = parseInt(amount, 10);
    if (!amountNum || amountNum <= 0) {
      setError('Введите сумму');
      return;
    }
    if (amountNum > maxAmount) {
      setError(`Максимум: ${maxAmount} ₽`);
      return;
    }

    setLoading(true);
    setError('');
    try {
      await payDebt(userId, debtorId, creditorId, amountNum);
      setSuccess(true);
      setTimeout(onBack, 1500);
    } catch (e: any) {
      setError(e.message || 'Ошибка оплаты');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <Panel>
        <PanelHeader before={<PanelHeaderBack onClick={onBack} />}>
          Оплата долга
        </PanelHeader>
        <Div style={{ textAlign: 'center', padding: 48 }}>
          <Text weight="2" style={{ fontSize: 24, color: 'var(--vkui-color-positive)' }}>
            Оплачено!
          </Text>
        </Div>
      </Panel>
    );
  }

  return (
    <Panel>
      <PanelHeader before={<PanelHeaderBack onClick={onBack} />}>
        Оплата долга
      </PanelHeader>

      <Group>
        <Div>
          <Text weight="2" style={{ textAlign: 'center', fontSize: 16, marginBottom: 16 }}>
            Сумма к оплате: {maxAmount} ₽
          </Text>
        </Div>

        <FormItem top="Сумма оплаты (₽)">
          <Input
            value={amount}
            onChange={(e) => {
              setAmount(e.target.value.replace(/\D/g, ''));
              setError('');
            }}
            placeholder="0"
            type="number"
          />
        </FormItem>

        {error && (
          <>
            <Spacing />
            <Text style={{ color: 'var(--vkui-color-negative)', padding: '0 16px' }}>{error}</Text>
          </>
        )}

        <Div>
          <Button
            size="l"
            stretched
            onClick={handlePay}
            disabled={loading}
            loading={loading}
          >
            Оплатить
          </Button>
        </Div>
      </Group>
    </Panel>
  );
};
