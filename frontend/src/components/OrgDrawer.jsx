import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { StatusBadge, fmtDate } from "@/components/StatusBadge";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { ExternalLink, Ban, Archive, Mail } from "lucide-react";

export default function OrgDrawer({ orgId, statuses, onClose, onChanged }) {
  const [org, setOrg] = useState(null);
  const [messages, setMessages] = useState([]);
  const [changes, setChanges] = useState([]);
  const [comment, setComment] = useState("");
  const [nextAction, setNextAction] = useState("");
  const [emailSubject, setEmailSubject] = useState("");
  const [emailText, setEmailText] = useState("");

  const load = () => {
    if (!orgId) return;
    api.get(`/organizations/${orgId}`).then((r) => {
      setOrg(r.data);
      setComment(r.data.comment || "");
      setNextAction(r.data.next_action_at || "");
    });
    api.get(`/organizations/${orgId}/messages`).then((r) => setMessages(r.data));
    api.get(`/organizations/${orgId}/changes`).then((r) => setChanges(r.data));
  };

  useEffect(() => {
    load(); // eslint-disable-next-line
  }, [orgId]);

  const notify = () => { onChanged?.(); load(); };

  const changeStatus = async (status) => {
    try { await api.post(`/organizations/${orgId}/status`, { status }); toast.success("Статус обновлён"); notify(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const markDnc = async () => {
    try { await api.post(`/organizations/${orgId}/dnc`, {}); toast.success("Отмечено «Не связываться»"); notify(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const saveComment = async () => {
    try { await api.post(`/organizations/${orgId}/comment`, { comment }); toast.success("Комментарий сохранён"); notify(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const saveNextAction = async () => {
    try { await api.post(`/organizations/${orgId}/next-action`, { next_action_at: nextAction }); toast.success("Действие назначено"); notify(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const archive = async () => {
    try { await api.post(`/organizations/${orgId}/archive`); toast.success("Архивировано"); notify(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const sendEmail = async () => {
    try {
      await api.post(`/email/send`, { org_id: orgId, subject: emailSubject, text: emailText });
      toast.success("Письмо отправлено (демо-режим)"); setEmailSubject(""); setEmailText(""); notify();
    } catch (e) { toast.error(apiError(e)); }
  };

  if (!org) return null;

  return (
    <Sheet open={!!orgId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full sm:max-w-2xl overflow-y-auto" data-testid="org-drawer">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            {org.name}
            <StatusBadge status={org.status} />
            {org.do_not_contact && (
              <span className="rounded-sm bg-red-600 text-white text-xs px-1.5 py-0.5" data-testid="dnc-indicator">
                Не связываться
              </span>
            )}
          </SheetTitle>
        </SheetHeader>

        <Tabs defaultValue="info" className="mt-4">
          <TabsList>
            <TabsTrigger value="info" data-testid="tab-info">Сведения</TabsTrigger>
            <TabsTrigger value="messages" data-testid="tab-messages">Сообщения ({messages.length})</TabsTrigger>
            <TabsTrigger value="changes" data-testid="tab-changes">Изменения ({changes.length})</TabsTrigger>
            <TabsTrigger value="actions" data-testid="tab-actions">Действия</TabsTrigger>
          </TabsList>

          <TabsContent value="info" className="space-y-2 text-sm mt-3">
            {[
              ["Категория", org.category], ["Город", org.city], ["Адрес", org.address],
              ["Телефон", org.phone], ["Email", org.email], ["Telegram", org.telegram],
              ["Источник", org.source_url], ["Причина отказа", org.rejection_reason],
              ["Последний канал", org.last_channel], ["Последнее сообщение", fmtDate(org.last_message_at)],
              ["Следующее действие", org.next_action_at ? fmtDate(org.next_action_at) : "—"],
              ["Последний ответ", org.last_reply_at ? fmtDate(org.last_reply_at) : "—"],
              ["Импортирована", fmtDate(org.first_import_at)],
            ].map(([k, v]) => (
              <div key={k} className="flex border-b border-border py-1">
                <div className="w-40 text-muted-foreground shrink-0">{k}</div>
                <div className="flex-1 break-all">{v || "—"}</div>
              </div>
            ))}
          </TabsContent>

          <TabsContent value="messages" className="mt-3">
            {messages.length === 0 && <div className="text-sm text-muted-foreground">Сообщений нет</div>}
            <div className="space-y-2">
              {messages.map((m) => (
                <div key={m.id} className="border border-border rounded-sm p-2 text-sm">
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>{m.channel} · {m.direction === "outgoing" ? "исходящее" : "входящее"}</span>
                    <span>{fmtDate(m.at)}</span>
                  </div>
                  <div className="mt-1 whitespace-pre-wrap">{m.text}</div>
                  <div className="mt-1 text-xs">
                    {m.delivery_status} {m.error && <span className="text-destructive">· {m.error}</span>}
                    {m.admin && <span className="text-muted-foreground"> · {m.admin}</span>}
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="changes" className="mt-3">
            {changes.length === 0 && <div className="text-sm text-muted-foreground">Изменений нет</div>}
            <div className="space-y-1">
              {changes.map((c) => (
                <div key={c.id} className="text-sm flex justify-between border-b border-border py-1">
                  <span>{c.description}</span>
                  <span className="text-xs text-muted-foreground">{fmtDate(c.at)}</span>
                </div>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="actions" className="space-y-4 mt-3">
            <div>
              <Label className="text-xs">Изменить статус</Label>
              <Select value={org.status} onValueChange={changeStatus}>
                <SelectTrigger className="h-8 mt-1" data-testid="status-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {statuses.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>

            <div>
              <Label className="text-xs">Комментарий</Label>
              <Textarea value={comment} onChange={(e) => setComment(e.target.value)} className="mt-1" data-testid="comment-input" />
              <Button size="sm" className="h-8 mt-1" onClick={saveComment} data-testid="save-comment-btn">Сохранить комментарий</Button>
            </div>

            <div>
              <Label className="text-xs">Следующее действие (дата)</Label>
              <div className="flex gap-2 mt-1">
                <Input type="date" value={nextAction?.slice(0, 10) || ""} onChange={(e) => setNextAction(e.target.value)} className="h-8" data-testid="next-action-input" />
                <Button size="sm" className="h-8" onClick={saveNextAction}>Назначить</Button>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <Dialog>
                <DialogTrigger asChild>
                  <Button size="sm" variant="outline" className="h-8" data-testid="send-email-btn"><Mail size={14} className="mr-1" />Отправить email</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader><DialogTitle>Отправить email — {org.name}</DialogTitle></DialogHeader>
                  <Input placeholder="Тема" value={emailSubject} onChange={(e) => setEmailSubject(e.target.value)} data-testid="email-subject" />
                  <Textarea placeholder="Текст письма" value={emailText} onChange={(e) => setEmailText(e.target.value)} data-testid="email-text" />
                  <DialogFooter>
                    <Button onClick={sendEmail} data-testid="confirm-send-email">Отправить</Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

              {org.source_url && (
                <Button size="sm" variant="outline" className="h-8" onClick={() => window.open(org.source_url, "_blank")}>
                  <ExternalLink size={14} className="mr-1" />Источник
                </Button>
              )}

              <Button size="sm" variant="outline" className="h-8" onClick={archive} data-testid="archive-btn">
                <Archive size={14} className="mr-1" />Архивировать
              </Button>

              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button size="sm" variant="destructive" className="h-8" data-testid="dnc-btn"><Ban size={14} className="mr-1" />Не связываться</Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Отметить «Не связываться»?</AlertDialogTitle>
                    <AlertDialogDescription>Ожидающие задачи будут отменены, новые заблокированы. Статус сохранится при повторном импорте.</AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Отмена</AlertDialogCancel>
                    <AlertDialogAction onClick={markDnc} data-testid="confirm-dnc">Подтвердить</AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}
