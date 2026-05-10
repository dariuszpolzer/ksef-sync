from pathlib import Path

from tools.ai_snapshot.config import (
    AI_INSTRUCTIONS,
    COMMON_AI_PITFALLS,
    CRITICAL_BUSINESS_RULES,
    CURRENT_STATUS,
    DATA_FLOW,
    DOMAIN_OBJECTS_CONTEXT,
    FILE_METADATA_CONTEXT,
    MODULE_RESPONSIBILITIES,
    MODULE_SUMMARY_CONTEXT,
    PIPELINE_ARCHITECTURE_CONTEXT,
    PROJECT_ARCHITECTURE,
    PROJECT_CONTEXT,
    SECRET_SENSITIVE_CONTEXT,
    SYSTEM_INVARIANTS,
)


def build_sections(
    root: Path,
    files: list[Path],
    deps,
    secret_warnings,
    render_dependencies,
    render_domain_objects,
    render_file_metadata,
    render_module_summaries,
    render_secret_warnings,
    render_tooling_context,
):
    return [
        AI_INSTRUCTIONS,
        CURRENT_STATUS,
        PROJECT_CONTEXT,
        PROJECT_ARCHITECTURE,
        SYSTEM_INVARIANTS,
        MODULE_RESPONSIBILITIES,
        COMMON_AI_PITFALLS,
        CRITICAL_BUSINESS_RULES,
        PIPELINE_ARCHITECTURE_CONTEXT,
        DATA_FLOW,
        SECRET_SENSITIVE_CONTEXT,
        render_secret_warnings(secret_warnings),
        render_tooling_context(root),
        render_dependencies(deps),
        MODULE_SUMMARY_CONTEXT,
        render_module_summaries(root, files),
        DOMAIN_OBJECTS_CONTEXT,
        render_domain_objects(root, files),
        FILE_METADATA_CONTEXT,
        render_file_metadata(root, files),
    ]
