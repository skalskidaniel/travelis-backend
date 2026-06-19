def test_health_check_returns_ok(client):
    response = client.get("/api/v2/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
