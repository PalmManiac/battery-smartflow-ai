from __future__ import annotations

import asyncio
import struct
import unittest
from unittest.mock import patch

from custom_components.battery_smartflow_ai.hardware.shelly_pro_3em import (
    ShellyPro3EMError,
)
from custom_components.battery_smartflow_ai.hardware.shelly_pro_3em_modbus import (
    _REGISTER_COUNT,
    _START_ADDRESS,
    async_read_shelly_pro_3em_modbus,
    parse_shelly_pro_3em_modbus_registers,
)


def _mixed_endian_registers(value: float) -> tuple[int, int]:
    ieee_bytes = struct.pack(">f", value)
    mixed_bytes = ieee_bytes[2:4] + ieee_bytes[0:2]
    return struct.unpack(">HH", mixed_bytes)


class _Reader:
    def __init__(self, payload: bytes):
        self.payload = bytearray(payload)

    async def readexactly(self, count: int) -> bytes:
        if len(self.payload) < count:
            raise asyncio.IncompleteReadError(bytes(self.payload), count)
        value = bytes(self.payload[:count])
        del self.payload[:count]
        return value


class _Writer:
    def __init__(self):
        self.payload = b""
        self.closed = False

    def write(self, payload: bytes) -> None:
        self.payload = payload

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


class ShellyPro3EMModbusTests(unittest.TestCase):
    def _registers(self) -> list[int]:
        registers = [0] * _REGISTER_COUNT
        for offset, value in ((0, 75.5), (11, 100.0), (31, -40.25), (51, 15.75)):
            registers[offset : offset + 2] = _mixed_endian_registers(value)
        return registers

    def test_parses_total_and_three_signed_phase_powers(self):
        reading = parse_shelly_pro_3em_modbus_registers(self._registers())
        self.assertAlmostEqual(reading.total_power_w, 75.5)
        self.assertAlmostEqual(reading.phase_a_power_w, 100.0)
        self.assertAlmostEqual(reading.phase_b_power_w, -40.25)
        self.assertAlmostEqual(reading.phase_c_power_w, 15.75)

    def test_rejects_invalid_register_blocks_and_non_finite_values(self):
        with self.assertRaisesRegex(ShellyPro3EMError, "register_count"):
            parse_shelly_pro_3em_modbus_registers([0, 1])

        registers = self._registers()
        registers[0:2] = _mixed_endian_registers(float("nan"))
        with self.assertRaisesRegex(ShellyPro3EMError, "invalid_modbus_float"):
            parse_shelly_pro_3em_modbus_registers(registers)

    def test_reads_one_register_block_over_modbus_tcp(self):
        registers = self._registers()
        data = struct.pack(f">{_REGISTER_COUNT}H", *registers)
        response_pdu = bytes((4, len(data))) + data
        response = struct.pack(">HHHB", 0x1234, 0, len(response_pdu) + 1, 1)
        response += response_pdu
        reader = _Reader(response)
        writer = _Writer()

        async def open_connection(host, port):
            self.assertEqual((host, port), ("192.168.1.20", 502))
            return reader, writer

        async def run():
            with patch(
                "custom_components.battery_smartflow_ai.hardware.shelly_pro_3em_modbus.secrets.randbelow",
                return_value=0x1234,
            ), patch(
                "custom_components.battery_smartflow_ai.hardware.shelly_pro_3em_modbus.asyncio.open_connection",
                side_effect=open_connection,
            ):
                return await async_read_shelly_pro_3em_modbus(
                    host="192.168.1.20"
                )

        reading = asyncio.run(run())
        self.assertAlmostEqual(reading.total_power_w, 75.5)
        self.assertAlmostEqual(reading.phase_b_power_w, -40.25)
        self.assertTrue(writer.closed)

        transaction, protocol, length, unit_id = struct.unpack(
            ">HHHB", writer.payload[:7]
        )
        function, address, quantity = struct.unpack(">BHH", writer.payload[7:])
        self.assertEqual((transaction, protocol, unit_id), (0x1234, 0, 1))
        self.assertEqual(length, 6)
        self.assertEqual((function, address, quantity), (4, _START_ADDRESS, _REGISTER_COUNT))


if __name__ == "__main__":
    unittest.main()
