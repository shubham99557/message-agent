def test_register_and_login(client):
    # Register new user
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "siliguri_rep@acttrident.ai",
            "password": "SecurePassword123!",
            "full_name": "Siliguri Sales Lead",
            "role": "sales_rep"
        }
    )
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "siliguri_rep@acttrident.ai"
    assert "hashed_password" not in data

    # Login
    login_res = client.post(
        "/api/v1/auth/login",
        data={"username": "siliguri_rep@acttrident.ai", "password": "SecurePassword123!"}
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

    # Profile check with token
    profile_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token_data['access_token']}"}
    )
    assert profile_res.status_code == 200
    assert profile_res.json()["email"] == "siliguri_rep@acttrident.ai"


def test_invalid_login(client):
    res = client.post(
        "/api/v1/auth/login",
        data={"username": "nonexistent@acttrident.ai", "password": "WrongPassword!"}
    )
    assert res.status_code == 401


def test_role_based_access(client, auth_headers, admin_auth_headers):
    # Regular sales rep cannot view all users (admin/manager only)
    res_forbidden = client.get("/api/v1/auth/users", headers=auth_headers)
    assert res_forbidden.status_code == 403

    # Admin can view all users
    res_admin = client.get("/api/v1/auth/users", headers=admin_auth_headers)
    assert res_admin.status_code == 200
