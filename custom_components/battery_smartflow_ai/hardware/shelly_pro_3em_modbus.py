"""Read Shelly Pro 3EM Gen2 active-power registers over Modbus TCP."""

from __future__ import annotations

import asyncio
import secrets
import struct

from ..const import DIRECT_SHELLY_REQUEST_TIMEOUT_S
from .shelly_pro_3em import (
    ShellyPro3EMError,
    ShellyPro3EMReading,
    validate_shelly_host,
)

_MODBUS_PORT = 502
_UNIT_ID = 1
_READ_INPUT_REGISTERS = 4
_START_ADDRESS = 1013
_REGISTER_COUNT = 53
_FLOAT_REGISTER_OFFSETS = {
    "total": 0,  # documented register 31013 -> zero-based Modbus address 1013
    "phase_a": 11,  # register 31024
    "phase_b": 31,  # register 31044
    "phase_c": 51,  # register 31064
}


def _decode_shelly_float(register_bytes: bytes) -> float:
    """Decode Shelly's mixed-endian IEEE-754 float (16-bit words swapped)."""

    if len(register_bytes) != 4:
        raise ShellyPro3EMError("invalid_modbus_float_length")
    value = struct.unpack(">f", register_bytes[2:4] + register_bytes[0:2])[0]
    if not -float("inf") < value < float("inf"):
        raise ShellyPro3EMError("invalid_modbus_float")
    return value


def parse_shelly_pro_3em_modbus_registers(
    registers: list[int] | tuple[int, ...],
) -> ShellyPro3EMReading:
    """Decode total and three phase power from input registers 1013..1065."""

    if len(registers) != _REGISTER_COUNT:
        raise ShellyPro3EMError("invalid_modbus_register_count")
    if any(not isinstance(register, int) or not 0 <= register <= 0xFFFF for register in registers):
        raise ShellyPro3EMError("invalid_modbus_register")

    raw = b"".join(struct.pack(">H", register) for register in registers)

    def read_float(name: str) -> float:
        offset = _FLOAT_REGISTER_OFFSETS[name]
        return _decode_shelly_float(raw[offset * 2 : (offset + 2) * 2])

    try:
        return ShellyPro3EMReading(
            total_power_w=read_float("total"),
            phase_a_power_w=read_float("phase_a"),
            phase_b_power_w=read_float("phase_b"),
            phase_c_power_w=read_float("phase_c"),
        )
    except (OverflowError, struct.error) as err:
        raise ShellyPro3EMError("invalid_modbus_float") from err


async def async_read_shelly_pro_3em_modbus(
    *,
    host: str,
    timeout_seconds: float = DIRECT_SHELLY_REQUEST_TIMEOUT_S,
) -> ShellyPro3EMReading:
    """Read one contiguous block of signed active-power input registers.

    This operation is read-only. It does not alter Shelly configuration or
    issue any control commands.
    """

    normalized_host = validate_shelly_host(host)
    transaction_id = secrets.randbelow(0x10000)
    pdu = struct.pack(">BHH", _READ_INPUT_REGISTERS, _START_ADDRESS, _REGISTER_COUNT)
    mbap = struct.pack(">HHHB", transaction_id, 0, len(pdu) + 1, _UNIT_ID)

    async def exchange() -> ShellyPro3EMReading:
        writer = None
        try:
            reader, writer = await asyncio.open_connection(
                normalized_host,
                _MODBUS_PORT,
            )
            writer.write(mbap + pdu)
            await writer.drain()

            header = await reader.readexactly(7)
            received_transaction, protocol_id, length, unit_id = struct.unpack(
                ">HHHB", header
            )
            if received_transaction != transaction_id or protocol_id != 0:
                raise ShellyPro3EMError("invalid_modbus_header")
            if unit_id != _UNIT_ID or length < 2:
                raise ShellyPro3EMError("invalid_modbus_header")

            response = await reader.readexactly(length - 1)
            function_code = response[0]
            if function_code == (_READ_INPUT_REGISTERS | 0x80):
                exception_code = response[1] if len(response) > 1 else 0
                raise ShellyPro3EMError(f"modbus_exception_{exception_code}")
            if function_code != _READ_INPUT_REGISTERS or len(response) < 2:
                raise ShellyPro3EMError("invalid_modbus_response")

            byte_count = response[1]
            register_data = response[2:]
            if byte_count != _REGISTER_COUNT * 2 or len(register_data) != byte_count:
                raise ShellyPro3EMError("invalid_modbus_byte_count")
            registers = struct.unpack(f">{_REGISTER_COUNT}H", register_data)
            return parse_shelly_pro_3em_modbus_registers(registers)
        finally:
            if writer is not None:
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), timeout=0.2)
                except (asyncio.TimeoutError, OSError):
                    pass

    try:
        return await asyncio.wait_for(exchange(), timeout=timeout_seconds)
    except asyncio.TimeoutError as err:
        raise ShellyPro3EMError("modbus_timeout") from err
    except OSError as err:
        raise ShellyPro3EMError("modbus_connection_failed") from err
