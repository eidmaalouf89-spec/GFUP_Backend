"""
src/consultant_ingest/__init__.py
JANSA VISASIST — Consultant Ingestion Package

Public API:
    from src.consultant_ingest.consultant_report_builder import build_consultant_reports
"""

from .consultant_report_builder import build_consultant_reports

__all__ = ["build_consultant_reports"]
