"""
CRM Cold Sales — full backend test suite (pytest)

Covers: auth (JWT + brute force), dashboard, organizations (filters/meta/status/dnc/bulk),
imports (upload/analyze/confirm + dedup + DNC preservation + phone normalization),
templates (CRUD + preview + empty rejection), queue (enqueue/process/stop/resume/clear/retry),
replies (simulate/read), duplicates (list/dismiss), exports (xlsx), backups (create/list/download),
settings (GET/PUT), integrations (telegram/email mock), admins CRUD.
"""

import io
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback for pytest running in repo
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                break

API = BASE_URL + "/api"

ADMIN_EMAIL = "admin@crm.ru"
ADMIN_PASSWORD = "Admin123!"


# ---------- fixtures ----------

@pytest.fixture(scope="session")
def token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data and "user" in data
    return data["token"]


@pytest.fixture(scope="session")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ==============================================================
# AUTH
# ==============================================================
class TestAuth:
    def test_login_ok(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == ADMIN_EMAIL
        assert isinstance(d["token"], str) and len(d["token"]) > 20

    def test_login_second_admin(self):
        r = requests.post(f"{API}/auth/login", json={"email": "manager2@crm.ru", "password": ADMIN_PASSWORD})
        assert r.status_code == 200

    def test_login_bad_password(self):
        # Use a unique email to avoid contaminating brute-force counter for admin
        r = requests.post(f"{API}/auth/login", json={"email": "nonexist_" + uuid.uuid4().hex[:6] + "@crm.ru", "password": "wrong"})
        assert r.status_code == 401

    def test_protected_requires_token(self):
        r = requests.get(f"{API}/dashboard")
        assert r.status_code == 401

    def test_me_with_token(self, auth):
        r = requests.get(f"{API}/auth/me", headers=auth)
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL

    def test_login_journal(self, auth):
        r = requests.get(f"{API}/auth/login-journal", headers=auth)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_brute_force_lockout(self):
        # Note: identifier is (ip:email) and requests are load-balanced across
        # multiple ingress pods, so we need enough attempts to hit each IP 5x.
        email = f"bf_{uuid.uuid4().hex[:8]}@crm.ru"
        codes = []
        for i in range(20):
            r = requests.post(f"{API}/auth/login", json={"email": email, "password": "bad"})
            codes.append(r.status_code)
        assert 429 in codes, f"Expected 429 lockout, got: {codes}"


# ==============================================================
# DASHBOARD
# ==============================================================
class TestDashboard:
    def test_dashboard(self, auth):
        r = requests.get(f"{API}/dashboard", headers=auth)
        assert r.status_code == 200
        d = r.json()
        assert "stats" in d and "funnel" in d
        for k in ("total", "new", "queue_count", "sending_stopped"):
            assert k in d["stats"]
        for k in ("imported", "sent", "replied"):
            assert k in d["funnel"]


# ==============================================================
# ORGANIZATIONS
# ==============================================================
class TestOrganizations:
    def test_meta(self, auth):
        r = requests.get(f"{API}/organizations/meta", headers=auth)
        assert r.status_code == 200
        d = r.json()
        assert "statuses" in d and "categories" in d and "cities" in d
        assert "Не связываться" in d["statuses"]

    def test_list(self, auth):
        r = requests.get(f"{API}/organizations", headers=auth, params={"page": 1, "page_size": 50})
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and "total" in d
        assert d["total"] >= 10  # seeded 10 demos
        # demos not returned as duplicates and don't include _id
        for it in d["items"]:
            assert "id" in it
            assert "_id" not in it

    def test_search_filter(self, auth):
        r = requests.get(f"{API}/organizations", headers=auth, params={"search": "Кофейня"})
        assert r.status_code == 200
        items = r.json()["items"]
        assert any("Кофейня" in i.get("name", "") for i in items)

    def test_filter_dnc(self, auth):
        r = requests.get(f"{API}/organizations", headers=auth, params={"do_not_contact": "yes"})
        assert r.status_code == 200
        for it in r.json()["items"]:
            assert it["do_not_contact"] is True

    def test_status_change_and_persist(self, auth):
        r = requests.get(f"{API}/organizations", headers=auth, params={"search": "Автосервис"})
        oid = r.json()["items"][0]["id"]
        r2 = requests.post(f"{API}/organizations/{oid}/status", headers=auth, json={"status": "В работе"})
        assert r2.status_code == 200
        assert r2.json()["status"] == "В работе"
        # verify persistence
        r3 = requests.get(f"{API}/organizations/{oid}", headers=auth)
        assert r3.json()["status"] == "В работе"
        # revert
        requests.post(f"{API}/organizations/{oid}/status", headers=auth, json={"status": "Готов к отправке"})

    def test_dnc_cancels_queue(self, auth):
        # create org, enqueue, then dnc → queue task cancelled
        create = requests.post(f"{API}/organizations", headers=auth, json={
            "name": "TEST_DNC_" + uuid.uuid4().hex[:6], "email": f"t{uuid.uuid4().hex[:6]}@x.ru",
        })
        assert create.status_code == 200
        oid = create.json()["id"]
        # get any email template
        tpls = requests.get(f"{API}/templates", headers=auth, params={"channel": "email"}).json()
        tpl_id = tpls[0]["id"]
        # global stop so worker doesn't process before we check
        requests.post(f"{API}/queue/stop-all", headers=auth)
        try:
            enq = requests.post(f"{API}/queue/enqueue", headers=auth, json={
                "org_ids": [oid], "channel": "email", "template_id": tpl_id
            })
            assert enq.status_code == 200 and enq.json()["added"] == 1
            # mark DNC (send empty JSON — body is optional)
            dnc = requests.post(f"{API}/organizations/{oid}/dnc", headers=auth, json={"status": "Не связываться", "reason": "тест"})
            assert dnc.status_code == 200
            assert dnc.json()["do_not_contact"] is True
            assert dnc.json()["status"] == "Не связываться"
            # Verify queue task became "Отменено"
            q = requests.get(f"{API}/queue", headers=auth).json()
            org_tasks = [t for t in q if t["org_id"] == oid]
            assert any(t["status"] == "Отменено" for t in org_tasks), f"tasks: {org_tasks}"
        finally:
            requests.post(f"{API}/queue/resume", headers=auth)
            requests.delete(f"{API}/organizations/{oid}", headers=auth)

    def test_bulk_status(self, auth):
        # create two orgs
        ids = []
        for _ in range(2):
            c = requests.post(f"{API}/organizations", headers=auth, json={
                "name": "TEST_BULK_" + uuid.uuid4().hex[:6]
            })
            ids.append(c.json()["id"])
        try:
            r = requests.post(f"{API}/organizations/bulk/status", headers=auth,
                              json={"ids": ids, "status": "Готов к отправке"})
            assert r.status_code == 200
            for i in ids:
                got = requests.get(f"{API}/organizations/{i}", headers=auth).json()
                assert got["status"] == "Готов к отправке"
        finally:
            for i in ids:
                requests.delete(f"{API}/organizations/{i}", headers=auth)


# ==============================================================
# IMPORTS (CSV) + dedup + DNC preservation + phone normalization
# ==============================================================
class TestImports:
    CSV_HEADER = "Название,Категория,Город,Адрес,Телефон,Email,Telegram\n"

    def _upload_csv(self, auth, content: str):
        files = {"file": ("test.csv", content.encode("utf-8"), "text/csv")}
        return requests.post(f"{API}/import/upload", headers=auth, files=files)

    def test_full_import_flow_new_org(self, auth):
        unique = uuid.uuid4().hex[:6]
        csv = self.CSV_HEADER + f"TEST_ImpNew_{unique},IT,Москва,ул. Новая 1,89991112233,imp{unique}@x.ru,\n"
        up = self._upload_csv(auth, csv)
        assert up.status_code == 200, up.text
        d = up.json()
        assert "suggested_mapping" in d and d["suggested_mapping"].get("name")
        # analyze
        an = requests.post(f"{API}/import/analyze", headers=auth,
                           json={"import_id": d["import_id"], "mapping": d["suggested_mapping"]})
        assert an.status_code == 200
        counts = an.json()["counts"]
        assert counts["new"] == 1, counts
        # confirm
        cf = requests.post(f"{API}/import/confirm", headers=auth, json={"import_id": d["import_id"]})
        assert cf.status_code == 200
        assert cf.json()["report"]["new"] == 1
        # verify org exists with normalized phone
        r = requests.get(f"{API}/organizations", headers=auth, params={"search": f"TEST_ImpNew_{unique}"})
        items = r.json()["items"]
        assert len(items) == 1
        assert items[0]["phone"] == "+79991112233"
        # cleanup
        requests.delete(f"{API}/organizations/{items[0]['id']}", headers=auth)

    def test_phone_normalization_dedup(self, auth):
        """8 999 XXX and +7 (999) XXX must dedupe into same contact."""
        unique = uuid.uuid4().hex[:6]
        # First import: 8-prefix with spaces/dashes
        csv1 = self.CSV_HEADER + f"TEST_PhoneA_{unique},IT,Москва,,8 999 123-45-67,,\n"
        up = self._upload_csv(auth, csv1)
        did = up.json()["import_id"]; mapping = up.json()["suggested_mapping"]
        requests.post(f"{API}/import/analyze", headers=auth, json={"import_id": did, "mapping": mapping})
        requests.post(f"{API}/import/confirm", headers=auth, json={"import_id": did})

        # Second import: +7-prefix with parens
        csv2 = self.CSV_HEADER + f"TEST_PhoneB_{unique},IT,Москва,,+7 (999) 123-45-67,,\n"
        up2 = self._upload_csv(auth, csv2)
        did2 = up2.json()["import_id"]; mapping2 = up2.json()["suggested_mapping"]
        an = requests.post(f"{API}/import/analyze", headers=auth, json={"import_id": did2, "mapping": mapping2}).json()
        # should match existing → update
        assert an["counts"]["update"] == 1, f"expected update via phone match, got: {an['counts']}"
        # cleanup
        r = requests.get(f"{API}/organizations", headers=auth, params={"search": "TEST_PhoneA"})
        for it in r.json()["items"]:
            requests.delete(f"{API}/organizations/{it['id']}", headers=auth)

    def test_reimport_preserves_dnc_and_status(self, auth):
        """Reimporting an existing DNC org must NOT reset DNC/status."""
        # Find seeded DNC org "Ресторан «Восток»"
        r = requests.get(f"{API}/organizations", headers=auth, params={"search": "Восток"})
        vostok = None
        for it in r.json()["items"]:
            if "Восток" in it["name"]:
                vostok = it; break
        assert vostok is not None, "seeded DNC org 'Восток' not found"
        assert vostok["do_not_contact"] is True

        unique = uuid.uuid4().hex[:6]
        # Same name+address as seeded, plus mail to force match
        csv = self.CSV_HEADER + f'Ресторан «Восток»,Общепит,Сочи,ул. Приморская\\, 22,8 862 333-44-55,vostok@rest.ru,\n'
        # Note: comma in address needs escaping — using different quoting
        csv = ('Название,Категория,Город,Адрес,Телефон,Email,Telegram\n'
               '"Ресторан «Восток»","Общепит","Сочи","ул. Приморская, 22","8 862 333-44-55","vostok@rest.ru",""\n')
        up = self._upload_csv(auth, csv)
        did = up.json()["import_id"]
        mapping = up.json()["suggested_mapping"]
        an = requests.post(f"{API}/import/analyze", headers=auth, json={"import_id": did, "mapping": mapping}).json()
        assert an["counts"]["update"] == 1, f"expected 1 update, got {an['counts']}"
        cf = requests.post(f"{API}/import/confirm", headers=auth, json={"import_id": did}).json()
        assert cf["report"].get("dnc_protected", 0) >= 1

        # verify DNC preserved
        after = requests.get(f"{API}/organizations/{vostok['id']}", headers=auth).json()
        assert after["do_not_contact"] is True, "DNC was reset by import!"
        assert after["status"] == "Не связываться", f"status changed to {after['status']}"

    def test_analyze_requires_name_mapping(self, auth):
        csv = "col1,col2\na,b\n"
        up = self._upload_csv(auth, csv)
        did = up.json()["import_id"]
        r = requests.post(f"{API}/import/analyze", headers=auth,
                          json={"import_id": did, "mapping": {"city": "col1"}})
        assert r.status_code == 400


# ==============================================================
# TEMPLATES
# ==============================================================
class TestTemplates:
    def test_list_templates(self, auth):
        r = requests.get(f"{API}/templates", headers=auth)
        assert r.status_code == 200
        assert len(r.json()) >= 2  # 2 seeded

    def test_crud_template_and_preview(self, auth):
        body = {"name": "TEST_TPL_" + uuid.uuid4().hex[:6], "channel": "email",
                "subject": "Привет {organization_name}", "body": "Привет {organization_name} из {city}",
                "signature": "С уважением"}
        r = requests.post(f"{API}/templates", headers=auth, json=body)
        assert r.status_code == 200
        tid = r.json()["id"]
        # preview
        orgs = requests.get(f"{API}/organizations", headers=auth, params={"search": "Кофейня"}).json()["items"]
        oid = orgs[0]["id"]
        prev = requests.post(f"{API}/templates/preview", headers=auth,
                             json={"template_id": tid, "org_id": oid})
        assert prev.status_code == 200
        pd = prev.json()
        assert "Кофейня" in pd["body"] and "Москва" in pd["body"]
        # copy
        cp = requests.post(f"{API}/templates/{tid}/copy", headers=auth)
        assert cp.status_code == 200
        # archive
        ar = requests.post(f"{API}/templates/{tid}/archive", headers=auth)
        assert ar.status_code == 200

    def test_empty_body_rejected(self, auth):
        r = requests.post(f"{API}/templates", headers=auth,
                          json={"name": "TEST_empty", "channel": "email", "body": "   "})
        assert r.status_code == 400


# ==============================================================
# QUEUE + WORKER (MOCK send)
# ==============================================================
class TestQueue:
    def test_enqueue_skips_dnc_and_duplicates(self, auth):
        # find a normal org and a DNC org
        orgs = requests.get(f"{API}/organizations", headers=auth, params={"page_size": 100}).json()["items"]
        normal = next(o for o in orgs if not o["do_not_contact"] and o.get("email"))
        dnc = next(o for o in orgs if o["do_not_contact"])
        tpl_id = requests.get(f"{API}/templates", headers=auth, params={"channel": "email"}).json()[0]["id"]
        requests.post(f"{API}/queue/stop-all", headers=auth)
        try:
            r = requests.post(f"{API}/queue/enqueue", headers=auth, json={
                "org_ids": [normal["id"], dnc["id"]], "channel": "email", "template_id": tpl_id
            })
            j = r.json()
            assert j["added"] == 1 and j["skipped"] == 1, j
            # enqueue same org again → skipped as duplicate active task
            r2 = requests.post(f"{API}/queue/enqueue", headers=auth, json={
                "org_ids": [normal["id"]], "channel": "email", "template_id": tpl_id
            }).json()
            assert r2["skipped"] == 1
        finally:
            requests.post(f"{API}/queue/clear-pending", headers=auth)
            requests.post(f"{API}/queue/resume", headers=auth)
            # restore org status
            requests.post(f"{API}/organizations/{normal['id']}/status", headers=auth,
                          json={"status": "Готов к отправке"})

    def test_global_stop_blocks_processing(self, auth):
        r = requests.post(f"{API}/queue/stop-all", headers=auth)
        assert r.status_code == 200
        proc = requests.post(f"{API}/queue/process", headers=auth).json()
        assert proc.get("stopped") is True
        requests.post(f"{API}/queue/resume", headers=auth)

    def test_process_sends_and_updates_org(self, auth):
        # Create fresh org with email, enqueue, process
        oid = requests.post(f"{API}/organizations", headers=auth, json={
            "name": "TEST_QSend_" + uuid.uuid4().hex[:6],
            "email": f"q{uuid.uuid4().hex[:6]}@x.ru",
        }).json()["id"]
        tpl_id = requests.get(f"{API}/templates", headers=auth, params={"channel": "email"}).json()[0]["id"]
        # ensure resume
        requests.post(f"{API}/queue/resume", headers=auth)
        requests.post(f"{API}/queue/enqueue", headers=auth, json={
            "org_ids": [oid], "channel": "email", "template_id": tpl_id
        })
        proc = requests.post(f"{API}/queue/process", headers=auth).json()
        assert proc.get("sent", 0) >= 1, proc
        # verify org status
        got = requests.get(f"{API}/organizations/{oid}", headers=auth).json()
        assert got["status"] == "Отправлено"
        # history should show outgoing message
        msgs = requests.get(f"{API}/organizations/{oid}/messages", headers=auth).json()
        assert any(m["direction"] == "outgoing" for m in msgs)
        # cleanup
        requests.delete(f"{API}/organizations/{oid}", headers=auth)

    def test_clear_pending_and_retry(self, auth):
        r1 = requests.post(f"{API}/queue/clear-pending", headers=auth)
        assert r1.status_code == 200
        r2 = requests.post(f"{API}/queue/retry-errors", headers=auth)
        assert r2.status_code == 200


# ==============================================================
# REPLIES
# ==============================================================
class TestReplies:
    def test_simulate_reply_flow(self, auth):
        # Create org, set status Sent, simulate reply
        oid = requests.post(f"{API}/organizations", headers=auth, json={
            "name": "TEST_Reply_" + uuid.uuid4().hex[:6], "telegram": "test"
        }).json()["id"]
        requests.post(f"{API}/organizations/{oid}/status", headers=auth, json={"status": "Отправлено"})
        r = requests.post(f"{API}/replies/simulate", headers=auth,
                          json={"org_id": oid, "text": "Спасибо, интересно", "channel": "telegram"})
        assert r.status_code == 200
        got = requests.get(f"{API}/organizations/{oid}", headers=auth).json()
        assert got["status"] == "Ответил"
        uc = requests.get(f"{API}/replies/unread-count", headers=auth).json()
        assert uc["count"] >= 1
        # list
        replies = requests.get(f"{API}/replies", headers=auth).json()
        assert any(m["org_id"] == oid for m in replies)
        requests.delete(f"{API}/organizations/{oid}", headers=auth)


# ==============================================================
# DUPLICATES
# ==============================================================
class TestDuplicates:
    def test_list(self, auth):
        r = requests.get(f"{API}/duplicates", headers=auth)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ==============================================================
# EXPORTS (xlsx)
# ==============================================================
class TestExports:
    def test_export_all(self, auth):
        r = requests.get(f"{API}/export/all", headers=auth)
        assert r.status_code == 200
        assert "spreadsheetml" in r.headers.get("content-type", "")
        assert len(r.content) > 500

    def test_export_dnc(self, auth):
        r = requests.get(f"{API}/export/dnc", headers=auth)
        assert r.status_code == 200
        assert len(r.content) > 200

    def test_export_messages(self, auth):
        r = requests.get(f"{API}/export/messages", headers=auth)
        assert r.status_code == 200

    def test_export_filtered(self, auth):
        r = requests.post(f"{API}/export/filtered", headers=auth,
                          json={"filters": {"status": "Новый"}})
        assert r.status_code == 200

    def test_export_rejections(self, auth):
        r = requests.get(f"{API}/export/rejections", headers=auth)
        assert r.status_code == 200

    def test_export_errors(self, auth):
        r = requests.get(f"{API}/export/errors", headers=auth)
        assert r.status_code == 200


# ==============================================================
# BACKUPS
# ==============================================================
class TestBackups:
    def test_create_list_download(self, auth):
        c = requests.post(f"{API}/backups", headers=auth)
        assert c.status_code == 200
        bid = c.json()["backup_id"]
        lst = requests.get(f"{API}/backups", headers=auth).json()
        assert any(b["backup_id"] == bid for b in lst)
        dl = requests.get(f"{API}/backups/{bid}/download", headers=auth)
        assert dl.status_code == 200

    def test_restore_requires_confirm(self, auth):
        c = requests.post(f"{API}/backups", headers=auth)
        bid = c.json()["backup_id"]
        r = requests.post(f"{API}/backups/restore", headers=auth,
                         json={"backup_id": bid, "confirm": False})
        assert r.status_code == 400


# ==============================================================
# SETTINGS + INTEGRATIONS (mock)
# ==============================================================
class TestSettings:
    def test_get_and_put(self, auth):
        r = requests.get(f"{API}/settings", headers=auth)
        assert r.status_code == 200
        old = r.json().get("crm_name")
        u = requests.put(f"{API}/settings", headers=auth, json={"crm_name": "TEST_CRM_" + uuid.uuid4().hex[:4]})
        assert u.status_code == 200
        assert u.json()["crm_name"].startswith("TEST_CRM_")
        # restore
        requests.put(f"{API}/settings", headers=auth, json={"crm_name": old})


class TestIntegrations:
    """Iteration-1: real Telegram (Telethon) + Resend HTTPS — NO simulation.
    Real keys are NOT set in test env => endpoints must return proper
    503/400 errors, NEVER a fake success."""

    # ---- Telegram ----
    def test_telegram_status_not_configured_not_connected(self, auth):
        # ensure clean state
        requests.post(f"{API}/telegram/disconnect", headers=auth)
        r = requests.get(f"{API}/telegram/status", headers=auth)
        assert r.status_code == 200
        d = r.json()
        assert d["connected"] is False
        assert d["api_configured"] is False
        assert "status" in d and "errors" in d

    def test_telegram_login_start_no_api_keys(self, auth):
        r = requests.post(f"{API}/telegram/login/start", headers=auth, json={"phone": "+79990000000"})
        # No fake success — must be 503 config error
        assert r.status_code == 503, f"expected 503, got {r.status_code} {r.text}"
        detail = r.json().get("detail", "")
        assert "TELEGRAM_API_ID" in detail and "TELEGRAM_API_HASH" in detail

    def test_telegram_test_requires_session(self, auth):
        # no session => 400 "не подключен" (NOT fake success)
        requests.post(f"{API}/telegram/disconnect", headers=auth)
        r = requests.post(f"{API}/telegram/test", headers=auth, json={"to": "@someone", "text": "hi"})
        assert r.status_code == 400
        assert "не подключен" in r.json().get("detail", "").lower()

    def test_telegram_send_requires_session(self, auth):
        # Pick any org and try to send — session missing => 400
        orgs = requests.get(f"{API}/organizations", headers=auth, params={"page_size": 5}).json()["items"]
        oid = orgs[0]["id"]
        r = requests.post(f"{API}/telegram/send", headers=auth, json={"org_id": oid, "text": "hi"})
        # Could be 400 due to no session OR missing telegram field OR DNC — accept 400,
        # but must not be a fake 200.
        assert r.status_code in (400, 404), f"unexpected: {r.status_code} {r.text}"
        assert r.status_code != 200

    def test_telegram_check_replies_requires_session(self, auth):
        requests.post(f"{API}/telegram/disconnect", headers=auth)
        r = requests.post(f"{API}/telegram/check-replies", headers=auth)
        assert r.status_code == 400
        assert "не подключен" in r.json().get("detail", "").lower()

    def test_telegram_disconnect_ok(self, auth):
        r = requests.post(f"{API}/telegram/disconnect", headers=auth)
        assert r.status_code == 200
        assert r.json().get("ok") is True

    # ---- Email (Resend) ----
    def test_email_status_not_configured(self, auth):
        r = requests.get(f"{API}/email/status", headers=auth)
        assert r.status_code == 200
        d = r.json()
        assert d["configured"] is False
        assert d["provider"] == "resend"

    def test_email_test_no_api_key(self, auth):
        r = requests.post(f"{API}/email/test", headers=auth,
                          json={"to": "test@example.com", "subject": "t", "text": "hi"})
        # No fake success — 503 config error
        assert r.status_code == 503, f"expected 503, got {r.status_code} {r.text}"
        assert "RESEND_API_KEY" in r.json().get("detail", "")

    def test_email_send_org_without_email(self, auth):
        # create org without email -> 400
        oid = requests.post(f"{API}/organizations", headers=auth,
                            json={"name": "TEST_NoEmail_" + uuid.uuid4().hex[:6]}).json()["id"]
        try:
            r = requests.post(f"{API}/email/send", headers=auth,
                              json={"org_id": oid, "subject": "s", "text": "hi"})
            assert r.status_code == 400
            assert "email" in r.json().get("detail", "").lower()
        finally:
            requests.delete(f"{API}/organizations/{oid}", headers=auth)

    def test_email_send_dnc_org(self, auth):
        # find a DNC org
        orgs = requests.get(f"{API}/organizations", headers=auth, params={"do_not_contact": "yes"}).json()["items"]
        if not orgs:
            pytest.skip("No DNC org in seed data")
        oid = orgs[0]["id"]
        r = requests.post(f"{API}/email/send", headers=auth,
                          json={"org_id": oid, "subject": "s", "text": "hi"})
        assert r.status_code == 400
        assert "не связываться" in r.json().get("detail", "").lower()

    def test_email_send_no_api_key_returns_503(self, auth):
        """Org with email + no DNC + no first msg => hits provider layer => 503 no API key.
        Must NOT mark org as 'Отправлено'."""
        oid = requests.post(f"{API}/organizations", headers=auth, json={
            "name": "TEST_EmailNoKey_" + uuid.uuid4().hex[:6],
            "email": f"noc{uuid.uuid4().hex[:6]}@x.ru",
        }).json()["id"]
        try:
            # capture status before
            before = requests.get(f"{API}/organizations/{oid}", headers=auth).json()
            status_before = before["status"]
            r = requests.post(f"{API}/email/send", headers=auth,
                              json={"org_id": oid, "subject": "s", "text": "hi"})
            assert r.status_code == 503
            assert "RESEND_API_KEY" in r.json().get("detail", "")
            # status must not change to "Отправлено"
            after = requests.get(f"{API}/organizations/{oid}", headers=auth).json()
            assert after["status"] == status_before, f"org status changed on failed send: {after['status']}"
            assert after["status"] != "Отправлено"
        finally:
            requests.delete(f"{API}/organizations/{oid}", headers=auth)


class TestNoBackgroundWorker:
    """Iteration-1: background queue worker DISABLED — enqueued tasks
    must NOT auto-transition to 'Отправлено' without an explicit process call."""

    def test_worker_does_not_auto_send(self, auth):
        # ensure global not stopped (so if worker were running it would send)
        requests.post(f"{API}/queue/resume", headers=auth)
        oid = requests.post(f"{API}/organizations", headers=auth, json={
            "name": "TEST_NoAuto_" + uuid.uuid4().hex[:6],
            "email": f"na{uuid.uuid4().hex[:6]}@x.ru",
        }).json()["id"]
        try:
            tpl_id = requests.get(f"{API}/templates", headers=auth,
                                  params={"channel": "email"}).json()[0]["id"]
            enq = requests.post(f"{API}/queue/enqueue", headers=auth, json={
                "org_ids": [oid], "channel": "email", "template_id": tpl_id
            })
            assert enq.status_code == 200 and enq.json()["added"] == 1
            # wait 20s > worker interval (15s) — if auto-loop were on, task
            # would be processed by now
            time.sleep(20)
            q = requests.get(f"{API}/queue", headers=auth).json()
            org_tasks = [t for t in q if t["org_id"] == oid]
            assert org_tasks, "queue task disappeared"
            # No task should be Отправлено — must remain waiting/scheduled
            for t in org_tasks:
                assert t["status"] not in ("Отправлено", "Ошибка"), \
                    f"background worker processed task: {t}"
            org = requests.get(f"{API}/organizations/{oid}", headers=auth).json()
            assert org["status"] != "Отправлено"
        finally:
            requests.post(f"{API}/queue/clear-pending", headers=auth)
            requests.delete(f"{API}/organizations/{oid}", headers=auth)


# ==============================================================
# ADMINS CRUD + change password
# ==============================================================
class TestAdmins:
    def test_list_admins(self, auth):
        r = requests.get(f"{API}/admins", headers=auth)
        assert r.status_code == 200
        emails = [a["email"] for a in r.json()]
        assert "admin@crm.ru" in emails

    def test_create_delete_admin(self, auth):
        email = f"test_{uuid.uuid4().hex[:6]}@crm.ru"
        c = requests.post(f"{API}/admins", headers=auth,
                          json={"email": email, "name": "TEST", "password": "Passw0rd!"})
        assert c.status_code == 200
        aid = c.json()["id"]
        d = requests.delete(f"{API}/admins/{aid}", headers=auth)
        assert d.status_code == 200

    def test_change_password_bad_current(self, auth):
        r = requests.post(f"{API}/auth/change-password", headers=auth,
                          json={"old_password": "WRONG", "new_password": "NewPass1!"})
        assert r.status_code == 400

    def test_sessions_list(self, auth):
        r = requests.get(f"{API}/auth/sessions", headers=auth)
        assert r.status_code == 200
        assert isinstance(r.json(), list)
