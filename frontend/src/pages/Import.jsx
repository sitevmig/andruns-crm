import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, apiError } from "@/lib/api";
import { fmtDate } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const CRM_FIELDS = [
  { key: "external_id", label: "Внешний ID" },
  { key: "name", label: "Наименование *" },
  { key: "category", label: "Категория" },
  { key: "city", label: "Город" },
  { key: "address", label: "Адрес" },
  { key: "phone", label: "Телефон" },
  { key: "email", label: "Email" },
  { key: "telegram", label: "Telegram" },
  { key: "source_url", label: "Ссылка / источник" },
  { key: "comment", label: "Комментарий" },
];
const NONE = "__none__";

export default function Import() {
  const [step, setStep] = useState(1);
  const [uploadData, setUploadData] = useState(null);
  const [mapping, setMapping] = useState({});
  const [analysis, setAnalysis] = useState(null);
  const [report, setReport] = useState(null);
  const [importId, setImportId] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);

  const loadHistory = () => api.get("/import/history").then((r) => setHistory(r.data));
  useEffect(() => { loadHistory(); }, []);

  const onFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setLoading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const { data } = await api.post("/import/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setUploadData(data);
      setImportId(data.import_id);
      setMapping(data.suggested_mapping || {});
      setStep(2);
    } catch (err) { toast.error(apiError(err)); }
    finally { setLoading(false); }
  };

  const analyze = async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/import/analyze", { import_id: importId, mapping });
      setAnalysis(data);
      setStep(3);
    } catch (err) { toast.error(apiError(err)); }
    finally { setLoading(false); }
  };

  const confirm = async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/import/confirm", { import_id: importId });
      setReport(data.report);
      setStep(4);
      loadHistory();
      toast.success("Импорт завершён");
    } catch (err) { toast.error(apiError(err)); }
    finally { setLoading(false); }
  };

  const reset = () => { setStep(1); setUploadData(null); setMapping({}); setAnalysis(null); setReport(null); setImportId(null); };

  const downloadReport = async (id) => {
    const res = await api.get(`/import/${id}/report`, { responseType: "blob" });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a"); a.href = url; a.download = `import_report_${id}.xlsx`; a.click();
  };

  return (
    <div className="space-y-4 max-w-4xl" data-testid="import-page">
      <h1 className="text-lg font-semibold tracking-tight">Импорт базы</h1>

      <div className="flex gap-2 text-xs">
        {["Файл", "Сопоставление", "Проверка", "Отчёт"].map((s, i) => (
          <div key={s} className={`px-2 py-1 rounded-sm ${step === i + 1 ? "bg-primary text-white" : "bg-zinc-100 text-muted-foreground"}`}>{i + 1}. {s}</div>
        ))}
      </div>

      {step === 1 && (
        <Card className="p-6 rounded-sm border shadow-none text-center">
          <p className="text-sm text-muted-foreground mb-3">Выберите файл .xlsx, .xls или .csv. Импорт не удаляет существующие записи.</p>
          <input type="file" accept=".xlsx,.xls,.csv" onChange={onFile} data-testid="import-file-input" className="block mx-auto" />
          {loading && <p className="mt-2 text-sm">Загрузка…</p>}
        </Card>
      )}

      {step === 2 && uploadData && (
        <Card className="p-4 rounded-sm border shadow-none space-y-3">
          <div className="text-sm">Строк в файле: <b>{uploadData.row_count}</b></div>
          <div className="overflow-auto border border-border rounded-sm">
            <table className="crm-table w-full text-xs">
              <thead><tr>{uploadData.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>
                {uploadData.sample.map((row, i) => (
                  <tr key={i}>{uploadData.columns.map((c) => <td key={c} className="max-w-[140px] truncate">{row[c]}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-sm font-medium">Сопоставление столбцов</div>
          <div className="grid grid-cols-2 gap-2">
            {CRM_FIELDS.map((f) => (
              <div key={f.key} className="flex items-center gap-2">
                <span className="w-40 text-sm">{f.label}</span>
                <Select value={mapping[f.key] || NONE} onValueChange={(v) => setMapping({ ...mapping, [f.key]: v === NONE ? undefined : v })}>
                  <SelectTrigger className="h-8" data-testid={`map-${f.key}`}><SelectValue placeholder="—" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NONE}>— не сопоставлять —</SelectItem>
                    {uploadData.columns.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={analyze} disabled={loading} data-testid="analyze-btn">Проверить</Button>
            <Button size="sm" variant="outline" onClick={reset}>Отмена</Button>
          </div>
        </Card>
      )}

      {step === 3 && analysis && (
        <Card className="p-4 rounded-sm border shadow-none space-y-3">
          <div className="grid grid-cols-4 gap-3">
            <Stat label="Новых" value={analysis.counts.new} color="text-emerald-600" testid="count-new" />
            <Stat label="Обновляемых" value={analysis.counts.update} color="text-blue-600" testid="count-update" />
            <Stat label="Возможных дублей" value={analysis.counts.duplicate} color="text-purple-600" testid="count-duplicate" />
            <Stat label="Ошибок" value={analysis.counts.error} color="text-rose-600" testid="count-error" />
          </div>
          <div className="max-h-64 overflow-auto border border-border rounded-sm">
            <table className="crm-table w-full text-xs">
              <thead><tr><th>Строка</th><th>Организация</th><th>Действие</th><th>Примечание</th></tr></thead>
              <tbody>
                {analysis.results.map((r, i) => (
                  <tr key={i}>
                    <td>{r.row}</td><td>{r.name || "—"}</td>
                    <td>{{ new: "Новая", update: "Обновление", duplicate: "Дубль", error: "Ошибка" }[r.action]}</td>
                    <td className="text-muted-foreground">{r.errors ? r.errors.join(", ") : r.dnc ? "Защита «Не связываться»" : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={confirm} disabled={loading} data-testid="confirm-import-btn">Подтвердить импорт</Button>
            <Button size="sm" variant="outline" onClick={() => setStep(2)}>Назад</Button>
          </div>
        </Card>
      )}

      {step === 4 && report && (
        <Card className="p-4 rounded-sm border shadow-none space-y-3" data-testid="import-report">
          <div className="text-sm font-medium">Импорт завершён</div>
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Добавлено" value={report.new} color="text-emerald-600" />
            <Stat label="Обновлено" value={report.updated} color="text-blue-600" />
            <Stat label="На проверку дублей" value={report.duplicates} color="text-purple-600" />
            <Stat label="Ошибок" value={report.errors} color="text-rose-600" />
            <Stat label="Защита «Не связываться»" value={report.dnc_protected} color="text-red-600" />
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => downloadReport(importId)} data-testid="download-report-btn">Скачать отчёт (Excel)</Button>
            <Button size="sm" variant="outline" onClick={reset}>Новый импорт</Button>
          </div>
        </Card>
      )}

      <Card className="p-4 rounded-sm border shadow-none">
        <div className="text-sm font-medium mb-2">История импортов</div>
        <table className="crm-table w-full text-xs">
          <thead><tr><th>Файл</th><th>Строк</th><th>Статус</th><th>Дата</th><th>Отчёт</th></tr></thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.id}>
                <td>{h.filename}</td><td>{h.row_count}</td><td>{h.status}</td><td>{fmtDate(h.created_at)}</td>
                <td>{h.status === "done" && <Button size="sm" variant="link" className="h-6 p-0" onClick={() => downloadReport(h.id)}>Скачать</Button>}</td>
              </tr>
            ))}
            {history.length === 0 && <tr><td colSpan={5} className="text-center text-muted-foreground py-3">Пусто</td></tr>}
          </tbody>
        </table>
      </Card>
    </div>
  );
}

function Stat({ label, value, color, testid }) {
  return (
    <div className="border border-border rounded-sm p-3 text-center" data-testid={testid}>
      <div className={`text-2xl font-semibold ${color}`}>{value}</div>
      <div className="text-xs text-muted-foreground mt-1">{label}</div>
    </div>
  );
}
