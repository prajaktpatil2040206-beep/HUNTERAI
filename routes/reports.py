"""
HunterAI - Report Generation Routes
"""

from flask import Blueprint, request, jsonify, send_file

from core.report_generator import report_generator
from core.vuln_detector import vuln_detector

reports_bp = Blueprint("reports", __name__)


@reports_bp.route("/api/reports/generate", methods=["POST"])
def generate_report():
    """Generate a vulnerability report for a hunt."""
    data = request.get_json()
    hunt_id = data.get("hunt_id")
    title = data.get("title", "HunterAI Security Report")
    target = data.get("target", "Unknown Target")
    report_format = data.get("format", "html")

    if not hunt_id:
        return jsonify({"error": "hunt_id is required"}), 400

    # Get findings for this hunt
    findings = vuln_detector.get_findings(hunt_id)
    severity = vuln_detector.get_severity_summary(hunt_id)

    # Generate report
    report = report_generator.generate(
        hunt_id=hunt_id,
        title=title,
        target=target,
        findings=findings,
        severity_summary=severity,
        report_format=report_format
    )

    return jsonify({"success": True, "report": report})


@reports_bp.route("/api/reports", methods=["GET"])
def list_reports():
    """List all reports."""
    hunt_id = request.args.get("hunt_id")
    reports = report_generator.list_reports(hunt_id=hunt_id)
    return jsonify({"reports": reports})


@reports_bp.route("/api/reports/<report_id>", methods=["GET"])
def get_report(report_id):
    """Get report metadata and content."""
    report = report_generator.get_report(report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404

    content = report_generator.get_report_content(report_id)
    return jsonify({"report": report, "content": content})


@reports_bp.route("/api/reports/<report_id>/download", methods=["GET"])
def download_report(report_id):
    """Download a report file."""
    report = report_generator.get_report(report_id)
    if not report:
        return jsonify({"error": "Report not found"}), 404

    file_path = report.get("file_path")
    if file_path and __import__("os").path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    return jsonify({"error": "Report file not found"}), 404
