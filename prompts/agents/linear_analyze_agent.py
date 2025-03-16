def chunk_analysis_prompt(event, message, memories, chunk):
    memory_stirng = "\n".join([m for m in memories])
    return f"""
## Task
Analyze the given chunk of text to trace the specified event,
using the provided message as a guideline. Focus on extracting information related to the event.
Provide a concise, informative response that includes:
1. Key details directly tied to the event.

Keep the response short, clear, and focused.

## Event to Trace
{event}

## Guideline Message
{message}
(This message highlights the key information to prioritize while analyzing the chunk.)

## Previous Analysis result
{memory_stirng}

## Text Chunk to Analyze
{chunk}
"""

def summarize_chunk_analysis_result(event, require_info, result):
    return f"""

"""

# def chunk_analysis_prompt(event, message, chunk):
#     return f"""
# ## Task
# Analyze the given chunk of text to trace the specified event,
# using the provided message as a guideline. Focus on extracting information related to the event.
# Provide a concise, informative response that includes:
# 1. Key details directly tied to the event.
# 2. Any additional relevant discoveries from the chunk, if present.
#
# Keep the response short, clear, and focused.
#
# ## Event to Trace
# {event}
#
# ## Guideline Message
# {message}
# (This message highlights the key information to prioritize while analyzing the chunk.)
#
# ## Text Chunk to Analyze
# {chunk}
# """
