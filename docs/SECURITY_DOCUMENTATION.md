# ActTrident AI Outreach Agent - Security Architecture & Documentation

## 1. Security Architecture Overview

The ActTrident sales platform is designed with defense-in-depth principles, protecting against data tampering, unsolicited messaging liability, SSRF, prompt injection, and credential exfiltration.

```
+-----------------------------------------------------------------------------------+
|                               Security Boundaries                                |
+-----------------------------------------------------------------------------------+
|  [External Web]    ---> SSRF Guard & IP Resolver Check                            |
|                         ---> Delimited & Sanitized HTML (Prompt Injection Guard)  |
|                         ---> AI Intelligence Layer (Zero Hallucination Rules)     |
|                                                                                   |
|  [User Actions]    ---> JWT Auth & RBAC (admin, manager, sales_rep)               |
|                         ---> Mandatory Human Approval Gate                        |
|                         ---> Global Suppression & Consent Verification Engine     |
|                         ---> Mail Transport (SMTP/Gmail) & Meta Cloud API         |
|                         ---> Immutable DB Audit Logs (IP, User, Action, Timestamp)|
+-----------------------------------------------------------------------------------+
```

---

## 2. Core Security Controls

### 2.1 SSRF (Server-Side Request Forgery) Protection
External URL fetching (e.g. reading company websites during discovery or research) is guarded by `app.core.security.is_safe_external_url`:
- Protocol whitelist: Only `http://` and `https://` are permitted.
- Hostname blacklist: Disallows `localhost`, `127.0.0.1`, `0.0.0.0`, `metadata.google.internal`, and AWS IMDS `169.254.169.254`.
- DNS Resolution Verification: Resolves IP address via system resolver and inspects `ipaddress.is_private`, `is_loopback`, `is_link_local`, and `is_reserved`. Any request resolving to private/internal space is blocked.

### 2.2 Prompt Injection Shielding
External scraped content is treated as untrusted input. `app.core.security.sanitize_untrusted_text`:
- Sanitizes instruction-override vectors (e.g., `ignore previous instructions`, `system prompt`, `you are now in developer mode`).
- Strips executable script tags and truncates inputs to 4,000 characters.
- Delimits user inputs clearly in system prompt instructions.

### 2.3 Strict Consent & Privacy Protection (WhatsApp Compliance)
- Unsolicited promotional messaging over WhatsApp is blocked at the database engine and service layer.
- Messages without documented consent are restricted to generating manual Click-to-Chat (`https://wa.me/...`) links.
- The approval engine blocks users from approving unconsented WhatsApp messages.

### 2.4 Human-in-the-Loop & Suppression Enforcement
- Default campaign and message state is `draft`.
- Outbound mail transfers verify that the draft status is `approved`.
- Global suppression list checks recipient email and phone against unsubscribes and opt-outs before every dispatch.
- Immediate opt-out synchronization: Any opt-out reply instantly suppresses the account, cancels upcoming follow-ups, and updates CRM status to `do_not_contact`.

### 2.5 Audit Logging
All security-sensitive operations (logins, email approvals, rejections, manual edits, trial activations, opt-outs) are persisted in the `audit_logs` table with timestamp, user ID, IP address, and JSON audit details.
