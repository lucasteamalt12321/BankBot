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
import { joinFamily } from '../api/budget';

interface Props {
  userId: string;
  onDone: (familyId: number, familyName: string) => void;
  onBack: () => void;
}

export const JoinFamilyPage: React.FC<Props> = ({ userId, onDone, onBack }) => {
  const [code, setCode] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleJoin = async () => {
    if (code.length !== 6) {
      setError('Код должен содержать 6 цифр');
      return;
    }
    if (!displayName.trim()) {
      setError('Введите ваше имя');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const result = await joinFamily(userId, code, displayName.trim());
      onDone(result.family_id, '');
    } catch (e: any) {
      setError(e.message || 'Ошибка вступления');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel>
      <PanelHeader before={<PanelHeaderBack onClick={onBack} />}>
        Присоединиться
      </PanelHeader>

      <Group>
        <FormItem top="Код приглашения">
          <Input
            value={code}
            onChange={(e) => {
              setCode(e.target.value.replace(/\D/g, '').slice(0, 6));
              setError('');
            }}
            placeholder="000000"
            maxLength={6}
          />
        </FormItem>

        <FormItem top="Ваше имя">
          <Input
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
              setError('');
            }}
            placeholder="Например, Брат"
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
            onClick={handleJoin}
            disabled={loading}
            loading={loading}
          >
            Присоединиться
          </Button>
        </Div>
      </Group>
    </Panel>
  );
};
