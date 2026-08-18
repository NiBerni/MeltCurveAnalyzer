"""
Application factory for the Flask server.
"""

from flask import Flask, Response
from flask_jwt_extended import JWTManager

from app.api.routes import api_bp
from app.config import JWT_SECRET_KEY


def create_app() -> Flask:
    """Application factory for the PCR Analyzer LIMS."""
    app = Flask("pcr_analyzer_mvp")

    # Core Configuration - Holt den Key dynamisch aus den Umgebungsvariablen
    app.config["JWT_SECRET_KEY"] = JWT_SECRET_KEY

    # Initialize Extensions
    JWTManager(app)

    # Register Blueprint Layer
    app.register_blueprint(api_bp)

    # Global Compliance Guardrail (Research Use Only Banner)
    @app.after_request
    def inject_compliance_headers(response: Response) -> Response:
        response.headers["X-Compliance-Notice"] = (
            "DEMO ENVIRONMENT - RESEARCH USE ONLY. Not for diagnostic procedures."
        )
        return response

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)
