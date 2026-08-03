from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from flask import Flask


def init_app(app: "Flask", url_prefix: str = "/salary-comparison") -> None:
    """Register the module with an existing Flask application."""
    from .routes import bp
    app.register_blueprint(bp, url_prefix=url_prefix)


def get_blueprint() -> Any:
    """Return the Blueprint for projects that prefer explicit registration."""
    from .routes import bp
    return bp


__all__ = ["init_app", "get_blueprint"]
