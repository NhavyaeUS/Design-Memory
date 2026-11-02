"""
Tests for Colour Palette resources and Color models — Milestone 1A.4 and Milestone 1A.5.
"""
import pytest
from sqlalchemy import text


def test_create_palette_with_colors(client):
    """Creating a color_palette resource with ordered colors normalizes hex and sets positions."""
    payload = {
        "title": "Nordic Dusk",
        "resource_type": "color_palette",
        "color": "#2E3440",
        "colors": [
            {"name": "Polar Night", "hex_value": "#2E3440", "source": "manual"},
            {"name": "Snow Storm", "hex_value": "#D8DEE9", "source": "manual"},
            {"name": "Frost", "hex_value": "#88C0D0", "source": "extracted"},
        ],
    }
    response = client.post("/api/v1/items", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Nordic Dusk"
    assert data["resource_type"] == "color_palette"
    assert len(data["colors"]) == 3

    colors = data["colors"]
    assert colors[0]["position"] == 0
    assert colors[0]["name"] == "Polar Night"
    assert colors[0]["hex_value"] == "#2E3440"

    assert colors[1]["position"] == 1
    assert colors[1]["name"] == "Snow Storm"

    assert colors[2]["position"] == 2
    assert colors[2]["source"] == "extracted"


def test_palette_color_hex_normalization(client):
    """3-digit hex values in palette colors are normalized to 6-digit uppercase."""
    payload = {
        "title": "Short Hex Palette",
        "resource_type": "color_palette",
        "color": "#000",
        "colors": [
            {"name": "White", "hex_value": "fff", "source": "manual"},
            {"name": "Red", "hex_value": "#f00", "source": "manual"},
        ],
    }
    response = client.post("/api/v1/items", json=payload)
    assert response.status_code == 201
    colors = response.json()["colors"]
    assert colors[0]["hex_value"] == "#FFFFFF"
    assert colors[1]["hex_value"] == "#FF0000"


def test_palette_invalid_color_rejected(client):
    """Invalid hex values return HTTP 422."""
    payload = {
        "title": "Bad Palette",
        "resource_type": "color_palette",
        "color": "#112233",
        "colors": [
            {"name": "Broken", "hex_value": "not-hex", "source": "manual"}
        ],
    }
    response = client.post("/api/v1/items", json=payload)
    assert response.status_code == 422


def test_reorder_and_update_palette_colors(client):
    """PATCH updates palette title and replaces/reorders color entries."""
    created = client.post("/api/v1/items", json={
        "title": "Original Palette",
        "resource_type": "color_palette",
        "color": "#111111",
        "colors": [
            {"name": "Color 1", "hex_value": "#111111", "source": "manual"},
            {"name": "Color 2", "hex_value": "#222222", "source": "manual"},
        ],
    }).json()
    item_id = created["id"]

    # Reorder and add a 3rd color
    patch_res = client.patch(f"/api/v1/items/{item_id}", json={
        "title": "Renamed Palette",
        "colors": [
            {"name": "Color 2", "hex_value": "#222222", "source": "manual"},
            {"name": "Color 3", "hex_value": "#333333", "source": "manual"},
            {"name": "Color 1", "hex_value": "#111111", "source": "manual"},
        ],
    })
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["title"] == "Renamed Palette"
    assert len(updated["colors"]) == 3
    assert updated["colors"][0]["name"] == "Color 2"
    assert updated["colors"][0]["position"] == 0
    assert updated["colors"][1]["name"] == "Color 3"
    assert updated["colors"][1]["position"] == 1
    assert updated["colors"][2]["name"] == "Color 1"
    assert updated["colors"][2]["position"] == 2


def test_palette_cascade_deletion(client, db):
    """Deleting a color_palette item cascades and removes its colors from the colors table."""
    created = client.post("/api/v1/items", json={
        "title": "Ephemeral Palette",
        "resource_type": "color_palette",
        "color": "#112233",
        "colors": [
            {"name": "C1", "hex_value": "#112233", "source": "manual"},
            {"name": "C2", "hex_value": "#445566", "source": "manual"},
        ],
    }).json()
    item_id = created["id"]

    # Verify colors exist in db
    count_before = db.execute(
        text("SELECT COUNT(*) FROM colors WHERE item_id = :id"),
        {"id": item_id},
    ).scalar()
    assert count_before == 2

    # Delete palette item
    del_res = client.delete(f"/api/v1/items/{item_id}")
    assert del_res.status_code == 204

    # Verify colors are deleted (cascade delete-orphan)
    count_after = db.execute(
        text("SELECT COUNT(*) FROM colors WHERE item_id = :id"),
        {"id": item_id},
    ).scalar()
    assert count_after == 0


def test_search_by_palette_color_name_and_hex(client):
    """Plain-text search finds palette by color name or hex."""
    client.post("/api/v1/items", json={
        "title": "Sunset Vibe",
        "resource_type": "color_palette",
        "color": "#FF7E5F",
        "colors": [
            {"name": "Tangerine Glow", "hex_value": "#FEB47B", "source": "manual"},
        ],
    })

    # Search by color name
    res1 = client.get("/api/v1/items?q=Tangerine")
    assert res1.status_code == 200
    assert len(res1.json()) == 1
    assert res1.json()[0]["title"] == "Sunset Vibe"

    # Search by hex
    res2 = client.get("/api/v1/items?q=FEB47B")
    assert res2.status_code == 200
    assert len(res2.json()) == 1
    assert res2.json()[0]["title"] == "Sunset Vibe"
