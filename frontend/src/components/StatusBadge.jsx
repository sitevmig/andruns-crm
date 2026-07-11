export const STATUS_COLORS = {
  "Новый": "bg-zinc-100 text-zinc-700",
  "Готов к отправке": "bg-sky-100 text-sky-800",
  "Запланирован": "bg-indigo-100 text-indigo-800",
  "Отправлено": "bg-blue-100 text-blue-800",
  "Ответил": "bg-emerald-100 text-emerald-800",
  "Проявил интерес": "bg-green-100 text-green-800",
  "Отказ": "bg-rose-100 text-rose-800",
  "В работе": "bg-amber-100 text-amber-800",
  "Завершено": "bg-teal-100 text-teal-800",
  "Не связываться": "bg-red-600 text-white",
  "Ошибка доставки": "bg-orange-100 text-orange-800",
  "Дубликат": "bg-purple-100 text-purple-800",
  "Архив": "bg-zinc-200 text-zinc-500",
};

export const QUEUE_COLORS = {
  "Ожидает": "bg-zinc-100 text-zinc-700",
  "Запланировано": "bg-indigo-100 text-indigo-800",
  "Отправляется": "bg-amber-100 text-amber-800",
  "Отправлено": "bg-emerald-100 text-emerald-800",
  "Ошибка": "bg-rose-100 text-rose-800",
  "Отменено": "bg-zinc-200 text-zinc-500",
  "Пропущено": "bg-zinc-200 text-zinc-500",
  "Заблокировано": "bg-red-100 text-red-800",
};

export function StatusBadge({ status, map = STATUS_COLORS }) {
  const cls = map[status] || "bg-zinc-100 text-zinc-700";
  return (
    <span className={`inline-block rounded-sm px-1.5 py-0.5 text-xs font-medium whitespace-nowrap ${cls}`}>
      {status}
    </span>
  );
}

export function fmtDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}
