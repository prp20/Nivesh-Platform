import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fundamental_scorer.graph import run_fundamental_scorer
from app.models import FinancialStatement

@pytest.mark.asyncio
async def test_run_fundamental_scorer_workflow():
    # 1. Setup Mocks
    db = AsyncMock()
    
    # Mock database results for fetch_financials_node
    mock_statements = [
        FinancialStatement(
            stock_id=1,
            period_end="2023-03-31",
            period_type="annual",
            statement_type="PL",
            data={"Revenue": 1000, "Operating Profit": 200, "Net Profit": 150}
        ),
        FinancialStatement(
            stock_id=1,
            period_end="2023-03-31",
            period_type="annual",
            statement_type="BS",
            data={"Borrowings": 100, "Equity Capital": 500, "Reserves": 400}
        ),
        FinancialStatement(
            stock_id=1,
            period_end="2023-03-31",
            period_type="annual",
            statement_type="CF",
            data={"Cash from Operating Activity": 180, "Cash from Investing Activity": -50}
        )
    ]
    
    # Needs a bit more data for CAGR (at least 3 years for PL)
    # Adding more dummy years
    for i in range(1, 4):
        mock_statements.append(
            FinancialStatement(
                stock_id=1,
                period_end=f"202{i}-03-31",
                period_type="annual",
                statement_type="PL",
                data={"Revenue": 500 + i*100, "Operating Profit": 100 + i*20, "Net Profit": 80 + i*10}
            )
        )

    # Setup the execution result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_statements
    db.execute.return_value = mock_result
    
    # Mock settings to ensure no API key is found for reasoning (to avoid real API calls)
    with patch("fundamental_scorer.nodes.reasoning_nodes.settings") as mock_settings:
        mock_settings.GOOGLE_API_KEY = None
        
        # 2. Execute Graph
        final_state = await run_fundamental_scorer(
            stock_id=1,
            symbol="TESTSTOCK",
            db=db,
            period_type="annual"
        )
        
        # 3. Assertions
        assert final_state["status"] == "COMPLETED"
        assert "composite_score" in final_state
        assert final_state["composite_score"] > 0
        
        # Verify persistence was attempted
        assert db.execute.call_count >= 2 # One for fetch, one for persist
        assert db.commit.called
