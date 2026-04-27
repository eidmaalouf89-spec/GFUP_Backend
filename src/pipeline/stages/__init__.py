"""
src/pipeline/stages — Pipeline stage functions.

Each stage reads from and writes to a PipelineState context object.
"""

from pipeline.stages.stage_init_run import stage_init_run
from pipeline.stages.stage_read import stage_read
from pipeline.stages.stage_read_flat import stage_read_flat
from pipeline.stages.stage_normalize import stage_normalize
from pipeline.stages.stage_version import stage_version
from pipeline.stages.stage_route import stage_route
from pipeline.stages.stage_report_memory import stage_report_memory
from pipeline.stages.stage_write_gf import stage_write_gf
from pipeline.stages.stage_build_team_version import stage_build_team_version
from pipeline.stages.stage_discrepancy import stage_discrepancy
from pipeline.stages.stage_diagnosis import stage_diagnosis
from pipeline.stages.stage_finalize_run import stage_finalize_run

__all__ = [
    "stage_init_run",
    "stage_read",
    "stage_read_flat",
    "stage_normalize",
    "stage_version",
    "stage_route",
    "stage_report_memory",
    "stage_write_gf",
    "stage_build_team_version",
    "stage_discrepancy",
    "stage_diagnosis",
    "stage_finalize_run",
]
