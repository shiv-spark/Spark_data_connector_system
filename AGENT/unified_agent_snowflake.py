

import sys
import os
import uuid
import time

# =============================================================================
# PATH SETUP - Add both agent paths
# =============================================================================

# Get the base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Add paths
TEXT_SQL_PATH = os.path.join(BASE_DIR, "text-sql")
AGENT_PATH = os.path.join(BASE_DIR, "AGENT")

sys.path.insert(0, TEXT_SQL_PATH)
sys.path.insert(0, AGENT_PATH)

# =============================================================================
# IMPORTS - Text-to-SQL Components (Snowflake version with Business Context)
# =============================================================================

try:
    from schema_manager import SchemaManager, get_enriched_schema, check_schema_changes
    from snowflake_executor import SnowflakeExecutor
    from snowflake_metadata_logger import SnowflakeMetadataLogger
    from sql_agent import SQLAgent
    from sql_validator import clean_sql, validate_sql
    from snowflake_config import MODEL_NAME, SNOWFLAKE_CONFIG
    TEXT_SQL_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import text-sql components: {e}")
    TEXT_SQL_AVAILABLE = False

# =============================================================================
# IMPORTS - ETL Pipeline Components
# =============================================================================

try:
    from Pipeline.pipeline_store import load_all_pipelines, load_pipeline, save_pipeline
    from Pipeline.pipeline_executor import execute_pipeline
    from Pipeline.pipeline_parser import parse_pipeline_prompt
    from Pipeline.pipeline_builder import build_execution_plan
    from Pipeline.pipeline_validator import validate_pipeline
    PIPELINE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import pipeline components: {e}")
    PIPELINE_AVAILABLE = False

# =============================================================================
# IMPORTS - Data Generation Components
# =============================================================================

try:
    from generator.prompt_parser import parse_prompt as parse_generation_prompt
    from generator.fake_generator import generate_data
    import generator.csv_writer as csv_writer_module
    from generator.csv_writer import save_csv
    from generator.loader import load_to_snowflake, verify_load
    GENERATION_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import data generation components: {e}")
    GENERATION_AVAILABLE = False

# =============================================================================
# UNIFIED AGENT CLASS
# =============================================================================

class UnifiedAgent:
    """
    Unified Agent that handles:
    - SQL queries (natural language to Snowflake)
    - ETL pipelines (create, list, execute)
    - Data generation (synthetic data)
    """
    
    def __init__(self):
        self.sql_agent = None
        self.sql_executor = None
        self.sql_logger = None
        self.schema_text = None
        self.schema_dict = None
        self._init_sql_components()
    
    def _init_sql_components(self):
        """Initialize SQL-related components if available."""
        if not TEXT_SQL_AVAILABLE:
            return
        
        try:
            print("Initializing Snowflake Text-to-SQL components...")
            print("Checking for schema changes and loading business context...")
            
            # Check for schema changes and regenerate business context if needed
            schema_manager = SchemaManager()
            regenerated = schema_manager.check_and_regenerate_business_context()
            
            if regenerated:
                print("✓ Business context regenerated with updated schema")
            
            # Load enriched schema with business context
            self.schema_text, self.schema_dict = get_enriched_schema()
            
            if self.schema_text:
                self.sql_agent = SQLAgent(
                    schema_text=self.schema_text,
                    schema_dict=self.schema_dict
                )
                self.sql_executor = SnowflakeExecutor()
                self.sql_logger = SnowflakeMetadataLogger()
                print("✓ Snowflake Text-to-SQL initialized successfully")
            else:
                print("Warning: Could not load Snowflake schema.")
        except Exception as e:
            print(f"Error initializing SQL components: {e}")
    
    # =========================================================================
    # SQL MODE
    # =========================================================================
    
    def run_sql_mode(self):
        """Run interactive SQL query mode."""
        if not TEXT_SQL_AVAILABLE or not self.sql_agent:
            print("Text-to-SQL components not available.")
            return
        
        print("\n" + "=" * 60)
        print("SQL MODE - Ask questions about your Snowflake database")
        print("Connected to: {}".format(SNOWFLAKE_CONFIG.get("database", "Unknown")))
        print("Type 'back' to return to main menu")
        print("=" * 60)
        
        while True:
            question = input("\n[SQL] Ask a question: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ["back", "exit", "quit", "q"]:
                break
            
            self._process_sql_query(question)
    
    def _process_sql_query(self, question):
        """Process a single SQL query."""
        try:
            from tabulate import tabulate
        except ImportError:
            print("Warning: tabulate not installed. Results will be displayed as lists.")
            tabulate = None
        
        run_id = str(uuid.uuid4())
        print("\nGenerating SQL...")
        
        try:
            generated = self.sql_agent.run(question)
        except Exception as e:
            print(f"\nError: {str(e)}")
            self._log_sql_error(run_id, question, str(e))
            return
        
        prompt_tokens = generated.get("prompt_tokens", 0)
        completion_tokens = generated.get("completion_tokens", 0)
        total_tokens = generated.get("total_tokens", 0)
        llm_latency = generated.get("llm_latency", 0)
        
        if not generated["success"]:
            print("\nThis request is currently not supported.")
            print(generated["message"])
            self._log_sql_failure(run_id, question, generated["message"], 
                                 prompt_tokens, completion_tokens, total_tokens, llm_latency)
            return
        
        sql = generated["sql"]
        print("\nGenerated SQL:")
        print("=" * 60)
        print(sql)
        print("=" * 60)
        
        approval = input("\nExecute this query? (yes/no): ").strip().lower()
        if approval not in ["y", "yes"]:
            print("Query execution cancelled.")
            self._log_sql_cancelled(run_id, question, sql, 
                                     prompt_tokens, completion_tokens, total_tokens, llm_latency)
            return
        
        print("\nExecuting query on Snowflake...")
        execution_start = time.time()
        result = self.sql_executor.execute(sql)
        execution_latency = round(time.time() - execution_start, 2)
        
        if not result["success"]:
            print("\nQuery execution failed.")
            print(result["error"])
            self._log_sql_execution_error(run_id, question, sql, result["error"],
                                         prompt_tokens, completion_tokens, total_tokens, 
                                         llm_latency, execution_latency)
            return
        
        rows = result["rows"]
        columns = result["columns"]
        
        print(f"\nReturned {len(rows)} rows.")
        
        # Generate summary
        summary = None
        try:
            sample_rows = rows[:20]
            summary = self.sql_agent.summarize_result(
                question=question, sql=sql, result=sample_rows
            )
            print("\nSummary:")
            print("=" * 60)
            print(summary)
        except Exception as e:
            summary = "Query executed successfully."
            print("\nSummary: Query executed successfully.")
        
        # Display results
        print("\nResults:")
        print("=" * 60)
        if not rows:
            print("No records found.")
        else:
            if tabulate:
                print(tabulate(rows, headers=columns, tablefmt="grid"))
            else:
                # Fallback if tabulate not available
                print(", ".join(columns))
                for row in rows[:20]:  # Limit to 20 rows
                    print(", ".join(str(col) for col in row))
                if len(rows) > 20:
                    print(f"... and {len(rows) - 20} more rows")
        
        self._log_sql_success(run_id, question, sql, len(rows), summary,
                             prompt_tokens, completion_tokens, total_tokens, 
                             llm_latency, execution_latency)
        print("\n" + "=" * 60)
    

    
    def _log_sql_error(self, run_id, question, error):
        if self.sql_logger:
            self.sql_logger.insert_run({
                "run_id": run_id, "user_question": question, "generated_sql": None,
                "validation_status": "FAILED", "execution_approved": False,
                "execution_status": "NOT_EXECUTED", "row_count": 0,
                "model_name": MODEL_NAME, "prompt_tokens": 0, "completion_tokens": 0,
                "total_tokens": 0, "llm_latency_seconds": 0, "execution_latency_seconds": 0,
                "response_summary": None, "error_message": error
            })
    
    def _log_sql_failure(self, run_id, question, message, prompt_tokens, completion_tokens, total_tokens, llm_latency):
        if self.sql_logger:
            self.sql_logger.insert_run({
                "run_id": run_id, "user_question": question, "generated_sql": None,
                "validation_status": "FAILED", "execution_approved": False,
                "execution_status": "NOT_EXECUTED", "row_count": 0,
                "model_name": MODEL_NAME, "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens, "total_tokens": total_tokens,
                "llm_latency_seconds": llm_latency, "execution_latency_seconds": 0,
                "response_summary": None, "error_message": message
            })
    
    def _log_sql_cancelled(self, run_id, question, sql, prompt_tokens, completion_tokens, total_tokens, llm_latency):
        if self.sql_logger:
            self.sql_logger.insert_run({
                "run_id": run_id, "user_question": question, "generated_sql": sql,
                "validation_status": "VALID", "execution_approved": False,
                "execution_status": "CANCELLED", "row_count": 0,
                "model_name": MODEL_NAME, "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens, "total_tokens": total_tokens,
                "llm_latency_seconds": llm_latency, "execution_latency_seconds": 0,
                "response_summary": None, "error_message": None
            })
    
    def _log_sql_execution_error(self, run_id, question, sql, error, prompt_tokens, completion_tokens, total_tokens, llm_latency, execution_latency):
        if self.sql_logger:
            self.sql_logger.insert_run({
                "run_id": run_id, "user_question": question, "generated_sql": sql,
                "validation_status": "VALID", "execution_approved": True,
                "execution_status": "FAILED", "row_count": 0,
                "model_name": MODEL_NAME, "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens, "total_tokens": total_tokens,
                "llm_latency_seconds": llm_latency, "execution_latency_seconds": execution_latency,
                "response_summary": None, "error_message": error
            })
    
    def _log_sql_success(self, run_id, question, sql, row_count, summary, prompt_tokens, completion_tokens, total_tokens, llm_latency, execution_latency):
        if self.sql_logger:
            self.sql_logger.insert_run({
                "run_id": run_id, "user_question": question, "generated_sql": sql,
                "validation_status": "VALID", "execution_approved": True,
                "execution_status": "SUCCESS", "row_count": row_count,
                "model_name": MODEL_NAME, "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens, "total_tokens": total_tokens,
                "llm_latency_seconds": llm_latency, "execution_latency_seconds": execution_latency,
                "response_summary": summary, "error_message": None
            })
    
    # =========================================================================
    # PIPELINE MODE
    # =========================================================================
    
    def run_pipeline_mode(self):
        """Run interactive pipeline management mode."""
        if not PIPELINE_AVAILABLE:
            print("Pipeline components not available.")
            return
        
        print("\n" + "=" * 60)
        print("PIPELINE MODE - list, and execute ETL pipelines")
        print("Commands: list, execute, back")
        print("=" * 60)
        
        while True:
            command = input("\n[PIPELINE] Enter command: ").strip().lower()
            
            if not command:
                continue
            
            if command in ["back", "exit", "quit", "q"]:
                break
            
            if command == "list":
                self._list_pipelines()
            elif command == "create":
                self._create_pipeline()
            elif command == "execute":
                self._execute_pipeline()
            elif command == "delete":
                self._delete_pipeline()
            else:
                print("Unknown command. Available: create, list, execute, delete, back")
    
    def _list_pipelines(self):
        """List all saved pipelines."""
        pipelines = load_all_pipelines()
        if not pipelines:
            print("\nNo pipelines found.")
            return
        
        print("\n" + "=" * 60)
        print("Saved Pipelines:")
        print("=" * 60)
        for name, config in pipelines.items():
            print(f"\n  {name}:")
            print(f"    Source: {config.get('source', 'N/A')}")
            print(f"    Target: {config.get('target', 'N/A')}")
            print(f"    Table: {config.get('table', 'N/A')}")
            print(f"    Schedule: {config.get('schedule', 'N/A')}")
    
    def _create_pipeline(self):
        """Create a new pipeline from natural language."""
        description = input("\nDescribe your pipeline (e.g., 'Create a daily ETL that moves orders from Snowflake to CSV'): ").strip()
        
        if not description:
            print("Pipeline description cannot be empty.")
            return
        
        try:
            print("\nGenerating pipeline configuration...")
            spec = parse_pipeline_prompt(description)
            
            print("\nGenerated Pipeline:")
            print("=" * 60)
            import json
            print(json.dumps(spec, indent=2))
            
            confirm = input("\nSave this pipeline? (yes/no): ").strip().lower()
            if confirm in ["y", "yes"]:
                save_pipeline(spec)
                print(f"Pipeline '{spec['pipeline_name']}' saved successfully!")
            else:
                print("Pipeline creation cancelled.")
        
        except Exception as e:
            print(f"\nError creating pipeline: {e}")
    
    def _execute_pipeline(self):
        """Execute a pipeline."""
        pipeline_name = input("\nEnter pipeline name to execute: ").strip()
        
        if not pipeline_name:
            print("Pipeline name cannot be empty.")
            return
        
        try:
            result = execute_pipeline(pipeline_name)
            print(f"\nPipeline '{pipeline_name}' executed successfully!")
            print(f"Rows processed: {result.get('rows_processed', 0)}")
            print(f"Duration: {result.get('duration_seconds', 0)}s")
        except Exception as e:
            print(f"\nError executing pipeline: {e}")
    
    def _delete_pipeline(self):
        """Delete a pipeline."""
        pipeline_name = input("\nEnter pipeline name to delete: ").strip()
        
        if not pipeline_name:
            print("Pipeline name cannot be empty.")
            return
        
        try:
            pipelines = load_all_pipelines()
            if pipeline_name in pipelines:
                confirm = input(f"Are you sure you want to delete '{pipeline_name}'? (yes/no): ").strip().lower()
                if confirm in ["y", "yes"]:
                    del pipelines[pipeline_name]
                    import json
                    with open("AGENT/Pipeline/pipelines.json", "w") as f:
                        json.dump(pipelines, f, indent=4)
                    print(f"Pipeline '{pipeline_name}' deleted.")
            else:
                print(f"Pipeline '{pipeline_name}' not found.")
        except Exception as e:
            print(f"\nError deleting pipeline: {e}")
    
    # =========================================================================
    # DATA GENERATION MODE
    # =========================================================================
    
    def run_generation_mode(self):
        """Run interactive data generation mode."""
        if not GENERATION_AVAILABLE:
            print("Data generation components not available.")
            return
        
        print("\n" + "=" * 60)
        print("GENERATE MODE - Generate synthetic data")
        print("Type 'back' to return to main menu")
        print("=" * 60)
        
        while True:
            description = input("\n[GEN] Describe data to generate (e.g., 'Generate 50 users with name, email'): ").strip()
            
            if not description:
                continue
            
            if description.lower() in ["back", "exit", "quit", "q"]:
                break
            
            self._generate_data(description)
    
    def _generate_data(self, description):
        """Generate synthetic data based on description."""
        try:
            print("\nParsing generation request...")
            config = parse_generation_prompt(description)
            
            print("\nConfiguration:")
            print(f"  Table: {config.get('table', 'N/A')}")
            print(f"  Rows: {config.get('rows', 0)}")
            print(f"  Locale: {config.get('locale', 'en_US')}")
            print(f"  Columns: {', '.join(config.get('columns', []))}")
            
            confirm = input("\nGenerate this data? (yes/no): ").strip().lower()
            if confirm not in ["y", "yes"]:
                print("Data generation cancelled.")
                return
            
            print("\nGenerating data...")
            df = generate_data(config)
            
            # Use a writable directory for CSV output
            writable_dir = os.path.join(BASE_DIR, "generated")
            os.makedirs(writable_dir, exist_ok=True)
            csv_writer_module.GENERATED_DIR = writable_dir
            
            # Save to CSV using save_csv function
            output_path = save_csv(df, config)
            
            print(f"\n✓ Successfully generated {len(df)} rows!")
            print(f"✓ Saved to: {output_path}")
            print("\nPreview (first 5 rows):")
            print(df.head().to_string())
            
            # Ask if user wants to load to Snowflake
            load_choice = input("\nLoad this data to Snowflake? (yes/no): ").strip().lower()
            if load_choice in ["y", "yes"]:
                print(f"\nLoading data to Snowflake table '{config['table']}'...")
                try:
                    total_rows = load_to_snowflake(output_path, config)
                    verify_load(config["table"], expected_rows=config["rows"])
                    print(f"✓ Successfully loaded into '{config['table']}' table!")
                    print(f"✓ Total rows in table: {total_rows}")
                except Exception as load_error:
                    print(f"✗ Error loading to Snowflake: {load_error}")
                    print("  Data is still saved in CSV file.")
            else:
                print("\nData not loaded to Snowflake (saved as CSV only)")
            
        except Exception as e:
            print(f"\nError generating data: {e}")


# =============================================================================
# MAIN MENU
# =============================================================================

def print_main_menu():
    """Print the main menu."""
    print("\n" + "=" * 60)
    print("UNIFIED AGENT - Snowflake Text-to-SQL + ETL Pipeline + Data Generation")
    print("=" * 60)
    print("\nAvailable Modes:")
    print("  1. SQL      - Ask questions about your Snowflake database")
    print("  2. PIPELINE - Create, list, and execute ETL pipelines")
    print("  3. GENERATE - Generate synthetic data")
    print("  4. EXIT     - Exit the application")
    print("\nEnter mode number or name:")


def main():
    """Main entry point for the unified agent."""
    print("\n" + "=" * 60)
    print("Welcome to Unified Agent!")
    print("Initializing...")
    
    agent = UnifiedAgent()
    
    while True:
        print_main_menu()
        choice = input("> ").strip().lower()
        
        if not choice:
            continue
        
        if choice in ["4", "exit", "quit", "q"]:
            print("\nGoodbye! Thanks for using Unified Agent.")
            break
        elif choice in ["1", "sql"]:
            agent.run_sql_mode()
        elif choice in ["2", "pipeline"]:
            agent.run_pipeline_mode()
        elif choice in ["3", "generate", "gen"]:
            agent.run_generation_mode()
        else:
            print("\nInvalid choice. Please enter 1-4 or the mode name.")


if __name__ == "__main__":
    main()
