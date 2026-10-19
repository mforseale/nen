# Автоматическая доставка Nen из GitHub Actions

## Первая автоматическая установка подтверждена — 19 октября 2026

Полная цепочка `push → CI → Deploy → VM` прошла для commit `651a3f4d3666aea0416817435819480772e9684f`: [CI №39287002015](https://github.com/mforseale/nen/actions/runs/39287002015) и [Deploy №39287786098](https://github.com/mforseale/nen/actions/runs/39287786098) завершились с `success`. В Deploy успешны выбор проверенного artifact, скачивание, `Deliver and install runtime` и `Check public HTTPS`; probe пропущен, поскольку выполнялась настоящая установка.

Независимый запрос через production SSH `status` вернул `status=success`, `exit_code=0`, тот же полный commit и SHA-256 пакета `08ca657d2f48cba6e0786aecd92b0841a0c08195b33fd9dfea1accbec4575e1e`. Повторная публичная проверка с обычной проверкой TLS: health HTTP 200 с `{"status":"ok"}`, главная HTTP 200 с HTML. Вход пользователя в браузере этой проверкой не проверялся.

Bootstrap, оба GitHub secrets, repository variable `NEN_CD_ENABLED=true` и права родителя `/srv/nen` настроены. Обычный push в `main` теперь запускает проверки и автоматическую установку прошедшего их актуального commit. Сохраняются одна рабочая версия и одна предыдущая копия; схема БД обновляется отдельным проверенным шагом. Последующие записи описывают историю настройки, а ожидания в них относятся к соответствующему этапу.

## Включение автоматической установки

Пользователь подтвердил создание repository variable `NEN_CD_ENABLED=true`; новый ручной CI при этом не запускался. Старый автоматический Deploy №39284837717, созданный до включения, завершился `skipped`. Для первой установки запускаем новую цепочку обычным push с записью подтверждённых этапов, чтобы проверить путь `push → CI → Deploy`.

Уточнение прав: корневой `/srv/nen` тоже должен принадлежать `root:nen` с режимом `0750`; первоначальная установка делала его владельцем `nen`. Иначе пользователь мог бы переименовать защищённые `api`/`web` через доступного на запись родителя. Исправлено в bootstrap CD и воспроизведено в Linux fixture с проверкой запрета записи от `nen`. Пользователь подтвердил успешное выполнение `chown root:nen /srv/nen && chmod 0750 /srv/nen` на VM без рекурсивной смены владельцев и без остановки приложения. После этого публичные HTTPS health и главная проверены: оба HTTP 200, health вернул `{"status":"ok"}`.

Push `651a3f4` создал [CI №39287002015](https://github.com/mforseale/nen/actions/runs/39287002015). Обе задачи API и Web завершились успешно, включая готовый runtime и реальную SSH/systemd fixture с проверкой прав родителя. До подтверждения первой установки новые изменения не отправлялись в `main`, чтобы SHA ожидаемого пакета не менялся.

## GitHub SSH probe подтверждён

Ручной [Deploy №39282608232](https://github.com/mforseale/nen/actions/runs/39282608232) на commit `148bb49` завершился успешно: `Check restricted SSH access` имеет success, выбор/скачивание artifact и `Deliver and install runtime` пропущены. Оба GitHub secrets настроены достаточно для настоящего подключения из Actions. Это именно проверка доступа; установка этим запуском не выполнялась.

[CI №39281981181](https://github.com/mforseale/nen/actions/runs/39281981181) для того же commit также успешен, включая smoke готового пакета и SSH/systemd fixture. После него создан автоматический Deploy №39284837717; при проверке он ещё находился в очереди. Чтение production SSH `status` вернуло `not-deployed`: первая установка через новую CD-службу ещё не подтверждена. Следующий шаг — подтверждение `NEN_CD_ENABLED=true` и успешный install через Deploy. Эта запись пока локальная: новый push в main до окончания ожидающего первого Deploy изменил бы SHA и заставил selector пропустить уже собранный пакет.

## Production SSH подтверждён

После запуска bootstrap пользователь очистил терминал и повторил установщик. Повторный запуск остановился на уже существующем `/usr/local/lib/nen/cd`; это штатная защита от перезаписи. Далее SSH-сессия пользователя закрылась, и Linux-команда `runuser` оказалась в Windows CMD. Для продолжения повторная установка не нужна.

Из текущей сессии выполнен настоящий SSH `probe` на `nen-deploy@144.31.189.98` с выделенным `.deploy/keys/nen-actions`, `IdentitiesOnly=yes`, `BatchMode=yes`, `StrictHostKeyChecking=yes`. Получен успешный ответ `{"ready":true,"protocol":1,"busy":false}`. Это подтверждает установленный SSH gate и sudo-команду на настоящей VM; GitHub Secrets и первый production Deploy из Actions ещё ожидаются.

Чтобы не возвращаться в VM-консоль за публичным host key, извлечена единственная ранее доверенная Ed25519-запись именно для `144.31.189.98` через локальный `ssh-keygen -F`. Её доверие дополнительно проверено успешным строгим SSH-соединением. Запись сохранена в игнорируемый `.deploy/keys/nen-known-hosts`; fingerprint `SHA256:XG5bHiHrix/pOY+SxWcdMKHbLbPLsB6x3LpB4fY4mTI`. Нового доверия через непроверенный `ssh-keyscan` не добавлялось.

Оставшаяся настройка GitHub: secret `NEN_DEPLOY_SSH_KEY` из `.deploy/keys/nen-actions` и secret `NEN_DEPLOY_KNOWN_HOSTS` из `.deploy/keys/nen-known-hosts`, затем Actions Deploy/probe, repository variable `NEN_CD_ENABLED=true`, CI на текущем `main`. Для копирования в clipboard из Windows CMD можно вызвать `powershell -NoProfile -Command "Get-Content -Raw 'D:\projects\nen\.deploy\keys\nen-actions' | Set-Clipboard"`; аналогично для `nen-known-hosts`. Приватный ключ не печатается и не передаётся в чат. Исторические ожидания bootstrap ниже относятся к моменту подготовки.

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
