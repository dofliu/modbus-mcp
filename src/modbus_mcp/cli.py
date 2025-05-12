import asyncio
import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import List, Union

from pymodbus.client import AsyncModbusTcpClient, AsyncModbusUdpClient, AsyncModbusSerialClient
from pymodbus.exceptions import ModbusException
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.fastmcp.prompts import base

from dotenv import load_dotenv

load_dotenv()

# Modbus client configuration from environment variables
MODBUS_TYPE = os.environ.get("MODBUS_TYPE", "tcp").lower()  # tcp, udp, or serial
MODBUS_HOST = os.environ.get("MODBUS_HOST", "127.0.0.1")
MODBUS_PORT = int(os.environ.get("MODBUS_PORT", 502))
MODBUS_SERIAL_PORT = os.environ.get("MODBUS_SERIAL_PORT", "/dev/ttyUSB0")
MODBUS_BAUDRATE = int(os.environ.get("MODBUS_BAUDRATE", 9600))
MODBUS_PARITY = os.environ.get("MODBUS_PARITY", "N")
MODBUS_STOPBITS = int(os.environ.get("MODBUS_STOPBITS", 1))
MODBUS_BYTESIZE = int(os.environ.get("MODBUS_BYTESIZE", 8))
MODBUS_TIMEOUT = float(os.environ.get("MODBUS_TIMEOUT", 1))
MODBUS_DEFAULT_SLAVE_ID = int(os.environ.get("MODBUS_DEFAULT_SLAVE_ID", 1))

# Application context for dependency injection
@dataclass
class AppContext:
    modbus_client: Union[AsyncModbusTcpClient, AsyncModbusUdpClient, AsyncModbusSerialClient]

# Lifespan manager for Modbus client
@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage Modbus client lifecycle."""
    # Initialize Modbus client based on MODBUS_TYPE
    if MODBUS_TYPE == "tcp":
        client = AsyncModbusTcpClient(host=MODBUS_HOST, port=MODBUS_PORT)
    elif MODBUS_TYPE == "udp":
        client = AsyncModbusUdpClient(host=MODBUS_HOST, port=MODBUS_PORT)
    elif MODBUS_TYPE == "serial":
        client = AsyncModbusSerialClient(
            port=MODBUS_SERIAL_PORT,
            baudrate=MODBUS_BAUDRATE,
            parity=MODBUS_PARITY,
            stopbits=MODBUS_STOPBITS,
            bytesize=MODBUS_BYTESIZE,
            timeout=MODBUS_TIMEOUT
        )
    else:
        raise ValueError(f"Invalid MODBUS_TYPE: {MODBUS_TYPE}. Must be 'tcp', 'udp', or 'serial'.")

    # Connect to the Modbus device
    await client.connect()
    if not client.connected:
        raise RuntimeError(f"Failed to connect to Modbus {MODBUS_TYPE} device")

    try:
        yield AppContext(modbus_client=client)
    finally:
        # Cleanup
        client.close()

# Initialize MCP server
mcp = FastMCP(
    name="Modbus MCP Server",
    dependencies=["pymodbus"],
    lifespan=app_lifespan
)

# Tools: Read and write Modbus registers
@mcp.tool()
async def read_register(address: int, ctx: Context, slave_id: int = MODBUS_DEFAULT_SLAVE_ID) -> str: 
    """
    Read a single Modbus holding register.
    Parameters:
        address (int): The starting address of the holding register (0-65535).
        slave_id (int): The Modbus slave ID (device ID).(2025/05/12)
    Returns:
        str: The value of the register or an error message.
    """
    client = ctx.request_context.lifespan_context.modbus_client
    try:
        result = await client.read_holding_registers(address=address, count=1, slave=slave_id) 
        if result.isError():
            return f"Error reading register {address} from slave {slave_id}: {result}"
        ctx.info(f"Read register {address} from slave {slave_id}: {result.registers[0]}")
        return f"Slave {slave_id}, Register {address} Value: {result.registers[0]}"
    except ModbusException as e:
        return f"Error communicating with slave {slave_id}: {str(e)}"

@mcp.tool()
async def write_register(address: int, value: int, ctx: Context) -> str:
    """
    Write a value to a Modbus holding register.

    Parameters:
        address (int): The address of the holding register (0-65535).
        value (int): The value to write (0-65535).
    
    Returns:
        str: Success message or an error message.
    """
    client = ctx.request_context.lifespan_context.modbus_client
    try:
        result = await client.write_register(address=address, value=value, slave=1)
        if result.isError():
            return f"Error writing to register {address}: {result}"
        ctx.info(f"Wrote {value} to register {address}")
        return f"Successfully wrote {value} to register {address}"
    except ModbusException as e:
        return f"Error: {str(e)}"

# Tools: Coil operations
@mcp.tool()
async def read_coils(address: int, count: int, ctx: Context) -> str:
    """
    Read the status of multiple Modbus coils.

    Parameters:
        address (int): The starting address of the coils (0-65535).
        count (int): The number of coils to read (1-2000).
    
    Returns:
        str: A list of coil states (True/False) or an error message.
    """
    client = ctx.request_context.lifespan_context.modbus_client
    try:
        if count <= 0:
            return "Error: Count must be positive"
        result = await client.read_coils(address=address, count=count, slave=1)
        if result.isError():
            return f"Error reading coils starting at {address}: {result}"
        ctx.info(f"Read {count} coils starting at {address}: {result.bits}")
        return f"Coils {address} to {address+count-1}: {result.bits[:count]}"
    except ModbusException as e:
        return f"Error: {str(e)}"

@mcp.tool()
async def write_coil(address: int, value: bool, ctx: Context) -> str:
    """
    Write a value to a single Modbus coil.

    Parameters:
        address (int): The address of the coil (0-65535).
        value (bool): The value to write (True for ON, False for OFF).
    
    Returns:
        str: Success message or an error message.
    """
    client = ctx.request_context.lifespan_context.modbus_client
    try:
        result = await client.write_coil(address=address, value=value, slave=1)
        if result.isError():
            return f"Error writing to coil {address}: {result}"
        ctx.info(f"Wrote {value} to coil {address}")
        return f"Successfully wrote {value} to coil {address}"
    except ModbusException as e:
        return f"Error: {str(e)}"

# Tools: Input registers
@mcp.tool()
async def read_input_registers(address: int, count: int, ctx: Context) -> str:
    """
    Read multiple Modbus input registers.

    Parameters:
        address (int): The starting address of the input registers (0-65535).
        count (int): The number of registers to read (1-125).
    
    Returns:
        str: A list of register values or an error message.
    """
    client = ctx.request_context.lifespan_context.modbus_client
    try:
        if count <= 0:
            return "Error: Count must be positive"
        result = await client.read_input_registers(address=address, count=count, slave=1)
        if result.isError():
            return f"Error reading input registers starting at {address}: {result}"
        ctx.info(f"Read {count} input registers starting at {address}: {result.registers}")
        return f"Input Registers {address} to {address+count-1}: {result.registers}"
    except ModbusException as e:
        return f"Error: {str(e)}"

# Tools: Read multiple holding registers
@mcp.tool()
async def read_multiple_holding_registers(address: int, count: int, ctx: Context) -> str:
    """
    Read multiple Modbus holding registers.

    Parameters:
        address (int): The starting address of the holding registers (0-65535).
        count (int): The number of registers to read (1-125).
    
    Returns:
        str: A list of register values or an error message.
    """
    client = ctx.request_context.lifespan_context.modbus_client
    try:
        if count <= 0:
            return "Error: Count must be positive"
        result = await client.read_holding_registers(address=address, count=count, slave=1)
        if result.isError():
            return f"Error reading holding registers starting at {address}: {result}"
        ctx.info(f"Read {count} holding registers starting at {address}: {result.registers}")
        return f"Holding Registers {address} to {address+count-1}: {result.registers}"
    except ModbusException as e:
        return f"Error: {str(e)}"


# Prompts: Templates for Modbus interactions
@mcp.prompt()
def analyze_register(value: str) -> List[base.Message]:
    """Prompt to analyze a Modbus register value."""
    return [
        base.UserMessage(f"I read this value from a Modbus register: {value}"),
        base.UserMessage("Can you help me understand what it means?"),
        base.AssistantMessage("I'll help analyze the register value. Please provide any context about the device or system.")
    ]

def main() -> None:
    """Run the MCP server."""
    mcp.run()
