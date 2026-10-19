CATALOG = [
    {"id": "morning", "title": "Вернуть себе утро", "description": "Первые 30 минут дня — без телефона. Стакан воды, тишина и время для себя.", "rarity": "common", "category": "Осознанность", "symbol": "sun"},
    {"id": "pages", "title": "Ещё одна глава", "description": "Читать не менее 20 страниц каждый день. Не ради количества — ради новых мыслей.", "rarity": "common", "category": "Развитие", "symbol": "book"},
    {"id": "walk", "title": "Выйти за порог", "description": "Каждый день находить 30 минут для прогулки. Без спешки и без наушников.", "rarity": "common", "category": "Движение", "symbol": "compass"},
    {"id": "focus", "title": "Искусство внимания", "description": "Один час глубокой работы каждый день. Одна задача, никаких уведомлений.", "rarity": "rare", "category": "Фокус", "symbol": "eye"},
    {"id": "sleep", "title": "На стороне ночи", "description": "Соблюдать выбранное время отхода ко сну. Оставлять себе не менее восьми часов отдыха.", "rarity": "rare", "category": "Здоровье", "symbol": "moon"},
    {"id": "journal", "title": "Диалог с собой", "description": "Ежедневно записывать несколько честных строк о прожитом дне.", "rarity": "rare", "category": "Осознанность", "symbol": "feather"},
    {"id": "craft", "title": "Год мастерства", "description": "Каждый день уделять время одному выбранному навыку и сохранять след своего пути.", "rarity": "epic", "category": "Развитие", "symbol": "flame"},
    {"id": "body", "title": "Быть в движении", "description": "Посвящать движению хотя бы 20 минут ежедневно, подбирая посильную нагрузку.", "rarity": "epic", "category": "Движение", "symbol": "mountain"},
    {"id": "create", "title": "Оставить след", "description": "Каждый день делать небольшой шаг в собственном творческом проекте.", "rarity": "epic", "category": "Творчество", "symbol": "star"},
    {"id": "word", "title": "Держать своё слово", "description": "Осознанно давать обещания. Каждый день замечать, где слово стало действием.", "rarity": "legendary", "category": "Принципы", "symbol": "sword"},
    {"id": "curiosity", "title": "Остаться учеником", "description": "Сохранять любопытство. Каждый день открывать для себя хотя бы одну новую вещь.", "rarity": "legendary", "category": "Развитие", "symbol": "infinity"},
    {"id": "kindness", "title": "Выбирать человечность", "description": "Ежедневно делать одно доброе дело, не ожидая ничего взамен.", "rarity": "legendary", "category": "Принципы", "symbol": "heart"},
]
_DIRECTIONS = {"morning": "Дисциплина", "pages": "Разум", "walk": "Тело", "focus": "Дисциплина", "sleep": "Тело", "journal": "Разум", "craft": "Разум", "body": "Тело", "create": "Созидание", "word": "Дисциплина", "curiosity": "Разум", "kindness": "Социум"}
for item in CATALOG:
    item["category"] = _DIRECTIONS[item["id"]]
CATALOG += [
    {"id": "conversation", "title": "Быть на связи", "description": "Каждый день уделять время одному содержательному разговору с близким человеком.", "rarity": "common", "category": "Социум", "symbol": "friends"},
    {"id": "sketch", "title": "Ежедневный набросок", "description": "Каждый день создавать небольшой рисунок, текст или музыкальный эскиз в течение 15 минут.", "rarity": "common", "category": "Созидание", "symbol": "feather"},
    {"id": "space", "title": "Порядок вокруг", "description": "Каждый день выделять 10 минут на порядок в одном выбранном месте.", "rarity": "common", "category": "Другое", "symbol": "grid"},
    {"id": "listen", "title": "Учиться слушать", "description": "Ежедневно внимательно выслушивать собеседника, не отвлекаясь на телефон и не перебивая.", "rarity": "rare", "category": "Социум", "symbol": "message"},
    {"id": "small-project", "title": "Месяц своего проекта", "description": "Каждый день работать над одним собственным проектом хотя бы 20 минут и сохранять результат.", "rarity": "rare", "category": "Созидание", "symbol": "star"},
    {"id": "daily-order", "title": "Личная система", "description": "Ежедневно уделять 15 минут выбранному личному делу: быту, документам или организации пространства.", "rarity": "rare", "category": "Другое", "symbol": "compass"},
    {"id": "relationships", "title": "Год внимания к людям", "description": "Ежедневно делать конкретный шаг для поддержания отношений: разговор, помощь или совместное время.", "rarity": "epic", "category": "Социум", "symbol": "friends"},
    {"id": "steady-day", "title": "Ритм года", "description": "Ежедневно выполнять главное запланированное действие и коротко подводить итог дня.", "rarity": "epic", "category": "Дисциплина", "symbol": "target"},
    {"id": "personal-year", "title": "Год личного дела", "description": "Каждый день выделять время одному выбранному личному делу, не относящемуся к остальным направлениям.", "rarity": "epic", "category": "Другое", "symbol": "calendar"},
    {"id": "care", "title": "Забота о теле", "description": "Каждый день находить посильный способ позаботиться о теле: отдых, движение или восстановление.", "rarity": "legendary", "category": "Тело", "symbol": "sun"},
    {"id": "lifelong-create", "title": "Продолжать создавать", "description": "Ежедневно возвращаться к творчеству и сохранять хотя бы небольшой собственный результат.", "rarity": "legendary", "category": "Созидание", "symbol": "feather"},
    {"id": "own-path", "title": "Свой ориентир", "description": "Ежедневно уделять внимание выбранной личной практике и замечать её место в своей жизни.", "rarity": "legendary", "category": "Другое", "symbol": "compass"},
]
TEMPLATES = {item["id"]: item for item in CATALOG}
