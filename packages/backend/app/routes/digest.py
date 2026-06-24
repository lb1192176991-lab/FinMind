"""Weekly financial digest route."""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..services.weekly_digest import generate_digest
import logging

bp = Blueprint("digest", __name__)
logger = logging.getLogger("finmind.digest")


@bp.get("/weekly-digest")
@jwt_required()
def weekly_digest():
    uid = int(get_jwt_identity())
    week = (request.args.get("week") or None)
    user_gemini_key = (request.headers.get("X-Gemini-Api-Key") or "").strip() or None
    persona = (request.headers.get("X-Insight-Persona") or "").strip() or None
    digest = generate_digest(uid, week_date=week, gemini_api_key=user_gemini_key)
    logger.info("Weekly digest served user=%s week=%s", uid, week or "this")
    return jsonify(digest)
