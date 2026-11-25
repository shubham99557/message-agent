# ActTrident AI Sales Outreach Agent — Testing Guide

## 1. Automated Test Suite Architecture (85+ Tests)
All automated backend tests run completely offline using isolated temporary SQLite databases and `httpx.MockTransport` — **zero real external emails, WhatsApp messages, or LinkedIn requests are ever sent during automated tests**.

| Test File | Scope |
| :--- | :--- |
| `backend/tests/test_auth_and_security.py` | Registration, login, JWT validation, RBAC basics |
| `backend/tests/test_security_regressions.py` | Production secret & CORS guards, approval tampering, webhook HMAC |
| `backend/tests/test_phase1_security_foundation.py` | Password policy, `token_version` revocation, Fernet encryption, atomic send claim |
| `backend/tests/test_phase2_email_integration.py` | Gmail OAuth 2.0 CSRF/refresh/send/sync, SMTP honesty, bounce detection |
| `backend/tests/test_phase3_whatsapp_integration.py` | Meta Cloud API health/template sync, ordered params, live consent, webhook STOP |
| `backend/tests/test_phase4_discovery_and_research.py` | Demo quarantine, real discovery adapters, verification workflow, missing-info research |
| `backend/tests/test_phase5_linkedin_and_channels.py` | Unified `ChannelAdapter`, LinkedIn OAuth 2.0, char limits, manual handoff & partner API |
| `backend/tests/test_phase6_orchestration.py` | Global Kill Switch, campaign pause/resume/stop, transactional outbox, IST hours guard |
| `backend/tests/test_phase7_e2e_and_security_penetration.py` | 14-step E2E B2B workflow, security penetration matrix, DB backup/restore + SHA-256 tamper test |
| `backend/tests/test_discovery_and_qualification.py` | CSV import attribution, 7-factor qualification, SSRF protection |
| `backend/tests/test_email_and_approval_flow.py` | Draft lifecycle, approval queue, rejection & skip |
| `backend/tests/test_whatsapp_and_consent.py` | Consent records, template rendering, webhook ingestion |
| `backend/tests/test_replies_crm_analytics.py` | 10-class reply classifier, CRM pipeline stages, honest analytics |
| `backend/tests/test_background_jobs.py` | Task persistence, idempotency keys, cancellation, dead-letter queue |

---

## 2. Running Automated Tests
```bash
# Run the complete backend regression suite
python -m pytest backend/tests -v

# Run a specific phase suite
python -m pytest backend/tests/test_phase7_e2e_and_security_penetration.py -v

# Verify frontend TypeScript compilation and Vite production bundle
npm run build --prefix frontend
```

---

## 3. Verifying Database Migrations & Backup Recovery
```bash
# Test non-destructive Alembic upgrade / downgrade / re-upgrade on a copy
cp acttrident.db acttrident_test.db
DATABASE_URL="sqlite:///./acttrident_test.db" python -m alembic -c backend/alembic.ini upgrade head
DATABASE_URL="sqlite:///./acttrident_test.db" python -m alembic -c backend/alembic.ini downgrade -1
DATABASE_URL="sqlite:///./acttrident_test.db" python -m alembic -c backend/alembic.ini upgrade head
rm acttrident_test.db

# Test CLI backup & restore with SHA-256 manifest verification
python backend/scripts/backup_restore_db.py backup --db-url sqlite:///./acttrident.db --output ./backups/test.db
```
