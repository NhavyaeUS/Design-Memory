"""Unit tests for Resource Category Classifier — Milestone 1B.6."""
from app.core.classifier import suggest_category
from app.models.item import ResourceType


def test_classifier_known_domains():
    """Authoritative domains resolve with high confidence."""
    assert suggest_category(domain="fontsinuse.com")[0] == ResourceType.type
    assert suggest_category(domain="coolors.co")[0] == ResourceType.color_palette
    assert suggest_category(domain="gsap.com")[0] == ResourceType.animation
    assert suggest_category(domain="unsplash.com")[0] == ResourceType.image
    assert suggest_category(domain="svgomg.net")[0] == ResourceType.tool
    assert suggest_category(domain="component.gallery")[0] == ResourceType.ui


def test_classifier_keyword_signals():
    """Text signals classify correctly according to keywords."""
    cat, conf = suggest_category(
        title="Radix UI — Accessible, unstyled React components for design systems",
        description="A library of headless primitives.",
    )
    assert cat == ResourceType.ui
    assert conf in ("high", "medium")

    cat, _ = suggest_category(
        title="Baskerville Specimen & Variable Font Foundry",
        description="A traditional serif typeface for editorial design.",
    )
    assert cat == ResourceType.type

    cat, _ = suggest_category(
        title="Creative WebGL and Three.js Shader Interactions",
        description="Smooth 3D page transitions and interactive canvas experiments.",
    )
    assert cat == ResourceType.animation

    cat, _ = suggest_category(
        title="Harmonious Pastel Color Schemes and Swatches",
        description="Find complementary hex codes for UI design.",
    )
    assert cat == ResourceType.color_palette

    cat, _ = suggest_category(
        title="Online SVG Optimizer and Path Compressor",
        description="A handy developer tool for cleaning vector files.",
    )
    assert cat == ResourceType.tool


def test_classifier_default_fallback_website():
    """Ambiguous or general agency/portfolio sites safely default to website."""
    cat, conf = suggest_category(
        domain="pentagram.com",
        title="Pentagram Design Studio",
        description="A multi-disciplinary independent design partnership.",
    )
    assert cat == ResourceType.website
    assert conf in ("low", "medium")
