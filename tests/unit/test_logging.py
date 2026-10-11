from typing import Any

from catering_agent.constants import SECRET_MASK
from catering_agent.logging import redact_sensitive_values


def test_redaction_masks_sensitive_values_in_nested_data() -> None:
    event: dict[str, Any] = {
        "event": "request_received",
        "client_name": "Example Client",
        "metadata": {"token": "not-for-logs", "safe": "value"},
    }

    result = redact_sensitive_values(None, "info", event)

    assert result["client_name"] == SECRET_MASK
    assert result["metadata"]["token"] == SECRET_MASK
    assert result["metadata"]["safe"] == "value"
