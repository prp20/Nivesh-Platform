"""
Specialist ReAct agents for the Nivesh multi-agent system.

Three agents, each with a focused tool subset:
  build_stock_agent()     → get_stock_detail, search_stocks, screen_stocks
  build_fund_agent()      → get_fund_detail, compare_funds
  build_portfolio_agent() → get_portfolio, get_market_overview

Each returns a compiled LangGraph ReAct agent graph.
Pass system_prompt as a string to inject the Nivesh persona + memory context.
"""

from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from .tools import FUND_TOOLS, PORTFOLIO_TOOLS, STOCK_TOOLS


def build_stock_agent(llm: ChatGroq, system_prompt: str):
    """
    ReAct agent specialised in NSE/BSE stock analysis and screening.
    Tools: get_stock_detail, search_stocks, screen_stocks.
    """
    return create_react_agent(llm, STOCK_TOOLS, prompt=system_prompt)


def build_fund_agent(llm: ChatGroq, system_prompt: str):
    """
    ReAct agent specialised in mutual fund research and comparison.
    Tools: get_fund_detail, compare_funds.
    """
    return create_react_agent(llm, FUND_TOOLS, prompt=system_prompt)


def build_portfolio_agent(llm: ChatGroq, system_prompt: str):
    """
    ReAct agent specialised in portfolio holdings and market overview.
    Tools: get_portfolio, get_market_overview.
    """
    return create_react_agent(llm, PORTFOLIO_TOOLS, prompt=system_prompt)
