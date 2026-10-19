# CI: проверки в GitHub Actions

Обновление: CI теперь дополнительно проверяет восстановление при ошибках деплоя, собирает standalone + Linux Python wheels и запускает готовый архив с временной БД. Web-job зависит от успешной API-job. Успешный `main` публикует artifact на 7 дней. Детали: [simple-deployment.md](simple-deployment.md). Сведения о первых проверках ниже сохранены как история.

Проверка новой схемы подтверждена успешным [запуском №39264071434](https://github.com/mforseale/nen/actions/runs/39264071434) на commit `865dbd0`; шаг запуска готового архива и публикация artifact успешны. Установщик на рабочей VM пока не выполнялся.

Решение от 19 октября 2026 года. Второй этап [плана CI/CD](ci-cd-plan.md) реализован в `.github/workflows/ci.yml`. Первый этап — [общий репозиторий](repository.md).

## Подтверждённый запуск

Workflow опубликован коммитом `3916776`. Первый автоматический [push-запуск CI №39253746767](https://github.com/mforseale/nen/actions/runs/39253746767) завершился успешно 19 октября 2026 года. Через GitHub REST проверены `conclusion: success` у всего запуска и обеих jobs; установка зависимостей, API-тесты, frontend-тесты, lint и production build имеют статус success. До отправки workflow проверен `actionlint` 1.7.12, загруженным из официального релиза с проверкой SHA-256. Состав тестов на момент настройки — 60 API и 32 frontend; результаты локальной проверки также записаны в [repository.md](repository.md).

## Когда и что запускается

Workflow `CI` запускается при push в `main`, при открытии и обновлении pull request в `main`, а также вручную через Actions → CI → Run workflow. Две независимые проверки выполняются на GitHub-hosted `ubuntu-22.04` x64:

| Проверка | Окружение | Команды |
|---|---|---|
| `API (Python 3.10)` | Python 3.10, зависимости из `api/requirements.txt` | `python -m pip check`, `python -m unittest discover -s tests -v` |
| `Web (Node 24)` | Node.js 24, установка через `npm ci` по `web/package-lock.json` | `npm test`, `npm run lint`, `npm run build` |

Сначала в каждой проверке устанавливаются зависимости. Кэшируются загрузки pip/npm, а не готовые виртуальные окружения, `node_modules` или `.next`. Версии официальных Actions закреплены полными SHA коммитов; при обновлении их следует сверять с официальными репозиториями. Среда согласована с текущей VM: Ubuntu 22.04, Python 3.10, Node 24.

Повторный запуск для той же ветки или PR отменяет предыдущую незавершённую проверку. API ограничен 10 минутами, frontend — 20 минутами. Это поведение относится только к CI; будущий deploy не должен прерываться посреди миграции.

## Изоляция от production

Workflow имеет только `contents: read`, не сохраняет Git-credentials в checkout и не использует пользовательские secrets или SSH. Используется событие `pull_request`, без `pull_request_target`.

API получает `DATABASE_URL=sqlite://`, `PACT_DEBUG=false`, `PACT_COOKIE_SECURE=false`; тесты создают изолированные базы в памяти и временные SQLite для проверок сохранности/конкурентности. Основной API fixture применяет настоящие миграции. Проверки [миграций и бэкапов](database-migrations-and-backups.md) включены в тот же unittest discovery; отдельный шаг проверяет Bash-синтаксис установщиков. Рабочие `api/pact.db` и `/var/lib/nen/pact.db` недоступны runner.

Frontend собирается с `NEN_API_ORIGIN=http://127.0.0.1:8000` и отключённой телеметрией Next.js. Браузер использует относительный `/api/v1`; `NEXT_PUBLIC_API_URL` не задаётся. Для текущей сборки работающий API не нужен: загрузка пользовательских данных происходит на клиенте.

Результат этого этапа — проверка исходников, включая production build. Готовый deploy-артефакт пока не сохраняется, standalone не включается, работающая VM не обновляется. Проверки браузера, внешнего HTTPS, миграций и перезапуска служб не входят в этот workflow.

## Как смотреть результат

Открыть [Actions → CI](https://github.com/mforseale/nen/actions/workflows/ci.yml), выбрать запуск и раскрыть шаг с ошибкой. Зелёный итог означает, что обе проверки завершились успешно. Для исправления ошибки нужно отправить следующий коммит; для повторения временно упавшего запуска доступна кнопка Re-run jobs.

Workflow сам не включает защиту `main`: обязательность успешных проверок при merge задаётся отдельно в настройках GitHub. Это не требуется для первого запуска CI.

## Источники

- [GitHub: синтаксис workflow](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
- [actions/checkout](https://github.com/actions/checkout)
- [actions/setup-python](https://github.com/actions/setup-python)
- [actions/setup-node](https://github.com/actions/setup-node)
- Установленная документация Next.js: `web/node_modules/next/dist/docs/01-app/01-getting-started/17-deploying.md` и `01-app/02-guides/environment-variables.md`.
