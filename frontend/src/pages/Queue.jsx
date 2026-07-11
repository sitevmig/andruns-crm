import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { StatusBadge, QUEUE_COLORS, fmtDate } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export default function Queue() {
  const [tasks, setTasks] = useState([]);

  const load = () => api.get("/queue").then((r) => setTasks(r.data));
  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, []);

  const act = async (url, label) => {
    try { const { data } = await api.post(url); toast.success(`${label}${data.count != null ? `: ${data.count}` : ""}`); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="space-y-3" data-testid="queue-page">
      <h1 className="text-lg font-semibold tracking-tight">Очередь рассылки</h1>

      <Card className="p-3 rounded-sm border shadow-none flex flex-wrap gap-2">
        <Button size="sm" className="h-8" onClick={() => act("/queue/process", "Очередь обработана")} data-testid="process-queue-btn">Обработать сейчас</Button>
        <Button size="sm" variant="outline" className="h-8" onClick={() => act("/queue/retry-errors", "Задачи с ошибками возобновлены")} data-testid="retry-errors-btn">Повторить ошибки</Button>
        <Button size="sm" variant="outline" className="h-8" onClick={() => act("/queue/stop-email", "Email-рассылка остановлена")} data-testid="stop-email-btn">Остановить email</Button>
        <Button size="sm" variant="outline" className="h-8" onClick={() => act("/queue/stop-telegram", "Telegram-рассылка остановлена")} data-testid="stop-telegram-btn">Остановить Telegram</Button>

        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button size="sm" variant="destructive" className="h-8" data-testid="clear-pending-btn">Очистить ожидающие</Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Очистить ожидающие задачи?</AlertDialogTitle>
              <AlertDialogDescription>Будут отменены все задачи в статусе «Ожидает» и «Запланировано». Отправленные не затрагиваются.</AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Отмена</AlertDialogCancel>
              <AlertDialogAction onClick={() => act("/queue/clear-pending", "Очередь очищена")} data-testid="confirm-clear-pending">Очистить</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </Card>

      <div className="bg-white border border-border rounded-sm overflow-auto">
        <table className="crm-table w-full text-sm">
          <thead>
            <tr>
              <th>Организация</th><th>Канал</th><th>Шаблон</th><th>Планируемое время</th>
              <th>Статус</th><th>Попыток</th><th>Ошибка</th><th>Автор</th>
            </tr>
          </thead>
          <tbody>
            {tasks.map((t) => (
              <tr key={t.id} data-testid={`queue-row-${t.id}`}>
                <td className="font-medium">{t.org_name}</td>
                <td>{t.channel}</td>
                <td>{t.template_name}</td>
                <td>{t.scheduled_at ? fmtDate(t.scheduled_at) : "сразу"}</td>
                <td><StatusBadge status={t.status} map={QUEUE_COLORS} /></td>
                <td>{t.attempts}</td>
                <td className="text-destructive text-xs max-w-[180px] truncate">{t.last_error || ""}</td>
                <td className="text-xs text-muted-foreground">{t.created_by}</td>
              </tr>
            ))}
            {tasks.length === 0 && <tr><td colSpan={8} className="text-center text-muted-foreground py-6">Очередь пуста</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
