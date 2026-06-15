from Pipeline.pipeline_parser import parse_pipeline_prompt
from Pipeline.pipeline_validator import validate_pipeline
from Pipeline.pipeline_store import save_pipeline


def create_pipeline_from_prompt(user_prompt):

    print("\nParsing prompt...")

    spec = parse_pipeline_prompt(
        user_prompt
    )

    print("Pipeline Spec Generated")

    validate_pipeline(spec)

    save_pipeline(spec)

    print(
        f"Pipeline Created: {spec['pipeline_name']}"
    )

    return spec


if __name__ == "__main__":

    prompt = """
    Create a daily ETL pipeline
    that moves supplier data from Snowflake
    to local file system every day at 2 AM
    """

    create_pipeline_from_prompt(prompt)