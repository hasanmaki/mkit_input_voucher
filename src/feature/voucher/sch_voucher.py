"""schemas / entities for voucher feature."""

from pydantic import BaseModel, Field


class VoucherBase(BaseModel):
    """Base schema for voucher physical attributes."""

    model_config = {"populate_by_name": True, "from_attributes": True}

    voucher_number: str = Field(..., description="Voucher number", alias="vn")
    serial_number: str = Field(..., description="Voucher serial number", alias="sn")
    expiry_date: str = Field(..., description="Voucher expiry date", alias="ed")


class VoucherCreateStaging(VoucherBase):
    """Schema for creating a voucher.

    di gunakan saat akan insert data voucher baru ke staging db
    """

    batch_id: int = Field(..., description="Batch ID", alias="bid")
