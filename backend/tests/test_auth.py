import pytest


@pytest.mark.asyncio
async def test_register(client):
    resp = await client.post("/auth/register", json={
        "email": "newuser@test.com",
        "password": "pass1234",
        "full_name": "New User",
        "role": "witness"
    })
    assert resp.status_code == 201
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/auth/register", json={
        "email": "login@test.com",
        "password": "pass1234",
        "full_name": "Login User",
        "role": "investigator"
    })
    resp = await client.post("/auth/login", json={
        "email": "login@test.com",
        "password": "pass1234"
    })
    assert resp.status_code == 200
    assert resp.json()["role"] == "investigator"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    resp = await client.post("/auth/login", json={
        "email": "login@test.com",
        "password": "wrongpass"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_register(client):
    payload = {"email": "dup@test.com", "password": "p", "full_name": "Dup", "role": "witness"}
    await client.post("/auth/register", json=payload)
    resp = await client.post("/auth/register", json=payload)
    assert resp.status_code == 400