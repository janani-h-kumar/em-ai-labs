# src/tools/calculator_tool.py

from pydantic import BaseModel

from src.tools.base_tool import BaseTool


class CalculatorInput(BaseModel):
    operation: str
    principal: float | None = None
    annual_rate_pct: float | None = None
    term_months: int | None = None


class CalculatorTool(BaseTool):
    name = "calculator"
    description = "Mortgage and home finance calculations"
    args_schema = CalculatorInput

    def amortise(self, principal: float, annual_rate_pct: float, term_months: int) -> dict:
        """Returns monthly_payment, total_paid, total_interest."""
        r = (annual_rate_pct / 100) / 12
        if r == 0:
            monthly = principal / term_months
        else:
            monthly = principal * r * (1 + r) ** term_months / ((1 + r) ** term_months - 1)
        total = monthly * term_months
        return {
            "monthly_payment": round(monthly, 2),
            "total_paid": round(total, 2),
            "total_interest": round(total - principal, 2),
        }

    def dti_ratio(self, gross_monthly_income: float, total_monthly_debts: float) -> float:
        """Debt-to-income ratio as a percentage. Under 36% = healthy."""
        if gross_monthly_income <= 0:
            raise ValueError("gross_monthly_income must be positive")
        return round((total_monthly_debts / gross_monthly_income) * 100, 1)

    def affordability_range(
        self, annual_income: float, down_payment: float, rate_pct: float, term_years: int = 30
    ) -> dict:
        """Returns min/max home price based on 28% and 36% DTI thresholds."""
        monthly_income = annual_income / 12
        max_payment_conservative = monthly_income * 0.28
        max_payment_aggressive = monthly_income * 0.36
        r = (rate_pct / 100) / 12
        term = term_years * 12
        factor = ((1 + r) ** term - 1) / (r * (1 + r) ** term) if r > 0 else term
        return {
            "min_home_price": round(max_payment_conservative * factor + down_payment),
            "max_home_price": round(max_payment_aggressive * factor + down_payment),
            "monthly_payment_at_max": round(max_payment_aggressive, 2),
            "assumed_rate_pct": rate_pct,
            "term_years": term_years,
        }

    def _run(self, input: str, **kwargs):
        # Route to specific method based on input
        raise NotImplementedError("Use amortise(), dti_ratio(), or affordability_range() directly")
