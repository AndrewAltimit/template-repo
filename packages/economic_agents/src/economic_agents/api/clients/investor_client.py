"""Investor Portal API client.

Provides interface for submitting investment proposals and checking status.
"""

from typing import Dict, List

import httpx


class InvestorPortalAPIClient:
    """Client for Investor Portal API service."""

    def __init__(self, api_url: str, api_key: str):
        """Initialize investor portal API client.

        Args:
            api_url: Base URL of Investor Portal API (e.g., http://localhost:8004)
            api_key: API key for authentication
        """
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.headers = {"X-API-Key": api_key}

    def submit_proposal(self, company: Dict) -> Dict:
        """Submit an investment proposal.

        Args:
            company: Company dictionary with proposal details

        Returns:
            Proposal submission result

        Raises:
            ValueError: If API call fails
        """
        try:
            # Build proposal from company data
            proposal_data = {
                "company_id": company.get("id", "unknown"),
                "company_name": company.get("name", "Unnamed Company"),
                "stage": company.get("stage", "idea"),
                "business_plan": company.get("business_plan", {}),
                "funding_requested": company.get("funding_requested", 50000.0),
                "use_of_funds": company.get("use_of_funds", "Product development and team expansion"),
                "team_size": len(company.get("team", [])),
                "revenue": company.get("revenue", 0.0),
                "monthly_burn_rate": company.get("monthly_burn_rate", 0.0),
            }

            response = httpx.post(
                f"{self.api_url}/proposals",
                headers=self.headers,
                json=proposal_data,
            )
            response.raise_for_status()
            result: Dict = response.json()
            return result

        except httpx.HTTPError as e:
            raise ValueError(f"Failed to submit proposal: {e}") from e

    def get_proposal_status(self, proposal_id: str) -> Dict:
        """Get status of a submitted proposal.

        Args:
            proposal_id: Proposal ID

        Returns:
            Investment decision

        Raises:
            ValueError: If API call fails or proposal not found
        """
        try:
            response = httpx.get(
                f"{self.api_url}/proposals/{proposal_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            result: Dict = response.json()
            return result

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError("Proposal not found or still being evaluated") from e
            if e.response.status_code == 403:
                raise ValueError("Not authorized to view this proposal") from e
            raise ValueError(f"Failed to get proposal status: {e}") from e
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to get proposal status: {e}") from e

    def list_investors(self) -> List[Dict]:
        """Get list of active investors.

        Returns:
            List of investor information

        Raises:
            ValueError: If API call fails
        """
        try:
            response = httpx.get(
                f"{self.api_url}/investors",
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()

            investors: List[Dict] = data["investors"]
            return investors

        except httpx.HTTPError as e:
            raise ValueError(f"Failed to get investors: {e}") from e

    def list_proposals(self) -> List[Dict]:
        """List all proposals submitted by this agent.

        Returns:
            List of proposals

        Raises:
            ValueError: If API call fails
        """
        try:
            response = httpx.get(
                f"{self.api_url}/proposals",
                headers=self.headers,
            )
            response.raise_for_status()
            data = response.json()

            proposals: List[Dict] = data["proposals"]
            return proposals

        except httpx.HTTPError as e:
            raise ValueError(f"Failed to list proposals: {e}") from e

    def __repr__(self) -> str:
        """String representation."""
        return f"InvestorPortalAPIClient(api_url={self.api_url})"
