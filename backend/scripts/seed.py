"""
Seed script for Design Memory database.

- Reads database connection from app settings.
- Idempotent: if records already exist, exits without modifying unless --force is given.
- Populates the initial 4 collections and 17 sample resources from the frontend prototype.
- Safe: never runs on app startup; executed explicitly by the user or during testing.

Usage:
    .venv/bin/python scripts/seed.py
    .venv/bin/python scripts/seed.py --force
"""
import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.collection import Collection
from app.models.item import Item, Color, ResourceType
from app.models.tag import Tag
from app.services.items import _get_or_create_tags

C = {
    "y": "#F3D46A",
    "o": "#EC8A5A",
    "m": "#BFE8CF",
    "b": "#B4C7EC",
    "p": "#F2B5DC",
    "f": "#244C3A",
    "r": "#7A2323",
    "c": "#F6ECC0",
    "l": "#C7B5EC",
}

INITIAL_COLLECTIONS = [
    {"id": 1, "name": "Portfolio references", "color": C["l"]},
    {"id": 2, "name": "Experimental type", "color": C["y"]},
    {"id": 3, "name": "Microinteractions", "color": C["m"]},
    {"id": 4, "name": "Japanese web design", "color": C["o"]},
]

INITIAL_ITEMS = [
    {
        "title": "Studio Ono: digital experiences",
        "domain": "ono.studio",
        "url": "https://ono.studio",
        "resource_type": ResourceType.website,
        "tags": ["portfolio", "editorial"],
        "collection_ids": [1, 4],
        "aspect_ratio": "4/5",
        "color": C["l"],
        "is_favorite": True,
        "notes": "Soft pastel blocks against a calm grid. The headline scale is the whole identity.",
        "reason_for_saving": "Reference for my own case-study layout.",
    },
    {
        "title": "Fraunces",
        "domain": "fonts.google.com",
        "url": "https://fonts.google.com",
        "resource_type": ResourceType.type,
        "tags": ["serif", "variable"],
        "collection_ids": [2],
        "aspect_ratio": "1/1",
        "color": C["y"],
        "font_family": "Fraunces",
        "notes": "Wonk axis gives it warmth at display sizes.",
        "reason_for_saving": "Candidate for headings.",
    },
    {
        "title": "shadcn/ui",
        "domain": "ui.shadcn.com",
        "url": "https://ui.shadcn.com",
        "resource_type": ResourceType.ui,
        "tags": ["react", "tailwind"],
        "collection_ids": [],
        "aspect_ratio": "5/4",
        "color": C["b"],
        "notes": "",
        "reason_for_saving": "Base for the extension popup.",
    },
    {
        "title": "Jupi brand identity",
        "domain": "behance.net",
        "url": "https://behance.net",
        "resource_type": ResourceType.image,
        "tags": ["illustration", "palette"],
        "collection_ids": [1],
        "aspect_ratio": "6/5",
        "color": C["b"],
        "color2": C["o"],
        "is_favorite": True,
        "notes": "Surreal scale shifts, muted olive and lilac. Great palette discipline.",
        "reason_for_saving": "Mood for the portfolio hero.",
    },
    {
        "title": "Paper Store: creative prompts and workbooks",
        "domain": "paper.example",
        "url": "https://paper.example",
        "resource_type": ResourceType.website,
        "tags": ["cards", "shadow"],
        "collection_ids": [4],
        "aspect_ratio": "1/1",
        "color": C["o"],
        "notes": "Book covers as tiles, each with its own colour.",
        "reason_for_saving": "Soft card shadows.",
    },
    {
        "title": "Switch-Lit Library",
        "domain": "switch-lit.org",
        "url": "https://switch-lit.org",
        "resource_type": ResourceType.website,
        "tags": ["editorial", "gradient"],
        "collection_ids": [1, 4],
        "aspect_ratio": "3/4",
        "color": C["p"],
        "is_favorite": True,
        "notes": "Blurred gradient covers over stripes.",
        "reason_for_saving": "Featured shelf pattern.",
    },
    {
        "title": "Instrument Serif",
        "domain": "fonts.google.com",
        "url": "https://fonts.google.com",
        "resource_type": ResourceType.type,
        "tags": ["serif", "display"],
        "collection_ids": [2],
        "aspect_ratio": "5/4",
        "color": C["c"],
        "font_family": "Instrument Serif",
        "notes": "Condensed, elegant. Used here for display text.",
        "reason_for_saving": "",
    },
    {
        "title": "Motion Primitives",
        "domain": "motion-primitives.com",
        "url": "https://motion-primitives.com",
        "resource_type": ResourceType.animation,
        "tags": ["react", "springs"],
        "collection_ids": [3],
        "aspect_ratio": "1/1",
        "color": C["m"],
        "notes": "",
        "reason_for_saving": "Spring presets for drawer.",
    },
    {
        "title": "lele: designer in pursuit of aesthetics",
        "domain": "lele.design",
        "url": "https://lele.design",
        "resource_type": ResourceType.website,
        "tags": ["playful", "polaroid"],
        "collection_ids": [1, 3],
        "aspect_ratio": "4/5",
        "color": C["b"],
        "notes": "Rotated polaroids and a chat input. Personality first.",
        "reason_for_saving": "Playful about page.",
    },
    {
        "title": "Radix Primitives",
        "domain": "radix-ui.com",
        "url": "https://radix-ui.com",
        "resource_type": ResourceType.ui,
        "tags": ["accessible", "headless"],
        "collection_ids": [],
        "aspect_ratio": "1/1",
        "color": C["m"],
        "notes": "",
        "reason_for_saving": "Accessible dialog behaviour.",
    },
    {
        "title": "Realtime Colors",
        "domain": "realtimecolors.com",
        "url": "https://realtimecolors.com",
        "resource_type": ResourceType.tool,
        "tags": ["palette", "preview"],
        "collection_ids": [],
        "aspect_ratio": "3/2",
        "color": C["c"],
        "color2": C["f"],
        "notes": "",
        "reason_for_saving": "Test palettes on a live page.",
    },
    {
        "title": "Plumb type notes",
        "domain": "plumb.example",
        "url": "https://plumb.example",
        "resource_type": ResourceType.image,
        "tags": ["type", "indic"],
        "collection_ids": [2],
        "aspect_ratio": "5/4",
        "color": C["r"],
        "color2": C["o"],
        "notes": "Warm maroon with a figure in the foreground.",
        "reason_for_saving": "",
    },
    {
        "title": "GSAP ScrollTrigger",
        "domain": "gsap.com",
        "url": "https://gsap.com",
        "resource_type": ResourceType.animation,
        "tags": ["scroll", "js"],
        "collection_ids": [3],
        "aspect_ratio": "4/3",
        "color": C["f"],
        "is_favorite": False,
        "notes": "",
        "reason_for_saving": "Scroll-linked reveals.",
    },
    {
        "title": "Coolors",
        "domain": "coolors.co",
        "url": "https://coolors.co",
        "resource_type": ResourceType.tool,
        "tags": ["palette"],
        "collection_ids": [1],
        "aspect_ratio": "1/1",
        "color": C["y"],
        "color2": C["p"],
        "notes": "",
        "reason_for_saving": "",
    },
    {
        "title": "Forest & ochre",
        "domain": "Colour palette",
        "url": None,
        "resource_type": ResourceType.color_palette,
        "tags": ["warm", "editorial"],
        "collection_ids": [1],
        "aspect_ratio": "5/4",
        "color": "#263D32",
        "notes": "Base palette for the portfolio.",
        "reason_for_saving": "Core brand colours.",
        "colors": [
            ("Forest", "#263D32"),
            ("Ochre", "#D9A86C"),
            ("Paper", "#F1EADA"),
            ("Clay", "#B5543A"),
            ("Sky", "#8FA7C9"),
        ],
    },
    {
        "title": "Jupi muted",
        "domain": "Colour palette",
        "url": None,
        "resource_type": ResourceType.color_palette,
        "tags": ["illustration"],
        "collection_ids": [1],
        "aspect_ratio": "5/4",
        "color": "#A3A58A",
        "notes": "",
        "reason_for_saving": "Quiet olive and lilac pairing.",
        "colors": [
            ("Olive", "#A3A58A"),
            ("Lilac", "#C7B5EC"),
            ("Ink", "#2F2F2B"),
            ("Rose", "#E9A0D2"),
            ("Cream", "#EFE8D4"),
        ],
    },
    {
        "title": "Interface Craft cards",
        "domain": "Colour palette",
        "url": None,
        "resource_type": ResourceType.color_palette,
        "tags": ["cards", "bright"],
        "collection_ids": [2],
        "aspect_ratio": "5/4",
        "color": "#E8502A",
        "is_favorite": True,
        "notes": "Saturated cover colours against warm paper.",
        "reason_for_saving": "",
        "colors": [
            ("Vermilion", "#E8502A"),
            ("Azure", "#3C8FD6"),
            ("Mint", "#6CF29E"),
            ("Ink", "#1F1F1D"),
            ("Paper", "#EDE3CF"),
        ],
    },
]


def seed(force: bool = False):
    db = SessionLocal()
    try:
        existing_items = db.execute(select(Item)).scalars().first()
        existing_cols = db.execute(select(Collection)).scalars().first()

        if (existing_items or existing_cols) and not force:
            print("Database already contains data. Pass --force to re-seed or skip.")
            return

        col_map = {}
        for c_data in INITIAL_COLLECTIONS:
            existing = db.execute(
                select(Collection).where(Collection.name == c_data["name"])
            ).scalar_one_or_none()
            if existing is None:
                col = Collection(name=c_data["name"], color=c_data["color"])
                db.add(col)
                db.flush()
                col_map[c_data["id"]] = col
            else:
                col_map[c_data["id"]] = existing

        for item_data in INITIAL_ITEMS:
            existing = db.execute(
                select(Item).where(Item.title == item_data["title"])
            ).scalar_one_or_none()
            if existing is not None:
                continue

            item = Item(
                title=item_data["title"],
                domain=item_data["domain"],
                url=item_data["url"],
                resource_type=item_data["resource_type"],
                color=item_data["color"],
                color2=item_data.get("color2"),
                aspect_ratio=item_data["aspect_ratio"],
                font_family=item_data.get("font_family"),
                notes=item_data["notes"],
                reason_for_saving=item_data["reason_for_saving"],
                is_favorite=item_data.get("is_favorite", False),
            )
            item.tags = _get_or_create_tags(db, item_data.get("tags", []))
            item.collections = [
                col_map[cid] for cid in item_data.get("collection_ids", []) if cid in col_map
            ]

            if "colors" in item_data:
                for idx, (cname, chex) in enumerate(item_data["colors"]):
                    item.colors.append(
                        Color(
                            position=idx,
                            name=cname,
                            hex_value=chex,
                            source="manual",
                        )
                    )

            db.add(item)

        db.commit()
        print("Database seeded successfully with initial collections and resources.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the Design Memory database.")
    parser.add_argument("--force", action="store_true", help="Force re-seeding even if records exist")
    args = parser.parse_args()
    seed(force=args.force)
