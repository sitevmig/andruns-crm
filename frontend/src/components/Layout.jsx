import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  LayoutDashboard, Building2, Upload, ListChecks, FileText, MessageSquare,
  Copy, Download, ScrollText, Settings as SettingsIcon, LogOut, Square, Play,
} from "lucide-react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

const NAV = [
  { to: "/", label: "Главная", icon: LayoutDashboard, end: true },
  { to: "/organizations", label: "Организации", icon: Building2 },
  { to: "/import", label: "Импорт", icon: Upload },
  { to: "/queue", label: "Очередь", icon: ListChecks },
  { to: "/templates", label: "Шаблоны", icon: FileText },
  { to: "/replies", label: "Ответы", icon: MessageSquare, badgeKey: "replies" },
  { to: "/duplicates", label: "Дубли", icon: Copy },
  { to: "/export", label: "Экспорт", icon: Download },
  { to: "/journal", label: "Журнал", icon: ScrollText },
  { to: "/settings", label: "Настройки", icon: SettingsIcon },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [unread, setUnread] = useState(0);
  const [sendingStopped, setSendingStopped] = useState(false);

  const refresh = () => {
    api.get("/replies/unread-count").then((r) => setUnread(r.data.count)).catch(() => {});
    api.get("/settings").then((r) => setSendingStopped(r.data.sending_stopped)).catch(() => {});
  };

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 20000);
    return () => clearInterval(t);
  }, [location.pathname]);

  const toggleSending = async () => {
    try {
      if (sendingStopped) {
        await api.post("/queue/resume");
        toast.success("Рассылка возобновлена");
      } else {
        await api.post("/queue/stop-all");
        toast.success("Все рассылки остановлены");
      }
      refresh();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-60 shrink-0 border-r border-border bg-white flex flex-col">
        <div className="h-14 flex items-center px-4 border-b border-border">
          <span className="font-semibold tracking-tight text-primary">CRM · Холодные продажи</span>
        </div>
        <nav className="flex-1 overflow-y-auto py-2">
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                data-testid={`nav-${item.label}`}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
                    isActive ? "bg-primary/10 text-primary font-medium border-r-2 border-primary" : "text-zinc-600 hover:bg-zinc-50"
                  }`
                }
              >
                <Icon size={16} />
                <span className="flex-1">{item.label}</span>
                {item.badgeKey === "replies" && unread > 0 && (
                  <span className="rounded-full bg-emerald-600 text-white text-[10px] px-1.5 py-0.5" data-testid="replies-badge">
                    {unread}
                  </span>
                )}
              </NavLink>
            );
          })}
        </nav>
        <div className="border-t border-border p-3 text-xs text-muted-foreground">
          <div className="mb-2 truncate">{user?.name} · {user?.email}</div>
          <Button variant="outline" size="sm" className="w-full h-8" onClick={logout} data-testid="logout-btn">
            <LogOut size={14} className="mr-1" /> Выйти
          </Button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-14 shrink-0 border-b border-border bg-white flex items-center justify-between px-4">
          <div className="text-sm text-muted-foreground">
            {sendingStopped ? (
              <span className="text-red-600 font-medium">● Рассылка остановлена</span>
            ) : (
              <span className="text-emerald-600 font-medium">● Рассылка активна</span>
            )}
          </div>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button
                variant={sendingStopped ? "default" : "destructive"}
                size="sm"
                className="h-8"
                data-testid="toggle-sending-btn"
              >
                {sendingStopped ? <><Play size={14} className="mr-1" /> Возобновить рассылку</> : <><Square size={14} className="mr-1" /> Остановить все рассылки</>}
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{sendingStopped ? "Возобновить рассылку?" : "Остановить все рассылки?"}</AlertDialogTitle>
                <AlertDialogDescription>
                  {sendingStopped
                    ? "Новые сообщения из очереди снова будут отправляться."
                    : "Отправка новых сообщений будет остановлена. Сохранённые данные не удаляются."}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Отмена</AlertDialogCancel>
                <AlertDialogAction onClick={toggleSending} data-testid="confirm-toggle-sending">Подтвердить</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </header>
        <main className="flex-1 overflow-auto p-4">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
