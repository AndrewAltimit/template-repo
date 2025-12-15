"""Individual contributor sub-agent for task execution."""

from typing import Any, Dict, List

from economic_agents.sub_agents.base_agent import SubAgent


class IndividualContributor(SubAgent):
    """Individual contributor responsible for hands-on task execution."""

    def __init__(self, agent_id: str, specialization: str):
        """Initialize individual contributor.

        Args:
            agent_id: Unique identifier
            specialization: Skill area (e.g., "backend-dev", "frontend-dev", "qa", "devops")
        """
        super().__init__(
            id=agent_id,
            role="ic",
            specialization=specialization,
        )

    def estimate_task(self, task_description: str, complexity: str = "medium") -> Dict[str, Any]:
        """Estimate effort and breakdown task.

        Args:
            task_description: Description of the task
            complexity: Task complexity (low, medium, high)

        Returns:
            Task estimation with breakdown
        """
        # Effort estimates in hours by complexity
        base_hours = {"low": 4, "medium": 12, "high": 24}
        hours = base_hours.get(complexity, 12)

        # Add specialization-specific adjustments
        if "backend" in self.specialization.lower():
            multiplier = 1.2 if "database" in task_description.lower() else 1.0
        elif "frontend" in self.specialization.lower():
            multiplier = 1.3 if "responsive" in task_description.lower() or "animation" in task_description.lower() else 1.0
        elif "qa" in self.specialization.lower():
            multiplier = 1.1 if complexity == "high" else 0.9
        else:
            multiplier = 1.0

        adjusted_hours = hours * multiplier

        # Break down into subtasks
        subtasks = self._generate_subtasks(task_description, complexity)

        return {
            "estimated_hours": round(adjusted_hours, 1),
            "complexity": complexity,
            "subtasks": subtasks,
            "confidence": 0.75 if complexity == "high" else 0.85,
            "specialization": self.specialization,
        }

    def _generate_subtasks(self, task_description: str, complexity: str) -> List[Dict[str, Any]]:
        """Generate subtask breakdown based on specialization.

        Args:
            task_description: Task description
            complexity: Complexity level

        Returns:
            List of subtasks
        """
        spec = self.specialization.lower()

        if "backend" in spec:
            subtasks = [
                {"name": "Design API endpoints", "hours": 2, "priority": "high"},
                {"name": "Implement business logic", "hours": 4, "priority": "high"},
                {"name": "Write unit tests", "hours": 3, "priority": "high"},
                {"name": "Add error handling", "hours": 2, "priority": "medium"},
                {"name": "Document API", "hours": 1, "priority": "low"},
            ]
        elif "frontend" in spec:
            subtasks = [
                {"name": "Create component structure", "hours": 2, "priority": "high"},
                {"name": "Implement UI logic", "hours": 4, "priority": "high"},
                {"name": "Add styling & responsive design", "hours": 3, "priority": "medium"},
                {"name": "Write component tests", "hours": 2, "priority": "high"},
                {"name": "Accessibility check", "hours": 1, "priority": "medium"},
            ]
        elif "qa" in spec:
            subtasks = [
                {"name": "Create test plan", "hours": 2, "priority": "high"},
                {"name": "Write test cases", "hours": 4, "priority": "high"},
                {"name": "Execute tests", "hours": 3, "priority": "high"},
                {"name": "Report bugs", "hours": 2, "priority": "high"},
                {"name": "Verify fixes", "hours": 1, "priority": "medium"},
            ]
        elif "devops" in spec:
            subtasks = [
                {"name": "Infrastructure setup", "hours": 3, "priority": "high"},
                {"name": "Configure CI/CD pipeline", "hours": 3, "priority": "high"},
                {"name": "Set up monitoring", "hours": 2, "priority": "high"},
                {"name": "Security hardening", "hours": 2, "priority": "medium"},
                {"name": "Documentation", "hours": 2, "priority": "low"},
            ]
        else:
            subtasks = [
                {"name": "Planning", "hours": 2, "priority": "high"},
                {"name": "Implementation", "hours": 6, "priority": "high"},
                {"name": "Testing", "hours": 3, "priority": "high"},
                {"name": "Documentation", "hours": 1, "priority": "low"},
            ]

        # Adjust for complexity
        if complexity == "low":
            return subtasks[:3]
        if complexity == "high":
            return subtasks + [{"name": "Performance optimization", "hours": 3, "priority": "medium"}]
        return subtasks

    def generate_code_artifact(self, task_type: str) -> Dict[str, Any]:
        """Generate realistic code artifact based on specialization.

        Args:
            task_type: Type of task (api, feature, test, etc.)

        Returns:
            Code artifact with file structure
        """
        spec = self.specialization.lower()

        if "backend" in spec:
            if "api" in task_type.lower():
                artifact = {
                    "files": {
                        "api/endpoints.py": self._generate_api_code(),
                        "api/models.py": self._generate_model_code(),
                        "api/schemas.py": self._generate_schema_code(),
                        "tests/test_endpoints.py": self._generate_test_code("api"),
                    },
                    "dependencies": ["fastapi", "pydantic", "sqlalchemy"],
                    "lines_of_code": 287,
                }
            else:
                artifact = {
                    "files": {
                        "services/core.py": "# Business logic implementation\nclass Service:\n    ...",
                        "tests/test_service.py": "# Unit tests\ndef test_service():\n    ...",
                    },
                    "dependencies": ["pytest"],
                    "lines_of_code": 156,
                }

        elif "frontend" in spec:
            artifact = {
                "files": {
                    "components/Feature.tsx": self._generate_react_component(),
                    "components/Feature.test.tsx": self._generate_test_code("react"),
                    "styles/Feature.module.css": "/* Component styles */\n.container { ... }",
                },
                "dependencies": ["react", "typescript", "@testing-library/react"],
                "lines_of_code": 198,
            }

        elif "qa" in spec:
            artifact = {
                "files": {
                    "tests/e2e/feature.spec.ts": self._generate_test_code("e2e"),
                    "tests/integration/api.test.ts": self._generate_test_code("integration"),
                },
                "dependencies": ["jest", "playwright", "supertest"],
                "test_cases": 24,
                "coverage_percentage": 87,
            }

        elif "devops" in spec:
            artifact = {
                "files": {
                    "terraform/main.tf": self._generate_terraform_code(),
                    ".github/workflows/ci.yml": self._generate_github_actions(),
                    "docker-compose.yml": "# Docker compose configuration\nversion: '3.8'\n...",
                },
                "dependencies": ["terraform", "docker", "kubernetes"],
                "infrastructure_components": 5,
            }

        else:
            artifact = {
                "files": {
                    "implementation.py": "# Implementation\ndef main():\n    ...",
                },
                "dependencies": [],
                "lines_of_code": 50,
            }

        artifact["specialization"] = self.specialization
        artifact["created_at"] = "2024-01-15T10:30:00Z"
        return artifact

    def _generate_api_code(self) -> str:
        """Generate sample API endpoint code."""
        return """from fastapi import APIRouter, HTTPException
from .schemas import ItemCreate, ItemResponse
from .models import Item

router = APIRouter()

@router.post("/items", response_model=ItemResponse)
async def create_item(item: ItemCreate):
    \"\"\"Create a new item.\"\"\"
    # Business logic here
    return ItemResponse(id=1, **item.dict())

@router.get("/items/{item_id}")
async def get_item(item_id: int):
    \"\"\"Retrieve item by ID.\"\"\"
    # Query database
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
"""

    def _generate_model_code(self) -> str:
        """Generate sample database model code."""
        return """from sqlalchemy import Column, Integer, String, Float
from .database import Base

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    price = Column(Float)
"""

    def _generate_schema_code(self) -> str:
        """Generate sample Pydantic schema code."""
        return """from pydantic import BaseModel, Field

class ItemBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str
    price: float = Field(..., gt=0)

class ItemCreate(ItemBase):
    pass

class ItemResponse(ItemBase):
    id: int

    class Config:
        from_attributes = True
"""

    def _generate_react_component(self) -> str:
        """Generate sample React component code."""
        return """import React, { useState } from 'react';
import styles from './Feature.module.css';

interface FeatureProps {
    title: string;
    onAction: () => void;
}

export const Feature: React.FC<FeatureProps> = ({ title, onAction }) => {
    const [isActive, setIsActive] = useState(false);

    return (
        <div className={styles.container}>
            <h2>{title}</h2>
            <button onClick={() => { setIsActive(true); onAction(); }}>
                Activate
            </button>
        </div>
    );
};
"""

    def _generate_test_code(self, test_type: str) -> str:
        """Generate sample test code."""
        if test_type == "api":
            return """import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_create_item():
    response = client.post("/items", json={"name": "Test", "price": 10.0})
    assert response.status_code == 200
    assert response.json()["name"] == "Test"
"""
        if test_type == "react":
            return """import { render, screen, fireEvent } from '@testing-library/react';
import { Feature } from './Feature';

test('renders feature and handles click', () => {
    const mockAction = jest.fn();
    render(<Feature title="Test" onAction={mockAction} />);

    fireEvent.click(screen.getByText('Activate'));
    expect(mockAction).toHaveBeenCalled();
});
"""
        else:
            return "# Generic test implementation\ndef test_feature():\n    assert True\n"

    def _generate_terraform_code(self) -> str:
        """Generate sample Terraform configuration."""
        return """terraform {
  required_version = ">= 1.0"
}

resource "aws_instance" "app_server" {
  ami           = "ami-0c55b159cbfafe1f0"
  instance_type = "t3.medium"

  tags = {
    Name = "AppServer"
  }
}
"""

    def _generate_github_actions(self) -> str:
        """Generate sample GitHub Actions workflow."""
        return """name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: pytest tests/
      - name: Upload coverage
        uses: codecov/codecov-action@v3
"""

    def complete_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Complete an assigned development task.

        Args:
            task: Task specification

        Returns:
            Task completion result
        """
        self.tasks_completed += 1

        task_type = task.get("type", "generic")
        complexity = task.get("complexity", "medium")

        # Generate estimation
        estimation = self.estimate_task(task.get("description", task_type), complexity)

        # Generate code artifact
        artifact = self.generate_code_artifact(task_type)

        # Calculate quality metrics
        quality_metrics = self._calculate_quality_metrics(complexity, artifact)

        return {
            "status": "completed",
            "task_type": task_type,
            "complexity": complexity,
            "specialization": self.specialization,
            "estimation": estimation,
            "artifact": artifact,
            "quality_metrics": quality_metrics,
            "hours_spent": estimation["estimated_hours"],
        }

    def _calculate_quality_metrics(self, complexity: str, artifact: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate quality metrics for completed work.

        Args:
            complexity: Task complexity
            artifact: Code artifact

        Returns:
            Quality metrics
        """
        spec = self.specialization.lower()

        # Base metrics
        if "qa" in spec:
            metrics = {
                "test_coverage": artifact.get("coverage_percentage", 87),
                "bugs_found": 3 if complexity == "high" else 1,
                "test_cases_written": artifact.get("test_cases", 24),
                "quality_score": 0.91,
            }
        elif "dev" in spec:
            metrics = {
                "test_coverage": 85 if complexity == "low" else 78,
                "code_quality_score": 0.88,
                "linting_issues": 2 if complexity == "high" else 0,
                "technical_debt_ratio": 0.05 if complexity == "low" else 0.12,
                "lines_of_code": artifact.get("lines_of_code", 150),
            }
        elif "devops" in spec:
            metrics = {
                "deployment_success_rate": 0.98,
                "infrastructure_components": artifact.get("infrastructure_components", 5),
                "configuration_score": 0.92,
                "security_score": 0.87,
            }
        else:
            metrics = {
                "completion_rate": 1.0,
                "quality_score": 0.85,
            }

        return metrics

    def review_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Review code and provide feedback.

        Args:
            code: Code to review
            language: Programming language

        Returns:
            Code review feedback
        """
        # Simulate code review based on specialization
        issues = []
        suggestions = []

        if len(code) < 50:
            issues.append({"severity": "low", "message": "Code seems incomplete or too brief"})

        if "TODO" in code or "FIXME" in code:
            issues.append({"severity": "medium", "message": "Contains TODO/FIXME comments"})

        if "test" not in code.lower() and "qa" in self.specialization.lower():
            issues.append({"severity": "high", "message": "Missing test coverage"})

        # Add constructive suggestions
        if "backend" in self.specialization.lower():
            suggestions.append("Consider adding error handling for edge cases")
            suggestions.append("Add input validation and sanitization")
        elif "frontend" in self.specialization.lower():
            suggestions.append("Ensure accessibility with ARIA labels")
            suggestions.append("Add loading and error states")

        return {
            "reviewer": self.specialization,
            "issues_found": len(issues),
            "issues": issues,
            "suggestions": suggestions,
            "overall_rating": 8 if len(issues) < 2 else 6,
            "approved": len(issues) < 3,
        }

    def make_decision(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Make implementation decision.

        Args:
            context: Decision context

        Returns:
            Implementation decision
        """
        self.decisions_made += 1

        task_complexity = context.get("complexity", "medium")
        timeline = context.get("timeline", "normal")

        # Decide on implementation approach
        if timeline == "urgent" and task_complexity == "high":
            approach = "MVP approach: Focus on core functionality, defer nice-to-haves"
            strategy = "quick_iteration"
        elif task_complexity == "high":
            approach = "Incremental development: Build in phases with testing at each stage"
            strategy = "phased_development"
        else:
            approach = "Standard development with TDD (Test-Driven Development)"
            strategy = "test_driven"

        return {
            "decision": "implement",
            "reasoning": f"Using {self.specialization} best practices for {task_complexity} complexity",
            "implementation_approach": approach,
            "strategy": strategy,
            "confidence": 0.82 if task_complexity == "high" else 0.88,
            "estimated_timeline": self._estimate_timeline(task_complexity, timeline),
        }

    def _estimate_timeline(self, complexity: str, urgency: str) -> str:
        """Estimate timeline based on complexity and urgency.

        Args:
            complexity: Task complexity
            urgency: Timeline urgency

        Returns:
            Timeline estimate
        """
        base_days = {"low": 2, "medium": 5, "high": 10}
        days = base_days.get(complexity, 5)

        if urgency == "urgent":
            days = max(1, days // 2)

        return f"{days} days" if days > 1 else "1 day"
