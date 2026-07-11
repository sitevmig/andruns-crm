import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import { Copy, Archive, Pencil, FlaskConical } from "lucide-react";

const VARS = ["{organization_name}", "{category}", "{city}", "{contact_name}", "{website_offer}", "{manager_name}"];
const empty = { name: "", channel: "email", subject: "", body: "", signature: "" };

export default function Templates() {
  const [templates, setTemplates] = useState([]);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(empty);
  const [orgs, setOrgs] = useState([]);
  const [testOrg, setTestOrg] = useState("");
  const [preview, setPreview] = useState(null);

  const load = () => api.get("/templates").then((r) => setTemplates(r.data));
  useEffect(() => {
    load();
    api.get("/organizations", { params: { page_size: 100 } }).then((r) => setOrgs(r.data.items));
  }, []);

  const openNew = () => { setEditing("new"); setForm(empty); };
  const openEdit = (t) => { setEditing(t.id); setForm({ name: t.name, channel: t.channel, subject: t.subject || "", body: t.body, signature: t.signature || "" }); };

  const save = async () => {
    try {
      if (editing === "new") await api.post("/templates", form);
      else await api.put(`/templates/${editing}`, form);
      toast.success("Шаблон сохранён"); setEditing(null); load();
    } catch (e) { toast.error(apiError(e)); }
  };
  const copy = async (id) => { await api.post(`/templates/${id}/copy`); toast.success("Скопировано"); load(); };
  const archive = async (id) => { await api.post(`/templates/${id}/archive`); toast.success("Архивировано"); load(); };

  const runPreview = async (tid) => {
    if (!testOrg) { toast.error("Выберите организацию"); return; }
    try { const { data } = await api.post("/templates/preview", { template_id: tid, org_id: testOrg }); setPreview(data); }
    catch (e) { toast.error(apiError(e)); }
  };

  return (
    <div className="space-y-3" data-testid="templates-page">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">Шаблоны сообщений</h1>
        <Button size="sm" className="h-8" onClick={openNew} data-testid="new-template-btn">Создать шаблон</Button>
      </div>

      <div className="grid md:grid-cols-2 gap-3">
        {templates.map((t) => (
          <Card key={t.id} className="p-3 rounded-sm border shadow-none" data-testid={`template-${t.id}`}>
            <div className="flex items-center justify-between">
              <div className="font-medium">{t.name}</div>
              <span className="text-xs bg-zinc-100 rounded-sm px-1.5 py-0.5">{t.channel}</span>
            </div>
            {t.subject && <div className="text-xs text-muted-foreground mt-1">Тема: {t.subject}</div>}
            <div className="text-sm mt-2 whitespace-pre-wrap line-clamp-4 text-zinc-600">{t.body}</div>
            <div className="flex gap-1 mt-2">
              <Button size="sm" variant="outline" className="h-7" onClick={() => openEdit(t)} data-testid={`edit-${t.id}`}><Pencil size={12} className="mr-1" />Изм.</Button>
              <Button size="sm" variant="outline" className="h-7" onClick={() => copy(t.id)}><Copy size={12} className="mr-1" />Копия</Button>
              <Dialog>
                <DialogTrigger asChild><Button size="sm" variant="outline" className="h-7" onClick={() => { setPreview(null); }} data-testid={`test-${t.id}`}><FlaskConical size={12} className="mr-1" />Тест</Button></DialogTrigger>
                <DialogContent>
                  <DialogHeader><DialogTitle>Тест шаблона: {t.name}</DialogTitle></DialogHeader>
                  <Select value={testOrg} onValueChange={setTestOrg}>
                    <SelectTrigger className="h-8" data-testid="test-org-select"><SelectValue placeholder="Организация" /></SelectTrigger>
                    <SelectContent>{orgs.map((o) => <SelectItem key={o.id} value={o.id}>{o.name}</SelectItem>)}</SelectContent>
                  </Select>
                  <Button size="sm" onClick={() => runPreview(t.id)} data-testid="run-preview-btn">Показать предпросмотр</Button>
                  {preview && (
                    <div className="border border-border rounded-sm p-3 text-sm space-y-1" data-testid="preview-result">
                      {preview.subject && <div><b>Тема:</b> {preview.subject}</div>}
                      <div className="whitespace-pre-wrap">{preview.body}</div>
                      {preview.signature && <div className="text-muted-foreground whitespace-pre-wrap">{preview.signature}</div>}
                    </div>
                  )}
                </DialogContent>
              </Dialog>
              <Button size="sm" variant="ghost" className="h-7" onClick={() => archive(t.id)}><Archive size={12} /></Button>
            </div>
          </Card>
        ))}
      </div>

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader><DialogTitle>{editing === "new" ? "Новый шаблон" : "Редактировать шаблон"}</DialogTitle></DialogHeader>
          <div className="space-y-2">
            <div><Label className="text-xs">Название</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="h-8 mt-1" data-testid="tpl-name" /></div>
            <div>
              <Label className="text-xs">Канал</Label>
              <Select value={form.channel} onValueChange={(v) => setForm({ ...form, channel: v })}>
                <SelectTrigger className="h-8 mt-1" data-testid="tpl-channel"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="email">Email</SelectItem><SelectItem value="telegram">Telegram</SelectItem></SelectContent>
              </Select>
            </div>
            {form.channel === "email" && (
              <div><Label className="text-xs">Тема письма</Label><Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} className="h-8 mt-1" data-testid="tpl-subject" /></div>
            )}
            <div><Label className="text-xs">Текст</Label><Textarea rows={5} value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} className="mt-1" data-testid="tpl-body" /></div>
            {form.channel === "email" && (
              <div><Label className="text-xs">Подпись</Label><Input value={form.signature} onChange={(e) => setForm({ ...form, signature: e.target.value })} className="h-8 mt-1" data-testid="tpl-signature" /></div>
            )}
            <div className="text-xs text-muted-foreground">Переменные: {VARS.map((v) => <button key={v} type="button" className="underline mr-1" onClick={() => setForm({ ...form, body: form.body + " " + v })}>{v}</button>)}</div>
          </div>
          <DialogFooter><Button onClick={save} data-testid="save-template-btn">Сохранить</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
