"""Project templates — spec §15.2."""

TEMPLATES = {
    "saas": {
        "name": "SaaS Dashboard",
        "stack": "Next.js + Node/Express + PostgreSQL + Stripe + Tailwind",
        "features": ["auth", "billing", "team mgmt", "dashboard charts", "settings"],
    },
    "ecommerce": {
        "name": "E-Commerce Storefront",
        "stack": "Next.js + Node/Express + PostgreSQL + Stripe Checkout",
        "features": ["catalog", "cart", "checkout", "orders", "admin"],
    },
    "mobile-api": {
        "name": "Mobile API Backend",
        "stack": "FastAPI + PostgreSQL + Redis + JWT",
        "features": ["auth", "users", "push notifications", "analytics", "admin"],
    },
}


def expand_brief(brief: str, template_id: str) -> str:
    t = TEMPLATES.get(template_id)
    if not t:
        return brief
    return (
        f"{brief}\n\n[TEMPLATE: {t['name']}]\n"
        f"Stack: {t['stack']}\n"
        f"Required features: {', '.join(t['features'])}"
    )
