"""
Deterministic Resource Category Classifier — Milestone 1B.6.

Suggests one of the 7 supported ResourceTypes:
  - website
  - image
  - type
  - ui
  - animation
  - tool
  - color_palette

Guarantees:
- Transparent rule-based classification based on domain, title, description, and URL path.
- Fast, deterministic execution without external AI dependencies or network calls.
- Returns a suggested category with confidence score ('high', 'medium', 'low').
- Defaults safely to 'website' when signals are general or absent.
"""
from typing import Optional, Tuple
from app.models.item import ResourceType


# High-confidence domain mappings
DOMAIN_MAPPINGS = {
    # Typography
    "fontsinuse.com": ResourceType.type,
    "fonts.google.com": ResourceType.type,
    "typewolf.com": ResourceType.type,
    "typography.com": ResourceType.type,
    "monotype.com": ResourceType.type,
    "myfonts.com": ResourceType.type,
    "velvetyne.fr": ResourceType.type,
    "futurefonts.xyz": ResourceType.type,
    "pangrampangram.com": ResourceType.type,
    "linotype.com": ResourceType.type,

    # UI Components & Design Systems
    "ui8.net": ResourceType.ui,
    "mobbin.com": ResourceType.ui,
    "component.gallery": ResourceType.ui,
    "shadcn.com": ResourceType.ui,
    "ui.shadcn.com": ResourceType.ui,
    "radix-ui.com": ResourceType.ui,
    "tailwindui.com": ResourceType.ui,
    "daisyui.com": ResourceType.ui,
    "ant.design": ResourceType.ui,
    "chakra-ui.com": ResourceType.ui,
    "mantine.dev": ResourceType.ui,
    "storybook.js.org": ResourceType.ui,

    # Animation & Motion
    "gsap.com": ResourceType.animation,
    "greensock.com": ResourceType.animation,
    "lottiefiles.com": ResourceType.animation,
    "threejs.org": ResourceType.animation,
    "framer.com/motion": ResourceType.animation,
    "motion.dev": ResourceType.animation,
    "codrops.com": ResourceType.animation,
    "tympanus.net": ResourceType.animation,

    # Color Palettes
    "coolors.co": ResourceType.color_palette,
    "colorhunt.co": ResourceType.color_palette,
    "paletton.com": ResourceType.color_palette,
    "khroma.co": ResourceType.color_palette,
    "colors.co": ResourceType.color_palette,

    # Tools & Utilities
    "figma.com": ResourceType.tool,
    "svgomg.net": ResourceType.tool,
    "squoosh.app": ResourceType.tool,
    "regex101.com": ResourceType.tool,
    "transform.tools": ResourceType.tool,
    "css-tricks.com": ResourceType.tool,

    # Imagery & Icons
    "unsplash.com": ResourceType.image,
    "pexels.com": ResourceType.image,
    "pixabay.com": ResourceType.image,
    "nounproject.com": ResourceType.image,
    "thenounproject.com": ResourceType.image,
    "feathericons.com": ResourceType.image,
    "lucide.dev": ResourceType.image,
    "heroicons.com": ResourceType.image,
}

# Keyword signals with associated weights
KEYWORD_RULES = [
    # Color palette
    (ResourceType.color_palette, [
        "color palette", "color scheme", "colour palette", "palette generator",
        "swatches", "hex codes", "color inspiration", "color harmony"
    ]),
    # Type / Typography
    (ResourceType.type, [
        "typography", "typeface", "typefaces", "font specimen", "variable font",
        "type foundry", "foundry", "serif", "sans-serif", "kerning", "ligatures",
        "monospaced font", "display font", "webfont", "lettering"
    ]),
    # UI Components
    (ResourceType.ui, [
        "design system", "component library", "ui components", "ui kit",
        "react components", "vue components", "button styles", "form elements",
        "modal pattern", "accessible components", "ui pattern", "micro-components"
    ]),
    # Animation & Interactions
    (ResourceType.animation, [
        "webgl", "three.js", "shader", "micro-interaction", "motion design",
        "css animation", "scroll animation", "page transition", "lottie animation",
        "gsap animation", "interactive canvas"
    ]),
    # Tools & Generators
    (ResourceType.tool, [
        "generator", "converter", "optimizer", "linter", "formatter",
        "color picker tool", "css generator", "developer tool", "cli tool",
        "utility for", "calculator", "compressor", "inspect tool"
    ]),
    # Imagery & Icons
    (ResourceType.image, [
        "stock photos", "free photography", "royalty-free images", "icon set",
        "vector icons", "svg icons", "3d illustrations", "photo gallery"
    ]),
]


def suggest_category(
    url: Optional[str] = None,
    domain: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
) -> Tuple[ResourceType, str]:
    """
    Classify a resource into a ResourceType.
    Returns: (suggested_type, confidence) where confidence is 'high', 'medium', or 'low'.
    """
    # 1. Exact or subdomain matching on known authoritative domains
    clean_dom = (domain or "").strip().lower().removeprefix("www.")
    if clean_dom:
        for mapped_dom, rtype in DOMAIN_MAPPINGS.items():
            if clean_dom == mapped_dom or clean_dom.endswith("." + mapped_dom):
                return rtype, "high"

    # Also check URL path against specific domain rules (e.g., framer.com/motion)
    if url:
        url_lower = url.lower()
        for mapped_dom, rtype in DOMAIN_MAPPINGS.items():
            if "/" in mapped_dom and mapped_dom in url_lower:
                return rtype, "high"

    # 2. Text keyword matching across title, description, and URL path
    text_corpus = " ".join([
        (title or ""),
        (description or ""),
        (url or ""),
        (domain or ""),
    ]).lower()

    if not text_corpus.strip():
        return ResourceType.website, "low"

    scores = {rtype: 0 for rtype in ResourceType}

    for rtype, keywords in KEYWORD_RULES:
        for kw in keywords:
            if kw in text_corpus:
                # Title matches have higher weight than description
                if title and kw in title.lower():
                    scores[rtype] += 3
                else:
                    scores[rtype] += 1

    # Find category with highest positive score
    best_type = max(scores, key=lambda k: scores[k])
    best_score = scores[best_type]

    if best_score >= 3:
        return best_type, "high"
    elif best_score >= 1:
        return best_type, "medium"

    # Default to website for design blogs, agencies, portfolios, general links
    return ResourceType.website, "low"
