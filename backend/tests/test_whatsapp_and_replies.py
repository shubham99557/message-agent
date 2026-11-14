def test_whatsapp_strict_consent_enforcement(client, auth_headers, admin_auth_headers):
    # 1. Company with public WhatsApp but NO recorded consent
    comp = client.post(
        "/api/v1/companies",
        json={
            "name": "Sikkim Valley Software",
            "city": "Gangtok",
            "public_phone": "+91-9733099999",
            "public_whatsapp": "+91-9733099999"
        },
        headers=auth_headers
    ).json()

    # Attempt to draft WhatsApp message using approved Meta template
    draft_res = client.post(
        "/api/v1/whatsapp/draft",
        json={
            "company_id": comp["id"],
            "template_name": "acttrident_intro_utility_v1",
            "parameters": {"1": "Lead", "2": "Gangtok"}
        },
        headers=auth_headers
    )
    assert draft_res.status_code == 201
    msg_data = draft_res.json()
    assert msg_data["has_valid_consent"] is False
    assert msg_data["click_to_chat_url"] is not None
    assert "https://wa.me/919733099999" in msg_data["click_to_chat_url"]

    # ATTEMPT TO APPROVE UNCONSENTED WHATSAPP MESSAGE -> MUST BE BLOCKED BY POLICY
    appr_res = client.post(f"/api/v1/whatsapp/approve/{msg_data['id']}", headers=admin_auth_headers)
    assert appr_res.status_code == 400
    assert "consent is mandatory" in appr_res.json()["detail"].lower()

    # 2. Record explicit valid consent (e.g. from an inbound web inquiry or signed business card)
    consent_res = client.post(
        "/api/v1/whatsapp/consent",
        json={
            "company_id": comp["id"],
            "channel": "whatsapp",
            "consent_status": "opted_in",
            "consent_source": "Inbound Web Inquiry Form (Consent Form #4102)",
            "consent_purpose": "ActTrident 90-day evaluation demonstration",
            "proof_reference": "https://acttrident.ai/inbound/form-4102.pdf"
        },
        headers=auth_headers
    )
    assert consent_res.status_code == 201

    # 3. Now draft WhatsApp message with verified consent
    draft_consented = client.post(
        "/api/v1/whatsapp/draft",
        json={
            "company_id": comp["id"],
            "template_name": "acttrident_intro_utility_v1",
            "parameters": {"1": "Lead", "2": "Gangtok"}
        },
        headers=auth_headers
    ).json()
    assert draft_consented["has_valid_consent"] is True

    # Approve consented message using admin/manager headers
    appr_success = client.post(f"/api/v1/whatsapp/approve/{draft_consented['id']}", headers=admin_auth_headers)
    assert appr_success.status_code == 200
    assert appr_success.json()["approval_status"] == "approved"

    # Send approved message
    send_res = client.post(f"/api/v1/whatsapp/send/{draft_consented['id']}", headers=admin_auth_headers)
    assert send_res.status_code == 200
    assert send_res.json()["status"] == "success"


def test_ai_reply_classification_10_categories(client, auth_headers, admin_auth_headers):
    # Test Inbound 'Interested' reply (authenticated endpoint)
    res_interest = client.post(
        "/api/v1/replies/inbound",
        json={
            "channel": "email",
            "sender_identifier": "cto@patnadevs.example.com",
            "subject": "Re: ActTrident 90-day Evaluation",
            "message_body": "This sounds relevant. We manage 15 hybrid laptops. Please share more details and a demo."
        },
        headers=auth_headers
    )
    assert res_interest.status_code == 201
    rep1 = res_interest.json()
    assert rep1["classification"] in ["interested", "requests_demonstration"]
    assert rep1["is_negotiation"] is True
    assert rep1["suggested_response"] is not None

    # Test Inbound 'Unsubscribe' reply -> must trigger opt-out
    res_unsub = client.post(
        "/api/v1/replies/inbound",
        json={
            "channel": "email",
            "sender_identifier": "remove@unsubcompany.example.com",
            "subject": "STOP",
            "message_body": "Please stop emailing me. Unsubscribe."
        },
        headers=auth_headers
    )
    assert res_unsub.status_code == 201
    rep2 = res_unsub.json()
    assert rep2["classification"] == "unsubscribe"

    # Test Inbound 'Out of Office' reply
    res_ooo = client.post(
        "/api/v1/replies/inbound",
        json={
            "channel": "email",
            "sender_identifier": "auto@holiday.example.com",
            "subject": "Out of office: Away on annual leave",
            "message_body": "I am away from my desk until next Monday. I will have limited access to email."
        },
        headers=auth_headers
    )
    assert res_ooo.status_code == 201
    rep3 = res_ooo.json()
    assert rep3["classification"] == "out_of_office"

    # Human approves negotiated response using admin credentials
    appr_resp = client.post(
        f"/api/v1/replies/{rep1['id']}/approve-response",
        json={"approved_text": "Thank you! We have confirmed Thursday at 3 PM IST.", "send_immediately": False},
        headers=admin_auth_headers
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["human_approved"] is True
