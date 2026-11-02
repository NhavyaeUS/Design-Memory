"""
Tests for Items API and Item models — Milestone 1A.4 and Milestone 1A.5.
"""
import pytest
from app.models.item import ResourceType


def test_create_item_success(client):
    """Creating an item with valid fields returns HTTP 201 and correct structure."""
    payload = {
        "title": "Minimal Studio",
        "url": "https://minimal.studio",
        "domain": "minimal.studio",
        "resource_type": "website",
        "color": "#B4C7EC",
        "aspect_ratio": "16/9",
        "notes": "Great clean layout",
        "reason_for_saving": "Reference for portfolio layout",
    }
    response = client.post("/api/v1/items", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["title"] == "Minimal Studio"
    assert data["url"] == "https://minimal.studio"
    assert data["domain"] == "minimal.studio"
    assert data["resource_type"] == "website"
    assert data["color"] == "#B4C7EC"
    assert data["is_favorite"] is False
    assert data["is_archived"] is False
    assert data["tags"] == []
    assert data["collection_ids"] == []


def test_create_item_invalid_type(client):
    """Invalid resource_type must return HTTP 422."""
    payload = {
        "title": "Invalid Type Item",
        "resource_type": "not_a_type",
        "color": "#112233",
    }
    response = client.post("/api/v1/items", json=payload)
    assert response.status_code == 422


def test_create_item_invalid_color(client):
    """Invalid HEX colour must return HTTP 422."""
    payload = {
        "title": "Bad Color",
        "resource_type": "website",
        "color": "not-a-hex",
    }
    response = client.post("/api/v1/items", json=payload)
    assert response.status_code == 422


def test_create_item_3_digit_hex_normalized(client):
    """3-digit hex like #abc or abc should be normalised to 6-digit #AABBCC."""
    payload = {
        "title": "Short Hex",
        "resource_type": "website",
        "color": "#f0a",
    }
    response = client.post("/api/v1/items", json=payload)
    assert response.status_code == 201
    assert response.json()["color"] == "#FF00AA"


def test_get_item_by_id(client):
    """GET /api/v1/items/{id} returns 200 for existing item, 404 for missing."""
    res = client.post("/api/v1/items", json={
        "title": "Fetchable Item",
        "resource_type": "type",
        "font_family": "Inter",
        "color": "#334455",
    })
    assert res.status_code == 201
    item_id = res.json()["id"]

    get_res = client.get(f"/api/v1/items/{item_id}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == "Fetchable Item"
    assert get_res.json()["font_family"] == "Inter"

    # Missing item
    missing = client.get("/api/v1/items/999999")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Item not found"


def test_list_items_and_filtering(client):
    """Listing items supports type filter, favorites filter, and search."""
    client.post("/api/v1/items", json={
        "title": "Brand Design Alpha",
        "domain": "alpha.design",
        "resource_type": "website",
        "color": "#AABBCC",
        "is_favorite": True,
        "notes": "Special typography",
    })
    client.post("/api/v1/items", json={
        "title": "Beta Component",
        "domain": "beta.ui",
        "resource_type": "ui",
        "color": "#CCDDEE",
        "is_favorite": False,
    })

    # All non-archived items
    all_res = client.get("/api/v1/items")
    assert all_res.status_code == 200
    titles = [i["title"] for i in all_res.json()]
    assert "Brand Design Alpha" in titles
    assert "Beta Component" in titles

    # Filter by resource_type
    type_res = client.get("/api/v1/items?type=ui")
    assert type_res.status_code == 200
    assert len(type_res.json()) == 1
    assert type_res.json()[0]["title"] == "Beta Component"

    # Filter by favorites
    fav_res = client.get("/api/v1/items?favorites=true")
    assert fav_res.status_code == 200
    fav_titles = [i["title"] for i in fav_res.json()]
    assert "Brand Design Alpha" in fav_titles
    assert "Beta Component" not in fav_titles

    # Search by text
    search_res = client.get("/api/v1/items?q=typography")
    assert search_res.status_code == 200
    assert len(search_res.json()) == 1
    assert search_res.json()[0]["title"] == "Brand Design Alpha"


def test_patch_item_partial_update(client):
    """PATCH updates specified fields without wiping unspecified fields."""
    res = client.post("/api/v1/items", json={
        "title": "Initial Title",
        "domain": "initial.com",
        "resource_type": "image",
        "color": "#112233",
        "notes": "Initial notes",
        "reason_for_saving": "Initial why",
    })
    item_id = res.json()["id"]

    # Update only title and notes
    patch_res = client.patch(f"/api/v1/items/{item_id}", json={
        "title": "Updated Title",
        "notes": "Updated notes",
    })
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["title"] == "Updated Title"
    assert data["notes"] == "Updated notes"
    assert data["reason_for_saving"] == "Initial why"  # preserved
    assert data["domain"] == "initial.com"              # preserved
    assert data["color"] == "#112233"                  # preserved


def test_toggle_favorite_and_archive(client):
    """POST /items/{id}/favorite and /archive correctly toggle and update state."""
    res = client.post("/api/v1/items", json={
        "title": "Fav Item",
        "resource_type": "tool",
        "color": "#334455",
    })
    item_id = res.json()["id"]
    assert res.json()["is_favorite"] is False

    # Favorite toggle: false -> true
    fav_res1 = client.post(f"/api/v1/items/{item_id}/favorite")
    assert fav_res1.status_code == 200
    assert fav_res1.json()["is_favorite"] is True

    # Favorite toggle: true -> false
    fav_res2 = client.post(f"/api/v1/items/{item_id}/favorite")
    assert fav_res2.status_code == 200
    assert fav_res2.json()["is_favorite"] is False

    # Archive item
    arch_res = client.post(f"/api/v1/items/{item_id}/archive")
    assert arch_res.status_code == 200
    assert arch_res.json()["is_archived"] is True

    # By default, archived items are hidden from list
    list_res = client.get("/api/v1/items")
    assert item_id not in [i["id"] for i in list_res.json()]

    # But included if archived=true
    arch_list = client.get("/api/v1/items?archived=true")
    assert item_id in [i["id"] for i in arch_list.json()]


def test_delete_item(client):
    """DELETE /items/{id} removes the item completely."""
    res = client.post("/api/v1/items", json={
        "title": "To Delete",
        "resource_type": "animation",
        "color": "#445566",
    })
    item_id = res.json()["id"]

    del_res = client.delete(f"/api/v1/items/{item_id}")
    assert del_res.status_code == 204

    # Getting deleted item returns 404
    get_res = client.get(f"/api/v1/items/{item_id}")
    assert get_res.status_code == 404

    # Deleting non-existent returns 404
    assert client.delete(f"/api/v1/items/{item_id}").status_code == 404


def test_duplicate_domain_check(client):
    """check_duplicate endpoint returns item if domain matches, null if none."""
    client.post("/api/v1/items", json={
        "title": "Stripe",
        "domain": "stripe.com",
        "resource_type": "website",
        "color": "#635BFF",
    })

    dup_res = client.get("/api/v1/items/check/duplicate-domain?domain=stripe.com")
    assert dup_res.status_code == 200
    assert dup_res.json() is not None
    assert dup_res.json()["title"] == "Stripe"

    non_dup = client.get("/api/v1/items/check/duplicate-domain?domain=github.com")
    assert non_dup.status_code == 200
    assert non_dup.json() is None
