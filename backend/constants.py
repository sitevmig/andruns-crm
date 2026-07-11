STATUS_NEW = "Новый"
STATUS_READY = "Готов к отправке"
STATUS_SCHEDULED = "Запланирован"
STATUS_SENT = "Отправлено"
STATUS_REPLIED = "Ответил"
STATUS_INTERESTED = "Проявил интерес"
STATUS_REJECTED = "Отказ"
STATUS_IN_PROGRESS = "В работе"
STATUS_DONE = "Завершено"
STATUS_DNC = "Не связываться"
STATUS_DELIVERY_ERROR = "Ошибка доставки"
STATUS_DUPLICATE = "Дубликат"
STATUS_ARCHIVE = "Архив"

ORG_STATUSES = [
    STATUS_NEW, STATUS_READY, STATUS_SCHEDULED, STATUS_SENT, STATUS_REPLIED,
    STATUS_INTERESTED, STATUS_REJECTED, STATUS_IN_PROGRESS, STATUS_DONE,
    STATUS_DNC, STATUS_DELIVERY_ERROR, STATUS_DUPLICATE, STATUS_ARCHIVE,
]

Q_WAITING = "Ожидает"
Q_SCHEDULED = "Запланировано"
Q_SENDING = "Отправляется"
Q_SENT = "Отправлено"
Q_ERROR = "Ошибка"
Q_CANCELLED = "Отменено"
Q_SKIPPED = "Пропущено"
Q_BLOCKED = "Заблокировано"

QUEUE_STATUSES = [Q_WAITING, Q_SCHEDULED, Q_SENDING, Q_SENT, Q_ERROR, Q_CANCELLED, Q_SKIPPED, Q_BLOCKED]

CHANNEL_EMAIL = "email"
CHANNEL_TELEGRAM = "telegram"

# CRM field keys used for import column mapping
CRM_FIELDS = [
    {"key": "external_id", "label": "Внешний ID"},
    {"key": "name", "label": "Наименование организации"},
    {"key": "category", "label": "Категория бизнеса"},
    {"key": "city", "label": "Город"},
    {"key": "address", "label": "Адрес"},
    {"key": "phone", "label": "Телефон"},
    {"key": "email", "label": "Email"},
    {"key": "telegram", "label": "Telegram"},
    {"key": "source_url", "label": "Ссылка / источник"},
    {"key": "comment", "label": "Комментарий"},
]

SAVED_FILTERS = [
    {"key": "new_leads", "label": "Новые лиды", "filters": {"status": STATUS_NEW}},
    {"key": "ready_email", "label": "Готовы к email-рассылке", "filters": {"status": STATUS_READY, "has_email": "yes"}},
    {"key": "ready_telegram", "label": "Готовы к Telegram-рассылке", "filters": {"status": STATUS_READY, "has_telegram": "yes"}},
    {"key": "replied", "label": "Ответившие", "filters": {"status": STATUS_REPLIED}},
    {"key": "interested", "label": "Заинтересованные", "filters": {"status": STATUS_INTERESTED}},
    {"key": "rejected", "label": "Отказы", "filters": {"status": STATUS_REJECTED}},
    {"key": "errors", "label": "Ошибки", "filters": {"status": STATUS_DELIVERY_ERROR}},
    {"key": "in_progress", "label": "В работе", "filters": {"status": STATUS_IN_PROGRESS}},
    {"key": "dnc", "label": "Не связываться", "filters": {"do_not_contact": "yes"}},
]
