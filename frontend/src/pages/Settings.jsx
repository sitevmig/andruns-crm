import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { fmtDate } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger } from "@/components/ui/dialog";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export default function Settings() {
  const [s, setS] = useState(null);
  const [templates, setTemplates] = useState([]);

  const load = () => api.get("/settings").then((r) => setS(r.data));
  useEffect(() => { load(); api.get("/templates").then((r) => setTemplates(r.data)); }, []);

  const update = async (patch) => {
    try { const { data } = await api.put("/settings", patch); setS(data); toast.success("Сохранено"); }
    catch (e) { toast.error(apiError(e)); }
  };

  if (!s) return <div className="text-muted-foreground">Загрузка…</div>;

  return (
    <div className="space-y-3 max-w-3xl" data-testid="settings-page">
      <h1 className="text-lg font-semibold tracking-tight">Настройки</h1>
      <Tabs defaultValue="general">
        <TabsList className="flex-wrap h-auto">
          <TabsTrigger value="general">Общие</TabsTrigger>
          <TabsTrigger value="sending">Рассылки</TabsTrigger>
          <TabsTrigger value="telegram" data-testid="tab-telegram">Telegram</TabsTrigger>
          <TabsTrigger value="email">Email</TabsTrigger>
          <TabsTrigger value="admins" data-testid="tab-admins">Администраторы</TabsTrigger>
          <TabsTrigger value="security">Безопасность</TabsTrigger>
        </TabsList>

        <TabsContent value="general">
          <Card className="p-4 rounded-sm border shadow-none space-y-3">
            <Field label="Название CRM"><Input value={s.crm_name} onChange={(e) => setS({ ...s, crm_name: e.target.value })} onBlur={() => update({ crm_name: s.crm_name })} className="h-8" data-testid="crm-name" /></Field>
            <Field label="Часовой пояс"><Input value={s.timezone} onChange={(e) => setS({ ...s, timezone: e.target.value })} onBlur={() => update({ timezone: s.timezone })} className="h-8" /></Field>
            <Field label="Формат даты"><Input value={s.date_format} onChange={(e) => setS({ ...s, date_format: e.target.value })} onBlur={() => update({ date_format: s.date_format })} className="h-8" /></Field>
          </Card>
        </TabsContent>

        <TabsContent value="sending">
          <Card className="p-4 rounded-sm border shadow-none space-y-3">
            <Toggle label="Email-рассылка включена" checked={s.email_enabled} onChange={(v) => update({ email_enabled: v })} testid="toggle-email" />
            <Toggle label="Telegram-рассылка включена" checked={s.telegram_enabled} onChange={(v) => update({ telegram_enabled: v })} testid="toggle-telegram" />
            <Field label="Шаблон по умолчанию">
              <Select value={s.default_template_id || ""} onValueChange={(v) => update({ default_template_id: v })}>
                <SelectTrigger className="h-8"><SelectValue placeholder="—" /></SelectTrigger>
                <SelectContent>{templates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent>
              </Select>
            </Field>
            <Field label="Подпись отправителя"><Input value={s.signature} onChange={(e) => setS({ ...s, signature: e.target.value })} onBlur={() => update({ signature: s.signature })} className="h-8" /></Field>
            <Field label="Макс. попыток при ошибке"><Input type="number" value={s.retry_max_attempts} onChange={(e) => setS({ ...s, retry_max_attempts: +e.target.value })} onBlur={() => update({ retry_max_attempts: s.retry_max_attempts })} className="h-8 w-24" /></Field>
          </Card>
        </TabsContent>

        <TabsContent value="telegram"><TelegramSettings /></TabsContent>

        <TabsContent value="email">
          <Card className="p-4 rounded-sm border shadow-none space-y-3">
            <Field label="Провайдер"><Input value="resend" readOnly disabled className="h-8" data-testid="email-provider" /></Field>
            <Field label="Имя отправителя"><Input value={s.sender_name} onChange={(e) => setS({ ...s, sender_name: e.target.value })} onBlur={() => update({ sender_name: s.sender_name })} className="h-8" /></Field>
            <Field label="Адрес отправителя"><Input value={s.sender_email} onChange={(e) => setS({ ...s, sender_email: e.target.value })} onBlur={() => update({ sender_email: s.sender_email })} className="h-8" /></Field>
            <Field label="Reply-to"><Input value={s.reply_to} onChange={(e) => setS({ ...s, reply_to: e.target.value })} onBlur={() => update({ reply_to: s.reply_to })} className="h-8" /></Field>
            <EmailTest />
          </Card>
        </TabsContent>

        <TabsContent value="admins"><AdminsSettings /></TabsContent>
        <TabsContent value="security"><SecuritySettings /></TabsContent>
      </Tabs>
    </div>
  );
}

const Field = ({ label, children }) => (
  <div><Label className="text-xs">{label}</Label><div className="mt-1">{children}</div></div>
);
const Toggle = ({ label, checked, onChange, testid }) => (
  <div className="flex items-center justify-between border-b border-border py-2">
    <span className="text-sm">{label}</span>
    <Switch checked={checked} onCheckedChange={onChange} data-testid={testid} />
  </div>
);

function TelegramSettings() {
  const [st, setSt] = useState(null);
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [testTo, setTestTo] = useState("");
  const [busy, setBusy] = useState(false);
  const load = () => api.get("/telegram/status").then((r) => setSt(r.data));
  useEffect(() => { load(); }, []);

  const startLogin = async () => {
    setBusy(true);
    try { await api.post("/telegram/login/start", { phone }); setCodeSent(true); toast.success("Код отправлен в Telegram"); }
    catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };
  const completeLogin = async () => {
    setBusy(true);
    try { await api.post("/telegram/login/complete", { code, password: password || null }); toast.success("Telegram подключён"); setCodeSent(false); setCode(""); setPassword(""); load(); }
    catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };
  const disconnect = async () => { await api.post("/telegram/disconnect"); toast.success("Отключено"); load(); };
  const check = async () => { try { const { data } = await api.post("/telegram/check"); toast.success(data.status); } catch (e) { toast.error(apiError(e)); } };
  const test = async () => {
    if (!testTo) { toast.error("Укажите получателя (@username)"); return; }
    setBusy(true);
    try { const { data } = await api.post("/telegram/test", { to: testTo }); toast.success(`Отправлено, id ${data.message_id}`); }
    catch (e) { toast.error(apiError(e)); }
    finally { setBusy(false); }
  };
  const checkReplies = async () => {
    try { const { data } = await api.post("/telegram/check-replies"); toast.success(`Новых ответов: ${data.new_replies}`); }
    catch (e) { toast.error(apiError(e)); }
  };

  if (!st) return null;
  return (
    <Card className="p-4 rounded-sm border shadow-none space-y-3">
      {!st.api_configured && (
        <div className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-sm p-2">
          На backend не заданы TELEGRAM_API_ID и TELEGRAM_API_HASH. Получите их на my.telegram.org и добавьте в переменные окружения Render.
        </div>
      )}
      <div className="text-sm">Состояние: <b className={st.connected ? "text-emerald-600" : "text-red-600"}>{st.status}</b></div>

      {!st.connected ? (
        !codeSent ? (
          <div className="flex gap-2 items-end">
            <div className="flex-1"><Label className="text-xs">Номер рабочего Telegram-аккаунта</Label>
              <Input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+7…" className="h-8 mt-1" data-testid="tg-phone" /></div>
            <Button size="sm" className="h-8" onClick={startLogin} disabled={busy || !st.api_configured} data-testid="tg-start-btn">Отправить код</Button>
          </div>
        ) : (
          <div className="space-y-2">
            <div><Label className="text-xs">Код из Telegram</Label>
              <Input value={code} onChange={(e) => setCode(e.target.value)} className="h-8 mt-1" data-testid="tg-code" /></div>
            <div><Label className="text-xs">Пароль 2FA (если включён)</Label>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="h-8 mt-1" data-testid="tg-2fa" /></div>
            <div className="flex gap-2">
              <Button size="sm" className="h-8" onClick={completeLogin} disabled={busy} data-testid="tg-complete-btn">Подтвердить</Button>
              <Button size="sm" variant="ghost" className="h-8" onClick={() => setCodeSent(false)}>Назад</Button>
            </div>
          </div>
        )
      ) : (
        <div className="space-y-2">
          <div className="flex gap-2 items-end">
            <div className="flex-1"><Label className="text-xs">Тест: отправить сообщение получателю</Label>
              <Input value={testTo} onChange={(e) => setTestTo(e.target.value)} placeholder="@username" className="h-8 mt-1" data-testid="tg-test-to" /></div>
            <Button size="sm" variant="outline" className="h-8" onClick={test} disabled={busy} data-testid="tg-test-btn">Отправить тест</Button>
          </div>
          <div className="flex gap-2">
            <Button size="sm" variant="outline" className="h-8" onClick={check} data-testid="tg-check-btn">Проверить соединение</Button>
            <Button size="sm" variant="outline" className="h-8" onClick={checkReplies} data-testid="tg-check-replies-btn">Проверить ответы</Button>
            <AlertDialog>
              <AlertDialogTrigger asChild><Button size="sm" variant="destructive" className="h-8" data-testid="tg-disconnect-btn">Отключить</Button></AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader><AlertDialogTitle>Отключить Telegram?</AlertDialogTitle>
                  <AlertDialogDescription>Зашифрованная сессия будет удалена. Отправка в Telegram остановится.</AlertDialogDescription></AlertDialogHeader>
                <AlertDialogFooter><AlertDialogCancel>Отмена</AlertDialogCancel><AlertDialogAction onClick={disconnect}>Отключить</AlertDialogAction></AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        </div>
      )}

      {st.errors?.length > 0 && (
        <div className="text-xs border-t border-border pt-2">
          <div className="font-medium mb-1">Журнал ошибок Telegram</div>
          {st.errors.slice(0, 5).map((e, i) => (
            <div key={i} className="text-destructive truncate">{e.action}: {e.error}</div>
          ))}
        </div>
      )}
    </Card>
  );
}

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function EmailTest() {
  const [to, setTo] = useState("");
  const send = async () => {
    const trimmed = to.trim();
    if (!EMAIL_RE.test(trimmed)) { toast.error("Укажите корректный email в формате email@example.com"); return; }
    try { const { data } = await api.post("/email/test", { to: trimmed }); toast.success(`Письмо отправлено, id ${data.message_id}`); }
    catch (e) { toast.error(apiError(e)); }
  };
  return (
    <div className="flex gap-2 items-end pt-2 border-t border-border">
      <div className="flex-1"><Label className="text-xs">Тестовое письмо на адрес</Label><Input value={to} onChange={(e) => setTo(e.target.value)} className="h-8 mt-1" data-testid="email-test-to" /></div>
      <Button size="sm" className="h-8" onClick={send} data-testid="email-test-btn">Отправить тест</Button>
    </div>
  );
}

function AdminsSettings() {
  const [admins, setAdmins] = useState([]);
  const [form, setForm] = useState({ email: "", name: "", password: "" });
  const load = () => api.get("/admins").then((r) => setAdmins(r.data));
  useEffect(() => { load(); }, []);

  const create = async () => {
    try { await api.post("/admins", form); toast.success("Администратор добавлен"); setForm({ email: "", name: "", password: "" }); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const remove = async (id) => {
    try { await api.delete(`/admins/${id}`); toast.success("Удалён"); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const resetPw = async (id) => {
    const pw = prompt("Новый пароль (мин. 6 символов):");
    if (!pw) return;
    try { await api.post(`/admins/${id}/reset-password`, { password: pw }); toast.success("Пароль сброшен"); }
    catch (e) { toast.error(apiError(e)); }
  };
  const terminate = async (id) => { await api.post(`/admins/${id}/terminate-sessions`); toast.success("Сессии завершены"); };

  return (
    <Card className="p-4 rounded-sm border shadow-none space-y-3">
      <table className="crm-table w-full text-sm">
        <thead><tr><th>Имя</th><th>Email</th><th>Создан</th><th>Действия</th></tr></thead>
        <tbody>
          {admins.map((a) => (
            <tr key={a.id} data-testid={`admin-${a.id}`}>
              <td>{a.name}</td><td>{a.email}</td><td>{fmtDate(a.created_at)}</td>
              <td className="flex gap-2">
                <Button size="sm" variant="link" className="h-6 p-0" onClick={() => resetPw(a.id)}>Сброс пароля</Button>
                <Button size="sm" variant="link" className="h-6 p-0" onClick={() => terminate(a.id)}>Завершить сессии</Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild><Button size="sm" variant="link" className="h-6 p-0 text-destructive" data-testid={`delete-admin-${a.id}`}>Удалить</Button></AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader><AlertDialogTitle>Удалить администратора?</AlertDialogTitle>
                      <AlertDialogDescription>{a.email} потеряет доступ к системе.</AlertDialogDescription></AlertDialogHeader>
                    <AlertDialogFooter><AlertDialogCancel>Отмена</AlertDialogCancel><AlertDialogAction onClick={() => remove(a.id)}>Удалить</AlertDialogAction></AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Dialog>
        <DialogTrigger asChild><Button size="sm" className="h-8" data-testid="add-admin-btn">Добавить администратора</Button></DialogTrigger>
        <DialogContent>
          <DialogHeader><DialogTitle>Новый администратор</DialogTitle></DialogHeader>
          <Input placeholder="Имя" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="admin-name" />
          <Input placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="admin-email" />
          <Input placeholder="Пароль" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="admin-password" />
          <DialogFooter><Button onClick={create} data-testid="save-admin-btn">Создать</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function SecuritySettings() {
  const [sessions, setSessions] = useState([]);
  const [pw, setPw] = useState({ old_password: "", new_password: "" });
  const load = () => api.get("/auth/sessions").then((r) => setSessions(r.data));
  useEffect(() => { load(); }, []);

  const change = async () => {
    try { await api.post("/auth/change-password", pw); toast.success("Пароль изменён"); setPw({ old_password: "", new_password: "" }); }
    catch (e) { toast.error(apiError(e)); }
  };
  const logoutAll = async () => { await api.post("/auth/logout-all"); toast.success("Все сессии завершены"); window.location.href = "/login"; };
  const killSession = async (id) => { await api.delete(`/auth/sessions/${id}`); load(); };

  return (
    <Card className="p-4 rounded-sm border shadow-none space-y-4">
      <div>
        <div className="text-sm font-medium mb-2">Смена пароля</div>
        <div className="flex gap-2 items-end">
          <Input placeholder="Текущий" type="password" value={pw.old_password} onChange={(e) => setPw({ ...pw, old_password: e.target.value })} className="h-8" data-testid="old-password" />
          <Input placeholder="Новый" type="password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} className="h-8" data-testid="new-password" />
          <Button size="sm" className="h-8" onClick={change} data-testid="change-password-btn">Изменить</Button>
        </div>
      </div>
      <div>
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm font-medium">Активные сессии</div>
          <Button size="sm" variant="destructive" className="h-8" onClick={logoutAll} data-testid="logout-all-btn">Завершить все</Button>
        </div>
        <table className="crm-table w-full text-xs">
          <thead><tr><th>IP</th><th>Устройство</th><th>Активность</th><th></th></tr></thead>
          <tbody>
            {sessions.map((se) => (
              <tr key={se.id}>
                <td>{se.ip}</td><td className="max-w-[280px] truncate">{se.user_agent}</td><td>{fmtDate(se.last_seen)}</td>
                <td><Button size="sm" variant="link" className="h-6 p-0" onClick={() => killSession(se.id)}>Завершить</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
