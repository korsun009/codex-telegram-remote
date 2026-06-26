# Codex Telegram Remote

Telegram bot and local gateway for remote control of [Codex Account Switcher](https://github.com/korsun009/codex-account-switcher).

Этот репозиторий содержит отдельный открытый код Telegram-бота. Бот не хранит аккаунты Codex сам. Он отправляет безопасные фиксированные команды в домашний gateway, а gateway пересылает их в Remote API программы Codex Account Switcher на Windows.

## Что умеет бот

По текущему коду бот умеет:

| Кнопка или команда | Что делает |
| --- | --- |
| `Статус ПК`, `/status` | Проверяет, отвечает ли Windows-ПК по сети и доступен ли Remote API. |
| `Включить ПК`, `/wake_pc` | Отправляет Wake-on-LAN пакет на Windows-ПК. |
| `Сон ПК`, `/sleep_pc` | Переводит Windows-ПК в сон через Remote API. |
| `Перезагрузить ПК`, `/reboot_pc` | Перезагружает Windows-ПК через Remote API. |
| `Выключить ПК`, `/shutdown_pc` | Выключает Windows-ПК через Remote API. |
| `Статус Codex`, `/codex_status` | Показывает статус Codex, активный профиль и доступность API. |
| `Запустить Codex`, `/codex_start` | Запускает Codex на Windows-ПК. |
| `Остановить Codex`, `/codex_stop` | Останавливает процессы Codex. |
| `Аккаунты`, `/accounts` | Показывает профили Codex из Codex Account Switcher. |
| `/switch_account <name>` | Переключает Codex на указанный профиль. В интерфейсе также есть кнопки переключения из списка аккаунтов. |
| `Лимиты`, `/limits` | Показывает 5-часовые и недельные лимиты Codex по профилям, которые видит Codex Account Switcher. |
| `VPN статус`, `/v2ray_status` | Показывает состояние V2RayTun/прокси по данным Windows Remote API. |
| `Запустить V2RayTun`, `/v2ray_start` | Запускает V2RayTun на Windows-ПК. |
| `VPN Proxy`, `/v2ray_proxy`, `/vpn_on` | Включает proxy mode для V2RayTun через Remote API. |
| `VPN перезапуск`, `/v2ray_restart` | Перезапускает V2RayTun через Remote API. |
| `Помощь`, `/help`, `/start` | Показывает краткую подсказку и клавиатуру. |

## Важное требование

Эта схема работает только если дома есть локальный сервер, который находится в той же локальной сети, что и Windows-ПК.

Причина простая: Telegram-бот не должен напрямую торчать в домашнюю сеть и не должен открывать Windows Remote API в интернет. Домашний сервер выполняет роль безопасного посредника:

1. он находится рядом с Windows-ПК в LAN;
2. он может отправить Wake-on-LAN пакет;
3. он может достучаться до Windows Remote API по локальному IP;
4. он сам поднимает исходящее SSH-соединение на VPS, поэтому не нужно открывать домашние входящие порты.

Если домашнего Linux-сервера в локальной сети нет, бот сможет работать только в упрощенной схеме, где VPS или другой сервер имеет прямой безопасный доступ к Windows Remote API. Публично открывать Windows Remote API не рекомендуется.

## Архитектура

Рекомендуемая схема:

```text
Telegram
  -> VPS with bot/bot/app.py
  -> SSH reverse tunnel on VPS 127.0.0.1:18790
  -> home Linux server with home-gateway/app.py
  -> Windows PC in the same LAN
  -> Codex Account Switcher Remote API
```

Компоненты:

- `bot/app.py` - Telegram polling bot. Работает на VPS или другом сервере с доступом к Telegram.
- `home-gateway/app.py` - локальный HTTP gateway. Работает на домашнем Linux-сервере в одной сети с Windows-ПК.
- `systemd/*.service` - примеры systemd-сервисов для постоянной работы.
- `home-gateway/reverse-tunnel.env.example` - пример настроек reverse SSH tunnel.

## Безопасность

- Не коммитьте `.env`.
- Не публикуйте Telegram bot token.
- Не публикуйте `HOME_GATEWAY_TOKEN`.
- Не публикуйте `WINDOWS_API_TOKEN`.
- Не публикуйте реальные Telegram user/chat IDs, если не хотите связывать их с собой.
- Разрешайте команды только своим Telegram user IDs или chat IDs.
- Не открывайте Windows Remote API напрямую в интернет.
- Не добавляйте произвольное выполнение shell-команд из Telegram. В этом коде команды фиксированы и заранее описаны.

## Требования

На Windows-ПК:

- Windows 10/11.
- Установленный [Codex Account Switcher](https://github.com/korsun009/codex-account-switcher).
- Включенный Remote API программы.
- Постоянный локальный IP или DHCP reservation на роутере.
- MAC-адрес сетевой карты для Wake-on-LAN.

На домашнем Linux-сервере:

- Linux-сервер в той же LAN, что и Windows-ПК.
- Python 3.11+.
- `openssh-client`.
- `iputils-ping`.
- `wakeonlan` или `etherwake`.
- Доступ к Windows-ПК по локальному IP.

На VPS:

- Linux VPS или другой сервер, который может ходить в Telegram API.
- Python 3.11+.
- SSH-доступ с домашнего сервера на VPS для reverse tunnel.

## 1. Настройте Codex Account Switcher Remote API на Windows

Установите Codex Account Switcher из основного репозитория:

https://github.com/korsun009/codex-account-switcher

Remote API запускается так:

```powershell
CodexAccountSwitcher.exe --remote-api
```

Для постоянного запуска используйте инструкцию из основного проекта:

https://github.com/korsun009/codex-account-switcher/blob/main/docs/REMOTE_API.md

Минимально должны быть заданы переменные окружения Windows:

```powershell
setx CODEX_REMOTE_API_URL "http://0.0.0.0:8765/"
setx CODEX_REMOTE_API_TOKEN "long-random-token"
```

`CODEX_REMOTE_API_TOKEN` должен совпадать с `WINDOWS_API_TOKEN` в `home-gateway/.env`.

## 2. Установите home gateway на домашний Linux-сервер

На домашнем сервере:

```bash
sudo apt update
sudo apt install -y git python3 openssh-client iputils-ping wakeonlan
sudo mkdir -p /opt/codex-telegram-remote
sudo git clone https://github.com/korsun009/codex-telegram-remote.git /opt/codex-telegram-remote
cd /opt/codex-telegram-remote/home-gateway
sudo cp .env.example .env
sudo nano .env
```

Заполните:

```env
HOME_GATEWAY_HOST=127.0.0.1
HOME_GATEWAY_PORT=8790
HOME_GATEWAY_TOKEN=long-random-home-gateway-token

WINDOWS_PC_IP=192.168.1.10
WINDOWS_PC_MAC=00:11:22:33:44:55
WINDOWS_WOL_BROADCAST=192.168.1.255
WINDOWS_WOL_INTERFACE=enp3s0

WINDOWS_API_BASE_URL=http://192.168.1.10:8765
WINDOWS_API_TOKEN=long-random-windows-api-token
WINDOWS_API_TIMEOUT_SECONDS=12
```

Пояснения:

- `HOME_GATEWAY_HOST=127.0.0.1` подходит для reverse tunnel. Gateway будет слушать только локально на домашнем сервере.
- `WINDOWS_PC_IP` - локальный IP Windows-ПК.
- `WINDOWS_PC_MAC` - MAC-адрес Windows-ПК для Wake-on-LAN.
- `WINDOWS_WOL_INTERFACE` - сетевой интерфейс домашнего Linux-сервера в LAN.
- `WINDOWS_API_BASE_URL` - адрес Remote API Codex Account Switcher на Windows.
- `WINDOWS_API_TOKEN` - тот же токен, что `CODEX_REMOTE_API_TOKEN` на Windows.

Проверка вручную:

```bash
cd /opt/codex-telegram-remote/home-gateway
python3 app.py
```

В другом терминале:

```bash
curl http://127.0.0.1:8790/health
curl -H "Authorization: Bearer long-random-home-gateway-token" http://127.0.0.1:8790/windows/status
```

## 3. Включите home gateway как systemd service

```bash
sudo cp /opt/codex-telegram-remote/systemd/codex-home-gateway.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now codex-home-gateway.service
sudo systemctl status codex-home-gateway.service
```

## 4. Настройте reverse SSH tunnel с домашнего сервера на VPS

Reverse tunnel нужен, если бот работает на VPS, а домашний сервер находится за NAT. Домашний сервер сам подключается к VPS и открывает на VPS локальный порт `127.0.0.1:18790`, который ведет к домашнему gateway.

На домашнем сервере создайте SSH-ключ:

```bash
sudo ssh-keygen -t ed25519 -f /root/.ssh/codex_remote_ed25519 -N ""
sudo cat /root/.ssh/codex_remote_ed25519.pub
```

Добавьте публичный ключ в `~/.ssh/authorized_keys` пользователя на VPS.

Создайте настройки tunnel:

```bash
cd /opt/codex-telegram-remote/home-gateway
sudo cp reverse-tunnel.env.example reverse-tunnel.env
sudo nano reverse-tunnel.env
```

Пример:

```env
REVERSE_TUNNEL_KEY=/root/.ssh/codex_remote_ed25519
REVERSE_TUNNEL_TARGET=user@your-vps-host
REVERSE_TUNNEL_REMOTE_BIND=127.0.0.1
REVERSE_TUNNEL_REMOTE_PORT=18790
HOME_GATEWAY_PORT=8790
```

Установите service:

```bash
sudo cp /opt/codex-telegram-remote/systemd/codex-home-reverse-tunnel.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now codex-home-reverse-tunnel.service
sudo systemctl status codex-home-reverse-tunnel.service
```

На VPS проверьте:

```bash
curl http://127.0.0.1:18790/health
```

## 5. Установите Telegram bot на VPS

На VPS:

```bash
sudo apt update
sudo apt install -y git python3
sudo mkdir -p /opt/codex-telegram-remote
sudo git clone https://github.com/korsun009/codex-telegram-remote.git /opt/codex-telegram-remote
cd /opt/codex-telegram-remote/bot
sudo cp .env.example .env
sudo nano .env
```

Заполните:

```env
TELEGRAM_BOT_TOKEN=token-from-botfather
TELEGRAM_ALLOWED_USER_IDS=111111111
TELEGRAM_ALLOWED_CHAT_IDS=

HOME_GATEWAY_BASE_URL=http://127.0.0.1:18790
HOME_GATEWAY_TOKEN=long-random-home-gateway-token
REQUEST_TIMEOUT_SECONDS=20
```

Пояснения:

- `TELEGRAM_BOT_TOKEN` выдает BotFather.
- `TELEGRAM_ALLOWED_USER_IDS` - Telegram user ID владельца или нескольких владельцев через запятую.
- `TELEGRAM_ALLOWED_CHAT_IDS` можно оставить пустым, если используется allowlist по user ID.
- `HOME_GATEWAY_BASE_URL` обычно `http://127.0.0.1:18790`, если используется reverse tunnel.
- `HOME_GATEWAY_TOKEN` должен совпадать с `HOME_GATEWAY_TOKEN` на домашнем сервере.

Проверка вручную:

```bash
cd /opt/codex-telegram-remote/bot
python3 app.py
```

Напишите боту `/start`. Если user ID разрешен, бот покажет клавиатуру.

## 6. Включите Telegram bot как systemd service

В service-файле по умолчанию используется пользователь `codex`. Создайте его или замените `User=` и `Group=` на вашего системного пользователя.

```bash
sudo useradd --system --home /opt/codex-telegram-remote --shell /usr/sbin/nologin codex || true
sudo chown -R codex:codex /opt/codex-telegram-remote/bot
sudo cp /opt/codex-telegram-remote/systemd/codex-telegram-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now codex-telegram-bot.service
sudo systemctl status codex-telegram-bot.service
```

Логи:

```bash
journalctl -u codex-telegram-bot.service -f
journalctl -u codex-home-gateway.service -f
journalctl -u codex-home-reverse-tunnel.service -f
```

## Как получить Telegram user ID

Самый простой способ:

1. Напишите любому Telegram боту, который показывает ваш user ID, например `@userinfobot`.
2. Вставьте ID в `TELEGRAM_ALLOWED_USER_IDS`.
3. Не публикуйте реальный ID в открытых issue/logs, если не хотите связывать его с собой.

## Как это должно работать после установки

1. Windows-ПК запускает Codex Account Switcher Remote API.
2. Домашний Linux-сервер видит Windows-ПК в локальной сети.
3. Home gateway на домашнем сервере принимает только запросы с `HOME_GATEWAY_TOKEN`.
4. Домашний сервер держит reverse SSH tunnel на VPS.
5. Telegram bot на VPS обращается к `http://127.0.0.1:18790`.
6. Команды из Telegram идут через tunnel на home gateway.
7. Home gateway пересылает разрешенные команды в Windows Remote API.
8. Ответ возвращается тем же путем обратно в Telegram.

## Проверка всей цепочки

На VPS:

```bash
curl http://127.0.0.1:18790/health
curl -H "Authorization: Bearer long-random-home-gateway-token" http://127.0.0.1:18790/windows/status
```

В Telegram:

```text
/start
/status
/accounts
/limits
/codex_status
```

Если `/status` работает, но `/accounts` или `/limits` нет, проблема обычно на Windows стороне: не запущен Remote API, не совпадает `WINDOWS_API_TOKEN`, Windows firewall блокирует порт или указан неправильный `WINDOWS_API_BASE_URL`.

## Разработка и тесты

Код использует только стандартную библиотеку Python.

Запуск тестов:

```bash
cd bot
python3 -m unittest test_app.py
```

Для быстрой проверки синтаксиса:

```bash
python3 -m py_compile bot/app.py bot/test_app.py home-gateway/app.py
```

## Что не входит в этот репозиторий

- Токены Telegram.
- Токены Codex Account Switcher Remote API.
- Личные Telegram user/chat IDs.
- Реальные домашние IP, MAC-адреса, домены или VPS-адреса.
- Код самой Windows-программы. Он находится в отдельном репозитории: https://github.com/korsun009/codex-account-switcher
