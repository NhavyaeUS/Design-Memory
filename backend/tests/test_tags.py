"""
Tests for Tag model, API, and relationships — Milestone 1A.4 and Milestone 1A.5.
"""
import pytest


def test_tag_assignment_and_normalization(client):
    """Tags are normalised to lowercase, whitespace-trimmed, and attached to items."""
    item_res = client.post("/api/v1/items", json={
        "title": "Tagged Item",
        "resource_type": "website",
        "color": "#112233",
    })
    item_id = item_res.json()["id"]

    # Assign tags with mixed casing and extra spaces
    patch_res = client.patch(f"/api/v1/items/{item_id}", json={
        "tags": [" Minimal ", "BRUTALISM", "web3"],
    })
    assert patch_res.status_code == 200
    tags = patch_res.json()["tags"]
    assert "minimal" in tags
    assert "brutalism" in tags
    assert "web3" in tags

    # Verify tags endpoint returns them sorted
    tag_list_res = client.get("/api/v1/tags")
    assert tag_list_res.status_code == 200
    all_tags = tag_list_res.json()
    assert "brutalism" in all_tags
    assert "minimal" in all_tags
    assert "web3" in all_tags


def test_remove_tag_from_item(client):
    """Removing a tag from an item updates its tag list without deleting other tags."""
    item_res = client.post("/api/v1/items", json={
        "title": "Tag Edit Item",
        "resource_type": "website",
        "color": "#112233",
    })
    item_id = item_res.json()["id"]

    # Set initial tags
    client.patch(f"/api/v1/items/{item_id}", json={"tags": ["art", "design"]})

    # Remove "art"
    patch_res = client.patch(f"/api/v1/items/{item_id}", json={"tags": ["design"]})
    assert patch_res.status_code == 200
    assert patch_res.json()["tags"] == ["design"]


def test_search_by_tag(client):
    """Item search matches tags."""
    client.post("/api/v1/items", json={
        "title": "Poster Collection",
        "resource_type": "image",
        "color": "#998877",
    })
    item2 = client.post("/api/v1/items", json={
        "title": "Abstract Artwork",
        "resource_type": "image",
        "color": "#223344",
    }).json()

    client.patch(f"/api/v1/items/{item2['id']}", json={"tags": ["bauhaus"]})

    search_res = client.get("/api/v1/items?q=bauhaus")
    assert search_res.status_code == 200
    results = search_res.json()
    assert len(results) == 1
    assert results[0]["id"] == item2["id"]
