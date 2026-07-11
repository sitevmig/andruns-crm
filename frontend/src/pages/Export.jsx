import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { fmtDate } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Download } from "lucide-react";

const EXPORTS = [
  { url: "/export/all", name: "crm_all.xlsx", label: "Вся база" },
  { url: "/export/messages", name: "crm_messages.xlsx", label: "История сообщений" },
  { url: "/export/rejections", name: "crm_rejections.xlsx", label: "Список отказов" },
  { url: "/export/dnc", name: "crm_do_not_contact.xlsx", label: "Список «Не связываться»" },
  { url: "/export/errors", name: "crm_errors.xlsx", label: "Ошибки доставки" },
];

export default function ExportPage() {
  const [backups, setBackups] = useState([]);
  const loadBackups = () => api.get("/backups").then((r) => setBackups(r.data));
  useEffect(() => { loadBackups(); }, []);

  const download = async (url, name) => {
    try {
      const res = await api.get(url, { responseType: "blob" });
      const objectUrl = URL.createObjectURL(res.data);
      const a = document.createElement("a"); a.href = objectUrl; a.download = name; a.click();
      toast.success("Файл выгружен");
    } catch (e) { toast.error(apiError(e)); }
  };

  const createBackup = async () => {
    try { await api.post("/backups"); toast.success("Резервная копия создана"); loadBackups(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const downloadBackup = async (id) => {
    const res = await api.get(`/backups/${id}/download`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a"); a.href = url; a.download = `backup_${id}.json`; a.click();
  };
  const restore = async (id) => {
    try { await api.post("/backups/restore", { backup_id: id, confirm: true }); toast.success("Восстановлено"); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="space-y-4 max-w-3xl" data-testid="export-page">
      <h1 className="text-lg font-semibold tracking-tight">Экспорт и резервное копирование</h1>

      <Card className="p-4 rounded-sm border shadow-none">
        <div className="text-sm font-medium mb-3">Экспорт в Excel (с актуальными статусами CRM)</div>
        <div className="grid md:grid-cols-2 gap-2">
          {EXPORTS.map((e) => (
            <Button key={e.url} variant="outline" className="h-9 justify-start" onClick={() => download(e.url, e.name)} data-testid={`export-${e.url.split("/").pop()}`}>
              <Download size={14} className="mr-2" />{e.label}
            </Button>
          ))}
        </div>
      </Card>

      <Card className="p-4 rounded-sm border shadow-none">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-medium">Резервные копии</div>
          <Button size="sm" className="h-8" onClick={createBackup} data-testid="create-backup-btn">Создать копию</Button>
        </div>
        <div className="text-xs text-muted-foreground mb-2">Последняя копия: {backups[0] ? fmtDate(backups[0].created_at) : "нет"}</div>
        <table className="crm-table w-full text-xs">
          <thead><tr><th>Дата</th><th>Автор</th><th>Размер</th><th>Действия</th></tr></thead>
          <tbody>
            {backups.map((b) => (
              <tr key={b.backup_id}>
                <td>{fmtDate(b.created_at)}</td><td>{b.created_by}</td><td>{(b.size / 1024).toFixed(1)} КБ</td>
                <td className="flex gap-2">
                  <Button size="sm" variant="link" className="h-6 p-0" onClick={() => downloadBackup(b.backup_id)}>Скачать</Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild><Button size="sm" variant="link" className="h-6 p-0 text-destructive" data-testid={`restore-${b.backup_id}`}>Восстановить</Button></AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Восстановить из копии?</AlertDialogTitle>
                        <AlertDialogDescription>Текущие данные будут заменены данными из этой резервной копии. Действие необратимо.</AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Отмена</AlertDialogCancel>
                        <AlertDialogAction onClick={() => restore(b.backup_id)}>Восстановить</AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </td>
              </tr>
            ))}
            {backups.length === 0 && <tr><td colSpan={4} className="text-center text-muted-foreground py-3">Копий нет</td></tr>}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
