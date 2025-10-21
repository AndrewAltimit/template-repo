"""Behavior observatory for studying AI agent decision patterns.

This module provides comprehensive analysis tools for studying autonomous AI agent behaviors,
decision-making patterns, and emergent strategies in economic environments.

Components:
- DecisionPatternAnalyzer: Analyzes long-term agent decision patterns
- LLMQualityAnalyzer: Measures LLM decision-making quality
- RiskProfiler: Profiles agent risk tolerance and crisis behaviors
- EmergentBehaviorDetector: Detects novel and unexpected agent strategies
- AnalysisReportGenerator: Generates comprehensive analysis reports
"""

from economic_agents.observatory.analysis_report import AnalysisReportGenerator, ComprehensiveAnalysis
from economic_agents.observatory.decision_analyzer import DecisionPatternAnalyzer, RiskProfile, StrategyAlignment
from economic_agents.observatory.emergent_behavior import EmergentBehaviorDetector, NovelStrategy
from economic_agents.observatory.llm_quality import (
    HallucinationDetector,
    LLMDecisionQualityAnalyzer,
    LLMQualityMetrics,
)
from economic_agents.observatory.risk_profiler import RiskProfiler, RiskTolerance

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
