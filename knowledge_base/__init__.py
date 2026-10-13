"""
KNOWLEDGE_BASE
==============
TikTok Knowledge Base & Policy Guardrails module.
"""

from .validator import PolicyValidator, validate_script, validate_text, get_default_validator
from .loader import (
    load_hooks_library,
    load_cta_templates,
    load_prohibited_words,
    load_brand_guidelines,
    get_formatted_hooks_for_prompt,
    get_formatted_ctas_for_prompt,
    get_brand_guidelines_summary,
    get_policy_rules_summary,
)

__all__ = [
    "PolicyValidator",
    "validate_script",
    "validate_text",
    "get_default_validator",
    "load_hooks_library",
    "load_cta_templates",
    "load_prohibited_words",
    "load_brand_guidelines",
    "get_formatted_hooks_for_prompt",
    "get_formatted_ctas_for_prompt",
    "get_brand_guidelines_summary",
    "get_policy_rules_summary",
]
