import React, { useState } from 'react';
import {
  Panel,
  PanelHeader,
  Group,
  FormItem,
  Input,
  Button,
  Text,
  Spacing,
  Div,
} from '@vkontakte/vkui';
import { Icon24LinkCircleOutline } from '@vkontakte/icons';
import { linkVK } from '../api/budget';

interface Props {
  vkUserId: string;
  onLinked: (tgUserId: string) => void;
}

export const LinkPage: React.FC<Props> = ({ vkUserId, onLinked }) => {
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLink = async () => {
    if (code.length !== 6) {
      setError('Код должен содержать 6 цифр');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await linkVK(vkUserId, code);
      if (result.linked && result.user_id) {
        onLinked(result.user_id);
      }
    } catch (e: any) {
      setError(e.message || 'Ошибка привязки');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Panel>
      <PanelHeader>Привязка аккаунта</PanelHeader>
      <Group>
        <Div style={{ textAlign: 'center', padding: '24px 16px' }}>
          <Icon24LinkCircleOutline width={48} height={48} style={{ color: 'var(--vkui-color-accent)' }} />
          <Spacing size="m" />
          <Text weight="2" style={{ fontSize: 20 }}>
            Привяжите Telegram
          </Text>
          <Spacing size="s" />
          <Text style={{ color: 'var(--vkui-color-text-secondary)' }}>
            Чтобы использовать семейный бюджет, привяжите ваш Telegram аккаунт
          </Text>
        </Div>

        <Group>
          <Div>
            <Text style={{ marginBottom: 12, color: 'var(--vkui-color-text-secondary)' }}>
              1. Откройте Telegram бота и введите /linkvk
            </Text>
            <Text style={{ marginBottom: 16, color: 'var(--vkui-color-text-secondary)' }}>
              2. Введите полученный 6-значный код ниже
            </Text>

            <FormItem top="Код привязки">
              <Input
                value={code}
                onChange={(e) => {
                  setCode(e.target.value.replace(/\D/g, '').slice(0, 6));
                  setError('');
                }}
                placeholder="000000"
                maxlength={6}
                status={error ? 'error' : 'default'}
                bottom={error}
              />
            </FormItem>

            <Button
              size="l"
              stretched
              onClick={handleLink}
              disabled={loading || code.length !== 6}
              loading={loading}
            >
              Привязать
            </Button>
          </Div>
        </Group>
      </Group>
    </Panel>
  );
};
