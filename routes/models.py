"""
HunterAI - AI Model Management Routes
"""

from flask import Blueprint, request, jsonify
from core.ai_manager import ai_manager, PROVIDERS

models_bp = Blueprint("models", __name__)


@models_bp.route("/api/models", methods=["GET"])
def list_models():
    """List all configured AI models."""
    models = ai_manager.list_models()
    return jsonify({"models": models})


@models_bp.route("/api/models", methods=["POST"])
def add_model():
    """Add a new AI model."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    provider = data.get("provider")
    api_key = data.get("api_key", "")
    model_name = data.get("model_name")
    custom_url = data.get("custom_url")
    display_name = data.get("display_name")

    if not provider:
        return jsonify({"error": "Provider is required"}), 400

    model_id, model_data = ai_manager.add_model(
        provider=provider,
        api_key=api_key,
        model_name=model_name,
        custom_url=custom_url,
        display_name=display_name
    )

    return jsonify({
        "success": True,
        "model_id": model_id,
        "model": {
            "_id": model_id,
            "provider": model_data["provider"],
            "model_name": model_data["model_name"],
            "display_name": model_data["display_name"],
            "is_active": model_data["is_active"]
        }
    }), 201


@models_bp.route("/api/models/test", methods=["POST"])
def test_model():
    """Test an API key for a provider."""
    data = request.get_json()
    provider = data.get("provider")
    api_key = data.get("api_key", "")
    model_name = data.get("model_name")
    custom_url = data.get("custom_url")

    if not provider or not api_key:
        return jsonify({"error": "Provider and API key are required"}), 400

    success, message = ai_manager.test_model(
        provider=provider,
        api_key=api_key,
        model_name=model_name,
        custom_url=custom_url
    )

    return jsonify({"success": success, "message": message})


@models_bp.route("/api/models/<model_id>/active", methods=["PUT"])
def set_active_model(model_id):
    """Set the active AI model."""
    if ai_manager.set_active_model(model_id):
        return jsonify({"success": True})
    return jsonify({"error": "Model not found"}), 404


@models_bp.route("/api/models/<model_id>", methods=["DELETE"])
def delete_model(model_id):
    """Delete an AI model."""
    if ai_manager.delete_model(model_id):
        return jsonify({"success": True})
    return jsonify({"error": "Model not found"}), 404


@models_bp.route("/api/models/providers", methods=["GET"])
def list_providers():
    """List all supported AI providers."""
    providers = []
    for key, config in PROVIDERS.items():
        providers.append({
            "id": key,
            "name": config["name"],
            "models": config["models"],
            "type": config["type"],
            "base_url": config.get("base_url", ""),
            "free_tier": config.get("free_tier", False),
            "notes": config.get("notes", "")
        })
    return jsonify({"providers": providers})


@models_bp.route("/api/models/active", methods=["GET"])
def get_active_model():
    """Get the currently active model."""
    model = ai_manager.get_active_model()
    if model:
        # Don't expose encrypted key
        if "api_key_encrypted" in model:
            del model["api_key_encrypted"]
        return jsonify({"model": model})
    return jsonify({"model": None})
