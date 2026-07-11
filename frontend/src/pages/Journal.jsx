import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { fmtDate } from "@/components/StatusBadge";
import { Card } from "@/components/ui/card";

export default function Journal() {
  const [events, setEvents] = useState([]);
  useEffect(() => { api.get("/auth/login-journal").then((r) => setEvents(r.data)); }, []);

  return (
    <div className="space-y-3" data-testid="journal-page">
      <h1 className="text-lg font-semibold tracking-tight">Журнал входов</h1>
      <Card className="rounded-sm border shadow-none overflow-auto">
        <table className="crm-table w-full text-sm">
          <thead><tr><th>Дата</th><th>Email</th><th>Результат</th><th>IP</th><th>Устройство</th></tr></thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id}>
                <td>{fmtDate(e.at)}</td>
                <td>{e.email}</td>
                <td>{e.success ? <span className="text-emerald-600">Успех</span> : <span className="text-destructive">Ошибка</span>}</td>
                <td>{e.ip}</td>
                <td className="text-xs text-muted-foreground max-w-[300px] truncate">{e.user_agent}</td>
              </tr>
            ))}
            {events.length === 0 && <tr><td colSpan={5} className="text-center text-muted-foreground py-4">Пусто</td></tr>}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
