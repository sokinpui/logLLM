def prompt(question: str, context: str) -> str:
    return f"""
    You are an assistant for question-answering tasks. Use the following pieces of retrieved context as supplementary information to help answer the question. You may also rely on your own knowledge to provide a comprehensive and accurate response. If the retrieved context is insufficient or irrelevant, prioritize your own knowledge. If you are unsure of the answer, simply state that you don't know.

    Question: {question}
    Context: {context}

    ---
    \n
    \n
    """
