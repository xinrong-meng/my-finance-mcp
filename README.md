# My Finance MCP Server

Bare-bones Model Context Protocol server that lets Claude store personal finance transactions and later query them via semantic search. Transactions are persisted in ChromaDB for vector search plus a JSON ledger for backup.

Run it alongside Claude Desktop and you get an AI bookkeeper that remembers your receipts, statements, and portfolios—then answers natural language questions about spending trends, allocations, or anything else you upload.

## Setup

### Install
```bash
uv sync
```

### Run
```bash
uv run my_finance_mcp.py
```

### Configure Claude Desktop
Add to `~/.claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "my-finance": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/my_finance",
        "/path/to/my_finance/my_finance_mcp.py"
      ]
    }
  }
}
```

## Usage

1. Upload financial data to Claude
2. Say: "Store this transaction data" 
3. Claude calls the MCP server to save it
4. Later ask: "How much did I spend on groceries last month?"
5. Claude searches your historical data via MCP

### Example Claude Desktop interaction
```
User: Remember these portfolio positions for later analysis.
Claude: I'll help you store your portfolio positions from the uploaded CSV file for later analysis. Let me read the file and process the data.
Claude (tool call): Store transactions
Claude: Perfect! I've stored your portfolio positions from November 6, 2025 in your finance system. Here's a summary of what was recorded:
...

The data is now stored and ready for later analysis. You can query this information anytime using natural language searches about your portfolio positions, performance, or allocation patterns.
```

## Data Storage
- `~/.my_finance_mcp/financial_data/` - ChromaDB vector database (created automatically)
- `~/.my_finance_mcp/transactions.json` - JSON backup of all transactions

Set the `MY_FINANCE_MCP_DIR` environment variable before launching Claude if you want to store data in a different directory.