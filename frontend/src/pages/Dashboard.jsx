import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";

const STAT_ITEMS = [
  { key: "total", label: "Всего организаций" },
  { key: "new", label: "Новых" },
  { key: "ready", label: "Готовы к отправке" },
  { key: "sent_today", label: "Отправлено сегодня" },
  { key: "sent_week", label: "Отправлено за неделю" },
  { key: "replied", label: "Ответили" },
  { key: "interested", label: "Проявили интерес" },
  { key: "rejected", label: "Отказали" },
  { key: "in_progress", label: "В работе" },
  { key: "errors", label: "Ошибки доставки" },
  { key: "queue_count", label: "Задач в очереди" },
];

const FUNNEL = [
  { key: "imported", label: "Импортировано" },
  { key: "sent", label: "Отправлено" },
  { key: "replied", label: "Ответило" },
  { key: "interested", label: "Проявило интерес" },
  { key: "in_progress", label: "В работе" },
  { key: "done", label: "Завершено" },
];

export default function Dashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/dashboard").then((r) => setData(r.data)).catch(() => {});
  }, []);

  if (!data) return <div className="text-muted-foreground">Загрузка…</div>;
  const { stats, funnel } = data;
  const maxFunnel = Math.max(...FUNNEL.map((f) => funnel[f.key] || 0), 1);

  return (
    <div className="space-y-4" data-testid="dashboard">
      <h1 className="text-lg font-semibold tracking-tight">Панель управления</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        {STAT_ITEMS.map((s) => (
          <Card key={s.key} className="p-3 rounded-sm border shadow-none" data-testid={`stat-${s.key}`}>
            <div className="text-2xl font-semibold tabular-nums">{stats[s.key]}</div>
            <div className="text-xs text-muted-foreground mt-1">{s.label}</div>
          </Card>
        ))}
      </div>

      <div className="grid md:grid-cols-3 gap-3">
        <Card className="p-3 rounded-sm border shadow-none">
          <div className="text-xs text-muted-foreground">Telegram</div>
          <div className={`text-sm font-medium mt-1 ${stats.telegram_connected ? "text-emerald-600" : "text-red-600"}`}>
            {stats.telegram_status}
          </div>
        </Card>
        <Card className="p-3 rounded-sm border shadow-none">
          <div className="text-xs text-muted-foreground">Email-рассылка</div>
          <div className={`text-sm font-medium mt-1 ${stats.email_enabled ? "text-emerald-600" : "text-red-600"}`}>
            {stats.email_enabled ? "Включена" : "Отключена"}
          </div>
        </Card>
        <Card className="p-3 rounded-sm border shadow-none">
          <div className="text-xs text-muted-foreground">Статус рассылки</div>
          <div className={`text-sm font-medium mt-1 ${stats.sending_stopped ? "text-red-600" : "text-emerald-600"}`}>
            {stats.sending_stopped ? "Остановлена" : "Активна"}
          </div>
        </Card>
      </div>

      <Card className="p-4 rounded-sm border shadow-none">
        <div className="text-sm font-semibold mb-3">Воронка</div>
        <div className="space-y-2">
          {FUNNEL.map((f) => (
            <div key={f.key} className="flex items-center gap-3" data-testid={`funnel-${f.key}`}>
              <div className="w-36 text-xs text-muted-foreground shrink-0">{f.label}</div>
              <div className="flex-1 bg-zinc-100 rounded-sm h-6 relative">
                <div
                  className="bg-primary h-6 rounded-sm transition-all"
                  style={{ width: `${((funnel[f.key] || 0) / maxFunnel) * 100}%` }}
                />
              </div>
              <div className="w-10 text-right text-sm font-medium tabular-nums">{funnel[f.key] || 0}</div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
