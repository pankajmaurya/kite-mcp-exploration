import asyncio
import webbrowser
import re
import json
from typing import Optional, Dict, Any


class KiteMCPClient:
    """Generic client for interacting with Kite MCP server."""
    
    def __init__(self, mcp_url: str = "https://mcp.kite.trade/sse"):
        self.mcp_url = mcp_url
        self.client = None
        self._is_logged_in = False
    
    async def __aenter__(self):
        from fastmcp import Client
        from fastmcp.client.transports import SSETransport
        
        transport = SSETransport(url=self.mcp_url, headers={})
        self.client = await Client(transport).__aenter__()
        print(f"✓ Connected to Kite MCP server at {self.mcp_url}")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
    
    def _extract_text_content(self, result) -> Optional[str]:
        """Extract text content from MCP tool result."""
        if hasattr(result, 'content') and isinstance(result.content, list):
            for item in result.content:
                if hasattr(item, 'type') and item.type == 'text':
                    return item.text
        elif isinstance(result, list):
            for item in result:
                if hasattr(item, 'type') and item.type == 'text':
                    return item.text
        return None
    
    def _extract_url(self, text: str) -> Optional[str]:
        """Extract URL from text using regex."""
        url_pattern = r'https://[^\s\)]+\S+'
        urls = re.findall(url_pattern, text)
        return urls[-1] if urls else None
    
    async def login(self, auto_open_browser: bool = True) -> bool:
        """
        Initiate login flow and wait for user to complete authentication.
        
        Args:
            auto_open_browser: Whether to automatically open the login URL in browser
            
        Returns:
            True if login was successful, False otherwise
        """
        print("\n📋 Initiating login...")
        
        try:
            login_result = await self.client.call_tool("login", {})
            text_content = self._extract_text_content(login_result)
            
            if not text_content:
                print("❌ No response from login tool")
                return False
            
            # Display warning to user
            if "WARNING" in text_content:
                print("\n" + "="*60)
                print("⚠️  IMPORTANT WARNING")
                print("="*60)
                lines = text_content.split('\n')
                for line in lines:
                    if 'WARNING' in line or 'risk' in line.lower():
                        print(line)
                print("="*60 + "\n")
            
            # Extract and open login URL
            login_url = self._extract_url(text_content)
            
            if not login_url:
                print("❌ Could not extract login URL")
                return False
            
            print(f"\n🔗 Login URL: {login_url}\n")
            
            if auto_open_browser:
                try:
                    webbrowser.open(login_url)
                    print("✓ Browser opened automatically")
                except Exception as e:
                    print(f"⚠️  Could not auto-open browser: {e}")
                    print("Please manually copy and paste the URL above")
            
            input("\n⏳ Press Enter after completing login in your browser...")
            
            # Give session time to sync
            await asyncio.sleep(2)
            
            self._is_logged_in = True
            print("✓ Login confirmed\n")
            return True
            
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False
    
    async def call_tool(self, tool_name: str, params: Dict[str, Any] = None) -> Any:
        """
        Generic method to call any MCP tool.
        
        Args:
            tool_name: Name of the tool to call
            params: Dictionary of parameters to pass to the tool
            
        Returns:
            The tool result
        """
        if not self._is_logged_in and tool_name != "login":
            print("⚠️  Warning: Not logged in. Some tools may fail.")
        
        if params is None:
            params = {}
        
        try:
            print(f"📞 Calling tool: {tool_name}")
            result = await self.client.call_tool(tool_name, params)
            return result
        except Exception as e:
            print(f"❌ Error calling {tool_name}: {e}")
            raise
    
    def _format_result(self, result, result_type: str = None) -> str:
        """Format the result for display."""
        text_content = self._extract_text_content(result)
        
        if text_content:
            try:
                # Try to parse as JSON for better formatting
                data = json.loads(text_content)
                return self._format_json_data(data, result_type)
            except (json.JSONDecodeError, TypeError):
                return text_content
        
        return str(result)
    
    def _format_json_data(self, data, result_type: str = None) -> str:
        """Format JSON data based on type."""
        if not data:
            return "No data available"
        
        if isinstance(data, list):
            if not data:
                return "No records found"
            
            # Format based on result type
            if result_type == "orders":
                return self._format_orders(data)
            elif result_type == "holdings":
                return self._format_holdings(data)
            elif result_type == "positions":
                return self._format_positions(data)
            elif result_type == "trades":
                return self._format_trades(data)
            else:
                # Generic list formatting
                return self._format_generic_list(data)
        
        elif isinstance(data, dict):
            return self._format_dict(data)
        
        return json.dumps(data, indent=2)
    
    def _format_orders(self, orders: list) -> str:
        """Format orders in a clean table."""
        if not orders:
            return "No orders found"
        
        output = []
        output.append(f"\n{'='*100}")
        output.append(f"{'Order ID':<20} {'Symbol':<15} {'Type':<5} {'Qty':<5} {'Price':<10} {'Avg':<10} {'Status':<12} {'Time':<20}")
        output.append(f"{'='*100}")
        
        for order in orders:
            order_id = order.get('order_id', 'N/A')[-10:]  # Last 10 digits
            symbol = order.get('tradingsymbol', 'N/A')[:14]
            tx_type = order.get('transaction_type', 'N/A')[:4]
            qty = order.get('quantity', 0)
            price = order.get('price', 0)
            avg_price = order.get('average_price', 0)
            status = order.get('status', 'N/A')[:11]
            timestamp = order.get('order_timestamp', 'N/A').split('T')[1][:8] if 'T' in order.get('order_timestamp', '') else 'N/A'
            
            output.append(f"{order_id:<20} {symbol:<15} {tx_type:<5} {qty:<5} {price:<10.2f} {avg_price:<10.2f} {status:<12} {timestamp:<20}")
        
        output.append(f"{'='*100}")
        output.append(f"\nTotal orders: {len(orders)}")
        
        return "\n".join(output)
    
    def _format_holdings(self, holdings: list) -> str:
        """Format holdings in a clean table."""
        if not holdings:
            return "No holdings found"
        
        output = []
        output.append(f"\n{'='*90}")
        output.append(f"{'Symbol':<15} {'Qty':<8} {'Avg Cost':<12} {'LTP':<12} {'P&L':<15} {'P&L %':<10}")
        output.append(f"{'='*90}")
        
        total_investment = 0
        total_current = 0
        
        for holding in holdings:
            symbol = holding.get('tradingsymbol', 'N/A')[:14]
            qty = holding.get('quantity', 0)
            avg_price = holding.get('average_price', 0)
            ltp = holding.get('last_price', 0)
            pnl = holding.get('pnl', 0)
            
            investment = avg_price * qty
            current_value = ltp * qty
            pnl_pct = ((current_value - investment) / investment * 100) if investment > 0 else 0
            
            total_investment += investment
            total_current += current_value
            
            pnl_str = f"₹{pnl:,.2f}" if pnl >= 0 else f"-₹{abs(pnl):,.2f}"
            output.append(f"{symbol:<15} {qty:<8} ₹{avg_price:<10.2f} ₹{ltp:<10.2f} {pnl_str:<15} {pnl_pct:>6.2f}%")
        
        output.append(f"{'='*90}")
        total_pnl = total_current - total_investment
        total_pnl_pct = (total_pnl / total_investment * 100) if total_investment > 0 else 0
        output.append(f"\nTotal Investment: ₹{total_investment:,.2f}")
        output.append(f"Current Value: ₹{total_current:,.2f}")
        output.append(f"Total P&L: ₹{total_pnl:,.2f} ({total_pnl_pct:+.2f}%)")
        
        return "\n".join(output)
    
    def _format_positions(self, positions: list) -> str:
        """Format positions in a clean table."""
        if not positions:
            return "No positions found"
        
        output = []
        output.append(f"\n{'='*100}")
        output.append(f"{'Symbol':<15} {'Product':<8} {'Qty':<6} {'Avg':<10} {'LTP':<10} {'P&L':<15} {'P&L %':<10}")
        output.append(f"{'='*100}")
        
        for pos in positions:
            symbol = pos.get('tradingsymbol', 'N/A')[:14]
            product = pos.get('product', 'N/A')[:7]
            qty = pos.get('quantity', 0)
            avg_price = pos.get('average_price', 0)
            ltp = pos.get('last_price', 0)
            pnl = pos.get('pnl', 0)
            
            pnl_pct = ((ltp - avg_price) / avg_price * 100) if avg_price > 0 else 0
            pnl_str = f"₹{pnl:,.2f}" if pnl >= 0 else f"-₹{abs(pnl):,.2f}"
            
            output.append(f"{symbol:<15} {product:<8} {qty:<6} ₹{avg_price:<8.2f} ₹{ltp:<8.2f} {pnl_str:<15} {pnl_pct:>6.2f}%")
        
        output.append(f"{'='*100}")
        output.append(f"\nTotal positions: {len(positions)}")
        
        return "\n".join(output)
    
    def _format_trades(self, trades: list) -> str:
        """Format trades in a clean table."""
        if not trades:
            return "No trades found"
        
        output = []
        output.append(f"\n{'='*90}")
        output.append(f"{'Trade ID':<15} {'Symbol':<15} {'Type':<5} {'Qty':<5} {'Price':<12} {'Time':<20}")
        output.append(f"{'='*90}")
        
        for trade in trades:
            trade_id = str(trade.get('trade_id', 'N/A'))[-10:]
            symbol = trade.get('tradingsymbol', 'N/A')[:14]
            tx_type = trade.get('transaction_type', 'N/A')[:4]
            qty = trade.get('quantity', 0)
            price = trade.get('price', 0)
            time = trade.get('fill_timestamp', 'N/A').split('T')[1][:8] if 'T' in trade.get('fill_timestamp', '') else 'N/A'
            
            output.append(f"{trade_id:<15} {symbol:<15} {tx_type:<5} {qty:<5} ₹{price:<10.2f} {time:<20}")
        
        output.append(f"{'='*90}")
        output.append(f"\nTotal trades: {len(trades)}")
        
        return "\n".join(output)
    
    def _format_generic_list(self, data: list) -> str:
        """Format generic list data."""
        if len(data) <= 3:
            return json.dumps(data, indent=2)
        
        output = [f"\nShowing {len(data)} records:"]
        for i, item in enumerate(data[:5], 1):
            if isinstance(item, dict):
                key_items = list(item.items())[:3]
                summary = ", ".join([f"{k}: {v}" for k, v in key_items])
                output.append(f"{i}. {summary}...")
            else:
                output.append(f"{i}. {item}")
        
        if len(data) > 5:
            output.append(f"... and {len(data) - 5} more")
        
        return "\n".join(output)
    
    def _format_dict(self, data: dict) -> str:
        """Format dictionary data."""
        output = []
        for key, value in data.items():
            if isinstance(value, (int, float)):
                output.append(f"{key}: {value:,}")
            else:
                output.append(f"{key}: {value}")
        return "\n".join(output)
    
    # Convenience methods for common operations
    
    async def get_holdings(self):
        """Get current holdings."""
        result = await self.call_tool("get_holdings")
        print("\n📊 HOLDINGS")
        print(self._format_result(result, "holdings"))
        return result
    
    async def get_positions(self):
        """Get current positions."""
        result = await self.call_tool("get_positions")
        print("\n📈 POSITIONS")
        print(self._format_result(result, "positions"))
        return result
    
    async def get_orders(self):
        """Get all orders."""
        result = await self.call_tool("get_orders")
        print("\n📋 ORDERS")
        print(self._format_result(result, "orders"))
        return result
    
    async def get_order_history(self, order_id: str):
        """Get history for a specific order."""
        result = await self.call_tool("get_order_history", {"order_id": order_id})
        print(f"\n📜 Order History for {order_id}:")
        print(self._format_result(result))
        return result
    
    async def get_trades(self):
        """Get all trades."""
        result = await self.call_tool("get_trades")
        print("\n💰 TRADES")
        print(self._format_result(result, "trades"))
        return result
    
    async def get_instruments(self, exchange: str):
        """Get instruments for an exchange."""
        result = await self.call_tool("get_instruments", {"exchange": exchange})
        print(f"\n🔧 Instruments for {exchange}:")
        print(self._format_result(result))
        return result
    
    async def get_quote(self, instruments: list):
        """Get quote for instruments."""
        result = await self.call_tool("get_quote", {"instruments": instruments})
        print(f"\n💹 Quote:")
        print(self._format_result(result))
        return result
    
    async def place_order(self, **order_params):
        """
        Place an order.
        
        Example params:
            tradingsymbol="INFY",
            exchange="NSE",
            transaction_type="BUY",
            quantity=1,
            order_type="MARKET",
            product="CNC"
        """
        result = await self.call_tool("place_order", order_params)
        print("\n✅ Order placed:")
        print(self._format_result(result))
        return result
    
    async def list_available_tools(self):
        """List all available tools from the MCP server."""
        try:
            if hasattr(self.client, 'list_tools'):
                tools = await self.client.list_tools()
                print("\n🔧 Available Tools:")
                for tool in tools:
                    tool_name = tool.name if hasattr(tool, 'name') else str(tool)
                    print(f"  • {tool_name}")
                return tools
            else:
                print("⚠️  Tool listing not available")
                return None
        except Exception as e:
            print(f"❌ Error listing tools: {e}")
            return None


async def interactive_mode():
    """Run interactive mode for testing various commands."""
    async with KiteMCPClient() as kite:
        # Login first
        if not await kite.login():
            print("Failed to login. Exiting.")
            return
        
        print("\n" + "="*60)
        print("🚀 Kite MCP Interactive Mode")
        print("="*60)
        print("\nAvailable commands:")
        print("  1. holdings     - Get your holdings")
        print("  2. positions    - Get your positions")
        print("  3. orders       - Get all orders")
        print("  4. trades       - Get all trades")
        print("  5. quote        - Get quote for a symbol")
        print("  6. tools        - List all available tools")
        print("  7. custom       - Call a custom tool")
        print("  0. exit         - Exit the program")
        print()
        
        while True:
            try:
                choice = input("\n💡 Enter command number or name: ").strip().lower()
                
                if choice in ['0', 'exit', 'quit']:
                    print("👋 Goodbye!")
                    break
                
                elif choice in ['1', 'holdings']:
                    await kite.get_holdings()
                
                elif choice in ['2', 'positions']:
                    await kite.get_positions()
                
                elif choice in ['3', 'orders']:
                    await kite.get_orders()
                
                elif choice in ['4', 'trades']:
                    await kite.get_trades()
                
                elif choice in ['6', 'tools']:
                    await kite.list_available_tools()
                
                elif choice in ['7', 'custom']:
                    tool_name = input("Enter tool name: ").strip()
                    params_str = input("Enter params as JSON (or leave empty): ").strip()
                    params = json.loads(params_str) if params_str else {}
                    result = await kite.call_tool(tool_name, params)
                    print("\n📤 Result:")
                    print(kite._format_result(result))
                
                else:
                    print("❌ Invalid command. Try again.")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")


async def example_usage():
    """Example of programmatic usage."""
    async with KiteMCPClient() as kite:
        # Login
        if not await kite.login():
            return
        
        # Get holdings
        await kite.get_holdings()
        
        # Get positions
        await kite.get_positions()
        
        # Get orders
        await kite.get_orders()
        
        # Custom tool call
        result = await kite.call_tool("get_profile")
        print("\n👤 Profile:")
        print(kite._format_result(result))


if __name__ == "__main__":
    import sys
    
    print("🎯 Kite MCP Client")
    print("="*60)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--example":
        print("Running example usage...\n")
        asyncio.run(example_usage())
    else:
        print("Running interactive mode...\n")
        asyncio.run(interactive_mode())
