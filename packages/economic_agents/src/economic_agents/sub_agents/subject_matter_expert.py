"""Subject matter expert sub-agent for specialized knowledge."""

from typing import Any, Dict, List

from economic_agents.sub_agents.base_agent import SubAgent


class SubjectMatterExpert(SubAgent):
    """Subject matter expert providing specialized knowledge and guidance."""

    def __init__(self, agent_id: str, specialization: str):
        """Initialize subject matter expert.

        Args:
            agent_id: Unique identifier
            specialization: Domain expertise (e.g., "machine-learning", "security", "scaling")
        """
        super().__init__(
            id=agent_id,
            role="sme",
            specialization=specialization,
        )
        # Knowledge base specific to specialization
        self.knowledge_base = self._initialize_knowledge_base()

    def _initialize_knowledge_base(self) -> Dict[str, Any]:
        """Initialize domain-specific knowledge base.

        Returns:
            Knowledge base with best practices, tools, and patterns
        """
        spec = self.specialization.lower()

        if "security" in spec or "cybersecurity" in spec:
            return {
                "best_practices": [
                    "Implement OAuth 2.0 or OpenID Connect for authentication",
                    "Use bcrypt/argon2 for password hashing (min 12 rounds)",
                    "Enable HTTPS with TLS 1.3, disable older protocols",
                    "Implement rate limiting (100 req/min per IP)",
                    "Use parameterized queries to prevent SQL injection",
                    "Apply principle of least privilege to all services",
                    "Regular penetration testing (quarterly minimum)",
                ],
                "tools": ["OWASP ZAP", "Burp Suite", "Snyk", "SonarQube", "HashiCorp Vault"],
                "risks": [
                    {"risk": "SQL Injection", "severity": "critical", "mitigation": "Parameterized queries"},
                    {"risk": "XSS attacks", "severity": "high", "mitigation": "Input sanitization + CSP headers"},
                    {"risk": "Auth bypass", "severity": "critical", "mitigation": "Multi-factor authentication"},
                ],
                "metrics": ["Vulnerability count", "Mean time to patch", "Failed login attempts"],
            }

        elif "scaling" in spec or "performance" in spec:
            return {
                "best_practices": [
                    "Implement Redis/Memcached caching (hit rate >80%)",
                    "Use CDN for static assets (CloudFlare, Fastly)",
                    "Database read replicas for read-heavy workloads",
                    "Horizontal scaling with load balancers (Nginx, HAProxy)",
                    "Async processing for long-running tasks (Celery, RabbitMQ)",
                    "Database connection pooling (pgBouncer, HikariCP)",
                    "Query optimization and indexing (explain plans)",
                ],
                "tools": ["Kubernetes", "Redis", "Nginx", "Prometheus", "Grafana", "New Relic"],
                "risks": [
                    {"risk": "Database bottleneck", "severity": "high", "mitigation": "Read replicas + caching"},
                    {"risk": "Memory leaks", "severity": "medium", "mitigation": "Monitoring + regular restarts"},
                    {"risk": "N+1 queries", "severity": "high", "mitigation": "Eager loading + query batching"},
                ],
                "metrics": ["Response time p95", "Throughput (req/sec)", "Cache hit rate", "CPU/Memory usage"],
            }

        elif "machine-learning" in spec or "ai" in spec or "ml" in spec:
            return {
                "best_practices": [
                    "Start with pre-trained models (BERT, GPT, ResNet)",
                    "Data quality > model complexity (80/20 rule)",
                    "Train/validation/test split (70/15/15 or 60/20/20)",
                    "Track experiments with MLflow or Weights & Biases",
                    "Version control datasets (DVC, LakeFS)",
                    "Monitor model drift in production (Evidently AI)",
                    "A/B test model changes before full rollout",
                ],
                "tools": ["PyTorch", "TensorFlow", "Hugging Face", "MLflow", "Kubeflow", "Jupyter"],
                "risks": [
                    {"risk": "Model bias", "severity": "high", "mitigation": "Fairness audits + diverse data"},
                    {"risk": "Overfitting", "severity": "medium", "mitigation": "Cross-validation + regularization"},
                    {"risk": "Data leakage", "severity": "critical", "mitigation": "Proper train/test separation"},
                ],
                "metrics": ["Accuracy", "Precision/Recall", "F1 score", "AUC-ROC", "Training time"],
            }

        elif "devops" in spec or "sre" in spec:
            return {
                "best_practices": [
                    "Infrastructure as code (Terraform, Pulumi)",
                    "CI/CD pipelines with automated testing",
                    "Container orchestration (Kubernetes)",
                    "Observability: metrics, logs, traces (3 pillars)",
                    "Incident response runbooks and on-call rotation",
                    "Chaos engineering for resilience testing",
                    "Blue-green or canary deployments",
                ],
                "tools": ["Kubernetes", "Terraform", "Docker", "Jenkins", "Prometheus", "ELK Stack"],
                "risks": [
                    {"risk": "Deployment failures", "severity": "high", "mitigation": "Rollback strategy + canary"},
                    {"risk": "Config drift", "severity": "medium", "mitigation": "IaC + state management"},
                    {"risk": "Alert fatigue", "severity": "medium", "mitigation": "Alert tuning + SLO-based alerts"},
                ],
                "metrics": ["Deployment frequency", "MTTR", "Change failure rate", "Uptime %"],
            }

        elif "data" in spec or "database" in spec:
            return {
                "best_practices": [
                    "Choose database based on access patterns (SQL vs NoSQL)",
                    "Normalize to 3NF for transactional data",
                    "Denormalize for read-heavy analytics workloads",
                    "Index foreign keys and WHERE clause columns",
                    "Implement database backups (daily + point-in-time recovery)",
                    "Use connection pooling to manage connections",
                    "Monitor slow queries and optimize (explain plans)",
                ],
                "tools": ["PostgreSQL", "MongoDB", "Redis", "Elasticsearch", "dbt", "Airflow"],
                "risks": [
                    {"risk": "Data loss", "severity": "critical", "mitigation": "Automated backups + replication"},
                    {"risk": "Slow queries", "severity": "high", "mitigation": "Indexing + query optimization"},
                    {"risk": "Data inconsistency", "severity": "high", "mitigation": "Transactions + constraints"},
                ],
                "metrics": ["Query response time", "Connection pool usage", "Replication lag", "Disk usage"],
            }

        elif "frontend" in spec or "ui" in spec or "ux" in spec:
            return {
                "best_practices": [
                    "Mobile-first responsive design",
                    "Accessibility compliance (WCAG 2.1 Level AA)",
                    "Component-based architecture (React, Vue, Svelte)",
                    "State management for complex UIs (Redux, Zustand)",
                    "Performance budgets (<3s initial load, <100ms interactions)",
                    "Progressive web app capabilities (offline, installable)",
                    "User testing with 5-8 representative users",
                ],
                "tools": ["React", "TypeScript", "Tailwind CSS", "Storybook", "Figma", "Cypress"],
                "risks": [
                    {"risk": "Poor mobile UX", "severity": "high", "mitigation": "Mobile-first design + testing"},
                    {"risk": "Accessibility gaps", "severity": "high", "mitigation": "ARIA labels + screen reader tests"},
                    {"risk": "Slow page loads", "severity": "medium", "mitigation": "Code splitting + lazy loading"},
                ],
                "metrics": ["Page load time", "Time to interactive", "Lighthouse score", "Conversion rate"],
            }

        else:
            # Generic knowledge base
            return {
                "best_practices": [
                    f"Follow {self.specialization} industry standards",
                    "Implement comprehensive testing",
                    "Document architectural decisions",
                ],
                "tools": ["Standard industry tools"],
                "risks": [],
                "metrics": ["Quality score", "Time to completion"],
            }

    def provide_expertise(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Provide expert advice on a question.

        Args:
            question: Question requiring expert input
            context: Additional context

        Returns:
            Expert advice
        """
        self.tasks_completed += 1

        question_lower = question.lower()
        kb = self.knowledge_base

        # Determine question type and provide targeted advice
        if "how" in question_lower or "implement" in question_lower:
            # Implementation guidance
            relevant_practices = kb["best_practices"][:3]
            recommended_tools = kb["tools"][:3]

            return {
                "advice": f"{self.specialization.title()} implementation guidance",
                "practices": relevant_practices,
                "recommended_tools": recommended_tools,
                "priority": "high",
                "confidence": 0.9,
                "references": [f"{self.specialization} best practices", "Industry standards"],
            }

        elif "risk" in question_lower or "problem" in question_lower or "issue" in question_lower:
            # Risk assessment
            return {
                "advice": f"Key {self.specialization} risks to address",
                "risks": (
                    kb["risks"]
                    if kb["risks"]
                    else [{"risk": "Implementation challenges", "severity": "medium", "mitigation": "Careful planning"}]
                ),
                "mitigation_strategies": (
                    [r["mitigation"] for r in kb["risks"][:3]] if kb["risks"] else ["Follow best practices"]
                ),
                "priority": "high",
                "confidence": 0.85,
            }

        elif "tool" in question_lower or "technology" in question_lower or "stack" in question_lower:
            # Technology recommendations
            return {
                "advice": f"Recommended {self.specialization} technology stack",
                "recommended_stack": kb["tools"],
                "rationale": f"Industry-proven tools for {self.specialization}",
                "priority": "medium",
                "confidence": 0.88,
            }

        elif "metric" in question_lower or "measure" in question_lower or "kpi" in question_lower:
            # Metrics and measurement
            return {
                "advice": f"Key {self.specialization} metrics to track",
                "metrics": kb.get("metrics", ["Quality score"]),
                "measurement_approach": "Automated monitoring with alerting thresholds",
                "priority": "medium",
                "confidence": 0.82,
            }

        else:
            # General best practices
            return {
                "advice": f"{self.specialization.title()} domain expertise",
                "best_practices": kb["best_practices"][:5],
                "tools": kb["tools"][:3],
                "priority": "high",
                "confidence": 0.85,
                "references": [f"{self.specialization} documentation", "Industry standards"],
            }

    def analyze_tradeoffs(self, option_a: str, option_b: str, criteria: List[str]) -> Dict[str, Any]:
        """Analyze tradeoffs between two technical options.

        Args:
            option_a: First option to compare
            option_b: Second option to compare
            criteria: Evaluation criteria (e.g., ["performance", "cost", "complexity"])

        Returns:
            Tradeoff analysis with recommendation
        """
        spec = self.specialization.lower()

        # Example tradeoff analysis based on specialization
        if "database" in spec or "data" in spec:
            analysis = {
                "option_a": {
                    "name": option_a,
                    "performance": 8 if "sql" in option_a.lower() else 7,
                    "cost": 6,
                    "complexity": 7,
                    "scalability": 7 if "sql" in option_a.lower() else 9,
                },
                "option_b": {
                    "name": option_b,
                    "performance": 7 if "sql" in option_b.lower() else 8,
                    "cost": 6,
                    "complexity": 7,
                    "scalability": 7 if "sql" in option_b.lower() else 9,
                },
            }

            recommendation = option_a if "sql" in option_a.lower() and "transaction" in str(criteria).lower() else option_b

        elif "security" in spec:
            analysis = {
                "option_a": {
                    "name": option_a,
                    "security": 8,
                    "usability": 6,
                    "implementation_time": 7,
                },
                "option_b": {
                    "name": option_b,
                    "security": 7,
                    "usability": 8,
                    "implementation_time": 6,
                },
            }

            recommendation = option_a  # Prioritize security

        else:
            analysis = {
                "option_a": {"name": option_a, "score": 7},
                "option_b": {"name": option_b, "score": 7},
            }
            recommendation = option_a

        return {
            "analysis": analysis,
            "recommendation": recommendation,
            "reasoning": f"Based on {self.specialization} priorities and criteria: {criteria}",
            "confidence": 0.78,
        }

    def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make technical recommendation.

        Args:
            context: Decision context

        Returns:
            Technical recommendation
        """
        self.decisions_made += 1

        decision_type = context.get("decision_type", "general")
        constraints = context.get("constraints", {})

        kb = self.knowledge_base

        if decision_type == "technology_selection":
            # Recommend technology stack based on constraints
            budget = constraints.get("budget", "medium")
            timeline = constraints.get("timeline", "normal")

            # Prioritize based on constraints
            if budget == "low" and timeline == "fast":
                tools = ["Open source alternatives"] + kb["tools"][:2]
                approach = "Use proven, low-cost tools for rapid deployment"
            elif budget == "high":
                tools = kb["tools"]
                approach = "Invest in enterprise-grade tools for long-term success"
            else:
                tools = kb["tools"][:3]
                approach = "Balance cost and capability with selective tool choices"

            return {
                "decision": "select_technology_stack",
                "reasoning": f"{self.specialization} analysis based on budget and timeline",
                "recommended_stack": tools,
                "approach": approach,
                "confidence": 0.82,
                "estimated_setup_time": "2-4 weeks" if timeline == "fast" else "4-8 weeks",
            }

        elif decision_type == "architecture":
            # Architecture recommendation
            scale = constraints.get("expected_scale", "medium")

            if scale in ("high", "large"):
                architecture = "Microservices with event-driven communication"
                practices = kb["best_practices"][:3]
            elif scale in ("low", "small"):
                architecture = "Monolithic with modular design"
                practices = kb["best_practices"][3:6] if len(kb["best_practices"]) > 3 else kb["best_practices"]
            else:
                architecture = "Modular monolith with potential for extraction"
                practices = kb["best_practices"][:4]

            return {
                "decision": "architecture_pattern",
                "reasoning": f"Based on {scale} scale requirements and {self.specialization} expertise",
                "recommended_architecture": architecture,
                "key_practices": practices,
                "confidence": 0.85,
            }

        else:
            # General recommendation
            return {
                "decision": "follow_best_practices",
                "reasoning": f"Apply {self.specialization} industry standards",
                "best_practices": kb["best_practices"][:5],
                "tools": kb["tools"][:3],
                "confidence": 0.8,
            }
