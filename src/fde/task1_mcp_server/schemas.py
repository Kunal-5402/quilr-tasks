"""Strict input models. The advertised JSON schema is generated from these."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CustomerId = Annotated[str, StringConstraints(pattern=r"^CUST-[A-Z0-9]{5}$")]

MAX_REFUND_AMOUNT = 100_000.0


class StrictModel(BaseModel):
    # forbid: reject an unknown field. strict: reject "10" where a float is due.
    model_config = ConfigDict(extra="forbid", strict=True)


class GetCustomerRecordInput(StrictModel):
    customer_id: CustomerId


class TriggerRefundInput(StrictModel):
    customer_id: CustomerId
    amount: float = Field(gt=0, le=MAX_REFUND_AMOUNT)
    reason: str = Field(min_length=10, max_length=500)
