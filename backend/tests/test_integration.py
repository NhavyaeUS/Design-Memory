"""
Integration tests for complete user flows — Milestone 1A.6.
Verifies all 14 end-to-end interactions defined in the specification.
"""
import pytest


def test_static_index_html_served(client):
    """The root URL must serve index.html with the frontend application."""
    res = client.get("/")
    assert res.status_code == 200
    assert "Design Memory" in res.text
    assert "api/v1" in res.text


def test_complete_user_flow(client):
    """
    Simulates the complete user workflow through the API endpoints:
    1. Load resources (initially empty or seeded).
    2. Add a resource.
    3. Retrieve resource details.
    4. Edit notes and reason for saving.
    5. Add and remove tags.
    6. Toggle favourite.
    7. Archive resource.
    8. Assign and remove collection membership.
    9. Create a collection.
    10. Delete a resource.
    11. Create a palette.
    12. Rename a palette.
    13. Add, edit, reorder, and remove palette colours.
    14. Reload and verify persistence across fresh fetches.
    """
    # 1. Load resources & collections
    items_res = client.get("/api/v1/items")
    assert items_res.status_code == 200
    cols_res = client.get("/api/v1/collections")
    assert cols_res.status_code == 200

    # 2. Add a resource
    create_res = client.post("/api/v1/items", json={
        "title": "Site Inspire",
        "url": "https://siteinspire.com",
        "domain": "siteinspire.com",
        "resource_type": "website",
        "color": "#F3D46A",
        "aspect_ratio": "4/3",
        "notes": "Initial note",
        "reason_for_saving": "",
    })
    assert create_res.status_code == 201
    item = create_res.json()
    item_id = item["id"]
    assert item["title"] == "Site Inspire"

    # 3. Open details (GET item)
    detail_res = client.get(f"/api/v1/items/{item_id}")
    assert detail_res.status_code == 200
    assert detail_res.json()["domain"] == "siteinspire.com"

    # 4. Edit notes and reason for saving
    note_res = client.patch(f"/api/v1/items/{item_id}", json={
        "notes": "Curated gallery for web inspiration.",
        "reason_for_saving": "Reference grid layout.",
    })
    assert note_res.status_code == 200
    assert note_res.json()["notes"] == "Curated gallery for web inspiration."
    assert note_res.json()["reason_for_saving"] == "Reference grid layout."

    # 5. Add and remove tags
    tags_res1 = client.patch(f"/api/v1/items/{item_id}", json={
        "tags": ["curation", "gallery", "web"],
    })
    assert tags_res1.status_code == 200
    assert sorted(tags_res1.json()["tags"]) == ["curation", "gallery", "web"]

    tags_res2 = client.patch(f"/api/v1/items/{item_id}", json={
        "tags": ["curation", "web"],
    })
    assert tags_res2.status_code == 200
    assert sorted(tags_res2.json()["tags"]) == ["curation", "web"]

    # 6. Toggle favourite
    fav_res = client.post(f"/api/v1/items/{item_id}/favorite")
    assert fav_res.status_code == 200
    assert fav_res.json()["is_favorite"] is True

    # 7. Archive resource
    arch_res = client.post(f"/api/v1/items/{item_id}/archive")
    assert arch_res.status_code == 200
    assert arch_res.json()["is_archived"] is True

    # 8. Un-archive or create a second resource to test collections
    item2 = client.post("/api/v1/items", json={
        "title": "Awwwards Nominee",
        "url": "https://awwwards.com",
        "domain": "awwwards.com",
        "resource_type": "website",
        "color": "#B4C7EC",
    }).json()
    item2_id = item2["id"]

    # 9. Create a collection
    col_res = client.post("/api/v1/collections", json={
        "name": "Design Awards",
        "color": "#F2B5DC",
    })
    assert col_res.status_code == 201
    col_id = col_res.json()["id"]

    # Assign membership
    assign_res = client.patch(f"/api/v1/items/{item2_id}", json={
        "collection_ids": [col_id],
    })
    assert assign_res.status_code == 200
    assert col_id in assign_res.json()["collection_ids"]

    # Remove membership
    unassign_res = client.patch(f"/api/v1/items/{item2_id}", json={
        "collection_ids": [],
    })
    assert unassign_res.status_code == 200
    assert assign_res.json()["collection_ids"] == [col_id]
    assert unassign_res.json()["collection_ids"] == []

    # 10. Delete a resource
    del_res = client.delete(f"/api/v1/items/{item2_id}")
    assert del_res.status_code == 204
    assert client.get(f"/api/v1/items/{item2_id}").status_code == 404

    # 11. Create a palette
    pal_res = client.post("/api/v1/items", json={
        "title": "Editorial Warmth",
        "resource_type": "color_palette",
        "color": "#263D32",
        "aspect_ratio": "5/4",
        "colors": [
            {"name": "Deep Forest", "hex_value": "#263D32", "source": "manual"},
            {"name": "Ochre", "hex_value": "#D9A86C", "source": "manual"},
            {"name": "Warm Paper", "hex_value": "#F1EADA", "source": "manual"},
        ],
    })
    assert pal_res.status_code == 201
    pal_id = pal_res.json()["id"]
    assert len(pal_res.json()["colors"]) == 3

    # 12. Rename palette
    rename_res = client.patch(f"/api/v1/items/{pal_id}", json={
        "title": "Editorial Warmth v2",
    })
    assert rename_res.status_code == 200
    assert rename_res.json()["title"] == "Editorial Warmth v2"

    # 13. Add, edit, reorder, remove colours
    colors_update = client.patch(f"/api/v1/items/{pal_id}", json={
        "colors": [
            {"name": "Ochre Sun", "hex_value": "#FFAA00", "source": "manual"}, # renamed & new hex
            {"name": "Deep Forest", "hex_value": "#263D32", "source": "manual"}, # reordered
            {"name": "Terracotta", "hex_value": "#B5543A", "source": "manual"},  # added
        ],
    })
    assert colors_update.status_code == 200
    updated_colors = colors_update.json()["colors"]
    assert len(updated_colors) == 3
    assert updated_colors[0]["name"] == "Ochre Sun"
    assert updated_colors[0]["hex_value"] == "#FFAA00"
    assert updated_colors[1]["name"] == "Deep Forest"
    assert updated_colors[2]["name"] == "Terracotta"

    # 14. Reload: verify persistence with a fresh GET query
    reload_res = client.get(f"/api/v1/items/{pal_id}")
    assert reload_res.status_code == 200
    reloaded_data = reload_res.json()
    assert reloaded_data["title"] == "Editorial Warmth v2"
    assert len(reloaded_data["colors"]) == 3
    assert reloaded_data["colors"][0]["name"] == "Ochre Sun"
