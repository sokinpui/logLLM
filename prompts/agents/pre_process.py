def interpre_event_prompt(event, files):
    # get the unique value only
    applications = set([file.belongs_to for file in files])

    return f"""
    ## Trace this Event: {event}

    ### Context Analysis Framework
    - Chronological Perspective:
      - What is the precise timeline of events?
      - Are there any temporal patterns or anomalies?

    - System Interaction Perspective:
      - Which system components or applications are potentially involved?
      - What are the interaction points between these components?

    - Causality Perspective:
      - What might be the root cause of this event?
      - Are there precursor events or conditions that could have triggered this?

    - Impact Assessment:
      - What is the potential scope of impact?
      - Are there cascading effects on other system components?

    ### Available System Applications
    {applications}

    ### Task Objectives
    1. Identify critical information needed to trace the event comprehensively
    2. Determine the most relevant applications for investigation
    3. Propose potential investigation paths

    ### Deliverable Requirements
    - Provide a structured breakdown of required tracing information
    - List applications that are most likely to contain relevant log entries
    - Suggest key patterns or keywords for log search

    ### Analytical Constraints
    - Focus on actionable and verifiable information
    - Prioritize evidence-based reasoning
    - Consider multiple hypothetical scenarios
    """


def filter_logs(event, info_for_tracing, apps, sample):
    return f"""
# Elasticsearch Log Search Query Generation

## Objective
Generate a precise, flexible Elasticsearch query targeting log entry content with the following constraints:

### Search Context
- Event: {event}
- Tracing Information: {info_for_tracing}
- Relevant Applications: {apps}

## Query Generation Guidelines
- before generation, you should first think about what should be focus in the search
- try to avoid noise in the search result

### Core Principles
1. Focus exclusively on the "content" field
2. Balance precision with comprehensive matching
3. Use a combination of query types for robust search

### Query Structure Template
```json
{{
    "query": {{
        "bool": {{
            "should": [
                // Flexible matching conditions
            ],
            "minimum_should_match": "x%"
        }}
    }}
}}
```

### Matching Strategies
1. **Phrase Matching** (`match_phrase`)
   - Use for exact, ordered sequence matching
   - Preserve precise word order and context
   - Example: Match "user login failure"
   - when order and proximity are critical

2. **Token-Based Matching** (`match`)
   - Support flexible, tokenized search
   - Good for partial matches and relevance scoring
   - Example: Match variations of login-related terms
   - regardless of their order or proximity.

### Refinement Techniques
- Include multiple `should` conditions to increase match probability, if needed, you can combine `must`[AND logic] or `must_not` to enhance precise
- at least 15 to ensure relevance
- try to match different variations of the same concept
- the pattern should not be too simple to avoid false positives
- use `minimum_should_match` to control matching flexibility, around 40% to ensure relevance
- try to use different query types to cover a wide range of log entry structures

### Sample Log Context
{sample}

## Output Requirements
- Provide a JSON-formatted Elasticsearch boolean query
- Ensure query targets ONLY the "content" field
- Maintain clear, logical query structure
"""

def search_feedback_prompt(hits, total_docs, query, event, message):
    if hits/total_docs < 0.01:
        return f"""
    - tracing this event: {event}
    - the information that is searched from the database: {message}
    - search query using: {query}

    ## your task
    since the hits rate is less than 1%, the search query is too narrow, consider expanding the search context to include more relevant log entries, need to search again.
    - you can provide tips for improvement
    """

    elif hits/total_docs > 0.9:
        return f"""
    - tracing this event: {event}
    - the information that is searched from the database: {message}
    - search query using: {query}

    ## your task
    since the hits rate is more than 90%, the search query is too broad, consider refining the search context to focus on more specific log entries, need to search again.
    - you can provide tips for improvement
    """

    else:
        return f"""
        - tracing this event: {event}
        - the information that is searched from the database: {message}
        - search query using: {query}

        ## your task

        since the hits rate is acceptable, no search is needed again
        - provide feedback on the search results
        - suggest potential improvements to the search query
        - consider the balance between precision and recall
        """



def main():
    from collector import Collector

    dir = "../../../log"
    collector = Collector(dir=dir)
    files = collector.collect_logs(dir)

    event = "The system is down"

    print(interpre_event_prompt(event, files))

if __name__ == "__main__":
    main()

