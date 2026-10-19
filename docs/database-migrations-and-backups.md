# Миграции SQLite и резервные копии

Решение от 19 октября 2026 года, третий этап [плана CI/CD](ci-cd-plan.md). Изменения сначала проверяются локально и в GitHub Actions; production VM автоматически не меняется.

## Решения

Схемой управляет Alembic. Начальная ревизия `20261019_0001` содержит зафиксированное описание всех текущих таблиц, индексов и ограничений. Она не импортирует изменяемые ORM-модели для создания таблиц. Новые изменения схемы оформляются следующими ревизиями; старые ревизии сохраняются.

`DATABASE_URL` имеет приоритет над значением в `alembic.ini`. Пути Alembic привязаны к расположению ini, а не к рабочей папке. Production использует существующий абсолютный URL `sqlite:////var/lib/nen/pact.db`.

Команда `python -m app.db_admin migrate --backup-dir <каталог>` предназначена для SQLite на диске. Она выполняет изменения в явной SQLite-транзакции `BEGIN IMMEDIATE`, проверяет целостность и схему, создаёт online backup перед изменением существующей БД и применяет миграции через то же соединение. При ошибке изменения транзакции откатываются; резервная копия сохраняется. Повтор на актуальной базе ничего не меняет.

Для существующей базы без версии требуется дополнительный `--adopt-existing`. Сначала её структура сравнивается с эталоном, созданным самой начальной ревизией в памяти: таблицы, колонки, типы, nullable/default, первичные и внешние ключи, уникальные ограничения, индексы и CHECK. Неизвестные таблицы, представления и триггеры также считаются несовпадением. Только точное соответствие позволяет выполнить stamp начальной ревизии; данные при этом не переписываются. Проверка использует зафиксированную ревизию, чтобы будущие изменения ORM не меняли смысл baseline.

API больше не создаёт таблицы при импорте. При старте он требует текущую ревизию; сначала должна успешно выполниться команда migrate. В тестах по-прежнему допустимо создавать изолированную схему из моделей; отдельные тесты проверяют настоящие миграции и соответствие модели/ревизии.

Online backup реализован через `sqlite3.Connection.backup()` с чтением источника в `mode=ro`, включая зафиксированные изменения из WAL. Копия проверяется через `quick_check` и `foreign_key_check`, снабжается JSON-манифестом с размером и SHA-256. Файлы публикуются после завершения записи и проверки, имеют права 0600; имена уникальны. Периодические копии и снимки перед миграцией разделены метками.

Восстановление проверяет манифест, checksum и целостность, затем создаёт только новый файл. Существующая база и её WAL/SHM/journal не перезаписываются. Проверка восстановления проходит на отдельном пути. Замена production-базы — отдельное действие после остановки API и сохранения текущего состояния, с учётом записей после снимка.

Первый установщик резервных копий создаёт отдельные systemd service/timer. Ежедневно в 03:30 по времени VM с небольшой случайной задержкой создаётся копия; хранятся 14 завершённых ежедневных снимков. Снимки `before-migration` и ручные копии автоматически не удаляются. Копии на той же VM не заменяют внешнее хранилище.

Этот этап не включает standalone-пакет, переключение служб на releases/current или SSH-доступ GitHub Actions.

## Использование

Из папки `api`, с установленными `requirements.txt`:

```bash
# Новая SQLite; для production URL уже содержится в /etc/nen/api.env.
export DATABASE_URL=sqlite:////absolute/path/to/pact.db
python -m app.db_admin migrate --backup-dir /absolute/path/to/backups
python -m app.db_admin check

# Только первый переход старой базы, после проверки на её копии:
python -m app.db_admin migrate --backup-dir /absolute/path/to/backups --adopt-existing

# Online backup при работающем API:
python -m app.sqlite_backup backup --source /absolute/path/to/pact.db --directory /absolute/path/to/backups
python -m app.sqlite_backup verify --source /absolute/path/to/backups/nen-manual-....sqlite3

# Восстановление в НОВЫЙ файл (исходный snapshot и JSON сохраняются рядом):
python -m app.sqlite_backup restore --source /absolute/path/to/backups/nen-manual-....sqlite3 --destination /absolute/path/to/restore-check.sqlite3
```

В PowerShell переменная задаётся через `$env:DATABASE_URL = 'sqlite:///...'`; локальный путь по умолчанию — `api/pact.db`, если текущая папка `api`. Рабочий env автоматически не загружается CLI из файла: systemd читает `EnvironmentFile`, а ручная команда получает окружение своей оболочки.

При изменении production-схемы сначала останавливается `nen-api.service`; используется актуальный код и Python-окружение с его зависимостями. Успешный `check` и проверка запуска обязательны перед возвращением трафика. Не запускать `alembic stamp head` вручную для обхода несовпадения схемы. `downgrade base` начальной ревизией запрещён: удаление всех таблиц не является восстановлением данных.

### Установка только ежедневных копий на текущую VM

Этот шаг не обновляет приложение и не запускает миграцию production. Выполняется пользователем через root SSH после публикации скрипта:

```bash
(
  set -eu
  test ! -e /root/nen-db-tools
  if ! command -v git >/dev/null; then
    apt-get update
    NEEDRESTART_MODE=l apt-get install -y git
  fi
  git clone --depth 1 --branch main https://github.com/mforseale/nen.git /root/nen-db-tools
  bash /root/nen-db-tools/scripts/setup-vm-backups.sh
)
```

Появятся `/usr/local/lib/nen/sqlite_backup.py` (stdlib, root-владелец), `/etc/systemd/system/nen-backup.service`, `/etc/systemd/system/nen-backup.timer`, `/var/backups/nen/`. Установщик не перезаписывает существующие service/timer и сразу создаёт первый проверенный снимок. Таймер использует `/usr/bin/python3`, а не venv внутри релиза.

```bash
systemctl list-timers nen-backup.timer --no-pager
journalctl -u nen-backup.service -n 20 --no-pager
```

Операции restore и проверки перед первым production stamp выполняются на отдельной копии; обновление `/srv/nen/api` вместе с переключением на миграции — следующий шаг развёртывания. Бэкапы и их JSON-манифесты не публикуются в Git.

## Проверка реализации

Локально прошли 76 API-тестов, включая 16 новых сценариев миграции/backup/restore, и `pip check`. Дополнительный тест настоящего `systemd-analyze verify` выполняется на Linux в CI; в Windows он пропускается. Основной API fixture теперь создаёт схему настоящими миграциями. Shell-синтаксис установщиков и workflow проверены Bash и actionlint.

На отдельном восстановленном снимке реальной локальной БД выполнен переход к baseline; хеши всех исходных строк, включая BLOB, до и после совпали. Исходная база при этой репетиции открывалась только в `mode=ro`. Отдельно тестируются данные из WAL, сохранность сессии/отметок/вложения, несовпадения схемы, ошибки CHECK/FK, неизвестная ревизия, rollback DDL/stamp/данных и отказ перезаписывать файл при restore. Production VM этой проверкой не затронута.

## Источники

- [Alembic: программные команды и общее соединение](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands)
- [Alembic: сравнение схемы](https://alembic.sqlalchemy.org/en/latest/api/autogenerate.html)
- [Python 3.10: SQLite backup](https://docs.python.org/3.10/library/sqlite3.html#sqlite3.Connection.backup)
- [SQLite: online backup](https://www.sqlite.org/backup.html)
