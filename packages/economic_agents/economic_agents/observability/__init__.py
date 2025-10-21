"""Observability and auditing for studying AI agent decision patterns.

This module provides comprehensive observability metrics and auditing tools for studying autonomous
AI agent behaviors, decision-making patterns, and emergent strategies in economic environments.

Components:
- DecisionPatternAnalyzer: Analyzes long-term agent decision patterns
- LLMQualityAnalyzer: Measures LLM decision-making quality
- RiskProfiler: Profiles agent risk tolerance and crisis behaviors
- EmergentBehaviorDetector: Detects novel and unexpected agent strategies
- AnalysisReportGenerator: Generates comprehensive analysis reports
"""

from economic_agents.observability.analysis_report import AnalysisReportGenerator, ComprehensiveAnalysis
from economic_agents.observability.decision_analyzer import DecisionPatternAnalyzer, RiskProfile, StrategyAlignment
from economic_agents.observability.emergent_behavior import EmergentBehaviorDetector, NovelStrategy
from economic_agents.observability.llm_quality import (
    HallucinationDetector,
    LLMDecisionQualityAnalyzer,
    LLMQualityMetrics,
)
from economic_agents.observability.risk_profiler import RiskProfiler, RiskTolerance

__all__ = [
    "DecisionPatternAnalyzer",
    "LLMDecisionQualityAnalyzer",
    "RiskProfiler",
    "EmergentBehaviorDetector",
    "AnalysisReportGenerator",
    "RiskProfile",
    "StrategyAlignment",
    "LLMQualityMetrics",
    "HallucinationDetector",
    "RiskTolerance",
    "NovelStrategy",
    "ComprehensiveAnalysis",
]
