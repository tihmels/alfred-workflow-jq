#!./venv/bin/python

import json
import os
import subprocess
import sys
from hashlib import sha256
from workflow import Workflow


def validate_json(content):
    """Validate if the given content is valid JSON."""
    try:
        json.loads(content)
        return True
    except json.JSONDecodeError:
        return False


def pretty_print_json(jq_output):
    """Format JSON output with indentation for better readability."""
    try:
        parsed_json = json.loads(jq_output)
        return json.dumps(parsed_json, indent=4, ensure_ascii=False)
    except json.JSONDecodeError:
        return jq_output  # Return raw output if it's not JSON


def get_cache_key(content, query):
    """Generate a unique cache key based on content and query."""
    return sha256((content + query).encode("utf-8")).hexdigest()


def main(wf):
    # Fetch Alfred workflow variables from the environment
    clipboard_content = os.getenv("clipboard", "").strip()  # Fetch clipboard content
    jq_query = os.getenv("jq", ".").strip()  # Default jq query to "."

    # Ensure clipboard content is present
    if not clipboard_content:
        error_response("Clipboard is empty or not set.")
        return

    # If the jq query is empty after stripping, default to "."
    if not jq_query:
        jq_query = "."

    # Validate clipboard content as JSON
    if not validate_json(clipboard_content):
        error_response("Clipboard content is not valid JSON.")
        return

    # Generate cache key
    cache_key = get_cache_key(clipboard_content, jq_query)

    # Check cache for previous result
    cached_result = wf.cached_data(cache_key, max_age=60)  # Cache for 60 seconds
    if cached_result:
        print(cached_result)
        return

    # Attempt to process clipboard content using jq
    try:
        result = subprocess.run(
            ["jq", jq_query],
            input=clipboard_content,
            text=True,
            capture_output=True,
            check=True
        )
        jq_output = result.stdout.strip()
        error_message = None
    except subprocess.CalledProcessError as e:
        jq_output = ""
        error_message = e.stderr.strip()

    # Prepare Markdown-formatted JSON
    if error_message is None:
        jq_output = pretty_print_json(jq_output)
        formatted_output = f"```json\n{jq_output}\n```"
    else:
        formatted_output = f"```text\nError: {error_message}\n```"

    # Add footer with examples for jq queries
    footer_message = (
        f"jq query applied: {jq_query}\n"
        "Examples: '.key', '.[] | .name', 'map(select(.age > 30))'"
    )

    # Scroll behavior based on output length
    scroll_behavior = "end" if len(jq_output.splitlines()) > 10 else "auto"

    # Build response JSON for Alfred Text View
    response_json = {
        "variables": {
            "jq": jq_query,
            "clipboard": clipboard_content,
        },
        "response": formatted_output,
        "footer": footer_message,
        "behaviour": {
            "response": "replace",
            "scroll": scroll_behavior,
            "inputfield": "select",
        },
    }

    # Cache the result for repeated queries
    wf.cache_data(cache_key, json.dumps(response_json))

    # Output response JSON for Alfred
    print(json.dumps(response_json))


def error_response(message):
    """Send an error message to Alfred's Text View."""
    response_json = {
        "response": f"```text\nError: {message}\n```",
        "footer": "Ensure clipboard content and jq query are set correctly.",
        "behaviour": {
            "response": "replace",
            "scroll": "end",
            "inputfield": "select",
        },
    }
    print(json.dumps(response_json))


if __name__ == "__main__":
    wf = Workflow()
    sys.exit(wf.run(main))