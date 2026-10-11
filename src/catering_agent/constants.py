"""Application-wide technical constants.

Business values such as prices, tax rates, currencies, capacities, and menu
content must come from approved regional catalog and rule data, never here.
"""

from decimal import Decimal
from typing import Final

APP_NAME: Final = "CateringProposalAgent"
APP_PORT: Final = 8080
DB_NAME: Final = "catering"
MONEY_QUANTUM: Final = Decimal("0.01")
LLM_TEMPERATURE_EXTRACTION: Final = 0
LLM_MAX_TOOL_ITERATIONS: Final = 6
LLM_REQUEST_TIMEOUT_S: Final = 60
RETRIEVAL_TOP_K: Final = 8
LOW_CONFIDENCE_THRESHOLD: Final = 0.75
SECRET_MASK: Final = "********"
