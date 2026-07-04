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
import { createFamily } from '../api/budget';

interface Props {
  userId: string;
  onDone: (familyId: number, familyName: string) => void;
  onBack: () => void;
}

export const CreateFamilyPage: React.FC<Props> = ({ userId, onDone, onBack }) => {
  const [name, setName] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleCreate = async () => {
    if (!name.trim()) {
      setError('Введите название семьи');
      return;
    }
    if (!displayName.trim()) {
      setError('Введите ваше имя');
      return;
    }

    setLoading(true);
    setError('');
    try {
      const result = await createFamily(userId, name.trim(), displayName.trim());
      onDone(result.family_id, name.trim());
    } catch (e: any) {
      setError(e.message || 'Ошибка создания');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel>
      <PanelHeader before={<PanelHeaderBack onClick={onBack} />}>
        Создать семью
      </PanelHeader>

      <Group>
        <FormItem top="Название семьи">
          <Input
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              setError('');
            }}
            placeholder="Например, Семья Петровых"
          />
        </FormItem>

        <FormItem top="Ваше имя">
          <Input
            value={displayName}
            onChange={(e) => {
              setDisplayName(e.target.value);
              setError('');
            }}
            placeholder="Например, Папа"
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
            onClick={handleCreate}
            disabled={loading}
            loading={loading}
          >
            Создать
          </Button>
        </Div>
      </Group>
    </Panel>
  );
};
