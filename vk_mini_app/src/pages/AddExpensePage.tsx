import React, { useEffect, useState } from 'react';
import {
  Panel,
  PanelHeader,
  PanelHeaderBack,
  Group,
  FormItem,
  Input,
  Select,
  Button,
  Checkbox,
  Text,
  Div,
  Spacing,
  Alert,
} from '@vkontakte/vkui';
import { getFamilyStatus, createTransaction } from '../api/budget';

const CATEGORIES = [
  { label: 'Еда', value: 'Еда' },
  { label: 'Транспорт', value: 'Транспорт' },
  { label: 'Хозяйство', value: 'Хозяйство' },
  { label: 'Развлечения', value: 'Развлечения' },
  { label: 'Другое', value: 'Другое' },
];

interface Props {
  userId: string;
  onBack: () => void;
}

export const AddExpensePage: React.FC<Props> = ({ userId, onBack }) => {
  const [members, setMembers] = useState<Array<{ user_id: string; display_name: string }>>([]);
  const [payerId, setPayerId] = useState('');
  const [forWhomIds, setForWhomIds] = useState<string[]>([]);
  const [amount, setAmount] = useState('');
  const [category, setCategory] = useState('Еда');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getFamilyStatus(userId).then((status) => {
      if (status.members) {
        setMembers(status.members);
        setPayerId(userId);
        setForWhomIds(status.members.map((m) => m.user_id));
      }
    });
  }, [userId]);

  const toggleForWhom = (uid: string) => {
    setForWhomIds((prev) =>
      prev.includes(uid) ? prev.filter((id) => id !== uid) : [...prev, uid]
    );
  };

  const handleSubmit = async () => {
    const amountNum = parseInt(amount, 10);
    if (!amountNum || amountNum <= 0) {
      setError('Введите сумму');
      return;
    }
    if (!payerId) {
      setError('Выберите, кто платил');
      return;
    }
    if (forWhomIds.length === 0) {
      setError('Выберите хотя бы одного человека');
      return;
    }

    setLoading(true);
    setError('');
    try {
      await createTransaction(userId, payerId, amountNum, category, forWhomIds, description || undefined);
      onBack();
    } catch (e: any) {
      setError(e.message || 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel>
      <PanelHeader before={<PanelHeaderBack onClick={onBack} />}>
        Новая трата
      </PanelHeader>

      <Group>
        <FormItem top="Кто платил">
          <Select
            value={payerId}
            onChange={(e) => setPayerId(e.target.value)}
            options={members.map((m) => ({
              label: m.display_name,
              value: m.user_id,
            }))}
          />
        </FormItem>

        <FormItem top="Для кого">
          <Div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {members.map((m) => (
              <Checkbox
                key={m.user_id}
                checked={forWhomIds.includes(m.user_id)}
                onChange={() => toggleForWhom(m.user_id)}
              >
                {m.display_name}
              </Checkbox>
            ))}
          </Div>
        </FormItem>

        <FormItem top="Сумма (₽)">
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

        <FormItem top="Категория">
          <Select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            options={CATEGORIES}
          />
        </FormItem>

        <FormItem top="Описание (необязательно)">
          <Input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Например, обед в столовой"
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
            onClick={handleSubmit}
            disabled={loading}
            loading={loading}
          >
            Сохранить
          </Button>
        </Div>
      </Group>
    </Panel>
  );
};
