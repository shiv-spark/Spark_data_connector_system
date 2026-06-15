"""
PostgreSQL Schema Manager for Text-to-SQL Agent

Manages schema loading and schema change detection for PostgreSQL.
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Tuple, Optional, Any, List
from .postgres_executor import PostgresExecutor
from .config import POSTGRES_CONFIG


class PostgresSchemaManager:
    """
    Manages database schema for PostgreSQL.
    
    Features:
    - Loads schema from PostgreSQL
    - Detects schema changes
    - Caches schema hash for quick change detection
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or POSTGRES_CONFIG
        self.executor = PostgresExecutor(config)
        self.schema_cache = {}
        self.current_hash = None
        
    def compute_schema_hash(self, schema_info: dict) -> str:
        """
        Compute a hash of the schema for change detection.
        
        Args:
            schema_info: Dictionary with schema information
            
        Returns:
            MD5 hash string of the schema
        """
        schema_str = json.dumps(schema_info, sort_keys=True, default=str)
        return hashlib.md5(schema_str.encode()).hexdigest()
    
    def extract_raw_schema(self) -> dict:
        """
        Extract raw schema from PostgreSQL.
        
        Returns:
            Dictionary with tables, columns, and data types
        """
        return self.executor.get_all_schemas()
    
    def extract_foreign_keys(self) -> dict:
        """
        Extract foreign key relationships from PostgreSQL.
        
        Returns:
            Dictionary with FK relationships
            Format: {table.column: referenced_table.referenced_column}
        """
        query = """
            SELECT
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS referenced_table,
                ccu.column_name AS referenced_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
        """
        
        result = self.executor.execute(query)
        fk_lookup = {}
        
        if result["success"]:
            for row in result["rows"]:
                table_name, column_name, ref_table, ref_column = row
                key = f"{table_name}.{column_name}"
                fk_lookup[key] = f"{ref_table}.{ref_column}"
        
        return fk_lookup
    
    def build_schema_text(self, tables: Optional[List[str]] = None) -> Tuple[str, dict]:
        """
        Build schema text and dictionary.
        
        Args:
            tables: Optional list of specific tables to include. If None, includes all tables.
        
        Returns:
            Tuple of (schema_text, schema_dict)
            - schema_text: Human-readable schema
            - schema_dict: Dictionary mapping tables to column sets for validation
        """
        raw_schema = self.extract_raw_schema()
        fk_lookup = self.extract_foreign_keys()
        
        # Filter tables if specified
        if tables:
            raw_schema = {k: v for k, v in raw_schema.items() if k in tables}
        
        # Build schema text
        schema_parts = []
        schema_dict = {}
        
        # Add database info
        schema_parts.append(f"Database: {self.config.get('database', 'postgres')}")
        schema_parts.append(f"Host: {self.config.get('host', 'localhost')}")
        schema_parts.append("")
        
        # Process each table
        for table_name in sorted(raw_schema.keys()):
            table_info = raw_schema[table_name]
            schema_dict[table_name] = set(table_info['column_list'])
            
            schema_parts.append("-" * 60)
            schema_parts.append(f"Table: {table_name}")
            schema_parts.append("  Columns:")
            
            for col_name in table_info['column_list']:
                col_info = table_info['columns'][col_name]
                data_type = col_info['data_type']
                nullable = "NULL" if col_info['nullable'] == 'YES' else "NOT NULL"
                
                col_desc = f"    - {col_name} ({data_type}, {nullable})"
                
                # Add FK reference if exists
                fk_key = f"{table_name}.{col_name}"
                if fk_key in fk_lookup:
                    col_desc += f" [FK -> {fk_lookup[fk_key]}]"
                
                schema_parts.append(col_desc)
            
            schema_parts.append("")
        
        schema_text = "\n".join(schema_parts)
        
        return schema_text, schema_dict
    
    def get_table_sample(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get sample rows from a table for better context.
        
        Args:
            table_name: Name of the table
            limit: Number of sample rows to fetch
        
        Returns:
            List of dictionaries representing sample rows
        """
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        result = self.executor.execute(query)
        
        if result["success"]:
            rows = []
            columns = result["columns"]
            for row_data in result["rows"]:
                row_dict = {}
                for i, col in enumerate(columns):
                    # Convert values to string for JSON serialization
                    value = row_data[i]
                    if value is None:
                        row_dict[col] = None
                    elif isinstance(value, (int, float, bool, str)):
                        row_dict[col] = value
                    else:
                        row_dict[col] = str(value)
                rows.append(row_dict)
            return rows
        
        return []
    
    def get_schema_with_samples(self, tables: Optional[List[str]] = None, sample_limit: int = 3) -> Tuple[str, dict]:
        """
        Build schema text with sample data for better LLM understanding.
        
        Args:
            tables: Optional list of specific tables to include
            sample_limit: Number of sample rows per table
        
        Returns:
            Tuple of (schema_text, schema_dict)
        """
        raw_schema = self.extract_raw_schema()
        fk_lookup = self.extract_foreign_keys()
        
        if tables:
            raw_schema = {k: v for k, v in raw_schema.items() if k in tables}
        
        schema_parts = []
        schema_dict = {}
        
        schema_parts.append(f"Database: {self.config.get('database', 'postgres')}")
        schema_parts.append("")
        
        for table_name in sorted(raw_schema.keys()):
            table_info = raw_schema[table_name]
            schema_dict[table_name] = set(table_info['column_list'])
            
            schema_parts.append("=" * 60)
            schema_parts.append(f"Table: {table_name}")
            schema_parts.append("-" * 60)
            schema_parts.append("Columns:")
            
            for col_name in table_info['column_list']:
                col_info = table_info['columns'][col_name]
                data_type = col_info['data_type']
                nullable = "NULL" if col_info['nullable'] == 'YES' else "NOT NULL"
                
                col_desc = f"  - {col_name} ({data_type}, {nullable})"
                
                fk_key = f"{table_name}.{col_name}"
                if fk_key in fk_lookup:
                    col_desc += f" [FK -> {fk_lookup[fk_key]}]"
                
                schema_parts.append(col_desc)
            
            # Add sample data
            samples = self.get_table_sample(table_name, sample_limit)
            if samples:
                schema_parts.append("")
                schema_parts.append(f"Sample Data ({len(samples)} rows):")
                for i, sample in enumerate(samples, 1):
                    sample_str = ", ".join([f"{k}={repr(v)[:50]}" for k, v in sample.items()])
                    schema_parts.append(f"  Row {i}: {sample_str}")
            
            schema_parts.append("")
        
        schema_text = "\n".join(schema_parts)
        return schema_text, schema_dict


def get_schema(tables: Optional[List[str]] = None, include_samples: bool = False) -> Tuple[str, dict]:
    """
    Convenience function to get schema.
    
    Args:
        tables: Optional list of specific tables to include
        include_samples: Whether to include sample data
    
    Returns:
        Tuple of (schema_text, schema_dict)
    """
    manager = PostgresSchemaManager()
    if include_samples:
        return manager.get_schema_with_samples(tables)
    return manager.build_schema_text(tables)


if __name__ == "__main__":
    print("=" * 60)
    print("PostgreSQL Schema Manager Test")
    print("=" * 60)
    
    manager = PostgresSchemaManager()
    
    # Test schema loading
    print("\n1. Testing schema loading...")
    schema_text, schema_dict = manager.build_schema_text()
    
    print("\n2. Schema Preview:")
    print(schema_text[:1500] + "..." if len(schema_text) > 1500 else schema_text)
    
    print("\n3. Schema Dictionary:")
    for table, columns in list(schema_dict.items())[:3]:
        print(f"  {table}: {columns}")
    
    # Test with samples
    print("\n4. Testing schema with samples...")
    schema_text_samples, _ = manager.get_schema_with_samples()
    print(schema_text_samples[:2000] + "..." if len(schema_text_samples) > 2000 else schema_text_samples)
    
    print("\n" + "=" * 60)
    print("Test complete!")
