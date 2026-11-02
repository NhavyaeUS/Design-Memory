"""
Tests for Collections API and relationships — Milestone 1A.4 and Milestone 1A.5.
"""
import pytest


def test_create_and_list_collections(client):
    """Creating a collection returns 201 and it appears in the collection list."""
    res = client.post("/api/v1/collections", json={
        "name": "Design Systems",
        "color": "#E5E5EA",
    })
    assert res.status_code == 201
    col = res.json()
    assert col["id"] > 0
    assert col["name"] == "Design Systems"
    assert col["color"] == "#E5E5EA"

    # List collections
    list_res = client.get("/api/v1/collections")
    assert list_res.status_code == 200
    names = [c["name"] for c in list_res.json()]
    assert "Design Systems" in names


def test_collection_validation(client):
    """Validation errors on invalid collection input."""
    # Empty name
    empty_name = client.post("/api/v1/collections", json={
        "name": "",
        "color": "#112233",
    })
    assert empty_name.status_code == 422

    # Invalid HEX
    bad_color = client.post("/api/v1/collections", json={
        "name": "Valid Name",
        "color": "xyz",
    })
    assert bad_color.status_code == 422


def test_update_collection(client):
    """PATCH /api/v1/collections/{id} updates name and color."""
    created = client.post("/api/v1/collections", json={
        "name": "Old Name",
        "color": "#111111",
    }).json()

    patch_res = client.patch(f"/api/v1/collections/{created['id']}", json={
        "name": "New Name",
        "color": "#222222",
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "New Name"
    assert patch_res.json()["color"] == "#222222"


def test_delete_collection_preserves_items(client):
    """Deleting a collection leaves the items intact (unintended cascade prevented)."""
    # Create collection
    col_res = client.post("/api/v1/collections", json={
        "name": "Temporary Collection",
        "color": "#ABCDEF",
    })
    col_id = col_res.json()["id"]

    # Create item assigned to collection
    item_res = client.post("/api/v1/items", json={
        "title": "Persistent Resource",
        "resource_type": "website",
        "color": "#123456",
    })
    item_id = item_res.json()["id"]

    # Assign item to collection
    assign_res = client.patch(f"/api/v1/items/{item_id}", json={
        "collection_ids": [col_id],
    })
    assert assign_res.status_code == 200
    assert assign_res.json()["collection_ids"] == [col_id]

    # Verify item filter by collection works
    filtered = client.get(f"/api/v1/items?collection_id={col_id}")
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1

    # Delete collection
    del_res = client.delete(f"/api/v1/collections/{col_id}")
    assert del_res.status_code == 204

    # Item must still exist!
    item_check = client.get(f"/api/v1/items/{item_id}")
    assert item_check.status_code == 200
    assert item_check.json()["title"] == "Persistent Resource"
    # Its collection_ids should no longer contain col_id
    assert col_id not in item_check.json()["collection_ids"]
