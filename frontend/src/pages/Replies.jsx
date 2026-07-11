import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { StatusBadge, fmtDate } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";

export default function Replies() {
  const [replies, setReplies] = useState([]);
  const [orgs, setOrgs] = useState([]);
  const [simOrg, setSimOrg] = useState("");
  const [simText, setSimText] = useState("Здравствуйте! Расскажите подробнее о ваших услугах.");

  const load = () => api.get("/replies").then((r) => setReplies(r.data));
  useEffect(() => {
    load();
    api.get("/organizations", { params: { page_size: 100 } }).then((r) => setOrgs(r.data.items));
  }, []);

  const markRead = async (id) => { await api.post(`/replies/${id}/read`); load(); };
  const markAll = async () => { await api.post("/replies/read-all"); toast.success("Отмечено прочитанным"); load(); };
  const simulate = async () => {
    if (!simOrg) { toast.error("Выберите организацию"); return; }
    try { await api.post("/replies/simulate", { org_id: simOrg, text: simText, channel: "telegram" }); toast.success("Ответ зарегистрирован"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="space-y-3" data-testid="replies-page">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">Ответы</h1>
        <div className="flex gap-2">
          <Dialog>
            <DialogTrigger asChild><Button size="sm" variant="outline" className="h-8" data-testid="simulate-reply-btn">Зарегистрировать ответ</Button></DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Входящий ответ (Telegram)</DialogTitle></DialogHeader>
              <Select value={simOrg} onValueChange={setSimOrg}>
                <SelectTrigger className="h-8" data-testid="sim-org-select"><SelectValue placeholder="Организация" /></SelectTrigger>
                <SelectContent>{orgs.map((o) => <SelectItem key={o.id} value={o.id}>{o.name}</SelectItem>)}</SelectContent>
              </Select>
              <Textarea value={simText} onChange={(e) => setSimText(e.target.value)} data-testid="sim-text" />
              <DialogFooter><Button onClick={simulate} data-testid="confirm-simulate">Сохранить</Button></DialogFooter>
            </DialogContent>
          </Dialog>
          <Button size="sm" variant="outline" className="h-8" onClick={markAll} data-testid="mark-all-read-btn">Всё прочитано</Button>
        </div>
      </div>

      <div className="space-y-2">
        {replies.map((m) => (
          <Card key={m.id} className={`p-3 rounded-sm border shadow-none ${m.read ? "" : "border-l-4 border-l-emerald-500"}`} data-testid={`reply-${m.id}`}>
            <div className="flex items-center justify-between">
              <div className="font-medium">{m.org_name} {m.org_status && <StatusBadge status={m.org_status} />}</div>
              <div className="text-xs text-muted-foreground">{m.channel} · {fmtDate(m.at)}</div>
            </div>
            <div className="text-sm mt-1 whitespace-pre-wrap">{m.text}</div>
            {!m.read && <Button size="sm" variant="link" className="h-6 p-0 mt-1" onClick={() => markRead(m.id)}>Отметить прочитанным</Button>}
          </Card>
        ))}
        {replies.length === 0 && <div className="text-center text-muted-foreground py-8">Входящих ответов нет</div>}
      </div>
    </div>
  );
}
