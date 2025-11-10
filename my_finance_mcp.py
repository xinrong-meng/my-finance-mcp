#!/usr/bin/env python3
"""
Bare minimum MCP server for financial data storage and RAG queries.
Usage: uv run my_finance_mcp.py
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
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

# Helper utilities

def _load_transactions() -> List[Dict[str, Any]]:
    if JSON_FILE.exists():
        with JSON_FILE.open("r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def _save_transactions(transactions: List[Dict[str, Any]]) -> None:
    JSON_FILE.parent.mkdir(parents=True, exist_ok=True)
    with JSON_FILE.open("w") as f:
        json.dump(transactions, f, indent=2)

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
    existing = _load_transactions()
    existing.extend(transactions)
    _save_transactions(existing)
    
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


@mcp.tool()
def list_transactions(limit: int = 20, offset: int = 0, category: Optional[str] = None) -> Dict[str, Any]:
    """
    List stored transactions from the JSON ledger with optional pagination and filtering.

    Args:
        limit: Maximum number of transactions to return (default 20)
        offset: Number of transactions to skip from the beginning (default 0)
        category: Optional category filter (case-insensitive)

    Returns:
        Dictionary containing total count, pagination info, and transactions with index field
    """
    transactions = _load_transactions()

    indexed: List[Dict[str, Any]] = []
    for idx, txn in enumerate(transactions):
        if category and str(txn.get("category", "")).lower() != category.lower():
            continue
        entry = dict(txn)
        entry["index"] = idx
        indexed.append(entry)

    total = len(indexed)
    sliced = indexed[offset: offset + limit]

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "transactions": sliced,
        "has_more": offset + limit < total
    }


@mcp.tool()
def delete_transactions(indices: Optional[List[int]] = None, delete_all: bool = False, confirm: bool = False) -> str:
    """
    Delete transactions from both the JSON ledger and ChromaDB.

    Args:
        indices: List of transaction indices (from list_transactions) to delete
        delete_all: Set to true to delete all transactions
        confirm: Must be true to actually perform deletion (safety guard)

    Returns:
        Status message describing the deletion result
    """
    if not confirm:
        raise ValueError("Deletion aborted: set confirm=True to proceed.")

    transactions = _load_transactions()

    if delete_all:
        deleted_count = len(transactions)
        _save_transactions([])
        try:
            # Recreate the collection to ensure it is empty
            global collection
            chroma_client.delete_collection("transactions")
            collection = chroma_client.get_or_create_collection("transactions")
        except chromadb.errors.InvalidCollectionException:
            pass
        return f"Deleted {deleted_count} transactions." if deleted_count else "No transactions to delete."

    if not indices:
        raise ValueError("Provide indices to delete or set delete_all=True.")

    indices_set = set(indices)
    remaining: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []

    for idx, txn in enumerate(transactions):
        if idx in indices_set:
            removed.append(txn)
        else:
            remaining.append(txn)

    if not removed:
        return "No transactions matched the provided indices."

    _save_transactions(remaining)

    # Remove matching entries from ChromaDB using metadata filters
    for txn in removed:
        metadata_filter = {k: v for k, v in txn.items() if isinstance(k, str)}
        try:
            collection.delete(where=metadata_filter)
        except Exception:
            # If metadata-based delete fails, ignore but keep JSON consistent
            continue

    return f"Deleted {len(removed)} transactions."


if __name__ == "__main__":
    mcp.run()
