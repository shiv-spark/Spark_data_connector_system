"""
Schema Manager for Text-to-SQL Agent

Manages schema loading, business context integration, and schema change detection.
Uses business_context.json from AGENT/metadata folder.
"""

import sys
import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Tuple, Optional

# Add AGENT path to import metadata modules
AGENT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "AGENT")
sys.path.insert(0, AGENT_PATH)

from snowflake_config import SNOWFLAKE_CONFIG
import snowflake.connector

# Import foreign keys extraction from AGENT module
from metadata.foreign_keys import get_foreign_keys

# Paths
BUSINESS_CONTEXT_PATH = os.path.join(AGENT_PATH, "metadata", "business_context.json")
SCHEMA_CATALOG_PATH = os.path.join(AGENT_PATH, "metadata", "schema_catalog.json")
SCHEMA_HASH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".schema_hash")


class SchemaManager:
    """
    Manages database schema with business context integration.
    
    Features:
    - Loads enriched schema from Snowflake
    - Integrates business_context.json for better SQL generation
    - Detects schema changes and triggers business context regeneration
    - Caches schema hash for quick change detection
    """
    
    def __init__(self):
        self.config = SNOWFLAKE_CONFIG
        self.business_context = {}
        self.schema_cache = {}
        self.current_hash = None
        
    def _get_connection(self):
        """Get Snowflake connection."""
        return snowflake.connector.connect(
            user=self.config["user"],
            password=self.config["password"],
            account=self.config["account"],
            warehouse=self.config["warehouse"],
            database=self.config["database"],
            schema=self.config["schema"]
        )
    




    def compute_schema_hash(self, schema_info: dict) -> str:
        """
        Compute a hash of the schema for change detection.
        
        Args:
            schema_info: Dictionary with schema information
            
        Returns:
            MD5 hash string of the schema
        """
        # Create a consistent string representation
        schema_str = json.dumps(schema_info, sort_keys=True, default=str)
        return hashlib.md5(schema_str.encode()).hexdigest()
    




    def load_schema_hash(self) -> Optional[str]:
        """Load the cached schema hash from file."""
        if os.path.exists(SCHEMA_HASH_FILE):
            try:
                with open(SCHEMA_HASH_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get('hash')
            except Exception:
                return None
        return None
    




    def save_schema_hash(self, hash_value: str):
        """Save the current schema hash to file."""
        try:
            with open(SCHEMA_HASH_FILE, 'w') as f:
                json.dump({
                    'hash': hash_value,
                    'timestamp': datetime.now().isoformat()
                }, f)
        except Exception as e:
            print(f"Warning: Could not save schema hash: {e}")
    




    def load_business_context(self) -> dict:
        """
        Load business_context.json from AGENT/metadata folder.
        
        Returns:
            Dictionary with business context or empty dict if not found
        """
        if os.path.exists(BUSINESS_CONTEXT_PATH):
            try:
                with open(BUSINESS_CONTEXT_PATH, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load business_context.json: {e}")
        else:
            print(f"Warning: business_context.json not found at {BUSINESS_CONTEXT_PATH}")
            print("Run AGENT/metadata/generate_business_context.py to generate it.")
        
        return {}
    




    def extract_raw_schema(self) -> dict:
        """
        Extract raw schema from Snowflake.
        
        Returns:
            Dictionary with tables, columns, and data types
        """
        conn = None
        try:
            conn = self._get_connection()
            cur = conn.cursor()
            
            # Get all tables and columns
            query = """
                SELECT
                    table_name,
                    column_name,
                    data_type,
                    is_nullable
                FROM information_schema.columns
                WHERE table_schema = CURRENT_SCHEMA()
                ORDER BY table_name, ordinal_position
            """
            
            cur.execute(query)
            rows = cur.fetchall()
            
            schema_info = {}
            for table_name, column_name, data_type, is_nullable in rows:
                if table_name not in schema_info:
                    schema_info[table_name] = {
                        'columns': {},
                        'column_list': []
                    }
                
                schema_info[table_name]['columns'][column_name] = {
                    'data_type': data_type,
                    'nullable': is_nullable
                }
                schema_info[table_name]['column_list'].append(column_name)
            
            return schema_info
            
        except Exception as e:
            print(f"Error extracting schema: {e}")
            return {}
        finally:
            if conn:
                conn.close()
    





    def extract_foreign_keys(self) -> dict:
        """
        Extract foreign key relationships from Snowflake.
        
        Note: FK extraction is optional. If it fails, we continue without FK info.
        Uses AGENT/metadata/foreign_keys.py for extraction.
        
        Returns:
            Dictionary with FK relationships or empty dict if not available
            Format: {fk_table.fk_column: pk_table.pk_column}
        """
        try:
            df = get_foreign_keys()
            
            fk_lookup = {}
            for _, row in df.iterrows():
                key = f"{row['TABLE_NAME']}.{row['COLUMN_NAME']}"
                fk_lookup[key] = f"{row['REFERENCED_TABLE']}.{row['REFERENCED_COLUMN']}"
            
            return fk_lookup
            
        except Exception:
            # FK extraction is optional - don't fail the whole process
            return {}
    





    def build_enriched_schema(self) -> Tuple[str, dict]:
        """
        Build enriched schema text and dictionary with business context.
        
        Returns:
            Tuple of (schema_text, schema_dict)
            - schema_text: Human-readable schema with business context
            - schema_dict: Dictionary mapping tables to column sets for validation
        """
        # Load business context
        business_context = self.load_business_context()
        tables_context = business_context.get('tables', {})
        relationships = business_context.get('relationships', {})
        global_context = business_context.get('global_context', {})
        
        # Extract current schema from database
        raw_schema = self.extract_raw_schema()
        fk_lookup = self.extract_foreign_keys()
        
        # Check for schema changes
        current_hash = self.compute_schema_hash(raw_schema)
        cached_hash = self.load_schema_hash()
        
        if cached_hash and current_hash != cached_hash:
            print("\n⚠️  Schema change detected!")
            print(f"   Previous hash: {cached_hash[:8]}...")
            print(f"   Current hash:  {current_hash[:8]}...")
            print("\n   Please run: python AGENT/metadata/generate_business_context.py")
            print("   to regenerate business_context.json with the updated schema.")
        
        # Save current hash
        self.save_schema_hash(current_hash)
        
        # Build enriched schema
        schema_parts = []
        schema_dict = {}
        
        # Add global context at the top
        if global_context:
            schema_parts.append("=" * 60)
            schema_parts.append("DATABASE CONTEXT")
            schema_parts.append("=" * 60)
            for key, value in global_context.items():
                schema_parts.append(f"{key}: {value}")
            schema_parts.append("")
        
        # Add database info
        schema_parts.append(f"Database: {self.config['database']}")
        schema_parts.append(f"Schema: {self.config['schema']}")
        schema_parts.append("")
        
        # Process each table
        for table_name in sorted(raw_schema.keys()):
            table_info = raw_schema[table_name]
            schema_dict[table_name] = set(table_info['column_list'])
            
            # Get business context for this table
            table_context = tables_context.get(table_name, {})
            
            schema_parts.append("-" * 60)
            schema_parts.append(f"Table: {table_name}")
            
            # Add table description and use case
            if table_context.get('description'):
                schema_parts.append(f"  Description: {table_context['description']}")
            if table_context.get('use_case'):
                schema_parts.append(f"  Use Case: {table_context['use_case']}")
            
            schema_parts.append("  Columns:")
            
            # Process each column
            columns_context = table_context.get('columns', {})
            for col_name in table_info['column_list']:
                col_info = table_info['columns'][col_name]
                data_type = col_info['data_type']
                nullable = "NULL" if col_info['nullable'] == 'YES' else "NOT NULL"
                
                # Get business context for column
                col_context = columns_context.get(col_name, "")
                
                # Build column description
                col_desc = f"    - {col_name} ({data_type}, {nullable})"
                if col_context:
                    col_desc += f" | {col_context}"
                
                # Add FK reference if exists
                fk_key = f"{table_name}.{col_name}"
                if fk_key in fk_lookup:
                    col_desc += f" [FK -> {fk_lookup[fk_key]}]"
                
                schema_parts.append(col_desc)
            
            schema_parts.append("")
        
        # Add relationships section
        if relationships:
            schema_parts.append("=" * 60)
            schema_parts.append("TABLE RELATIONSHIPS")
            schema_parts.append("=" * 60)
            for rel_key, rel_desc in relationships.items():
                schema_parts.append(f"  {rel_key}: {rel_desc}")
            schema_parts.append("")
        
        schema_text = "\n".join(schema_parts)
        
        print(f"\n✓ Loaded schema with {len(raw_schema)} tables")
        if tables_context:
            print(f"✓ Business context loaded with {len(tables_context)} tables")
        else:
            print("⚠️  No business context found - using raw schema only")
        
        return schema_text, schema_dict
    





    def check_and_regenerate_business_context(self, force: bool = False) -> bool:
        """
        Check if schema has changed and regenerate business context if needed.
        
        Args:
            force: If True, regenerate even if no changes detected
            
        Returns:
            True if regeneration was triggered, False otherwise
        """
        raw_schema = self.extract_raw_schema()
        current_hash = self.compute_schema_hash(raw_schema)
        cached_hash = self.load_schema_hash()
        
        if force or not cached_hash or current_hash != cached_hash:
            print("\n" + "=" * 60)
            print("SCHEMA CHANGE DETECTED")
            print("=" * 60)
            print(f"Schema hash changed: {cached_hash[:8] if cached_hash else 'None'} → {current_hash[:8]}")
            print("\nRegenerating business_context.json...")
            
            # Run the business context generator
            try:
                # Import and run the generator
                sys.path.insert(0, AGENT_PATH)
                from metadata.generate_business_context import (
                    collect_schema_info,
                    generate_business_context,
                    save_business_context
                )
                
                schema_info = collect_schema_info()
                context = generate_business_context(schema_info)
                save_business_context(context)
                
                # Rebuild schema_catalog.json with updated business context
                try:
                    from metadata.catalog_builder import build_catalog
                    catalog = build_catalog()
                    with open(SCHEMA_CATALOG_PATH, "w") as f:
                        json.dump(catalog, f, indent=4)
                    print(f"✓ Schema catalog rebuilt → {SCHEMA_CATALOG_PATH}")
                except Exception as e:
                    print(f"Warning: Could not rebuild schema_catalog.json: {e}")
                
                # Save new hash
                self.save_schema_hash(current_hash)
                
                print("\n✓ Business context regenerated successfully!")
                return True
                
            except Exception as e:
                print(f"\n✗ Failed to regenerate business context: {e}")
                return False
        
        return False






def get_enriched_schema() -> Tuple[str, dict]:
    """
    Convenience function to get enriched schema.
    
    Returns:
        Tuple of (schema_text, schema_dict)
    """
    manager = SchemaManager()
    return manager.build_enriched_schema()






def check_schema_changes() -> bool:
    """
    Check if schema has changed and regenerate business context if needed.
    
    Returns:
        True if business context was regenerated, False otherwise
    """
    manager = SchemaManager()
    return manager.check_and_regenerate_business_context()


\


if __name__ == "__main__":
    print("=" * 60)
    print("Schema Manager Test")
    print("=" * 60)
    
    manager = SchemaManager()
    
    # Test schema loading
    print("\n1. Testing schema loading with business context...")
    schema_text, schema_dict = manager.build_enriched_schema()
    
    print("\n2. Schema Preview:")
    print(schema_text[:1500] + "..." if len(schema_text) > 1500 else schema_text)
    
    print("\n3. Schema Dictionary:")
    for table, columns in list(schema_dict.items())[:3]:
        print(f"  {table}: {columns}")
    
    print("\n4. Checking for schema changes...")
    regenerated = manager.check_and_regenerate_business_context()
    if regenerated:
        print("   Business context was regenerated!")
    else:
        print("   No changes detected.")
    
    print("\n" + "=" * 60)
    print("Test complete!")
