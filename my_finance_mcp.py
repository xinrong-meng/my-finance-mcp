#!/usr/bin/env python3
"""
Bare minimum MCP server for financial data storage and RAG queries.
Usage: uv run my_finance_mcp.py
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

import chromadb
from mcp.server.fastmcp import FastMCP
import pandas as pd

# Initialize FastMCP server
mcp = FastMCP("my-finance")

# Persistent storage paths
DATA_DIR = Path(os.environ.get("MY_FINANCE_MCP_DIR", Path.home() / ".my_finance_mcp"))
DB_PATH = DATA_DIR / "financial_data"
JSON_FILE = DATA_DIR / "transactions.json"
DB_PATH.mkdir(parents=True, exist_ok=True)

# Global data
chroma_client = chromadb.PersistentClient(path=str(DB_PATH))
collection = chroma_client.get_or_create_collection("transactions")


@mcp.tool()
def store_transactions(transactions: List[Dict[str, Any]]) -> str:
    """
    Parse and store transaction data from uploaded financial documents.
    
    If you receive unstructured financial data (statements, receipts, CSV files, etc.),
    extract transactions into the format: [{"date": "YYYY-MM-DD", "amount": number, "description": "string", "category": "string"}]
    
    Args:
        transactions: List of transaction dictionaries, each containing:
            - date: Transaction date (string, format: YYYY-MM-DD)
            - amount: Transaction amount (number, can be negative for expenses)
            - description: Transaction description (string)
            - category: Transaction category (string, optional, e.g. "Food", "Transport", "Bills")
    
    Returns:
        Success message with count of stored transactions
    """
    # Store in ChromaDB
    ids = []
    documents = []
    metadatas = []
    
    for i, txn in enumerate(transactions):
        txn_id = f"txn_{datetime.now().timestamp()}_{i}"
        doc = f"Date: {txn.get('date')} Amount: {txn.get('amount')} Description: {txn.get('description')} Category: {txn.get('category', 'unknown')}"
        
        ids.append(txn_id)
        documents.append(doc)
        metadatas.append(txn)
    
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas
    )
    
    # Also save to JSON file
    if JSON_FILE.exists():
        with JSON_FILE.open('r') as f:
            existing = json.load(f)
    else:
        existing = []

    existing.extend(transactions)

    with JSON_FILE.open('w') as f:
        json.dump(existing, f, indent=2)
    
    return f"Stored {len(transactions)} transactions successfully"


@mcp.tool()
def query_financial_history(query: str) -> str:
    """
    Search through all stored financial data using semantic search.
    
    Args:
        query: Search query string to find relevant transactions
    
    Returns:
        Formatted summary of matching transactions with totals
    """
    # Search ChromaDB
    results = collection.query(
        query_texts=[query],
        n_results=10
    )
    
    # Format results
    found_transactions = []
    if results['metadatas'][0]:
        for metadata in results['metadatas'][0]:
            found_transactions.append(metadata)
    
    # Create summary
    if found_transactions:
        df = pd.DataFrame(found_transactions)
        total_amount = df['amount'].sum() if 'amount' in df.columns else 0
        count = len(found_transactions)
        
        response = f"Found {count} relevant transactions.\n"
        response += f"Total amount: ${total_amount:.2f}\n\n"
        response += "Recent transactions:\n"
        
        for txn in found_transactions[:5]:
            response += f"- {txn.get('date')}: ${txn.get('amount'):.2f} - {txn.get('description')}\n"
            
    else:
        response = "No matching transactions found."
    
    return response


if __name__ == "__main__":
    mcp.run()
