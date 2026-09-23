import { useEffect, useState, useCallback, useRef } from "react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { StatusBadge, fmtDate } from "@/components/StatusBadge";
import OrgDrawer from "@/components/OrgDrawer";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger,
} from "@/components/ui/dialog";
import { Search, Download, Send, Square } from "lucide-react";

const ALL = "__all__";
const CAMPAIGN_MAX = 10;

export default function Organizations() {
  const [meta, setMeta] = useState({ statuses: [], categories: [], cities: [], saved_filters: [] });
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState(new Set());
  const [openId, setOpenId] = useState(null);
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ search: "", status: "", category: "", city: "", has_email: "", has_telegram: "", do_not_contact: "" });
  const [sortBy, setSortBy] = useState("updated_at");
  const [templates, setTemplates] = useState([]);
  const [campaignTpl, setCampaignTpl] = useState("");
  const [bulkStatus, setBulkStatus] = useState("");
  const [campaign, setCampaign] = useState({ running: false, total: 0, sent: 0, errors: 0 });

  useEffect(() => {
    api.get("/organizations/meta").then((r) => setMeta(r.data));
    api.get("/templates", { params: { channel: "email" } }).then((r) => setTemplates(r.data));
  }, []);

  const load = useCallback(() => {
    const params = { ...filters, sort_by: sortBy, sort_dir: -1, page, page_size: 50 };
    Object.keys(params).forEach((k) => { if (params[k] === "" || params[k] == null) delete params[k]; });
    api.get("/organizations", { params }).then((r) => { setItems(r.data.items); setTotal(r.data.total); });
  }, [filters, sortBy, page]);

  useEffect(() => { load(); }, [load]);

  const wasRunning = useRef(false);
  const refreshCampaign = useCallback(() => {
    api.get("/queue/campaign-status").then((r) => {
      setCampaign(r.data);
      if (wasRunning.current && !r.data.running) load(); // campaign just finished
      wasRunning.current = r.data.running;
    }).catch(() => {});
  }, [load]);

  useEffect(() => {
    refreshCampaign();
    const t = setInterval(refreshCampaign, 5000);
    return () => clearInterval(t);
  }, [refreshCampaign]);

  const applySaved = (sf) => {
    setFilters({ search: "", status: "", category: "", city: "", has_email: "", has_telegram: "", do_not_contact: "", ...sf.filters });
    setPage(1);
  };

  const toggleAll = () => {
    if (selected.size === items.length) { setSelected(new Set()); return; }
    if (items.length > CAMPAIGN_MAX) {
      toast.error(`За один запуск рассылки можно выбрать не более ${CAMPAIGN_MAX} клиентов`);
      setSelected(new Set(items.slice(0, CAMPAIGN_MAX).map((i) => i.id)));
      return;
    }
    setSelected(new Set(items.map((i) => i.id)));
  };
  const toggle = (id) => {
    const s = new Set(selected);
    if (s.has(id)) { s.delete(id); setSelected(s); return; }
    if (s.size >= CAMPAIGN_MAX) {
      toast.error(`За один запуск рассылки можно выбрать не более ${CAMPAIGN_MAX} клиентов`);
      return;
    }
    s.add(id);
    setSelected(s);
  };

  const ids = [...selected];

  const doBulkStatus = async () => {
    if (!bulkStatus || ids.length === 0) return;
    try { await api.post("/organizations/bulk/status", { ids, status: bulkStatus }); toast.success("Статус обновлён"); setSelected(new Set()); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const doArchive = async () => {
    try { await api.post("/organizations/bulk/archive", { ids }); toast.success("Архивировано"); setSelected(new Set()); load(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const doStartCampaign = async () => {
    if (!campaignTpl) { toast.error("Выберите шаблон"); return; }
    try {
      const { data } = await api.post("/queue/start-campaign", { org_ids: ids, template_id: campaignTpl });
      toast.success(`Рассылка запущена: ${data.started}${data.skipped ? `, пропущено: ${data.skipped}` : ""}`);
      setSelected(new Set());
      refreshCampaign();
    } catch (e) { toast.error(apiError(e)); }
  };
  const doStopCampaign = async () => {
    try { await api.post("/queue/stop-campaign"); toast.success("Рассылка остановлена"); refreshCampaign(); }
    catch (e) { toast.error(apiError(e)); }
  };
  const doRemoveQueue = async () => {
    try { await api.post("/queue/remove", { ids }); toast.success("Исключено из очереди"); }
    catch (e) { toast.error(apiError(e)); }
  };
  const exportSelected = async () => {
    // export filtered current view
    const res = await api.post("/export/filtered", { filters }, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a"); a.href = url; a.download = "crm_filtered.xlsx"; a.click();
  };

  return (
    <div className="space-y-3" data-testid="organizations-page">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">Клиенты <span className="text-muted-foreground font-normal">({total})</span></h1>
        <Button size="sm" variant="outline" className="h-8" onClick={exportSelected} data-testid="export-view-btn"><Download size={14} className="mr-1" />Экспорт вида</Button>
      </div>

      {/* Saved filters */}
      <div className="flex flex-wrap gap-1">
        {meta.saved_filters
          .filter((sf) => !["ready_email", "ready_telegram", "interested", "errors"].includes(sf.key))
          .map((sf) => (
          <Button key={sf.key} size="sm" variant="secondary" className="h-7 text-xs" onClick={() => applySaved(sf)} data-testid={`saved-filter-${sf.key}`}>
            {sf.label}
          </Button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-2 items-center bg-white border border-border rounded-sm p-2">
        <div className="relative">
          <Search size={14} className="absolute left-2 top-2 text-muted-foreground" />
          <Input placeholder="Поиск…" value={filters.search} onChange={(e) => setFilters({ ...filters, search: e.target.value })} className="h-8 pl-7 w-56" data-testid="search-input" />
        </div>
        <FilterSelect value={filters.status} onChange={(v) => setFilters({ ...filters, status: v })} options={meta.statuses} placeholder="Статус" testid="filter-status" />
        <FilterSelect value={filters.category} onChange={(v) => setFilters({ ...filters, category: v })} options={meta.categories} placeholder="Категория" testid="filter-category" />
        <FilterSelect value={filters.city} onChange={(v) => setFilters({ ...filters, city: v })} options={meta.cities} placeholder="Город" testid="filter-city" />
        <FilterSelect value={filters.has_email} onChange={(v) => setFilters({ ...filters, has_email: v })} options={["yes", "no"]} labels={{ yes: "Есть email", no: "Нет email" }} placeholder="Email" testid="filter-email" />
        <FilterSelect value={filters.has_telegram} onChange={(v) => setFilters({ ...filters, has_telegram: v })} options={["yes", "no"]} labels={{ yes: "Есть TG", no: "Нет TG" }} placeholder="Telegram" testid="filter-tg" />
        <FilterSelect value={filters.do_not_contact} onChange={(v) => setFilters({ ...filters, do_not_contact: v })} options={["yes", "no"]} labels={{ yes: "Не связываться", no: "Можно писать" }} placeholder="ЧС" testid="filter-dnc" />
        <Button size="sm" variant="ghost" className="h-8" onClick={() => setFilters({ search: "", status: "", category: "", city: "", has_email: "", has_telegram: "", do_not_contact: "" })}>Сброс</Button>
      </div>

      {/* Active campaign status */}
      {campaign.running && (
        <div className="flex flex-wrap items-center gap-3 bg-emerald-50 border border-emerald-200 rounded-sm p-2" data-testid="campaign-banner">
          <span className="text-sm font-medium text-emerald-800">
            Рассылка выполняется: отправлено {campaign.sent} из {campaign.total}
            {campaign.errors > 0 && <span className="text-destructive"> · ошибок: {campaign.errors}</span>}
          </span>
          <Button size="sm" variant="destructive" className="h-8" onClick={doStopCampaign} data-testid="stop-campaign-btn">
            <Square size={14} className="mr-1" />Остановить рассылку
          </Button>
        </div>
      )}

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 bg-primary/5 border border-primary/20 rounded-sm p-2" data-testid="bulk-bar">
          <span className="text-sm font-medium">Выбрано: {selected.size} / {CAMPAIGN_MAX}</span>
          <Select value={bulkStatus} onValueChange={setBulkStatus}>
            <SelectTrigger className="h-8 w-44" data-testid="bulk-status-select"><SelectValue placeholder="Изменить статус" /></SelectTrigger>
            <SelectContent>{meta.statuses.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
          </Select>
          <Button size="sm" className="h-8" onClick={doBulkStatus} data-testid="apply-bulk-status">Применить</Button>

          <Dialog>
            <DialogTrigger asChild>
              <Button size="sm" className="h-8" disabled={campaign.running} data-testid="start-campaign-btn">
                <Send size={14} className="mr-1" />Начать рассылку
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle>Начать рассылку — {selected.size} клиентов</DialogTitle></DialogHeader>
              <div className="space-y-2">
                <Select value={campaignTpl} onValueChange={setCampaignTpl}>
                  <SelectTrigger className="h-8" data-testid="campaign-template"><SelectValue placeholder="Шаблон из раздела «Шаблоны»" /></SelectTrigger>
                  <SelectContent>{templates.map((t) => <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>)}</SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Письма уйдут по одному с интервалом 3 минуты между отправками. Остановить можно в любой момент.
                </p>
              </div>
              <DialogFooter><Button onClick={doStartCampaign} data-testid="confirm-start-campaign">Начать рассылку</Button></DialogFooter>
            </DialogContent>
          </Dialog>

          <Button size="sm" variant="outline" className="h-8" onClick={doRemoveQueue} data-testid="bulk-remove-queue">Исключить из очереди</Button>
          <Button size="sm" variant="outline" className="h-8" onClick={doArchive} data-testid="bulk-archive">Архивировать</Button>
        </div>
      )}

      {/* Table */}
      <div className="bg-white border border-border rounded-sm overflow-auto">
        <table className="crm-table w-full text-sm border-collapse">
          <thead>
            <tr>
              <th className="w-8"><Checkbox checked={selected.size > 0 && selected.size === items.length} onCheckedChange={toggleAll} data-testid="select-all" /></th>
              <th className="cursor-pointer" onClick={() => setSortBy("name")}>Клиент</th>
              <th>Категория</th>
              <th>Город</th>
              <th>Телефон</th>
              <th>Email</th>
              <th>Telegram</th>
              <th>Статус</th>
              <th>Менеджер</th>
              <th className="cursor-pointer" onClick={() => setSortBy("last_message_at")}>Последнее сообщение</th>
              <th>Комментарий</th>
            </tr>
          </thead>
          <tbody>
            {items.map((o) => (
              <tr key={o.id} className="cursor-pointer" data-testid={`org-row-${o.id}`}>
                <td onClick={(e) => e.stopPropagation()}><Checkbox checked={selected.has(o.id)} onCheckedChange={() => toggle(o.id)} data-testid={`select-${o.id}`} /></td>
                <td className="font-medium text-primary" onClick={() => setOpenId(o.id)} data-testid={`org-name-${o.id}`}>{o.name}</td>
                <td onClick={() => setOpenId(o.id)}>{o.category || "—"}</td>
                <td onClick={() => setOpenId(o.id)}>{o.city || "—"}</td>
                <td onClick={() => setOpenId(o.id)}>{o.phone || "—"}</td>
                <td onClick={() => setOpenId(o.id)}>{o.email || "—"}</td>
                <td onClick={() => setOpenId(o.id)}>{o.telegram || "—"}</td>
                <td onClick={() => setOpenId(o.id)}><StatusBadge status={o.status} /></td>
                <td onClick={() => setOpenId(o.id)}>{o.assigned_manager_name || "—"}</td>
                <td onClick={() => setOpenId(o.id)}>{fmtDate(o.last_message_at)}</td>
                <td onClick={() => setOpenId(o.id)} className="max-w-[160px] truncate">{o.comment || "—"}</td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={11} className="text-center text-muted-foreground py-6">Нет данных</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">Стр. {page} · всего {total}</span>
        <div className="flex gap-2">
          <Button size="sm" variant="outline" className="h-8" disabled={page <= 1} onClick={() => setPage(page - 1)}>Назад</Button>
          <Button size="sm" variant="outline" className="h-8" disabled={page * 50 >= total} onClick={() => setPage(page + 1)}>Вперёд</Button>
        </div>
      </div>

      {openId && <OrgDrawer orgId={openId} statuses={meta.statuses} onClose={() => setOpenId(null)} onChanged={load} />}
    </div>
  );
}

function FilterSelect({ value, onChange, options, labels = {}, placeholder, testid }) {
  return (
    <Select value={value || ALL} onValueChange={(v) => onChange(v === ALL ? "" : v)}>
      <SelectTrigger className="h-8 w-36" data-testid={testid}><SelectValue placeholder={placeholder} /></SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{placeholder}: все</SelectItem>
        {options.map((o) => <SelectItem key={o} value={o}>{labels[o] || o}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}
