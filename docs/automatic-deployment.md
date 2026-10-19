# Автоматическая доставка Nen из GitHub Actions

Решение от 19 октября 2026 года. Продолжает подтверждённую [установку готового пакета](simple-deployment.md). Сохраняются фиксированные рабочие каталоги и одна предыдущая копия; накопления релизов нет. Реализация подготовлена в репозитории, установка SSH-доступа и secrets на настоящей VM/GitHub пока ожидается. Этот документ заменяет прежние упоминания SSH-доставки как ещё не реализованного кода; исторические записи сохранены.

## Подтверждённый Linux CI

[Запуск №39273932076](https://github.com/mforseale/nen/actions/runs/39273932076) для commit `7cdaa72911cac62034485c0514bb3be1f8e99907` завершился успешно. Пройдены API-тесты, 17 тестов архива/протокола/восстановления, frontend-тесты, lint, сборка, smoke готового архива и сквозной `Exercise VM deployment over restricted SSH`. Последний выполнял настоящий SSH и systemd на одноразовом runner: установка продолжилась после завершения клиента, повторный deploy не заменил предыдущую отличающуюся версию, данные тестового аккаунта сохранились, код принадлежит root, общий sudo для `nen-deploy` запрещён. Это подтверждение испытания в CI, а не подключения production secrets.

Попытка `ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@144.31.189.98 id -un` из текущей сессии отклонена авторизацией (`Permission denied (publickey,password)`). Доверие host key прошло, но беспарольного root-доступа у агента нет. Поэтому bootstrap на настоящей VM выполняет пользователь в своей уже доступной консоли; закрытые ключи и root-пароль в чат не запрашиваются.

## Поток обновления

`push main → CI → тесты API/frontend → standalone + wheels → smoke + SSH/VM fixture → artifact → Deploy → ограниченный SSH → systemd → установка → health → HTTPS`.

`.github/workflows/deploy.yml` запускается после успешного `CI` через `workflow_run`. Это отдельный workflow, поэтому отмена старой CI-проверки новым push не отменяет установку. Очередь `nen-production` имеет `cancel-in-progress: false`. По умолчанию автоматическая доставка выключена: repository variable `NEN_CD_ENABLED` должна быть равна `true`. До настройки доступа пуши запускают только проверки/сборку.

Деплой разрешён только для успешного CI `push`/`workflow_dispatch` из `main` этого репозитория. `scripts/select_runtime.py` повторно проверяет workflow ID, источник, ветку, событие, результат, SHA и существование artifact. Если в `main` уже другой SHA, старый пакет пропускается. PR и fork не допускаются к secrets. Скачивается artifact конкретного CI run с `actions: read`; распакованные из artifact установочные скрипты **не исполняются с root**.

Проверка свежести выполняется перед доставкой. Если новый push произойдёт после неё, уже начатое обновление завершается, затем очередь обрабатывает новую успешную сборку. GitHub может заменять старые ожидающие jobs более новыми; схема не требует развернуть каждый промежуточный commit.

## Доступ на VM

`scripts/setup-vm-cd.sh` устанавливает:

| Путь/объект | Назначение |
|---|---|
| Пользователь `nen-deploy`, shell `/bin/sh`, без пароля | Отдельная учётная запись для ключа Actions |
| `/var/lib/nen-deploy/.ssh/authorized_keys` | Root-владелец, чтение через группу `nen-deploy`; `restrict` и фиксированный forced command |
| `/usr/local/sbin/nen-deploy` | Root-owned SSH entry point без аргументов |
| `/etc/sudoers.d/nen-deploy` | Только этот entry point с **пустым списком аргументов**, без общего sudo |
| `/usr/local/lib/nen/cd/` | Доверенные root-owned `deploy_vm.py`, `runtime_bundle.py`, `ssh_receive.py` |
| `/etc/systemd/system/nen-deploy.service` | Однократная установка принятого пакета, не привязана к SSH-сессии |
| `/var/lib/nen-cd/` | Закрытая root-папка: один pending-пакет, lock приёма и последний результат |

Ключ разрешает только `probe`, `status` и установку пакета по ограниченному JSON/stdin-протоколу. Shell, SCP/SFTP, tunnel, PTY и произвольные sudo-команды не предоставляются. Передача идёт через SSH со строгой проверкой host key из secret; `ssh-keyscan` с доверием неизвестному серверу в workflow не применяется.

Приём ограничен 512 МиБ и 180 секундами; сверяются длина и SHA-256. После передачи пакет обрабатывает самостоятельная systemd-служба. Разрыв SSH или отмена runner не удаляет её входной файл и не убивает установку. После штатного завершения входной файл удаляется, остаются journal и один `last-result.json`. Авария ОС или принудительное завершение самой службы может потребовать ручной проверки pending/marker; старые файлы не очищаются вслепую.

Установщик закреплён на VM и обновляется оператором отдельно: пользователь, управляющий пакетом, не может подменить root-код установщика. Новые каталоги приложения имеют владельца root и чтение для `nen`; `.next` остаётся доступен на запись для runtime-кэша, `.venv` создаётся от `nen` внутри защищённого API-каталога. Это предотвращает замену путей root-операций из Python/pip-кода, запущенного от `nen`. Повторная установка уже работающего commit не заменяет предыдущую копию. Ожидаемый SHA commit сверяется с `runtime.json` архива.

Данные, сертификаты, env, backup timer и ограничение неизменной схемы БД остаются как в [simple-deployment.md](simple-deployment.md). Root-owned копия установщика поддерживает и ручной откат: `/usr/bin/python3 -E -s /usr/local/lib/nen/cd/deploy_vm.py rollback`.

## Первое подключение

Локальная пара Ed25519 создана в игнорируемой `.deploy/keys/nen-actions` и `.pub`. Закрытый ключ не публикуется, не печатается в логах и не передаётся в чат. Он предназначен только для GitHub Actions. Bootstrap откажется перезаписывать уже установленный доступ; смена ключа/инструментов выполняется отдельным осознанным обновлением.

1. PowerShell на компьютере:

```powershell
Set-Location D:\projects\nen
scp .\.deploy\keys\nen-actions.pub root@144.31.189.98:/root/nen-actions.pub
```

2. На VM от root, из существующего checkout:

```bash
(
  set -eu
  command -v sudo >/dev/null || apt-get install -y sudo
  git -C /root/nen-db-tools pull --ff-only
  bash /root/nen-db-tools/scripts/setup-vm-cd.sh /root/nen-actions.pub
)
```

Bootstrap не меняет SSH-конфигурацию демона, не развёртывает приложение и не перезапускает app-службы. Проверяет sudoers/systemd и выполняет локальный probe от `nen-deploy`. В конце выводит публичную строку host key сервера `144.31.189.98 ssh-ed25519 ...`. Её можно передавать; это не приватный ключ.

3. GitHub → repository **Settings → Secrets and variables → Actions → Secrets**:

- `NEN_DEPLOY_SSH_KEY` — весь локальный закрытый ключ `.deploy/keys/nen-actions`. Для копирования без печати в терминал: `Get-Content -Raw .\.deploy\keys\nen-actions | Set-Clipboard`. Вставить непосредственно в secret.
- `NEN_DEPLOY_KNOWN_HOSTS` — публичная строка из вывода bootstrap на доверенной VM-консоли.

4. Actions → **Deploy → Run workflow**, branch `main`, mode `probe`, `ci_run_id` оставить пустым. Результат должен содержать `ready: true`, `protocol: 1`. Это проверка настоящего SSH-пути из GitHub; приложение не обновляется.
5. Settings → Secrets and variables → Actions → **Variables**: создать repository variable `NEN_CD_ENABLED=true`.
6. Запустить **CI → Run workflow** на текущем `main` либо отправить новый commit. После успешного CI workflow **Deploy** должен сам установить его пакет. Для ручного повторения: Deploy → mode `install`, numeric ID успешного CI run для текущего `main`.

Оператору требуется передать только публичный ключ на VM и добавить два secrets/одну variable в GitHub. Для GitHub использовать доступ пользователя через UI; дополнительных GitHub PAT на VM нет. Доступ Codex к SSH VM и GitHub Secrets в этой сессии отсутствует, поэтому эти шаги выполняются пользователем. Они не считаются завершёнными до подтверждения probe/Deploy.

## Проверки и диагностика

В CI проверяются protocol bounds, hash/commit, источник CI run, обработка ошибок и прежний rollback. Дополнительно `scripts/ci_ssh_deploy.py` допускается только на одноразовом GitHub-hosted Linux runner: готовит настоящий API/web/systemd fixture, ограниченную SSH-учётную запись и отдельный localhost sshd. Передаёт готовый пакет, обрывает клиент после старта службы, проверяет завершение установки, сохранение данных, повторный deploy и запрет общего sudo. Настоящая VM этим тестом не затрагивается.

На VM: `systemctl status nen-deploy.service`, `journalctl -u nen-deploy.service -n 100 --no-pager`, `/var/lib/nen-cd/last-result.json`. После успешного oneshot нормален статус `inactive (dead)`, `Result=success`; служба не должна постоянно работать. Для паузы будущих доставок установить `NEN_CD_ENABLED=false`. Уже начатая установка продолжит работу; это не останавливает сайт.

Основания: [GitHub workflow_run](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_run), [download-artifact](https://github.com/actions/download-artifact), [OpenSSH authorized_keys](https://man.openbsd.org/sshd#AUTHORIZED_KEYS_FILE_FORMAT). Подтверждённые результаты Linux CI и настоящего подключения фиксируются после выполнения.
